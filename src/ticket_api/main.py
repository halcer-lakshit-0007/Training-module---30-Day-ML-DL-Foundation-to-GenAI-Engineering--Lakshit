"""
FastAPI backend for the ticket dashboard.

A second front end on the same service layer as the Streamlit UI: it accepts
an uploaded CSV, calls ``service.analyse_upload`` and returns the result as
JSON. It holds no CSV reading, validation, cleaning or calculation of its own.
Run with:

    uvicorn ticket_api.main:app --reload

Endpoints:
    GET  /health    liveness check
    POST /analyse   multipart upload, form field "file"
"""

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from ticket_dashboard.service import (
    MAX_UPLOAD_BYTES,
    DashboardResult,
    UploadError,
    analyse_upload,
)

app = FastAPI(
    title="Ticket Data API",
    version="1.0.0",
    description="Upload a support-ticket CSV and get a preview, analytics and data-quality report.",
)


# --- response models (JSON shape of DashboardResult) ------------------------

class ColumnType(BaseModel):
    column: str
    type: str


class RejectedRow(BaseModel):
    line: int
    problem: str


class PriorityCount(BaseModel):
    priority: str
    tickets: int


class CategoryResolutionOut(BaseModel):
    category: str
    tickets_with_time: int
    mean_hours: float
    median_hours: float


class QualityMetric(BaseModel):
    metric: str
    value: str


class AnalysisResponse(BaseModel):
    source_name: str
    columns: list[str]
    column_types: list[ColumnType]
    rows_read: int
    preview: list[dict[str, str]]
    valid_count: int
    rejected: list[RejectedRow]
    priority_counts: list[PriorityCount]
    resolution_by_category: list[CategoryResolutionOut]
    quality: list[QualityMetric]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str


def to_response(result: DashboardResult) -> AnalysisResponse:
    """Convert the service's immutable result into the JSON response model."""
    return AnalysisResponse(
        source_name=result.source_name,
        columns=list(result.columns),
        column_types=[ColumnType(column=c, type=t) for c, t in result.column_types],
        rows_read=result.rows_read,
        preview=[dict(row) for row in result.preview],
        valid_count=result.valid_count,
        rejected=[RejectedRow(line=line, problem=problem) for line, problem in result.rejected],
        priority_counts=[
            PriorityCount(priority=name, tickets=count) for name, count in result.priority_counts
        ],
        resolution_by_category=[
            CategoryResolutionOut(
                category=row.category,
                tickets_with_time=row.tickets_with_time,
                mean_hours=row.mean_hours,
                median_hours=row.median_hours,
            )
            for row in result.resolution_by_category
        ],
        quality=[QualityMetric(metric=m, value=v) for m, v in result.quality],
    )


# --- endpoints ---------------------------------------------------------------

@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/analyse",
    responses={
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "model": ErrorResponse, "description": "File larger than 5 MB",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The file cannot be analysed (empty, header only, wrong columns, "
                           "malformed CSV), or the request has no 'file' field",
        },
    },
)
def analyse(file: Annotated[UploadFile, File(description="Ticket CSV, at most 5 MB")]) -> (
    AnalysisResponse
):
    """Analyse one uploaded ticket CSV.

    A plain ``def`` (not ``async``): FastAPI runs it in a worker thread, so the
    blocking file work in the service does not stall the event loop.
    """
    # Read at most one byte past the limit: enough to detect "too large"
    # without loading an arbitrarily large upload into memory.
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        result = analyse_upload(file.filename or "", data)
    except UploadError as exc:
        code = (status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if len(data) > MAX_UPLOAD_BYTES
                else status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(status_code=code, detail=exc.message) from exc
    return to_response(result)
