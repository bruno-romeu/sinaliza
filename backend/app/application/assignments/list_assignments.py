"""`ListAssignmentsByClassroomService` — lists every `Assignment` registered
for a given classroom (`EVAL_DEMO` split concerns don't apply here —
`Assignment` isn't student-scoped — but the classroom existence check
mirrors `ListEnrolledStudentsService`'s precedent).

This listing is the read-back endpoint the story needs internally, to
populate the atividade `<select>` before status-de-entrega registration can
happen at all (spec Design Notes: "Assignment selection surfaces via a live
list, not a second navigation").
"""

from __future__ import annotations

import uuid

from app.application.assignments.errors import ClassroomNotFoundError
from app.application.assignments.ports import AssignmentRepositoryPort
from app.application.attendance.ports import ClassroomRepositoryPort
from app.domain.assignment import Assignment


class ListAssignmentsByClassroomService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        assignment_repository: AssignmentRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._assignment_repository = assignment_repository

    def execute(self, classroom_id: uuid.UUID) -> list[Assignment]:
        if self._classroom_repository.get_by_id(classroom_id) is None:
            raise ClassroomNotFoundError()

        return self._assignment_repository.list_by_classroom(classroom_id)
