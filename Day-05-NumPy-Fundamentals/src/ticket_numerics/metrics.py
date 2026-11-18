"""
Task B (and the numerical-reasoning part of Task C) - vectorised metrics.

Every vectorised function has a plain-Python loop twin (``*_loop``) that uses
no NumPy and no ``statistics`` module. Tests compare the two on hand-checked
data and on seeded random data.

Definitions (match Day 03/04 where they overlap):

* Missing = NaN. Missing values are *excluded*, never treated as 0.
* Mean/median of nothing is ``None`` (Day 03: ``average_resolution_hours``
  is None when no ticket has a value), never NaN and never an exception.
* Display values are rounded to 2 decimals like Day 03's ``_mean``.
* ``std`` is the *population* standard deviation (ddof=0); with one value it is 0.0.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ticket_numerics.arrays import as_float_array
from ticket_numerics.errors import IncompatibleShapesError, NumericInputError


@dataclass(frozen=True)
class NumericSummary:
    count: int                 # non-missing values
    missing: int               # NaN / None values
    mean: Optional[float]
    median: Optional[float]
    std: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]


_TOO_LARGE = "values are too large: the sum or squares overflow float64"
_EMPTY = dict(mean=None, median=None, std=None, minimum=None, maximum=None)


def _require_finite(*arrays: Any) -> None:
    """Overflow in NumPy gives inf/NaN plus a warning; turn that into a clear error."""
    if not all(np.isfinite(a).all() for a in arrays):
        raise NumericInputError(_TOO_LARGE)


def _r(x: float) -> float:
    return round(float(x), 2) + 0.0          # + 0.0 turns -0.0 into 0.0 for display


# --- vectorised ----------------------------------------------------------------

def summary_stats(values: Any) -> NumericSummary:
    """Vectorised summary of one 1-D numeric column (NaN/None = missing)."""
    a = as_float_array(values)
    present = a[~np.isnan(a)]
    if present.size == 0:
        return NumericSummary(0, int(a.size), **_EMPTY)
    with np.errstate(over="ignore", invalid="ignore"):    # we check the results ourselves
        mean, std = present.mean(), present.std()          # std is ddof=0
    if not (math.isfinite(mean) and math.isfinite(std)):
        raise NumericInputError(_TOO_LARGE)
    return NumericSummary(
        count=int(present.size),
        missing=int(a.size - present.size),
        mean=_r(mean),
        median=_r(np.median(present)),
        std=_r(std),
        minimum=_r(present.min()),
        maximum=_r(present.max()),
    )


def _validate_groups(v: np.ndarray, groups: Any, n_groups: Any) -> np.ndarray:
    g = np.asarray(groups)
    if isinstance(n_groups, bool) or not isinstance(n_groups, numbers.Integral):
        raise NumericInputError("n_groups must be an integer")
    if n_groups < 0:
        raise NumericInputError("n_groups must not be negative")
    if g.shape != v.shape:
        raise IncompatibleShapesError(f"values {v.shape} and groups {g.shape} differ")
    if g.size and g.dtype.kind not in "iu":
        raise NumericInputError(f"groups must be integer codes, got {g.dtype}")
    if g.size and (g.min() < 0 or g.max() >= n_groups):
        raise NumericInputError(f"group codes must be in [0, {n_groups})")
    return g


def group_mean(values: Any, groups: Any, n_groups: int) -> Tuple[np.ndarray, np.ndarray]:
    """Mean of ``values`` per integer group code, ignoring NaN, without a Python loop.

    Returns ``(means, counts)``, both shape ``(n_groups,)``. A group with no
    present value has mean NaN and count 0 (Day 04 omits such categories when
    *displaying*; the array keeps a slot per group so positions stay aligned).
    """
    v = as_float_array(values)
    g = _validate_groups(v, groups, n_groups)

    keep = ~np.isnan(v)
    codes = g[keep].astype(np.intp)
    sums = np.bincount(codes, weights=v[keep], minlength=n_groups)
    counts = np.bincount(codes, minlength=n_groups)
    _require_finite(sums)
    means = np.full(n_groups, np.nan)
    np.divide(sums, counts, out=means, where=counts > 0)
    return means, counts


def zscore(values: Any) -> np.ndarray:
    """(x - mean) / std over present values; NaN stays NaN.

    Constant data (std == 0) gives 0.0 for present values instead of a
    division by zero; all-missing or empty data returns NaN / empty.
    """
    a = as_float_array(values)
    out = np.full(a.shape, np.nan)
    present = ~np.isnan(a)
    if not present.any():
        return out
    with np.errstate(over="ignore", invalid="ignore"):
        centred = a[present] - a[present].mean()
        std = a[present].std()
    _require_finite(centred, std)
    out[present] = centred / std if std > 0 else 0.0
    return out


def min_max_scale(values: Any) -> np.ndarray:
    """Scale present values to [0, 1]; constant data -> 0.0; NaN stays NaN."""
    a = as_float_array(values)
    out = np.full(a.shape, np.nan)
    present = ~np.isnan(a)
    if not present.any():
        return out
    lo, hi = a[present].min(), a[present].max()
    with np.errstate(over="ignore", invalid="ignore"):
        span = hi - lo
        scaled = (a[present] - lo) / span if hi > lo else np.zeros(int(present.sum()))
    _require_finite(span, scaled)
    out[present] = scaled
    return out


def standardise_columns(matrix: Any) -> np.ndarray:
    """Column-wise z-score of an (n, k) matrix using broadcasting.

    ``matrix - means`` subtracts a shape-(k,) vector from a shape-(n, k)
    matrix: shapes (n, k) and (k,) are right-aligned to (n, k) and (1, k), so
    the same row of means is applied to every row. NaN is ignored when
    computing each column's mean/std; a constant column becomes 0.0; an
    all-NaN column stays NaN.
    """
    m = as_float_array(matrix, "matrix", ndim=2)
    if m.shape[0] == 0:
        return m.copy()
    present = ~np.isnan(m)
    counts = present.sum(axis=0)                           # axis=0 collapses the rows
    safe = np.maximum(counts, 1)
    with np.errstate(over="ignore", invalid="ignore"):
        means = np.where(present, m, 0.0).sum(axis=0) / safe   # shape (k,)
        centred = np.where(present, m - means, 0.0)            # broadcast (n,k) - (k,)
        stds = np.sqrt((centred ** 2).sum(axis=0) / safe)      # shape (k,)
        scale = np.where(stds > 0, stds, 1.0)
        out = (m - means) / scale                              # broadcast again
    _require_finite(means, centred, stds)
    out[:, counts == 0] = np.nan
    return out


# --- loop twins (independent implementation) ------------------------------------

def _present(values: Any) -> list:
    return [float(v) for v in as_float_array(values).tolist() if not math.isnan(v)]


def summary_stats_loop(values: Any) -> NumericSummary:
    a = as_float_array(values).tolist()
    present = [v for v in a if not math.isnan(v)]
    n = len(present)
    if n == 0:
        return NumericSummary(0, len(a), **_EMPTY)
    total = 0.0
    lo = hi = present[0]
    for v in present:
        total += v
        lo = min(lo, v)
        hi = max(hi, v)
    mean = total / n
    sq = 0.0
    try:
        for v in present:
            sq += (v - mean) ** 2          # Python raises OverflowError here, NumPy gives inf
    except OverflowError:
        raise NumericInputError(_TOO_LARGE) from None
    if not (math.isfinite(mean) and math.isfinite(sq)):
        raise NumericInputError(_TOO_LARGE)
    ordered = sorted(present)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return NumericSummary(n, len(a) - n, _r(mean), _r(median), _r(math.sqrt(sq / n)),
                          _r(lo), _r(hi))


def group_mean_loop(values: Any, groups: Any, n_groups: int) -> Tuple[list, list]:
    v = as_float_array(values)
    g = _validate_groups(v, groups, n_groups).tolist()    # same input rules as the twin
    sums = [0.0] * n_groups
    counts = [0] * n_groups
    for value, code in zip(v.tolist(), g):
        if not math.isnan(value):
            sums[code] += value
            counts[code] += 1
    if not all(math.isfinite(s) for s in sums):
        raise NumericInputError(_TOO_LARGE)
    means = [sums[i] / counts[i] if counts[i] else math.nan for i in range(n_groups)]
    return means, counts


def agree(a: NumericSummary, b: NumericSummary, tol: float = 1e-9) -> bool:
    """Compare two summaries field by field (``None`` must match ``None``)."""
    for x, y in zip(
        (a.count, a.missing, a.mean, a.median, a.std, a.minimum, a.maximum),
        (b.count, b.missing, b.mean, b.median, b.std, b.minimum, b.maximum),
    ):
        if (x is None) != (y is None):
            return False
        if x is not None and not math.isclose(x, y, rel_tol=tol, abs_tol=tol):
            return False
    return True


# --- numerical-stability helpers ------------------------------------------------

def exact_sum(values: Any) -> float:
    """Correctly rounded sum of present values (``math.fsum``), for checking ``np.sum``."""
    try:
        return math.fsum(_present(values))
    except OverflowError:
        raise NumericInputError(_TOO_LARGE) from None


def naive_variance(values: Any) -> float:
    """E[x^2] - E[x]^2: one pass, *numerically unstable*. For comparison only.

    With a large offset (e.g. 1e9 + small numbers) the two terms are nearly
    equal and cancel catastrophically. ``np.var`` subtracts the mean first
    (two-pass), which is why summary_stats uses it.
    """
    p = np.array(_present(values))
    if p.size == 0:
        raise NumericInputError("naive_variance: no present values")
    with np.errstate(over="ignore", invalid="ignore"):
        result = float((p ** 2).mean() - p.mean() ** 2)
    if not math.isfinite(result):
        raise NumericInputError(_TOO_LARGE)
    return result


def broadcast_shape(a: Tuple[int, ...], b: Tuple[int, ...]) -> Tuple[int, ...]:
    """Result shape of broadcasting ``a`` with ``b``, or ``IncompatibleShapesError``.

    Rule: align shapes on the *right*; each pair of sizes must be equal or one
    of them must be 1 (a missing leading size counts as 1); the result takes
    the larger size. Size 0 only matches 0 or 1.
    """
    try:
        a, b = tuple(a), tuple(b)
    except TypeError:
        raise NumericInputError("shapes must be tuples of non-negative integers") from None
    for shape in (a, b):
        if not all(isinstance(d, numbers.Integral) and not isinstance(d, bool) and d >= 0
                   for d in shape):
            raise NumericInputError(f"invalid shape {shape}: sizes must be non-negative integers")
    result = []
    for i in range(1, max(len(a), len(b)) + 1):
        x = a[-i] if i <= len(a) else 1
        y = b[-i] if i <= len(b) else 1
        if x == y or y == 1:
            result.append(int(x))
        elif x == 1:
            result.append(int(y))
        else:
            raise IncompatibleShapesError(
                f"shapes {a} and {b} do not broadcast: "
                f"dimension -{i} has sizes {x} and {y} (must be equal or 1)"
            )
    return tuple(reversed(result))


def checked_add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``a + b`` with a clear error (naming both shapes) when they cannot broadcast."""
    a, b = np.asarray(a), np.asarray(b)
    broadcast_shape(a.shape, b.shape)
    with np.errstate(over="ignore"):
        result = a + b
    # inf is fine if an input already was inf; finite + finite must not become inf silently
    if np.isinf(result).any() and not (np.isinf(a).any() or np.isinf(b).any()):
        raise NumericInputError(_TOO_LARGE)
    return result


def describe(values: Any) -> Dict[str, Any]:
    """Plain-dict form of ``summary_stats`` (handy for printing / JSON)."""
    return dict(summary_stats(values).__dict__)
