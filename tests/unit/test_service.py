"""Unit tests for the service layer between the Streamlit UI and ticket_pipeline.

Temporary files are redirected into pytest's ``tmp_path`` (by setting
``tempfile.tempdir``), so the tests can prove the upload is deleted after
each call and that no message reveals where it was stored.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest
from ticket_pipeline.config import DEFAULT_INPUT_PATH, PipelineConfig
from ticket_pipeline.pipeline import run_pipeline

import ticket_dashboard.service as service
from ticket_dashboard.analytics import CategoryResolution
from ticket_dashboard.service import (
    EMPTY_FILE_MESSAGE,
    MAX_UPLOAD_BYTES,
    PREVIEW_ROWS,
    TOO_LARGE_MESSAGE,
    UNREADABLE_MESSAGE,
    UploadError,
    analyse_upload,
    infer_column_type,
    safe_file_name,
)

TICKETS_CSV = DEFAULT_INPUT_PATH  # Day 03's own data/tickets.csv, not a copy
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make tempfile create its directories inside this test's tmp_path."""
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def upload_error(filename: str, data: bytes) -> str:
    with pytest.raises(UploadError) as caught:
        analyse_upload(filename, data)
    return caught.value.message


# --- UploadError cases -------------------------------------------------------

UPLOAD_ERROR_CASES = [
    pytest.param("empty.csv", EMPTY_FILE_MESSAGE, id="empty"),
    pytest.param(
        "header_only.csv",
        "header_only.csv has a header row but no data rows. Add at least one ticket.",
        id="header-only",
    ),
    pytest.param(
        "missing_columns.csv",
        "missing_columns.csv is missing required column(s): category, created_at, customer, "
        "description, status. Found columns: id, priority. "
        "Add the missing column(s) to the header row.",
        id="missing-columns",
    ),
    pytest.param(
        "malformed_quote.csv",
        "CSV could not be parsed (unexpected end of data) (malformed_quote.csv, line 2). "
        "Check for an unbalanced or stray double quote, or binary content.",
        id="malformed-quote",
    ),
]


@pytest.mark.parametrize(("fixture", "expected"), UPLOAD_ERROR_CASES)
def test_bad_files_raise_upload_error_with_exact_message(
    fixture: str, expected: str, temp_root: Path
) -> None:
    assert upload_error(fixture, fixture_bytes(fixture)) == expected


def test_empty_fixture_is_really_zero_bytes() -> None:
    assert (FIXTURES / "empty.csv").stat().st_size == 0


def test_file_over_5_mb_is_rejected_before_it_is_written(temp_root: Path) -> None:
    assert upload_error("big.csv", b"x" * (MAX_UPLOAD_BYTES + 1)) == TOO_LARGE_MESSAGE
    assert list(temp_root.iterdir()) == []


def test_file_of_exactly_5_mb_is_not_rejected_for_size(temp_root: Path) -> None:
    header = (FIXTURES / "header_only.csv").read_bytes()
    data = header + b"\n" * (MAX_UPLOAD_BYTES - len(header))  # blank lines are skipped
    assert len(data) == MAX_UPLOAD_BYTES
    assert "no data rows" in upload_error("big.csv", data)


def test_unreadable_file_gives_a_generic_message(
    temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate the OS refusing to read the file (an external boundary)."""
    data = TICKETS_CSV.read_bytes()
    real_open = Path.open

    def deny_reads(self: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        if "r" in mode:  # writing the upload still works; reading it back fails
            raise PermissionError(13, "Permission denied")
        return real_open(self, mode, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(Path, "open", deny_reads)
    message = upload_error("tickets.csv", data)
    assert message == UNREADABLE_MESSAGE


def test_file_with_only_invalid_rows_is_analysed_without_error(temp_root: Path) -> None:
    result = analyse_upload("all_rows_invalid.csv", fixture_bytes("all_rows_invalid.csv"))
    assert (result.rows_read, result.valid_count, len(result.rejected)) == (2, 0, 2)
    assert result.priority_counts == (("urgent", 0), ("high", 0), ("medium", 0), ("low", 0))
    assert result.resolution_by_category == ()
    assert dict(result.quality)["Rejection rate"] == "100.0%"


# --- established results on data/tickets.csv --------------------------------

@pytest.fixture
def tickets_result(temp_root: Path) -> service.DashboardResult:
    return analyse_upload("tickets.csv", TICKETS_CSV.read_bytes())


def test_sample_dataset_counts(tickets_result: service.DashboardResult) -> None:
    assert tickets_result.source_name == "tickets.csv"
    assert (tickets_result.rows_read, tickets_result.valid_count) == (10, 7)
    assert tickets_result.rejected == (
        (4, "'customer' is required but empty"),
        (7, "'description' is required but empty"),
        (9, "'customer' is required but empty; 'category' is required but empty"),
    )


def test_sample_dataset_priority_counts(tickets_result: service.DashboardResult) -> None:
    assert tickets_result.priority_counts == (
        ("urgent", 1), ("high", 2), ("medium", 2), ("low", 2),
    )


def test_sample_dataset_resolution_by_category(tickets_result: service.DashboardResult) -> None:
    assert tickets_result.resolution_by_category == (
        CategoryResolution("technical", 2, 6.25, 6.25),
        CategoryResolution("billing", 1, 3.0, 3.0),
        CategoryResolution("account", 1, 2.0, 2.0),
        CategoryResolution("unknown", 1, 1.5, 1.5),
    )


def test_sample_dataset_quality_rows(tickets_result: service.DashboardResult) -> None:
    assert tickets_result.quality == (
        ("Rows read", "10"),
        ("Valid tickets", "7"),
        ("Rejected rows", "3"),
        ("Rejection rate", "30.0%"),
        ("Rejections by column", "category: 1, customer: 2, description: 1"),
        ("Valid tickets without resolution time", "2"),
    )


def test_sample_dataset_overall_average_resolution_is_unchanged() -> None:
    summary = run_pipeline(PipelineConfig(input_path=TICKETS_CSV)).summary
    assert summary.average_resolution_hours == 3.8


def test_sample_dataset_columns_preview_and_types(
    tickets_result: service.DashboardResult,
) -> None:
    assert tickets_result.columns == (
        "id", "customer", "priority", "category", "status", "description",
        "resolution_time_hours", "customer_rating", "created_at",
    )
    assert dict(tickets_result.column_types) == {
        "id": "text", "customer": "text", "priority": "text", "category": "text",
        "status": "text", "description": "text", "resolution_time_hours": "decimal",
        "customer_rating": "integer", "created_at": "date",
    }
    assert len(tickets_result.preview) == PREVIEW_ROWS
    assert tickets_result.preview[0]["id"] == "T001"
    assert tickets_result.preview[2]["customer"] == ""  # raw values, not cleaned


def test_preview_is_limited_to_preview_rows(temp_root: Path) -> None:
    header = (FIXTURES / "header_only.csv").read_text(encoding="utf-8").strip()
    rows = [f"T{i:03},Name {i},low,billing,open,Text,,,2024-01-15" for i in range(15)]
    result = analyse_upload("many.csv", "\n".join([header, *rows]).encode())
    assert (result.rows_read, len(result.preview)) == (15, PREVIEW_ROWS)
    assert dict(result.quality)["Rejections by column"] == "none"


# --- temporary files and paths ----------------------------------------------

def test_temp_directory_is_deleted_after_success(temp_root: Path) -> None:
    analyse_upload("tickets.csv", TICKETS_CSV.read_bytes())
    assert list(temp_root.iterdir()) == []


@pytest.mark.parametrize("fixture", ["header_only.csv", "missing_columns.csv",
                                     "malformed_quote.csv"])
def test_temp_directory_is_deleted_after_an_error(fixture: str, temp_root: Path) -> None:
    upload_error(fixture, fixture_bytes(fixture))
    assert list(temp_root.iterdir()) == []


@pytest.mark.parametrize("fixture", ["empty.csv", "header_only.csv", "missing_columns.csv",
                                     "malformed_quote.csv"])
def test_error_messages_never_contain_the_temp_directory(
    fixture: str, temp_root: Path
) -> None:
    message = upload_error(fixture, fixture_bytes(fixture))
    assert str(temp_root) not in message
    assert str(temp_root.resolve()) not in message
    assert "\\" not in message and "/" not in message


def test_unsafe_filename_is_made_safe(temp_root: Path) -> None:
    result = analyse_upload("../my tickets?.csv", TICKETS_CSV.read_bytes())
    assert result.source_name == "my_tickets_.csv"
    message = upload_error("../my tickets?.csv", fixture_bytes("header_only.csv"))
    assert message.startswith("my_tickets_.csv has a header row")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("../my tickets?.csv", "my_tickets_.csv"),
        ("C:\\Users\\someone\\data.csv", "data.csv"),
        ("/home/someone/data.CSV", "data.csv"),
        ("report.txt", "report.txt.csv"),
        ("tickets", "tickets.csv"),
        ("", "upload.csv"),
        ("..", "...csv"),
    ],
)
def test_safe_file_name(filename: str, expected: str) -> None:
    assert safe_file_name(filename) == expected


# --- infer_column_type -------------------------------------------------------

@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], "empty"),
        (["", "  "], "empty"),
        (["1", " 2 ", "", "-3"], "integer"),
        (["1", "2.5", ".5"], "decimal"),
        (["2024-01-15", " 2024-01-16"], "date"),
        (["2024-01-15", "soon"], "text"),
        (["1", "abc"], "text"),
        (["nan"], "text"),
    ],
)
def test_infer_column_type(values: list[str], expected: str) -> None:
    assert infer_column_type(values) == expected


# --- layering ----------------------------------------------------------------

def test_service_imports_neither_streamlit_nor_pandas() -> None:
    source = Path(service.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "ticket_pipeline" in imported  # sanity: the parser found the imports
    assert not imported & {"streamlit", "pandas"}
