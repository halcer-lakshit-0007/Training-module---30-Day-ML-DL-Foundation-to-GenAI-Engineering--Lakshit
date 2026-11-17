"""Determinism: the same upload always gives exactly the same result.

Checked against everything that could vary between runs: repetition, row
order, Python's hash seed (set/dict ordering), the working directory, the
temporary directory, threads running at the same time, and the file name.
No randomness is used: the shuffled order is a fixed permutation.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import ticket_pipeline
from ticket_pipeline.config import DEFAULT_INPUT_PATH

from ticket_dashboard.service import DashboardResult, analyse_upload, upload_cache_key

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TICKETS_CSV = DEFAULT_INPUT_PATH  # Day 03's own data/tickets.csv, not a copy
# Wherever Day 03's package is imported from (editable install or pytest path).
DAY03_SRC = Path(ticket_pipeline.__file__).resolve().parents[1]
GOOD = TICKETS_CSV.read_bytes()


@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


def analytics(result: DashboardResult) -> tuple[object, ...]:
    """Everything except the parts that legitimately follow the row order."""
    return (result.rows_read, result.valid_count, result.priority_counts,
            result.resolution_by_category, result.quality, result.column_types)


def test_repeated_calls_give_identical_results(temp_root: Path) -> None:
    results = [analyse_upload("tickets.csv", GOOD) for _ in range(5)]
    assert all(result == results[0] for result in results)
    assert len({repr(result) for result in results}) == 1


def test_row_order_does_not_change_the_analytics(temp_root: Path) -> None:
    header, *rows = GOOD.splitlines()
    fixed_permutation = [7, 2, 9, 0, 5, 3, 8, 1, 6, 4]  # fixed, not random
    shuffled = b"\n".join([header, *(rows[i] for i in fixed_permutation)]) + b"\n"
    reversed_rows = b"\n".join([header, *reversed(rows)]) + b"\n"
    expected = analytics(analyse_upload("t.csv", GOOD))
    assert analytics(analyse_upload("t.csv", shuffled)) == expected
    assert analytics(analyse_upload("t.csv", reversed_rows)) == expected


def test_result_does_not_depend_on_the_working_directory(
    temp_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = analyse_upload("tickets.csv", GOOD)
    monkeypatch.chdir(tmp_path)
    assert analyse_upload("tickets.csv", GOOD) == expected


def test_result_does_not_depend_on_the_temp_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results = []
    for name in ("a", "a much longer directory name with spaces"):
        root = tmp_path / name
        root.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(root))
        results.append(analyse_upload("tickets.csv", GOOD))
    assert results[0] == results[1]


def test_file_name_changes_only_the_source_name(temp_root: Path) -> None:
    first = analyse_upload("one.csv", GOOD)
    second = analyse_upload("two.csv", GOOD)
    assert (first.source_name, second.source_name) == ("one.csv", "two.csv")
    assert analytics(first) == analytics(second) and first.rejected == second.rejected


def test_concurrent_uploads_do_not_interfere(temp_root: Path) -> None:
    """Each call has its own temporary directory, so parallel calls (as in the
    API's worker threads) cannot read each other's files."""
    other = GOOD.replace(b"T002,Bob Smith,low", b"T002,Bob Smith,urgent")
    jobs = [("tickets.csv", GOOD) if i % 2 == 0 else ("other.csv", other) for i in range(16)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda job: analyse_upload(*job), jobs))
    assert all(r == results[0] for r in results[0::2])
    assert all(r == results[1] for r in results[1::2])
    assert dict(results[1].priority_counts)["urgent"] == 2
    assert list(temp_root.iterdir()) == []


@pytest.mark.parametrize("seed", ["0", "1", "4242"])
def test_result_does_not_depend_on_the_hash_seed(seed: str) -> None:
    """Run the service in a fresh interpreter with a fixed PYTHONHASHSEED.

    Set and dict-of-set ordering changes with the seed. Identical output for
    every seed shows that no result depends on that ordering.
    """
    script = (
        "import sys; from pathlib import Path; "
        "from ticket_dashboard.service import analyse_upload; "
        "print(repr(analyse_upload('tickets.csv', Path(sys.argv[1]).read_bytes())))"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed,
           "PYTHONPATH": os.pathsep.join([str(PROJECT_ROOT / "src"), str(DAY03_SRC),
                                          os.environ.get("PYTHONPATH", "")])}
    completed = subprocess.run(
        [sys.executable, "-c", script, str(TICKETS_CSV)],
        capture_output=True, text=True, timeout=120, check=False, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == repr(analyse_upload("tickets.csv", GOOD))


# --- session cache key ---------------------------------------------------------

def test_cache_key_is_stable_and_known() -> None:
    assert upload_cache_key("a.csv", b"abc") == (
        "a.csv:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert upload_cache_key("a.csv", b"abc") == upload_cache_key("a.csv", b"abc")


def test_cache_key_changes_with_content_or_name() -> None:
    keys = {
        upload_cache_key("a.csv", b"abc"),
        upload_cache_key("a.csv", b"abd"),
        upload_cache_key("b.csv", b"abc"),
        upload_cache_key("a.csv", b""),
    }
    assert len(keys) == 4
