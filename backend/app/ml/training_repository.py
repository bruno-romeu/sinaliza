"""`TrainingRepository` — the only place offline training code reads
students (spec-5-1 Boundaries & Constraints, AD-11).

Structurally separate from the web path: a different module than
`infrastructure/repositories/`, no shared base class or mixin with
`SqlAlchemyStudentRepository`, and it never calls
`filter_eval_demo_students`/`filter_as_of` from
`infrastructure/repositories/base.py` — those enforce the `EVAL_DEMO`/
`as_of()` invariants the web path needs, and are structurally the wrong
filter for a repository whose entire purpose is reading the opposite split.

Reads only `StudentModel` rows with `dataset_split == TRAIN` and a non-null
`synthetic_profile` label (a `TRAIN` row with no label is simply excluded,
per the spec I/O Matrix — not an error on its own), joined with per-student
aggregates over attendance/grade/assignment/pedagogical-observation facts as
features (computed by the shared `feature_aggregation.fetch_feature_rows()`
helper, spec-5-3 — the single source of truth also used by
`PredictionRepository`/`EvaluationRepository`). A student with no rows in one
of those fact tables gets `None` for that feature (`build_pipeline()`'s
`SimpleImputer` fills it in at fit time) rather than being excluded — only a
missing *label* excludes a row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit, SyntheticProfile
from app.infrastructure.db.models import StudentModel
from app.ml.feature_aggregation import FEATURE_COLUMNS, fetch_feature_rows

#: Re-exported from `feature_aggregation` (the module that now owns the
#: definition) so existing imports (`app.ml.pipeline`,
#: `app.ml.prediction_repository`) keep working unchanged.
__all__ = ["FEATURE_COLUMNS", "TrainingRow", "TrainingRepository"]


@dataclass(frozen=True)
class TrainingRow:
    """One student's feature vector + label, ready for `app/ml/train.py` to
    assemble into `X`/`y`. `attendance_rate`/`grade_average`/
    `assignment_completion_rate` are `None` when the student has no rows in
    the corresponding fact table; `observation_count` is `0` in that case
    (a count, not a rate — "no observations" is a real, meaningful value)."""

    student_id: uuid.UUID
    attendance_rate: float | None
    grade_average: float | None
    assignment_completion_rate: float | None
    observation_count: int
    label: SyntheticProfile


class TrainingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_training_rows(self) -> list[TrainingRow]:
        feature_rows = fetch_feature_rows(self._session, DatasetSplit.TRAIN)
        if not feature_rows:
            return []

        student_ids = [row.student_id for row in feature_rows]
        labels_by_student = {
            row.id: row.synthetic_profile
            for row in self._session.execute(
                select(StudentModel.id, StudentModel.synthetic_profile).where(
                    StudentModel.id.in_(student_ids)
                )
            ).all()
            if row.synthetic_profile is not None
        }

        rows: list[TrainingRow] = []
        for feature_row in feature_rows:
            label = labels_by_student.get(feature_row.student_id)
            if label is None:
                continue
            rows.append(
                TrainingRow(
                    student_id=feature_row.student_id,
                    attendance_rate=feature_row.attendance_rate,
                    grade_average=feature_row.grade_average,
                    assignment_completion_rate=feature_row.assignment_completion_rate,
                    observation_count=feature_row.observation_count,
                    label=label,
                )
            )
        return rows
