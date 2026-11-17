# Ticket Data Dashboard — Streamlit & Application Basics (+ FastAPI backend)

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 04 — Streamlit & Application Basics |
| **Author** | Lakshit (HALCER) |
| **Date** | 17 November 2026 |
| **Status** | Implementation complete; manual UI checklist pending |
| **Test result** | 154 passed, 0 failed — [`logs/test_results.txt`](logs/test_results.txt) |
| **Determinism** | Same results under 3 hash seeds, in reverse order and with each test alone — [`logs/test_isolation.txt`](logs/test_isolation.txt) |
| **Static checks** | `ruff` clean · `mypy --strict` clean — [`logs/static_checks.txt`](logs/static_checks.txt) |

---

## Contents

1. [Purpose](#1-purpose)
2. [Acceptance Criteria Mapping](#2-acceptance-criteria-mapping)
3. [Architecture](#3-architecture)
4. [Project Structure](#4-project-structure)
5. [Setup](#5-setup)
6. [Run](#6-run)
7. [Test](#7-test)
8. [Data Contract](#8-data-contract)
9. [Error Messages](#9-error-messages)
10. [Assumptions](#10-assumptions)
11. [Limitations](#11-limitations)

---

## 1. Purpose

A small Streamlit web app for checking a support-ticket CSV before anyone relies on it. A user uploads a file and gets three views:

- **Preview** — size, inferred column types and the first 10 raw rows;
- **Analytics** — tickets per priority (table and bar chart) and resolution time per category (mean and median);
- **Data quality** — counts, rejection rate, rejections per column and every rejected row with its line number and problem.

The same analysis is also available as a **FastAPI backend** (`POST /analyse`), so other programs can check a file over HTTP and get the result as JSON.

All reading, validation and cleaning is done by the Day 03 `ticket_pipeline` package. Day 04 **uses it from its own folder** (`../Day-03-Python-Engineering-Practices-Exceptions-Testing/`); it is installed from there, not copied, so there is one copy of the logic in the repository. Day 04 adds a thin **service layer**, two front ends on top of it (the Streamlit **UI** and the **API**), and one pure analytics module.

---

## 2. Acceptance Criteria Mapping

The criteria below are taken from the Day 04 build instructions (see Assumption 1).

| # | Criterion | How it is met | Proof |
|---|---|---|---|
| 1 | The UI contains no data logic | `app.py` only uploads, caches and displays. It calls `service.analyse_upload` once per new file and has no CSV parsing, validation, cleaning or calculation | `src/ticket_dashboard/app.py`; §3 |
| 2 | Reading, validation and cleaning are reused, not re-implemented or copied | `service.py` calls Day 03's `CSVLoader(...).load()` and `run_pipeline(...)`. `ticket_pipeline` is installed from the Day 03 folder (`requirements.txt`: `-e ../Day-03-…`); Day 04 contains no copy of it, of its tests or of its data | `src/ticket_dashboard/service.py`; `requirements.txt`; Day 03's own tests stay in Day 03 |
| 3 | The service layer is independent of the UI framework | `service.py` imports neither Streamlit nor pandas | `test_service.py::test_service_imports_neither_streamlit_nor_pandas` |
| 4 | Uploads are validated, with one clear message per problem | Empty, over 5 MB, header only, missing columns, malformed CSV and unreadable file each give a fixed `UploadError` message (§9) | `test_service.py::test_bad_files_raise_upload_error_with_exact_message`, `test_file_over_5_mb_is_rejected_before_it_is_written`, `test_unreadable_file_gives_a_generic_message` |
| 5 | An empty file is handled safely | Rejected before anything is written to disk, with a message that says what to upload instead | `test_service.py::test_bad_files_raise_upload_error_with_exact_message[empty]`; checklist UI-03 |
| 6 | Uploaded files are handled safely | Written under a sanitised name into a `TemporaryDirectory` that is deleted before `analyse_upload` returns or raises. No message contains the temporary path | `test_temp_directory_is_deleted_after_success`, `test_temp_directory_is_deleted_after_an_error`, `test_error_messages_never_contain_the_temp_directory`, `test_unsafe_filename_is_made_safe`, `test_safe_file_name`, `test_edge_cases.py::test_awkward_file_names_never_crash` |
| 7 | Session state avoids reprocessing | The result is cached in `st.session_state` under `upload_cache_key`: the file name plus the SHA-256 of the bytes. Switching tabs reuses it; a new file replaces it; removing the file clears it | `app.py::_result_for_upload`; `test_determinism.py::test_cache_key_*`; checklist UI-10 to UI-12, UI-14 |
| 8 | Analytics are correct on the sample data | Exact §5 values asserted: 10 / 7 / 3 rows; priorities 1/2/2/2; resolution by category; 30.0 % rejection rate; overall average 3.8 h | `test_service.py::test_sample_dataset_*` |
| 9 | New analytics are pure and tested | `ticket_dashboard/analytics.py` has no I/O and no logging; tests cover zero counts and fixed order, sorting and tie-break, rounding, omitted categories and that the input is not changed | `tests/unit/test_dashboard_analytics.py` |
| 10 | Unexpected errors never show a traceback | `UploadError` → `st.error(message)`; any other exception → a generic `st.error`, `logger.exception` to the server log, `st.stop()` | `app.py::_result_for_upload` |
| 11 | The app starts | `streamlit run src/ticket_dashboard/app.py --server.headless true` ran for 15 s with no error and answered its health check | §7.3 |
| 12 | The no-upload state works | AppTest runs the real script headless | `tests/ui/test_app.py` |
| 13 | The same analysis is available over HTTP | FastAPI `POST /analyse` calls the same `analyse_upload` and returns its result as JSON: 200 on success, 413 if too large, 422 for an invalid file. A bug gives a plain 500 with no traceback. The API imports neither Streamlit nor `ticket_pipeline` | `tests/api/test_api.py` (27 tests, real multipart uploads); live `uvicorn` check in §7.4 |
| 14 | Results are deterministic | The same upload gives the same result regardless of repetition, row order, hash seed, working directory, temp directory, threads or Git line-ending settings. The bar chart always uses the fixed priority order | `tests/unit/test_determinism.py`; `logs/test_isolation.txt`; `.gitattributes` |
| 15 | Edge cases fail safely | Every awkward input either gives a result or an exact `UploadError` message, never an unexpected exception: encodings, line endings, headers, rows, file names, type inference | `tests/unit/test_edge_cases.py` (62 tests); README §7.5 |

---

## 3. Architecture

```
 Browser                                 HTTP client (curl, another service)
    │  file name + bytes                       │  multipart POST /analyse
    ▼                                          ▼
 ┌──────────────────────────────────┐  ┌──────────────────────────────────┐
 │ UI — ticket_dashboard/app.py     │  │ API — ticket_api/main.py         │
 │ (Streamlit) upload, session      │  │ (FastAPI) JSON models,           │
 │ cache, tabs, messages            │  │ UploadError -> 413 / 422         │
 └────────────────┬─────────────────┘  └────────────────┬─────────────────┘
                  └──────────────┬──────────────────────┘
                                 │ analyse_upload(filename, data) -> DashboardResult | UploadError
                                 ▼
 ┌────────────────────────────────────────────┐
 │ Service — ticket_dashboard/service.py      │  size checks, safe temp file, error mapping,
 │ (no streamlit, no pandas)                  │  builds one immutable DashboardResult
 └────────────────────┬───────────────────────┘
                      │ CSVLoader, run_pipeline, priority_counts, resolution_by_category
                      ▼
 ┌────────────────────────────────────────────┐
 │ ticket_dashboard/analytics.py (Day 04)     │  priority counts, resolution by category (pure)
 └────────────────────┬───────────────────────┘
                      │ works on Day 03's Ticket objects
                      ▼
 ┌────────────────────────────────────────────┐
 │ ticket_pipeline — lives in Day 03's folder │  read → validate → clean → summarise
 │ (installed from there, not copied)         │
 └────────────────────────────────────────────┘
```

**Why the UI holds no logic**

- **Testable without a browser.** Streamlit re-runs the whole script on every click, and AppTest cannot even simulate an upload in 1.39.0. With all the logic in `service.py`, 41 fast unit tests cover every upload case without starting a UI.
- **One source of truth.** The CLI (Day 03) and the dashboard (Day 04) use the same loader, parser and rules, so a file gets the same verdict wherever it is checked.
- **Replaceable UI.** `DashboardResult` contains plain Python values only. The FastAPI backend proves this: it is a second front end on the same service, with no change to `service.py`. Its only jobs are HTTP concerns: JSON models, status codes, and reading at most 5 MB + 1 byte of the upload.
- **Clear error boundary.** The service turns every *expected* failure into `UploadError` with a safe message. Anything else is a bug. The UI logs it and shows a generic message, never a traceback.

**`DashboardResult` fields:** `source_name`, `columns`, `column_types`, `rows_read`, `preview` (first 10 raw rows), `valid_count`, `rejected` (line, problem), `priority_counts`, `resolution_by_category`, `quality` (metric, value).

---

## 4. Project Structure

```
Day-04-Streamlit-Application-Basics/
├── pyproject.toml                  Package metadata; ruff, mypy (strict) and pytest settings
├── .gitattributes                  *.csv always LF, so test data has identical bytes on every OS
├── requirements.txt                Day 03 package (-e ../Day-03-…) + pinned Streamlit, FastAPI, uvicorn, …
├── src/
│   ├── ticket_dashboard/
│   │   ├── analytics.py            priority_counts, resolution_by_category (pure)
│   │   ├── service.py              analyse_upload, DashboardResult, UploadError
│   │   └── app.py                  Streamlit UI only
│   └── ticket_api/
│       └── main.py                 FastAPI app: GET /health, POST /analyse
├── tests/
│   ├── unit/test_dashboard_analytics.py   11 tests
│   ├── unit/test_service.py               41 tests
│   ├── unit/test_edge_cases.py            62 tests
│   ├── unit/test_determinism.py           11 tests
│   ├── ui/test_app.py                     2 AppTest tests
│   ├── api/test_api.py                    27 FastAPI TestClient tests
│   └── fixtures/                   empty, header-only, missing-columns, malformed-quote, all-rows-invalid CSVs
├── docs/ui_test_checklist.md       Manual UI test cases (to be filled in)
├── logs/                           test_results.txt, static_checks.txt, test_isolation.txt (real output)
└── screenshots/                    For screenshots from the manual checklist
```

**Nothing from Day 01–03 is copied into this folder.** The pipeline package, its tests and the sample data `tickets.csv` stay in `../Day-03-Python-Engineering-Practices-Exceptions-Testing/`. Day 04 imports the package (installed from that folder) and reads the sample data from there via `ticket_pipeline.config.DEFAULT_INPUT_PATH`.

---

## 5. Setup

**Prerequisites:** Python 3.11 or later and Git. Verified with Python 3.12.10 (x64) on Windows 11.

> **Windows on ARM (e.g. Snapdragon laptops):** `streamlit==1.39.0` requires `pandas<3` and `pyarrow`, which have **no Windows ARM64 wheels**, so installation fails with a native ARM64 Python (pip tries to compile pandas and stops with `Could not find ... vswhere.exe`). Install the **x64** build of Python from python.org and create the virtual environment with it. It runs under Windows' built-in x64 emulation. This is how this project was verified.

Day 04 needs the Day 03 folder next to it (it is in the same repository). From the repository root:

**Windows PowerShell**

```powershell
cd Day-04-Streamlit-Application-Basics
py -3.12 -m venv .venv          # on Windows ARM64: & "<path to x64 python>\python.exe" -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
```

**Git Bash (Windows)**

```bash
cd Day-04-Streamlit-Application-Basics
py -3.12 -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
```

**macOS / Linux**

```bash
cd Day-04-Streamlit-Application-Basics
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
```

`requirements.txt` first installs Day 03's `ticket_pipeline` **from its own folder** in editable mode (`-e ../Day-03-Python-Engineering-Practices-Exceptions-Testing`; run pip from the Day 04 folder so this relative path resolves), then pins the exact versions of Streamlit, FastAPI, uvicorn, python-multipart (needed by FastAPI for file uploads), httpx (needed by FastAPI's `TestClient`) and pytest. `-e ".[dev]"` installs Day 04's own packages (`ticket_dashboard`, `ticket_api`) in editable mode, plus pytest-cov, mypy, ruff and httpx.

`ticket-pipeline` is deliberately **not** listed in `pyproject.toml` dependencies: pip cannot express a relative folder there, and a plain name could make pip fetch an unrelated package of the same name from PyPI. pytest (`pythonpath`) and mypy (`mypy_path`) are also pointed at `../Day-03-Python-Engineering-Practices-Exceptions-Testing/src`, so tests and type checks use Day 03's source even without the install.

Versions used for the saved logs: streamlit 1.39.0, fastapi 0.115.0 (starlette 0.38.6, pydantic 2.14.3), uvicorn 0.31.0, python-multipart 0.0.12, httpx 0.27.2, pandas 2.3.3, pyarrow 26.0.1, pytest 8.3.3, pytest-cov 7.1.0, mypy 2.4.1, ruff 0.17.5.

---

## 6. Run

With the virtual environment active, from `Day-04-Streamlit-Application-Basics/`:

```bash
streamlit run src/ticket_dashboard/app.py
```

Open http://localhost:8501, then upload Day 03's sample file `../Day-03-Python-Engineering-Practices-Exceptions-Testing/data/tickets.csv` or one of the files in `tests/fixtures/`. Stop the server with `Ctrl+C`.

Add `--server.headless true` to start without opening a browser. Add `--browser.gatherUsageStats false` to turn off Streamlit's usage statistics.

### 6.1 FastAPI backend

```bash
uvicorn ticket_api.main:app --reload            # http://127.0.0.1:8000
uvicorn ticket_api.main:app --port 8765         # if port 8000 is already in use
```

Interactive documentation (try uploads in the browser): http://127.0.0.1:8000/docs. OpenAPI schema: `/openapi.json`.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | — | `200 {"status": "ok"}` |
| POST | `/analyse` | `multipart/form-data`, field `file` = the CSV | `200` JSON with `source_name`, `columns`, `column_types[{column,type}]`, `rows_read`, `preview[{…}]`, `valid_count`, `rejected[{line,problem}]`, `priority_counts[{priority,tickets}]`, `resolution_by_category[{category,tickets_with_time,mean_hours,median_hours}]`, `quality[{metric,value}]` |

```bash
curl -F "file=@../Day-03-Python-Engineering-Practices-Exceptions-Testing/data/tickets.csv" http://127.0.0.1:8000/analyse
curl -F "file=@tests/fixtures/empty.csv" http://127.0.0.1:8000/analyse
# -> 422 {"detail":"The uploaded file is empty. Choose a CSV file that has a header row and at least one ticket."}
```

In PowerShell, use `curl.exe` (plain `curl` is an alias for `Invoke-WebRequest`).

| Status | When | Body |
|---|---|---|
| 200 | File analysed, even if every row was rejected | Analysis JSON |
| 413 | File larger than 5 MB | `{"detail": "The file is larger than 5 MB. Upload a smaller CSV."}` |
| 422 | Empty, header only, missing columns, malformed CSV, unreadable: the exact §9 message | `{"detail": "<message>"}` |
| 422 | No `file` field in the request (FastAPI validation) | `{"detail": [{"loc": ["body", "file"], …}]}` |
| 500 | Unexpected error (a bug) | `Internal Server Error`. The traceback goes to the uvicorn log only |

The Streamlit app does **not** call the API. Both are independent front ends on the same service layer, so each can run without the other.

---

## 7. Test

```bash
pytest -q                    # all 154 Day 04 tests
pytest tests/unit            # unit tests, including service and dashboard analytics
pytest tests/ui              # Streamlit AppTest (no-upload state)
pytest tests/api             # FastAPI endpoints with real multipart uploads
ruff check src tests
mypy src
```

### 7.1 Test inventory

| File | Tests | Covers |
|---|---|---|
| `unit/test_dashboard_analytics.py` | 11 | Fixed priority order with zero counts; sort by mean descending; tie-break by category; rounding to 2 decimals; mean vs median; tickets without time ignored and empty categories omitted; zero hours counted; input not changed; generators accepted |
| `unit/test_service.py` | 41 | Exact message for each `UploadError` (empty, over 5 MB, header only, missing columns, malformed quote, unreadable); exactly 5 MB accepted; all-rows-invalid file returns `valid_count` 0; every §5 value on Day 03's `data/tickets.csv`; preview limit; temp directory deleted after success and after errors; no temp path in messages; unsafe file names; `infer_column_type` rules; no Streamlit or pandas import in `service.py` |
| `ui/test_app.py` | 2 | AppTest: the no-upload state shows the title and "Upload a ticket CSV to begin." with no exception or error and no tabs; the sidebar lists the required columns and the 5 MB limit |
| `unit/test_edge_cases.py` | 62 | See §7.5 |
| `unit/test_determinism.py` | 11 | Repeated calls identical; fixed-permutation and reversed row order give the same analytics; independent of working directory, temp directory and file name (except `source_name`); 16 concurrent calls in 8 threads do not interfere; identical `repr` of the result in fresh interpreters with `PYTHONHASHSEED` 0, 1 and 4242; cache key fixed and sensitive to both name and content |
| `api/test_api.py` | 27 | `/health`; OpenAPI lists both endpoints; Day 03's `tickets.csv` over HTTP with every expected value; all-rows-invalid is a 200; the JSON equals the service result 1:1; 422 with the exact message for empty, header-only, missing-columns and malformed files; 413 over 5 MB; 422 when the `file` field is missing; unsafe file name made safe; no temp files left; a simulated bug gives a 500 without traceback or internals; identical requests give byte-identical responses; 300-character, Windows-device and Windows-path file names; content type ignored; wrong field, text instead of file, JSON body and missing file name all give 422; with two `file` parts the last one is used (pinned); `GET /analyse` gives 405; exactly 5 MB is not "too large"; `main.py` imports neither Streamlit nor `ticket_pipeline` |
| **Total** | **154** | **154 passed, 0 failed** (`logs/test_results.txt`) |

Day 03's own 127 tests are not duplicated here; they stay in, and run from, the Day 03 folder.

The API tests use Starlette's in-process `TestClient`, which sends real multipart requests to the app without opening a socket. The run shows one `DeprecationWarning` from inside Starlette 0.38.6 (`anyio.abc.BlockingPortal`), caused by the newer anyio it was installed with. It is not from this project's code and does not affect results.

Tests use no network, no real clock (fixed `datetime`) and no random values. Temporary files are redirected into pytest's `tmp_path` by setting `tempfile.tempdir`, so each test can check that its upload was deleted.

### 7.2 Upload cases and AppTest

`streamlit.testing.v1.AppTest` in 1.39.0 has **no API to set a file on `st.file_uploader`**: the element appears in the tree as an `UnknownElement` with no value setter. Faking an upload would test the fake, not the app. So:

- every upload outcome is tested at the service boundary in `tests/unit/test_service.py`;
- what the user sees for each case (messages, tabs, caching, replacing and removing a file) is in the manual checklist [`docs/ui_test_checklist.md`](docs/ui_test_checklist.md).

### 7.3 Start-up check

`streamlit run src/ticket_dashboard/app.py --server.headless true` was run for 15 seconds. The server printed its URLs, answered `GET /_stcore/health` with `ok`, wrote nothing to stderr, and was then stopped.

### 7.4 API live check

`uvicorn ticket_api.main:app --port 8765` was started (port 8000 was taken by another program on the test machine), sent real requests with `curl.exe`, then stopped:

| Request | Result |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `POST /analyse` with Day 03's `tickets.csv` | 200; rows 10, valid 7, rejected 3; urgent 1, high 2, medium 2, low 2; rejection rate 30.0% |
| `POST /analyse` with `tests/fixtures/empty.csv` | 422 with the empty-file message |
| `POST /analyse` with `tests/fixtures/missing_columns.csv` | 422 |
| `GET /docs` | 200 |

The uvicorn log showed only start-up lines and the pipeline's three `stage=parse status=rejected` warnings. No errors.

---

### 7.5 Determinism and edge cases

**What could make results differ, and what prevents it**

| Possible source of variation | Prevention | Proof |
|---|---|---|
| Set or dict ordering (hash seed) | Every output list is either in a fixed order (priorities) or explicitly sorted (categories by mean then name; rejected columns by name; missing columns by name) | `test_result_does_not_depend_on_the_hash_seed` (3 seeds, fresh interpreters); full suite under 3 seeds (`logs/test_isolation.txt`) |
| Row order in the file | Counts and statistics do not depend on order. Means use `statistics.fmean` (exactly rounded, so the same for any order) | `test_row_order_does_not_change_the_analytics` |
| Git line endings (`core.autocrlf`) | Day 04's `.gitattributes` checks its fixture CSVs out with LF. Day 03's `tickets.csv` may be checked out with CRLF on Windows, and the loader treats LF, CRLF and CR alike | `test_line_endings_do_not_change_the_result` |
| Working or temporary directory | Paths come from `__file__`; the temp path never reaches the result or a message | `test_result_does_not_depend_on_the_working_directory`, `..._temp_directory` |
| Parallel requests | Each call has its own `TemporaryDirectory` | `test_concurrent_uploads_do_not_interfere` |
| Unicode digits, locale | Type inference accepts ASCII digits only (`[0-9]`, not `\d`) | `test_infer_column_type_edge_cases` |
| Chart axis order | `st.bar_chart` in 1.39 sorts alphabetically, so the app uses a Vega-Lite spec with an explicit `sort` | `app.py::_show_analytics`; checklist UI-02 |
| Cached result for the wrong file | The cache key includes the file name as well as the content hash | `test_cache_key_changes_with_content_or_name`; checklist UI-14 |
| Test order or test interaction | No shared state: per-test `tmp_path`, `monkeypatch`, fixed dates, no network, no random values | Reverse-order run and each test alone in a fresh process (`logs/test_isolation.txt`) |
| Slow machine (e.g. x64 emulation) | AppTest timeout raised from 30 s to 60 s | `tests/ui/test_app.py` |

**Edge cases found and fixed**

| Input | Before | Now |
|---|---|---|
| File name of 300 characters | Uncaught `FileNotFoundError` (Windows path limit). The UI showed "Something went wrong"; the API returned 500 | Name cut to 100 characters (`MAX_NAME_LENGTH`), analysed normally |
| `CON.csv`, `nul`, `COM1.csv`, … | Worked on Windows 11 only by luck (older Windows refuses device names) | Prefixed with `_` (`_CON.csv`) on every OS |
| `tickets.CSV` | Kept as `tickets.CSV` | Normalised to `tickets.csv`. Applying `safe_file_name` again never changes the name (tested) |
| Arabic-Indic or full-width digits | Shown as `integer` / `date` (Python's `\d` matches them) | `text` |
| `2024-02-30`, `2024-13-01` | Shown as `date` | `text`; only real calendar dates are `date` |
| `1e3`, `2.5E-1` | Shown as `text`, although the pipeline reads them as numbers | `decimal`; `1e400`, `inf`, `nan` stay `text` |
| Same bytes uploaded under a different name | Reused the cached result with the old name | New key, new result |
| Priority bar chart | Possibly alphabetical (high, low, medium, urgent) | Always urgent, high, medium, low |

**Edge cases already handled, now pinned by tests** (`tests/unit/test_edge_cases.py`): UTF-8 BOM; CRLF and CR-only line endings; latin-1, UTF-16 and binary (PNG) content; NUL bytes; a file that is only a newline or only spaces; a header with no final newline; a header followed by blank lines only; duplicate headers after normalising; upper-case and padded header names; extra columns; rows with too many or too few fields; a field over the CSV limit; blank lines between rows; multi-line quoted values; case-insensitive duplicate IDs; unknown categories; valid tickets without resolution times; rejection-rate rounding (0.0 %, 33.3 %, 66.7 %, 12.5 %, 100.0 %); path traversal and Windows paths in file names.

## 8. Data Contract

The ticket columns, value rules and normalisation are unchanged from Day 03. See [Day 03 README §7 — Ticket Data Contract](../Day-03-Python-Engineering-Practices-Exceptions-Testing/README.md#7-ticket-data-contract).

Required columns: `id`, `customer`, `priority`, `category`, `status`, `description`, `created_at`. Optional: `resolution_time_hours`, `customer_rating`. Extra columns are allowed. The upload itself must be a non-empty `.csv` file of at most 5 MB (5 × 1024 × 1024 bytes), UTF-8 encoded.

**Inferred column types** (Preview tab, display only), using non-empty, trimmed values:

| Type | Rule |
|---|---|
| `empty` | No non-empty values |
| `integer` | Every value is an ASCII whole number (`-3`, `42`, `007`) |
| `decimal` | Every value is a finite ASCII number (`2`, `4.5`, `.5`, `1e3`) |
| `date` | Every value is a real calendar date written `YYYY-MM-DD` (`2024-02-29` yes, `2024-02-30` no) |
| `text` | Anything else (including `nan`, `inf`, `1e400`, `1_000` and non-ASCII digits) |

**Dashboard analytics** (in addition to Day 03's [§8 analytics contract](../Day-03-Python-Engineering-Practices-Exceptions-Testing/README.md#8-analytics-contract)):

| Output | Definition | Day 03's `data/tickets.csv` |
|---|---|---|
| Priority counts | Valid tickets per priority, always in the order urgent, high, medium, low, zeros included | urgent 1, high 2, medium 2, low 2 |
| Resolution by category | Per category: tickets with a recorded time, mean and median hours (2 decimals). Sorted by mean descending, then name. Categories with no recorded times are omitted | technical 2 / 6.25 / 6.25; billing 1 / 3.0 / 3.0; account 1 / 2.0 / 2.0; unknown 1 / 1.5 / 1.5 |
| Rejection rate | Rejected rows ÷ rows read, one decimal | 30.0% |
| Rejections by column | Number of rejected rows naming each column, sorted by column | category: 1, customer: 2, description: 1 |
| Valid tickets without resolution time | Valid tickets with an empty `resolution_time_hours` | 2 |

---

## 9. Error Messages

The API returns the same messages as `{"detail": …}`. Its HTTP status codes are listed in §6.1.

| Situation | Where detected | Message shown (`st.error`) |
|---|---|---|
| No file selected | UI | *(info, not error)* "Upload a ticket CSV to begin." |
| File is 0 bytes | Service, before writing | "The uploaded file is empty. Choose a CSV file that has a header row and at least one ticket." |
| File over 5 MB | Service, before writing | "The file is larger than 5 MB. Upload a smaller CSV." |
| Header row only | Service, after the pipeline | "header_only.csv has a header row but no data rows. Add at least one ticket." |
| Required columns missing (`SchemaMismatchError`) | `CSVLoader` | "missing_columns.csv is missing required column(s): category, created_at, customer, description, status. Found columns: id, priority. Add the missing column(s) to the header row." |
| Malformed CSV (`MalformedFileError`: unbalanced quote, not UTF-8, blank or duplicate header names, extra fields, NUL bytes) | `CSVLoader` | e.g. "CSV could not be parsed (unexpected end of data) (malformed_quote.csv, line 2). Check for an unbalanced or stray double quote, or binary content." |
| File cannot be read (`InputPathError`) | `CSVLoader` | "The file could not be read. Upload it again." *(the pipeline's own message contains a path, so it is replaced)* |
| Some rows invalid | Pipeline (per row) | *(warning, not error)* "3 of 10 rows were rejected. See the Data quality tab." |
| Every row invalid | Pipeline | Warning as above; Analytics tab shows "No valid tickets to analyse." |
| Any other exception (a bug) | UI | "Something went wrong while processing the file. Check the logs." The traceback goes to the server log via `logger.exception`, never to the page |

File names in messages are the **sanitised** name (§10, Assumption 4). Messages never contain the temporary directory or any local path.

---

## 10. Assumptions

| # | Assumption |
|---|---|
| 1 | The Day 04 brief was not available when this was built. The acceptance criteria in §2 come from the Day 04 build instructions, and `DAILY_REPORT.md` follows the section structure of Day 03's report. |
| 2 | In `DashboardResult.rejected`, the message is the row's issues joined with "; ", **without** the `line N:` prefix that `InvalidRowError` adds, because the line has its own column in the table. |
| 3 | Column types are inferred from **all** rows, not only the 10 preview rows, using raw (uncleaned) values. The preview also shows raw values (e.g. ` 2024-01-15` keeps its leading space), so the user sees exactly what was uploaded. |
| 4 | The sanitised file name is used everywhere, including messages: `../my tickets?.csv` → `my_tickets_.csv`. Rules in order: base name only; characters outside `[A-Za-z0-9._-]` → `_`; a final `.csv` (any case) removed; cut to 96 characters; Windows device names (`CON`, `NUL`, `COM1`…) prefixed with `_`; `.csv` added. A name with nothing left becomes `upload.csv`. So `report.txt` → `report.txt.csv` and `tickets.CSV` → `tickets.csv`. |
| 5 | "Rejections by column" shows `none` when no row was rejected. A rejected row that names a column twice is impossible (the parser reports each column once), so the count is the number of rejected rows per column. Duplicate-ID rejections count under `id`. |
| 6 | `pyproject.toml` keeps Day 03's tool settings (ruff, mypy strict, pytest, coverage) but not its package or console script: those belong to Day 03, which Day 04 uses from its own folder. |
| 7 | `requirements.txt` installs the Day 03 package from its folder and pins the runtime packages and pytest. ruff, mypy and pytest-cov come from the `dev` extra. |
| 8 | An unexpected exception is logged through the `ticket_dashboard.app` logger. No handler is configured, so Python prints it to the terminal running Streamlit. |

---

## 11. Limitations

| # | Limitation | Impact / mitigation |
|---|---|---|
| 1 | AppTest (1.39.0) cannot drive `st.file_uploader` | Upload behaviour is tested at the service layer and by the manual checklist, not end-to-end in automated tests |
| 2 | `streamlit==1.39.0` does not install on Windows ARM64 Python | Use an x64 Python (§5) |
| 3 | Streamlit's own upload limit (200 MB by default) is higher than the 5 MB rule | A 5–200 MB file is uploaded into memory before the service rejects it. Setting `server.maxUploadSize` in `.streamlit/config.toml` would stop it earlier, but that file was not in scope |
| 4 | `type=["csv"]` checks only the extension | A renamed non-CSV file reaches the service. The pipeline then rejects it with a specific message (checklist UI-08) |
| 5 | Only successful results are cached | A file that fails is re-analysed on each rerun while it stays selected. It fails fast, so the cost is small |
| 6 | The chart's fixed order is set in a Vega-Lite spec | Checked in code and by checklist UI-02, not by an automated test (AppTest cannot upload a file) |
| 7 | On start-up, Streamlit looks up the machine's external IP (shown as "External URL") and collects usage statistics by default | Run with `--browser.gatherUsageStats false` to turn statistics off |
| 8 | The whole file (≤ 5 MB) is held in memory and written once to a temporary file | Fine for the 5 MB limit; much larger files would need streaming |
| 9 | The session cache holds one result per browser session | Uploading a second file discards the first file's result |
| 10 | The API has no authentication, rate limiting or CORS configuration | Suitable for local use or behind a gateway, not for direct exposure to the internet |
| 11 | The API's 5 MB check runs after the request body has been received | Only 5 MB + 1 byte is read from the upload, but the server still receives the whole request body first. A reverse-proxy body limit would stop larger requests earlier |
| 12 | The API returns `413` only for size and `422` for every other file problem | Clients tell problems apart by the `detail` message, not by separate error codes |
| 13 | The pipeline (Day 03) accepts non-ASCII digits such as `١٢` as numbers, because Python's `float()` does | The Preview shows such a column as `text` while the ticket is still valid. Changing this would mean changing Day 03 |
| 14 | If a request sends two `file` parts, FastAPI uses the last one | Deterministic and pinned by a test, but a client sending two files gets no warning |
| 15 | Day 04 depends on the Day 03 folder being next to it | Moving Day 04 on its own needs Day 03's package installed some other way (e.g. `pip install -e <path to Day 03>`) |
