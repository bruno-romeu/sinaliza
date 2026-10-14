"""`OpenFollowUpService` — the application-layer entry point for
`POST /follow-ups` (Story 4.1, RF-12).

Opening a follow-up is always an explicit click — never auto-attached when a
new `TrajectoryChange` later appears for an already-open `FollowUp` (AD-1,
spec Boundaries & Constraints). This service only ever creates a brand new
`FollowUp` row; it never looks up or reuses an existing one for the same
student/change.

`status` is always `EM_OBSERVACAO`; `reason`/`next_review_date` are always
`None` — no UI captures them in this story (spec Design Notes).
`responsible_user_id` is always the caller-supplied authenticated user, never
a request field (spec Boundaries & Constraints) — the router is responsible
for sourcing it from `get_current_user`, never this service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.followups.errors import (
    TrajectoryChangeMismatchError,
    TrajectoryChangeNotFoundError,
)
from app.application.followups.ports import FollowUpRepositoryPort, TrajectoryChangeRepositoryPort
from app.domain.follow_up import FollowUp, FollowUpEvidence, FollowUpStatus


class OpenFollowUpService:
    def __init__(
        self,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        follow_up_repository: FollowUpRepositoryPort,
    ) -> None:
        self._trajectory_change_repository = trajectory_change_repository
        self._follow_up_repository = follow_up_repository

    def execute(
        self,
        student_id: uuid.UUID,
        trajectory_change_id: uuid.UUID,
        responsible_user_id: uuid.UUID,
    ) -> FollowUp:
        change = self._trajectory_change_repository.get_by_id(trajectory_change_id)
        if change is None:
            raise TrajectoryChangeNotFoundError()
        if change.student_id != student_id:
            raise TrajectoryChangeMismatchError()

        follow_up = FollowUp(
            id=uuid.uuid4(),
            student_id=student_id,
            status=FollowUpStatus.EM_OBSERVACAO,
            reason=None,
            responsible_user_id=responsible_user_id,
            next_review_date=None,
            created_at=datetime.now(UTC),
        )
        evidence = [
            FollowUpEvidence(
                id=uuid.uuid4(),
                follow_up_id=follow_up.id,
                trajectory_change_id=trajectory_change_id,
            )
        ]
        return self._follow_up_repository.save_with_evidence(follow_up, evidence)
