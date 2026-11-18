"""
Task D - benchmark a small operation and report the method with the numbers.

Operation: count, mean and population std of a column with ~10 % missing
values (what ``summary_stats`` computes), three ways:

  loop         pure-Python loop over a list of floats (None = missing)
  numpy        NumPy on an array that already exists
  numpy+convert  list -> array conversion *plus* NumPy (the cost you pay if
                 your data starts as a Python list)

Method: results are checked to agree BEFORE timing; each timing is the wall
clock of one call (``time.perf_counter``); one untimed warm-up call; ``repeats``
timed calls; the median and minimum are reported. Nothing here asserts a
speed-up: ratios are printed from what was measured, on this machine, this run.

Run:  python -m ticket_numerics.benchmark --sizes 1000 100000 --repeats 7 --seed 42
"""

from __future__ import annotations

import argparse
import math
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Sequence

import numpy as np

from ticket_numerics.synthetic import make_hours, require_int, require_size

DEFAULT_SIZES = (1_000, 10_000, 100_000, 1_000_000)


@dataclass(frozen=True)
class BenchmarkRow:
    n: int
    method: str
    median_ms: float
    min_ms: float
    repeats: int


def _loop(data: list) -> tuple:
    count = 0
    total = 0.0
    for v in data:
        if v is not None:
            count += 1
            total += v
    mean = total / count
    sq = 0.0
    for v in data:
        if v is not None:
            sq += (v - mean) ** 2
    return count, mean, math.sqrt(sq / count)


def _numpy(arr: np.ndarray) -> tuple:
    present = arr[~np.isnan(arr)]
    return int(present.size), float(present.mean()), float(present.std())


def _time(fn: Callable[[], object], repeats: int) -> List[float]:
    fn()                                                  # warm-up, not recorded
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def run_benchmark(
    sizes: Sequence[int] = DEFAULT_SIZES, repeats: int = 7, seed: int = 42
) -> List[BenchmarkRow]:
    if require_int(repeats, "repeats") < 1:
        raise ValueError("repeats must be at least 1")
    rows: List[BenchmarkRow] = []
    for n in sizes:
        if require_size(n) < 1:
            raise ValueError("sizes must be positive")
        arr = make_hours(n, seed)
        if np.isnan(arr).all():          # tiny n can draw all-missing; the mean needs one value
            arr[0] = 1.0
        py_list = [None if math.isnan(v) else v for v in arr.tolist()]

        a, b = _loop(py_list), _numpy(arr)                 # correctness before speed
        if a[0] != b[0] or not all(math.isclose(x, y, rel_tol=1e-9) for x, y in zip(a, b)):
            raise RuntimeError(f"loop and numpy disagree at n={n}: {a} vs {b}")

        def convert_then_numpy() -> tuple:
            return _numpy(np.array([np.nan if v is None else v for v in py_list]))

        for method, fn in (
            ("loop", lambda: _loop(py_list)),
            ("numpy", lambda: _numpy(arr)),
            ("numpy+convert", convert_then_numpy),
        ):
            s = _time(fn, repeats)
            rows.append(BenchmarkRow(n, method, statistics.median(s), min(s), repeats))
    return rows


def format_report(rows: Sequence[BenchmarkRow], seed: int) -> str:
    lines = [
        "BENCHMARK: count/mean/std of a column with ~10% missing values",
        f"python {platform.python_version()} | numpy {np.__version__} | "
        f"{platform.system()} {platform.machine()} | seed {seed} | "
        f"repeats {rows[0].repeats if rows else 0} (1 warm-up call each, median reported)",
        "Timing: time.perf_counter around one call; results verified equal before timing.",
        "",
        f"{'n':>10}  {'method':<14}{'median ms':>12}{'min ms':>12}{'loop/method':>14}",
    ]
    baseline = {}
    for r in rows:
        if r.method == "loop":
            baseline[r.n] = r.median_ms
    for r in rows:
        ratio = baseline[r.n] / r.median_ms if r.median_ms > 0 else float("inf")
        lines.append(f"{r.n:>10}  {r.method:<14}{r.median_ms:>12.4f}{r.min_ms:>12.4f}{ratio:>13.1f}x")
    lines += [
        "",
        "Read with care: one machine, one run, background load not controlled.",
        "loop/method = loop median / method median. These are measurements, not guarantees.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] = None) -> int:  # type: ignore[assignment]
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        rows = run_benchmark(args.sizes, args.repeats, args.seed)
    except (ValueError, TypeError, RuntimeError, MemoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_report(rows, args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
