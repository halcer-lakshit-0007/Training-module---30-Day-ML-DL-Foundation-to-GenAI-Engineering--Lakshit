"""Integration with Day 03. Skipped (not failed) when ticket_pipeline cannot be imported,
e.g. on Python < 3.11. Run on 3.11+ to execute it."""

import os
from pathlib import Path

import pytest

pytest.importorskip("ticket_pipeline")

from ticket_numerics.bridge import arrays_from_csv  # noqa: E402
from ticket_numerics.metrics import summary_stats  # noqa: E402

# Sibling folder in the consolidated repo; set DAY03_CSV to point somewhere else.
DAY03_CSV = Path(os.environ.get("DAY03_CSV") or (
    Path(__file__).resolve().parents[2]
    / "Day-03-Python-Engineering-Practices-Exceptions-Testing" / "data" / "tickets.csv"))


@pytest.mark.skipif(not DAY03_CSV.exists(), reason="Day 03 folder not next to Day 05")
def test_day03_sample_file_matches_hand_checked_values():
    ta = arrays_from_csv(DAY03_CSV)
    assert len(ta) == 7                                   # 10 rows, 3 rejected by Day 03
    assert summary_stats(ta.resolution_hours).mean == 3.8
    assert ta.high_priority_open_ids() == ("T001", "T004", "T009")
