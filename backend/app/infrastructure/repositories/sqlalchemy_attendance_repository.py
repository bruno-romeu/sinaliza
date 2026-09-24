"""Implements `AttendanceRepositoryPort` on top of SQLAlchemy.

`save` lets `IntegrityError` (the DB-level `UNIQUE(student_id, classroom_id,
date)` violation, AD-7) propagate to the caller after rolling back, so
`RegisterAttendanceService` can translate it into `DuplicateAttendanceError`
(spec I/O Matrix, "Duplicate" / "DB-level bypass"). The `rollback()` is
required — a failed flush leaves the session's transaction merely
*deactivated*, not actually rolled back yet (`PendingRollbackError` on any
further use); the explicit call here is what puts the session back in a
usable state for whatever the caller does next, in production (the next
request gets a brand-new session either way) and in tests (a single
`db_session` reused across several requests, see `conftest.py`)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.infrastructure.db.models import AttendanceRecordModel


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
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(model)
        return AttendanceRecord(
            id=model.id,
            student_id=model.student_id,
            classroom_id=model.classroom_id,
            date=model.date,
            status=model.status,
        )
