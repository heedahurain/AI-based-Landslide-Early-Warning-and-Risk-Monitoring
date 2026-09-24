"""Road blockage and connectivity impact.

A road is not cut by its own gradient. It is cut by the slope units above and
beside it failing onto it, so blockage probability here is derived from the
stability of the slope units within a buffer of each segment, weighted by how
close they are.

The graph analysis then answers the question an officer actually asks: with
these segments gone, which places can no longer be reached?
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.core.problems import ProblemDetailError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/connectivity", tags=["connectivity"])

# Slope units within this distance of a segment can deliver debris onto it.
# Chosen to match the scale of a shallow translational failure runout on these
# hillsides rather than to tune an outcome.
BUFFER_M = 250.0

COMPUTATION_CRS = "EPSG:32646"


class RoadRisk(BaseModel):
    osm_id: str | None
    name: str | None
    highway_class: str
    length_m: float
    blockage_probability: float
    expected_blockages: float
    contributing_units: int
    min_fos_nearby: float | None


class ConnectivityResponse(BaseModel):
    run: str
    wetness_fraction: float
    lithology: str
    buffer_m: float
    threshold: float
    segments_total: int
    segments_at_risk: int
    length_at_risk_km: float
    facilities_total: int
    facilities_cut_off: int
    by_class: dict[str, int]
    top_segments: list[RoadRisk]
    method: str


def _data_root() -> Path:
    from app.core.config import get_settings

    return Path(get_settings().data_root)


@lru_cache(maxsize=2)
def _load_network(run: str, area: str) -> tuple[Any, Any, Any]:
    """Roads, slope-unit centroids and facilities, all projected to metres."""
    import geopandas as gpd

    root = _data_root()
    roads_path = root / "osm" / area / "roads.parquet"
    units_path = root / "terrain" / run / "slope_units.parquet"
    facilities_path = root / "osm" / area / "facilities.parquet"

    if not roads_path.exists() or not units_path.exists():
        raise FileNotFoundError(f"{roads_path} or {units_path}")

    roads = gpd.read_parquet(roads_path).to_crs(COMPUTATION_CRS)
    units = gpd.read_parquet(units_path).to_crs(COMPUTATION_CRS)
    facilities = (
        gpd.read_parquet(facilities_path).to_crs(COMPUTATION_CRS)
        if facilities_path.exists()
        else None
    )
    return roads, units, facilities


# Only the few most threatening sources are combined into a probability. See
# ml.physics.runout.blockage_probability for why combining all of them is wrong.
TOP_K_CONTRIBUTORS = 5


def _segment_risk(
    roads: Any, units: Any, params: Any, wetness: float, per_unit_materials: bool = False
) -> Any:
    """Per-segment blockage metrics, shared by the table and the map.

    Both endpoints call this so the map can never disagree with the ranking
    beside it. Three things happen here that did not happen in the first
    version of this calculation:

    1. A factor of safety becomes a failure probability through a reliability
       calculation rather than the linear rescaling ``clip(2 - FoS, 0, 1)``,
       which had assigned a stable slope a 61 percent chance of failing.
    2. A source only contributes if it can physically reach the road, judged by
       its angle of reach. Height above the road is taken as the source's
       elevation minus the lowest slope-unit elevation within the same buffer,
       a proxy for the road's own elevation that holds because roads here sit
       in valley bottoms and on benches, not on ridge crests. It is a proxy and
       is labelled as one.
    3. The headline number is the expected count of blocking failures, which
       grows with the number of threatening slopes instead of saturating at one.
    """
    import geopandas as gpd

    from ml.physics.geotech import parameter_arrays
    from ml.physics.runout import (
        blockage_probability,
        probability_of_failure,
        reach_weight,
    )
    from ml.physics.slope_stability import estimate_soil_depth, factor_of_safety

    slope = np.nan_to_num(units["slope_deg"].to_numpy(dtype="float64"), nan=0.0)
    depth = estimate_soil_depth(slope)

    # Score each unit against the material its landform position implies, so a
    # road cutting and the valley floor beside it are not given the same
    # strength. Falls back to the single supplied class for a run built before
    # material assignment existed.
    cohesion: Any = params.cohesion_kpa
    friction: Any = params.friction_angle_deg
    unit_weight: Any = params.unit_weight_kn_m3
    if per_unit_materials and "material_class" in units:
        cohesion, friction, unit_weight = parameter_arrays(
            [str(m) for m in units["material_class"].to_numpy(dtype=object)]
        )

    fos = factor_of_safety(slope, depth, cohesion, friction, unit_weight, wetness)

    scored = units[["geometry", "elevation_mean_m"]].copy()
    scored["fos"] = fos
    scored["p_fail"] = probability_of_failure(fos)
    scored["source_point"] = units.geometry.centroid

    buffered = roads[["geometry"]].copy()
    buffered["geometry"] = buffered.geometry.buffer(BUFFER_M)
    joined = buffered.sjoin(scored, how="inner", predicate="intersects")

    if len(joined) == 0:
        return roads.assign(
            blockage_probability=0.0, expected_blockages=0.0, contributing_units=0
        ), None

    # Horizontal distance from each source to the segment itself, not to the
    # buffer that selected it.
    segment_geom = gpd.GeoSeries(
        roads.geometry.loc[joined.index].to_numpy(), crs=roads.crs
    ).reset_index(drop=True)
    source_geom = gpd.GeoSeries(joined["source_point"].to_numpy(), crs=roads.crs).reset_index(
        drop=True
    )
    joined["distance_m"] = segment_geom.distance(source_geom).to_numpy()

    # Height of the source above the road, proxied by the lowest unit in the
    # same buffer. A source at or below that level delivers nothing.
    road_level = joined.groupby(level=0)["elevation_mean_m"].transform("min")
    height = joined["elevation_mean_m"].to_numpy() - road_level.to_numpy()

    joined["delivered"] = joined["p_fail"].to_numpy() * reach_weight(
        height, joined["distance_m"].to_numpy()
    )

    reachable = joined[joined["delivered"] > 1e-3]
    grouped = reachable.groupby(level=0)["delivered"]

    expected = grouped.sum().reindex(roads.index).fillna(0.0)
    probability = (
        grouped.apply(lambda values: blockage_probability(values.to_numpy(), TOP_K_CONTRIBUTORS))
        .reindex(roads.index)
        .fillna(0.0)
    )
    counts = grouped.count().reindex(roads.index).fillna(0).astype(int)
    min_fos = reachable.groupby(level=0)["fos"].min().reindex(roads.index)

    enriched = roads.assign(
        blockage_probability=probability.to_numpy(),
        expected_blockages=expected.to_numpy(),
        contributing_units=counts.to_numpy(),
    )
    return enriched, min_fos


@router.get("/roads.geojson", summary="All road segments as GeoJSON, coloured by blockage")
async def road_blockage_geojson(
    run: str = Query("noney_30m"),
    area: str = Query("noney"),
    lithology: str | None = Query(None),
    wetness: float = Query(0.75, ge=0.0, le=1.0),
) -> Response:
    """The full segment set with geometry, for the map on the roads dashboard.

    Shares the same blockage computation as /roads so the map and the table
    never disagree with each other.
    """

    from ml.physics.geotech import TERRAIN_DERIVED_KEY, get_parameters

    try:
        roads, units, _facilities = _load_network(run, area)
    except FileNotFoundError as exc:
        raise ProblemDetailError(
            status_code=404,
            title="Network data not available",
            detail="Roads or slope units are missing.",
            problem_type="https://shailsuraksha.in/problems/network-not-loaded",
        ) from exc

    params = get_parameters(lithology)
    enriched, _min_fos = _segment_risk(
        roads, units, params, wetness, per_unit_materials=lithology in (None, TERRAIN_DERIVED_KEY)
    )

    out = enriched[
        ["geometry", "highway_class", "length_m", "blockage_probability", "expected_blockages"]
    ].to_crs("EPSG:4326")
    out = out.assign(
        blockage_probability=out["blockage_probability"].round(3),
        expected_blockages=out["expected_blockages"].round(2),
        name=roads.get("name"),
    )

    payload = out.to_json(drop_id=True)
    return Response(content=payload, media_type="application/geo+json")


@router.get("/roads", response_model=ConnectivityResponse)
async def road_blockage(
    run: str = Query("noney_30m"),
    area: str = Query("noney"),
    lithology: str | None = Query(None),
    wetness: float = Query(0.75, ge=0.0, le=1.0),
    threshold: float = Query(
        0.35, ge=0.0, le=1.0, description="blockage probability above which a segment is at risk"
    ),
    limit: int = Query(25, ge=1, le=200),
) -> ConnectivityResponse:
    from ml.physics.geotech import TERRAIN_DERIVED_KEY, get_parameters

    try:
        roads, units, facilities = _load_network(run, area)
    except FileNotFoundError as exc:
        raise ProblemDetailError(
            status_code=404,
            title="Network data not available",
            detail=(
                "Roads or slope units are missing. Run the terrain pipeline and the OSM "
                "loader first."
            ),
            problem_type="https://shailsuraksha.in/problems/network-not-loaded",
        ) from exc

    params = get_parameters(lithology)
    roads, min_fos = _segment_risk(
        roads, units, params, wetness, per_unit_materials=lithology in (None, TERRAIN_DERIVED_KEY)
    )

    at_risk = roads[roads["blockage_probability"] >= threshold]
    length_at_risk_km = float(at_risk["length_m"].sum() / 1000.0)

    by_class: dict[str, int] = (
        at_risk["highway_class"].value_counts().to_dict() if len(at_risk) else {}
    )

    # Facilities whose nearest road is itself at risk lose their access route.
    facilities_cut = 0
    facilities_total = 0
    if facilities is not None and len(facilities) and len(at_risk):
        facilities_total = len(facilities)
        nearest = facilities.sjoin_nearest(
            at_risk[["geometry"]], how="left", max_distance=1000.0, distance_col="d"
        )
        facilities_cut = int(nearest["d"].notna().sum())
    elif facilities is not None:
        facilities_total = len(facilities)

    def clean_text(value: Any) -> str | None:
        """Pandas represents a missing string as NaN, which str() turns into "nan"."""
        import math

        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        text = str(value).strip()
        return text or None

    ranked = roads.sort_values("expected_blockages", ascending=False).head(limit)
    top = [
        RoadRisk(
            osm_id=clean_text(row.get("osm_id")),
            name=clean_text(row.get("name")),
            highway_class=str(row["highway_class"]),
            length_m=round(float(row["length_m"]), 1),
            blockage_probability=round(float(row["blockage_probability"]), 3),
            expected_blockages=round(float(row["expected_blockages"]), 2),
            contributing_units=int(row["contributing_units"]),
            min_fos_nearby=(
                round(float(min_fos.loc[index]), 2)
                if min_fos is not None
                and index in min_fos.index
                and np.isfinite(min_fos.loc[index])
                else None
            ),
        )
        for index, row in ranked.iterrows()
    ]

    return ConnectivityResponse(
        run=run,
        wetness_fraction=wetness,
        lithology=params.key,
        buffer_m=BUFFER_M,
        threshold=threshold,
        segments_total=len(roads),
        segments_at_risk=len(at_risk),
        length_at_risk_km=round(length_at_risk_km, 1),
        facilities_total=facilities_total,
        facilities_cut_off=facilities_cut,
        by_class={str(k): int(v) for k, v in by_class.items()},
        top_segments=top,
        method=(
            f"Each slope unit within {BUFFER_M:.0f} m of a segment is converted from a factor "
            "of safety to a probability of failure by a first-order reliability calculation "
            "(lognormal FoS, coefficient of variation 0.25). That probability is then scaled "
            "by whether the unit can physically reach the road, judged by its angle of reach "
            "between 22 and 35 degrees. Expected blockages is the sum of the surviving "
            "probabilities and is the value the table ranks on. Blockage probability combines "
            f"only the {TOP_K_CONTRIBUTORS} largest contributors, because combining every unit "
            "in range saturates at 1.00 for every segment and carries no information."
        ),
    )
