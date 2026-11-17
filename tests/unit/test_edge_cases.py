"""Edge cases for uploads: every input either produces a result or raises
UploadError with an exact message. No other exception may escape, because
the UI would show it as "Something went wrong" and the API as a 500.

The CSV text is built from constants here (no files, no randomness), and
temporary files go to pytest's tmp_path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from ticket_pipeline.config import DEFAULT_INPUT_PATH

from ticket_dashboard.service import (
    MAX_NAME_LENGTH,
    DashboardResult,
    UploadError,
    analyse_upload,
    infer_column_type,
    safe_file_name,
)

TICKETS_CSV = DEFAULT_INPUT_PATH  # Day 03's own data/tickets.csv, not a copy
HEADER = (
    "id,customer,priority,category,status,description,"
    "resolution_time_hours,customer_rating,created_at"
)
# Normalised to "\n": with core.autocrlf, Git may check Day 03's file out with CRLF.
GOOD = b"\n".join(TICKETS_CSV.read_bytes().splitlines()) + b"\n"
ROW = "T001,Ann Lee,low,billing,open,Login issue,2,4,2024-01-15"


@pytest.fixture(autouse=True)
def _temp_in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


def csv_bytes(*rows: str, header: str = HEADER, newline: str = "\n") -> bytes:
    return (newline.join([header, *rows]) + newline).encode("utf-8")


def message_for(filename: str, data: bytes) -> str:
    with pytest.raises(UploadError) as caught:
        analyse_upload(filename, data)
    return caught.value.message


def analytics(result: DashboardResult) -> tuple[object, ...]:
    """The parts of a result that must not depend on file formatting."""
    return (result.rows_read, result.valid_count, result.rejected, result.priority_counts,
            result.resolution_by_category, result.quality, result.column_types)


# --- encodings and line endings ----------------------------------------------

def test_utf8_byte_order_mark_is_accepted(tmp_path: Path) -> None:
    with_bom = analyse_upload("bom.csv", b"\xef\xbb\xbf" + GOOD)
    assert with_bom.columns[0] == "id"  # the BOM is not part of the first column name
    assert analytics(with_bom) == analytics(analyse_upload("tickets.csv", GOOD))


@pytest.mark.parametrize("newline", [b"\r\n", b"\r"], ids=["crlf", "cr-only"])
def test_line_endings_do_not_change_the_result(newline: bytes) -> None:
    converted = GOOD.replace(b"\n", newline)
    assert analytics(analyse_upload("t.csv", converted)) == analytics(
        analyse_upload("t.csv", GOOD)
    )


LATIN_1 = csv_bytes("T001,José,low,billing,open,x,,,2024-01-15").replace(
    "é".encode(), "é".encode("latin-1"))


@pytest.mark.parametrize(
    ("data", "position"),
    [
        pytest.param(LATIN_1, LATIN_1.index(b"\xe9"), id="latin-1"),
        pytest.param(GOOD.decode("utf-8").encode("utf-16"), 0, id="utf-16"),
        pytest.param(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", 0, id="binary-png"),
    ],
)
def test_non_utf8_content_gives_the_encoding_message(data: bytes, position: int) -> None:
    assert message_for("file.csv", data) == (
        f"File is not valid UTF-8 text (byte {position}) (file.csv). "
        "Re-save the file with UTF-8 encoding."
    )


def test_nul_byte_is_rejected() -> None:
    data = csv_bytes("T001,Ann\x00Lee,low,billing,open,x,,,2024-01-15")
    assert message_for("nul_byte.csv", data) == (
        "Row contains a NUL byte (binary or corrupted content) (nul_byte.csv, line 2). "
        "Re-export the file as plain UTF-8 text."
    )


# --- headers -------------------------------------------------------------------

def test_file_with_only_a_newline_has_no_columns() -> None:
    assert message_for("blank.csv", b"\n") == (
        "blank.csv is missing required column(s): category, created_at, customer, "
        "description, id, priority, status. Found columns: (none). "
        "Add the missing column(s) to the header row."
    )


def test_file_with_only_whitespace_has_a_blank_header() -> None:
    assert message_for("spaces.csv", b"   \n  \n") == (
        "Header has blank column name(s) at position(s) 1 (spaces.csv, line 1). "
        "Name every column, or remove trailing commas from the header."
    )


def test_header_without_a_final_newline_is_header_only() -> None:
    assert message_for("h.csv", HEADER.encode()) == (
        "h.csv has a header row but no data rows. Add at least one ticket."
    )


def test_header_with_only_blank_lines_after_it_is_header_only() -> None:
    assert "has a header row but no data rows" in message_for("h.csv", csv_bytes("", "  ", ""))


def test_duplicate_header_after_normalising_is_rejected() -> None:
    data = csv_bytes(ROW + ",x", header=HEADER + ", ID ")
    assert message_for("dup.csv", data) == (
        "Header repeats column(s) after ignoring case and spaces: "
        "'id' appears as 'id', ' ID ' (dup.csv, line 1). Keep exactly one column for each name."
    )


def test_header_names_are_normalised_and_extra_columns_kept() -> None:
    header = HEADER.upper().replace("ID,", " Id ,", 1) + ",Agent Notes"
    result = analyse_upload("t.csv", csv_bytes(ROW + ",called back", header=header))
    assert result.columns[0] == "id" and result.columns[-1] == "agent notes"
    assert dict(result.column_types)["agent notes"] == "text"
    assert result.valid_count == 1


# --- rows ------------------------------------------------------------------------

def test_row_with_too_many_fields_is_rejected() -> None:
    assert message_for("wide.csv", csv_bytes(ROW + ",extra")) == (
        "Row has 10 fields but the header defines 9 (wide.csv, line 2). "
        "Remove the extra field(s) or quote values that contain commas."
    )


def test_short_row_is_padded_and_reported() -> None:
    result = analyse_upload("short.csv", csv_bytes("T001,Ann Lee,low,billing,open,x"))
    assert result.rejected == ((2, "'created_at' is required but empty"),)
    assert result.preview[0]["created_at"] == ""


def test_field_over_the_csv_limit_is_rejected() -> None:
    data = csv_bytes("T001,Ann," + "x" * 200_000 + ",billing,open,x,,,2024-01-15")
    assert message_for("huge.csv", data) == (
        "CSV could not be parsed (field larger than field limit (131072)) (huge.csv, line 2). "
        "Check for an unbalanced or stray double quote, or binary content."
    )


def test_blank_lines_are_skipped_and_line_numbers_kept() -> None:
    data = csv_bytes(ROW, "", "   ", "T002,,low,billing,open,x,,,2024-01-15")
    result = analyse_upload("gaps.csv", data)
    assert result.rows_read == 2
    assert result.rejected == ((5, "'customer' is required but empty"),)


def test_multiline_quoted_value_keeps_later_line_numbers_right() -> None:
    data = csv_bytes('T001,Ann Lee,low,billing,open,"first line\nsecond line",,,2024-01-15',
                     "T002,,low,billing,open,x,,,2024-01-15")
    result = analyse_upload("multi.csv", data)
    assert result.valid_count == 1
    assert result.rejected == ((4, "'customer' is required but empty"),)


def test_duplicate_ids_ignoring_case_are_rejected() -> None:
    result = analyse_upload("dups.csv", csv_bytes(ROW, ROW.replace("T001", " t001 ", 1)))
    assert result.valid_count == 1
    assert result.rejected == ((3, "'id' duplicates line 2"),)
    assert dict(result.quality)["Rejections by column"] == "id: 1"


def test_unknown_category_is_counted_as_unknown() -> None:
    result = analyse_upload("cat.csv", csv_bytes(ROW.replace("billing", "Shipping")))
    assert [r.category for r in result.resolution_by_category] == ["unknown"]


def test_valid_tickets_without_any_resolution_time() -> None:
    result = analyse_upload("open.csv", csv_bytes("T001,Ann Lee,low,billing,open,x,,,2024-01-15"))
    assert result.valid_count == 1
    assert result.resolution_by_category == ()
    assert dict(result.quality)["Valid tickets without resolution time"] == "1"
    assert dict(result.column_types)["resolution_time_hours"] == "empty"


@pytest.mark.parametrize(
    ("valid", "invalid", "rate"),
    [(1, 0, "0.0%"), (2, 1, "33.3%"), (1, 2, "66.7%"), (7, 1, "12.5%"), (0, 3, "100.0%")],
)
def test_rejection_rate_is_rounded_to_one_decimal(valid: int, invalid: int, rate: str) -> None:
    rows = [ROW.replace("T001", f"T{i:03}", 1) for i in range(valid)]
    rows += [f"X{i:03},,low,billing,open,x,,,2024-01-15" for i in range(invalid)]
    assert dict(analyse_upload("r.csv", csv_bytes(*rows)).quality)["Rejection rate"] == rate


# --- file names --------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("a" * 300 + ".csv", id="300-characters"),
        pytest.param("é" * 200 + ".csv", id="300-bytes-unicode"),
        pytest.param("CON.csv", id="windows-device-con"),
        pytest.param("nul", id="windows-device-nul"),
        pytest.param("com1.backup.csv", id="windows-device-com1"),
        pytest.param("???.csv", id="only-unsafe"),
        pytest.param(" .csv", id="space-only-stem"),
        pytest.param("../../etc/passwd", id="path-traversal"),
        pytest.param("C:\\Windows\\System32\\tickets.csv", id="windows-path"),
    ],
)
def test_awkward_file_names_never_crash(filename: str) -> None:
    result = analyse_upload(filename, GOOD)
    assert result.source_name == safe_file_name(filename)
    assert len(result.source_name) <= MAX_NAME_LENGTH
    assert result.source_name.endswith(".csv")
    assert (result.rows_read, result.valid_count) == (10, 7)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("CON.csv", "_CON.csv"),
        ("con.backup.csv", "_con.backup.csv"),
        ("LPT9", "_LPT9.csv"),
        ("CONSOLE.csv", "CONSOLE.csv"),  # only exact device names are changed
        ("tickets.CSV", "tickets.csv"),
        ("a" * 300, "a" * (MAX_NAME_LENGTH - 4) + ".csv"),
    ],
)
def test_safe_file_name_edge_cases(filename: str, expected: str) -> None:
    assert safe_file_name(filename) == expected


@pytest.mark.parametrize(
    "filename",
    ["", ".csv", "..", "CON", "a" * 300, "../my tickets?.csv", "x.csv.csv", "é.CSV", "_CON.csv"],
)
def test_safe_file_name_is_idempotent(filename: str) -> None:
    once = safe_file_name(filename)
    assert safe_file_name(once) == once


# --- column type inference ---------------------------------------------------

@pytest.mark.parametrize(
    ("values", "expected"),
    [
        pytest.param(["٢٠٢٤-٠١-١٥"], "text", id="arabic-indic-date"),
        pytest.param(["١٢"], "text", id="arabic-indic-number"),
        pytest.param(["１２"], "text", id="fullwidth-number"),
        pytest.param(["2024-02-30"], "text", id="impossible-date"),
        pytest.param(["2024-13-01"], "text", id="month-13"),
        pytest.param(["2024-02-29"], "date", id="leap-day"),
        pytest.param(["1e3", "2.5E-1"], "decimal", id="exponent"),
        pytest.param(["1e400"], "text", id="overflow-not-finite"),
        pytest.param(["inf", "nan"], "text", id="inf-nan"),
        pytest.param(["4.", "-.5", "+3"], "decimal", id="loose-decimals"),
        pytest.param(["1_000"], "text", id="underscore"),
        pytest.param(["007", "-0"], "integer", id="leading-zeros"),
    ],
)
def test_infer_column_type_edge_cases(values: list[str], expected: str) -> None:
    assert infer_column_type(values) == expected
