"""UI tests for the Streamlit app, run headless with streamlit.testing.v1.AppTest.

AppTest in Streamlit 1.39.0 has no API for setting a file on
``st.file_uploader``, so only the no-upload state is tested here. Upload
behaviour is covered by tests/unit/test_service.py and the manual checklist
in docs/ui_test_checklist.md.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "ticket_dashboard" / "app.py"


def run_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=60).run()


def test_no_upload_shows_the_start_message_without_error() -> None:
    app = run_app()
    assert not app.exception
    assert app.title[0].value == "Ticket Data Dashboard"
    assert [info.value for info in app.info] == ["Upload a ticket CSV to begin."]
    assert not app.error
    assert len(app.tabs) == 0  # st.stop() ran before the tabs


def test_sidebar_lists_required_columns_and_size_limit() -> None:
    sidebar_text = " ".join(str(element.value) for element in run_app().sidebar.markdown)
    for column in ("id", "customer", "priority", "category", "status", "description",
                   "created_at"):
        assert f"`{column}`" in sidebar_text
    assert "Max file size: 5 MB" in sidebar_text
