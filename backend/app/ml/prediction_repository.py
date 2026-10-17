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

Reads every `StudentModel` row with `dataset_split == EVAL_DEMO` via the
shared `feature_aggregation.fetch_feature_rows()` helper (spec-5-3 — the
single source of truth also used by `TrainingRepository`/
`EvaluationRepository`), reusing `FEATURE_COLUMNS` so feature ordering never
drifts between training and scoring. Unlike `TrainingRepository`, there is no
label and no label-based exclusion: every `EVAL_DEMO` student is scored,
including one with no rows in a fact table (`None`/`0` features, same
null-handling as training's `SimpleImputer`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.student import DatasetSplit
from app.ml.feature_aggregation import fetch_feature_rows

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
        feature_rows = fetch_feature_rows(self._session, DatasetSplit.EVAL_DEMO)
        return [
            ScoringRow(
                student_id=row.student_id,
                attendance_rate=row.attendance_rate,
                grade_average=row.grade_average,
                assignment_completion_rate=row.assignment_completion_rate,
                observation_count=row.observation_count,
            )
            for row in feature_rows
        ]
