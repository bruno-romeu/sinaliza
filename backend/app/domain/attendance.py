"""Domain model for `AttendanceRecord` — pure Python, zero framework imports
(AD-2).

`status` is a fixed, closed enum (AD-10) — not a boolean `present` — but
RF-11 counts justified and unjustified absences equally in trend
calculation for the MVP; the distinction is recorded for future use, not
used in detection math yet (out of scope for this story).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT_JUSTIFIED = "ABSENT_JUSTIFIED"
    ABSENT_UNJUSTIFIED = "ABSENT_UNJUSTIFIED"


@dataclass(frozen=True)
class AttendanceRecord:
    id: uuid.UUID
    student_id: uuid.UUID
    classroom_id: uuid.UUID
    date: date
    status: AttendanceStatus
