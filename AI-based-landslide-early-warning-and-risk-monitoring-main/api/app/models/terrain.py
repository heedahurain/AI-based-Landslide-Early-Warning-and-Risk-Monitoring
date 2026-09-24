"""Slope units and their terrain attributes.

The slope unit is the atomic risk object. It is a hydrologically derived
hillslope polygon, meaning the left-bank or right-bank half of a small basin,
bounded by the drainage line below and the divide above. A grid cell has no
physical meaning; a hillslope fails or holds as a unit, which is why every risk
score in this system is attached to one of these.
"""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import STORAGE_SRID
from app.db.base import Base, TimestampMixin


class SlopeUnit(TimestampMixin, Base):
    __tablename__ = "slope_unit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    geom: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )
    centroid: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    # Computed in EPSG:32646, never from degrees.
    area_m2: Mapped[float] = mapped_column(Float, nullable=False)

    # Provenance from the delineation run: the WhiteboxTools hillslope
    # identifier and the basin it belongs to, so a unit can be traced back to
    # the raster it came from and the run reproduced.
    hillslope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    basin_id: Mapped[int | None] = mapped_column(Integer)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Denormalised for the leave-one-district-out spatial cross-validation in
    # Phase 3. Keeping it on the row avoids a spatial join per fold.
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("district.id", ondelete="SET NULL")
    )
    village_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("village.id", ondelete="SET NULL")
    )

    terrain: Mapped[TerrainProfile | None] = relationship(
        back_populates="slope_unit", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_slope_unit_geom", "geom", postgresql_using="gist"),
        Index("ix_slope_unit_centroid", "centroid", postgresql_using="gist"),
        Index("ix_slope_unit_district_id", "district_id"),
        # The risk engine scores every unit of a run at once, so this is the
        # hot path for inference.
        Index("ix_slope_unit_run_district", "run_id", "district_id"),
    )


class TerrainProfile(TimestampMixin, Base):
    """Terrain attributes aggregated over one slope unit.

    Written once by the Phase 1 pipeline and read by every later phase. Storing
    the aggregate here rather than recomputing from rasters is what makes the
    sub-90-second full-region inference budget achievable.

    Units are explicit in the column names because a silent unit error in a
    slope angle would propagate straight into the factor-of-safety calculation.
    """

    __tablename__ = "terrain_profile"

    slope_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slope_unit.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # --- Elevation -------------------------------------------------------
    elevation_min_m: Mapped[float | None] = mapped_column(Float)
    elevation_mean_m: Mapped[float | None] = mapped_column(Float)
    elevation_max_m: Mapped[float | None] = mapped_column(Float)
    local_relief_m: Mapped[float | None] = mapped_column(Float)

    # --- Gradient --------------------------------------------------------
    # beta in the factor-of-safety equation. Degrees, not radians, and
    # converted at the point of use.
    slope_deg: Mapped[float | None] = mapped_column(Float)
    slope_max_deg: Mapped[float | None] = mapped_column(Float)
    slope_std_deg: Mapped[float | None] = mapped_column(Float)

    # Circular mean, so a unit facing due north does not average to south.
    aspect_deg: Mapped[float | None] = mapped_column(Float)

    # --- Curvature, 1/m. Negative plan curvature converges flow. ---------
    plan_curvature: Mapped[float | None] = mapped_column(Float)
    profile_curvature: Mapped[float | None] = mapped_column(Float)

    # --- Hydrology -------------------------------------------------------
    twi: Mapped[float | None] = mapped_column(Float)
    tpi: Mapped[float | None] = mapped_column(Float)
    flow_accumulation: Mapped[float | None] = mapped_column(Float)
    distance_to_stream_m: Mapped[float | None] = mapped_column(Float)

    # --- Context ---------------------------------------------------------
    # Road proximity is a proxy for cut-slope destabilisation, which was a
    # proximate cause at Tupul.
    distance_to_road_m: Mapped[float | None] = mapped_column(Float)
    distance_to_fault_m: Mapped[float | None] = mapped_column(Float)

    # ESA WorldCover class code.
    land_cover_class: Mapped[int | None] = mapped_column(SmallInteger)

    # Joins to geotech_parameter in Phase 3. Null until a lithology source is
    # obtained, and the physics layer must handle that rather than assume.
    lithology_class: Mapped[str | None] = mapped_column(String(64), index=True)

    # Estimated, typically from a terrain proxy. It appears in both the
    # numerator and denominator of the factor of safety and is a leading
    # source of error, which docs/MODEL_CARD.md §6.1 states plainly.
    soil_depth_m: Mapped[float | None] = mapped_column(Float)

    # Per-attribute provenance: which raster and which run produced each value.
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    slope_unit: Mapped[SlopeUnit] = relationship(back_populates="terrain")
