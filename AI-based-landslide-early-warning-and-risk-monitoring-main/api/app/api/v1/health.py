"""Liveness, readiness and build metadata.

Readiness deliberately reports each dependency separately. "The API is up" and
"the API can serve a risk query" are different statements, and during an
incident the difference matters.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import NER_STATES, Settings, get_settings

router = APIRouter(tags=["status"])

ComponentState = Literal["ok", "degraded", "unavailable", "not_configured"]


class ComponentHealth(BaseModel):
    name: str
    state: ComponentState
    detail: str


class ReadinessResponse(BaseModel):
    ready: bool
    components: list[ComponentHealth]


class MetaResponse(BaseModel):
    name: str
    version: str
    phase: str
    environment: str
    states_covered: list[str]
    bbox: tuple[float, float, float, float]
    disclaimer: str


# Bumped when the API contract changes, not on every commit.
API_VERSION = "0.1.0"
CURRENT_PHASE = "0 of 11 — foundation"

DISCLAIMER = (
    "Decision-support tool. Not a substitute for official warnings from the "
    "Geological Survey of India or the India Meteorological Department."
)


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """Answers only "is this process running". Never touches a dependency."""
    return {"status": "ok"}


async def _check_postgres(settings: Settings) -> ComponentHealth:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return ComponentHealth(name="postgres", state="ok", detail="connection established")
        finally:
            await engine.dispose()
    except Exception as exc:  # noqa: BLE001 - a readiness probe reports, never raises
        return ComponentHealth(name="postgres", state="unavailable", detail=str(exc)[:200])


async def _check_redis(settings: Settings) -> ComponentHealth:
    try:
        # Redis.from_url is typed; the module-level from_url helper is not.
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url)
        try:
            await client.ping()
            return ComponentHealth(name="redis", state="ok", detail="ping succeeded")
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(name="redis", state="unavailable", detail=str(exc)[:200])


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(response: Response) -> ReadinessResponse:
    settings = get_settings()
    components = list(await asyncio.gather(_check_postgres(settings), _check_redis(settings)))
    is_ready = all(component.state == "ok" for component in components)
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(ready=is_ready, components=components)


@router.get("/meta", response_model=MetaResponse, summary="Build and coverage metadata")
async def meta() -> MetaResponse:
    settings = get_settings()
    return MetaResponse(
        name=settings.app_name,
        version=API_VERSION,
        phase=CURRENT_PHASE,
        environment=settings.environment,
        states_covered=list(NER_STATES),
        bbox=settings.ner_bbox,
        disclaimer=DISCLAIMER,
    )
