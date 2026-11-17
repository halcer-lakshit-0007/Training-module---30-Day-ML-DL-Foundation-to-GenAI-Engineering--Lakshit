"""
Application/service layer: the only boundary between the Streamlit UI and
the ``ticket_pipeline`` package.

``analyse_upload`` takes what the browser sent (a file name and bytes) and
returns one immutable ``DashboardResult`` with everything the UI shows, or
raises ``UploadError`` with one message that is safe to show to the user.

This module imports neither Streamlit nor pandas, so it can be tested
without starting a UI. It does not read, validate or clean CSV data itself:
all of that is done by Day 03's ``ticket_pipeline`` package (CSVLoader and
run_pipeline), which is installed from its own folder, not copied.
"""

from __future__ import annotations

import hashlib
import math
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from ticket_pipeline.config import PipelineConfig
from ticket_pipeline.errors import InputPathError, MalformedFileError, SchemaMismatchError
from ticket_pipeline.pipeline import run_pipeline
from ticket_pipeline.processing.loader import CSVLoader
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS

from ticket_dashboard.analytics import (
    CategoryResolution,
    priority_counts,
    resolution_by_category,
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PREVIEW_ROWS = 10
MAX_NAME_LENGTH = 100  # keeps temp paths far below the Windows 260-character limit

EMPTY_FILE_MESSAGE = (
    "The uploaded file is empty. "
    "Choose a CSV file that has a header row and at least one ticket."
)
TOO_LARGE_MESSAGE = "The file is larger than 5 MB. Upload a smaller CSV."
UNREADABLE_MESSAGE = "The file could not be read. Upload it again."

_UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9._-]")
# [0-9], not \d: \d also matches non-ASCII digits such as Arabic-Indic ones.
_INTEGER = re.compile(r"[+-]?[0-9]+")
_DECIMAL = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Device names that Windows (before 11) refuses as file names, even with an extension.
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


class UploadError(Exception):
    """An uploaded file cannot be analysed. ``message`` is safe to show to the user."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class DashboardResult:
    """Everything the dashboard displays for one uploaded file."""

    source_name: str
    columns: tuple[str, ...]
    column_types: tuple[tuple[str, str], ...]     # (column, inferred type)
    rows_read: int
    preview: tuple[dict[str, str], ...]          # first PREVIEW_ROWS raw rows
    valid_count: int
    rejected: tuple[tuple[int, str], ...]         # (line, message)
    priority_counts: tuple[tuple[str, int], ...]
    resolution_by_category: tuple[CategoryResolution, ...]
    quality: tuple[tuple[str, str], ...]          # (metric, value) display rows


def safe_file_name(filename: str) -> str:
    """A file name that is safe to create on any operating system.

    Rules, applied in order: keep only the base name (drop any directory);
    replace every character outside [A-Za-z0-9._-] with "_"; drop a
    trailing ".csv" (any case); cut the rest to ``MAX_NAME_LENGTH`` - 4
    characters; prefix "_" to a Windows device name (CON, NUL, COM1, ...);
    add ".csv". A name with nothing left becomes "upload.csv".
    The result is deterministic, at most ``MAX_NAME_LENGTH`` characters,
    and applying the function again does not change it.
    """
    base = PurePosixPath(filename.replace("\\", "/")).name
    stem = _UNSAFE_CHARACTERS.sub("_", base)
    if stem.lower().endswith(".csv"):
        stem = stem[: -len(".csv")]
    stem = stem[: MAX_NAME_LENGTH - len(".csv")]
    if not stem:
        return "upload.csv"
    if stem.split(".")[0].upper() in _WINDOWS_RESERVED:
        stem = "_" + stem[: MAX_NAME_LENGTH - len(".csv") - 1]
    return stem + ".csv"


def upload_cache_key(filename: str, data: bytes) -> str:
    """Deterministic key for one upload: the file name plus the SHA-256 of the bytes.

    The name is part of the key because the result (and its messages) name
    the file: the same bytes uploaded as a different file must not reuse
    the old result.
    """
    return f"{filename}:{hashlib.sha256(data).hexdigest()}"


def _is_decimal(value: str) -> bool:
    return _DECIMAL.fullmatch(value) is not None and math.isfinite(float(value))


def _is_date(value: str) -> bool:
    if _DATE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(value)  # rejects impossible dates such as 2024-02-30
    except ValueError:
        return False
    return True


def infer_column_type(values: list[str]) -> str:
    """Infer a display type from the non-empty, trimmed values of one column.

    Rules, in order: no values -> "empty"; all ASCII whole numbers ->
    "integer"; all finite ASCII numbers (decimal point or exponent allowed)
    -> "decimal"; all real calendar dates written YYYY-MM-DD -> "date";
    otherwise "text". Only ASCII digits count, so the answer never depends
    on the locale or on Unicode digit rules.
    """
    present = [value.strip() for value in values if value.strip()]
    if not present:
        return "empty"
    if all(_INTEGER.fullmatch(value) for value in present):
        return "integer"
    if all(_is_decimal(value) for value in present):
        return "decimal"
    if all(_is_date(value) for value in present):
        return "date"
    return "text"


def analyse_upload(filename: str, data: bytes) -> DashboardResult:
    """Validate and analyse one uploaded ticket CSV.

    Raises ``UploadError`` for every expected problem with the file. Any
    other exception is a bug and propagates unchanged.
    """
    if len(data) == 0:
        raise UploadError(EMPTY_FILE_MESSAGE)
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(TOO_LARGE_MESSAGE)

    name = safe_file_name(filename)
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / name
        path.write_bytes(data)
        try:
            rows = CSVLoader(path, required_columns=REQUIRED_COLUMNS).load()
            result = run_pipeline(PipelineConfig(input_path=path))
        except (MalformedFileError, SchemaMismatchError) as exc:
            raise UploadError(_without_path(str(exc), temp_dir)) from exc
        except InputPathError as exc:
            raise UploadError(UNREADABLE_MESSAGE) from exc
    # The temporary directory has been deleted at this point.

    if result.rows_read == 0:
        raise UploadError(f"{name} has a header row but no data rows. Add at least one ticket.")

    columns = tuple(rows[0].values)
    rejected = tuple(
        (error.line, "; ".join(str(issue) for issue in error.issues))
        for error in result.rejected
    )
    rejected_columns = Counter(column for error in result.rejected for column in error.columns)
    without_time = sum(t.resolution_time_hours is None for t in result.tickets)

    return DashboardResult(
        source_name=name,
        columns=columns,
        column_types=tuple(
            (column, infer_column_type([row.values[column] for row in rows]))
            for column in columns
        ),
        rows_read=result.rows_read,
        preview=tuple(dict(row.values) for row in rows[:PREVIEW_ROWS]),
        valid_count=len(result.tickets),
        rejected=rejected,
        priority_counts=tuple(priority_counts(result.tickets)),
        resolution_by_category=tuple(resolution_by_category(result.tickets)),
        quality=(
            ("Rows read", str(result.rows_read)),
            ("Valid tickets", str(len(result.tickets))),
            ("Rejected rows", str(len(rejected))),
            ("Rejection rate", f"{len(rejected) / result.rows_read * 100:.1f}%"),
            ("Rejections by column", ", ".join(
                f"{column}: {count}" for column, count in sorted(rejected_columns.items())
            ) or "none"),
            ("Valid tickets without resolution time", str(without_time)),
        ),
    )


def _without_path(message: str, temp_dir: str) -> str:
    """Defence in depth: the pipeline's messages use the file name only, but
    a temporary path must never reach the user even if that changes."""
    return message.replace(temp_dir, "").replace(str(Path(temp_dir).resolve()), "")
