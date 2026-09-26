"""Domain model for `Grade` — pure Python, zero framework imports (AD-2).

`value` is `Decimal` on a fixed 0.0–10.0 scale (AD-10) with no derived
approval/failure field — no RF requires that semantics. There is no
`Assessment` entity: `subject`/`date` live directly on `Grade`
(`data-model.md`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Grade:
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    subject: str
    period_id: uuid.UUID
    date: date
    value: Decimal
