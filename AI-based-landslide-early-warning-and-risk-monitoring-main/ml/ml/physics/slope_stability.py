"""Infinite-slope stability with pore water pressure.

This is the defensible floor of the risk engine. It has no training data, so it
cannot overfit, and a geologist can check every term against a textbook. That is
exactly why it exists: when asked "why should I trust this number", the answer
is an equation with the inputs substituted, not a model artefact.

The governing equation, for a planar failure surface parallel to the ground and
seepage parallel to the slope:

    FoS = [c' + (gamma * z * cos^2(beta) - u) * tan(phi')]
          / (gamma * z * sin(beta) * cos(beta))

    c'    effective cohesion                     kPa
    phi'  effective angle of internal friction   degrees
    gamma bulk unit weight of the soil           kN/m^3
    z     vertical soil thickness above the failure plane   m
    beta  slope angle                            degrees
    u     pore water pressure on the failure plane          kPa

Below 1.0 the slope is unstable, 1.0 to 1.3 is marginal, above 1.3 is stable
under these assumptions. The assumptions matter and are stated in
docs/MODEL_CARD.md: a planar surface, a slope long enough that end effects are
negligible, and no seismic loading.

Two limits are worth remembering because they are the tests at the bottom of
this module:

    dry, cohesionless        FoS = tan(phi') / tan(beta)
    fully saturated          FoS = (gamma - gamma_w) / gamma * tan(phi') / tan(beta)

The second is roughly half the first for typical soils, which is the whole
reason rainfall matters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

# Unit weight of water at 10 degrees Celsius, kN/m^3.
WATER_UNIT_WEIGHT = 9.81

# Gravitational acceleration, m/s^2. Used by the infiltration response.
GRAVITY = 9.81

# Below this gradient the infinite-slope model does not apply: the denominator
# tends to zero and the factor of safety to infinity. Flat ground does not slide,
# so it is reported as stable rather than as a very large number.
MIN_SLOPE_DEG = 1.0

# Above this the surface is rock face rather than a soil-mantled hillslope, and
# a soil-mechanics model is the wrong tool.
MAX_SLOPE_DEG = 85.0

# Reported ceiling. An unbounded factor of safety is meaningless to display and
# distorts every colour scale it appears in.
FOS_CEILING = 10.0

STABLE_THRESHOLD = 1.3
MARGINAL_THRESHOLD = 1.0


@dataclass(frozen=True)
class GeotechParameters:
    """Effective-stress parameters for one lithology or soil class.

    Values are regional class averages, not site investigations. They are the
    dominant source of uncertainty in the output, which is why the risk engine
    reports a sensitivity band rather than a single factor of safety.
    """

    key: str
    name: str
    cohesion_kpa: float
    friction_angle_deg: float
    unit_weight_kn_m3: float
    saturated_hydraulic_conductivity_m_s: float
    typical_soil_depth_m: float
    source: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.friction_angle_deg < 90.0:
            raise ValueError(f"{self.key}: friction angle must be in [0, 90)")
        if self.unit_weight_kn_m3 <= WATER_UNIT_WEIGHT:
            raise ValueError(
                f"{self.key}: bulk unit weight {self.unit_weight_kn_m3} kN/m3 must exceed "
                f"that of water ({WATER_UNIT_WEIGHT}); a soil lighter than water would float"
            )
        if self.cohesion_kpa < 0:
            raise ValueError(f"{self.key}: cohesion cannot be negative")
        if self.typical_soil_depth_m <= 0:
            raise ValueError(f"{self.key}: soil depth must be positive")


def pore_pressure(
    wetness_fraction: FloatArray | float,
    soil_depth_m: FloatArray | float,
    slope_deg: FloatArray | float,
    water_unit_weight: float = WATER_UNIT_WEIGHT,
) -> FloatArray:
    """Pore water pressure on the failure plane, in kPa.

    For slope-parallel seepage with a water table standing at a height
    ``m * z`` above the failure plane:

        u = gamma_w * m * z * cos^2(beta)

    ``wetness_fraction`` is that ``m``: 0 is a dry profile, 1 is saturated to the
    ground surface. The cosine-squared term is not decorative. It is the
    component of the water column acting normal to the failure plane, and
    dropping it overestimates pore pressure on steep ground, which is precisely
    where the answer matters.
    """
    m = np.clip(np.asarray(wetness_fraction, dtype="float64"), 0.0, 1.0)
    z = np.asarray(soil_depth_m, dtype="float64")
    beta = np.deg2rad(np.asarray(slope_deg, dtype="float64"))
    return np.asarray(water_unit_weight * m * z * np.cos(beta) ** 2, dtype="float64")


def factor_of_safety(
    slope_deg: FloatArray | float,
    soil_depth_m: FloatArray | float,
    cohesion_kpa: FloatArray | float,
    friction_angle_deg: FloatArray | float,
    unit_weight_kn_m3: FloatArray | float,
    wetness_fraction: FloatArray | float = 0.0,
    *,
    ceiling: float = FOS_CEILING,
) -> FloatArray:
    """Factor of safety for an infinite slope, vectorised over slope units.

    Vectorised rather than looped because the risk engine has to score the whole
    region inside 90 seconds, and because the same array maths runs unchanged
    for one unit or for a million.
    """
    beta_deg = np.asarray(slope_deg, dtype="float64")
    z = np.asarray(soil_depth_m, dtype="float64")
    c = np.asarray(cohesion_kpa, dtype="float64")
    phi = np.deg2rad(np.asarray(friction_angle_deg, dtype="float64"))
    gamma = np.asarray(unit_weight_kn_m3, dtype="float64")

    beta = np.deg2rad(np.clip(beta_deg, MIN_SLOPE_DEG, MAX_SLOPE_DEG))

    u = pore_pressure(wetness_fraction, z, np.rad2deg(beta))

    # Effective normal stress on the failure plane. It cannot go negative:
    # soil does not pull the plane together, and a negative value would produce
    # a nonsensical negative friction contribution.
    normal_stress = gamma * z * np.cos(beta) ** 2 - u
    normal_stress = np.maximum(normal_stress, 0.0)

    resisting = c + normal_stress * np.tan(phi)
    driving = gamma * z * np.sin(beta) * np.cos(beta)

    with np.errstate(divide="ignore", invalid="ignore"):
        fos = np.where(driving > 0, resisting / driving, ceiling)

    # Ground flatter than the model's floor is reported stable rather than
    # infinite, and everything is capped so the number stays displayable.
    fos = np.where(beta_deg < MIN_SLOPE_DEG, ceiling, fos)
    return np.asarray(np.clip(fos, 0.0, ceiling), dtype="float64")


def wetness_from_rainfall(
    rainfall_intensity_mm_hr: FloatArray | float,
    duration_hr: FloatArray | float,
    saturated_conductivity_m_s: FloatArray | float,
    soil_depth_m: FloatArray | float,
    initial_wetness: FloatArray | float = 0.3,
    drainable_porosity: float = 0.35,
) -> FloatArray:
    """Wetness fraction after rain, as a simplified transient response.

    This is the reduced form of the Iverson and Green-Ampt treatment: the
    wetting front advances while rain falls, and infiltration is limited by the
    saturated hydraulic conductivity of the soil, so rain arriving faster than
    the soil can accept it runs off rather than raising pore pressure.

        infiltrated depth = min(rainfall, Ksat * duration)
        rise in water table = infiltrated depth / drainable porosity
        m = m0 + rise / z, capped at 1

    What this deliberately does not do is model the pressure diffusion that
    gives the full Iverson solution its time lag, where a slope can fail hours
    after the rain stops. That needs the soil-moisture time series from Phase 2.
    Until then this response is monotonic in rainfall, which is the right
    behaviour for a scenario tool and the wrong behaviour for a forecast, and it
    is labelled that way wherever it is used.
    """
    rain_m = np.asarray(rainfall_intensity_mm_hr, dtype="float64") / 1000.0
    hours = np.asarray(duration_hr, dtype="float64")
    ksat = np.asarray(saturated_conductivity_m_s, dtype="float64")
    z = np.asarray(soil_depth_m, dtype="float64")
    m0 = np.clip(np.asarray(initial_wetness, dtype="float64"), 0.0, 1.0)

    total_rain_m = rain_m * hours
    capacity_m = ksat * hours * 3600.0
    infiltrated_m = np.minimum(total_rain_m, capacity_m)

    rise_m = infiltrated_m / max(drainable_porosity, 1e-6)
    with np.errstate(divide="ignore", invalid="ignore"):
        added = np.where(z > 0, rise_m / z, 0.0)

    return np.asarray(np.clip(m0 + added, 0.0, 1.0), dtype="float64")


def estimate_soil_depth(
    slope_deg: FloatArray | float,
    max_depth_m: float = 2.5,
    min_depth_m: float = 0.3,
    decay_slope_deg: float = 45.0,
) -> FloatArray:
    """Soil thickness estimated from gradient, in metres.

    **This is a proxy, not a measurement.** No soil-depth survey exists for the
    region, and soil depth appears in both the numerator and the denominator of
    the factor of safety, which makes it a leading source of error. The model
    card says so plainly.

    The proxy encodes one robust field observation: steep ground sheds its
    regolith and gentle ground accumulates it, so thickness falls as gradient
    rises. Depth decays linearly from ``max_depth_m`` on flat ground to
    ``min_depth_m`` at ``decay_slope_deg`` and stays there beyond.

    Replacing this with a real soil-thickness raster is one of the highest-value
    improvements available to this project.
    """
    beta = np.asarray(slope_deg, dtype="float64")
    fraction = np.clip(beta / decay_slope_deg, 0.0, 1.0)
    depth = max_depth_m - (max_depth_m - min_depth_m) * fraction
    return np.asarray(np.clip(depth, min_depth_m, max_depth_m), dtype="float64")


def stability_class(fos: FloatArray | float) -> npt.NDArray[np.str_]:
    """Map a factor of safety onto the three textbook bands."""
    values = np.asarray(fos, dtype="float64")
    return np.asarray(
        np.select(
            [values < MARGINAL_THRESHOLD, values < STABLE_THRESHOLD],
            ["unstable", "marginal"],
            default="stable",
        )
    )


def sensitivity_band(
    slope_deg: FloatArray | float,
    soil_depth_m: FloatArray | float,
    parameters: GeotechParameters,
    wetness_fraction: FloatArray | float = 0.0,
    *,
    cohesion_spread: float = 0.4,
    friction_spread_deg: float = 3.0,
) -> tuple[FloatArray, FloatArray]:
    """Factor of safety under pessimistic and optimistic parameter choices.

    Regional class averages carry real uncertainty, so a single factor of safety
    overstates what is known. This returns the low and high ends produced by
    varying cohesion by a fraction and the friction angle by a few degrees,
    which is what the interface shows as a band. A confident-looking wrong
    number is the failure mode this exists to prevent.
    """
    low = factor_of_safety(
        slope_deg,
        soil_depth_m,
        parameters.cohesion_kpa * (1.0 - cohesion_spread),
        parameters.friction_angle_deg - friction_spread_deg,
        parameters.unit_weight_kn_m3,
        wetness_fraction,
    )
    high = factor_of_safety(
        slope_deg,
        soil_depth_m,
        parameters.cohesion_kpa * (1.0 + cohesion_spread),
        parameters.friction_angle_deg + friction_spread_deg,
        parameters.unit_weight_kn_m3,
        wetness_fraction,
    )
    return low, high
