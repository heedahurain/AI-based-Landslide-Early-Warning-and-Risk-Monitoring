"""Location lookup for any point in India.

This is deliberately two different things stitched honestly together.

For a point inside the Noney and Tupul pilot area, the answer is real:
the nearest of the 14,714 measured slope units and its physics-layer factor
of safety, the same computation the map and the dashboards use.

For everywhere else in India, which is almost everywhere a user will actually
tap, there is no slope-level data. Rather than inventing a number, the answer
falls back to a documented fact: whether the state is one of the 19 states and
union territories the Geological Survey of India covers under its National
Landslide Susceptibility Mapping programme. That is a real, citable
classification, not a computed risk, and the response says so explicitly.

Source: GSI's NLSM programme, reported to cover roughly 4.3 lakh km2 across
179 districts in 19 states and union territories, verified against press
coverage on 2026-09-09 (Business Standard, ETV Bharat). See
docs/DATA_SOURCES.md.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["location"])

INDIA_DISTRICTS_SHP = "data/boundaries/_src/2011_Dist.shp"

# The 19 states and union territories GSI's National Landslide Susceptibility
# Mapping programme covers, grouped by the belt they sit in. Canonical names;
# the source shapefile misspells Arunachal Pradesh as "Arunanchal Pradesh",
# handled at lookup time rather than by editing the list.
GSI_NLSM_COVERAGE: dict[str, str] = {
    # North-western Himalaya
    "Jammu & Kashmir": "north-western Himalaya",
    "Ladakh": "north-western Himalaya",
    "Himachal Pradesh": "north-western Himalaya",
    "Uttarakhand": "north-western Himalaya",
    # Sub-Himalayan North East
    "Sikkim": "sub-Himalayan North East",
    "West Bengal": "sub-Himalayan North East",
    "Assam": "sub-Himalayan North East",
    "Arunachal Pradesh": "sub-Himalayan North East",
    "Manipur": "sub-Himalayan North East",
    "Meghalaya": "sub-Himalayan North East",
    "Mizoram": "sub-Himalayan North East",
    "Nagaland": "sub-Himalayan North East",
    "Tripura": "sub-Himalayan North East",
    # Western Ghats
    "Maharashtra": "Western Ghats",
    "Goa": "Western Ghats",
    "Karnataka": "Western Ghats",
    "Kerala": "Western Ghats",
    # Eastern Ghats
    "Andhra Pradesh": "Eastern Ghats",
    "Tamil Nadu": "Eastern Ghats",
}

# The source shapefile's own spelling for a handful of states does not match
# the canonical names above. Mapped once, here, rather than silently dropped.
NAME_CORRECTIONS: dict[str, str] = {
    "Arunanchal Pradesh": "Arunachal Pradesh",
    "Andaman & Nicobar Island": "Andaman & Nicobar Islands",
    "NCT of Delhi": "Delhi",
}

# The bounding box of the one area with real slope-level data. Matches
# ingest.terrain.regions.NONEY.
PILOT_BBOX = (93.2, 24.6, 93.8, 25.2)
PILOT_RUN = "noney_30m"


class LocationLookupResponse(BaseModel):
    latitude: float
    longitude: float
    state: str | None
    district: str | None
    within_india_boundary_data: bool
    gsi_landslide_prone: bool
    gsi_belt: str | None
    gsi_note: str
    has_detailed_coverage: bool
    detailed_run: str | None
    nearest_unit: dict[str, Any] | None
    nearest_unit_distance_m: float | None
    stability_summary: dict[str, Any] | None


@lru_cache(maxsize=1)
def _india_districts() -> Any:
    import geopandas as gpd

    path = Path(INDIA_DISTRICTS_SHP)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run the boundary loader first: "
            'python -c "from ingest.boundaries import download_source; '
            "download_source(__import__('pathlib').Path('data/boundaries/_src'))\""
        )
    frame = gpd.read_file(path)
    frame["state_clean"] = frame["ST_NM"].map(lambda name: NAME_CORRECTIONS.get(name, name))
    return frame


def _data_root() -> Path:
    from app.core.config import get_settings

    return Path(get_settings().data_root)


@router.get("/lookup", response_model=LocationLookupResponse)
async def lookup(
    latitude: float = Query(..., ge=6.0, le=38.0, description="Latitude, roughly India's extent"),
    longitude: float = Query(
        ..., ge=68.0, le=98.0, description="Longitude, roughly India's extent"
    ),
    wetness: float = Query(0.75, ge=0.0, le=1.0),
) -> LocationLookupResponse:
    from shapely.geometry import Point

    point = Point(longitude, latitude)

    try:
        districts = _india_districts()
        matches = districts[districts.geometry.contains(point)]
    except FileNotFoundError as exc:
        log.warning("location.boundaries_missing", extra={"error": str(exc)})
        matches = None

    state: str | None = None
    district: str | None = None
    within_boundary_data = False

    if matches is not None and len(matches):
        row = matches.iloc[0]
        state = str(row["state_clean"])
        district = str(row["DISTRICT"]).strip()
        within_boundary_data = True

    gsi_prone = state in GSI_NLSM_COVERAGE if state else False
    gsi_belt = GSI_NLSM_COVERAGE.get(state) if state else None

    if within_boundary_data:
        gsi_note = (
            f"{state} is one of the 19 states and union territories covered by GSI's "
            f"National Landslide Susceptibility Mapping programme ({gsi_belt})."
            if gsi_prone
            else f"{state} is not among the 19 states GSI's landslide susceptibility "
            "mapping programme currently covers. That is a statement about where GSI has "
            "published mapping, not a claim that the area is free of landslide risk."
        )
    else:
        gsi_note = (
            "This point did not match any district in the boundary data on file. "
            "State and district cannot be determined."
        )

    west, south, east, north = PILOT_BBOX
    in_pilot = west <= longitude <= east and south <= latitude <= north

    nearest_unit: dict[str, Any] | None = None
    nearest_distance: float | None = None
    stability_summary: dict[str, Any] | None = None

    if in_pilot:
        try:
            nearest_unit, nearest_distance, stability_summary = _nearest_pilot_unit(
                latitude, longitude, wetness
            )
        except FileNotFoundError:
            in_pilot = False

    return LocationLookupResponse(
        latitude=latitude,
        longitude=longitude,
        state=state,
        district=district,
        within_india_boundary_data=within_boundary_data,
        gsi_landslide_prone=gsi_prone,
        gsi_belt=gsi_belt,
        gsi_note=gsi_note,
        has_detailed_coverage=in_pilot and nearest_unit is not None,
        detailed_run=PILOT_RUN if (in_pilot and nearest_unit is not None) else None,
        nearest_unit=nearest_unit,
        nearest_unit_distance_m=nearest_distance,
        stability_summary=stability_summary,
    )


def _nearest_pilot_unit(
    lat: float, lon: float, wetness: float
) -> tuple[dict[str, Any], float, dict[str, Any]]:
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import Point

    from ml.physics.geotech import get_parameters
    from ml.physics.slope_stability import estimate_soil_depth, factor_of_safety, stability_class

    path = _data_root() / "terrain" / PILOT_RUN / "slope_units.parquet"
    if not path.exists():
        raise FileNotFoundError(str(path))

    frame = gpd.read_parquet(path)
    point_utm = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32646").iloc[0]
    units_utm = frame.to_crs("EPSG:32646")

    distances = units_utm.geometry.distance(point_utm)
    idx = int(distances.values.argmin())
    row = frame.iloc[idx]
    distance_m = float(distances.iloc[idx])

    slope = float(row["slope_deg"]) if row["slope_deg"] == row["slope_deg"] else 0.0
    depth = float(estimate_soil_depth(np.array([slope]))[0])
    params = get_parameters(None)
    fos = float(
        factor_of_safety(
            slope,
            depth,
            params.cohesion_kpa,
            params.friction_angle_deg,
            params.unit_weight_kn_m3,
            wetness,
        )
    )
    band = str(stability_class(np.array([fos]))[0])

    unit = {
        "hillslope_id": int(row["hillslope_id"]),
        "slope_deg": round(slope, 1),
        "elevation_mean_m": (
            round(float(row["elevation_mean_m"]), 0)
            if "elevation_mean_m" in row and row["elevation_mean_m"] == row["elevation_mean_m"]
            else None
        ),
        "factor_of_safety": round(fos, 2),
        "stability_class": band,
        "lithology": params.name,
        "wetness_fraction": wetness,
    }

    all_slope = np.nan_to_num(frame["slope_deg"].to_numpy(dtype="float64"), nan=0.0)
    all_depth = estimate_soil_depth(all_slope)
    all_fos = factor_of_safety(
        all_slope,
        all_depth,
        params.cohesion_kpa,
        params.friction_angle_deg,
        params.unit_weight_kn_m3,
        wetness,
    )
    all_bands = stability_class(all_fos)
    summary = {
        "scored_units": len(frame),
        "unstable": int(np.sum(all_bands == "unstable")),
        "marginal": int(np.sum(all_bands == "marginal")),
        "stable": int(np.sum(all_bands == "stable")),
    }

    return unit, distance_m, summary


@router.get("/gsi-coverage", summary="The 19 GSI landslide-mapped states")
async def gsi_coverage() -> dict[str, Any]:
    by_belt: dict[str, list[str]] = {}
    for state, belt in GSI_NLSM_COVERAGE.items():
        by_belt.setdefault(belt, []).append(state)
    return {
        "state_count": len(GSI_NLSM_COVERAGE),
        "by_belt": by_belt,
        "source": (
            "GSI National Landslide Susceptibility Mapping (NLSM), reported coverage of "
            "roughly 4.3 lakh km2 across 179 districts in 19 states and union territories."
        ),
        "verified": "2026-09-09, cross-checked against Business Standard and ETV Bharat coverage",
    }
