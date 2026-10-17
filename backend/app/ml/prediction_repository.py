"""`PredictionRepository` — the only place offline scoring code reads
students (spec-5-2 Boundaries & Constraints, mirroring `TrainingRepository`'s
precedent, spec-5-1 AD-11).

Structurally separate from the web path: a different module than
`infrastructure/repositories/`, no shared base class or mixin with
`SqlAlchemyStudentRepository`, and it filters `EVAL_DEMO` itself rather than
calling `filter_eval_demo_students`/`filter_as_of` from
`infrastructure/repositories/base.py` — those are the wrong filters here:
this reads the full `EVAL_DEMO` cut with no `as_of()` truncation (same
rationale as `ml/evaluate`, Story 5.3: this is offline research tooling, not
the live-demo path).

Reads every `StudentModel` row with `dataset_split == EVAL_DEMO`, joined with
the same pedagogical fact sources `TrainingRepository` uses, reusing
`FEATURE_COLUMNS` so feature ordering never drifts between training and
scoring. Unlike `TrainingRepository`, there is no label and no label-based
exclusion: every `EVAL_DEMO` student is scored, including one with no rows in
a fact table (`None`/`0` features, same null-handling as training's
`SimpleImputer`)."""

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

#: Reused directly from training (not redefined here) so scoring's feature
#: vectors line up with what the pipeline was fit on (spec Code Map).
# `app/ml/predict.py` imports this from `training_repository` directly; this
# module's own `ScoringRow` field order below is manually kept identical to
# it, asserted at import time just below.
from app.ml.training_repository import FEATURE_COLUMNS


@dataclass(frozen=True)
class ScoringRow:
    """One `EVAL_DEMO` student's feature vector, ready for `app/ml/predict.py`
    to assemble into a feature matrix and score via the loaded `Pipeline`.
    Same null-handling convention as `TrainingRepository.TrainingRow`: rate
    features are `None` when the student has no rows in the corresponding
    fact table, `observation_count` is `0` in that case."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int


#: Guards against `ScoringRow`'s field order silently drifting from
#: `FEATURE_COLUMNS` — both must list the same four features in the same
#: order so `app/ml/predict.py`'s feature matrix lines up with the fitted
#: pipeline's expected column positions. An `if`/`raise` rather than a bare
#: `assert` so the check still runs under `python -O` (assertions are
#: stripped in optimized mode and would silently defeat this guard).
if tuple(FEATURE_COLUMNS) != (
    "attendance_rate",
    "grade_average",
    "assignment_completion_rate",
    "observation_count",
):
    raise RuntimeError(
        "training_repository.FEATURE_COLUMNS has drifted from the feature "
        "order ScoringRow/app.ml.predict assume — update both in lockstep."
    )


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_scoring_rows(self) -> list[ScoringRow]:
        students = self._session.execute(
            select(StudentModel.id).where(StudentModel.dataset_split == DatasetSplit.EVAL_DEMO)
        ).all()
        if not students:
            return []

        student_ids = [student.id for student in students]

        attendance_by_student = {
            row.student_id: (row.present, row.total)
            for row in self._session.execute(
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
            for row in self._session.execute(
                select(GradeModel.student_id, func.avg(GradeModel.value).label("average"))
                .where(GradeModel.student_id.in_(student_ids))
                .group_by(GradeModel.student_id)
            ).all()
        }

        submission_by_student = {
            row.student_id: (row.delivered, row.total)
            for row in self._session.execute(
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
            for row in self._session.execute(
                select(
                    PedagogicalObservationModel.student_id,
                    func.count(PedagogicalObservationModel.id).label("total"),
                )
                .where(PedagogicalObservationModel.student_id.in_(student_ids))
                .group_by(PedagogicalObservationModel.student_id)
            ).all()
        }

        rows: list[ScoringRow] = []
        for student in students:
            present, total = attendance_by_student.get(student.id, (0, 0))
            attendance_rate = (present / total) if total else None

            delivered, submission_total = submission_by_student.get(student.id, (0, 0))
            assignment_completion_rate = (delivered / submission_total) if submission_total else None

            rows.append(
                ScoringRow(
                    student_id=student.id,
                    attendance_rate=attendance_rate,
                    grade_average=grade_average_by_student.get(student.id),
                    assignment_completion_rate=assignment_completion_rate,
                    observation_count=observation_count_by_student.get(student.id, 0),
                )
            )
        return rows
