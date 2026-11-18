import math

import numpy as np
import pytest

from sample_data import SAMPLE
from ticket_numerics.arrays import from_tickets
from ticket_numerics.errors import IncompatibleShapesError, NumericInputError
from ticket_numerics.metrics import (agree, group_mean, group_mean_loop, summary_stats,
                                     summary_stats_loop)

TA = from_tickets(SAMPLE)


def test_hours_summary_matches_hand_calculation():
    # present: 4.5, 1.5, 8, 3, 2 -> mean 19/5 = 3.8 (Day 04 README: overall average 3.8 h)
    # sorted 1.5 2 3 4.5 8 -> median 3; squared deviations sum 27.3 -> sqrt(27.3/5) = 2.3367
    s = summary_stats(TA.resolution_hours)
    assert (s.count, s.missing) == (5, 2)
    assert (s.mean, s.median, s.std, s.minimum, s.maximum) == (3.8, 3.0, 2.34, 1.5, 8.0)


def test_rating_summary_matches_hand_calculation():
    # present: 4 3 4 5 3 4 -> sum 23 / 6 = 3.8333; sorted 3 3 4 4 4 5 -> median 4
    s = summary_stats(TA.rating)
    assert (s.count, s.missing, s.mean, s.median, s.minimum, s.maximum) == (6, 1, 3.83, 4.0, 3.0, 5.0)
    assert s.std == 0.69                                   # sqrt(2.8333/6) = 0.6872


def test_summary_agrees_with_python_statistics_module():
    import statistics
    values = [4.5, 1.5, 8.0, 3.0, 2.0]
    s = summary_stats(values)
    assert s.mean == round(statistics.fmean(values), 2)
    assert s.median == statistics.median(values)
    assert s.std == round(statistics.pstdev(values), 2)


def test_vectorised_and_loop_agree_on_sample():
    for col in (TA.resolution_hours, TA.rating):
        assert agree(summary_stats(col), summary_stats_loop(col))


@pytest.mark.parametrize("seed", range(20))
def test_vectorised_and_loop_agree_on_random_data(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(0, 300))
    data = rng.normal(50, 20, n)
    data[rng.random(n) < 0.2] = np.nan
    assert agree(summary_stats(data), summary_stats_loop(data))


def test_group_mean_matches_day04_resolution_by_category():
    # billing: T007 -> 3.0 | technical: T002, T005 -> 6.25 (T009 missing) | account: T010 -> 2.0
    # general: nothing | unknown: T004 -> 1.5
    means, counts = group_mean(TA.resolution_hours, TA.category_code, 5)
    assert counts.tolist() == [1, 2, 1, 0, 1]
    np.testing.assert_allclose(means[[0, 1, 2, 4]], [3.0, 6.25, 2.0, 1.5])
    assert np.isnan(means[3])                              # empty group: NaN, not 0


def test_group_mean_matches_loop_twin():
    m1, c1 = group_mean(TA.resolution_hours, TA.category_code, 5)
    m2, c2 = group_mean_loop(TA.resolution_hours, TA.category_code, 5)
    assert c1.tolist() == c2
    np.testing.assert_allclose(m1, m2, equal_nan=True)


def test_group_mean_rejects_bad_groups():
    v = np.array([1.0, 2.0])
    with pytest.raises(IncompatibleShapesError):
        group_mean(v, np.array([0, 1, 1]), 2)
    with pytest.raises(NumericInputError, match="integer"):
        group_mean(v, np.array([0.0, 1.0]), 2)
    with pytest.raises(NumericInputError, match="in \\[0"):
        group_mean(v, np.array([0, 2]), 2)
    with pytest.raises(NumericInputError, match="in \\[0"):
        group_mean(v, np.array([-1, 0]), 2)                # negative would silently wrap in NumPy
    with pytest.raises(NumericInputError):
        group_mean(v, np.array([0, 1]), -1)


def test_group_mean_empty_input():
    means, counts = group_mean([], np.array([], dtype=int), 3)
    assert counts.tolist() == [0, 0, 0] and np.isnan(means).all()
    means, counts = group_mean([], np.array([], dtype=int), 0)
    assert means.shape == (0,) and counts.shape == (0,)


def test_summary_is_deterministic_and_does_not_mutate():
    data = np.array([3.0, np.nan, 1.0])
    before = data.copy()
    assert summary_stats(data) == summary_stats(data)
    np.testing.assert_array_equal(data, before)
    assert not math.isnan(summary_stats(data).mean)
