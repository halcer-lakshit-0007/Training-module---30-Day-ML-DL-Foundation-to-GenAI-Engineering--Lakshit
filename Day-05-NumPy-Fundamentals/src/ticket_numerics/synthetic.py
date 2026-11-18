"""Seeded synthetic data. Same seed -> identical array on every run and machine."""

from __future__ import annotations

import numbers
from typing import Optional

import numpy as np

MAX_N = 50_000_000          # 400 MB of float64: a guard against typos like 10**12, not a real limit


def require_int(value: object, name: str) -> int:
    """``value`` as an int, or TypeError (bool and floats such as 2.5 are not accepted)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    return int(value)


def require_size(n: object) -> int:
    n = require_int(n, "n")
    if n < 0:
        raise ValueError("n must not be negative")
    if n > MAX_N:
        raise ValueError(f"n must be at most {MAX_N:,}")
    return n


def make_hours(n: int, seed: Optional[int] = 42, missing_rate: float = 0.1) -> np.ndarray:
    """``n`` resolution times (float64, hours, > 0) with ~``missing_rate`` NaN.

    Uses a local ``default_rng(seed)`` generator, never the global NumPy
    state, so other code cannot change the result and this cannot change theirs.
    """
    n = require_size(n)
    if seed is not None:
        seed = require_int(seed, "seed")
        if seed < 0:
            raise ValueError("seed must not be negative")
    if isinstance(missing_rate, bool) or not isinstance(missing_rate, numbers.Real):
        raise TypeError(f"missing_rate must be a number, got {type(missing_rate).__name__}")
    if not 0.0 <= missing_rate <= 1.0:
        raise ValueError("missing_rate must be in [0, 1]")
    rng = np.random.default_rng(seed)
    hours = rng.gamma(shape=2.0, scale=3.0, size=n)       # right-skewed, like real ticket times
    hours[rng.random(n) < missing_rate] = np.nan
    return hours
