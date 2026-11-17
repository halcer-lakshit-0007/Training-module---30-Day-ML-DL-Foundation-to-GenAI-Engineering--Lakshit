"""
Streamlit UI for the ticket dashboard.

This file only handles the page: upload, session cache, and display. All
reading, validation, cleaning and calculation happens behind
``service.analyse_upload``. Run with:

    streamlit run src/ticket_dashboard/app.py
"""

from __future__ import annotations

import logging

import streamlit as st
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS

from ticket_dashboard.service import (
    DashboardResult,
    UploadError,
    analyse_upload,
    upload_cache_key,
)

logger = logging.getLogger("ticket_dashboard.app")

CACHE_KEY = "dashboard_result"  # session_state value: (cache key, DashboardResult)
UNEXPECTED_ERROR = "Something went wrong while processing the file. Check the logs."


def _result_for_upload(filename: str, data: bytes) -> DashboardResult:
    """Return the cached result for this upload, or analyse it once and cache it."""
    key = upload_cache_key(filename, data)
    cached: tuple[str, DashboardResult] | None = st.session_state.get(CACHE_KEY)
    if cached is not None and cached[0] == key:
        return cached[1]

    st.session_state.pop(CACHE_KEY, None)  # a new file replaces the old result
    try:
        result = analyse_upload(filename, data)
    except UploadError as exc:
        st.error(exc.message)
        st.stop()
    except Exception:
        logger.exception("Unexpected error while processing an uploaded file")
        st.error(UNEXPECTED_ERROR)
        st.stop()
    st.session_state[CACHE_KEY] = (key, result)
    return result


def _show_preview(result: DashboardResult) -> None:
    rows_col, columns_col = st.columns(2)
    rows_col.metric("Rows", result.rows_read)
    columns_col.metric("Columns", len(result.columns))
    st.caption(f"{result.rows_read} rows x {len(result.columns)} columns")
    st.subheader("Column types")
    st.dataframe(
        [{"Column": column, "Type": kind} for column, kind in result.column_types],
        hide_index=True,
    )
    st.subheader(f"First {len(result.preview)} rows")
    st.dataframe(list(result.preview), hide_index=True)


def _show_analytics(result: DashboardResult) -> None:
    if result.valid_count == 0:
        st.info("No valid tickets to analyse.")
        return
    st.subheader("Tickets by priority")
    st.dataframe(
        [{"Priority": name, "Tickets": count} for name, count in result.priority_counts],
        hide_index=True,
    )
    # st.bar_chart (1.39) sorts the x axis alphabetically; this spec keeps the
    # service's fixed order (urgent, high, medium, low) on every run.
    order = [name for name, _ in result.priority_counts]
    st.vega_lite_chart(
        {
            "data": {"values": [{"Priority": n, "Tickets": c} for n, c in result.priority_counts]},
            "mark": {"type": "bar"},
            "encoding": {
                "x": {"field": "Priority", "type": "nominal", "sort": order,
                      "axis": {"labelAngle": 0}},
                "y": {"field": "Tickets", "type": "quantitative", "axis": {"tickMinStep": 1}},
            },
        },
        use_container_width=True,
    )
    st.subheader("Resolution time by category")
    st.dataframe(
        [
            {
                "Category": row.category,
                "Tickets with time": row.tickets_with_time,
                "Mean hours": row.mean_hours,
                "Median hours": row.median_hours,
            }
            for row in result.resolution_by_category
        ],
        hide_index=True,
    )


def _show_quality(result: DashboardResult) -> None:
    st.dataframe(
        [{"Metric": metric, "Value": value} for metric, value in result.quality],
        hide_index=True,
    )
    if result.rejected:
        st.subheader("Rejected rows")
        st.dataframe(
            [{"Line": line, "Problem": problem} for line, problem in result.rejected],
            hide_index=True,
        )
    else:
        st.success("No rows were rejected.")


def main() -> None:
    st.set_page_config(page_title="Ticket Data Dashboard", layout="wide")
    st.title("Ticket Data Dashboard")

    with st.sidebar:
        st.write("Upload a support-ticket CSV to preview it, see analytics and check data quality.")
        st.markdown("**Required columns**")
        st.markdown("\n".join(f"- `{column}`" for column in REQUIRED_COLUMNS))
        st.markdown("Max file size: 5 MB")

    uploaded = st.file_uploader("Upload a ticket CSV", type=["csv"])
    if uploaded is None:
        st.session_state.pop(CACHE_KEY, None)  # removing the file clears the result
        st.info("Upload a ticket CSV to begin.")
        st.stop()

    result = _result_for_upload(uploaded.name, uploaded.getvalue())

    if result.rejected:
        st.warning(
            f"{len(result.rejected)} of {result.rows_read} rows were rejected. "
            "See the Data quality tab."
        )

    preview_tab, analytics_tab, quality_tab = st.tabs(["Preview", "Analytics", "Data quality"])
    with preview_tab:
        _show_preview(result)
    with analytics_tab:
        _show_analytics(result)
    with quality_tab:
        _show_quality(result)


main()
