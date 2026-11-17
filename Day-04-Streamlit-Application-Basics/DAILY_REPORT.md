# Daily Report — Day 04

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 04 — Streamlit & Application Basics |
| **Developer** | Lakshit (HALCER) |
| **Date** | 17 November 2026 |
| **Duration** | _[TO BE FILLED IN BY LAKSHIT]_ |
| **Status** | Implementation complete; manual UI checklist not yet run |
| **Test result** | 181 passed, 0 failed (`logs/test_results.txt`) |
| **Determinism** | 181 passed under `PYTHONHASHSEED` 0, 1 and 4242, in reverse order, and with each test alone in a fresh process (`logs/test_isolation.txt`) |
| **Static checks** | `ruff check src tests` clean; `mypy src` (strict, 6 files) clean (`logs/static_checks.txt`) |

---

## 1. Topics Learned

> _[TO BE COMPLETED BY LAKSHIT: study blocks and durations from the Day 04 brief.]_ The table lists only where each topic shows up in this project's code.

| Topic | Where it is applied in this project |
|---|---|
| Streamlit script model (the script re-runs top to bottom on every interaction) | `app.py`: `main()` runs on each rerun; `st.stop()` ends a run early for the empty and error states |
| Layout and widgets | `st.set_page_config(layout="wide")`, sidebar, `st.file_uploader(type=["csv"])`, `st.tabs`, `st.metric`, `st.columns`, `st.dataframe`, `st.bar_chart` |
| User feedback | `st.info` (no file, no valid tickets), `st.warning` (some rows rejected), `st.error` (upload failed), `st.success` (no rejections) |
| Session state | `st.session_state` caches `(sha256, DashboardResult)` so switching tabs does not re-run the pipeline |
| Validating uploaded files | `service.analyse_upload`: size checks, sanitised name, temporary directory, pipeline errors mapped to `UploadError` |
| Separating UI from logic | UI → service → `ticket_pipeline`; `service.py` imports neither Streamlit nor pandas (tested) |
| HTTP backend with FastAPI | `ticket_api/main.py`: `POST /analyse` (multipart upload), pydantic response models, `UploadError` mapped to 413/422 |
| Testing a Streamlit app | `streamlit.testing.v1.AppTest` for the no-upload state; service-level tests for uploads |

### 1.1 Key learnings

_[TO BE COMPLETED BY LAKSHIT]_

---

## 2. What I Can Explain Without Notes

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_

---

## 3. Implementation Completed

| Deliverable | Files | Status |
|---|---|---|
| Day 03 pipeline reused, not copied | Day 03's `ticket_pipeline` is installed from its own folder (`requirements.txt`: `-e ../Day-03-…`); pytest and mypy are pointed at `../Day-03-…/src`. Day 04 holds no copy of Day 03's package, tests or `tickets.csv` | Complete |
| Pure dashboard analytics | `src/ticket_dashboard/analytics.py`: `priority_counts`, `CategoryResolution`, `resolution_by_category` | Complete |
| Service layer | `src/ticket_dashboard/service.py`: `analyse_upload`, `DashboardResult`, `UploadError`, `infer_column_type`, `safe_file_name` | Complete |
| Streamlit UI | `src/ticket_dashboard/app.py`: sidebar, uploader, session cache, Preview / Analytics / Data quality tabs | Complete |
| Tests | `tests/unit/test_dashboard_analytics.py` (11), `tests/unit/test_service.py` (41), `tests/ui/test_app.py` (2), 5 fixture CSVs | Complete |
| FastAPI backend | `src/ticket_api/main.py`: `GET /health`, `POST /analyse`; `tests/api/test_api.py` (30 tests) | Complete |
| Determinism and edge cases | `tests/unit/test_determinism.py` (11), `tests/unit/test_edge_cases.py` (86), 12 more API tests; fixes in `service.py` (file names, type inference, cache key) and `app.py` (fixed chart order); `.gitattributes`; `logs/test_isolation.txt` | Complete |
| Manual UI checklist | `docs/ui_test_checklist.md` (15 cases) | Written; **not yet executed** |
| Packaging and docs | `pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md`, this report; Day 04 row in the root README | Complete |

---

## 4. Tests / Experiment Results

```
$ pytest -q
181 passed, 1 warning in 30.41s

$ ruff check src tests
All checks passed!

$ mypy src
Success: no issues found in 6 source files
```

| Check | Result | Evidence |
|---|---|---|
| Full Day 04 test suite | 181 passed, 0 failed; 1 DeprecationWarning from inside Starlette 0.38.6 | `logs/test_results.txt` |
| Static checks | ruff clean; mypy strict clean on 6 source files | `logs/static_checks.txt` |
| Suite under `PYTHONHASHSEED` = 0, 1, 4242 | 181 passed each time | `logs/test_isolation.txt` |
| Suite in reverse order (all 181 test ids reversed) | 181 passed | `logs/test_isolation.txt` |
| Each test alone in a fresh process | 181 passed, 0 failed | `logs/test_isolation.txt` |
| Day 03's `data/tickets.csv` through the service | rows 10 / valid 7 / rejected 3 (lines 4, 7, 9); priorities urgent 1, high 2, medium 2, low 2; resolution technical 6.25, billing 3.0, account 2.0, unknown 1.5; rejection rate 30.0%; 2 valid tickets without resolution time; overall average 3.8 h. All equal the expected values | `test_service.py::test_sample_dataset_*` |
| `streamlit run src/ticket_dashboard/app.py --server.headless true` for 15 s | Started, health endpoint returned `ok`, nothing on stderr, stopped | README §7.3 |
| `uvicorn ticket_api.main:app --port 8765` with real `curl.exe` uploads | `/health` ok; `tickets.csv` returned 200 with 10 / 7 / 3 rows and a 30.0% rejection rate; `empty.csv` and `missing_columns.csv` returned 422; `/docs` returned 200 | README §7.4 |
| AppTest and `st.file_uploader` | Streamlit 1.39.0 AppTest has no file-upload API (the uploader is an `UnknownElement`) | README §7.2 |
| Manual UI checklist | _[TO BE FILLED IN BY LAKSHIT after running `docs/ui_test_checklist.md`]_ | `docs/ui_test_checklist.md`, `screenshots/` |

Environment: Windows 11 (ARM64 hardware), Python 3.12.10 **x64** under emulation, streamlit 1.39.0, fastapi 0.115.0, uvicorn 0.31.0, pandas 2.3.3, pyarrow 26.0.1, pytest 8.3.3, mypy 2.4.1, ruff 0.17.5.

---

## 5. Bug or Challenge and Its Root Cause

### 5.1 Main challenge — `streamlit==1.39.0` would not install

**Symptom:** `pip install -e ".[dev]"` failed while building pandas from source: `ERROR: Could not find C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe`.

**Root cause:** the machine is Windows on ARM64 and the installed Python was the ARM64 build (`cp312-win_arm64`). Streamlit 1.39.0 requires `pandas<3` and `pyarrow`. On PyPI, only pandas 3.x has Windows ARM64 wheels, and pyarrow has none. So pip fell back to compiling pandas 2.x, which needs Visual Studio build tools.

**Fix:** installed the official python.org **x64** Python 3.12.10 alongside the ARM64 one (per-user, not added to PATH) and created the virtual environment with it. pip then selected `win_amd64` wheels and the install succeeded. Documented in README §5 and §11.

### 5.2 Other problems found and fixed

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | `test_unreadable_file_gives_a_generic_message` failed with `PermissionError` inside the test itself | The test patched `Path.open` to refuse reads *before* reading the sample file it needed | Read the sample bytes first, then patch |
| 2 | Checklist case UI-10 first relied on INFO log lines to prove the pipeline did not re-run | `ticket_pipeline` configures no handler outside its CLI, so Python prints only WARNING and above | The case now watches the `stage=parse status=rejected` WARNING lines instead |
| 3 | First draft of the large-file recipe (60,000 rows) made a file under 5 MB | Row size × count was below 5,242,880 bytes | Changed to 70,000 rows (5,320,850 bytes, measured) |
| 4 | First live API check returned `404 Not Found` for `/health` | Another program on the machine was already listening on port 8000, so uvicorn could not bind (`WinError 10048`) and the requests reached that program | Re-ran on port 8765 after checking it was free; README §6.1 shows the `--port` option |
| 5 | A 300-character file name crashed the upload with `FileNotFoundError`; the UI showed "Something went wrong" and the API a 500 | The sanitised name was not length-limited, so the temporary path passed the Windows 260-character limit | Names are cut to 100 characters; Windows device names (`CON`, `NUL`, …) get a `_` prefix; tested for idempotence |
| 6 | Type inference called Arabic-Indic digits `integer`/`date`, `2024-02-30` a `date`, and `1e3` `text` | Python's `\d` matches every Unicode digit; the date rule checked only the pattern; the decimal pattern had no exponent | ASCII-only `[0-9]`; real calendar check with `date.fromisoformat`; exponent allowed, non-finite values excluded |
| 7 | The same bytes uploaded under another name reused the cached result | The session cache key was only the SHA-256 of the bytes | Key is now file name + SHA-256 (`upload_cache_key`, tested) |
| 8 | `st.bar_chart` could show priorities alphabetically | Streamlit 1.39's `bar_chart` has no sort option | Vega-Lite spec with an explicit `sort` in the service's order |
| 9 | Two new line-ending tests failed on this machine | Git (`core.autocrlf=true`) had checked `tickets.csv` out with CRLF (850 bytes instead of the committed 839) | Tests normalise line endings before converting; `.gitattributes` keeps Day 04's fixture CSVs LF |
| 10 | Day 04 first contained a full copy of Day 03 (package, 127 tests, `tickets.csv`) | The brief asked to copy the package; the copy duplicated logic that already exists in the repository | Copies removed. Day 04 installs `ticket_pipeline` from the Day 03 folder and reads Day 03's `tickets.csv` via `DEFAULT_INPUT_PATH`; the dashboard analytics moved to `ticket_dashboard/analytics.py` |
| 11 | Code review listed three blocking defects (B1 non-finite numbers reach the mean, B2 extra CSV fields shift columns, B3 duplicate headers renamed by pandas) | The review was of a pandas-based dashboard; each case was reproduced here before changing anything | None of the three occurs: the Day 03 loader rejects non-finite numbers per row, refuses rows wider than the header, and checks the raw header for duplicates. 27 regression tests added (24 service, 3 API) with the reviewer's exact inputs; README §7.5 |

---

## 6. Design Decision and Why

**Decision:** put a service layer between Streamlit and the pipeline. The UI only displays an immutable `DashboardResult` or an `UploadError` message.

- The service is plain Python, so every upload case is unit-tested even though AppTest cannot upload a file.
- The pipeline is used from Day 03's folder, not copied, so the dashboard and the Day 03 CLI run the very same code and always agree on what a valid ticket is.
- Expected failures become one user-safe message. Unexpected ones are logged and shown as a generic error, never as a traceback.
- Uploaded bytes go to a sanitised file name in a `TemporaryDirectory`, which is deleted before the function returns, so no upload stays on disk and no local path reaches the user.
- The result is cached in `st.session_state` under the file name plus the SHA-256 of the bytes. Streamlit re-runs the script on every click, but the pipeline runs once per distinct file.

**Alternative considered:** reading the upload straight into pandas inside `app.py`. Rejected, because it would duplicate the Day 03 validation rules in a second place and make them testable only through the UI.

---

## 7. Blocker and What I Tried

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_

---

## 8. Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
|---|---|---|
| UI contains no data logic | Met | `app.py`; README §3 |
| Day 03 logic reused from its own folder, not copied | Met | `requirements.txt`; `pyproject.toml` (`pythonpath`, `mypy_path`) |
| Service independent of Streamlit and pandas | Met | `test_service_imports_neither_streamlit_nor_pandas` |
| Uploads validated with exact, safe messages | Met | `test_service.py`; README §9 |
| Session state prevents reprocessing | Implemented; manual check pending | `app.py::_result_for_upload`; `test_cache_key_*`; checklist UI-10 to UI-12, UI-14 |
| Results are deterministic | Met | `tests/unit/test_determinism.py`; `logs/test_isolation.txt` |
| Edge cases fail safely | Met | `tests/unit/test_edge_cases.py`; README §7.5 |
| Sample-data analytics match the expected values | Met | `test_service.py::test_sample_dataset_*` |
| App starts without error | Met | README §7.3 |
| Same analysis available over HTTP (FastAPI) | Met | `tests/api/test_api.py`; README §7.4 |
| Manual UI checklist passed | **Pending** | `docs/ui_test_checklist.md` |

**Submission checklist:**
- Source code committed to Git with a meaningful commit message — _not yet committed_
- Actual test and static-check output saved in `logs/` ✔
- README with setup, run, test, assumptions and limitations ✔
- Manual UI checklist executed and screenshots saved — _pending_

---

## 9. Tomorrow's Plan

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_
