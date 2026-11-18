"""
Optional bridge to Day 03: load real tickets through Day 03's pipeline, then
build arrays. All reading/validation/cleaning stays in Day 03 (not copied).
Needs Python >= 3.11 and Day 03's ``ticket_pipeline`` installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from ticket_numerics.arrays import TicketArrays, from_tickets


def arrays_from_csv(path: Union[str, Path]) -> TicketArrays:
    """Valid tickets of ``path`` (rejected rows are dropped, as in Day 03) as arrays."""
    from ticket_pipeline.config import PipelineConfig      # imported lazily on purpose
    from ticket_pipeline.pipeline import run_pipeline

    result = run_pipeline(PipelineConfig(input_path=Path(path)))
    return from_tickets(result.tickets)
