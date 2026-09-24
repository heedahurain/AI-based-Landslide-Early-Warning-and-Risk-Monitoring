"""Known-answer tests for the failure-probability and runout model.

Every expected value here is derived by hand in the docstring or comment that
accompanies it, so a failure points at the arithmetic rather than at a
remembered number.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ml.physics.runout import (
    ANGLE_OF_REACH_FULL_DEG,
    ANGLE_OF_REACH_MIN_DEG,
    blockage_probability,
    expected_blockages,
    probability_of_failure,
    reach_weight,
)


class TestProbabilityOfFailure:
    def test_limit_state_is_a_coin_toss(self) -> None:
        """FoS exactly 1.0 must give exactly 0.5, for any spread.

        ln(1/1) = 0, so z = 0 and Phi(0) = 0.5 regardless of sigma. This is the
        anchor that proves the distribution is centred on the computed value.
        """
        for cov in (0.05, 0.25, 0.8):
            result = float(probability_of_failure(np.array([1.0]), cov)[0])
            assert result == pytest.approx(0.5, abs=1e-12)

    def test_worked_value_at_fos_1_2(self) -> None:
        """Hand-derived, COV 0.25.

        sigma = sqrt(ln(1 + 0.0625)) = sqrt(0.0606246) = 0.2462206
        z     = ln(1/1.2) / sigma = -0.1823216 / 0.2462206 = -0.7404
        Phi(-0.7404) = 0.22946
        """
        result = float(probability_of_failure(np.array([1.2]), 0.25)[0])
        assert result == pytest.approx(0.2295, abs=5e-4)

    def test_monotonic_decreasing_in_fos(self) -> None:
        values = probability_of_failure(np.array([0.5, 0.8, 1.0, 1.5, 2.0, 4.0]))
        assert np.all(np.diff(values) < 0.0)

    def test_stable_slope_is_not_a_coin_toss(self) -> None:
        """The bug this module exists to fix.

        The previous mapping, clip(2 - FoS, 0, 1), gave a slope at FoS 1.394 a
        probability of 0.606. A slope the model calls stable must not carry a
        failure probability anywhere near a half.
        """
        result = float(probability_of_failure(np.array([1.394]))[0])
        assert result < 0.15
        assert result == pytest.approx(0.0887, abs=5e-4)

    def test_bounds_are_respected(self) -> None:
        values = probability_of_failure(np.array([1e-9, 0.01, 1000.0]))
        assert np.all(values >= 0.0)
        assert np.all(values <= 1.0)

    def test_rejects_nonpositive_spread(self) -> None:
        with pytest.raises(ValueError):
            probability_of_failure(np.array([1.0]), 0.0)


class TestReachWeight:
    def test_zero_at_and_below_the_minimum_angle(self) -> None:
        """A source 100 m up and 250 m away subtends arctan(0.4) = 21.80 deg.

        That is below the 22 degree minimum, so nothing is delivered. This is
        also the geometry that sets the 250 m search buffer used upstream.
        """
        assert float(reach_weight(100.0, 250.0)) == 0.0
        assert math.degrees(math.atan(100.0 / 250.0)) == pytest.approx(21.80, abs=0.01)

    def test_full_at_and_above_the_full_angle(self) -> None:
        """tan(35 deg) = 0.7002, so 100 m up and 142.8 m away is exactly full."""
        distance = 100.0 / math.tan(math.radians(ANGLE_OF_REACH_FULL_DEG))
        assert float(reach_weight(100.0, distance)) == pytest.approx(1.0, abs=1e-9)
        assert float(reach_weight(100.0, distance * 0.5)) == 1.0

    def test_midpoint_of_the_ramp(self) -> None:
        """Half way between 22 and 35 degrees is 28.5 degrees, weight 0.5."""
        midpoint = 0.5 * (ANGLE_OF_REACH_MIN_DEG + ANGLE_OF_REACH_FULL_DEG)
        distance = 100.0 / math.tan(math.radians(midpoint))
        assert float(reach_weight(100.0, distance)) == pytest.approx(0.5, abs=1e-9)

    def test_source_at_or_below_target_delivers_nothing(self) -> None:
        assert float(reach_weight(0.0, 50.0)) == 0.0
        assert float(reach_weight(-30.0, 50.0)) == 0.0

    def test_vectorises(self) -> None:
        weights = reach_weight(np.array([100.0, 100.0, 0.0]), np.array([50.0, 250.0, 10.0]))
        assert weights.shape == (3,)
        assert weights[0] == 1.0
        assert weights[1] == 0.0
        assert weights[2] == 0.0


class TestCombination:
    def test_expected_count_does_not_saturate(self) -> None:
        """The property the old metric lacked.

        Forty sources at 0.089 each give an expected 3.56 blockages. The old
        independent-combination probability would have returned 0.976 here and
        1.000 for anything worse, which is why every row read the same.
        """
        delivered = np.full(40, 0.089)
        assert expected_blockages(delivered) == pytest.approx(3.56, abs=0.01)

    def test_expected_count_keeps_rising(self) -> None:
        few = expected_blockages(np.full(5, 0.1))
        many = expected_blockages(np.full(50, 0.1))
        assert many > few * 5 - 1e-9

    def test_top_k_caps_the_combination(self) -> None:
        """1 - (1 - 0.1)^5 = 1 - 0.59049 = 0.40951, however many sources exist."""
        for count in (5, 20, 100):
            result = blockage_probability(np.full(count, 0.1), top_k=5)
            assert result == pytest.approx(0.40951, abs=1e-5)

    def test_takes_the_largest_contributors(self) -> None:
        mixed = np.array([0.01, 0.9, 0.02, 0.8, 0.03])
        # Top 2 are 0.9 and 0.8: 1 - 0.1*0.2 = 0.98
        assert blockage_probability(mixed, top_k=2) == pytest.approx(0.98, abs=1e-9)

    def test_empty_input_is_zero(self) -> None:
        assert blockage_probability(np.array([])) == 0.0
        assert expected_blockages(np.array([])) == 0.0

    def test_rejects_bad_k(self) -> None:
        with pytest.raises(ValueError):
            blockage_probability(np.array([0.5]), top_k=0)
