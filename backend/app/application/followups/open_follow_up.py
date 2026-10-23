"""`OpenFollowUpService` — the application-layer entry point for
`POST /follow-ups` (Story 4.1, RF-12).

Opening a follow-up is always an explicit click: a new `TrajectoryChange`
is never auto-attached to an already-open `FollowUp` (AD-1, spec Boundaries
& Constraints). What the click does depends on what already exists
(spec-ui-1 "Acompanhamento duplicado"):

- no open (non-`ENCERRADO`) `FollowUp` for this student and responsible
  user: a brand new `FollowUp` is created, exactly as before (`created=True`);
- an open one already exists: it is reused (`created=False`). If the clicked
  change is not linked to it yet, one `FollowUpEvidence` row is added, so the
  explicit click still records the new evidence instead of silently
  dropping it; clicking again on an already-linked change writes nothing.

Before this, every click created another `FollowUp`, so a double click or a
second visit to the trajectory page left duplicate open cases.

`status` is always `EM_OBSERVACAO`; `reason`/`next_review_date` are always
`None` — no UI captures them in this story (spec Design Notes).
`responsible_user_id` is always the caller-supplied authenticated user, never
a request field (spec Boundaries & Constraints) — the router is responsible
for sourcing it from `get_current_user`, never this service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.followups.errors import (
    TrajectoryChangeMismatchError,
    TrajectoryChangeNotFoundError,
)
from app.application.followups.ports import FollowUpRepositoryPort, TrajectoryChangeRepositoryPort
from app.domain.follow_up import FollowUp, FollowUpEvidence, FollowUpStatus


@dataclass(frozen=True)
class OpenFollowUpResult:
    follow_up: FollowUp
    created: bool


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
    ) -> OpenFollowUpResult:
        change = self._trajectory_change_repository.get_by_id(trajectory_change_id)
        if change is None:
            raise TrajectoryChangeNotFoundError()
        if change.student_id != student_id:
            raise TrajectoryChangeMismatchError()

        existing = self._follow_up_repository.find_open_for_student(
            student_id, responsible_user_id
        )
        if existing is not None:
            linked = {
                item.trajectory_change_id
                for item in self._follow_up_repository.list_evidence_by_follow_up(existing.id)
            }
            if trajectory_change_id not in linked:
                self._follow_up_repository.add_evidence(
                    FollowUpEvidence(
                        id=uuid.uuid4(),
                        follow_up_id=existing.id,
                        trajectory_change_id=trajectory_change_id,
                    )
                )
            return OpenFollowUpResult(follow_up=existing, created=False)

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
        saved = self._follow_up_repository.save_with_evidence(follow_up, evidence)
        return OpenFollowUpResult(follow_up=saved, created=True)
