"""Application settings.

Every value is environment driven with a development-safe default, and nothing
secret has a usable default. `.env.example` at the repository root lists the
full set.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The North Eastern Region bounding box, in EPSG:4326. Every ingest and terrain
# job is clipped to this. Source: PROJECT_CONTEXT.md and the Phase 1 brief.
NER_BBOX_WEST = 88.0
NER_BBOX_SOUTH = 21.5
NER_BBOX_EAST = 97.5
NER_BBOX_NORTH = 29.6

# Area and distance computations use UTM zone 46N. Geometry is stored in 4326.
STORAGE_SRID = 4326
COMPUTATION_SRID = 32646

# The signing key shipped for local development. Production must override it;
# Settings refuses to start otherwise.
DEV_JWT_SECRET = "dev-only-not-a-secret"

NER_STATES = (
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Service identity ---------------------------------------------------
    app_name: str = "ShailSuraksha API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Where the ingest pipelines write their outputs. The geo endpoints read
    # these directly, so the map works before a database exists.
    data_root: str = "data"

    # --- Datastores ---------------------------------------------------------
    database_url: str = "postgresql+asyncpg://shail:shail@localhost:5432/shailsuraksha"
    redis_url: str = "redis://localhost:6379/0"

    # --- Object storage -----------------------------------------------------
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "shailsuraksha"

    # --- MQTT ---------------------------------------------------------------
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "shailsuraksha/sensors"

    # --- Security -----------------------------------------------------------
    # No default. Startup fails loudly in production rather than running with a
    # predictable signing key.
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Provider toggles ---------------------------------------------------
    # Each provider can be switched off without touching code. When a provider
    # is disabled or fails, the registry falls back to the synthetic engine and
    # the response is labelled SIMULATED. See docs/DATA_SOURCES.md.
    enable_open_meteo: bool = True
    enable_nasa_power: bool = True
    enable_gpm_imerg: bool = False
    enable_planetary_computer: bool = True
    enable_osm: bool = True
    provider_cache_ttl_seconds: int = 1800
    provider_timeout_seconds: float = 20.0

    # --- Credentials for key-gated sources ----------------------------------
    earthdata_username: str | None = None
    earthdata_password: str | None = None
    opentopography_api_key: str | None = None

    @model_validator(mode="after")
    def _reject_default_secret_outside_development(self) -> "Settings":
        # A predictable signing key in a system that authorises evacuation
        # alerts is not acceptable anywhere but a laptop, so refuse to start.
        if self.environment != "development" and self.jwt_secret_key == DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY is still the development default. "
                f"Set a real secret before running in {self.environment}."
            )
        return self

    @property
    def ner_bbox(self) -> tuple[float, float, float, float]:
        """West, south, east, north in EPSG:4326."""
        return (NER_BBOX_WEST, NER_BBOX_SOUTH, NER_BBOX_EAST, NER_BBOX_NORTH)


@lru_cache
def get_settings() -> Settings:
    return Settings()
