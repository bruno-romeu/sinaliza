"""Shared evidence resolution — extracted out of
`get_student_trajectory_detail.py`'s `_resolve_evidence`/
`_resolve_items_for_type`/description-helper methods verbatim (spec Code
Map), so `GetStudentTrajectoryDetailService` and the new `GetFollowUpService`
(Story 4.1) genuinely share one resolution path, not two.

Batch-resolves `TrajectoryChangeSource` rows for a `trajectory_change_id`
into factual PT-BR descriptions (RNF-11: never a free-text-only "AI flagged
this"), in the same deterministic per-`source_type` order as
`domain/convergence.py`'s `_DESCRIPTION_ORDER` (RNF-09).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.application.trajectory.ports import (
    AssignmentSubmissionRepositoryPort,
    AttendanceRepositoryPort,
    GradeRepositoryPort,
    PedagogicalObservationRepositoryPort,
    TrajectoryChangeSourceRepositoryPort,
)
from app.domain.assignment_submission import AssignmentSubmission, AssignmentSubmissionStatus
from app.domain.attendance import AttendanceRecord, AttendanceStatus
from app.domain.grade import Grade
from app.domain.pedagogical_observation import PedagogicalObservation
from app.domain.trajectory_change import SourceType

# Deterministic evidence ordering — mirrors `domain/convergence.py`'s
# `_DESCRIPTION_ORDER` so the same confirmed sources always render in the
# same order (RNF-09), independent of query/set iteration order.
_SOURCE_TYPE_ORDER: tuple[SourceType, ...] = (
    SourceType.ATTENDANCE_RECORD,
    SourceType.GRADE,
    SourceType.ASSIGNMENT_SUBMISSION,
    SourceType.PEDAGOGICAL_OBSERVATION,
)

_ATTENDANCE_STATUS_LABEL: dict[AttendanceStatus, str] = {
    AttendanceStatus.PRESENT: "Presença registrada",
    AttendanceStatus.ABSENT_JUSTIFIED: "Falta justificada",
    AttendanceStatus.ABSENT_UNJUSTIFIED: "Falta não justificada",
}

_SUBMISSION_STATUS_LABEL: dict[AssignmentSubmissionStatus, str] = {
    AssignmentSubmissionStatus.DELIVERED: "Atividade entregue",
    AssignmentSubmissionStatus.NOT_DELIVERED: "Atividade não entregue",
    AssignmentSubmissionStatus.PARTIAL: "Atividade entregue parcialmente",
}


def _format_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


@dataclass(frozen=True)
class EvidenceItem:
    source_type: SourceType
    description: str
    date: date


def resolve_evidence(
    trajectory_change_id: uuid.UUID,
    source_repo: TrajectoryChangeSourceRepositoryPort,
    attendance_repo: AttendanceRepositoryPort,
    grade_repo: GradeRepositoryPort,
    submission_repo: AssignmentSubmissionRepositoryPort,
    observation_repo: PedagogicalObservationRepositoryPort,
) -> list[EvidenceItem]:
    sources = source_repo.list_sources_by_change(trajectory_change_id)
    ids_by_type: dict[SourceType, list[uuid.UUID]] = {}
    for source in sources:
        ids_by_type.setdefault(source.source_type, []).append(source.source_id)

    items: list[EvidenceItem] = []
    for source_type in _SOURCE_TYPE_ORDER:
        ids = ids_by_type.get(source_type)
        if not ids:
            continue
        items.extend(
            _resolve_items_for_type(
                source_type, ids, attendance_repo, grade_repo, submission_repo, observation_repo
            )
        )
    return items


def _resolve_items_for_type(
    source_type: SourceType,
    ids: list[uuid.UUID],
    attendance_repo: AttendanceRepositoryPort,
    grade_repo: GradeRepositoryPort,
    submission_repo: AssignmentSubmissionRepositoryPort,
    observation_repo: PedagogicalObservationRepositoryPort,
) -> list[EvidenceItem]:
    if source_type == SourceType.ATTENDANCE_RECORD:
        records = attendance_repo.get_by_ids(ids)
        items = [
            EvidenceItem(
                source_type=source_type,
                description=_attendance_description(record),
                date=record.date,
            )
            for record in records
        ]
    elif source_type == SourceType.GRADE:
        grades = grade_repo.get_by_ids(ids)
        items = [
            EvidenceItem(
                source_type=source_type,
                description=_grade_description(grade),
                date=grade.date,
            )
            for grade in grades
        ]
    elif source_type == SourceType.ASSIGNMENT_SUBMISSION:
        submissions = submission_repo.get_by_ids(ids)
        items = [
            EvidenceItem(
                source_type=source_type,
                description=_assignment_submission_description(submission),
                date=submission.date,
            )
            for submission in submissions
        ]
    else:
        observations = observation_repo.get_by_ids(ids)
        items = [
            EvidenceItem(
                source_type=source_type,
                description=_observation_description(observation),
                date=observation.created_at.date(),
            )
            for observation in observations
        ]
    items.sort(key=lambda item: item.date)
    return items


def _attendance_description(record: AttendanceRecord) -> str:
    return f"{_ATTENDANCE_STATUS_LABEL[record.status]} em {_format_date_br(record.date)}"


def _grade_description(grade: Grade) -> str:
    return f"Nota {grade.value} em {grade.subject} — {_format_date_br(grade.date)}"


def _assignment_submission_description(submission: AssignmentSubmission) -> str:
    return (
        f"{_SUBMISSION_STATUS_LABEL[submission.status]} em "
        f"{_format_date_br(submission.date)}"
    )


def _observation_description(observation: PedagogicalObservation) -> str:
    return (
        f"Registro pedagógico em {_format_date_br(observation.created_at.date())}: "
        f"{observation.text}"
    )
