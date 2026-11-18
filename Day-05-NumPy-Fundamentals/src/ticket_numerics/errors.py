"""Specific exceptions for the numerical layer (same idea as Day 03's errors.py)."""

from __future__ import annotations


class NumericInputError(ValueError):
    """An input array has the wrong dtype, dimensions, range or contains inf."""


class IncompatibleShapesError(ValueError):
    """Two arrays cannot be combined because their shapes do not broadcast."""
