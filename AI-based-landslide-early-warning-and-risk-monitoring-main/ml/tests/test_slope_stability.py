"""Known-answer tests for the infinite-slope factor of safety.

Every expected value here is derived by hand from the closed-form solution, not
copied from a previous run of this code. A test that only asserts the code
agrees with itself would pass just as happily with the sine and cosine
transposed.

The two analytic limits do most of the work:

    dry, cohesionless        FoS = tan(phi') / tan(beta)
    fully saturated          FoS = (gamma - gamma_w) / gamma * tan(phi') / tan(beta)

Both fall straight out of the governing equation and are in every soil mechanics
textbook, so a reviewer can check them without running anything.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ml.physics.geotech import DEFAULT_CLASS_KEY, GEOTECH_CLASSES, get_parameters
from ml.physics.slope_stability import (
    FOS_CEILING,
    WATER_UNIT_WEIGHT,
    GeotechParameters,
    estimate_soil_depth,
    factor_of_safety,
    pore_pressure,
    sensitivity_band,
    stability_class,
    wetness_from_rainfall,
)


# --------------------------------------------------------------------------
# The analytic limits
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("slope_deg", "friction_deg"),
    [(20.0, 30.0), (30.0, 35.0), (35.0, 30.0), (25.0, 25.0), (45.0, 40.0), (15.0, 38.0)],
)
def test_dry_cohesionless_slope_matches_tan_phi_over_tan_beta(
    slope_deg: float, friction_deg: float
) -> None:
    """With no cohesion and no water, FoS reduces to tan(phi') / tan(beta).

    Six parameter sets, each hand-computable. Note the third case: a 35 degree
    slope of material with a 30 degree friction angle gives FoS below 1, which
    is the statement that a dry cohesionless slope cannot stand steeper than its
    angle of repose.
    """
    expected = math.tan(math.radians(friction_deg)) / math.tan(math.radians(slope_deg))

    result = factor_of_safety(
        slope_deg=slope_deg,
        soil_depth_m=1.5,
        cohesion_kpa=0.0,
        friction_angle_deg=friction_deg,
        unit_weight_kn_m3=18.0,
        wetness_fraction=0.0,
    )

    assert float(result) == pytest.approx(expected, rel=1e-9)
    # Soil depth and unit weight cancel in this limit, so a different soil of a
    # different thickness must give exactly the same answer.
    other = factor_of_safety(slope_deg, 4.0, 0.0, friction_deg, 22.0, 0.0)
    assert float(other) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize(
    ("slope_deg", "friction_deg", "unit_weight"),
    [(25.0, 33.0, 18.0), (30.0, 30.0, 19.0), (35.0, 36.0, 20.0)],
)
def test_fully_saturated_slope_matches_buoyant_unit_weight_form(
    slope_deg: float, friction_deg: float, unit_weight: float
) -> None:
    """Saturated to the surface, FoS falls by the ratio of buoyant to bulk weight."""
    expected = (
        (unit_weight - WATER_UNIT_WEIGHT)
        / unit_weight
        * math.tan(math.radians(friction_deg))
        / math.tan(math.radians(slope_deg))
    )

    result = factor_of_safety(
        slope_deg=slope_deg,
        soil_depth_m=2.0,
        cohesion_kpa=0.0,
        friction_angle_deg=friction_deg,
        unit_weight_kn_m3=unit_weight,
        wetness_fraction=1.0,
    )
    assert float(result) == pytest.approx(expected, rel=1e-9)


def test_saturation_roughly_halves_the_factor_of_safety() -> None:
    """The headline reason rainfall matters, stated as a test.

    For a soil at 18.5 kN/m3 the buoyant ratio is (18.5 - 9.81) / 18.5, about
    0.47, so wetting a cohesionless slope to the surface cuts its factor of
    safety by more than half.
    """
    dry = float(factor_of_safety(30.0, 1.5, 0.0, 33.0, 18.5, 0.0))
    wet = float(factor_of_safety(30.0, 1.5, 0.0, 33.0, 18.5, 1.0))
    ratio = wet / dry
    assert ratio == pytest.approx((18.5 - WATER_UNIT_WEIGHT) / 18.5, rel=1e-9)
    assert 0.4 < ratio < 0.5


# --------------------------------------------------------------------------
# A fully worked case with every term active
# --------------------------------------------------------------------------
def test_worked_example_with_cohesion_and_partial_saturation() -> None:
    """One case computed by hand, term by term.

    beta = 30 deg, z = 1.5 m, c' = 5 kPa, phi' = 32 deg,
    gamma = 18.5 kN/m3, m = 0.5

        cos(30)   = 0.8660254038,  cos^2 = 0.75
        sin(30)   = 0.5
        u         = 9.81 * 0.5 * 1.5 * 0.75            = 5.518125 kPa
        sigma'    = 18.5 * 1.5 * 0.75 - 5.518125       = 20.81875  - 5.518125
                                                       = 15.300625 kPa
        resisting = 5 + 15.300625 * tan(32 deg)
                  = 5 + 15.300625 * 0.6248693519       = 14.5619...
        driving   = 18.5 * 1.5 * 0.5 * 0.8660254038    = 12.01610...
        FoS       = 14.5619 / 12.0161                  = 1.2118...
    """
    beta = 30.0
    z = 1.5
    c = 5.0
    phi = 32.0
    gamma = 18.5
    m = 0.5

    cos_b = math.cos(math.radians(beta))
    sin_b = math.sin(math.radians(beta))

    u_expected = WATER_UNIT_WEIGHT * m * z * cos_b**2
    assert float(pore_pressure(m, z, beta)) == pytest.approx(u_expected, rel=1e-12)

    normal = gamma * z * cos_b**2 - u_expected
    expected = (c + normal * math.tan(math.radians(phi))) / (gamma * z * sin_b * cos_b)

    result = float(factor_of_safety(beta, z, c, phi, gamma, m))
    assert result == pytest.approx(expected, rel=1e-12)
    # Sanity against the arithmetic written out in the docstring.
    assert result == pytest.approx(1.2118, abs=1e-3)
    # And it lands in the marginal band, which is the operationally useful part.
    assert str(stability_class(result)) == "marginal"


# --------------------------------------------------------------------------
# Behaviour that must hold whatever the parameters
# --------------------------------------------------------------------------
def test_factor_of_safety_falls_monotonically_as_the_slope_wets() -> None:
    wetness = np.linspace(0.0, 1.0, 21)
    values = factor_of_safety(32.0, 1.5, 5.0, 30.0, 18.5, wetness)
    assert np.all(np.diff(values) <= 1e-12), "wetting a slope must never increase stability"


def test_factor_of_safety_falls_monotonically_as_the_slope_steepens() -> None:
    slopes = np.linspace(5.0, 60.0, 40)
    values = factor_of_safety(slopes, 1.5, 5.0, 30.0, 18.5, 0.3)
    assert np.all(np.diff(values) <= 1e-9), "a steeper slope must never be more stable"


def test_cohesion_matters_more_on_thin_soil() -> None:
    """Cohesion is a fixed strength; the driving stress grows with depth.

    So a thin cohesive soil is proportionally much stronger than a thick one,
    which is why shallow failures concentrate where regolith is deep.
    """
    thin = float(factor_of_safety(35.0, 0.5, 8.0, 30.0, 18.5, 0.3))
    thick = float(factor_of_safety(35.0, 4.0, 8.0, 30.0, 18.5, 0.3))
    assert thin > thick


def test_flat_ground_is_reported_stable_not_infinite() -> None:
    """The equation divides by sin(beta), so flat ground needs explicit handling."""
    assert float(factor_of_safety(0.0, 1.5, 5.0, 30.0, 18.5, 0.5)) == FOS_CEILING
    assert float(factor_of_safety(0.5, 1.5, 5.0, 30.0, 18.5, 0.5)) == FOS_CEILING
    assert np.all(np.isfinite(factor_of_safety(np.array([0.0, 1.0, 90.0]), 1.5, 5.0, 30.0, 18.5)))


def test_effective_stress_never_goes_negative() -> None:
    """Water cannot pull the failure plane together.

    With an absurdly high wetness on a thin soil the buoyant term would go
    negative if unclamped, producing negative friction and a factor of safety
    below zero, which is physically meaningless.
    """
    result = factor_of_safety(40.0, 0.3, 0.0, 30.0, 18.5, 1.0)
    assert float(result) >= 0.0


def test_pore_pressure_carries_the_cosine_squared_term() -> None:
    """Dropping cos^2(beta) would overstate pressure exactly where it matters."""
    steep = float(pore_pressure(1.0, 2.0, 45.0))
    flat = float(pore_pressure(1.0, 2.0, 0.0))
    assert steep == pytest.approx(flat * 0.5, rel=1e-12)


# --------------------------------------------------------------------------
# Classification, soil depth proxy and the infiltration response
# --------------------------------------------------------------------------
def test_stability_bands_match_the_documented_thresholds() -> None:
    values = np.array([0.5, 0.99, 1.0, 1.29, 1.3, 4.0])
    assert list(stability_class(values)) == [
        "unstable",
        "unstable",
        "marginal",
        "marginal",
        "stable",
        "stable",
    ]


def test_soil_depth_proxy_decreases_with_gradient() -> None:
    depths = estimate_soil_depth(np.array([0.0, 15.0, 30.0, 45.0, 70.0]))
    assert np.all(np.diff(depths) <= 0)
    assert float(depths[0]) == pytest.approx(2.5)
    assert float(depths[-1]) == pytest.approx(0.3)


def test_infiltration_is_limited_by_hydraulic_conductivity() -> None:
    """Rain arriving faster than the soil can accept it runs off.

    Both cases are 50 mm/hr for 2 hours, which is 0.1 m of rain, onto 1.5 m of
    soil with a drainable porosity of 0.35.

    Tight soil, Ksat 1e-7 m/s:
        capacity    = 1e-7 * 7200                = 0.00072 m, the binding limit
        rise        = 0.00072 / 0.35             = 0.002057 m
        added       = 0.002057 / 1.5             = 0.001371
        m           = 0.3 + 0.001371             = 0.30137

    Permeable soil, Ksat 1e-4 m/s:
        capacity    = 1e-4 * 7200                = 0.72 m, so rainfall binds
        rise        = 0.1 / 0.35                 = 0.285714 m
        added       = 0.285714 / 1.5             = 0.190476
        m           = 0.3 + 0.190476             = 0.490476

    Note what the permeable case shows: 100 mm of rain does not saturate a
    metre and a half of soil. Saturation needs either far more rain or a much
    thinner profile, which is why shallow regolith fails first.
    """
    slow = float(wetness_from_rainfall(50.0, 2.0, 1e-7, 1.5, initial_wetness=0.3))
    fast = float(wetness_from_rainfall(50.0, 2.0, 1e-4, 1.5, initial_wetness=0.3))

    assert slow < fast
    assert slow == pytest.approx(0.30137, abs=1e-4)
    assert fast == pytest.approx(0.490476, abs=1e-5)


def test_sustained_rain_on_thin_soil_reaches_saturation() -> None:
    """Six hours at 100 mm/hr is 0.6 m of rain onto 0.8 m of permeable soil.

        rise  = 0.6 / 0.35   = 1.714 m, which exceeds the profile
        added = 1.714 / 0.8  = 2.14, so m is capped at 1.0

    This is the Cyclone Remal type of event: enough rain, on thin enough
    regolith, to saturate the whole profile and halve the factor of safety.
    """
    m = float(wetness_from_rainfall(100.0, 6.0, 1e-4, 0.8, initial_wetness=0.25))
    assert m == pytest.approx(1.0)


def test_wetness_is_bounded_and_monotonic_in_rainfall() -> None:
    rain = np.linspace(0.0, 200.0, 30)
    m = wetness_from_rainfall(rain, 6.0, 1e-5, 1.5, initial_wetness=0.2)
    assert np.all(np.diff(m) >= -1e-12)
    assert float(m.min()) >= 0.0
    assert float(m.max()) <= 1.0


# --------------------------------------------------------------------------
# Parameter table
# --------------------------------------------------------------------------
def test_every_geotech_class_is_physically_admissible() -> None:
    """Construction validates each entry, so this asserts the set is complete."""
    assert DEFAULT_CLASS_KEY in GEOTECH_CLASSES
    for key, params in GEOTECH_CLASSES.items():
        assert params.key == key
        assert 0 < params.friction_angle_deg < 90
        assert params.unit_weight_kn_m3 > WATER_UNIT_WEIGHT
        assert params.saturated_hydraulic_conductivity_m_s > 0
        assert params.source


def test_a_soil_lighter_than_water_is_rejected() -> None:
    with pytest.raises(ValueError, match="float"):
        GeotechParameters(
            key="impossible",
            name="Lighter than water",
            cohesion_kpa=5.0,
            friction_angle_deg=30.0,
            unit_weight_kn_m3=5.0,
            saturated_hydraulic_conductivity_m_s=1e-5,
            typical_soil_depth_m=1.0,
            source="test",
        )


def test_unknown_lithology_falls_back_to_the_documented_default() -> None:
    assert get_parameters(None).key == DEFAULT_CLASS_KEY
    assert get_parameters("not_a_real_class").key == DEFAULT_CLASS_KEY
    assert get_parameters("colluvium").key == "colluvium"


def test_colluvium_is_more_sensitive_to_wetting_than_gneiss_residual_soil() -> None:
    """A physical expectation the parameter table must reproduce.

    Colluvium is previously mobilised debris with almost no cohesion, so it
    should lose a larger share of its strength when wet than a cohesive
    residual soil does.
    """
    colluvium = GEOTECH_CLASSES["colluvium"]
    residual = GEOTECH_CLASSES["residual_soil_gneiss"]

    def loss(p: GeotechParameters) -> float:
        dry = float(
            factor_of_safety(
                30.0, 1.5, p.cohesion_kpa, p.friction_angle_deg, p.unit_weight_kn_m3, 0.0
            )
        )
        wet = float(
            factor_of_safety(
                30.0, 1.5, p.cohesion_kpa, p.friction_angle_deg, p.unit_weight_kn_m3, 1.0
            )
        )
        return 1.0 - wet / dry

    assert loss(colluvium) > loss(residual)


def test_sensitivity_band_brackets_the_central_estimate() -> None:
    params = GEOTECH_CLASSES[DEFAULT_CLASS_KEY]
    central = factor_of_safety(
        30.0, 1.5, params.cohesion_kpa, params.friction_angle_deg, params.unit_weight_kn_m3, 0.4
    )
    low, high = sensitivity_band(30.0, 1.5, params, 0.4)
    assert float(low) < float(central) < float(high)
