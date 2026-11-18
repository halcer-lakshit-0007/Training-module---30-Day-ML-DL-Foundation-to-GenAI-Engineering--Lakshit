
# Daily Report — Day 05

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 05 — NumPy Fundamentals |
| **Developer** | Lakshit (HALCER) |
| **Date** | 18 November 2026 |
| **Duration** | _[TO BE FILLED IN BY LAKSHIT]_ |
| **Status** | Implementation complete; **not yet run on real Python ≥ 3.11** (see §4) |
| **Test result** | 159 passed, 4 skipped without Day 03; 163 passed, 0 skipped with Day 03 on a Python 3.9–patched copy (`logs/test_results.txt`, `logs/test_results_with_day03_py39_patched.txt`) |
| **Warnings** | Suite run with `-W error`: any warning fails a test |
| **Benchmark** | `logs/benchmark.txt` (method and environment recorded in the file) |

---

## 1. Topics Learned

> _[TO BE COMPLETED BY LAKSHIT: study blocks and durations from the Day 05 brief.]_ The table lists only where each topic shows up in this project's code.

| Topic | Where it is applied in this project |
|---|---|
| `ndarray`: shape, dtype, itemsize, nbytes | `arrays.array_info`; `logs/array_exercises.txt`; `tests/test_arrays.py` (nine predicted-shape cases) |
| Array creation from ticket fields | `arrays.from_tickets` builds six column arrays (float64, int8, bool, str) from Day 03 `Ticket` objects |
| Boolean masks, slicing, views | `TicketArrays.high_priority_open_mask`, `arrays.select` (rejects integer "masks"), `scripts/show_arrays.py` (`np.shares_memory`) |
| Reductions and `axis` | `metrics.standardise_columns`, `tests/test_broadcasting.py::test_axis_semantics` |
| Broadcasting | `metrics.broadcast_shape` (rule written out by hand, checked against `np.broadcast_shapes` for every small shape pair), `standardise_columns`, `checked_add` |
| Vectorisation vs loops | `metrics.summary_stats` / `group_mean` and their NumPy-free `*_loop` twins; `benchmark.py` |
| NaN handling | Missing = NaN everywhere; `summary_stats` excludes it; empty or all-missing gives `None` (Day 03 contract) |
| Floating point and stability | `tests/test_numerical.py`: `0.1 + 0.2`, absorbed small values (`math.fsum`), cancellation in `E[x²] − E[x]²` |
| Random seeds | `synthetic.make_hours` uses a local `default_rng(seed)`; tests prove the global NumPy state is untouched |
| Benchmarking | `benchmark.py`: results verified equal first, warm-up, median and minimum, environment printed |

### 1.1 Key learnings

_[TO BE COMPLETED BY LAKSHIT]_

---

## 2. What I Can Explain Without Notes

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_ Draft answers to the five viva questions are in `docs/day05_viva_answers.md`; they are a starting point, not a substitute for explaining them yourself.

---

## 3. Implementation Completed

| Deliverable | Files | Status |
|---|---|---|
| Task A — arrays from numeric ticket fields | `src/ticket_numerics/arrays.py` (`TicketArrays`, `from_tickets`, `array_info`, `as_float_array`, `select`, `sequence_to_2d`); `scripts/show_arrays.py` | Complete |
| Task B — vectorised metrics and loop comparison | `src/ticket_numerics/metrics.py` (`summary_stats`, `group_mean`, `zscore`, `min_max_scale`, `standardise_columns` and `summary_stats_loop`, `group_mean_loop`, `agree`) | Complete |
| Task C — edge cases | empty, all-missing, single value, inf, overflow, bool/text/2-D input, constant columns, incompatible shapes: `tests/test_edge_cases.py`, `tests/test_regressions.py` | Complete |
| Task D — benchmark | `src/ticket_numerics/benchmark.py`; `logs/benchmark.txt` | Complete |
| Day 03 reused, not copied | `bridge.py` calls Day 03's `run_pipeline`; the pure functions accept Day 03-style objects by duck typing | Complete; integration run on a patched copy only |
| Command line | `python -m ticket_numerics file.csv` (`cli.py`); exit codes 0 / 2 / 3; `logs/cli_output.txt` | Complete |
| Tests | 163 tests in 9 files (§4) | Complete |
| Packaging and docs | `pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md`, this report, `docs/day05_viva_answers.md`; Day 05 row in the root README | Complete |

---

## 4. Tests / Experiment Results

```
$ python -m pytest -q -W error                       # Day 03 not installed
159 passed, 4 skipped in 0.2 s

$ DAY03_CSV=<scratch Day 03> python -m pytest -q -W error -o pythonpath="src tests <scratch Day 03>/src"
163 passed in 0.2 s
```

| Check | Result | Evidence |
|---|---|---|
| Full suite, Day 03 absent | 159 passed, 4 skipped (the 4 need `ticket_pipeline`) | `logs/test_results.txt` |
| Full suite, real Day 03 code on a **scratch copy patched only for Python 3.9 syntax** (`StrEnum` stand-in, `ParamSpec` from `typing_extensions`, `zip(strict=)` removed; `csv.reader(strict=True)` kept) | 163 passed, 0 skipped | `logs/test_results_with_day03_py39_patched.txt` |
| Hand-worked values from Day 03's sample | hours: mean 3.8, median 3.0, std 2.34, 5 present / 2 missing; ratings: mean 3.83, median 4.0; by category 3.0 / 6.25 / 2.0 / 1.5; high-priority open T001, T004, T009 | `tests/test_metrics.py`, `tests/test_arrays.py`, `tests/test_cli.py` |
| Independent checks | `statistics` module, `math.fsum`, NumPy-free loop twins on 20 seeded random datasets, `np.broadcast_shapes` on every pair of shapes up to 2-D with sizes 0–3 | `tests/test_metrics.py`, `tests/test_broadcasting.py`, `tests/test_numerical.py` |
| Test sensitivity | changing `std` to `ddof=1` made 28 tests fail | run once, by hand |
| Unterminated-quote CSV (another submission's FAIL case) | `csv.DictReader` returns one record with T2 hidden in T1's value; a strict reader raises; Day 03's loader raises `MalformedFileError`; the CLI exits 2 | `tests/test_csv_structure.py`, `tests/test_cli.py` |
| Benchmark (count/mean/std, ~10 % missing, seed 42, 7 repeats, 1 warm-up) | at n = 100,000: loop 11.90 ms, NumPy 0.31 ms, list→array + NumPy 5.40 ms. One machine, one run; an earlier run gave 10.86 / 0.29 / 4.64 | `logs/benchmark.txt`; README §7.3 |
| Run on real Python ≥ 3.11 | _[TO BE FILLED IN BY LAKSHIT]_ | — |

Test files: `test_arrays.py` (30), `test_metrics.py` (29), `test_edge_cases.py` (22), `test_broadcasting.py` (15), `test_numerical.py` (10), `test_benchmark.py` (6), `test_regressions.py` (42), `test_cli.py` (4), `test_csv_structure.py` (4), `test_bridge.py` (1).

Environment: macOS arm64, Python 3.9.6, NumPy 2.0.2, pytest 8.4.2.

---

## 5. Bug or Challenge and Its Root Cause

### 5.1 Main challenge — overflow returned `inf` or wrong numbers without an error

**Symptom:** `summary_stats([-5, 5, 1e300])` returned `inf` with a `RuntimeWarning`. Later probes found the same family: `zscore([1.7e308, -1.7e308])` returned `[0, -0]`, `min_max_scale` returned `[0, nan]`, `group_mean` returned `inf`, and `checked_add([1e308], [1e308])` returned `inf`.

**Root cause:** NumPy does not raise on float64 overflow; it produces `inf` or `nan` and at most warns. Squaring 1e300 or adding two 1.7e308 values leaves the float64 range, and every later step (division, comparison) then silently gives a wrong but plausible result.

**Fix:** every function that can overflow computes under `np.errstate`, checks the result is finite, and raises `NumericInputError` ("values are too large…"). The loop twins catch Python's `OverflowError` so both paths behave the same. Pinned by `test_regressions.py`.

### 5.2 Other problems found and fixed

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | `group_mean_loop` accepted code `-1`; the NumPy version raised | Python list indexing accepts negative numbers and wraps to the last group; the twin skipped the validation | One shared `_validate_groups` used by both |
| 2 | Ragged lists, `10**400`, and `n_groups=2.5` leaked raw NumPy `ValueError`, `OverflowError`, `TypeError` | Conversion errors were not translated at the input boundary | Boundary converts them to `NumericInputError` |
| 3 | A masked array's hidden value (`99`) was read as data | `np.ma.MaskedArray` is an `ndarray` subclass; the code treated it as a plain array | Masked entries become NaN (missing) before anything else |
| 4 | `broadcast_shape((-1,), (1,))` returned `(-1,)` | The rule only compared sizes; it did not check they were valid sizes | Sizes must be non-negative integers; results are plain `int` |
| 5 | `sequence_to_2d(np.ones((2, 2)))` raised "truth value of an array is ambiguous" | `if rows:` on an ndarray | Arrays are handled first; non-row items are rejected with a clear message |
| 6 | `from_tickets` accepted a rating of 3.5 | Range check (1–5) did not check "whole number", which Day 03 requires | `_whole_numbers` check |
| 7 | `run_benchmark((1,), seed=0)` raised `ZeroDivisionError` | With 10 % missing, one value can be all-missing, so the mean has no values | Benchmark data always keeps at least one value |
| 8 | `--sizes 1000000000000` killed the process | No upper limit on generated sizes | Cap of 50,000,000 with a clear error; wrong types give `TypeError` |
| 9 | `exact_sum` and `naive_variance` leaked `OverflowError` / a warning | Same overflow family as 5.1 | Converted to `NumericInputError` |
| 10 | `-0.0` appeared in summaries | `round(-0.0, 2)` stays `-0.0` | `+ 0.0` normalisation |
| 11 | Own test compared `zscore` output with `==` and failed by 2e-16 | Floating-point rounding (the lesson of viva question 5) | `np.testing.assert_allclose` |
| 12 | The first CLI bad-quote test would have passed on a schema error | The test CSV had too few columns, so the schema check fired before the quote check | Test uses the full Day 03 header and asserts the message is not "missing required" |
| 13 | `requirements.txt` pinned `pytest==8.3.5` but the logs were produced with 8.4.2 | The pin was typed, not read from the environment | Pin set to 8.4.2 |
| 14 | My own scratch patch of Day 03 first removed `strict=True` from `csv.reader` too | A blanket text replace also matched that line | Replaced only the `zip(...)` arguments; the unterminated-quote test then passed |

---

## 6. Design Decision and Why

**Decision:** Missing = NaN in float64 (ratings too), and a single conversion boundary (`as_float_array`) that validates, converts and rejects before any maths runs.

- Vectorised code stays loop-free: a NaN mask is one boolean array, not a per-element check.
- Day 03 uses `None` for "not recorded". The boundary converts `None` → NaN, and `summary_stats` converts "nothing present" back to `None`, so the Day 03 contract (no value → `None`) is kept for callers.
- Everything that is not a finite number (bool, text, infinity, 2-D data) is rejected once, with a message naming the problem, instead of producing a plausible wrong number. This is the Day 01 lesson (silent column shift) applied to arrays.
- Reading and cleaning CSV stays in Day 03 (used from its own folder, not copied), as Day 04 does.

**Alternative considered:** NumPy masked arrays (`np.ma`) for missing values. Rejected: many functions ignore or mishandle the mask (see 5.2 #3), and NaN is what Day 03/04 consumers and pandas (Day 06) expect.

---

## 7. Blocker and What I Tried

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_ Facts that may help: Python ≥ 3.11 (needed by Day 03's `StrEnum`) was not available where Day 05 was built, so the Day 03 integration could only be run on a patched Python 3.9 copy.

---

## 8. Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
|---|---|---|
| Array shapes and dtypes are correct | Met | `tests/test_arrays.py`; `logs/array_exercises.txt` |
| Broadcasting behaviour is explained accurately | Met | README §8.2; `tests/test_broadcasting.py` (checked against NumPy on all small shape pairs) |
| Results match a manual or independent check | Met | hand-worked values; `statistics`, `math.fsum`, loop twins (§4) |
| Edge cases are tested | Met | `tests/test_edge_cases.py`, `tests/test_regressions.py` |
| Performance claims are supported by a reproducible comparison | Met | `benchmark.py`, `logs/benchmark.txt`; README §7.3 states what is not claimed |
| Day 03 hand-off works on real Python ≥ 3.11 | **Pending** | only run on a patched 3.9 copy |

**Submission checklist:**
- Source code committed to Git with a meaningful commit message ✔
- Tests and actual output saved in `logs/` ✔
- README with setup, assumptions and limitations ✔
- Developer can explain the implementation without reading code line by line — _for Lakshit to confirm_

---

## 9. Tomorrow's Plan

_[TO BE WRITTEN BY LAKSHIT — placeholder. Not filled in on purpose.]_
