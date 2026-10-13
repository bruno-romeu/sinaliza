"""Ports (interfaces) the `application/trajectory` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). Concrete adapters are wired up in `composition.py`
(the composition root) and injected here. None of these are reused from
`application/attendance`/`application/grades`/`application/assignments` as-is
— every method here is a new, trajectory-specific read shape (AD-11's
`filter_as_of` applied underneath each implementation).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from app.domain.academic_period import AcademicPeriod
from app.domain.assignment import Assignment
from app.domain.assignment_submission import AssignmentSubmission
from app.domain.attendance import AttendanceRecord
from app.domain.grade import Grade
from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.student import Student
from app.domain.trajectory_change import TrajectoryChange, TrajectoryChangeSource


class StudentRepositoryPort(Protocol):
    def get_by_id(self, student_id: uuid.UUID) -> Student | None: ...


class AttendanceRepositoryPort(Protocol):
    def list_by_student_in_range(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[AttendanceRecord]: ...

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[AttendanceRecord]:
        """Story 3.4 — batch-resolves `TrajectoryChangeSource.source_id` rows
        of type `ATTENDANCE_RECORD` into real records for the evidence card
        (never a free-text-only citation, RNF-11)."""
        ...


class GradeRepositoryPort(Protocol):
    def list_by_student_and_periods(
        self, student_id: uuid.UUID, period_ids: list[uuid.UUID]
    ) -> list[Grade]: ...

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[Grade]:
        """Story 3.4 — batch-resolves `TrajectoryChangeSource.source_id` rows
        of type `GRADE` into real records for the evidence card."""
        ...


class AssignmentRepositoryPort(Protocol):
    def list_due_in_range_for_student(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[Assignment]: ...


class AssignmentSubmissionRepositoryPort(Protocol):
    def list_by_student_and_assignments(
        self, student_id: uuid.UUID, assignment_ids: list[uuid.UUID]
    ) -> list[AssignmentSubmission]: ...

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[AssignmentSubmission]:
        """Story 3.4 — batch-resolves `TrajectoryChangeSource.source_id` rows
        of type `ASSIGNMENT_SUBMISSION` into real records for the evidence
        card."""
        ...


class AcademicPeriodRepositoryPort(Protocol):
    def list_all(self) -> list[AcademicPeriod]: ...


class PedagogicalObservationRepositoryPort(Protocol):
    def list_by_student_in_range(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[PedagogicalObservation]: ...

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[PedagogicalObservation]:
        """Story 3.4 — batch-resolves `TrajectoryChangeSource.source_id` rows
        of type `PEDAGOGICAL_OBSERVATION` into real records for the evidence
        card."""
        ...


class TrajectoryChangeRepositoryPort(Protocol):
    def upsert(
        self, change: TrajectoryChange, sources: list[TrajectoryChangeSource]
    ) -> TrajectoryChange:
        """Upserts `change` by its `(student_id, type, period_id)` key via
        `INSERT ... ON CONFLICT ... DO UPDATE` — never `SELECT`-then-write
        (AD-1, RF-11). Always `DO UPDATE` unconditionally — no freeze-on-
        evidence guard in this story (spec Never, `deferred-work.md`: Epic 4
        adds the `NOT EXISTS (follow_up_evidence)` guard once that table
        exists). `sources` fully replaces whatever `TrajectoryChangeSource`
        rows already existed for this change (delete+reinsert), in the same
        transaction as the upsert itself (RNF-11: never without a source)."""
        ...


class TrajectoryChangeSourceRepositoryPort(Protocol):
    def list_sources_by_change(self, change_id: uuid.UUID) -> list[TrajectoryChangeSource]:
        """Story 3.4 — every `TrajectoryChangeSource` row attached to one
        `TrajectoryChange`, used by `GetStudentTrajectoryDetailService` to
        resolve the evidence card's real source records (RNF-11: never a
        free-text-only "AI flagged this")."""
        ...
