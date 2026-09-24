"""Named bounding boxes for the terrain pipeline.

Working at 30 m over the whole region means roughly 1.1 million by 900 thousand
pixels, which is far beyond what a laptop can hold. So the pipeline takes a
named region, and the honest engineering answer is to run pilots at full
resolution and the whole region at a coarser one, recording which was which.
Every run writes its region and resolution into the manifest, so no output can
later be mistaken for something it is not.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """A named area of interest, in EPSG:4326 as (west, south, east, north)."""

    key: str
    name: str
    west: float
    south: float
    east: float
    north: float
    note: str = ""

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)

    @property
    def width_deg(self) -> float:
        return self.east - self.west

    @property
    def height_deg(self) -> float:
        return self.north - self.south

    def estimated_pixels(self, resolution_m: float) -> int:
        """Rough pixel count at a given ground resolution.

        Uses 111,320 m per degree of latitude and shrinks longitude by the
        cosine of the mid-latitude. Good enough to warn someone before they
        start a run that cannot finish.
        """
        import math

        mid_lat_rad = math.radians((self.north + self.south) / 2)
        metres_per_deg_lat = 111_320.0
        metres_per_deg_lon = metres_per_deg_lat * math.cos(mid_lat_rad)
        rows = self.height_deg * metres_per_deg_lat / resolution_m
        cols = self.width_deg * metres_per_deg_lon / resolution_m
        return int(rows * cols)


# The full region, from the Phase 1 brief.
NER = Region(
    key="ner",
    name="North Eastern Region",
    west=88.0,
    south=21.5,
    east=97.5,
    north=29.6,
    note="All eight states. Roughly 900 gigapixels at 30 m; use a container with disk.",
)

# Pilot areas, chosen because they are where the reference events happened.
# Running the pipeline over ground that actually failed is more informative
# than running it over an arbitrary square.
NONEY = Region(
    key="noney",
    name="Noney and Tupul, Manipur",
    west=93.2,
    south=24.6,
    east=93.8,
    north=25.2,
    note="The June 2022 railway cut-slope failure that buried a Territorial Army camp.",
)

AIZAWL = Region(
    key="aizawl",
    name="Aizawl, Mizoram",
    west=92.55,
    south=23.55,
    east=93.05,
    north=23.95,
    note="The May 2024 quarry and hillside collapses during Cyclone Remal remnants.",
)

SIKKIM = Region(
    key="sikkim",
    name="Sikkim",
    west=88.0,
    south=27.0,
    east=88.95,
    north=28.15,
    note="High relief, useful for checking the pipeline against extreme terrain.",
)

REGIONS: dict[str, Region] = {r.key: r for r in (NER, NONEY, AIZAWL, SIKKIM)}


def get_region(key: str) -> Region:
    try:
        return REGIONS[key]
    except KeyError:
        available = ", ".join(sorted(REGIONS))
        raise KeyError(f"Unknown region '{key}'. Available: {available}") from None
