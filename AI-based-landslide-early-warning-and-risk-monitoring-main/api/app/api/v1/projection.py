"""Project slope stability forward using forecast rainfall.

This is the step that turns a nowcast into a warning with lead time.

Everything needed was already in the application and simply not joined up. The
weather screen already fetched three days of forecast rainfall from Open-Meteo.
The physics layer already had an infiltration model that converts rainfall into
a profile wetness fraction, and a factor-of-safety calculation that consumes
that wetness. Nothing here acquires new data; it runs the forecast rainfall
already on screen through the physics already tested, and reports how the
stability of the 14,714 slope units moves over the next three days.

**What this is honestly not.** The infiltration model is monotonic in rainfall.
It advances a wetting front while rain falls and caps infiltration at the
saturated conductivity of the soil, but it does not model the pressure
diffusion that lets a slope fail hours after the rain has stopped. Real
rainfall-triggered failures often occur on that lag. So this projection will
tend to time the peak with the rain rather than after it, and it should be read
as "how much worse does the ground get, and roughly when", not as a failure
time. That limitation is stated in the response itself, not only here.

The empirical intensity-duration thresholds that would complement this, and the
full Iverson pressure-diffusion solution that would fix the timing, are both
still outstanding.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.problems import ProblemDetailError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/projection", tags=["projection"])

# Horizons reported, in hours ahead of now.
HORIZONS_HR = (0, 6, 12, 24, 36, 48, 72)


class ProjectionPoint(BaseModel):
    hours_ahead: int
    valid_at: str | None
    cumulative_rain_mm: float
    wetness_fraction: float
    unstable: int
    marginal: int
    stable: int
    median_fos: float | None
    min_fos: float | None


class ProjectionResponse(BaseModel):
    run: str
    scored_units: int
    current_wetness_fraction: float
    lead_time_hours: int
    first_deterioration_at_hours: int | None
    peak_unstable: int
    peak_at_hours: int | None
    points: list[ProjectionPoint]
    method: str
    limitation: str


def _data_root() -> Path:
    from app.core.config import get_settings

    return Path(get_settings().data_root)


@router.get("", response_model=ProjectionResponse)
async def project(
    run: str = Query("noney_30m"),
    latitude: float = Query(24.9, ge=-90, le=90),
    longitude: float = Query(93.5, ge=-180, le=180),
) -> ProjectionResponse:
    import geopandas as gpd

    from app.api.v1.weather import forecast as weather_forecast
    from ml.physics.geotech import get_parameters, parameter_arrays
    from ml.physics.slope_stability import (
        estimate_soil_depth,
        factor_of_safety,
        stability_class,
        wetness_from_rainfall,
    )

    path = _data_root() / "terrain" / run / "slope_units.parquet"
    if not path.exists():
        raise ProblemDetailError(
            status_code=404,
            title="Run not available",
            detail=f"No slope units for run '{run}'.",
            problem_type="https://shailsuraksha.in/problems/run-not-found",
        )

    # Every argument is passed explicitly. Calling an endpoint function
    # directly bypasses FastAPI's dependency resolution, so any omitted
    # parameter arrives as the Query object itself rather than its default,
    # which silently corrupts both the cache key and the upstream request.
    past_days = 7
    weather = await weather_forecast(
        latitude=latitude, longitude=longitude, past_days=past_days, forecast_days=3
    )

    # The forecast half of the series starts at the past/future boundary.
    boundary = past_days * 24
    precipitation = [value or 0.0 for value in weather.precipitation_mm]
    times = weather.times
    current_wetness = weather.suggested_wetness_fraction

    frame = gpd.read_parquet(path)
    slope = np.nan_to_num(frame["slope_deg"].to_numpy(dtype="float64"), nan=0.0)
    depth = estimate_soil_depth(slope)
    measured = np.isfinite(frame["slope_deg"].to_numpy(dtype="float64"))

    params = get_parameters(None)
    cohesion: Any = params.cohesion_kpa
    friction: Any = params.friction_angle_deg
    unit_weight: Any = params.unit_weight_kn_m3
    conductivity: Any = params.saturated_hydraulic_conductivity_m_s
    if "material_class" in frame:
        cohesion, friction, unit_weight = parameter_arrays(
            [str(m) for m in frame["material_class"].to_numpy(dtype=object)]
        )

    points: list[ProjectionPoint] = []
    for hours in HORIZONS_HR:
        window = precipitation[boundary : boundary + hours] if hours else []
        cumulative_mm = float(sum(window))

        if hours == 0:
            wetness_array = np.full(slope.shape, current_wetness, dtype="float64")
        else:
            # Mean intensity over the window, fed through the infiltration model
            # starting from the wetness the ground is actually at now.
            intensity = cumulative_mm / hours
            wetness_array = wetness_from_rainfall(
                rainfall_intensity_mm_hr=intensity,
                duration_hr=float(hours),
                saturated_conductivity_m_s=conductivity,
                soil_depth_m=depth,
                initial_wetness=current_wetness,
            )

        values = factor_of_safety(
            slope_deg=slope,
            soil_depth_m=depth,
            cohesion_kpa=cohesion,
            friction_angle_deg=friction,
            unit_weight_kn_m3=unit_weight,
            wetness_fraction=wetness_array,
        )
        valid = values[measured]
        classes = stability_class(valid)

        index = boundary + hours
        points.append(
            ProjectionPoint(
                hours_ahead=hours,
                valid_at=times[index] if index < len(times) else None,
                cumulative_rain_mm=round(cumulative_mm, 1),
                wetness_fraction=round(float(np.mean(wetness_array)), 3),
                unstable=int(np.sum(classes == "unstable")),
                marginal=int(np.sum(classes == "marginal")),
                stable=int(np.sum(classes == "stable")),
                median_fos=round(float(np.median(valid)), 3) if valid.size else None,
                min_fos=round(float(np.min(valid)), 3) if valid.size else None,
            )
        )

    baseline = points[0].unstable
    deterioration = next((p.hours_ahead for p in points if p.unstable > baseline), None)
    peak = max(points, key=lambda p: p.unstable)

    return ProjectionResponse(
        run=run,
        scored_units=int(np.sum(measured)),
        current_wetness_fraction=current_wetness,
        lead_time_hours=HORIZONS_HR[-1],
        first_deterioration_at_hours=deterioration,
        peak_unstable=peak.unstable,
        peak_at_hours=peak.hours_ahead,
        points=points,
        method=(
            "Forecast hourly rainfall from Open-Meteo is accumulated to each horizon, "
            "converted to a profile wetness fraction by the Green-Ampt style infiltration "
            "model in ml.physics.slope_stability, and run through the same infinite-slope "
            "factor of safety used everywhere else. Each unit keeps the material its "
            "landform position implies."
        ),
        limitation=(
            "The infiltration model is monotonic in rainfall: it has no pressure-diffusion "
            "term, so it cannot reproduce a failure that occurs hours after the rain stops. "
            "Read this as how much worse the ground gets and roughly when, not as a "
            "predicted failure time."
        ),
    )
