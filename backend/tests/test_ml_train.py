"""DB-backed tests covering every row of spec-5-1's I/O & Edge-Case Matrix.

Calls `run_training(db_session, tmp_path)` directly against the `db_session`
fixture (never subprocess), mirroring `test_synthetic_facts_generation.py`'s
precedent of seeding rows directly rather than depending on the full
synthetic generator.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest
from sklearn.pipeline import Pipeline
from sqlalchemy.orm import Session

from app.domain.assignment_submission import AssignmentSubmissionStatus
from app.domain.attendance import AttendanceStatus
from app.domain.student import DatasetSplit, SyntheticProfile
from app.infrastructure.db.models import (
    AssignmentModel,
    AssignmentSubmissionModel,
    AttendanceRecordModel,
    ClassroomModel,
    GradeModel,
    MLModelVersionModel,
    PedagogicalObservationModel,
    StudentModel,
    UserModel,
)
from app.ml import train as train_module
from app.ml.train import NoTrainingDataError, run_training
from app.ml.training_repository import TrainingRepository


class _SessionContext:
    """Minimal stand-in for `SessionLocal()`'s context-manager protocol
    (`with SessionLocal() as session:`), wrapping the already-provided
    `db_session` fixture so `main()`'s writes stay inside the test's
    rolled-back savepoint instead of hitting a separate real connection."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *exc_info: object) -> bool:
        return False


def _seed_train_student(
    db_session: Session,
    classroom: ClassroomModel,
    profile: SyntheticProfile,
    *,
    with_facts: bool,
    period_id,
    assignment: AssignmentModel | None = None,
    author_user_id=None,
) -> StudentModel:
    student = StudentModel(
        name="Estudante TRAIN", dataset_split=DatasetSplit.TRAIN, synthetic_profile=profile
    )
    db_session.add(student)
    db_session.flush()

    if with_facts:
        db_session.add_all(
            [
                AttendanceRecordModel(
                    student_id=student.id,
                    classroom_id=classroom.id,
                    date=date(2026, 3, 2),
                    status=AttendanceStatus.PRESENT,
                ),
                AttendanceRecordModel(
                    student_id=student.id,
                    classroom_id=classroom.id,
                    date=date(2026, 3, 3),
                    status=AttendanceStatus.ABSENT_UNJUSTIFIED,
                ),
                GradeModel(
                    student_id=student.id,
                    classroom_id=classroom.id,
                    subject="Matemática",
                    period_id=period_id,
                    date=date(2026, 3, 4),
                    value=7.5,
                ),
            ]
        )
        if assignment is not None:
            db_session.add(
                AssignmentSubmissionModel(
                    assignment_id=assignment.id,
                    student_id=student.id,
                    status=AssignmentSubmissionStatus.DELIVERED,
                    date=date(2026, 3, 5),
                )
            )
        if author_user_id is not None:
            db_session.add(
                PedagogicalObservationModel(
                    student_id=student.id,
                    author_user_id=author_user_id,
                    text="Observação de teste.",
                    created_at=datetime(2026, 3, 6, tzinfo=timezone.utc),
                )
            )
    db_session.commit()
    return student


# ---------------------------------------------------------------------------
# Matrix row: happy path
# ---------------------------------------------------------------------------


def test_happy_path_fits_pipeline_writes_artifact_and_model_version(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    for profile, with_facts in (
        (SyntheticProfile.STABLE, True),
        (SyntheticProfile.STABLE, True),
        (SyntheticProfile.FALLING_ATTENDANCE, True),
        # A TRAIN row missing some facts (not the label) is not fatal on its
        # own — its features are just imputed at fit time.
        (SyntheticProfile.FALLING_ATTENDANCE, False),
    ):
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=with_facts,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    model_version = run_training(db_session, tmp_path)

    assert db_session.query(MLModelVersionModel).count() == 1
    row = db_session.query(MLModelVersionModel).one()
    assert row.version == model_version.version
    assert row.artifact_path == model_version.artifact_path
    assert Path(row.artifact_path).exists()

    loaded = joblib.load(model_version.artifact_path)
    assert isinstance(loaded, Pipeline)
    prediction = loaded.predict([[0.9, 7.0, 1.0, 2]])
    assert prediction[0] in {p.value for p in SyntheticProfile}
    probabilities = loaded.predict_proba([[0.9, 7.0, 1.0, 2]])
    assert probabilities.shape[0] == 1


# ---------------------------------------------------------------------------
# Matrix row: no usable training rows
# ---------------------------------------------------------------------------


def test_no_train_rows_raises_and_writes_nothing(db_session: Session, tmp_path: Path) -> None:
    with pytest.raises(NoTrainingDataError):
        run_training(db_session, tmp_path)

    assert db_session.query(MLModelVersionModel).count() == 0
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Matrix row: TRAIN row missing label (only fatal if it empties the set)
# ---------------------------------------------------------------------------


def test_train_row_missing_label_is_excluded_and_fatal_only_if_set_empties(
    db_session: Session, tmp_path: Path
) -> None:
    db_session.add(
        StudentModel(
            name="Sem rótulo", dataset_split=DatasetSplit.TRAIN, synthetic_profile=None
        )
    )
    db_session.commit()

    # The only TRAIN row has no label, so the usable set is empty — fatal,
    # same as the zero-rows case.
    with pytest.raises(NoTrainingDataError):
        run_training(db_session, tmp_path)
    assert db_session.query(MLModelVersionModel).count() == 0


def test_train_row_missing_label_does_not_block_other_usable_rows(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    db_session.add(
        StudentModel(
            name="Sem rótulo", dataset_split=DatasetSplit.TRAIN, synthetic_profile=None
        )
    )
    db_session.commit()
    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_ATTENDANCE):
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    model_version = run_training(db_session, tmp_path)

    assert db_session.query(MLModelVersionModel).count() == 1
    assert Path(model_version.artifact_path).exists()


# ---------------------------------------------------------------------------
# Matrix row: re-run the command twice
# ---------------------------------------------------------------------------


def test_two_consecutive_runs_produce_two_distinct_versions_and_files(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_ATTENDANCE):
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    first = run_training(db_session, tmp_path)
    second = run_training(db_session, tmp_path)

    assert first.version != second.version
    assert first.artifact_path != second.artifact_path
    assert Path(first.artifact_path).exists()
    assert Path(second.artifact_path).exists()
    assert db_session.query(MLModelVersionModel).count() == 2


# ---------------------------------------------------------------------------
# TrainingRepository feature-value correctness (not just end-to-end fit)
# ---------------------------------------------------------------------------


def test_training_repository_computes_feature_values_matching_seeded_facts(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    student = _seed_train_student(
        db_session,
        seeded_classroom,
        SyntheticProfile.STABLE,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )

    rows = TrainingRepository(db_session).fetch_training_rows()

    assert len(rows) == 1
    row = rows[0]
    assert row.student_id == student.id
    # 1 PRESENT + 1 ABSENT_UNJUSTIFIED (per `_seed_train_student`) -> 0.5
    assert row.attendance_rate == pytest.approx(0.5)
    # Single grade of 7.5 -> average is itself
    assert row.grade_average == pytest.approx(7.5)
    # 1 DELIVERED out of 1 submission -> 1.0
    assert row.assignment_completion_rate == pytest.approx(1.0)
    # Single seeded observation
    assert row.observation_count == 1
    assert row.label == SyntheticProfile.STABLE


# ---------------------------------------------------------------------------
# `main()` CLI entry point: stderr+exit(1) and stdout-summary+exit(0) paths
# ---------------------------------------------------------------------------


def test_main_exits_nonzero_and_prints_to_stderr_on_no_training_data(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(train_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(train_module, "get_settings", lambda: SimpleNamespace(ml_artifact_dir=str(tmp_path)))

    with pytest.raises(SystemExit) as exc_info:
        train_module.main([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No TRAIN students" in captured.err
    assert db_session.query(MLModelVersionModel).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_main_exits_zero_and_prints_summary_on_success(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_ATTENDANCE):
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    monkeypatch.setattr(train_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(train_module, "get_settings", lambda: SimpleNamespace(ml_artifact_dir=str(tmp_path)))

    with pytest.raises(SystemExit) as exc_info:
        train_module.main([])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Trained model version=" in captured.out
    assert db_session.query(MLModelVersionModel).count() == 1
