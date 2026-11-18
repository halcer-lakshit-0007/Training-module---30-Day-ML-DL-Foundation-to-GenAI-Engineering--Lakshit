"""
The 7 VALID tickets of Day 03's data/tickets.csv (T003, T006, T008 are rejected
by Day 03 for an empty customer/description), transcribed by hand. Expected
numbers in the tests were worked out on paper from these rows, not by running
the code under test; see README section 5.
"""

from types import SimpleNamespace as T

SAMPLE = [
    T(ticket_id="T001", priority="high",   category="billing",   status="open",     resolution_time_hours=None, customer_rating=None),
    T(ticket_id="T002", priority="low",    category="technical", status="closed",   resolution_time_hours=4.5,  customer_rating=4),
    T(ticket_id="T004", priority="urgent", category="unknown",   status="pending",  resolution_time_hours=1.5,  customer_rating=3),
    T(ticket_id="T005", priority="low",    category="technical", status="resolved", resolution_time_hours=8.0,  customer_rating=4),
    T(ticket_id="T007", priority="medium", category="billing",   status="closed",   resolution_time_hours=3.0,  customer_rating=5),
    T(ticket_id="T009", priority="high",   category="technical", status="open",     resolution_time_hours=None, customer_rating=3),
    T(ticket_id="T010", priority="medium", category="account",   status="pending",  resolution_time_hours=2.0,  customer_rating=4),
]
