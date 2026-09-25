"""Ports (interfaces) the `application/assignments` layer depends on.

`ClassroomRepositoryPort`/`StudentRepositoryPort` (from
`application/attendance/ports.py`) and `AcademicPeriodRepositoryPort` (from
`application/academic_periods/ports.py`) are reused as-is (spec Code Map:
"import only, no changes") — only `AssignmentRepositoryPort` and
`AssignmentSubmissionRepositoryPort` are new here.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus


class AssignmentRepositoryPort(Protocol):
    def save(
        self,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        due_date: date,
    ) -> Assignment: ...

    def get_by_id(self, assignment_id: uuid.UUID) -> Assignment | None: ...

    def list_by_classroom(self, classroom_id: uuid.UUID) -> list[Assignment]: ...


class AssignmentSubmissionRepositoryPort(Protocol):
    def save(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
        status: AssignmentSubmissionStatus,
        date_: date,
    ) -> AssignmentSubmission: ...
