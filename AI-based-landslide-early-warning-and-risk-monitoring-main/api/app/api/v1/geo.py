"""Geospatial read endpoints.

These serve the Phase 1 pipeline outputs to the map. They read the GeoParquet
files the pipeline writes rather than the database, because the pipeline runs
and produces useful output long before a PostGIS instance exists. When the
database is available the same routes will read from it, and the response shape
will not change.

Two things make a 14,714-polygon layer usable in a browser:

*Simplification.* The raw geometry is 49 MB of GeoJSON. Simplified to a 40 m
tolerance with coordinates snapped to a 1e-5 degree grid, roughly one metre, it
is 8.4 MB with every unit retained. That is a display concern only. Analysis
always uses the full-precision geometry.

*Compression and caching.* GeoJSON is highly repetitive text, so the gzip
middleware takes it down by roughly a further five times, and a strong ETag
means the browser refetches only when the run changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request, Response

from app.core.problems import ProblemDetailError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/geo", tags=["geo"])

# Attributes exposed to the map. Everything else stays server-side: each extra
# float across 14,714 features is another 100 KB on the wire.
SLOPE_UNIT_FIELDS = (
    "hillslope_id",
    "area_m2",
    "slope_deg",
    "slope_max_deg",
    "aspect_deg",
    "twi",
    "tpi",
    "local_relief_m",
    "elevation_mean_m",
    "distance_to_stream_m",
)

ROAD_FIELDS = ("osm_id", "name", "highway_class", "length_m")
DISTRICT_FIELDS = ("district_name", "state_name", "census_code", "area_km2")
STATE_FIELDS = ("name", "area_km2")

DEFAULT_SIMPLIFY_M = 40.0
PRECISION_GRID_DEG = 1e-5


def data_root() -> Path:
    """Where the pipeline writes its outputs."""
    from app.core.config import get_settings

    return Path(get_settings().data_root)


def _round_numeric(frame: Any, fields: tuple[str, ...]) -> Any:
    for column in fields:
        if column in frame.columns and frame[column].dtype.kind == "f":
            frame[column] = frame[column].round(2)
    return frame


@lru_cache(maxsize=8)
def _load_geojson(path_str: str, fields: tuple[str, ...], simplify_m: float) -> tuple[str, str]:
    """Read a GeoParquet file and return (geojson, etag).

    Cached because the parse and simplify cost is significant and the file only
    changes when the pipeline is re-run.
    """
    import geopandas as gpd
    import shapely

    path = Path(path_str)
    frame = gpd.read_parquet(path)

    keep = [f for f in fields if f in frame.columns]
    frame = frame[[*keep, "geometry"]].copy()

    if simplify_m > 0:
        # Simplify in projected metres. Simplifying in degrees would apply a
        # different tolerance north to south.
        frame["geometry"] = (
            frame.to_crs("EPSG:32646").geometry.simplify(simplify_m).to_crs("EPSG:4326")
        )
        try:
            frame["geometry"] = shapely.set_precision(frame.geometry.values, PRECISION_GRID_DEG)
        except Exception as exc:  # noqa: BLE001 - precision snapping is an optimisation
            # Snapping can fail on self-touching rings with a TopologyException.
            # The layer is still correct without it, just larger.
            log.warning("geo.precision_snap_failed", extra={"error": str(exc)})

        frame = frame[frame.geometry.notna() & ~frame.geometry.is_empty]

    frame = _round_numeric(frame, fields)

    payload = frame.to_json(drop_id=True)
    etag = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return payload, etag


def _geojson_response(
    request: Request, path: Path, fields: tuple[str, ...], simplify_m: float
) -> Response:
    if not path.exists():
        raise ProblemDetailError(
            status_code=404,
            title="Layer not available",
            detail=(
                f"{path.name} has not been generated. Run the terrain pipeline first: "
                "python -m ingest.terrain build --bbox noney --resolution 30"
            ),
            problem_type="https://shailsuraksha.in/problems/layer-not-generated",
        )

    payload, etag = _load_geojson(str(path), fields, simplify_m)

    # A matching ETag means the client already has this exact layer.
    if request.headers.get("if-none-match") == f'"{etag}"':
        return Response(status_code=304)

    return Response(
        content=payload,
        media_type="application/geo+json",
        headers={
            "ETag": f'"{etag}"',
            "Cache-Control": "public, max-age=300",
        },
    )


@router.get("/runs", summary="Terrain runs available on disk")
async def runs() -> dict[str, Any]:
    """List completed pipeline runs and the statistics each one measured."""
    terrain_dir = data_root() / "terrain"
    available: list[dict[str, Any]] = []

    if terrain_dir.exists():
        for report_path in sorted(terrain_dir.glob("*/report.json")):
            try:
                available.append(json.loads(report_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("geo.bad_report", extra={"path": str(report_path), "error": str(exc)})

    return {"runs": available, "count": len(available)}


@router.get("/slope-units", summary="Slope units with their terrain attributes")
async def slope_units(
    request: Request,
    run: str = Query("noney_30m", description="Run identifier, see /geo/runs"),
    simplify: float = Query(
        DEFAULT_SIMPLIFY_M, ge=0, le=500, description="Display simplification in metres"
    ),
) -> Response:
    path = data_root() / "terrain" / run / "slope_units.parquet"
    return _geojson_response(request, path, SLOPE_UNIT_FIELDS, simplify)


@router.get("/districts", summary="District boundaries for the eight states")
async def districts(
    request: Request,
    simplify: float = Query(100.0, ge=0, le=2000),
) -> Response:
    path = data_root() / "boundaries" / "districts.parquet"
    return _geojson_response(request, path, DISTRICT_FIELDS, simplify)


@router.get("/states", summary="State boundaries for the eight states")
async def states(
    request: Request,
    simplify: float = Query(200.0, ge=0, le=2000),
) -> Response:
    path = data_root() / "boundaries" / "states.parquet"
    return _geojson_response(request, path, STATE_FIELDS, simplify)


@router.get("/roads", summary="Road centrelines")
async def roads(
    request: Request,
    area: str = Query("noney", description="OSM extract name"),
    simplify: float = Query(20.0, ge=0, le=500),
) -> Response:
    path = data_root() / "osm" / area / "roads.parquet"
    return _geojson_response(request, path, ROAD_FIELDS, simplify)


@router.get("/facilities", summary="Hospitals, schools and other critical facilities")
async def facilities(
    request: Request,
    area: str = Query("noney"),
) -> Response:
    path = data_root() / "osm" / area / "facilities.parquet"
    return _geojson_response(request, path, ("osm_id", "name", "category", "capacity"), 0.0)
