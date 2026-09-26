"""Implements `AssignmentSubmissionRepositoryPort` on top of SQLAlchemy.

`save` never needs to translate an `IntegrityError` into a domain error —
`assignment_submissions` carries no UNIQUE constraint (spec Boundaries &
Constraints) — a corrected/updated status is simply a new row, mirrors
`SqlAlchemyGradeRepository`'s precedent.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.infrastructure.db.models import AssignmentSubmissionModel


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
