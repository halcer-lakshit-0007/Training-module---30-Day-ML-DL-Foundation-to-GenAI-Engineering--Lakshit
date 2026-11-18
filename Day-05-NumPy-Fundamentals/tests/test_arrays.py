import numpy as np
import pytest

from sample_data import SAMPLE
from ticket_numerics.arrays import (CATEGORY_ORDER, array_info, as_float_array, from_tickets,
                                    select, sequence_to_2d)
from ticket_numerics.errors import NumericInputError


def test_shapes_and_dtypes_of_ticket_arrays():
    ta = from_tickets(SAMPLE)
    assert len(ta) == 7
    for arr in (ta.ticket_ids, ta.resolution_hours, ta.rating, ta.priority_rank,
                ta.category_code, ta.is_open):
        assert arr.shape == (7,)
    assert ta.resolution_hours.dtype == np.float64
    assert ta.rating.dtype == np.float64            # float so that NaN can mean "missing"
    assert ta.priority_rank.dtype == np.int8
    assert ta.is_open.dtype == np.bool_
    assert ta.numeric_matrix().shape == (7, 2)


def test_missing_values_become_nan_not_zero():
    ta = from_tickets(SAMPLE)
    assert np.isnan(ta.resolution_hours).sum() == 2       # T001, T009
    assert np.isnan(ta.rating).sum() == 1                 # T001
    assert ta.resolution_hours[1] == 4.5


def test_high_priority_open_matches_day03_contract():
    # Day 03 summary: HIGH or URGENT and OPEN/PENDING -> T001, T004, T009
    assert from_tickets(SAMPLE).high_priority_open_ids() == ("T001", "T004", "T009")


def test_priority_counts_match_day04_sample_values():
    ta = from_tickets(SAMPLE)
    counts = np.bincount(ta.priority_rank, minlength=4)    # low, medium, high, urgent
    assert counts.tolist() == [2, 2, 2, 1]
    assert int(ta.is_open.sum()) == 4                      # T001, T004, T009, T010


def test_empty_ticket_list_gives_empty_typed_arrays():
    ta = from_tickets([])
    assert len(ta) == 0
    assert ta.resolution_hours.shape == (0,) and ta.resolution_hours.dtype == np.float64
    assert ta.priority_rank.dtype == np.int8
    assert ta.numeric_matrix().shape == (0, 2)
    assert ta.high_priority_open_ids() == ()


def test_unknown_labels_are_rejected_not_coded():
    bad = SAMPLE[0].__class__(**{**vars(SAMPLE[0]), "priority": "critical"})
    with pytest.raises(NumericInputError, match="priority"):
        from_tickets([bad])


def test_enum_like_values_use_their_value():
    from types import SimpleNamespace as T
    enum_like = lambda v: T(value=v)  # noqa: E731
    t = T(ticket_id="X", priority=enum_like("URGENT"), category=enum_like("billing"),
          status=enum_like("Open"), resolution_time_hours=1, customer_rating=5)
    ta = from_tickets([t])
    assert ta.priority_rank[0] == 3 and ta.is_open[0] and ta.category_code[0] == 0
    assert CATEGORY_ORDER[ta.category_code[0]] == "billing"


def test_array_info_reports_shape_dtype_and_bytes():
    info = array_info(np.zeros((3, 4), dtype=np.float64))
    assert (info.shape, info.ndim, info.dtype, info.itemsize, info.nbytes) == (
        (3, 4), 2, "float64", 8, 96)
    assert array_info(np.zeros(5, dtype=np.int8)).nbytes == 5


@pytest.mark.parametrize("data, expected_shape", [
    (np.arange(12), (12,)),
    (np.arange(12).reshape(3, 4), (3, 4)),
    (np.arange(12).reshape(3, 4).T, (4, 3)),
    (np.arange(12).reshape(3, 4)[:, 1], (3,)),          # integer index drops a dimension
    (np.arange(12).reshape(3, 4)[:, 1:2], (3, 1)),      # slice keeps it
    (np.arange(12).reshape(3, 4)[None, :, :], (1, 3, 4)),
    (np.concatenate([np.zeros((2, 3)), np.ones((4, 3))]), (6, 3)),
    (np.arange(12).reshape(3, 4).sum(axis=0), (4,)),
    (np.arange(12).reshape(3, 4).sum(axis=1, keepdims=True), (3, 1)),
])
def test_predicted_shapes(data, expected_shape):
    """Study output: predict the shape first, then check. Predictions are the 2nd column."""
    assert data.shape == expected_shape


def test_as_float_array_accepts_ints_lists_and_none():
    out = as_float_array([1, None, 3.5, np.nan])
    assert out.dtype == np.float64 and out.shape == (4,)
    assert np.isnan(out[1]) and np.isnan(out[3])


def test_as_float_array_does_not_mutate_input():
    original = np.array([1.0, np.nan, 3.0])
    snapshot = original.copy()
    as_float_array(original)
    np.testing.assert_array_equal(original, snapshot)


@pytest.mark.parametrize("bad", [
    [True, False], ["1", "2"], [1, "x"], [1 + 2j], [[1, 2], [3, 4]], 5.0,
    [1.0, float("inf")], [float("-inf")],
])
def test_as_float_array_rejects_bad_input(bad):
    with pytest.raises(NumericInputError):
        as_float_array(bad)


def test_range_checks_ignore_missing_values():
    as_float_array([None, 3], minimum=1, maximum=5)
    with pytest.raises(NumericInputError, match="below"):
        as_float_array([0, 3], minimum=1)
    with pytest.raises(NumericInputError, match="above"):
        as_float_array([6], maximum=5)


def test_select_requires_a_boolean_mask_of_the_same_shape():
    a = np.array([10.0, 20.0, 30.0])
    np.testing.assert_array_equal(select(a, np.array([True, False, True])), [10.0, 30.0])
    with pytest.raises(NumericInputError, match="boolean"):
        select(a, np.array([0, 2]))              # ints would silently mean *positions*
    with pytest.raises(NumericInputError, match="shape"):
        select(a, np.array([True, False]))


def test_sequence_to_2d_rejects_ragged_rows():
    assert sequence_to_2d([[1, 2], [3, 4]]).shape == (2, 2)
    assert sequence_to_2d([]).shape == (0, 0)
    with pytest.raises(NumericInputError, match="different lengths"):
        sequence_to_2d([[1, 2], [3]])
