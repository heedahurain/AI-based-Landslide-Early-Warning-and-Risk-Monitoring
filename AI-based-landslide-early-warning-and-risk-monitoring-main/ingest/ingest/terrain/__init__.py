"""Terrain pipeline: elevation, derivatives and hydrological slope units.

Entry point:

    python -m ingest.terrain build --bbox noney --resolution 30
"""

from ingest.terrain.regions import REGIONS, Region, get_region

__all__ = ["REGIONS", "Region", "get_region"]
