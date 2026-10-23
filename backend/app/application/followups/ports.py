"""Ports (interfaces) the `application/followups` layer depends on.

`application/` only ever sees these Protocols — never a concrete class from
`infrastructure/` (AD-2). Re-imports the read ports already defined in
`application/trajectory/ports.py` rather than redeclaring duplicate
Protocols (spec Code Map) — `GetFollowUpService` needs the exact same shapes
`resolve_evidence` depends on.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.application.trajectory.ports import (
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    GradeRepositoryPort,
    PedagogicalObservationRepositoryPort,
    StudentRepositoryPort,
    TrajectoryChangeRepositoryPort,
    TrajectoryChangeSourceRepositoryPort,
)
from app.domain.follow_up import FollowUp, FollowUpAction, FollowUpEvidence, FollowUpStatus

__all__ = [
    "AssignmentSubmissionRepositoryPort",
    "AttendanceRepositoryPort",
    "GradeRepositoryPort",
    "PedagogicalObservationRepositoryPort",
    "StudentRepositoryPort",
    "TrajectoryChangeRepositoryPort",
    "TrajectoryChangeSourceRepositoryPort",
    "FollowUpRepositoryPort",
]


class FollowUpRepositoryPort(Protocol):
    def save_with_evidence(
        self, follow_up: FollowUp, evidence: list[FollowUpEvidence]
    ) -> FollowUp:
        """Inserts `follow_up` + every `FollowUpEvidence` row in one
        transaction (spec Boundaries & Constraints, same atomicity pattern as
        `TrajectoryChange`+`TrajectoryChangeSource`, AD-7)."""
        ...

    def find_open_for_student(
        self, student_id: uuid.UUID, responsible_user_id: uuid.UUID
    ) -> FollowUp | None:
        """The most recent non-`ENCERRADO` `FollowUp` for this student whose
        responsible user is `responsible_user_id`, or `None` (spec-ui-1).
        Scoped to the responsible user because writes on a `FollowUp` are
        (RF-22, epic-4-retro-item-18)."""
        ...

    def add_evidence(self, evidence: FollowUpEvidence) -> FollowUpEvidence:
        """Plain insert+commit of one extra `FollowUpEvidence` row on an
        existing `FollowUp` (spec-ui-1)."""
        ...

    def get_by_id(self, follow_up_id: uuid.UUID) -> FollowUp | None:
        """Loads one `FollowUp` by id for `GetFollowUpService` — `None` when
        it does not exist (spec I/O Matrix, "Nonexistent follow-up")."""
        ...

    def list_evidence_by_follow_up(self, follow_up_id: uuid.UUID) -> list[FollowUpEvidence]:
        """Every `FollowUpEvidence` row attached to one `FollowUp`, ordered by
        its linked `TrajectoryChange.detected_at` ascending (then `id`
        ascending as a deterministic tiebreak) so `GetFollowUpService` can
        group/order evidence by `detected_at` without a second query (spec
        Boundaries & Constraints, RF-14/RF-20; story 4.1 always has exactly
        one, future stories may add more)."""
        ...

    def list_actions_by_follow_up(self, follow_up_id: uuid.UUID) -> list[FollowUpAction]:
        """Every `FollowUpAction` row attached to one `FollowUp`, ordered by
        `created_at` ascending (then `id` ascending as a deterministic
        tiebreak) — oldest first, matching "histórico" (spec Boundaries &
        Constraints, RF-14)."""
        ...

    def add_action(self, action: FollowUpAction) -> FollowUpAction:
        """Plain insert+commit of a new `FollowUpAction` row — every call
        appends, never replaces a prior row (spec Boundaries & Constraints,
        RF-13/RF-14)."""
        ...

    def update_status(
        self, follow_up_id: uuid.UUID, status: FollowUpStatus
    ) -> FollowUp | None:
        """UPDATE scoped to the `status` column only. Returns `None` when
        `follow_up_id` does not exist so `ChangeFollowUpStatusService` can
        raise `FollowUpNotFoundError` without a prior extra read (spec Code
        Map, mirrors `get_by_id`'s existing `| None` contract)."""
        ...
