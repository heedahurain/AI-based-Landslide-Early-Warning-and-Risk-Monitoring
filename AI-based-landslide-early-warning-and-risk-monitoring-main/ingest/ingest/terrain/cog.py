"""Cloud-Optimised GeoTIFF output and object-storage upload.

Derivative rasters are written as COGs so the API and the map can read a window
over HTTP without downloading the whole raster. That is what makes a regional
DEM usable from a browser at all.

Two rules apply to the compression settings here, both learned the hard way.
Floating-point rasters use predictor 3, never 2: predictor 2 is the horizontal
differencing predictor for integers, and applying it to float data produces a
file that some readers silently decode as garbage. And no file written here is
ever fed back into WhiteboxTools, which cannot read compressed tiled GeoTIFFs.
Those stay uncompressed in the working directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling

log = logging.getLogger(__name__)

# Overview levels. A 2,000 by 2,000 raster needs four; more is harmless.
OVERVIEW_LEVELS = (2, 4, 8, 16, 32)


def to_cog(source: Path, destination: Path, *, resampling: Resampling = Resampling.average) -> Path:
    """Rewrite a raster as a tiled, overviewed, compressed COG."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source) as src:
        profile = src.profile.copy()
        data = src.read(1)
        dtype = str(src.dtypes[0])

    is_float = np.issubdtype(np.dtype(dtype), np.floating)

    profile.update(
        driver="GTiff",
        count=1,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        compress="deflate",
        # 3 for floating point, 2 for integers. Getting this wrong is a silent
        # data-corruption bug, not an error.
        predictor=3 if is_float else 2,
        BIGTIFF="IF_SAFER",
    )
    profile.pop("interleave", None)

    with rasterio.open(destination, "w", **profile) as dst:
        dst.write(data, 1)
        dst.build_overviews(OVERVIEW_LEVELS, resampling)
        dst.update_tags(ns="rio_overview", resampling=resampling.name)

    log.info("cog.written", extra={"source": source.name, "bytes": destination.stat().st_size})
    return destination


def convert_derivatives(rasters: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Convert every derivative raster to a COG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}

    for name, path in rasters.items():
        if not Path(path).exists():
            log.warning("cog.missing_source", extra={"name": name})
            continue
        # The hillslope raster holds integer labels, so nearest-neighbour
        # overviews. Averaging label values would invent hillslopes that do
        # not exist.
        resampling = Resampling.nearest if name in {"hillslopes", "streams"} else Resampling.average
        outputs[name] = to_cog(Path(path), output_dir / f"{name}.tif", resampling=resampling)

    return outputs


def upload_to_minio(
    files: dict[str, Path], prefix: str, settings: Any | None = None
) -> dict[str, str]:
    """Upload COGs to MinIO, returning object keys.

    Returns an empty mapping when object storage is not configured or not
    reachable, and says so in the log. The pipeline keeps its local outputs
    either way, so a missing MinIO degrades the run rather than failing it.
    """
    try:
        from minio import Minio
    except ImportError:
        log.warning("cog.minio_unavailable", extra={"reason": "minio package not installed"})
        return {}

    if settings is None:
        try:
            from app.core.config import get_settings

            settings = get_settings()
        except Exception as exc:  # noqa: BLE001 - the API package may not be importable here
            log.warning("cog.settings_unavailable", extra={"error": str(exc)})
            return {}

    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)

        keys: dict[str, str] = {}
        for name, path in files.items():
            key = f"{prefix}/{name}.tif"
            client.fput_object(settings.minio_bucket, key, str(path))
            keys[name] = key
            log.info("cog.uploaded", extra={"key": key})
        return keys
    except Exception as exc:  # noqa: BLE001 - object storage is optional at this phase
        log.warning("cog.upload_failed", extra={"error": str(exc)})
        return {}
