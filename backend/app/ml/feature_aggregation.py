"""Shared per-student feature aggregation — the single source of truth for
the attendance/grade/assignment/pedagogical-observation SQL that
`TrainingRepository`, `PredictionRepository`, and `EvaluationRepository` all
need (spec-5-3 Intent: this SQL was duplicated almost verbatim between the
first two before this extraction).

Extracted verbatim from `training_repository.fetch_training_rows()` /
`prediction_repository.fetch_scoring_rows()` — only the student-selection
(`dataset_split`/label filtering) stayed behind in each caller, which is
still structurally repository-specific. This module itself never filters by
label and never calls `filter_as_of` — it only answers "what are this
`dataset_split`'s students' feature values," leaving every split/label
decision to the caller.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit
from app.infrastructure.db.models import (
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    GradeModel,
    PedagogicalObservationModel,
    StudentModel,
)

#: Order feeds `app/ml/train.py`'s feature matrix construction and
#: `build_pipeline()`'s column indices — keep the two in sync. The single
#: definition every other module (`training_repository`, `prediction_repository`,
#: `evaluation_repository`, `pipeline`) imports from.
FEATURE_COLUMNS: tuple[str, ...] = (
    "attendance_rate",
    "grade_average",
    "assignment_completion_rate",
    "observation_count",
)


@dataclass(frozen=True)
class FeatureRow:
    """One student's feature vector for a given `dataset_split` — no label,
    no split/filter semantics attached. `attendance_rate`/`grade_average`/
    `assignment_completion_rate` are `None` when the student has no rows in
    the corresponding fact table; `observation_count` is `0` in that case (a
    count, not a rate — "no observations" is a real, meaningful value)."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int


def fetch_feature_rows(session: Session, dataset_split: DatasetSplit) -> list[FeatureRow]:
    """Returns one `FeatureRow` per `StudentModel` row with the given
    `dataset_split`, regardless of label — callers decide whether/how to
    filter or join a `synthetic_profile` label on top of this. Never calls
    `filter_as_of`/`filter_eval_demo_students` (`infrastructure/repositories/
    base.py`'s invariants are for the web path, not offline ML tooling)."""
    students = session.execute(
        select(StudentModel.id).where(StudentModel.dataset_split == dataset_split)
    ).all()
    if not students:
        return []

    student_ids = [student.id for student in students]

    attendance_by_student = {
        row.student_id: (row.present, row.total)
        for row in session.execute(
            select(
                AttendanceRecordModel.student_id,
                func.count(AttendanceRecordModel.id).label("total"),
                func.sum(
                    case((AttendanceRecordModel.status == AttendanceStatus.PRESENT, 1), else_=0)
                ).label("present"),
            )
            .where(AttendanceRecordModel.student_id.in_(student_ids))
            .group_by(AttendanceRecordModel.student_id)
        ).all()
    }

    grade_average_by_student = {
        row.student_id: float(row.average)
        for row in session.execute(
            select(GradeModel.student_id, func.avg(GradeModel.value).label("average"))
            .where(GradeModel.student_id.in_(student_ids))
            .group_by(GradeModel.student_id)
        ).all()
    }

    submission_by_student = {
        row.student_id: (row.delivered, row.total)
        for row in session.execute(
            select(
                AssignmentSubmissionModel.student_id,
                func.count(AssignmentSubmissionModel.id).label("total"),
                func.sum(
                    case(
                        (
                            AssignmentSubmissionModel.status
                            == AssignmentSubmissionStatus.DELIVERED,
                            1,
                        ),
                        else_=0,
                    )
                ).label("delivered"),
            )
            .where(AssignmentSubmissionModel.student_id.in_(student_ids))
            .group_by(AssignmentSubmissionModel.student_id)
        ).all()
    }

    observation_count_by_student = {
        row.student_id: row.total
        for row in session.execute(
            select(
                PedagogicalObservationModel.student_id,
                func.count(PedagogicalObservationModel.id).label("total"),
            )
            .where(PedagogicalObservationModel.student_id.in_(student_ids))
            .group_by(PedagogicalObservationModel.student_id)
        ).all()
    }

    rows: list[FeatureRow] = []
    for student in students:
        present, total = attendance_by_student.get(student.id, (0, 0))
        attendance_rate = (present / total) if total else None

        delivered, submission_total = submission_by_student.get(student.id, (0, 0))
        assignment_completion_rate = (delivered / submission_total) if submission_total else None

        rows.append(
            FeatureRow(
                student_id=student.id,
                attendance_rate=attendance_rate,
                grade_average=grade_average_by_student.get(student.id),
                assignment_completion_rate=assignment_completion_rate,
                observation_count=observation_count_by_student.get(student.id, 0),
            )
        )
    return rows
