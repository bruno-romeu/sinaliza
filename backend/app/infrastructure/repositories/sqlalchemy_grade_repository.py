"""Implements `GradeRepositoryPort` on top of SQLAlchemy.

Unlike `SqlAlchemyAttendanceRepository`, `save` never needs to translate an
`IntegrityError` into a domain error — `grades` carries no UNIQUE constraint
(spec Boundaries & Constraints), so the only constraint that can fail at
write time is the `ck_grade_value_range` CHECK, which is already unreachable
here because `RegisterGradeService`'s caller validates `value` via Pydantic
before this is ever called (spec I/O Matrix)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.grade import Grade
from app.infrastructure.db.models import GradeModel


class SqlAlchemyGradeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        subject: str,
        period_id: uuid.UUID,
        date_: date,
        value: Decimal,
    ) -> Grade:
        model = GradeModel(
            student_id=student_id,
            classroom_id=classroom_id,
            subject=subject,
            period_id=period_id,
            date=date_,
            value=value,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return Grade(
            id=model.id,
            student_id=model.student_id,
            classroom_id=model.classroom_id,
            subject=model.subject,
            period_id=model.period_id,
            date=model.date,
            value=model.value,
        )
