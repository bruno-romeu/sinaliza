"""Implements `GradeRepositoryPort` on top of SQLAlchemy.

Unlike `SqlAlchemyAttendanceRepository`, `save` never needs to translate an
`IntegrityError` into a domain error — `grades` carries no UNIQUE constraint
(spec Boundaries & Constraints), so the only constraint that can fail at
write time is the `ck_grade_value_range` CHECK, which is already unreachable
here because `RegisterGradeService`'s caller validates `value` via Pydantic
before this is ever called (spec I/O Matrix).

`list_by_student_and_periods` (Story 3.1) reads grades for the current and
previous `AcademicPeriod` at once (`grade_average`/`grade_trend` follow
`Grade.period_id`, not the rolling window — spec Boundaries & Constraints)
and applies `filter_as_of` on `date` (AD-11) as defense in depth."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.grade import Grade
from app.infrastructure.db.models import GradeModel
from app.infrastructure.repositories.base import filter_as_of


def _to_domain(model: GradeModel) -> Grade:
    return Grade(
        id=model.id,
        student_id=model.student_id,
        classroom_id=model.classroom_id,
        subject=model.subject,
        period_id=model.period_id,
        date=model.date,
        value=model.value,
    )


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
        return _to_domain(model)

    def list_by_student_and_periods(
        self, student_id: uuid.UUID, period_ids: list[uuid.UUID]
    ) -> list[Grade]:
        if not period_ids:
            return []
        stmt = select(GradeModel).where(
            GradeModel.student_id == student_id,
            GradeModel.period_id.in_(period_ids),
        )
        stmt = filter_as_of(stmt, GradeModel.date)
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]
