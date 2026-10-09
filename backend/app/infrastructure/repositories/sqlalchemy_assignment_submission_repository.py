"""Implements `AssignmentSubmissionRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`assignment_submissions` carries no UNIQUE constraint (spec Boundaries &
Constraints) — a corrected/updated status is simply a new row, mirrors
`SqlAlchemyGradeRepository`'s precedent.

`list_by_student_and_assignments` (Story 3.1) feeds the "pendente" check in
`domain/trajectory.py`: it is matched by `assignment_id`, not by its own
`date`, so a submission recorded any time on/before `as_of()` still counts —
`filter_as_of` on `date` (AD-11) is applied purely as the leak-prevention
invariant, not as a window filter."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.infrastructure.db.models import AssignmentSubmissionModel
from app.infrastructure.repositories.base import filter_as_of


class SqlAlchemyAssignmentSubmissionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
        status: AssignmentSubmissionStatus,
        date_: date,
    ) -> AssignmentSubmission:
        model = AssignmentSubmissionModel(
            assignment_id=assignment_id,
            student_id=student_id,
            status=status,
            date=date_,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return AssignmentSubmission(
            id=model.id,
            assignment_id=model.assignment_id,
            student_id=model.student_id,
            status=model.status,
            date=model.date,
        )

    def list_by_student_and_assignments(
        self, student_id: uuid.UUID, assignment_ids: list[uuid.UUID]
    ) -> list[AssignmentSubmission]:
        if not assignment_ids:
            return []
        stmt = select(AssignmentSubmissionModel).where(
            AssignmentSubmissionModel.student_id == student_id,
            AssignmentSubmissionModel.assignment_id.in_(assignment_ids),
        )
        stmt = filter_as_of(stmt, AssignmentSubmissionModel.date)
        models = self._session.execute(stmt).scalars().all()
        return [
            AssignmentSubmission(
                id=model.id,
                assignment_id=model.assignment_id,
                student_id=model.student_id,
                status=model.status,
                date=model.date,
            )
            for model in models
        ]
