"""Whether a failing slope can actually reach a road, and how likely it is to fail.

Two separate ideas live here, both of which were missing from the first version
of the road blockage calculation and both of which it needed.

**Probability of failure from a factor of safety.** The first implementation
mapped a factor of safety to a probability with ``clip(2 - FoS, 0, 1)``. That
is indefensible: it assigns a slope with FoS 1.39, which the model itself calls
stable, a 61 percent chance of failing. The standard geotechnical treatment is
a reliability calculation, not a linear rescaling. Parameter uncertainty makes
the factor of safety a random variable rather than a single number, so the
quantity of interest is the probability that it falls below one. Assuming FoS
is lognormally distributed, which keeps it positive and is the usual first-order
assumption in the reliability literature, gives

    P(failure) = Phi( ln(1 / FoS_median) / sigma_lnFoS )

with ``sigma_lnFoS = sqrt(ln(1 + COV^2))``. The coefficient of variation carries
the uncertainty in cohesion, friction angle and regolith thickness. This is the
first-order second-moment approach described in the standard references on
reliability in geotechnical engineering; the COV value used here is an
assumption of this project, not a measured quantity, and is stated as such in
the model card.

**Angle of reach.** A slope unit 2 km away cannot bury a road no matter how
unstable it is, but the first implementation let every unit inside a flat 250 m
buffer contribute equally. The travel distance of a landslide is bounded by its
angle of reach, the angle subtended between the crown of the source and the
distal end of the deposit. Debris reaches a target only when

    arctan(H / L) >= alpha_reach

where H is the height of the source above the target and L the horizontal
distance. Shallow debris slides on these hillsides have angles of reach in
roughly the 20 to 35 degree range, so a source 100 m above a road can deliver
material about 250 m horizontally, which is where the existing buffer distance
comes from. Sources far below that limit contribute nothing; sources well above
it contribute fully.

Both parameters are assumptions of the model, not measurements, and both are
exposed rather than buried.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

# Uncertainty in the computed factor of safety, as a coefficient of variation.
# Dominated by the unmeasured terms: cohesion, friction angle and regolith
# thickness. An assumption of this project, recorded in the model card.
FOS_COEFFICIENT_OF_VARIATION = 0.25

# Below this angle of reach, debris does not arrive.
ANGLE_OF_REACH_MIN_DEG = 22.0
# At or above this angle the source is effectively overhead and delivers fully.
ANGLE_OF_REACH_FULL_DEG = 35.0


def probability_of_failure(
    factor_of_safety: NDArray[np.float64] | float,
    coefficient_of_variation: float = FOS_COEFFICIENT_OF_VARIATION,
) -> NDArray[np.float64]:
    """P(FoS < 1) treating the factor of safety as lognormal about its median.

    A factor of safety of exactly 1.0 returns 0.5 by construction, which is the
    correct sanity check: at the limit state, failure is a coin toss.
    """
    if coefficient_of_variation <= 0.0:
        raise ValueError("coefficient_of_variation must be positive")

    fos = np.asarray(factor_of_safety, dtype="float64")
    sigma = math.sqrt(math.log(1.0 + coefficient_of_variation**2))

    # Guard the log: a non-positive factor of safety means the slope has already
    # failed under the model's own assumptions.
    safe = np.where(fos > 1e-9, fos, 1e-9)
    z = np.log(1.0 / safe) / sigma
    probability = 0.5 * (1.0 + _erf(z / math.sqrt(2.0)))
    return np.clip(probability, 0.0, 1.0).astype("float64")


def _erf(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Vectorised error function, so the module needs no SciPy dependency."""
    result = np.vectorize(math.erf, otypes=["float64"])(values)
    return np.asarray(result, dtype="float64")


def reach_weight(
    height_above_m: NDArray[np.float64] | float,
    horizontal_distance_m: NDArray[np.float64] | float,
    minimum_angle_deg: float = ANGLE_OF_REACH_MIN_DEG,
    full_angle_deg: float = ANGLE_OF_REACH_FULL_DEG,
) -> NDArray[np.float64]:
    """How much of a source's failure probability is actually delivered downslope.

    Returns 0 where the travel angle is too shallow for debris to arrive, 1
    where the source sits steeply above the target, and a linear ramp between.
    A source at or below the level of the target returns 0: it cannot slide
    onto something that is not beneath it.
    """
    if not minimum_angle_deg < full_angle_deg:
        raise ValueError("minimum_angle_deg must be below full_angle_deg")

    height = np.asarray(height_above_m, dtype="float64")
    distance = np.asarray(horizontal_distance_m, dtype="float64")

    # A source level with or below the road delivers nothing. A source directly
    # overhead, at zero horizontal distance, delivers fully.
    safe_distance = np.where(distance > 1.0, distance, 1.0)
    travel_angle_deg = np.degrees(np.arctan(np.maximum(height, 0.0) / safe_distance))

    span = full_angle_deg - minimum_angle_deg
    weight = (travel_angle_deg - minimum_angle_deg) / span
    weight = np.where(height <= 0.0, 0.0, weight)
    return np.clip(weight, 0.0, 1.0).astype("float64")


def expected_blockages(delivered: NDArray[np.float64]) -> float:
    """Expected number of failures that reach the segment.

    The metric that does not saturate. Summing delivery probabilities gives the
    expected count directly, by linearity of expectation, and it keeps rising
    with the number of threatening slopes instead of pinning at one.
    """
    return float(np.sum(delivered))


def blockage_probability(delivered: NDArray[np.float64], top_k: int = 5) -> float:
    """P(at least one of the k most threatening sources reaches the segment).

    Restricted to the top k contributors on purpose. Combining every source in
    range as an independent event is what made the original metric useless:
    with forty contributors, even a per-source probability of 0.1 produces
    98.8 percent, so every road in the district reported 1.00 and the ranking
    carried no information. Capping the count keeps the number bounded away
    from certainty and keeps it interpretable, as the risk from the handful of
    slopes an engineer would actually go and look at.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if delivered.size == 0:
        return 0.0
    ordered = np.sort(np.clip(delivered, 0.0, 0.999))[::-1][:top_k]
    return float(1.0 - np.prod(1.0 - ordered))
