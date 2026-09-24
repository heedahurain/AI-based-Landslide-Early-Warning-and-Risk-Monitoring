"""Physics-layer risk endpoints.

The factor of safety is computed on request rather than precomputed, because
the two inputs that dominate it, the material class and the wetness of the
profile, are exactly the two we have not measured. Making them query parameters
turns that weakness into the honest thing to show: move the sliders and watch
which hillsides fail under which assumption.

Scoring 14,714 units is a handful of vectorised numpy operations, so the answer
comes back in milliseconds and the interface can update as the slider moves.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.problems import ProblemDetailError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])

EQUATION = (
    "FoS = [c' + (gamma * z * cos^2(beta) - u) * tan(phi')] / (gamma * z * sin(beta) * cos(beta))"
)

DISCLAIMER = (
    "Physics layer only. This is an infinite-slope factor of safety under an "
    "assumed wetness, not a forecast and not a probability of failure. "
    "Geotechnical parameters are regional class averages, and soil depth is a "
    "terrain proxy rather than a measurement."
)


class LithologyOption(BaseModel):
    key: str
    name: str
    cohesion_kpa: float
    friction_angle_deg: float
    unit_weight_kn_m3: float
    typical_soil_depth_m: float
    source_reference: str
    is_default: bool


class StabilitySummary(BaseModel):
    unstable: int = Field(description="factor of safety below 1.0")
    marginal: int = Field(description="factor of safety between 1.0 and 1.3")
    stable: int = Field(description="factor of safety at or above 1.3")
    median_fos: float | None
    min_fos: float | None
    scored: int


class FactorOfSafetyResponse(BaseModel):
    run: str
    lithology: LithologyOption
    material_breakdown: dict[str, int] | None = None
    wetness_fraction: float
    equation: str
    disclaimer: str
    summary: StabilitySummary
    hillslope_ids: list[int]
    fos: list[float | None]


def _data_root() -> Path:
    from app.core.config import get_settings

    return Path(get_settings().data_root)


@lru_cache(maxsize=4)
def _load_inputs(path_str: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Return (hillslope ids, slope in degrees, soil depth in metres, material class).

    The material class is None for a run built before landform-based material
    assignment existed, in which case callers fall back to a single class.

    Cached: the pipeline output only changes when the pipeline is re-run, and
    re-reading a Parquet file on every slider movement would dominate the
    response time.
    """
    import geopandas as gpd

    from ml.physics.slope_stability import estimate_soil_depth

    frame = gpd.read_parquet(Path(path_str))
    ids = frame["hillslope_id"].to_numpy(dtype="int64")
    slope = frame["slope_deg"].to_numpy(dtype="float64")
    depth = estimate_soil_depth(np.nan_to_num(slope, nan=0.0))
    materials = (
        frame["material_class"].to_numpy(dtype=object) if "material_class" in frame else None
    )
    return ids, slope, depth, materials


@router.get("/lithology-classes", response_model=list[LithologyOption])
async def lithology_classes() -> list[LithologyOption]:
    """The geotechnical parameter table.

    Phase 4 makes these editable by the geologist role, with every change
    audited. They are published here so a reviewer can see exactly which
    numbers produced any factor of safety on screen.
    """
    # The dataclasses are used directly rather than the loosely typed row
    # helper, so the checker verifies each field rather than trusting a cast.
    from ml.physics.geotech import (
        GEOTECH_CLASSES,
        TERRAIN_DERIVED_KEY,
        TERRAIN_DERIVED_NAME,
    )

    # Listed first, and the default, because scoring every unit against one
    # class leaves slope angle as the only thing that varies across the map.
    terrain_option = LithologyOption(
        key=TERRAIN_DERIVED_KEY,
        name=TERRAIN_DERIVED_NAME,
        cohesion_kpa=0.0,
        friction_angle_deg=0.0,
        unit_weight_kn_m3=0.0,
        typical_soil_depth_m=0.0,
        source_reference=(
            "Each unit takes the material its landform position implies: valley floor, "
            "footslope, road cutting, or in-place weathering. Bedrock type is not resolved "
            "from terrain and must be set by a geologist or a lithological map."
        ),
        is_default=True,
    )

    return [terrain_option] + [
        LithologyOption(
            key=params.key,
            name=params.name,
            cohesion_kpa=params.cohesion_kpa,
            friction_angle_deg=params.friction_angle_deg,
            unit_weight_kn_m3=params.unit_weight_kn_m3,
            typical_soil_depth_m=params.typical_soil_depth_m,
            source_reference=params.source,
            is_default=False,
        )
        for params in GEOTECH_CLASSES.values()
    ]


@router.get("/factor-of-safety", response_model=FactorOfSafetyResponse)
async def factor_of_safety_endpoint(
    run: str = Query("noney_30m", description="terrain run identifier"),
    lithology: str | None = Query(None, description="material class key"),
    wetness: float = Query(
        0.5,
        ge=0.0,
        le=1.0,
        description="fraction of the soil profile standing saturated above the failure plane",
    ),
) -> FactorOfSafetyResponse:
    from ml.physics.geotech import (
        TERRAIN_DERIVED_KEY,
        TERRAIN_DERIVED_NAME,
        get_parameters,
        parameter_arrays,
    )
    from ml.physics.slope_stability import factor_of_safety, stability_class

    path = _data_root() / "terrain" / run / "slope_units.parquet"
    if not path.exists():
        raise ProblemDetailError(
            status_code=404,
            title="Run not available",
            detail=(
                f"No slope units for run '{run}'. Build the terrain first: "
                "python -m ingest.terrain build --bbox noney --resolution 30"
            ),
            problem_type="https://shailsuraksha.in/problems/run-not-found",
        )

    ids, slope, depth, materials = _load_inputs(str(path))
    params = get_parameters(lithology)

    # With no explicit material chosen, score every unit against the class its
    # landform position implies rather than forcing one class across the whole
    # area. That per-unit variation is what gives the risk map spatial
    # structure; a single class leaves slope angle as the only thing that
    # varies, which is why the layer used to read as a uniform wash.
    use_per_unit = lithology in (None, TERRAIN_DERIVED_KEY) and materials is not None
    breakdown: dict[str, int] | None = None

    cohesion: np.ndarray | float
    friction: np.ndarray | float
    unit_weight: np.ndarray | float

    if use_per_unit and materials is not None:
        cohesion, friction, unit_weight = parameter_arrays([str(m) for m in materials])
        unique, counts = np.unique(materials.astype(str), return_counts=True)
        breakdown = {str(k): int(v) for k, v in zip(unique, counts, strict=True)}
    else:
        cohesion = params.cohesion_kpa
        friction = params.friction_angle_deg
        unit_weight = params.unit_weight_kn_m3

    measured = np.isfinite(slope)
    values = factor_of_safety(
        slope_deg=np.nan_to_num(slope, nan=0.0),
        soil_depth_m=depth,
        cohesion_kpa=cohesion,
        friction_angle_deg=friction,
        unit_weight_kn_m3=unit_weight,
        wetness_fraction=wetness,
    )

    valid = values[measured]
    classes = stability_class(valid)

    summary = StabilitySummary(
        unstable=int(np.sum(classes == "unstable")),
        marginal=int(np.sum(classes == "marginal")),
        stable=int(np.sum(classes == "stable")),
        median_fos=round(float(np.median(valid)), 3) if valid.size else None,
        min_fos=round(float(np.min(valid)), 3) if valid.size else None,
        scored=int(valid.size),
    )

    # A unit with no measured slope is returned as null, never as zero. Zero
    # would render as the most unstable colour on the map.
    payload = [round(float(v), 3) if ok else None for v, ok in zip(values, measured, strict=True)]

    return FactorOfSafetyResponse(
        run=run,
        lithology=LithologyOption(
            key=TERRAIN_DERIVED_KEY if use_per_unit else params.key,
            name=TERRAIN_DERIVED_NAME if use_per_unit else params.name,
            cohesion_kpa=(
                round(float(np.mean(cohesion)), 2) if use_per_unit else params.cohesion_kpa
            ),
            friction_angle_deg=(
                round(float(np.mean(friction)), 2) if use_per_unit else params.friction_angle_deg
            ),
            unit_weight_kn_m3=(
                round(float(np.mean(unit_weight)), 2) if use_per_unit else params.unit_weight_kn_m3
            ),
            typical_soil_depth_m=params.typical_soil_depth_m,
            source_reference=(
                "Each slope unit is scored against the material its landform position implies "
                "(valley floor, footslope, road cutting, or in-place weathering). The values "
                "shown here are the plain means across units and are a summary only, not the "
                "parameters used. Bedrock type is NOT resolved from terrain."
                if use_per_unit
                else params.source
            ),
            is_default=lithology is None,
        ),
        material_breakdown=breakdown,
        wetness_fraction=wetness,
        equation=EQUATION,
        disclaimer=DISCLAIMER,
        summary=summary,
        hillslope_ids=[int(i) for i in ids],
        fos=payload,
    )


@router.get("/sensitivity", summary="Which input decides the answer")
async def sensitivity(run: str = Query("noney_30m")) -> dict[str, Any]:
    """Stability under every material class and a sweep of soil depths.

    This is the physics layer's most useful output. On this terrain the
    material and the regolith thickness move the result far more than the slope
    angle does, and neither has been measured, so the range matters more than
    any single number.
    """
    import json

    path = _data_root() / "terrain" / run / "physics_report.json"
    if not path.exists():
        raise ProblemDetailError(
            status_code=404,
            title="Physics report not available",
            detail=f"Run 'python -m ml.physics.compute_run --run {run}' first.",
            problem_type="https://shailsuraksha.in/problems/physics-not-computed",
        )
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return report
