"""ShailSuraksha API.

Phase 0 exposes only what the platform itself needs: liveness, readiness,
metadata and metrics. Domain routers arrive with their phases, listed in
PROJECT_CONTEXT.md §16.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import (
    connectivity,
    geo,
    health,
    location,
    projection,
    reports,
    risk,
    weather,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.problems import register_exception_handlers

settings = get_settings()
configure_logging(debug=settings.debug)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info(
        "api.startup",
        environment=settings.environment,
        bbox=settings.ner_bbox,
    )
    yield
    log.info("api.shutdown")


app = FastAPI(
    title=settings.app_name,
    version=health.API_VERSION,
    description=(
        "Landslide early-warning and risk-monitoring API for the eight North "
        "Eastern states of India. Decision-support only: it does not replace "
        "official warnings from the Geological Survey of India or the India "
        "Meteorological Department."
    ),
    # FastAPI emits OpenAPI 3.1 for this version string.
    openapi_version="3.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# GeoJSON is highly repetitive text and compresses by roughly five times, which
# is the difference between an 8 MB layer and a 1.5 MB one on a slow connection.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# /metrics for Prometheus. Excluded from the OpenAPI schema because it is an
# operational endpoint, not part of the public contract.
Instrumentator().instrument(app).expose(app, include_in_schema=False)

app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(geo.router, prefix=settings.api_v1_prefix)
app.include_router(risk.router, prefix=settings.api_v1_prefix)
app.include_router(weather.router, prefix=settings.api_v1_prefix)
app.include_router(connectivity.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)
app.include_router(location.router, prefix=settings.api_v1_prefix)
app.include_router(projection.router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
