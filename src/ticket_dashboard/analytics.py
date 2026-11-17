"""
Dashboard analytics. Pure functions: no I/O and no logging.

These add two views that the dashboard needs and Day 03's
``ticket_pipeline.analytics.summary`` does not provide: priority counts in a
fixed business order (including zeros), and resolution-time statistics per
category. They work on Day 03's ``Ticket`` objects.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from ticket_pipeline.models.ticket import Priority, Ticket

PRIORITY_ORDER: tuple[Priority, ...] = (
    Priority.URGENT, Priority.HIGH, Priority.MEDIUM, Priority.LOW,
)


@dataclass(frozen=True)
class CategoryResolution:
    """Resolution-time statistics for one category."""

    category: str
    tickets_with_time: int
    mean_hours: float
    median_hours: float


def priority_counts(tickets: Iterable[Ticket]) -> list[tuple[str, int]]:
    """Count tickets per priority: urgent, high, medium, low, including zeros."""
    counts = Counter(t.priority for t in tickets)
    return [(priority.value, counts[priority]) for priority in PRIORITY_ORDER]


def resolution_by_category(tickets: Iterable[Ticket]) -> list[CategoryResolution]:
    """Mean and median resolution hours per category.

    Only tickets with a recorded resolution time count; categories without
    any are omitted. Values are rounded to 2 decimals. Sorted by mean hours
    (highest first), then category name.
    """
    hours: dict[str, list[float]] = {}
    for ticket in tickets:
        if ticket.resolution_time_hours is not None:
            hours.setdefault(ticket.category.value, []).append(ticket.resolution_time_hours)

    rows = [
        CategoryResolution(
            category=category,
            tickets_with_time=len(values),
            mean_hours=round(statistics.fmean(values), 2),
            median_hours=round(statistics.median(values), 2),
        )
        for category, values in hours.items()
    ]
    return sorted(rows, key=lambda row: (-row.mean_hours, row.category))
