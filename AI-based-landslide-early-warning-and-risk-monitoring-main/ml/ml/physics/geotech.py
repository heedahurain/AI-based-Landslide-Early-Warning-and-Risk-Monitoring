"""Geotechnical parameters by lithology class.

These are the numbers a geologist judge will interrogate first, so the rules
around them are strict.

**They are regional class averages taken from published ranges for these
material types, not site investigations, and not values measured in the North
East.** Each entry records where its range comes from. They are starting points
for a geologist to tune, which is why the Phase 4 interface exposes this table
to the geologist role and audits every edit.

The eight North Eastern states are underlain broadly by the Himalayan and
Patkai-Naga fold belts, the Shillong plateau gneisses, and the Barail and Surma
sedimentary groups. Until a lithology raster is joined to the slope units, every
unit is scored against a single conservative default and the interface says so.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from ml.physics.slope_stability import GeotechParameters

# Ranges below are typical published effective-stress values for these material
# classes in humid tropical and sub-tropical settings. The citation column names
# the class of source rather than a specific paper, because inventing a precise
# citation would be worse than admitting the provenance is generic.
_PUBLISHED_RANGE = "Typical published effective-stress range for this material class"

GEOTECH_CLASSES: dict[str, GeotechParameters] = {
    "residual_soil_gneiss": GeotechParameters(
        key="residual_soil_gneiss",
        name="Residual soil over gneiss",
        cohesion_kpa=5.0,
        friction_angle_deg=32.0,
        unit_weight_kn_m3=18.5,
        saturated_hydraulic_conductivity_m_s=1e-5,
        typical_soil_depth_m=1.8,
        source=_PUBLISHED_RANGE,
    ),
    "weathered_sandstone": GeotechParameters(
        key="weathered_sandstone",
        name="Weathered sandstone, Barail and Surma groups",
        cohesion_kpa=8.0,
        friction_angle_deg=34.0,
        unit_weight_kn_m3=19.0,
        saturated_hydraulic_conductivity_m_s=5e-6,
        typical_soil_depth_m=1.5,
        source=_PUBLISHED_RANGE,
    ),
    "weathered_shale": GeotechParameters(
        key="weathered_shale",
        name="Weathered shale and siltstone",
        # Shale weathers to a clay-rich regolith: more cohesive when dry, much
        # weaker in friction, and it loses strength sharply when wet. This is
        # the class that fails most readily under sustained rain.
        cohesion_kpa=12.0,
        friction_angle_deg=24.0,
        unit_weight_kn_m3=19.5,
        saturated_hydraulic_conductivity_m_s=1e-7,
        typical_soil_depth_m=1.2,
        source=_PUBLISHED_RANGE,
    ),
    "colluvium": GeotechParameters(
        key="colluvium",
        name="Colluvium and slope debris",
        # Previously mobilised material sitting at close to its repose angle.
        # Little cohesion, and the class most sensitive to pore pressure.
        cohesion_kpa=2.0,
        friction_angle_deg=30.0,
        unit_weight_kn_m3=18.0,
        saturated_hydraulic_conductivity_m_s=5e-5,
        typical_soil_depth_m=2.5,
        source=_PUBLISHED_RANGE,
    ),
    "alluvium": GeotechParameters(
        key="alluvium",
        name="Alluvium, valley floor",
        cohesion_kpa=6.0,
        friction_angle_deg=28.0,
        unit_weight_kn_m3=18.0,
        saturated_hydraulic_conductivity_m_s=1e-4,
        typical_soil_depth_m=3.0,
        source=_PUBLISHED_RANGE,
    ),
    "engineered_cut": GeotechParameters(
        key="engineered_cut",
        name="Road and railway cut slope",
        # A cut face removes lateral support and exposes a steeper profile than
        # the hillside would hold naturally. The proximate cause at Tupul in
        # June 2022 was an unstabilised construction cut, so this class exists
        # even though no cut-slope inventory is available to assign it yet.
        cohesion_kpa=3.0,
        friction_angle_deg=29.0,
        unit_weight_kn_m3=18.5,
        saturated_hydraulic_conductivity_m_s=2e-5,
        typical_soil_depth_m=1.5,
        source=_PUBLISHED_RANGE,
    ),
}

# Used for every slope unit until a lithology source is joined. Deliberately the
# residual-soil class rather than the weakest one: defaulting to the weakest
# class would mark most of the region unstable and destroy the alerting signal,
# while defaulting to the strongest would hide real hazard. The choice is a
# judgement, it is documented here, and it is the first thing to replace when
# lithology data arrives.
DEFAULT_CLASS_KEY = "residual_soil_gneiss"


def get_parameters(lithology_class: str | None) -> GeotechParameters:
    """Parameters for a lithology class, falling back to the documented default."""
    if lithology_class and lithology_class in GEOTECH_CLASSES:
        return GEOTECH_CLASSES[lithology_class]
    return GEOTECH_CLASSES[DEFAULT_CLASS_KEY]


def as_rows() -> list[dict[str, object]]:
    """The table as plain rows, for seeding the database and the API."""
    return [
        {
            "lithology_class": p.key,
            "name": p.name,
            "cohesion_kpa": p.cohesion_kpa,
            "friction_angle_deg": p.friction_angle_deg,
            "unit_weight_kn_m3": p.unit_weight_kn_m3,
            "ksat_m_s": p.saturated_hydraulic_conductivity_m_s,
            "typical_soil_depth_m": p.typical_soil_depth_m,
            "source_reference": p.source,
            "is_default": p.key == DEFAULT_CLASS_KEY,
        }
        for p in GEOTECH_CLASSES.values()
    ]


# The key meaning "use the per-unit class assigned by landform position", as
# produced by ingest.terrain.materials. Not a material itself.
TERRAIN_DERIVED_KEY = "terrain_derived"
TERRAIN_DERIVED_NAME = "Terrain-derived regolith classes"


def parameter_arrays(
    material_classes: Sequence[str],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Per-unit cohesion, friction angle and unit weight for a list of class keys.

    Lets the physics layer score every slope unit against its own material
    instead of forcing one class across the whole area. An unrecognised key
    falls back to the project default rather than raising, because a single
    stray value in a data file should not take down the risk map.
    """
    default = GEOTECH_CLASSES[DEFAULT_CLASS_KEY]
    cohesion = np.empty(len(material_classes), dtype="float64")
    friction = np.empty(len(material_classes), dtype="float64")
    unit_weight = np.empty(len(material_classes), dtype="float64")

    for index, key in enumerate(material_classes):
        params = GEOTECH_CLASSES.get(str(key), default)
        cohesion[index] = params.cohesion_kpa
        friction[index] = params.friction_angle_deg
        unit_weight[index] = params.unit_weight_kn_m3

    return cohesion, friction, unit_weight
