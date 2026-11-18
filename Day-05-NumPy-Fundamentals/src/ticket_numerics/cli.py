"""
Command line: numeric analysis of a ticket CSV.

    python -m ticket_numerics path/to/tickets.csv

Reading, validation and cleaning are done by Day 03's pipeline (not copied);
this module only turns the valid tickets into arrays and prints metrics.

Exit codes: 0 ok | 2 the file or its data cannot be analysed (message on stderr)
            | 3 Day 03's ticket_pipeline is not installed (needs Python >= 3.11).
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from ticket_numerics.arrays import CATEGORY_ORDER, TicketArrays, array_info
from ticket_numerics.errors import NumericInputError
from ticket_numerics.metrics import group_mean, summary_stats


def format_report(ta: TicketArrays) -> str:
    """Pure function: arrays in, text out (no I/O), so it is testable without Day 03."""
    hours, rating = summary_stats(ta.resolution_hours), summary_stats(ta.rating)
    means, counts = group_mean(ta.resolution_hours, ta.category_code, len(CATEGORY_ORDER))

    def fmt(value: Optional[float], unit: str = "") -> str:
        return "n/a" if value is None else f"{value:.2f}{unit}"

    lines = [
        "NUMERIC TICKET ANALYSIS",
        f"  Valid tickets      : {len(ta)}",
        f"  resolution_hours   : {array_info(ta.resolution_hours)}",
        f"  numeric matrix     : {array_info(ta.numeric_matrix())}",
        f"  Resolution hours   : count {hours.count}, missing {hours.missing}, mean {fmt(hours.mean)}, "
        f"median {fmt(hours.median)}, std {fmt(hours.std)}, min {fmt(hours.minimum)}, max {fmt(hours.maximum)}",
        f"  Customer rating    : count {rating.count}, missing {rating.missing}, mean {fmt(rating.mean)}, "
        f"median {fmt(rating.median)}",
        f"  High-priority open : {', '.join(ta.high_priority_open_ids()) or 'none'}",
        "  Mean hours by category (tickets with a recorded time):",
    ]
    for name, mean, count in zip(CATEGORY_ORDER, means.tolist(), counts.tolist()):
        if count:                                   # empty categories omitted, like Day 04
            lines.append(f"    {name:<10}{mean:>8.2f}   (n={count})")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ticket_numerics", description=__doc__.split("\n")[1])
    parser.add_argument("csv", help="ticket CSV file (Day 03 format)")
    args = parser.parse_args(argv)
    try:
        from ticket_numerics.bridge import arrays_from_csv
        ta = arrays_from_csv(args.csv)
    except ImportError:
        print("error: Day 03's ticket_pipeline is not installed (needs Python >= 3.11). "
              "Install it with: pip install -e ../Day-03-Python-Engineering-Practices-Exceptions-Testing",
              file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 - Day 03 errors share a base; see below
        if type(exc).__module__.startswith("ticket_pipeline") or isinstance(exc, NumericInputError):
            print(f"error: {exc}", file=sys.stderr)
            return 2
        raise                                        # a real bug must not be hidden
    try:
        print(format_report(ta))
    except NumericInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
