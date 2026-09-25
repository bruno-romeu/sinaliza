"""`RegisterSubmissionService` — the one and only path that writes an
`AssignmentSubmission` (spec Boundaries & Constraints: "assignment and
submission writes go through one application-service method each... never a
router assigning fields directly").

Checks the assignment exists first, then that the student is actually
enrolled in *the assignment's own classroom* (not an arbitrary one) — same
`exists_enrollment` port reused from `attendance`/`grades` (spec Boundaries &
Constraints, I/O Matrix). No duplicate-submission rejection:
`AssignmentSubmission` carries no UNIQUE constraint and no AC requires one
(spec Boundaries & Constraints) — a corrected/updated status is simply a new
row.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.application.assignments.errors import AssignmentNotFoundError, StudentNotEnrolledError
from app.application.assignments.ports import AssignmentRepositoryPort, AssignmentSubmissionRepositoryPort
from app.application.attendance.ports import StudentRepositoryPort
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus


class RegisterSubmissionService:
    def __init__(
        self,
        assignment_repository: AssignmentRepositoryPort,
        student_repository: StudentRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
    ) -> None:
        self._assignment_repository = assignment_repository
        self._student_repository = student_repository
        self._assignment_submission_repository = assignment_submission_repository

    def execute(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
        status: AssignmentSubmissionStatus,
        date_: date,
    ) -> AssignmentSubmission:
        assignment = self._assignment_repository.get_by_id(assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError()

        if not self._student_repository.exists_enrollment(student_id, assignment.classroom_id):
            raise StudentNotEnrolledError()

        return self._assignment_submission_repository.save(
            assignment_id=assignment_id,
            student_id=student_id,
            status=status,
            date_=date_,
        )
