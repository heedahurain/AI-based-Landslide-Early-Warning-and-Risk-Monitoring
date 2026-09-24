# ShailSuraksha API, worker and beat all run from this image.
#
# Python 3.12 is pinned here deliberately: several geospatial and ML wheels
# (richdem, whitebox, some GDAL builds) lag the newest interpreter, and the
# container is the source of truth for the runtime.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/api:/app/ingest:/app/ml

# GDAL and PROJ are required by rasterio, geopandas and pyproj. libpq is needed
# by psycopg-family drivers; asyncpg builds without it but Alembic tooling uses it.
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies are copied and installed before the source so a code change does
# not invalidate the dependency layer.
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --requirement api/requirements.txt

COPY api ./api
COPY ingest ./ingest
COPY ml ./ml

WORKDIR /app/api

# Run as a non-root user. A service that dispatches evacuation alerts should not
# be running as root in any environment.
RUN useradd --create-home --uid 10001 shail && chown -R shail:shail /app
USER shail

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-"]
