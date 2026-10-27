"""`RegisterObservationService` — the one and only path that writes a
`PedagogicalObservation` (spec Boundaries & Constraints: "the write goes
through one application-service method... never a router assigning fields
directly").

Checks the classroom exists first, then that the student is actually
enrolled in it — same order and status codes as
`RegisterGradeService`/`RegisterAttendanceService`'s precedent (spec
Boundaries & Constraints, I/O Matrix). `classroom_id` is validation-only: it
runs the same enrollment gate reused everywhere else in the epic, then is
discarded — never persisted on `PedagogicalObservation` (spec Design Notes,
data-model.md's fixed shape). `created_at` is computed here, server-side,
at the moment of the actual write — never accepted from the caller (spec
Boundaries & Constraints: "created_at is set server-side
(`datetime.now(UTC)`), never client-supplied").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.attendance.ports import ClassroomRepositoryPort, StudentRepositoryPort
from app.application.observations.errors import ClassroomNotFoundError, StudentNotEnrolledError
from app.application.observations.ports import PedagogicalObservationRepositoryPort
from app.domain.pedagogical_observation import PedagogicalObservation


class RegisterObservationService:
    def __init__(
        self,
        classroom_repository: ClassroomRepositoryPort,
        student_repository: StudentRepositoryPort,
        observation_repository: PedagogicalObservationRepositoryPort,
    ) -> None:
        self._classroom_repository = classroom_repository
        self._student_repository = student_repository
        self._observation_repository = observation_repository

    def execute(
        self,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
        text: str,
        author_user_id: uuid.UUID,
        registers_concern: bool = False,
    ) -> PedagogicalObservation:
        if self._classroom_repository.get_by_id(classroom_id) is None:
            raise ClassroomNotFoundError()

        if not self._student_repository.exists_enrollment(student_id, classroom_id):
            raise StudentNotEnrolledError()

        return self._observation_repository.save(
            student_id=student_id,
            author_user_id=author_user_id,
            text=text,
            created_at=datetime.now(UTC),
            registers_concern=registers_concern,
        )
