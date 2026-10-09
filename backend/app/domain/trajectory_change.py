"""Domain model for `TrajectoryChange`/`TrajectoryChangeSource` — pure
Python, zero framework imports (AD-2). Shapes `data-model.md:70-76` as code.

`TrajectoryChangeType` is a closed enum (data-model.md draft, revisable at
implementation time per `data-model.md:85`): exactly one of
`ATTENDANCE_DROP`/`GRADE_DROP`/`MISSING_ASSIGNMENTS_INCREASE` when exactly one
of `{ATTENDANCE, GRADE, ASSIGNMENTS}` confirms (always alongside
`PEDAGOGICAL_OBSERVATION`, since convergence needs ≥2 confirmed signals), or
`COMBINED_DETERIORATION` when ≥2 of `{ATTENDANCE, GRADE, ASSIGNMENTS}`
confirm together (see `domain/convergence.decide_change_type`).

`SourceType` mirrors `TrajectoryChangeSource.source_type` — the table each
source row actually points at (`ATTENDANCE_RECORD`, `GRADE`,
`ASSIGNMENT_SUBMISSION`, `PEDAGOGICAL_OBSERVATION`). `TrajectoryChangeSource`
is a real FK to `TrajectoryChange` (never a loose array) but its own
`source_id` is necessarily polymorphic — it points at one of four different
tables depending on `source_type`, so it cannot itself be a single DB-level
FK (data-model.md: "é FK real... não array solto" refers to
`trajectory_change_id`, the one relationship that *can* be a real FK).

`TrajectoryChange` is an immutable event once written (spec Boundaries &
Constraints): a later recomputation of the same `period_id` that no longer
converges never deletes or reverts an already-persisted row — it simply
writes nothing new for that period.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TrajectoryChangeType(str, Enum):
    ATTENDANCE_DROP = "ATTENDANCE_DROP"
    GRADE_DROP = "GRADE_DROP"
    MISSING_ASSIGNMENTS_INCREASE = "MISSING_ASSIGNMENTS_INCREASE"
    COMBINED_DETERIORATION = "COMBINED_DETERIORATION"


class SourceType(str, Enum):
    ATTENDANCE_RECORD = "ATTENDANCE_RECORD"
    GRADE = "GRADE"
    ASSIGNMENT_SUBMISSION = "ASSIGNMENT_SUBMISSION"
    PEDAGOGICAL_OBSERVATION = "PEDAGOGICAL_OBSERVATION"


@dataclass(frozen=True)
class TrajectoryChange:
    id: uuid.UUID
    student_id: uuid.UUID
    type: TrajectoryChangeType
    period_id: uuid.UUID
    detected_at: datetime
    description: str


@dataclass(frozen=True)
class TrajectoryChangeSource:
    id: uuid.UUID
    trajectory_change_id: uuid.UUID
    source_type: SourceType
    source_id: uuid.UUID
