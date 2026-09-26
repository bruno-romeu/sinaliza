"""Domain model for `AssignmentSubmission` — pure Python, zero framework
imports (AD-2).

`status` is a fixed, closed enum (spec Boundaries & Constraints) — same
native-Postgres-enum + `Literal[...]` pattern as `AttendanceRecord.status`
(AD-10).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum


class AssignmentSubmissionStatus(str, Enum):
    DELIVERED = "DELIVERED"
    NOT_DELIVERED = "NOT_DELIVERED"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class AssignmentSubmission:
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: AssignmentSubmissionStatus
    date: date
