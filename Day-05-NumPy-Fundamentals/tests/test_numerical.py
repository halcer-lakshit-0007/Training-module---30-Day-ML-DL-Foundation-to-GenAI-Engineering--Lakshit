"""Numerical reasoning: floating point, stability, seeds, reproducibility."""

import math

import numpy as np

from ticket_numerics.metrics import exact_sum, naive_variance, summary_stats
from ticket_numerics.synthetic import make_hours
import pytest


def test_floating_point_is_not_exact_in_binary():
    assert 0.1 + 0.2 != 0.3                              # 0.1 and 0.2 have no exact binary form
    assert abs((0.1 + 0.2) - 0.3) < 1e-15
    assert math.isclose(0.1 + 0.2, 0.3) and np.isclose(0.1 + 0.2, 0.3)


def test_nan_is_never_equal_to_itself():
    assert np.nan != np.nan
    assert np.isnan(np.nan)


def test_float32_has_fewer_digits_than_float64():
    assert np.float32(0.1) != np.float64(0.1)
    assert np.finfo(np.float32).eps > np.finfo(np.float64).eps


def test_naive_sum_loses_small_values_but_fsum_does_not():
    data = [1e16, 1.0, -1e16]
    assert sum(data) == 0.0              # the 1.0 is absorbed: 1e16 + 1.0 == 1e16 in float64
    assert exact_sum(data) == 1.0        # math.fsum tracks the lost bits


def test_naive_variance_fails_with_large_offset_but_two_pass_does_not():
    offset = 1e9
    data = offset + np.array([1.0, 2.0, 3.0, 4.0])        # true population variance = 1.25
    assert summary_stats(data).std == round(math.sqrt(1.25), 2)       # 1.12, two-pass
    assert abs(naive_variance(data) - 1.25) > 0.1                     # cancellation destroys it


def test_same_seed_gives_identical_data_and_results():
    a, b = make_hours(1000, seed=7), make_hours(1000, seed=7)
    np.testing.assert_array_equal(a, b)
    assert summary_stats(a) == summary_stats(b)


def test_different_seed_gives_different_data():
    assert not np.array_equal(make_hours(1000, seed=1), make_hours(1000, seed=2), equal_nan=True)


def test_local_generator_ignores_and_preserves_global_state():
    np.random.seed(123)
    expected_next = np.random.random()
    np.random.seed(123)
    make_hours(500, seed=9)                               # must not consume the global stream
    assert np.random.random() == expected_next


def test_generated_data_has_expected_shape_and_range():
    """Sanity of the generator output (exact values are not pinned: NumPy does not
    guarantee distribution streams such as gamma across versions)."""
    first = make_hours(5, seed=42, missing_rate=0.0)
    assert first.shape == (5,) and (first > 0).all() and not np.isnan(first).any()
    np.testing.assert_array_equal(first, make_hours(5, seed=42, missing_rate=0.0))


def test_missing_rate_extremes_and_bad_arguments():
    assert np.isnan(make_hours(50, 1, 1.0)).all()
    assert not np.isnan(make_hours(50, 1, 0.0)).any()
    assert make_hours(0).shape == (0,)
    with pytest.raises(ValueError):
        make_hours(-1)
    with pytest.raises(ValueError):
        make_hours(5, missing_rate=1.5)
