"""Administrative hierarchy: state, district, block, village.

Four tables rather than one self-referencing table. The levels carry different
attributes in practice (a village has households, a state does not), the joins
are the ones the dashboards actually make, and typed foreign keys let the
database reject a village parented to a state.

Geometry is stored in EPSG:4326. Area and distance are computed in EPSG:32646,
per PROJECT_CONTEXT.md §5.
"""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import STORAGE_SRID
from app.db.base import Base, TimestampMixin


class AdminAttributesMixin:
    """Columns every level of the hierarchy shares."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # Name per locale, so a village can be shown in the reader's own script.
    # Keyed by the locale codes in web/src/i18n/routing.ts.
    name_local: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Census or Local Government Directory code where one is known.
    code: Mapped[str | None] = mapped_column(String(32), index=True)

    area_km2: Mapped[float | None] = mapped_column(Float)
    population: Mapped[int | None] = mapped_column(Integer)
    households: Mapped[int | None] = mapped_column(Integer)

    # True when the geometry does not come from an official source. This is
    # load-bearing: community boundary data disagrees with Survey of India
    # boundaries along the international and interstate borders of the North
    # East, and the interface must label such geometry as indicative rather
    # than authoritative. Never default this to False for convenience.
    provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Provider key from the ingest registry, so any row can be traced back to
    # the fetch that produced it.
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class State(AdminAttributesMixin, TimestampMixin, Base):
    __tablename__ = "state"

    geom: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    districts: Mapped[list[District]] = relationship(back_populates="state")

    __table_args__ = (Index("ix_state_geom", "geom", postgresql_using="gist"),)


class District(AdminAttributesMixin, TimestampMixin, Base):
    __tablename__ = "district"

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("state.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    state: Mapped[State] = relationship(back_populates="districts")
    blocks: Mapped[list[Block]] = relationship(back_populates="district")

    __table_args__ = (
        Index("ix_district_geom", "geom", postgresql_using="gist"),
        Index("ix_district_state_id", "state_id"),
    )


class Block(AdminAttributesMixin, TimestampMixin, Base):
    __tablename__ = "block"

    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("district.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    district: Mapped[District] = relationship(back_populates="blocks")
    villages: Mapped[list[Village]] = relationship(back_populates="block")

    __table_args__ = (
        Index("ix_block_geom", "geom", postgresql_using="gist"),
        Index("ix_block_district_id", "district_id"),
    )


class Village(AdminAttributesMixin, TimestampMixin, Base):
    __tablename__ = "village"

    block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("block.id", ondelete="SET NULL")
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("district.id", ondelete="CASCADE"), nullable=False
    )

    # A village is a polygon where a boundary is known and a point where only a
    # settlement location is known. Both are stored; the interface prefers the
    # polygon and falls back to a buffered point.
    geom: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=STORAGE_SRID, spatial_index=False)
    )
    centroid: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    # Demographics used by the Phase 8 response-prioritisation index.
    population_children: Mapped[int | None] = mapped_column(Integer)
    population_elderly: Mapped[int | None] = mapped_column(Integer)
    population_disabled: Mapped[int | None] = mapped_column(Integer)

    pin_code: Mapped[str | None] = mapped_column(String(10), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    block: Mapped[Block | None] = relationship(back_populates="villages")

    __table_args__ = (
        Index("ix_village_geom", "geom", postgresql_using="gist"),
        Index("ix_village_centroid", "centroid", postgresql_using="gist"),
        Index("ix_village_district_id", "district_id"),
    )
