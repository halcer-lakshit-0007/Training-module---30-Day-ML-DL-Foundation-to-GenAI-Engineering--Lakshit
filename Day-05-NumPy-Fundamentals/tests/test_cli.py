import os
import sys
from pathlib import Path

import pytest

from sample_data import SAMPLE
from ticket_numerics.arrays import from_tickets
from ticket_numerics.cli import format_report, main

DAY03_CSV = Path(os.environ.get("DAY03_CSV") or (
    Path(__file__).resolve().parents[2]
    / "Day-03-Python-Engineering-Practices-Exceptions-Testing" / "data" / "tickets.csv"))


def test_report_contains_hand_checked_values():
    text = format_report(from_tickets(SAMPLE))
    for needle in ("Valid tickets      : 7", "mean 3.80", "median 3.00", "std 2.34",
                   "T001, T004, T009", "technical     6.25   (n=2)", "billing       3.00   (n=1)"):
        assert needle in text, needle
    assert "general" not in text.split("by category")[1]          # empty category omitted


def test_report_on_no_tickets_says_n_a_instead_of_failing():
    text = format_report(from_tickets([]))
    assert "Valid tickets      : 0" in text and "mean n/a" in text and "none" in text


def test_missing_day03_gives_exit_code_3_and_install_hint(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "ticket_pipeline", None)      # makes `import ticket_pipeline` fail
    monkeypatch.delitem(sys.modules, "ticket_pipeline.pipeline", raising=False)
    assert main(["whatever.csv"]) == 3
    assert "pip install -e" in capsys.readouterr().err


def test_cli_on_day03_sample_and_error_cases(tmp_path, capsys):
    pytest.importorskip("ticket_pipeline")
    if not DAY03_CSV.exists():
        pytest.skip("Day 03 folder not next to Day 05")
    assert main([str(DAY03_CSV)]) == 0
    assert "Valid tickets      : 7" in capsys.readouterr().out

    assert main([str(tmp_path / "missing.csv")]) == 2             # InputPathError
    bad = tmp_path / "bad.csv"
    header = "id,customer,priority,category,status,description,created_at"
    bad.write_text(f'{header}\nT1,Ann,low,billing,open,"unterminated,2024-01-01\n'
                   "T2,Bob,low,billing,open,fine,2024-01-02\n", encoding="utf-8")
    capsys.readouterr()
    assert main([str(bad)]) == 2                                  # malformed quote, not a one-row result
    err = capsys.readouterr().err
    assert "error:" in err and "missing required" not in err      # it is the QUOTE that was reported
