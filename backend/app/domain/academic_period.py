"""Domain model for `AcademicPeriod` — pure Python, zero framework imports
(AD-2).

Dev-fixture seeded only (extends `seed_dev_fixtures.py`) — there is no
registration screen for it (spec Boundaries & Constraints). It is the
context used by `Grade` and by matrícula; it is *not* the granularity used
to calculate trajectory (`data-model.md`, `TrajectorySnapshot` uses a
rolling window instead).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AcademicPeriod:
    id: uuid.UUID
    label: str
    start_date: date
    end_date: date
    order_index: int
