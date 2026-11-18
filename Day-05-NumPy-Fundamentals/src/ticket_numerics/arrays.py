"""
Task A - arrays built from numeric ticket fields.

Conventions (chosen once, used everywhere):

* Missing numeric values are ``NaN`` in a ``float64`` array. Day 03 uses
  ``None`` for "not recorded"; NumPy integer arrays cannot hold NaN, so
  ratings are stored as float64 too. ``from_tickets`` converts ``None`` -> NaN.
* Priority is an ``int8`` rank, low=0 ... urgent=3. (Day 04's *display* order
  is urgent first; ranks are for comparing, display order stays in Day 04.)
* Category is an ``int8`` code that indexes ``CATEGORY_ORDER`` (Day 03's enum order).
* ``from_tickets`` is duck-typed: any object with the Day 03 ``Ticket``
  attributes works, so this module does not import Day 03 (which needs
  Python >= 3.11) and can be tested on its own.
"""

from __future__ import annotations

import numbers
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

import numpy as np

from ticket_numerics.errors import NumericInputError

PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "urgent": 3}
CATEGORY_ORDER: Tuple[str, ...] = ("billing", "technical", "account", "general", "unknown")
CATEGORY_CODE = {name: code for code, name in enumerate(CATEGORY_ORDER)}
OPEN_STATUSES = frozenset({"open", "pending"})      # same as Day 03 Ticket.OPEN_STATUSES
HIGH_RANK = PRIORITY_RANK["high"]                    # high and urgent are "high priority"


@dataclass(frozen=True)
class ArrayInfo:
    """What to inspect about an array: its shape, dtype and memory footprint."""

    shape: Tuple[int, ...]
    ndim: int
    dtype: str
    itemsize: int   # bytes per element
    nbytes: int     # total bytes of the element buffer (size * itemsize)


def array_info(array: np.ndarray) -> ArrayInfo:
    return ArrayInfo(array.shape, array.ndim, str(array.dtype), array.itemsize, array.nbytes)


def as_float_array(
    values: Any,
    name: str = "values",
    *,
    ndim: Optional[int] = 1,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> np.ndarray:
    """Validate ``values`` and return it as a float64 array. Never mutates the input.

    Accepted: numeric lists/arrays; ``None`` and ``NaN`` mean "missing" (NaN).
    Rejected with ``NumericInputError``: bool, strings, complex and other
    non-numeric dtypes; wrong number of dimensions; +-inf; values outside
    ``[minimum, maximum]`` (missing values are not range-checked).
    """
    if isinstance(values, np.ma.MaskedArray):     # masked = missing; never read the hidden data
        array = values.astype(np.float64).filled(np.nan)
    elif isinstance(values, np.ndarray):
        array = np.asarray(values)                # drops subclasses such as np.matrix
    elif not hasattr(values, "__len__"):
        raise NumericInputError(f"{name}: expected a list, tuple or array, got {type(values).__name__}")
    else:
        try:
            array = np.asarray(values)
        except (ValueError, TypeError) as exc:    # e.g. ragged nested lists
            raise NumericInputError(f"{name}: not a regular numeric array ({exc})") from None
    if array.dtype == object:
        array = _object_to_float(array, name)
    elif array.dtype.kind == "b":
        raise NumericInputError(f"{name}: boolean values are not numbers")
    elif array.dtype.kind not in "iuf":
        raise NumericInputError(f"{name}: dtype {array.dtype} is not numeric")
    array = array.astype(np.float64, copy=False)

    if ndim is not None and array.ndim != ndim:
        raise NumericInputError(f"{name}: expected {ndim}-D data, got shape {array.shape}")
    if np.isinf(array).any():
        raise NumericInputError(f"{name}: contains infinity")
    present = array[~np.isnan(array)]
    if minimum is not None and present.size and present.min() < minimum:
        raise NumericInputError(f"{name}: contains values below {minimum}")
    if maximum is not None and present.size and present.max() > maximum:
        raise NumericInputError(f"{name}: contains values above {maximum}")
    return array


def _object_to_float(array: np.ndarray, name: str) -> np.ndarray:
    out = np.empty(array.shape, dtype=np.float64)
    for index, item in np.ndenumerate(array):
        if item is None:
            out[index] = np.nan
        elif isinstance(item, (bool, np.bool_)) or not isinstance(item, numbers.Real):
            raise NumericInputError(f"{name}: {type(item).__name__} is not a number")
        else:
            try:
                out[index] = float(item)
            except OverflowError:                 # e.g. 10**400
                raise NumericInputError(f"{name}: {item!r:.20} is too large for float64") from None
    return out


@dataclass(frozen=True)
class TicketArrays:
    """Column-oriented numeric view of a collection of tickets. All arrays have shape (n,)."""

    ticket_ids: np.ndarray        # <U str
    resolution_hours: np.ndarray  # float64, NaN = not recorded
    rating: np.ndarray            # float64, NaN = not rated
    priority_rank: np.ndarray     # int8, see PRIORITY_RANK
    category_code: np.ndarray     # int8, index into CATEGORY_ORDER
    is_open: np.ndarray           # bool, True for open/pending

    def __len__(self) -> int:
        return int(self.ticket_ids.shape[0])

    def numeric_matrix(self) -> np.ndarray:
        """Shape (n, 2): columns are resolution_hours and rating."""
        return np.column_stack((self.resolution_hours, self.rating))

    def high_priority_open_mask(self) -> np.ndarray:
        """Boolean mask: open/pending AND high/urgent (Day 03's ``high_priority_open_ids``)."""
        return self.is_open & (self.priority_rank >= HIGH_RANK)

    def high_priority_open_ids(self) -> Tuple[str, ...]:
        return tuple(self.ticket_ids[self.high_priority_open_mask()].tolist())


def _label(value: Any) -> str:
    """Enum member or plain string -> lowercase string."""
    return str(getattr(value, "value", value)).strip().lower()


def from_tickets(tickets: Iterable[Any]) -> TicketArrays:
    """Build ``TicketArrays`` from Day 03-style ticket objects (no per-element numpy loops).

    Raises ``NumericInputError`` for an unknown priority/category/status label
    instead of silently coding it.
    """
    items = list(tickets)
    ids, hours, ratings, prio, cat, is_open = [], [], [], [], [], []
    for position, t in enumerate(items):
        try:
            ids.append(str(t.ticket_id))
            hours.append(t.resolution_time_hours)
            ratings.append(t.customer_rating)
            prio.append(_lookup(PRIORITY_RANK, _label(t.priority), "priority"))
            cat.append(_lookup(CATEGORY_CODE, _label(t.category), "category"))
            is_open.append(_label(t.status) in OPEN_STATUSES)
        except AttributeError as exc:
            raise NumericInputError(f"ticket #{position} is missing an attribute: {exc}") from None

    return TicketArrays(
        ticket_ids=np.array(ids, dtype=np.str_) if ids else np.array([], dtype=np.str_),
        resolution_hours=as_float_array(hours, "resolution_hours", minimum=0.0),
        rating=_whole_numbers(
            as_float_array(ratings, "rating", minimum=1.0, maximum=5.0), "rating"),
        priority_rank=np.array(prio, dtype=np.int8),
        category_code=np.array(cat, dtype=np.int8),
        is_open=np.array(is_open, dtype=np.bool_),
    )



def _whole_numbers(array: np.ndarray, name: str) -> np.ndarray:
    """Day 03 only allows whole-number ratings, so 3.5 is a data error, not a value."""
    present = array[~np.isnan(array)]
    if present.size and (present != np.floor(present)).any():
        raise NumericInputError(f"{name}: must be whole numbers")
    return array


def _lookup(table: "dict[str, int]", label: str, field: str) -> int:
    try:
        return table[label]
    except KeyError:
        raise NumericInputError(f"{field}: unknown value {label!r}") from None


def select(array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Boolean-mask filter that fails loudly on a shape mismatch.

    NumPy itself raises IndexError for a wrong-length mask; we keep that
    behaviour but require a real boolean mask (an int array would be read as
    *positions*, a classic silent bug).
    """
    array = np.asarray(array)
    mask = np.asarray(mask)
    if mask.dtype != np.bool_:
        raise NumericInputError(f"mask must be boolean, got {mask.dtype}")
    if mask.shape != array.shape:
        raise NumericInputError(f"mask shape {mask.shape} != array shape {array.shape}")
    return array[mask]


def sequence_to_2d(rows: Sequence[Sequence[float]], name: str = "matrix") -> np.ndarray:
    """Build a rectangular float matrix; ragged rows are rejected with a clear message."""
    if isinstance(rows, np.ndarray):
        return as_float_array(rows, name, ndim=2)
    if not all(isinstance(r, (list, tuple, np.ndarray)) for r in rows):
        raise NumericInputError(f"{name}: every row must be a list, tuple or array")
    if len(rows) == 0:
        return np.empty((0, 0))
    lengths = {len(r) for r in rows}
    if len(lengths) > 1:
        raise NumericInputError(f"{name}: rows have different lengths {sorted(lengths)}")
    return as_float_array(rows, name, ndim=2)
