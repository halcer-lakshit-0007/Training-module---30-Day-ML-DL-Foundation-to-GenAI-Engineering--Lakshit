"""Broadcasting: our rule-based ``broadcast_shape`` is checked against NumPy itself."""

import itertools

import numpy as np
import pytest

from ticket_numerics.errors import IncompatibleShapesError
from ticket_numerics.metrics import broadcast_shape


@pytest.mark.parametrize("a, b, expected", [
    ((3, 4), (4,), (3, 4)),          # row vector applied to every row
    ((3, 4), (3, 1), (3, 4)),        # column vector applied to every column
    ((3, 1), (1, 4), (3, 4)),        # outer-product style: both stretch
    ((5,), (), (5,)),                # scalar
    ((2, 1, 4), (3, 1), (2, 3, 4)),
    ((0,), (1,), (0,)),              # size 1 stretches to 0
    ((0, 3), (3,), (0, 3)),
])
def test_valid_broadcasts(a, b, expected):
    assert broadcast_shape(a, b) == expected
    assert np.broadcast_shapes(a, b) == expected           # independent check


@pytest.mark.parametrize("a, b", [
    ((3,), (4,)), ((3, 4), (3,)), ((2, 3), (3, 2)), ((0,), (3,)),
])
def test_invalid_broadcasts(a, b):
    with pytest.raises(IncompatibleShapesError):
        broadcast_shape(a, b)
    with pytest.raises(ValueError):
        np.broadcast_shapes(a, b)


def test_rule_agrees_with_numpy_for_all_small_shapes():
    dims = (0, 1, 2, 3)
    shapes = [s for n in range(0, 3) for s in itertools.product(dims, repeat=n)]
    for a, b in itertools.product(shapes, repeat=2):
        try:
            expected = np.broadcast_shapes(a, b)
        except ValueError:
            with pytest.raises(IncompatibleShapesError):
                broadcast_shape(a, b)
        else:
            assert broadcast_shape(a, b) == expected, (a, b)


def test_concrete_example_used_in_the_readme():
    hours = np.array([[4.0, 10.0], [6.0, 20.0]])          # (2 tickets, 2 columns)
    column_means = hours.mean(axis=0)                     # (2,)  -> [5, 15]
    assert column_means.shape == (2,)
    centred = hours - column_means                        # (2,2) - (2,) -> (2,2)
    assert centred.tolist() == [[-1.0, -5.0], [1.0, 5.0]]


def test_missing_keepdims_is_a_silent_bug():
    """(3,) vs (3,1) broadcast to (3,3), not (3,): a classic silent shape bug."""
    a, b = np.arange(3), np.arange(3).reshape(3, 1)
    assert (a + b).shape == (3, 3)


def test_axis_semantics():
    m = np.arange(6).reshape(2, 3)             # [[0,1,2],[3,4,5]]
    assert m.sum(axis=0).tolist() == [3, 5, 7]     # collapse rows: one value per column
    assert m.sum(axis=1).tolist() == [3, 12]       # collapse columns: one value per row
    assert m.sum() == 15
