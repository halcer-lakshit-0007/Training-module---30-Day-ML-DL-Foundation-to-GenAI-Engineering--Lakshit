# Day 05 - NumPy Fundamentals (ticket numerical utilities)

Adds NumPy-based numerical utilities to the ticket analytics module built in Days 01-04.
Task brief: `Day_05_numpy_fundamentals.md`.

## 1. Setup

```bash
cd Day-05-NumPy-Fundamentals
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # numpy, pytest
pip install -e .                           # or: export PYTHONPATH=src
python -m pytest -v                        # 159 passed, 4 skipped (see logs/test_results.txt)
python -m ticket_numerics.benchmark --sizes 1000 10000 100000 1000000 --repeats 7 --seed 42
```

The core runs on Python >= 3.9. The optional bridge to Day 03 (`bridge.py`, `tests/test_bridge.py`)
needs Python >= 3.11 (Day 03 uses `StrEnum`) and Day 03 installed from its own folder
(uncomment the last line of `requirements.txt`). Without it those 4 tests are **skipped, not failed**.

Command line (needs Day 03): `python -m ticket_numerics path/to/tickets.csv` - exit 0 ok, 2 bad file/data (message on stderr), 3 Day 03 not installed. Output saved in `logs/cli_output.txt`.

## 2. How Day 05 fits Days 01-04

| Earlier day | What Day 05 reuses / follows |
|---|---|
| Day 03 `Ticket` / `run_pipeline` | Reading, validation, cleaning and duplicate handling stay in Day 03. `from_tickets()` accepts Day 03's `Ticket` objects (duck-typed); `bridge.arrays_from_csv()` runs Day 03's pipeline first. Nothing is copied. |
| Day 03 `summarise` | Same definitions: missing values are excluded (never 0); the mean of nothing is `None`; values rounded to 2 decimals; open = OPEN or PENDING; high priority = HIGH or URGENT. |
| Day 04 `analytics.py` | `group_mean` over category codes is the vectorised twin of `resolution_by_category` and is checked against the same hand-worked numbers (billing 3.0, technical 6.25, account 2.0, unknown 1.5; overall mean 3.8 h). |
| Day 01 review (FAIL: silent column shift) | Lesson applied: bad input fails loudly at the boundary (`as_float_array`, `select`, `group_mean`) instead of being silently reinterpreted - e.g. an int array used as a "mask" would mean positions, so it is rejected. |
| Day 02-04 style | Specific exceptions (`errors.py`), pure functions, no I/O in the math, tests that state the expected value and why, logs saved in `logs/`. |

## 3. Layout

```
src/ticket_numerics/
  arrays.py     Task A  TicketArrays, from_tickets, array_info, as_float_array, select
  metrics.py    Task B/C summary_stats (+ loop twin), group_mean, zscore, min_max_scale,
                         standardise_columns, broadcast_shape, stability helpers
  benchmark.py  Task D  reproducible timing + report
  synthetic.py          seeded data generator (local Generator, no global state)
  bridge.py             optional Day 03 integration
  cli.py                python -m ticket_numerics file.csv (via Day 03)
  errors.py             NumericInputError, IncompatibleShapesError
tests/                  163 tests (4 need Day 03)    logs/   actual outputs
docs/day05_viva_answers.md                             DAILY_REPORT.md
```

## 4. Design decisions and conventions

* **Missing = `NaN` in float64.** NumPy integer arrays cannot hold NaN, so ratings are float64.
  `None` (Day 03) -> `NaN` in `from_tickets`.
* **Empty / all-missing -> `None` statistics**, with `count=0`, like Day 03. Raw NumPy would return
  `NaN` plus a `RuntimeWarning` (shown in `test_numpy_itself_would_warn...`).
* **Population std (ddof=0)**; one value gives 0.0. Chosen because the data is the whole set of tickets, not a sample.
* **Infinity is rejected** at the boundary (Day 03 also rejects non-finite hours). **Overflow** (sum or squares
  exceeding float64) raises `NumericInputError` instead of returning `inf`.
* **Constant data** in `zscore` / `min_max_scale` / `standardise_columns` gives 0.0, not a divide-by-zero.
* **Priority is an int rank low=0..urgent=3** for comparison; Day 04's urgent-first order is a display concern and stays in Day 04.
* **Unknown labels raise**, rather than being coded silently.

## 5. Acceptance criteria -> evidence

| Criterion | Evidence |
|---|---|
| Shapes and dtypes correct | `tests/test_arrays.py` (ticket arrays `(7,)`, float64/int8/bool, `numeric_matrix (7,2)`, nine predicted-shape cases) |
| Broadcasting explained accurately | section 6 below; `tests/test_broadcasting.py` checks my own `broadcast_shape` against `np.broadcast_shapes` for **every** pair of shapes up to 2-D with dims 0-3 |
| Results match a manual or independent check | Hand-worked values from Day 03's sample (`tests/sample_data.py` docstring): hours mean 3.8 / median 3.0 / std 2.34; rating mean 3.83; by-category 3.0 / 6.25 / 2.0 / 1.5. Also cross-checked against `statistics`, `math.fsum`, and a NumPy-free loop on 20 seeded random datasets |
| Edge cases tested | `tests/test_edge_cases.py` (empty, all-NaN, single value, zero, inf, overflow, bool/text/2-D, constant columns, incompatible shapes, no stray warnings) |
| Performance claims supported | `logs/benchmark.txt` + method in `benchmark.py`; section 7 |

**Hand check (hours, present values 4.5, 1.5, 8, 3, 2):** mean = 19/5 = 3.8; sorted 1.5 2 3 4.5 8 -> median 3;
squared deviations 0.49+5.29+17.64+0.64+3.24 = 27.3; sqrt(27.3/5) = 2.34.

## 6. Broadcasting, explained

Align the two shapes on the **right**; for each position the sizes must be equal or one of them 1
(a missing leading size counts as 1); the result takes the larger size. Example used in `standardise_columns`:
`(n, k) - (k,)`: `(n, k)` vs `(1, k)` -> `(n, k)`; the row of column means is applied to every row, no copy.
`(3,) + (4,)` fails (`IncompatibleShapesError` names both shapes). `(3,) + (3, 1)` silently gives `(3, 3)`.

## 7. Benchmark (Task D) - what is and is not claimed

Operation: count/mean/std of a column with ~10 % missing values. Method: seed 42, results verified equal
before timing, 1 warm-up call, 7 timed calls with `time.perf_counter`, median and min reported. Run on
Python 3.9.6, NumPy 2.0.2, macOS arm64, one run, background load not controlled
(full table: `logs/benchmark.txt`). Median ms at n = 100,000:

| method | ms | note |
|---|---|---|
| pure-Python loop | 11.90 | |
| NumPy, array already exists | 0.31 | ~38x faster *in this run* |
| list -> array conversion + NumPy | 5.40 | ~2.2x faster *in this run* |

Supported: on this machine NumPy was faster at every size tested, and most of the benefit disappears if
the data must be converted from a Python list each time. **Not** claimed: any universal factor; other
machines, NumPy builds or operations will differ - rerun the command to reproduce.

## 8. Known limitations / assumptions

* Verified on Python 3.9.6 + NumPy 2.0.2 only. The Day 03 bridge test was **not executed** here (no Python >= 3.11 available);
  `from_tickets` is tested with stand-in objects that have Day 03's attributes, and the 7 sample tickets were transcribed by hand from Day 03's CSV.
* `n` for generated data and benchmark sizes is capped at 50,000,000 (guards against typos like 10**12, which previously exhausted memory).
* Values near 1e154 or larger can overflow when squared and are rejected with a clear error.
* float64 ratings: integers above 2^53 would lose precision (irrelevant for 1-5).
* Overflow (sums or squares beyond float64) is an error everywhere: `summary_stats`, `group_mean`, `zscore`, `min_max_scale`, `standardise_columns`.
* The benchmark measures one small operation; it says nothing about I/O or pandas.
* `group_mean` keeps a slot for every group code (NaN when empty); Day 04 *omits* empty categories when displaying.

## 8b. Day 03 integration evidence (read this)

Python >= 3.11 was not available where this was built. To still exercise the real hand-off, a **scratch copy** of Day 03 was
patched only for Python 3.9 syntax (a `StrEnum` stand-in, `ParamSpec` from `typing_extensions`, `zip(strict=)` removed; `csv.reader(strict=True)` kept)
and the suite was run against it: **163 passed, 0 skipped** (`logs/test_results_with_day03_py39_patched.txt`), including the real
Day 03 loader rejecting an unterminated quote and the CLI producing `logs/cli_output.txt`. This is strong evidence, **not** a run on real 3.11 - repeat it there
(`pip install -e ../Day-03-...; pytest`) and expect 163 passed.

## 9. Note on the earlier days (review findings)

Read through the repo while preparing Day 05. Day 01's reviewed defect (extra CSV field shifting columns) is fixed in
the Day 01 processor and handled by Day 03's loader (`Row has N fields but the header defines M`). Observations, none blocking Day 05:
Day 01 uses a different schema (`ticket_id`, no `customer`/`created_at`) from Days 02-04 (`id`, ...), so only Day 03/04 are the reuse target; Days 03-04
declare Python >= 3.11 while many machines default to older versions - state the required version in each README setup step.
I did not re-run Days 01-04 test suites here (Python 3.9 only), so their "passing" status is as logged in their own `logs/`, not independently re-verified today.
