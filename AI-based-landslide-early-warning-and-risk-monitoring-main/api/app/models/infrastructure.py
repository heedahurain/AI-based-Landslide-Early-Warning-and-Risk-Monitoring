"""Roads and critical facilities from OpenStreetMap.

Phase 1 loads the geometry. Phase 7 adds betweenness centrality and the
blockage model on top of it, which is why the centrality column exists here but
stays null until then.
"""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import STORAGE_SRID
from app.db.base import Base, TimestampMixin

# OSM highway values kept for the connectivity graph. Tracks and paths are
# excluded: they carry no vehicle traffic and would inflate the graph without
# changing which villages can be reached by an ambulance or a JCB.
ROAD_CLASSES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
)

FACILITY_CATEGORIES = ("hospital", "clinic", "school", "helipad", "shelter", "police", "fire")


class RoadSegment(TimestampMixin, Base):
    __tablename__ = "road_segment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    osm_id: Mapped[str | None] = mapped_column(String(32), index=True)

    geom: Mapped[Any] = mapped_column(
        Geometry("LINESTRING", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    name: Mapped[str | None] = mapped_column(String(200))
    highway_class: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    length_m: Mapped[float] = mapped_column(Float, nullable=False)

    # A bridge or tunnel responds to an adjacent slope failure differently from
    # a cut section, so the distinction is kept for the Phase 7 blockage model.
    is_bridge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_tunnel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Populated in Phase 7. Null here rather than zero, because zero is a
    # meaningful centrality value and would be indistinguishable from unknown.
    betweenness_centrality: Mapped[float | None] = mapped_column(Float)

    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        Index("ix_road_segment_geom", "geom", postgresql_using="gist"),
        Index("ix_road_segment_class_centrality", "highway_class", "betweenness_centrality"),
    )


class CriticalFacility(TimestampMixin, Base):
    """Hospitals, schools, helipads and shelters.

    These drive the exposure terms in the Phase 8 prioritisation index, and the
    hospital catchment analysis in Phase 7.
    """

    __tablename__ = "critical_facility"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    osm_id: Mapped[str | None] = mapped_column(String(32), index=True)

    geom: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=STORAGE_SRID, spatial_index=False), nullable=False
    )

    name: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    capacity: Mapped[int | None] = mapped_column(Integer)

    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (Index("ix_critical_facility_geom", "geom", postgresql_using="gist"),)
