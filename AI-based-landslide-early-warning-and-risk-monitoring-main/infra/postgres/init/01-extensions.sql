-- Extensions required by the domain model.
--
-- PostGIS carries every geometry: admin boundaries, slope units, road segments,
-- citizen report locations. TimescaleDB carries the time series: rainfall,
-- soil moisture and sensor readings, as hypertables with continuous aggregates.
-- Alembic migrations in Phase 1 assume both are present.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Trigram search backs the command palette, which must find a village by a
-- partial or misspelled name.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Deterministic UUID generation for alert and report identifiers.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
