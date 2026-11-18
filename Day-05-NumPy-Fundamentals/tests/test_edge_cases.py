"""Task C: empty arrays, missing values and incompatible shapes - each handled on purpose."""

import numpy as np
import pytest

from ticket_numerics.errors import IncompatibleShapesError, NumericInputError
from ticket_numerics.metrics import (checked_add, min_max_scale, standardise_columns,
                                     summary_stats, summary_stats_loop, zscore, agree)


@pytest.mark.parametrize("fn", [summary_stats, summary_stats_loop])
def test_empty_array_gives_none_not_nan_or_exception(fn):
    s = fn([])
    assert (s.count, s.missing) == (0, 0)
    assert s.mean is s.median is s.std is s.minimum is s.maximum is None   # like Day 03


@pytest.mark.parametrize("fn", [summary_stats, summary_stats_loop])
def test_all_missing_array(fn):
    s = fn([np.nan, None, np.nan])
    assert (s.count, s.missing, s.mean) == (0, 3, None)


def test_single_value():
    s = summary_stats([7.0])
    assert (s.count, s.mean, s.median, s.std, s.minimum, s.maximum) == (1, 7.0, 7.0, 0.0, 7.0, 7.0)


def test_numpy_itself_would_warn_and_return_nan_for_empty_mean():
    # This is WHY the guard exists: np.mean([]) is NaN plus a RuntimeWarning.
    with pytest.warns(RuntimeWarning):
        assert np.isnan(np.mean(np.array([])))


def test_no_numpy_warnings_on_edge_inputs(recwarn):
    for data in ([], [np.nan], [5.0], [np.nan, np.nan]):
        summary_stats(data)
        zscore(data)
        min_max_scale(data)
    standardise_columns(np.empty((0, 3)))
    standardise_columns(np.full((3, 2), np.nan))
    assert [str(w.message) for w in recwarn.list] == []


def test_zero_is_a_value_not_missing():
    s = summary_stats([0.0, 0.0, 4.0])
    assert s.count == 3 and s.mean == 1.33 and s.minimum == 0.0


def test_negative_and_large_values_are_ordinary_numbers():
    s = summary_stats([-5.0, 5.0, 1e100])
    assert s.minimum == -5.0 and s.maximum == 1e100


@pytest.mark.parametrize("fn", [summary_stats, summary_stats_loop])
@pytest.mark.parametrize("data", [[1.7e308, 1.7e308], [-5.0, 5.0, 1e300]])
def test_overflow_is_reported_not_returned_as_inf_or_warned(fn, data, recwarn):
    # the sum (first) or the squared deviations (second) overflow float64
    with pytest.raises(NumericInputError, match="too large"):
        fn(data)
    assert [str(w.message) for w in recwarn.list] == []


def test_infinity_is_rejected_at_the_boundary():
    with pytest.raises(NumericInputError, match="infinity"):
        summary_stats([1.0, np.inf])


def test_text_bool_and_2d_input_rejected():
    for bad in (["a"], [True], [[1.0, 2.0]]):
        with pytest.raises(NumericInputError):
            summary_stats(bad)


def test_zscore_constant_empty_and_missing():
    assert zscore([4.0, 4.0, 4.0]).tolist() == [0.0, 0.0, 0.0]        # no divide-by-zero
    assert zscore([]).shape == (0,)
    out = zscore([1.0, np.nan, 3.0])
    assert np.isnan(out[1]) and out[0] == -1.0 and out[2] == 1.0
    assert np.isnan(zscore([np.nan, np.nan])).all()


def test_min_max_scale_edges():
    assert min_max_scale([2.0, 4.0, 6.0]).tolist() == [0.0, 0.5, 1.0]
    assert min_max_scale([3.0, 3.0]).tolist() == [0.0, 0.0]
    assert np.isnan(min_max_scale([np.nan])).all()


def test_standardise_columns_uses_column_stats_and_handles_edges():
    m = np.array([[1.0, 10.0, 5.0], [3.0, 20.0, 5.0], [5.0, np.nan, 5.0]])
    out = standardise_columns(m)
    assert out.shape == m.shape
    np.testing.assert_allclose(out[:, 0], [-1.2247449, 0.0, 1.2247449], rtol=1e-6)
    np.testing.assert_allclose(out[:2, 1], [-1.0, 1.0])
    assert np.isnan(out[2, 1])                                   # missing stays missing
    assert out[:, 2].tolist() == [0.0, 0.0, 0.0]                 # constant column
    assert np.isnan(standardise_columns(np.full((2, 1), np.nan))).all()


def test_standardise_columns_requires_2d():
    with pytest.raises(NumericInputError, match="2-D"):
        standardise_columns([1.0, 2.0, 3.0])


def test_incompatible_shapes_raise_a_clear_error():
    with pytest.raises(IncompatibleShapesError, match=r"\(3,\) and \(4,\)"):
        checked_add(np.zeros(3), np.zeros(4))
    with pytest.raises(IncompatibleShapesError):
        checked_add(np.zeros((2, 3)), np.zeros((3, 2)))


def test_nan_propagates_in_plain_numpy_but_not_in_our_summary():
    data = np.array([1.0, np.nan, 3.0])
    assert np.isnan(data.mean())                  # the trap
    assert summary_stats(data).mean == 2.0        # handled deliberately


def test_agree_requires_none_to_match_none():
    assert not agree(summary_stats([]), summary_stats([1.0]))
