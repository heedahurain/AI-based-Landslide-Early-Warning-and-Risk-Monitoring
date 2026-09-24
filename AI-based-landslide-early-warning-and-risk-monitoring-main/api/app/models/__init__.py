"""SQLAlchemy models.

Importing them here registers every table on Base.metadata, which is what
Alembic autogenerate compares against the live schema. A model that is not
imported here is invisible to migrations.
"""

from app.models.admin import Block, District, State, Village
from app.models.infrastructure import CriticalFacility, RoadSegment
from app.models.terrain import SlopeUnit, TerrainProfile

__all__ = [
    "Block",
    "CriticalFacility",
    "District",
    "RoadSegment",
    "SlopeUnit",
    "State",
    "TerrainProfile",
    "Village",
]
