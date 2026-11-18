# Ticket Numerical Analysis — NumPy Fundamentals

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 05 — NumPy Fundamentals |
| **Author** | Lakshit (HALCER) |
| **Date** | 18 November 2026 |
| **Status** | Implementation complete; Day 03 integration not yet run on real Python ≥ 3.11 |
| **Test result** | 183 passed, 4 skipped without Day 03 — [`logs/test_results.txt`](logs/test_results.txt); 187 passed with Day 03 on a Python 3.9–patched copy — [`logs/test_results_with_day03_py39_patched.txt`](logs/test_results_with_day03_py39_patched.txt) |
| **Warnings** | Suite run with `-W error` |
| **Benchmark** | [`logs/benchmark.txt`](logs/benchmark.txt) |

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

Adds NumPy-based numerical analysis utilities to the ticket analytics module of Days 01–04 (task brief: `Day_05_numpy_fundamentals.md`):

- **Task A** — arrays built from the numeric ticket fields (resolution hours, rating, priority rank, category code, open flag), with shape/dtype inspection, indexing and boolean filtering;
- **Task B** — vectorised summary metrics and per-category means, each compared with an independent plain-Python loop;
- **Task C** — deliberate handling of empty arrays, missing values, infinity, overflow and incompatible shapes;
- **Task D** — a reproducible benchmark whose report records its method and makes no speed claim beyond what it measured.

All CSV reading, validation and cleaning is done by the Day 03 `ticket_pipeline` package. Day 05 **uses it from its own folder** (`../Day-03-Python-Engineering-Practices-Exceptions-Testing/`); it is not copied. The numerical functions themselves do not import Day 03: they accept any object with the Day 03 `Ticket` attributes, so they are testable without it.

How Day 05 follows the earlier days:

| Earlier day | What Day 05 reuses or follows |
|---|---|
| Day 03 `summarise` | Same definitions: missing values are excluded (never 0); the mean of nothing is `None`; values rounded to 2 decimals; open = OPEN or PENDING; high priority = HIGH or URGENT |
| Day 04 `analytics.py` | `group_mean` over category codes is the vectorised twin of `resolution_by_category`, checked against the same expected numbers (billing 3.0, technical 6.25, account 2.0, unknown 1.5; overall mean 3.8 h) |
| Day 01 review (FAIL: extra CSV field silently shifted columns) | Bad input fails loudly at the boundary instead of being silently reinterpreted; the unterminated-quote case of another submission's review is pinned (§7.2) |
| Days 02–04 style | Specific exceptions, pure functions, expected values worked out by hand, evidence logs in `logs/` |

---

## 2. Acceptance Criteria Mapping

The criteria are taken from `Day_05_numpy_fundamentals.md` §6.

| # | Criterion | How it is met | Proof |
|---|---|---|---|
| 1 | Array shapes and dtypes are correct | Ticket arrays have shape `(n,)` with dtypes float64 / int8 / bool / str; the numeric matrix has shape `(n, 2)`; an empty ticket list gives empty arrays of the same dtypes | `tests/test_arrays.py` (30 tests, incl. nine predicted-shape cases); `logs/array_exercises.txt` |
| 2 | Broadcasting behaviour is explained accurately | The rule is written out in §8.2 and implemented by hand in `broadcast_shape`, which agrees with `np.broadcast_shapes` for every pair of shapes up to 2-D with sizes 0–3 and gives an error naming both shapes when they do not fit | `tests/test_broadcasting.py` (15 tests) |
| 3 | Results match a manual or independent check | Hours from Day 03's sample: mean 19/5 = 3.8, median 3.0, std √(27.3/5) = 2.34; also cross-checked against `statistics`, `math.fsum` and NumPy-free loop twins (20 seeded random datasets) | `tests/test_metrics.py` (29), `tests/test_numerical.py` (10) |
| 4 | Edge cases are tested | Empty, all-missing, single value, zero, ±inf, overflow, bool / text / 2-D input, constant data, ragged rows, wrong group codes, incompatible shapes, masked arrays, tiny benchmark sizes; no stray warnings | `tests/test_edge_cases.py` (22), `tests/test_regressions.py` (66) |
| 5 | Performance claims are supported by a reproducible comparison | `python -m ticket_numerics.benchmark` verifies loop and NumPy agree before timing, uses a warm-up and repeats, and prints method and environment | `logs/benchmark.txt`; §7.3 |
| 6 | Missing values are handled deliberately | NaN = missing in float64; excluded from every statistic; "nothing present" returns `None` like Day 03 | `test_edge_cases.py`; §8.1 |
| 7 | Reading and cleaning are reused, not re-implemented | `bridge.arrays_from_csv` calls Day 03's `run_pipeline`; no CSV parsing in Day 05's numerical code | `bridge.py`; `tests/test_csv_structure.py` |
| 8 | A malformed CSV never gives a silently shorter result | Unterminated quote → Day 03 `MalformedFileError` → CLI exit 2 | `tests/test_csv_structure.py`, `tests/test_cli.py` |
| 9 | Results are reproducible | Seeded local `default_rng`; the global NumPy state is neither read nor changed | `tests/test_numerical.py` |

---

## 3. Architecture

```
 tickets.csv ──► Day 03 ticket_pipeline ──► valid Ticket objects
 (not copied)    (CSVLoader strict, parse,         │
                  duplicates, rejects)             ▼
                                         arrays.from_tickets()   (duck-typed)
                                                   │  TicketArrays: 6 columns, shape (n,)
                                                   ▼
                          metrics.py  summary_stats · group_mean · zscore ·
                                      min_max_scale · standardise_columns · broadcast_shape
                                      (each with a NumPy-free loop twin where compared)
                                                   │
                         cli.py (text report) ◄────┴────► benchmark.py (timing report)
```

Dependency direction: `cli` and `benchmark` → `metrics` → `arrays` → `errors`; only `bridge` imports Day 03, and it does so lazily inside the function.

---

## 4. Project Structure

```
Day-05-NumPy-Fundamentals/
├── README.md · DAILY_REPORT.md · pyproject.toml · requirements.txt · .gitignore
├── src/ticket_numerics/
│   ├── arrays.py      Task A   TicketArrays, from_tickets, array_info, as_float_array, select
│   ├── metrics.py     Task B/C summary_stats, group_mean, zscore, min_max_scale,
│   │                           standardise_columns, broadcast_shape, loop twins
│   ├── benchmark.py   Task D   reproducible timing report
│   ├── synthetic.py            seeded data generator
│   ├── bridge.py               optional Day 03 integration
│   ├── cli.py · __main__.py    python -m ticket_numerics file.csv
│   └── errors.py               NumericInputError, IncompatibleShapesError
├── scripts/show_arrays.py      prints Task A output
├── tests/                      10 files, 187 tests
├── docs/day05_viva_answers.md  draft answers to the five viva questions
└── logs/                       test, benchmark, array and CLI outputs
```

---

## 5. Setup

Core requirements: Python ≥ 3.9 and NumPy ≥ 1.24. The Day 03 bridge, the CLI and 4 tests need Python ≥ 3.11 (Day 03 uses `StrEnum`).

```bash
cd Day-05-NumPy-Fundamentals
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt        # numpy 2.0.2, pytest 8.4.2
pip install -e .                       # or: export PYTHONPATH=src
```

For the Day 03 integration (Python ≥ 3.11), also run from this folder:

```bash
pip install -e ../Day-03-Python-Engineering-Practices-Exceptions-Testing
```

---

## 6. Run

```bash
python scripts/show_arrays.py                      # Task A (needs PYTHONPATH=src:tests)
python -m ticket_numerics ../Day-03-Python-Engineering-Practices-Exceptions-Testing/data/tickets.csv
python -m ticket_numerics.benchmark --sizes 1000 10000 100000 1000000 --repeats 7 --seed 42
```

CLI exit codes: `0` ok · `2` the file or its data cannot be analysed (message on stderr) · `3` Day 03's `ticket_pipeline` is not installed. Output on Day 03's sample is saved in `logs/cli_output.txt`.

---

## 7. Test

```bash
python -m pytest -v -W error
```

### 7.1 Test inventory

| File | Tests | Covers |
|---|---|---|
| `test_arrays.py` | 30 | shapes, dtypes, missing → NaN, filtering, input validation, predicted shapes |
| `test_metrics.py` | 29 | hand-checked values, loop vs vectorised, group means |
| `test_edge_cases.py` | 22 | empty, all-missing, overflow, scaling, incompatible shapes |
| `test_broadcasting.py` | 15 | rule vs NumPy, axis semantics |
| `test_numerical.py` | 10 | floating point, stability, seeds |
| `test_benchmark.py` | 6 | structure, agreement check, argument errors |
| `test_regressions.py` | 66 | every defect found by probing (DAILY_REPORT §5) |
| `test_cli.py` | 4 | report values and exit codes (3 run anywhere, 1 needs Day 03) |
| `test_csv_structure.py` | 4 | quote trap with the standard library (2); Day 03 loader (2, need Day 03) |
| `test_bridge.py` | 1 | real Day 03 sample file (needs Day 03) |

### 7.2 Day 03 integration evidence

Python ≥ 3.11 was not available where this was built. To still exercise the real hand-off, a **scratch copy** of Day 03 was patched only for Python 3.9 syntax (`StrEnum` stand-in, `ParamSpec` from `typing_extensions`, `zip(strict=)` removed; `csv.reader(strict=True)` kept) and the suite run against it: **187 passed, 0 skipped**. That includes Day 03's real loader rejecting this input and the CLI reading the real sample file:

```
ticket_id,priority,category,resolution_time_hours
T1,High,Technical,"5
T2,Low,General,8
```

`csv.DictReader` returns **one** record (T2 hidden inside T1's value); `csv.reader(strict=True)`, which Day 03 uses, raises. This is strong evidence, **not** a run on real Python 3.11 — repeat it there and expect 187 passed.

### 7.3 Benchmark (Task D)

Operation: count, mean and population std of a column with ~10 % missing values. Method: seed 42; loop and NumPy results verified equal before timing; one untimed warm-up call; 7 timed calls with `time.perf_counter`; median and minimum reported. Environment: Python 3.9.6, NumPy 2.0.2, macOS arm64, one run, background load not controlled. Median ms at n = 100,000:

| Method | ms | Note |
|---|---|---|
| pure-Python loop | 11.90 | |
| NumPy, array already exists | 0.31 | ~38× faster *in this run* |
| list → array conversion + NumPy | 5.40 | ~2.2× faster *in this run* |

Supported: on this machine NumPy was faster at every size tested, and most of the gain disappears if the data must be converted from a Python list each time. Not claimed: any universal factor. Another run on the same machine differed by about 10 % (10.86 / 0.29 / 4.64 ms); other machines and NumPy builds will differ. Full table: `logs/benchmark.txt`.

---

## 8. Data Contract

### 8.1 Arrays

| Array | dtype | Meaning |
|---|---|---|
| `ticket_ids` | `<U…` | ticket id |
| `resolution_hours` | float64 | hours; **NaN = not recorded** |
| `rating` | float64 | 1–5, whole numbers; **NaN = not rated** (float because integer arrays cannot hold NaN) |
| `priority_rank` | int8 | low 0, medium 1, high 2, urgent 3 |
| `category_code` | int8 | index into `CATEGORY_ORDER` = billing, technical, account, general, unknown |
| `is_open` | bool | OPEN or PENDING; RESOLVED and CLOSED are False; any other status raises |

`numeric_matrix()` has shape `(n, 2)`: hours and rating.

### 8.2 Broadcasting

Align the two shapes on the **right**; for each position the sizes must be equal or one of them 1 (a missing leading size counts as 1); the result takes the larger size. Used in `standardise_columns`: `(n, k) − (k,)` becomes `(n, k)` vs `(1, k)`, so the row of column means is applied to every row without copying. `(3,) + (4,)` fails with an error naming both shapes. `(3,) + (3, 1)` silently gives `(3, 3)`, a classic trap.

### 8.3 Numerical rules

| Rule | Behaviour |
|---|---|
| Missing values | excluded from every statistic, never treated as 0 |
| Empty or all-missing | `count = 0`, every statistic `None` (NumPy alone would give NaN plus a warning) |
| Standard deviation | population (ddof = 0); one value gives 0.0 |
| Rounding | 2 decimals; `-0.0` shown as `0.0` |
| Constant data | `zscore`, `min_max_scale`, `standardise_columns` give 0.0 instead of dividing by zero |
| Infinity | rejected at the boundary |
| Overflow (sum or squares beyond float64) | `NumericInputError`, never `inf` |
| Random data | local `default_rng(seed)`; global NumPy state untouched |

---

## 9. Error Messages

| Situation | Exception | Message (start) |
|---|---|---|
| bool (including mixed `[True, 1]`), text, complex, dict, generator input | `NumericInputError` | `values: bool is not a number` / `dtype … is not numeric` / `expected a list, tuple or array` |
| wrong number of dimensions | `NumericInputError` | `values: expected 1-D data, got shape …` |
| ragged rows, `10**400` | `NumericInputError` | `not a regular numeric array …` / `… is too large for float64` |
| infinity | `NumericInputError` | `values: contains infinity` |
| outside allowed range | `NumericInputError` | `contains values below 0.0` / `above 5.0` |
| fractional rating | `NumericInputError` | `rating: must be whole numbers` |
| unknown priority / category label | `NumericInputError` | `priority: unknown value 'critical'` |
| ticket without a needed attribute | `NumericInputError` | `ticket #1 is missing an attribute …` |
| overflow | `NumericInputError` | `values are too large: the sum or squares overflow float64` |
| bad group codes or `n_groups` | `NumericInputError` | `group codes must be in [0, n)` / `n_groups must be an integer` |
| shapes that cannot broadcast | `IncompatibleShapesError` | `shapes (3,) and (4,) do not broadcast: dimension -1 has sizes 3 and 4 …` |
| bad benchmark / generator arguments | `TypeError` / `ValueError` | `n must be an integer, got float` / `n must be at most 50,000,000` |
| CLI: Day 03 not installed | exit code 3 | `Day 03's ticket_pipeline is not installed (needs Python >= 3.11)…` |
| CLI: file or data cannot be analysed | exit code 2 | `error: …` |

---

## 10. Assumptions

| # | Assumption |
|---|---|
| 1 | The task brief is `Day_05_numpy_fundamentals.md`; the acceptance criteria in §2 come from its §6. Day 05 builds on Days 03 and 04 only: Day 01 uses a different schema (`ticket_id`, no `customer` or `created_at`). |
| 2 | Missing = NaN in float64. Ratings are float64 as well, because NumPy integer arrays cannot hold NaN. |
| 3 | Population standard deviation (ddof = 0), because the data is every ticket, not a sample. |
| 4 | An unknown priority, category or status label raises instead of being coded silently; Day 03 already guarantees valid labels, so this only guards other callers. |
| 5 | Priority rank order is low → urgent for comparison. Day 04's urgent-first order is a display concern and stays in Day 04. |
| 6 | Values near 1e154 or larger overflow when squared and are rejected, not approximated. |
| 7 | `n` for generated data and benchmark sizes is capped at 50,000,000 (guards against typos such as `10**12`). |
| 8 | Day 03's own test results are as logged in Day 03; they were not re-run for Day 05. |
| 9 | `pyproject.toml` lists `pythonpath` entries for `src`, `tests` and Day 03's `src`, so pytest finds Day 03 without installing it; a missing Day 03 folder is harmless. |

---

## 11. Limitations

| # | Limitation | Impact / mitigation |
|---|---|---|
| 1 | The Day 03 integration has been run only on a Python 3.9–patched copy | Run `pytest` on real Python ≥ 3.11 and expect 187 passed (§7.2) |
| 2 | Verified on Python 3.9.6 and NumPy 2.0.2 only | Other versions untested |
| 3 | The benchmark measures one small operation, once, on one machine | It says nothing about I/O, pandas or other operations; rerun to reproduce |
| 4 | float64 ratings lose precision above 2⁵³ | Irrelevant for ratings 1–5 |
| 5 | Very large inputs (≥ 1e154 squared) are rejected rather than scaled | Documented in §8.3 |
| 6 | `group_mean` keeps a slot per group (NaN when empty); Day 04 omits empty categories when displaying | The CLI omits empty categories like Day 04 |
| 7 | `Decimal` values are rejected | Convert to float first |
| 8 | Day 05 depends on the Day 03 folder being next to it for the bridge and CLI | Install Day 03 another way if moved (`pip install -e <path>`) |
| 9 | Generated data is gamma-distributed; exact values are not pinned | NumPy does not guarantee distribution streams across versions; reproducibility holds for the same NumPy version |
