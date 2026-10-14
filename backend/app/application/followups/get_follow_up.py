"""`GetFollowUpService` — the application-layer entry point for
`GET /follow-ups/{id}` (Story 4.1, RF-20).

Evidence resolution reuses Story 3.4's existing, unfiltered reads as-is
(`application/trajectory/evidence.resolve_evidence`) — never filters
`PedagogicalObservation` visibility here (spec Never: Story 4.4 scope).
Story 4.1 always has exactly one `FollowUpEvidence` row per `FollowUp`, but
this concatenates across every linked `trajectory_change_id` so a future
story that adds more never needs this service rewritten.
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
    TrajectoryChangeSourceRepositoryPort,
)
from app.application.trajectory.evidence import EvidenceItem, resolve_evidence
from app.domain.follow_up import FollowUp


@dataclass(frozen=True)
class FollowUpDetailResult:
    follow_up: FollowUp
    student_name: str
    evidence: list[EvidenceItem]


class GetFollowUpService:
    def __init__(
        self,
        follow_up_repository: FollowUpRepositoryPort,
        student_repository: StudentRepositoryPort,
        trajectory_change_source_repository: TrajectoryChangeSourceRepositoryPort,
        attendance_repository: AttendanceRepositoryPort,
        grade_repository: GradeRepositoryPort,
        assignment_submission_repository: AssignmentSubmissionRepositoryPort,
        pedagogical_observation_repository: PedagogicalObservationRepositoryPort,
    ) -> None:
        self._follow_up_repository = follow_up_repository
        self._student_repository = student_repository
        self._trajectory_change_source_repository = trajectory_change_source_repository
        self._attendance_repository = attendance_repository
        self._grade_repository = grade_repository
        self._assignment_submission_repository = assignment_submission_repository
        self._pedagogical_observation_repository = pedagogical_observation_repository

    def execute(self, follow_up_id: uuid.UUID) -> FollowUpDetailResult:
        follow_up = self._follow_up_repository.get_by_id(follow_up_id)
        if follow_up is None:
            raise FollowUpNotFoundError()

        student = self._student_repository.get_by_id(follow_up.student_id)
        student_name = student.name if student is not None else ""

        evidence_rows = self._follow_up_repository.list_evidence_by_follow_up(follow_up_id)
        evidence: list[EvidenceItem] = []
        for row in evidence_rows:
            evidence.extend(
                resolve_evidence(
                    row.trajectory_change_id,
                    source_repo=self._trajectory_change_source_repository,
                    attendance_repo=self._attendance_repository,
                    grade_repo=self._grade_repository,
                    submission_repo=self._assignment_submission_repository,
                    observation_repo=self._pedagogical_observation_repository,
                )
            )

        return FollowUpDetailResult(follow_up=follow_up, student_name=student_name, evidence=evidence)
