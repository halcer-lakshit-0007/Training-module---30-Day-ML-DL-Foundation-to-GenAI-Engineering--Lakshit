"""Bugs found by adversarial probing (each failed before its fix). Warnings are errors here."""

from types import SimpleNamespace as T

import numpy as np
import pytest

from ticket_numerics.arrays import as_float_array, from_tickets, select, sequence_to_2d
from ticket_numerics.benchmark import run_benchmark
from ticket_numerics.errors import IncompatibleShapesError, NumericInputError
from ticket_numerics.metrics import (broadcast_shape, checked_add, group_mean, group_mean_loop,
                                     min_max_scale, standardise_columns, summary_stats, zscore)
from ticket_numerics.synthetic import make_hours

BIG = 1.7e308   # two of these overflow float64 when added; their difference overflows too

pytestmark = pytest.mark.filterwarnings("error")


@pytest.mark.parametrize("bad", [[[1, 2], [3]], [10**400], [[1], 2]])
def test_unconvertible_input_is_numeric_input_error_not_a_raw_numpy_or_overflow_error(bad):
    with pytest.raises(NumericInputError):
        as_float_array(bad)


@pytest.mark.parametrize("fn", [group_mean, group_mean_loop])
def test_group_mean_overflow_is_an_error_not_inf(fn):
    with pytest.raises(NumericInputError, match="too large"):
        fn([BIG, BIG], [0, 0], 1)


def test_group_mean_loop_rejects_negative_codes_like_the_vectorised_twin():
    # before: the loop silently wrapped -1 to the last group; NumPy path raised
    for fn in (group_mean, group_mean_loop):
        with pytest.raises(NumericInputError, match="in \\[0"):
            fn([1.0, 2.0], [-1, 0], 2)


@pytest.mark.parametrize("n_groups", [2.5, True, "2", None])
def test_n_groups_must_be_an_integer(n_groups):
    for fn in (group_mean, group_mean_loop):
        with pytest.raises(NumericInputError, match="integer"):
            fn([1.0], [0], n_groups)


def test_scaling_overflow_raises_instead_of_returning_wrong_numbers():
    # before: zscore -> [0, -0] (wrong), min_max_scale -> [0, nan], plus RuntimeWarnings
    with pytest.raises(NumericInputError, match="too large"):
        zscore([BIG, -BIG])
    with pytest.raises(NumericInputError, match="too large"):
        min_max_scale([-BIG, BIG])
    with pytest.raises(NumericInputError, match="too large"):
        standardise_columns([[BIG], [-BIG]])


def test_scaling_still_works_near_but_below_the_overflow_limit():
    assert min_max_scale([0.0, 1e300]).tolist() == [0.0, 1.0]
    np.testing.assert_allclose(zscore([1e100, 3e100]), [-1.0, 1.0], rtol=1e-12)


@pytest.mark.parametrize("a, b", [((-1,), (1,)), ((2.5,), (1,)), ((True,), (1,)), (("3",), (3,))])
def test_broadcast_shape_rejects_invalid_shapes(a, b):
    with pytest.raises(NumericInputError, match="invalid shape"):
        broadcast_shape(a, b)


def test_checked_add_and_select_accept_plain_lists():
    assert checked_add([1, 2], [3, 4]).tolist() == [4, 6]
    with pytest.raises(IncompatibleShapesError):
        checked_add([1, 2], [1, 2, 3])
    assert select([1, 2, 3], np.array([True, False, True])).tolist() == [1, 3]


def test_sequence_to_2d_accepts_arrays_and_rejects_non_rows():
    assert sequence_to_2d(np.ones((2, 3))).shape == (2, 3)
    assert sequence_to_2d([[], []]).shape == (2, 0)
    with pytest.raises(NumericInputError, match="every row"):
        sequence_to_2d([1, 2])
    with pytest.raises(NumericInputError, match="every row"):
        sequence_to_2d(["ab", "cd"])        # strings are sequences but not numeric rows


def test_fractional_rating_is_rejected_like_day03():
    bad = T(ticket_id="X", priority="low", category="billing", status="open",
            resolution_time_hours=1, customer_rating=3.5)
    with pytest.raises(NumericInputError, match="whole"):
        from_tickets([bad])


def test_benchmark_survives_tiny_sizes_whose_random_data_is_all_missing():
    seed = next(s for s in range(500) if np.isnan(make_hours(1, s)).all())   # seed 0 today
    rows = run_benchmark((1,), repeats=1, seed=seed)                          # before: ZeroDivisionError
    assert len(rows) == 3
    for s in range(40):
        run_benchmark((1, 2, 3), repeats=1, seed=s)


# ---- second probing round --------------------------------------------------------

def test_masked_array_hidden_values_are_treated_as_missing():
    masked = np.ma.array([1.0, 2.0, 99.0], mask=[0, 0, 1])
    s = summary_stats(masked)
    assert (s.count, s.missing, s.mean, s.maximum) == (2, 1, 1.5, 2.0)   # 99 must not leak in


def test_np_matrix_is_not_silently_accepted_as_1d():
    with pytest.warns(PendingDeprecationWarning):
        with pytest.raises(NumericInputError, match="1-D"):
            summary_stats(np.matrix([[1, 2]]))


@pytest.mark.parametrize("bad", [None, 5, (x for x in [1, 2])])
def test_non_sequences_get_a_clear_message(bad):
    with pytest.raises(NumericInputError, match="list, tuple or array"):
        as_float_array(bad)


def test_ticket_missing_an_attribute_is_a_numeric_input_error_naming_the_position():
    good = T(ticket_id="a", priority="low", category="billing", status="open",
             resolution_time_hours=1, customer_rating=None)
    with pytest.raises(NumericInputError, match="ticket #1"):
        from_tickets([good, T(ticket_id="b")])


def test_negative_zero_is_displayed_as_zero():
    s = summary_stats([-0.0, 0.0])
    assert str(s.minimum) == "0.0" and str(s.mean) == "0.0"


def test_broadcast_shape_returns_plain_ints_and_rejects_non_shapes():
    assert [type(d) for d in broadcast_shape((np.int64(3),), (1,))] == [int]
    assert broadcast_shape([3, 1], [1, 4]) == (3, 4)
    with pytest.raises(NumericInputError, match="tuples"):
        broadcast_shape(3, (1,))


def test_read_only_and_non_contiguous_inputs_work_and_are_untouched():
    ro = np.array([1.0, np.nan, 3.0])
    ro.setflags(write=False)
    assert summary_stats(ro).mean == 2.0
    assert summary_stats(np.arange(10.0)[::3]).mean == 4.5               # 0, 3, 6, 9
    assert summary_stats(np.array([200, 100], dtype=np.uint8)).mean == 150.0   # no uint8 wrap-around


# ---- third probing round ---------------------------------------------------------

def test_exact_sum_and_naive_variance_overflow_are_numeric_input_errors():
    from ticket_numerics.metrics import exact_sum, naive_variance
    with pytest.raises(NumericInputError, match="too large"):
        exact_sum([BIG, BIG])
    with pytest.raises(NumericInputError, match="too large"):
        naive_variance([1e200, 1e200])


@pytest.mark.parametrize("kwargs", [
    dict(n=2.5), dict(n="5"), dict(n=True), dict(n=3, seed="abc"), dict(n=3, seed=1.5),
    dict(n=3, missing_rate=None), dict(n=3, missing_rate="x"), dict(n=3, missing_rate=True),
])
def test_make_hours_wrong_types_give_clear_type_errors(kwargs):
    with pytest.raises(TypeError, match="must be"):
        make_hours(**kwargs)


def test_make_hours_ranges_and_size_cap():
    for kwargs in (dict(n=-1), dict(n=3, seed=-1), dict(n=10**12), dict(n=3, missing_rate=2)):
        with pytest.raises(ValueError):
            make_hours(**kwargs)
    assert make_hours(3, seed=None).shape == (3,)           # None = fresh entropy, allowed


def test_benchmark_rejects_absurd_or_mistyped_arguments_without_allocating(capsys):
    from ticket_numerics.benchmark import main
    for args in (["--sizes", "1000000000000"], ["--sizes", "5", "--repeats", "0"]):
        assert main(args) == 2
    with pytest.raises(TypeError):
        run_benchmark((2.5,), 1, 1)
    with pytest.raises(TypeError):
        run_benchmark((5,), 2.5, 1)
    assert "error" in capsys.readouterr().err


# ---- found by comparing with another submission's review (finite + finite overflow) ----

def test_checked_add_overflow_of_finite_inputs_is_an_error_not_inf():
    with pytest.raises(NumericInputError, match="too large"):
        checked_add([1e308], [1e308])
    assert checked_add([1e308], [1.0]).tolist() == [1e308]
    assert checked_add([np.inf], [1.0]).tolist() == [np.inf]      # an inf *input* stays inf


def test_checked_add_broadcasts_and_keeps_nan():
    out = checked_add(np.array([[1.0], [2.0]]), np.array([10.0, np.nan]))
    assert out.shape == (2, 2) and np.isnan(out[:, 1]).all() and out[:, 0].tolist() == [11.0, 12.0]


# ---- code review 2026-11-18: two blocking defects ----

@pytest.mark.parametrize("bad", [[True, 1], [False, 2.5], [1, True], [1.5, np.True_], (True, 2), [[1, 2], [True, 4]]])
def test_mixed_bool_and_numeric_sequences_are_rejected(bad):
    # np.asarray([True, 1]) silently becomes int [1, 1]; the bool must be caught first.
    with pytest.raises(NumericInputError, match="bool"):
        as_float_array(bad, ndim=None)


@pytest.mark.parametrize("good,expected", [
    ([1, 2, 3], [1.0, 2.0, 3.0]),
    ([1, 2.5, None], [1.0, 2.5, np.nan]),
    ([1.0, float("nan")], [1.0, np.nan]),
    ((4, 5), [4.0, 5.0]),
    ([], []),
])
def test_valid_numeric_controls_still_pass(good, expected):
    out = as_float_array(good)
    assert out.dtype == np.float64
    np.testing.assert_array_equal(out, np.array(expected, dtype=float))


def test_valid_2d_list_still_passes():
    assert as_float_array([[1, 2], [3, 4.5]], ndim=2).shape == (2, 2)


def _ticket(status):
    return T(ticket_id="T1", resolution_time_hours=1.0, customer_rating=3,
             priority="high", category="billing", status=status)


@pytest.mark.parametrize("status", ["escalated", "INVALID", "", "opened", "on hold"])
def test_unknown_status_is_rejected_not_treated_as_closed(status):
    with pytest.raises(NumericInputError, match="status"):
        from_tickets([_ticket(status)])


@pytest.mark.parametrize("status,is_open", [
    ("open", True), ("pending", True), ("OPEN", True), (" Pending ", True),
    ("resolved", False), ("closed", False), ("Closed", False),
])
def test_valid_statuses_map_to_the_right_flag(status, is_open):
    assert from_tickets([_ticket(status)]).is_open.tolist() == [is_open]
