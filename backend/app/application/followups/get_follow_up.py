"""`GetFollowUpService` — the application-layer entry point for
`GET /follow-ups/{id}` (Story 4.1, RF-20; extended Story 4.3, RF-14/RF-20).

Evidence resolution reuses Story 3.4's existing reads
(`application/trajectory/evidence.resolve_evidence`). Story 4.4 adds
`requesting_user_id`-scoped `PedagogicalObservation` visibility — the
filter itself lives in `SqlAlchemyPedagogicalObservationRepository
.get_by_ids`, never inline here (AD-11); this service only threads the
caller's identity through.

Story 4.3 groups evidence per linked `TrajectoryChange` instead of returning
a single flat list: `list_evidence_by_follow_up` already orders its rows by
the linked change's `detected_at` (repository layer), so iterating it in
order and loading each `TrajectoryChange` via `TrajectoryChangeRepositoryPort
.get_by_id` yields groups already ordered by `detected_at` ascending (spec
Boundaries & Constraints). Story 4.1 always has exactly one
`FollowUpEvidence` row per `FollowUp`, but this never assumes that — a future
story that adds more never needs this service rewritten.

Also surfaces every `FollowUpAction` in chronological order (oldest first,
spec Boundaries & Constraints) — the repository already returns them sorted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.followups.errors import FollowUpNotFoundError
from app.application.followups.ports import (
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    FollowUpRepositoryPort,
    GradeRepositoryPort,
    PedagogicalObservationRepositoryPort,
    StudentRepositoryPort,
    TrajectoryChangeRepositoryPort,
    TrajectoryChangeSourceRepositoryPort,
)
from app.application.trajectory.evidence import EvidenceItem, resolve_evidence
from app.domain.follow_up import FollowUp, FollowUpAction
from app.domain.trajectory_change import TrajectoryChange


@dataclass(frozen=True)
class TrajectoryChangeEvidenceGroup:
    trajectory_change: TrajectoryChange
    evidence: list[EvidenceItem]


@dataclass(frozen=True)
class FollowUpDetailResult:
    follow_up: FollowUp
    student_name: str
    actions: list[FollowUpAction]
    trajectory_changes: list[TrajectoryChangeEvidenceGroup]


class GetFollowUpService:
    def __init__(
        self,
        follow_up_repository: FollowUpRepositoryPort,
        student_repository: StudentRepositoryPort,
        trajectory_change_repository: TrajectoryChangeRepositoryPort,
        trajectory_change_source_repository: TrajectoryChangeSourceRepositoryPort,
        attendance_repository: AttendanceRepositoryPort,
        grade_repository: GradeRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
        pedagogical_observation_repository: PedagogicalObservationRepositoryPort,
    ) -> None:
        self._follow_up_repository = follow_up_repository
        self._student_repository = student_repository
        self._trajectory_change_repository = trajectory_change_repository
        self._trajectory_change_source_repository = trajectory_change_source_repository
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._pedagogical_observation_repository = pedagogical_observation_repository

    def execute(
        self, follow_up_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> FollowUpDetailResult:
        follow_up = self._follow_up_repository.get_by_id(follow_up_id)
        if follow_up is None:
            raise FollowUpNotFoundError()

        student = self._student_repository.get_by_id(follow_up.student_id)
        student_name = student.name if student is not None else ""

        actions = self._follow_up_repository.list_actions_by_follow_up(follow_up_id)

        evidence_rows = self._follow_up_repository.list_evidence_by_follow_up(follow_up_id)
        trajectory_changes: list[TrajectoryChangeEvidenceGroup] = []
        for row in evidence_rows:
            change = self._trajectory_change_repository.get_by_id(row.trajectory_change_id)
            if change is None:
                continue
            evidence = resolve_evidence(
                row.trajectory_change_id,
                source_repo=self._trajectory_change_source_repository,
                attendance_repo=self._attendance_repository,
                grade_repo=self._grade_repository,
                submission_repo=self._assignment_submission_repository,
                observation_repo=self._pedagogical_observation_repository,
                requesting_user_id=requesting_user_id,
            )
            trajectory_changes.append(
                TrajectoryChangeEvidenceGroup(trajectory_change=change, evidence=evidence)
            )

        return FollowUpDetailResult(
            follow_up=follow_up,
            student_name=student_name,
            actions=actions,
            trajectory_changes=trajectory_changes,
        )
