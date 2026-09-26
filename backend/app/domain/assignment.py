"""Domain model for `Assignment` — pure Python, zero framework imports
(AD-2).

Mirrors `Grade`'s shape: no CHECK/UNIQUE beyond FK integrity — no AC
requires dedup (spec Boundaries & Constraints).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Assignment:
    id: uuid.UUID
    classroom_id: uuid.UUID
    subject: str
    period_id: uuid.UUID
    due_date: date
