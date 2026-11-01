"""Implements `GradeRepositoryPort` on top of SQLAlchemy.

`grades` carries no UNIQUE constraint (spec Boundaries & Constraints), and
the `ck_grade_value_range` CHECK is already unreachable here because
`RegisterGradeService`'s caller validates `value` via Pydantic before this is
ever called (spec I/O Matrix) — but the FKs (`student_id`, `classroom_id`,
`period_id`) remain violable, so `save` goes through
`translating_integrity_errors` like every other write path here: the session
is rolled back and the violation surfaces as a typed
`ForeignKeyViolationError`/`CheckViolationError` instead of a raw
`IntegrityError` over a poisoned session (`repositories/errors.py`).

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
from app.infrastructure.repositories.errors import translating_integrity_errors


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
        with translating_integrity_errors(self._session):
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

    def get_by_ids(self, ids: list[uuid.UUID]) -> list[Grade]:
        """Story 3.4 — batch resolution of `TrajectoryChangeSource.source_id`
        rows for the evidence card (RNF-11)."""
        if not ids:
            return []
        stmt = select(GradeModel).where(GradeModel.id.in_(ids))
        stmt = filter_as_of(stmt, GradeModel.date)
        models = self._session.execute(stmt).scalars().all()
        return [_to_domain(model) for model in models]
