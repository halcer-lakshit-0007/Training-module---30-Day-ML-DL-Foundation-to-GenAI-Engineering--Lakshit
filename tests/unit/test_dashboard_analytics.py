"""Unit tests for the pure dashboard analytics (priority counts, resolution by category)."""

from __future__ import annotations

from datetime import datetime

from ticket_pipeline.models.ticket import Category, Priority, Status, Ticket

from ticket_dashboard.analytics import (
    CategoryResolution,
    priority_counts,
    resolution_by_category,
)

CREATED = datetime(2024, 1, 15)  # fixed date: no real clock


def make_ticket(
    ticket_id: str,
    priority: Priority = Priority.LOW,
    category: Category = Category.BILLING,
    hours: float | None = None,
) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        customer="Test Customer",
        priority=priority,
        category=category,
        status=Status.OPEN,
        description="Test description",
        created_at=CREATED,
        resolution_time_hours=hours,
    )


# --- priority_counts -----------------------------------------------------------

def test_priority_counts_include_zeros_in_fixed_order() -> None:
    tickets = [make_ticket("T1", Priority.LOW), make_ticket("T2", Priority.HIGH),
               make_ticket("T3", Priority.LOW)]
    assert priority_counts(tickets) == [("urgent", 0), ("high", 1), ("medium", 0), ("low", 2)]


def test_priority_counts_of_no_tickets_are_all_zero() -> None:
    assert priority_counts([]) == [("urgent", 0), ("high", 0), ("medium", 0), ("low", 0)]


# --- resolution_by_category --------------------------------------------------

def test_resolution_is_sorted_by_mean_descending() -> None:
    tickets = [
        make_ticket("T1", category=Category.BILLING, hours=2),
        make_ticket("T2", category=Category.TECHNICAL, hours=8),
        make_ticket("T3", category=Category.ACCOUNT, hours=5),
    ]
    assert [row.category for row in resolution_by_category(tickets)] == [
        "technical", "account", "billing",
    ]


def test_equal_means_are_tie_broken_by_category_name() -> None:
    tickets = [
        make_ticket("T1", category=Category.TECHNICAL, hours=3),
        make_ticket("T2", category=Category.ACCOUNT, hours=3),
        make_ticket("T3", category=Category.BILLING, hours=3),
    ]
    assert [row.category for row in resolution_by_category(tickets)] == [
        "account", "billing", "technical",
    ]


def test_mean_and_median_are_rounded_to_two_decimals() -> None:
    tickets = [
        make_ticket("T1", category=Category.GENERAL, hours=1),
        make_ticket("T2", category=Category.GENERAL, hours=1),
        make_ticket("T3", category=Category.GENERAL, hours=2),
        make_ticket("T4", category=Category.GENERAL, hours=2.333),
    ]
    # mean = 6.333 / 4 = 1.58325 -> 1.58; median = (1 + 2) / 2 = 1.5
    assert resolution_by_category(tickets) == [
        CategoryResolution("general", tickets_with_time=4, mean_hours=1.58, median_hours=1.5),
    ]


def test_median_differs_from_mean_for_skewed_values() -> None:
    tickets = [make_ticket(f"T{i}", category=Category.TECHNICAL, hours=h)
               for i, h in enumerate([1, 2, 30])]
    assert resolution_by_category(tickets) == [
        CategoryResolution("technical", tickets_with_time=3, mean_hours=11.0, median_hours=2.0),
    ]


def test_tickets_without_time_are_ignored_and_empty_categories_omitted() -> None:
    tickets = [
        make_ticket("T1", category=Category.BILLING, hours=None),
        make_ticket("T2", category=Category.ACCOUNT, hours=4),
        make_ticket("T3", category=Category.ACCOUNT, hours=None),
    ]
    assert resolution_by_category(tickets) == [
        CategoryResolution("account", tickets_with_time=1, mean_hours=4.0, median_hours=4.0),
    ]


def test_no_resolution_times_gives_an_empty_list() -> None:
    assert resolution_by_category([make_ticket("T1")]) == []


def test_zero_hours_count_as_a_recorded_time() -> None:
    result = resolution_by_category([make_ticket("T1", category=Category.GENERAL, hours=0)])
    assert result == [CategoryResolution("general", 1, 0.0, 0.0)]


# --- purity ------------------------------------------------------------------

def test_input_is_not_mutated() -> None:
    tickets = [
        make_ticket("T2", Priority.HIGH, Category.TECHNICAL, hours=8),
        make_ticket("T1", Priority.LOW, Category.BILLING, hours=2),
    ]
    snapshot = list(tickets)
    priority_counts(tickets)
    resolution_by_category(tickets)
    assert tickets == snapshot  # same tickets, same order


def test_generators_are_accepted() -> None:
    tickets = [make_ticket("T1", Priority.URGENT, hours=1)]
    assert priority_counts(t for t in tickets)[0] == ("urgent", 1)
    assert len(resolution_by_category(t for t in tickets)) == 1
