"""API tests: the real FastAPI app through Starlette's TestClient (in-process, no network).

Unlike Streamlit's AppTest, TestClient can send real multipart uploads, so
every upload case is tested end to end through HTTP here.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ticket_pipeline.config import DEFAULT_INPUT_PATH

import ticket_api.main as api
from ticket_api.main import app
from ticket_dashboard.service import (
    EMPTY_FILE_MESSAGE,
    MAX_UPLOAD_BYTES,
    TOO_LARGE_MESSAGE,
    DashboardResult,
    analyse_upload,
)

TICKETS_CSV = DEFAULT_INPUT_PATH  # Day 03's own data/tickets.csv, not a copy
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client whose uploads are written under this test's tmp_path."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return TestClient(app)


def upload(client: TestClient, name: str, data: bytes) -> tuple[int, dict[str, object]]:
    response = client.post("/analyse", files={"file": (name, data, "text/csv")})
    return response.status_code, response.json()


# --- health and schema -------------------------------------------------------

def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_openapi_lists_both_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {"/health", "/analyse"}
    assert "post" in paths["/analyse"] and "get" in paths["/health"]


# --- successful analysis -----------------------------------------------------

def test_sample_dataset_through_http(client: TestClient) -> None:
    code, body = upload(client, "tickets.csv", TICKETS_CSV.read_bytes())
    assert code == 200
    assert body["source_name"] == "tickets.csv"
    assert (body["rows_read"], body["valid_count"]) == (10, 7)
    assert body["rejected"] == [
        {"line": 4, "problem": "'customer' is required but empty"},
        {"line": 7, "problem": "'description' is required but empty"},
        {"line": 9, "problem": "'customer' is required but empty; "
                               "'category' is required but empty"},
    ]
    assert body["priority_counts"] == [
        {"priority": "urgent", "tickets": 1}, {"priority": "high", "tickets": 2},
        {"priority": "medium", "tickets": 2}, {"priority": "low", "tickets": 2},
    ]
    assert body["resolution_by_category"] == [
        {"category": "technical", "tickets_with_time": 2, "mean_hours": 6.25,
         "median_hours": 6.25},
        {"category": "billing", "tickets_with_time": 1, "mean_hours": 3.0, "median_hours": 3.0},
        {"category": "account", "tickets_with_time": 1, "mean_hours": 2.0, "median_hours": 2.0},
        {"category": "unknown", "tickets_with_time": 1, "mean_hours": 1.5, "median_hours": 1.5},
    ]
    assert body["quality"] == [
        {"metric": "Rows read", "value": "10"},
        {"metric": "Valid tickets", "value": "7"},
        {"metric": "Rejected rows", "value": "3"},
        {"metric": "Rejection rate", "value": "30.0%"},
        {"metric": "Rejections by column", "value": "category: 1, customer: 2, description: 1"},
        {"metric": "Valid tickets without resolution time", "value": "2"},
    ]
    assert {"column": "created_at", "type": "date"} in body["column_types"]
    assert len(body["preview"]) == 10 and body["preview"][0]["id"] == "T001"


def test_all_rows_invalid_is_a_successful_response(client: TestClient) -> None:
    code, body = upload(client, "all_rows_invalid.csv",
                        (FIXTURES / "all_rows_invalid.csv").read_bytes())
    assert code == 200
    assert body["valid_count"] == 0
    assert body["resolution_by_category"] == []


def test_response_matches_the_service_result_exactly(client: TestClient) -> None:
    """The API adds no logic: its JSON is a 1:1 conversion of DashboardResult."""
    data = TICKETS_CSV.read_bytes()
    expected = api.to_response(analyse_upload("tickets.csv", data)).model_dump()
    assert upload(client, "tickets.csv", data) == (200, expected)


# --- errors --------------------------------------------------------------------

@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        pytest.param("empty.csv", EMPTY_FILE_MESSAGE, id="empty"),
        pytest.param("header_only.csv",
                     "header_only.csv has a header row but no data rows. Add at least one ticket.",
                     id="header-only"),
        pytest.param("missing_columns.csv",
                     "missing_columns.csv is missing required column(s): category, created_at, "
                     "customer, description, status. Found columns: id, priority. "
                     "Add the missing column(s) to the header row.",
                     id="missing-columns"),
        pytest.param("malformed_quote.csv",
                     "CSV could not be parsed (unexpected end of data) (malformed_quote.csv, "
                     "line 2). Check for an unbalanced or stray double quote, or binary content.",
                     id="malformed-quote"),
    ],
)
def test_bad_files_return_422_with_the_service_message(
    client: TestClient, fixture: str, expected: str
) -> None:
    assert upload(client, fixture, (FIXTURES / fixture).read_bytes()) == (
        422, {"detail": expected},
    )


def test_file_over_5_mb_returns_413(client: TestClient) -> None:
    code, body = upload(client, "big.csv", b"x" * (MAX_UPLOAD_BYTES + 1))
    assert (code, body) == (413, {"detail": TOO_LARGE_MESSAGE})


def test_request_without_a_file_returns_422(client: TestClient) -> None:
    response = client.post("/analyse")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_unsafe_filename_is_made_safe(client: TestClient) -> None:
    code, body = upload(client, "../my tickets?.csv", TICKETS_CSV.read_bytes())
    assert (code, body["source_name"]) == (200, "my_tickets_.csv")


def test_uploads_leave_no_temporary_files(client: TestClient, tmp_path: Path) -> None:
    upload(client, "tickets.csv", TICKETS_CSV.read_bytes())
    upload(client, "header_only.csv", (FIXTURES / "header_only.csv").read_bytes())
    assert list(tmp_path.iterdir()) == []


def test_unexpected_error_returns_500_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a bug in the service: the client gets a generic 500, no internals."""

    def buggy(_filename: str, _data: bytes) -> DashboardResult:
        raise ZeroDivisionError("simulated bug in /secret/path")

    monkeypatch.setattr(api, "analyse_upload", buggy)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/analyse", files={"file": ("tickets.csv", b"id\n1\n", "text/csv")}
    )
    assert response.status_code == 500
    assert "ZeroDivisionError" not in response.text
    assert "/secret/path" not in response.text
    assert "Traceback" not in response.text


# --- edge cases and determinism ----------------------------------------------

def test_identical_requests_give_identical_responses(client: TestClient) -> None:
    data = TICKETS_CSV.read_bytes()
    responses = [client.post("/analyse", files={"file": ("t.csv", data, "text/csv")})
                 for _ in range(3)]
    assert len({(r.status_code, r.content) for r in responses}) == 1


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("a" * 300 + ".csv", "a" * 96 + ".csv"), ("CON.csv", "_CON.csv"),
     ("C:\\Users\\someone\\t.csv", "t.csv")],
    ids=["300-characters", "windows-device", "windows-path"],
)
def test_awkward_file_names_are_accepted(
    client: TestClient, filename: str, expected: str
) -> None:
    code, body = upload(client, filename, TICKETS_CSV.read_bytes())
    assert (code, body["source_name"]) == (200, expected)


def test_content_type_is_ignored(client: TestClient) -> None:
    """Browsers send unreliable content types; the bytes decide, not the label."""
    response = client.post(
        "/analyse", files={"file": ("t.csv", TICKETS_CSV.read_bytes(), "image/png")}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "request_kwargs",
    [
        pytest.param({"files": {"upload": ("t.csv", b"id\n", "text/csv")}}, id="wrong-field"),
        pytest.param({"data": {"file": "id,customer"}}, id="text-not-file"),
        pytest.param({"json": {"file": "id,customer"}}, id="json-body"),
        pytest.param({"files": {"file": ("", b"id\n", "text/csv")}}, id="no-filename"),
    ],
)
def test_malformed_requests_return_422(
    client: TestClient, request_kwargs: dict[str, object]
) -> None:
    response = client.post("/analyse", **request_kwargs)  # type: ignore[arg-type]
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_with_two_file_parts_the_last_one_is_used(client: TestClient) -> None:
    """Pinned so the behaviour cannot change silently: FastAPI keeps the last part."""
    response = client.post("/analyse", files=[
        ("file", ("first.csv", TICKETS_CSV.read_bytes(), "text/csv")),
        ("file", ("second.csv", b"", "text/csv")),
    ])
    assert (response.status_code, response.json()) == (422, {"detail": EMPTY_FILE_MESSAGE})


def test_wrong_method_returns_405(client: TestClient) -> None:
    assert client.get("/analyse").status_code == 405


def test_exactly_5_mb_is_not_rejected_for_size(client: TestClient) -> None:
    header = (FIXTURES / "header_only.csv").read_bytes()
    data = header + b"\n" * (MAX_UPLOAD_BYTES - len(header))
    code, body = upload(client, "big.csv", data)
    assert code == 422 and "no data rows" in str(body["detail"])


# --- layering ----------------------------------------------------------------

def test_api_does_not_import_streamlit_or_the_pipeline_directly() -> None:
    """The API talks only to the service layer, like the Streamlit UI."""
    source = Path(api.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "ticket_dashboard" in imported
    assert not imported & {"streamlit", "pandas", "ticket_pipeline"}
