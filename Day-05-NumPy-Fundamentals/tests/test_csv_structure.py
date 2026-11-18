"""
Why Day 05 reads CSV only through Day 03's loader (and never csv.DictReader directly).

Part 1 runs everywhere and demonstrates the trap with the standard library alone.
Part 2 needs Day 03 (Python >= 3.11) and is skipped otherwise.
"""

import csv
import io

import pytest

# header / T1 with an unterminated quote / T2
MALFORMED = 'ticket_id,priority,category,resolution_time_hours\nT1,High,Technical,"5\nT2,Low,General,8\n'


def test_default_dictreader_silently_merges_the_next_ticket_into_one_record():
    rows = list(csv.DictReader(io.StringIO(MALFORMED, newline="")))
    assert len(rows) == 1                                           # T2 has vanished
    assert "T2,Low,General,8" in rows[0]["resolution_time_hours"]   # ...inside T1's value


def test_strict_reader_raises_instead():
    with pytest.raises(csv.Error):
        list(csv.reader(io.StringIO(MALFORMED, newline=""), strict=True))


def test_day03_loader_rejects_the_unterminated_quote(tmp_path):
    pytest.importorskip("ticket_pipeline")
    from ticket_pipeline.errors import MalformedFileError
    from ticket_pipeline.processing.loader import CSVLoader

    path = tmp_path / "malformed.csv"
    path.write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(MalformedFileError):
        CSVLoader(path).load()


def test_day03_loader_keeps_valid_quoted_values_and_row_count(tmp_path):
    pytest.importorskip("ticket_pipeline")
    from ticket_pipeline.processing.loader import CSVLoader

    path = tmp_path / "quoted.csv"
    path.write_text('id,note\nT1,"a, b"\nT2,"say ""hi"""\nT3,"two\nlines"\n', encoding="utf-8")
    rows = CSVLoader(path).load()
    assert [r.values["id"] for r in rows] == ["T1", "T2", "T3"]
    assert [r.values["note"] for r in rows] == ["a, b", 'say "hi"', "two\nlines"]
