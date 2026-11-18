"""Task A output: shapes, dtypes, indexing and filtering on the Day 03 sample tickets.
Run:  PYTHONPATH=src:tests python scripts/show_arrays.py"""

import numpy as np

from sample_data import SAMPLE
from ticket_numerics.arrays import array_info, from_tickets, select
from ticket_numerics.metrics import group_mean, summary_stats

ta = from_tickets(SAMPLE)
print("== shapes and dtypes ==")
for name in ("ticket_ids", "resolution_hours", "rating", "priority_rank", "category_code", "is_open"):
    print(f"{name:18}{array_info(getattr(ta, name))}")
print(f"{'numeric_matrix':18}{array_info(ta.numeric_matrix())}")

print("\n== indexing / filtering (no loops) ==")
print("hours of open tickets      :", select(ta.resolution_hours, ta.is_open))
print("high-priority open ids     :", ta.high_priority_open_ids())
print("slice first 3 hours        :", ta.resolution_hours[:3], "| view shares memory:",
      np.shares_memory(ta.resolution_hours, ta.resolution_hours[:3]))
print("matrix column means (nan-aware):", np.nanmean(ta.numeric_matrix(), axis=0))

print("\n== summaries ==")
print("hours :", summary_stats(ta.resolution_hours))
print("rating:", summary_stats(ta.rating))
means, counts = group_mean(ta.resolution_hours, ta.category_code, 5)
print("hours by category (billing, technical, account, general, unknown):", means, counts)
