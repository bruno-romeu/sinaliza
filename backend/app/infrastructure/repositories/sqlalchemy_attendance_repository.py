"""Implements `AttendanceRepositoryPort` on top of SQLAlchemy.

`save` rolls back and raises the typed translation of the DB-level
`UNIQUE(student_id, classroom_id, date)` violation (AD-7):
`UniqueViolationError`, which is still an `IntegrityError`, so
`RegisterAttendanceService` keeps translating it into
`DuplicateAttendanceError` unchanged (spec I/O Matrix, "Duplicate" /
"DB-level bypass"). The hand-written try/rollback/raise this method used to
carry alone is now `translating_integrity_errors`, shared with every other
write path in this package (`repositories/errors.py`) — which is also where
the reason the `rollback()` is required is documented: a failed flush leaves
the session's transaction merely *deactivated*, not actually rolled back yet
(`PendingRollbackError` on any further use), and the explicit call is what
puts the session back in a usable state for whatever the caller does next,
in production (the next request gets a brand-new session either way) and in
tests (a single `db_session` reused across several requests, see
`conftest.py`).

`list_by_student_in_range` (Story 3.1) additionally applies `filter_as_of`
on `date` (AD-11) — defense in depth alongside the caller-supplied
`end_date`, so a miscomputed range can never leak a record past `as_of()`.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.infrastructure.db.models import AttendanceRecordModel
from app.infrastructure.repositories.base import filter_as_of
from app.infrastructure.repositories.errors import translating_integrity_errors


class SqlAlchemyAttendanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        date_: date,
        status: AttendanceStatus,
    ) -> AttendanceRecord:
        model = AttendanceRecordModel(
            student_id=student_id,
            classroom_id=classroom_id,
            date=date_,
            status=status,
        )
        self._session.add(model)
        with translating_integrity_errors(self._session):
            self._session.commit()
        self._session.refresh(model)
        return AttendanceRecord(
            id=model.id,
            student_id=model.student_id,
            classroom_id=model.classroom_id,
            date=model.date,
            status=model.status,
        )

    def list_by_student_in_range(
        self, student_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[AttendanceRecord]:
        stmt = select(AttendanceRecordModel).where(
            AttendanceRecordModel.student_id == student_id,
            AttendanceRecordModel.date >= start_date,
            AttendanceRecordModel.date <= end_date,
        )
        stmt = filter_as_of(stmt, AttendanceRecordModel.date)
        models = self._session.execute(stmt).scalars().all()
        return [
            AttendanceRecord(
                id=model.id,
                student_id=model.student_id,
                classroom_id=model.classroom_id,
                date=model.date,
                status=model.status,
            )
            for model in models
        ]

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[AttendanceRecord]:
        """Story 3.4 — batch resolution of `TrajectoryChangeSource.source_id`
        rows for the evidence card (RNF-11)."""
        if not ids:
            return []
        stmt = select(AttendanceRecordModel).where(AttendanceRecordModel.id.in_(ids))
        stmt = filter_as_of(stmt, AttendanceRecordModel.date)
        models = self._session.execute(stmt).scalars().all()
        return [
            AttendanceRecord(
                id=model.id,
                student_id=model.student_id,
                classroom_id=model.classroom_id,
                date=model.date,
                status=model.status,
            )
            for model in models
        ]
