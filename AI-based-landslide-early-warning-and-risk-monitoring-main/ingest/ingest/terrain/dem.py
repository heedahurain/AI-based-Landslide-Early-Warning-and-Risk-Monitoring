"""Digital elevation model acquisition.

Source: Copernicus DEM GLO-30 through the Microsoft Planetary Computer STAC
API, verified reachable on 2026-09-08 with the `cop-dem-glo-30` collection
confirmed present. Anonymous access works; a free subscription key only raises
rate limits.

Tiles arrive as one-degree COGs at 3600 by 3600, float32, in EPSG:4326. They
are mosaicked, clipped to the region and reprojected to EPSG:32646, because
every slope, curvature and area computation downstream needs equal-area metres
rather than degrees. Computing a slope angle in degrees of longitude would be
wrong by the cosine of the latitude, and wrong slope means wrong factor of
safety.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject

from ingest.terrain.regions import Region

log = logging.getLogger(__name__)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEM_COLLECTION = "cop-dem-glo-30"
DEM_FALLBACK_COLLECTION = "cop-dem-glo-90"

# UTM zone 46N. Covers the region with acceptable distortion, and matches
# COMPUTATION_SRID in the API settings.
TARGET_CRS = "EPSG:32646"

# Copernicus DEM marks sea and voids with this value.
DEM_NODATA = -32767.0


def search_dem_items(region: Region, collection: str = DEM_COLLECTION) -> list[str]:
    """Return signed asset URLs for every DEM tile intersecting the region."""
    import planetary_computer
    import pystac_client

    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(collections=[collection], bbox=region.bbox)
    items = list(search.items())

    if not items:
        raise RuntimeError(
            f"No {collection} tiles returned for {region.key} {region.bbox}. "
            "The collection name or the bounding box is wrong."
        )

    log.info("dem.search", extra={"collection": collection, "tiles": len(items)})
    return [item.assets["data"].href for item in items]


# --------------------------------------------------------------------------
# Second elevation provider: AWS Terrain Tiles.
#
# The Copernicus tiles are the better source, being a genuine 30 m DSM in one
# piece. But the Planetary Computer blob host measured 0.1 MB/s from here and
# then stalled outright at 5 MiB, which makes a 46 MB tile unusable. AWS Terrain
# Tiles are keyless, served as small 256-pixel PNGs, and reachable at usable
# speed, so they are the fallback that lets the pipeline actually run.
#
# The trade is real and is recorded in every run manifest: at zoom 12 and this
# latitude the ground sample is about 35 m rather than 30 m, and the underlying
# data is a blend of SRTM and GMTED rather than Copernicus. No run may present
# one as the other.
# --------------------------------------------------------------------------

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TERRARIUM_TILE_PX = 256
WEB_MERCATOR_HALF_WORLD = 20_037_508.342789244
TERRARIUM_CRS = "EPSG:3857"

CHUNK_BYTES = 1 << 20  # 1 MiB


def _deg_to_tile(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    import math

    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n
    return x, y


def terrarium_zoom_for_resolution(resolution_m: float, mid_latitude: float) -> int:
    """Smallest zoom whose ground sample is at least as fine as requested."""
    import math

    for zoom in range(6, 16):
        ground = 156_543.03392 * math.cos(math.radians(mid_latitude)) / (2**zoom)
        if ground <= resolution_m:
            return zoom
    return 15


def _decode_terrarium(png_bytes: bytes) -> np.ndarray:
    """Terrarium encodes elevation across the RGB channels.

    elevation_m = (red * 256 + green + blue / 256) - 32768
    """
    import warnings

    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.io import MemoryFile

    with warnings.catch_warnings():
        # A terrain tile is a bare PNG with no geotransform. That is expected:
        # its position comes from the tile coordinates, and the mosaic
        # transform is constructed from those below.
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(png_bytes) as memfile, memfile.open() as src:
            rgb = src.read(indexes=[1, 2, 3]).astype("float64")

    elevation: np.ndarray = (rgb[0] * 256.0 + rgb[1] + rgb[2] / 256.0) - 32768.0
    return elevation


def fetch_terrarium_dem(
    region: Region, destination: Path, resolution_m: float, cache_dir: Path
) -> tuple[Path, dict[str, object]]:
    """Assemble an elevation raster for the region from AWS Terrain Tiles."""
    import urllib.request

    from rasterio.transform import from_origin

    cache_dir.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)

    mid_lat = (region.north + region.south) / 2
    zoom = terrarium_zoom_for_resolution(resolution_m, mid_lat)

    x_min, y_min = _deg_to_tile(region.west, region.north, zoom)
    x_max, y_max = _deg_to_tile(region.east, region.south, zoom)
    x_start, x_end = int(x_min), int(x_max)
    y_start, y_end = int(y_min), int(y_max)

    cols = x_end - x_start + 1
    rows = y_end - y_start + 1
    total = cols * rows

    tile_span_m = 2 * WEB_MERCATOR_HALF_WORLD / (2**zoom)
    pixel_m = tile_span_m / TERRARIUM_TILE_PX

    mosaic = np.full(
        (rows * TERRARIUM_TILE_PX, cols * TERRARIUM_TILE_PX), DEM_NODATA, dtype="float32"
    )

    print(f"    terrarium zoom {zoom}: {cols} x {rows} = {total} tiles", flush=True)
    fetched = 0
    failed = 0

    for row, tile_y in enumerate(range(y_start, y_end + 1)):
        for col, tile_x in enumerate(range(x_start, x_end + 1)):
            cached = cache_dir / f"{zoom}_{tile_x}_{tile_y}.png"
            try:
                if cached.exists() and cached.stat().st_size > 0:
                    payload = cached.read_bytes()
                else:
                    url = TERRARIUM_URL.format(z=zoom, x=tile_x, y=tile_y)
                    with urllib.request.urlopen(url, timeout=120) as response:
                        payload = response.read()
                    cached.write_bytes(payload)

                elevation = _decode_terrarium(payload)
            except Exception as exc:  # noqa: BLE001 - one missing tile is a hole, not a failure
                log.warning(
                    "terrarium.tile_failed", extra={"x": tile_x, "y": tile_y, "err": str(exc)}
                )
                failed += 1
                continue

            r0 = row * TERRARIUM_TILE_PX
            c0 = col * TERRARIUM_TILE_PX
            mosaic[r0 : r0 + TERRARIUM_TILE_PX, c0 : c0 + TERRARIUM_TILE_PX] = elevation
            fetched += 1

            if fetched % 20 == 0:
                print(f"      {fetched}/{total} tiles", flush=True)

    if fetched == 0:
        raise RuntimeError(
            "No terrain tiles could be fetched; the elevation source is unreachable."
        )

    origin_x = -WEB_MERCATOR_HALF_WORLD + x_start * tile_span_m
    origin_y = WEB_MERCATOR_HALF_WORLD - y_start * tile_span_m
    transform = from_origin(origin_x, origin_y, pixel_m, pixel_m)

    profile = {
        "driver": "GTiff",
        "height": mosaic.shape[0],
        "width": mosaic.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": TERRARIUM_CRS,
        "transform": transform,
        "nodata": DEM_NODATA,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
    }
    with rasterio.open(destination, "w", **profile) as dst:
        dst.write(mosaic, 1)

    detail: dict[str, object] = {
        "dem_source": "aws_terrain_tiles_terrarium",
        "zoom": zoom,
        "tiles_fetched": fetched,
        "tiles_failed": failed,
        "native_resolution_m": round(pixel_m, 2),
        "note": (
            "SRTM and GMTED blend served by AWS Terrain Tiles, not Copernicus GLO-30. "
            "Used because the Copernicus host stalled at 5 MiB when measured."
        ),
    }
    log.info("dem.terrarium", extra=detail)
    return destination, detail


def _stream_to_file(href: str, target: Path, *, timeout: int = 600) -> Path:
    """Stream one tile to disk, resuming a partial download where possible.

    Reading the whole response into memory gives no progress and no resume, and
    the tile host measured here serves at roughly 0.1 MB/s, which makes a 46 MB
    tile an eight-minute wait. Streaming in chunks makes that wait observable
    and an interruption recoverable via an HTTP range request.
    """
    import urllib.request

    partial = target.with_suffix(target.suffix + ".partial")
    existing = partial.stat().st_size if partial.exists() else 0

    request = urllib.request.Request(href)
    if existing:
        request.add_header("Range", f"bytes={existing}-")
        print(f"      resuming at {existing / 1e6:.1f} MB", flush=True)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        # A server that ignores the range header restarts the file, so the
        # local partial must be discarded rather than appended to.
        resuming = response.status == 206
        mode = "ab" if (existing and resuming) else "wb"
        if existing and not resuming:
            existing = 0

        declared = response.headers.get("Content-Length")
        total = (int(declared) + existing) if declared else None

        written = existing
        next_report = written + 10 * CHUNK_BYTES
        with partial.open(mode) as handle:
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                if written >= next_report:
                    if total:
                        print(
                            f"      {written / 1e6:6.1f} / {total / 1e6:.1f} MB"
                            f" ({100 * written / total:4.1f}%)",
                            flush=True,
                        )
                    else:
                        print(f"      {written / 1e6:6.1f} MB", flush=True)
                    next_report = written + 10 * CHUNK_BYTES

    # Only now is the file complete, so only now does it get its real name.
    # A future run therefore never mistakes a truncated tile for a good one.
    partial.replace(target)
    return target


def download_tiles(hrefs: list[str], cache_dir: Path) -> list[Path]:
    """Fetch each DEM tile to local disk before any raster work.

    Mosaicking straight from the signed remote URLs is possible but slow and
    opaque: GDAL streams blocks over HTTPS, progress is invisible, and an
    interrupted run starts over. Measured here, that approach had not produced
    an output after 25 minutes for two tiles.

    Downloading first is faster, shows progress, makes re-runs instant, and
    leaves the pipeline able to run offline once the tiles are cached. Signed
    Planetary Computer URLs expire, so the download happens promptly after the
    search that produced them.
    """

    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for index, href in enumerate(hrefs, start=1):
        # Strip the SAS query string to get a stable filename.
        name = href.split("?")[0].rsplit("/", 1)[-1]
        target = cache_dir / name

        if target.exists() and target.stat().st_size > 0:
            log.info("dem.tile_cached", extra={"tile": name})
            print(f"    tile {index}/{len(hrefs)} cached: {name}")
            paths.append(target)
            continue

        print(f"    tile {index}/{len(hrefs)} downloading: {name}", flush=True)
        _stream_to_file(href, target)
        print(f"      {target.stat().st_size / 1e6:.1f} MB")
        paths.append(target)

    return paths


def build_mosaic(
    sources_or_hrefs: list[Path] | list[str], region: Region, destination: Path
) -> Path:
    """Mosaic the tiles, clip to the region, and write EPSG:4326 elevation."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    sources = [rasterio.open(str(item)) for item in sources_or_hrefs]
    try:
        mosaic, transform = merge(sources, bounds=region.bbox, nodata=DEM_NODATA)
        profile = sources[0].profile.copy()
    finally:
        for src in sources:
            src.close()

    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=transform,
        count=1,
        dtype="float32",
        nodata=DEM_NODATA,
        compress="deflate",
        predictor=2,
        tiled=True,
    )

    with rasterio.open(destination, "w", **profile) as dst:
        dst.write(mosaic[0].astype("float32"), 1)

    log.info("dem.mosaic", extra={"shape": mosaic.shape, "path": str(destination)})
    return destination


def reproject_to_utm(source: Path, destination: Path, resolution_m: float) -> Path:
    """Reproject to EPSG:32646 at a fixed ground resolution.

    Bilinear resampling, not nearest: elevation is a continuous surface, and
    nearest-neighbour resampling introduces stair steps that a slope operator
    then reports as spurious steep faces.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source) as src:
        transform, width, height = calculate_default_transform(
            src.crs,
            TARGET_CRS,
            src.width,
            src.height,
            *src.bounds,
            resolution=resolution_m,
        )
        profile = src.profile.copy()
        profile.update(
            crs=TARGET_CRS,
            transform=transform,
            width=width,
            height=height,
            dtype="float32",
            nodata=DEM_NODATA,
            # Uncompressed and untiled, deliberately.
            #
            # This file is consumed by WhiteboxTools, which uses its own
            # GeoTIFF reader rather than GDAL. Measured on 2026-09-09 against
            # this exact raster: written DEFLATE-compressed and tiled, the
            # slope tool returned 8,527 valid pixels out of 5.2 million and
            # depression breaching produced elevations up to 3.9e37. Written
            # uncompressed and untiled, the same tool returned 5,203,183 valid
            # pixels with a mean slope of 21.6 degrees.
            #
            # The failure is silent: WhiteboxTools still exits 0 and writes an
            # output. Every downstream derivative would have been garbage while
            # looking perfectly well-formed, so this is not a size trade to
            # revisit casually.
            tiled=False,
        )
        # Popped rather than set to None: rasterio rejects a None creation option.
        profile.pop("compress", None)
        profile.pop("predictor", None)
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)

        with rasterio.open(destination, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=TARGET_CRS,
                resampling=Resampling.bilinear,
                src_nodata=DEM_NODATA,
                dst_nodata=DEM_NODATA,
            )

    log.info(
        "dem.reproject",
        extra={"width": width, "height": height, "resolution_m": resolution_m},
    )
    return destination


def summarise(path: Path) -> dict[str, float | int]:
    """Elevation statistics, used for the run report and as a sanity check."""
    with rasterio.open(path) as src:
        data = src.read(1, masked=True)
        valid = int(data.count())
        if valid == 0:
            raise RuntimeError(f"{path} contains no valid elevation values.")
        return {
            "width": src.width,
            "height": src.height,
            "valid_pixels": valid,
            "nodata_pixels": int(data.size - valid),
            "elevation_min_m": float(np.min(data)),
            "elevation_mean_m": float(np.mean(data)),
            "elevation_max_m": float(np.max(data)),
            "resolution_m": float(abs(src.transform.a)),
        }
