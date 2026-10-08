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
`db_session` reused across several requests, see `conftest.py`).

`list_by_student_in_range` (Story 3.1) additionally applies `filter_as_of`
on `date` (AD-11) — defense in depth alongside the caller-supplied
`end_date`, so a miscomputed range can never leak a record past `as_of()`.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.infrastructure.db.models import AttendanceRecordModel
from app.infrastructure.repositories.base import filter_as_of


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
