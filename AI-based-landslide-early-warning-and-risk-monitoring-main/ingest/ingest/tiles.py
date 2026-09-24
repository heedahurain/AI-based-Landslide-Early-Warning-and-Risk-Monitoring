"""Vector tile generation with tippecanoe.

Admin boundaries, slope units and roads are served to the map as PMTiles. A
single PMTiles archive is one file that supports HTTP range requests, so the
browser fetches only the tiles it needs. That is what lets a district pack be
downloaded for offline use in Phase 9, and it removes any dependency on a
third-party tile service during the demo.

tippecanoe is a native binary and is not available on Windows. It is installed
in the API container image, so this module runs there. When the binary is
absent it says so and returns nothing rather than half-writing an archive.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

TIPPECANOE = "tippecanoe"


@dataclass(frozen=True)
class LayerSpec:
    """One layer inside the tile archive."""

    name: str
    source: Path
    min_zoom: int
    max_zoom: int
    # Attributes kept in the tiles. Everything else is dropped, because tile
    # size is the constraint that decides whether the map is usable on a phone
    # with two bars of signal.
    keep: tuple[str, ...] = ()


def tippecanoe_available() -> bool:
    return shutil.which(TIPPECANOE) is not None


def _geojson_from_parquet(parquet: Path, destination: Path, keep: tuple[str, ...]) -> Path:
    """tippecanoe reads GeoJSON, so convert and trim attributes on the way."""
    import geopandas as gpd

    frame = gpd.read_parquet(parquet).to_crs("EPSG:4326")
    if keep:
        columns = [c for c in keep if c in frame.columns]
        frame = frame[[*columns, "geometry"]]

    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(destination, driver="GeoJSON")
    return destination


def build_pmtiles(layers: list[LayerSpec], output: Path, *, force: bool = False) -> Path | None:
    """Build one PMTiles archive containing every layer.

    Returns None when tippecanoe is unavailable, so a caller on a machine
    without it can carry on and produce the rest of the outputs.
    """
    if not tippecanoe_available():
        log.warning(
            "tiles.tippecanoe_missing",
            extra={"hint": "Run inside the api container, where tippecanoe is installed."},
        )
        return None

    if output.exists() and not force:
        log.info("tiles.exists", extra={"path": str(output)})
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / "_geojson"
    staging.mkdir(parents=True, exist_ok=True)

    command: list[str] = [
        TIPPECANOE,
        "-o",
        str(output),
        "--force",
        # Drop nothing silently. Without these, tippecanoe thins features to
        # meet a tile size budget, and a dropped slope unit is a slope nobody
        # is warned about.
        "--no-feature-limit",
        "--no-tile-size-limit",
        # Keep small polygons visible when zoomed out rather than dropping them.
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--simplification=4",
    ]

    for layer in layers:
        if not layer.source.exists():
            log.warning("tiles.layer_missing", extra={"layer": layer.name})
            continue
        geojson = _geojson_from_parquet(layer.source, staging / f"{layer.name}.geojson", layer.keep)
        command += [
            "-L",
            json.dumps(
                {
                    "file": str(geojson),
                    "layer": layer.name,
                    "minzoom": layer.min_zoom,
                    "maxzoom": layer.max_zoom,
                }
            ),
        ]

    log.info("tiles.building", extra={"layers": len(layers), "output": str(output)})
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(
            f"tippecanoe failed with code {result.returncode}:\n{result.stderr[-2000:]}"
        )

    log.info("tiles.built", extra={"bytes": output.stat().st_size})
    return output


def default_layers(terrain_dir: Path, boundaries_dir: Path, osm_dir: Path) -> list[LayerSpec]:
    """The layer set the risk command centre needs.

    Zoom ranges are chosen by what the layer is for. Admin boundaries are
    useful from the regional overview down, slope units only once a district
    fills the screen, and roads only when a village is in view.
    """
    return [
        LayerSpec(
            name="state",
            source=boundaries_dir / "states.parquet",
            min_zoom=4,
            max_zoom=10,
            keep=("name", "area_km2"),
        ),
        LayerSpec(
            name="district",
            source=boundaries_dir / "districts.parquet",
            min_zoom=5,
            max_zoom=12,
            keep=("district_name", "state_name", "census_code", "area_km2"),
        ),
        LayerSpec(
            name="slope_unit",
            source=terrain_dir / "slope_units.parquet",
            min_zoom=8,
            max_zoom=14,
            keep=("hillslope_id", "run_id", "area_m2", "slope_deg", "twi", "local_relief_m"),
        ),
        LayerSpec(
            name="road",
            source=osm_dir / "roads.parquet",
            min_zoom=9,
            max_zoom=14,
            keep=("osm_id", "name", "highway_class", "length_m"),
        ),
    ]
