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

import hashlib
import uuid
from dataclasses import dataclass, fields

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

#: The single declaration of which features exist and in which order. Every
#: other module derives from it rather than restating it: `build_pipeline()`
#: takes its column indices from `len()`, and `train`/`evaluate`/`predict`
#: build their feature matrices through `feature_vector()` below, so a
#: reorder here reorders all three together instead of silently feeding the
#: pipeline swapped columns (epic-5-retro-item-1).
FEATURE_COLUMNS: tuple[str, ...] = (
    "attendance_rate",
    "grade_average",
    "assignment_completion_rate",
    "observation_count",
)


def _compute_feature_schema_version(columns: tuple[str, ...]) -> str:
    """SHA-256 over the ordered column names, truncated — the same
    `population_fingerprint()` idea applied to the feature schema instead of
    the dataset. Derived rather than hand-maintained on purpose: a constant
    someone forgets to bump is exactly the drift this guards against."""
    digest = hashlib.sha256("|".join(columns).encode()).hexdigest()
    return f"sha256:{digest[:12]}"


#: Identifies the feature schema a model artifact was fitted under, persisted
#: on `ml_model_version.feature_schema_version` (`AGENTS.md` §Versionamento de
#: modelo). Changes whenever a feature is added, removed, renamed **or
#: reordered** — which is what lets `predict`/`evaluate` refuse an artifact
#: fitted under a different column order instead of scoring with swapped
#: columns.
FEATURE_SCHEMA_VERSION: str = _compute_feature_schema_version(FEATURE_COLUMNS)


def require_feature_fields(row_type: type) -> None:
    """Fails loudly at import time when a feature-carrying row dataclass does
    not declare a field for every `FEATURE_COLUMNS` entry — the structural
    replacement for the hardcoded tuple comparison `prediction_repository`
    used to carry (which also forbade ever *adding* a feature). An
    `if`/`raise` rather than a bare `assert` so the check still runs under
    `python -O`, where assertions are stripped."""
    declared = {field.name for field in fields(row_type)}
    missing = [column for column in FEATURE_COLUMNS if column not in declared]
    if missing:
        raise RuntimeError(
            f"{row_type.__name__} declares no field for FEATURE_COLUMNS "
            f"entries {missing!r} — feature rows and FEATURE_COLUMNS must be "
            "updated in lockstep."
        )


class FeatureSchemaMismatchError(RuntimeError):
    """Raised when a persisted `MLModelVersion.feature_schema_version` differs
    from the running code's `FEATURE_SCHEMA_VERSION`."""


def require_matching_feature_schema(version: str, persisted: str | None) -> None:
    """Refuses to use an artifact fitted under a different feature schema.

    This covers the half of the drift problem no import-time guard can:
    `train`/`evaluate`/`predict` all deriving their column order from
    `FEATURE_COLUMNS` keeps them consistent *with each other*, but an artifact
    serialized before the reorder is still on disk, and `joblib.load` has no
    idea its columns moved. Scoring it would produce plausible numbers for
    swapped features.

    `persisted is None` means a row written before migration 0015 — unknown,
    not mismatched. Proceeding there is deliberate: refusing on a guess would
    break a pre-existing artifact for no evidence at all. `if`/`raise`, never
    `assert` (stripped under `python -O`)."""
    if persisted is not None and persisted != FEATURE_SCHEMA_VERSION:
        raise FeatureSchemaMismatchError(
            f"MLModelVersion {version} was fitted under feature schema "
            f"{persisted}, but the running code declares {FEATURE_SCHEMA_VERSION} "
            f"({', '.join(FEATURE_COLUMNS)}). FEATURE_COLUMNS changed since this "
            "artifact was trained — retrain with `python -m app.ml.train` "
            "instead of scoring with mismatched columns."
        )


def feature_vector(row: object) -> list[float | None]:
    """One row's feature values in `FEATURE_COLUMNS` order — the only way
    `train`/`evaluate`/`predict` are allowed to build a feature matrix. Works
    for `FeatureRow`, `TrainingRow`, `ScoringRow` and `EvaluationRow` alike:
    all four name their feature fields exactly as `FEATURE_COLUMNS` does
    (enforced by `require_feature_fields`)."""
    return [getattr(row, column) for column in FEATURE_COLUMNS]


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


require_feature_fields(FeatureRow)


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
