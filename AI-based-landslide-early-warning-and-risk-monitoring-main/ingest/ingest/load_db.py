"""Load pipeline outputs into PostGIS.

The terrain pipeline and the boundary loader both write GeoParquet, and this
module moves those into the database. Keeping the two steps separate means a
long terrain run is never lost because the database happened to be down, and it
means the pipeline can run on a machine that has no database at all.

Loads are idempotent. Slope units are keyed by (run_id, hillslope_id), which
the migration enforces with a unique constraint, so re-running replaces a run
rather than duplicating every unit in the region.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STORAGE_SRID = 4326


def _engine(database_url: str | None = None):  # type: ignore[no-untyped-def]
    from sqlalchemy.ext.asyncio import create_async_engine

    if database_url is None:
        from app.core.config import get_settings

        database_url = get_settings().database_url
    return create_async_engine(database_url, pool_pre_ping=True)


async def load_boundaries(
    states_parquet: Path, districts_parquet: Path, *, database_url: str | None = None
) -> dict[str, int]:
    """Insert or update the state and district tables.

    Names are matched on the census code rather than the name string, for the
    same reason the loader filters on it: the source misspells Arunachal
    Pradesh, and a name-keyed upsert would create a duplicate state on the
    next run rather than updating the existing one.
    """
    import geopandas as gpd
    from sqlalchemy import text

    states = gpd.read_parquet(states_parquet).to_crs(f"EPSG:{STORAGE_SRID}")
    districts = gpd.read_parquet(districts_parquet).to_crs(f"EPSG:{STORAGE_SRID}")

    engine = _engine(database_url)
    counts = {"state": 0, "district": 0}

    try:
        async with engine.begin() as conn:
            state_ids: dict[int, uuid.UUID] = {}

            for _, row in states.iterrows():
                code = str(int(row["state_code"]))
                result = await conn.execute(
                    text("SELECT id FROM state WHERE code = :code"), {"code": code}
                )
                existing = result.scalar_one_or_none()
                state_id = existing or uuid.uuid4()

                await conn.execute(
                    text(
                        """
                        INSERT INTO state (id, name, code, geom, area_km2, provisional, source,
                                           name_local, attributes)
                        VALUES (:id, :name, :code,
                                ST_Multi(ST_GeomFromText(:wkt, :srid)),
                                :area, true, :source, '{}'::jsonb, '{}'::jsonb)
                        ON CONFLICT (id) DO UPDATE
                        SET name = EXCLUDED.name,
                            geom = EXCLUDED.geom,
                            area_km2 = EXCLUDED.area_km2,
                            updated_at = now()
                        """
                    ),
                    {
                        "id": state_id,
                        "name": row["name"],
                        "code": code,
                        "wkt": row.geometry.wkt,
                        "srid": STORAGE_SRID,
                        "area": float(row["area_km2"]),
                        "source": "datameet_census_2011",
                    },
                )
                state_ids[int(row["state_code"])] = state_id
                counts["state"] += 1

            for _, row in districts.iterrows():
                code = str(int(row["census_code"]))
                result = await conn.execute(
                    text("SELECT id FROM district WHERE code = :code"), {"code": code}
                )
                existing = result.scalar_one_or_none()
                district_id = existing or uuid.uuid4()

                await conn.execute(
                    text(
                        """
                        INSERT INTO district (id, name, code, state_id, geom, area_km2,
                                              provisional, source, name_local, attributes)
                        VALUES (:id, :name, :code, :state_id,
                                ST_Multi(ST_GeomFromText(:wkt, :srid)),
                                :area, true, :source, '{}'::jsonb, '{}'::jsonb)
                        ON CONFLICT (id) DO UPDATE
                        SET name = EXCLUDED.name,
                            geom = EXCLUDED.geom,
                            area_km2 = EXCLUDED.area_km2,
                            updated_at = now()
                        """
                    ),
                    {
                        "id": district_id,
                        "name": row["district_name"],
                        "code": code,
                        "state_id": state_ids[int(row["state_code"])],
                        "wkt": row.geometry.wkt,
                        "srid": STORAGE_SRID,
                        "area": float(row["area_km2"]),
                        "source": "datameet_census_2011",
                    },
                )
                counts["district"] += 1
    finally:
        await engine.dispose()

    log.info("load.boundaries", extra=counts)
    return counts


async def load_slope_units(
    parquet: Path, *, database_url: str | None = None, batch_size: int = 1000
) -> dict[str, int]:
    """Insert slope units and their terrain profiles for one run.

    Written in batches because a regional run is hundreds of thousands of rows,
    and a single statement per row would make the load the slowest part of the
    whole pipeline.
    """
    import geopandas as gpd
    from sqlalchemy import text

    frame = gpd.read_parquet(parquet).to_crs(f"EPSG:{STORAGE_SRID}")
    if frame.empty:
        return {"slope_unit": 0, "terrain_profile": 0}

    run_id = str(frame["run_id"].iloc[0])
    engine = _engine(database_url)
    counts = {"slope_unit": 0, "terrain_profile": 0}

    profile_columns = [
        "slope_deg",
        "slope_max_deg",
        "slope_std_deg",
        "aspect_deg",
        "plan_curvature",
        "profile_curvature",
        "twi",
        "tpi",
        "flow_accumulation",
        "distance_to_stream_m",
        "local_relief_m",
        "elevation_mean_m",
    ]

    def clean(value: Any) -> float | None:
        """NaN is not a value. It must reach the database as NULL."""
        import math

        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(number) or math.isinf(number) else number

    try:
        async with engine.begin() as conn:
            # Replacing a run wholesale is simpler and safer than reconciling
            # it row by row, and the cascade removes the matching profiles.
            await conn.execute(
                text("DELETE FROM slope_unit WHERE run_id = :run_id"), {"run_id": run_id}
            )

            batch: list[dict[str, Any]] = []
            for _, row in frame.iterrows():
                unit_id = uuid.uuid4()
                record: dict[str, Any] = {
                    "id": unit_id,
                    "wkt": row.geometry.wkt,
                    "lon": float(row["centroid_lon"]),
                    "lat": float(row["centroid_lat"]),
                    "area_m2": float(row["area_m2"]),
                    "hillslope_id": int(row["hillslope_id"]),
                    "run_id": run_id,
                }
                for column in profile_columns:
                    record[column] = clean(row.get(column))
                batch.append(record)

                if len(batch) >= batch_size:
                    counts["slope_unit"] += await _write_batch(conn, batch, profile_columns)
                    batch = []

            if batch:
                counts["slope_unit"] += await _write_batch(conn, batch, profile_columns)

            # Attach each unit to the district containing its centroid. Done in
            # one spatial join rather than per row, which is the difference
            # between seconds and hours at regional scale.
            await conn.execute(
                text(
                    """
                    UPDATE slope_unit su
                    SET district_id = d.id
                    FROM district d
                    WHERE su.run_id = :run_id
                      AND ST_Intersects(d.geom, su.centroid)
                    """
                ),
                {"run_id": run_id},
            )
    finally:
        await engine.dispose()

    counts["terrain_profile"] = counts["slope_unit"]
    log.info("load.slope_units", extra={"run_id": run_id, **counts})
    return counts


async def _write_batch(conn: Any, batch: list[dict[str, Any]], profile_columns: list[str]) -> int:
    from sqlalchemy import text

    await conn.execute(
        text(
            """
            INSERT INTO slope_unit
                (id, geom, centroid, area_m2, hillslope_id, run_id)
            VALUES
                (:id,
                 ST_GeomFromText(:wkt, 4326),
                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                 :area_m2, :hillslope_id, :run_id)
            """
        ),
        batch,
    )

    columns = ", ".join(profile_columns)
    placeholders = ", ".join(f":{c}" for c in profile_columns)
    await conn.execute(
        text(
            f"""
            INSERT INTO terrain_profile (slope_unit_id, {columns}, provenance)
            VALUES (:id, {placeholders}, '{{}}'::jsonb)
            """
        ),
        batch,
    )
    return len(batch)
