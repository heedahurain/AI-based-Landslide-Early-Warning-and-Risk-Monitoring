"""Live rainfall and soil moisture.

Source: the Open-Meteo forecast API, verified reachable on 2026-09-08 with the
full hourly variable set returning real values. No key is required.

This is the one place in the product where genuinely live data reaches the
interface today, so the provenance rules matter most here. Every response
carries a status of `live`, `cached` or `simulated`, and the age of the data.
If Open-Meteo cannot be reached, the endpoint says so rather than silently
serving something else.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["weather"])

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARIABLES = (
    "precipitation",
    "rain",
    "precipitation_probability",
    "relative_humidity_2m",
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
    "soil_moisture_3_to_9cm",
    "soil_moisture_9_to_27cm",
    "soil_moisture_27_to_81cm",
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
)

# Centre of the Noney pilot area.
DEFAULT_LAT = 24.9
DEFAULT_LON = 93.5

CACHE_TTL_SECONDS = 1800
_cache: dict[str, tuple[float, dict[str, Any]]] = {}

Provenance = Literal["live", "cached", "simulated"]


class SoilLayer(BaseModel):
    depth: str
    volumetric_water_content: float | None


class WeatherResponse(BaseModel):
    status: Provenance
    fetched_at: str
    age_minutes: int
    source: str
    latitude: float
    longitude: float
    timezone: str | None = None
    times: list[str]
    precipitation_mm: list[float | None]
    precipitation_probability: list[float | None]
    humidity_pct: list[float | None]
    soil_moisture_surface: list[float | None]
    soil_moisture_deep: list[float | None]
    rainfall_24h_mm: float
    rainfall_72h_mm: float
    rainfall_next_24h_mm: float
    current_soil_moisture: list[SoilLayer]
    # The wetness fraction the physics layer can consume directly.
    suggested_wetness_fraction: float
    note: str


def _fetch(latitude: float, longitude: float, past_days: int, forecast_days: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(HOURLY_VARIABLES),
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "Asia/Kolkata",
        }
    )
    request = urllib.request.Request(
        f"{OPEN_METEO_URL}?{query}",
        headers={"User-Agent": "ShailSuraksha/0.1 (SIH26001)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return payload


def _sum_window(values: list[float | None], start: int, end: int) -> float:
    window = values[max(0, start) : max(0, end)]
    return round(sum(v for v in window if v is not None), 1)


@router.get("/forecast", response_model=WeatherResponse)
async def forecast(
    latitude: float = Query(DEFAULT_LAT, ge=-90, le=90),
    longitude: float = Query(DEFAULT_LON, ge=-180, le=180),
    past_days: int = Query(7, ge=0, le=30),
    forecast_days: int = Query(3, ge=1, le=7),
) -> WeatherResponse:
    """Hourly rainfall and soil moisture around a point.

    Serves from a 30 minute cache. When the upstream call fails the cached
    answer is returned with a `cached` status and its true age, and when there
    is nothing cached the failure is reported rather than papered over.
    """
    key = f"{latitude:.3f},{longitude:.3f},{past_days},{forecast_days}"
    now = time.time()
    cached = _cache.get(key)

    status: Provenance = "live"
    fetched_at = now
    payload: dict[str, Any]

    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        fetched_at, payload = cached
        status = "cached"
    else:
        try:
            payload = _fetch(latitude, longitude, past_days, forecast_days)
            _cache[key] = (now, payload)
        except Exception as exc:
            log.warning("weather.fetch_failed", extra={"error": str(exc)})
            if cached:
                fetched_at, payload = cached
                status = "cached"
            else:
                from app.core.problems import ProblemDetailError

                raise ProblemDetailError(
                    status_code=503,
                    title="Weather provider unavailable",
                    detail=(
                        "Open-Meteo could not be reached and nothing is cached for this "
                        f"location. Underlying error: {type(exc).__name__}."
                    ),
                    problem_type="https://shailsuraksha.in/problems/provider-unavailable",
                ) from exc

    hourly = payload.get("hourly", {})
    times: list[str] = hourly.get("time", [])
    precipitation: list[float | None] = hourly.get("precipitation", [])

    # The forecast starts at index past_days * 24, so windows either side of
    # "now" are taken relative to that boundary.
    boundary = past_days * 24
    rainfall_24h = _sum_window(precipitation, boundary - 24, boundary)
    rainfall_72h = _sum_window(precipitation, boundary - 72, boundary)
    rainfall_next_24h = _sum_window(precipitation, boundary, boundary + 24)

    surface = hourly.get("soil_moisture_0_to_1cm", [])
    deep = hourly.get("soil_moisture_27_to_81cm", [])

    layers = [
        SoilLayer(
            depth="0 to 1 cm",
            volumetric_water_content=_at(hourly, "soil_moisture_0_to_1cm", boundary),
        ),
        SoilLayer(
            depth="1 to 3 cm",
            volumetric_water_content=_at(hourly, "soil_moisture_1_to_3cm", boundary),
        ),
        SoilLayer(
            depth="3 to 9 cm",
            volumetric_water_content=_at(hourly, "soil_moisture_3_to_9cm", boundary),
        ),
        SoilLayer(
            depth="9 to 27 cm",
            volumetric_water_content=_at(hourly, "soil_moisture_9_to_27cm", boundary),
        ),
        SoilLayer(
            depth="27 to 81 cm",
            volumetric_water_content=_at(hourly, "soil_moisture_27_to_81cm", boundary),
        ),
    ]

    # Deep soil moisture in m3/m3 mapped onto the physics layer's wetness
    # fraction. Saturation for these soils is around 0.45, so the ratio to that
    # is a defensible first approximation. It is labelled as suggested, not
    # asserted, because a proper mapping needs the soil water retention curve
    # for the actual material.
    deepest = layers[-1].volumetric_water_content
    suggested = round(min(1.0, max(0.0, (deepest or 0.0) / 0.45)), 2)

    return WeatherResponse(
        status=status,
        fetched_at=datetime.fromtimestamp(fetched_at, UTC).isoformat(timespec="seconds"),
        age_minutes=int((now - fetched_at) / 60),
        source="open_meteo_forecast",
        latitude=latitude,
        longitude=longitude,
        timezone=payload.get("timezone"),
        times=times,
        precipitation_mm=precipitation,
        precipitation_probability=hourly.get("precipitation_probability", []),
        humidity_pct=hourly.get("relative_humidity_2m", []),
        soil_moisture_surface=surface,
        soil_moisture_deep=deep,
        rainfall_24h_mm=rainfall_24h,
        rainfall_72h_mm=rainfall_72h,
        rainfall_next_24h_mm=rainfall_next_24h,
        current_soil_moisture=layers,
        suggested_wetness_fraction=suggested,
        note=(
            "Rainfall and modelled soil moisture from Open-Meteo. The wetness fraction is "
            "derived from deep soil moisture against an assumed saturation of 0.45 m3/m3 "
            "and is a first approximation, not a calibrated mapping."
        ),
    )


def _at(hourly: dict[str, Any], key: str, index: int) -> float | None:
    values = hourly.get(key) or []
    if 0 <= index < len(values):
        value = values[index]
        return float(value) if value is not None else None
    return None
