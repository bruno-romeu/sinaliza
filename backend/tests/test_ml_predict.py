"""DB-backed tests covering every row of spec-5-2's I/O & Edge-Case Matrix.

Calls `run_prediction(db_session, tmp_path)` directly against the
`db_session` fixture (never subprocess), mirroring `test_ml_train.py`'s
precedent of seeding rows directly and driving the real `Session`-taking
function.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest
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
    MLPredictionModel,
    PedagogicalObservationModel,
    StudentModel,
    UserModel,
)
from app.ml import predict as predict_module
from app.ml.pipeline import build_pipeline
from app.ml.predict import NoModelVersionError, NoScoringDataError, run_prediction
from app.ml.train import run_training


class _SessionContext:
    """Minimal stand-in for `SessionLocal()`'s context-manager protocol,
    mirroring `test_ml_train.py`'s `_SessionContext`."""

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
    """Seeds a TRAIN student with real facts so `run_training` has something
    non-trivial to fit a usable `Pipeline` on (mirrors `test_ml_train.py`'s
    helper of the same name)."""
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


def _seed_eval_demo_student(
    db_session: Session,
    classroom: ClassroomModel,
    *,
    with_facts: bool,
    period_id,
    assignment: AssignmentModel | None = None,
    author_user_id=None,
) -> StudentModel:
    student = StudentModel(name="Estudante EVAL_DEMO", dataset_split=DatasetSplit.EVAL_DEMO)
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
                    value=6.0,
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


def _train_a_model(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> MLModelVersionModel:
    for profile in (
        SyntheticProfile.STABLE,
        SyntheticProfile.STABLE,
        SyntheticProfile.FALLING_ATTENDANCE,
        SyntheticProfile.FALLING_GRADES,
    ):
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )
    run_training(db_session, tmp_path)
    return db_session.query(MLModelVersionModel).one()


def _seed_model_version(
    db_session: Session, tmp_path: Path, version_label: str, trained_at: datetime
) -> MLModelVersionModel:
    """Fits a tiny real `Pipeline` and dumps it to its own artifact file, then
    inserts an `MLModelVersionModel` row with an explicit `trained_at` — lets
    tests control which of several model versions is "latest" without
    depending on wall-clock timing between successive `run_training` calls."""
    pipeline = build_pipeline()
    feature_matrix = [[0.9, 7.0, 1.0, 2], [0.1, 3.0, 0.2, 0], [0.5, 5.0, 0.5, 1], [0.8, 6.0, 0.9, 2]]
    labels = [
        SyntheticProfile.STABLE.value,
        SyntheticProfile.FALLING_ATTENDANCE.value,
        SyntheticProfile.FALLING_GRADES.value,
        SyntheticProfile.STABLE.value,
    ]
    pipeline.fit(feature_matrix, labels)
    artifact_path = tmp_path / f"model-{version_label}.joblib"
    joblib.dump(pipeline, artifact_path)

    model_version = MLModelVersionModel(
        id=uuid.uuid4(),
        version=version_label,
        artifact_path=str(artifact_path),
        trained_at=trained_at,
        created_at=trained_at,
    )
    db_session.add(model_version)
    db_session.commit()
    return model_version


# ---------------------------------------------------------------------------
# Latest-MLModelVersion selection, with more than one row present
# ---------------------------------------------------------------------------


def test_run_prediction_uses_the_most_recently_trained_model_version(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    older_version = _seed_model_version(
        db_session, tmp_path, "older", datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    newer_version = _seed_model_version(
        db_session, tmp_path, "newer", datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    student = _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )

    predictions = run_prediction(db_session, tmp_path)

    assert len(predictions) == 1
    assert predictions[0].student_id == student.id
    assert predictions[0].model_version_id == newer_version.id
    assert predictions[0].model_version_id != older_version.id


# ---------------------------------------------------------------------------
# Matrix row: happy path
# ---------------------------------------------------------------------------


def test_happy_path_scores_every_eval_demo_student(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    trained_version = _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )

    eval_students = [
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )
        for _ in range(3)
    ]

    predictions = run_prediction(db_session, tmp_path)

    assert len(predictions) == len(eval_students)
    assert db_session.query(MLPredictionModel).count() == len(eval_students)
    scored_student_ids = {row.student_id for row in db_session.query(MLPredictionModel).all()}
    assert scored_student_ids == {student.id for student in eval_students}
    for row in db_session.query(MLPredictionModel).all():
        assert 0.0 <= row.score <= 1.0
        assert row.model_version_id == trained_version.id


# ---------------------------------------------------------------------------
# Matrix row: no MLModelVersion exists
# ---------------------------------------------------------------------------


def test_no_model_version_raises_and_writes_nothing(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    tmp_path: Path,
) -> None:
    _seed_eval_demo_student(
        db_session, seeded_classroom, with_facts=False, period_id=seeded_academic_period.id
    )

    with pytest.raises(NoModelVersionError):
        run_prediction(db_session, tmp_path)

    assert db_session.query(MLPredictionModel).count() == 0


# ---------------------------------------------------------------------------
# Matrix row: no EVAL_DEMO rows
# ---------------------------------------------------------------------------


def test_no_eval_demo_rows_raises_and_writes_nothing(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )

    with pytest.raises(NoScoringDataError):
        run_prediction(db_session, tmp_path)

    assert db_session.query(MLPredictionModel).count() == 0


# ---------------------------------------------------------------------------
# Matrix row: EVAL_DEMO student missing some facts
# ---------------------------------------------------------------------------


def test_eval_demo_student_missing_facts_is_scored_not_skipped(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )
    student = _seed_eval_demo_student(
        db_session, seeded_classroom, with_facts=False, period_id=seeded_academic_period.id
    )

    predictions = run_prediction(db_session, tmp_path)

    assert len(predictions) == 1
    assert predictions[0].student_id == student.id
    assert 0.0 <= predictions[0].score <= 1.0


# ---------------------------------------------------------------------------
# Matrix row: re-run the command twice
# ---------------------------------------------------------------------------


def test_two_runs_produce_two_rows_per_student_same_model_version(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    trained_version = _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )
    student = _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )

    first = run_prediction(db_session, tmp_path)
    second = run_prediction(db_session, tmp_path)

    assert len(first) == 1
    assert len(second) == 1
    assert db_session.query(MLPredictionModel).count() == 2
    rows = db_session.query(MLPredictionModel).filter_by(student_id=student.id).all()
    assert len(rows) == 2
    for row in rows:
        assert row.model_version_id == trained_version.id


# ---------------------------------------------------------------------------
# `main()` CLI entry point: stderr+exit(1) and stdout-summary+exit(0) paths
# ---------------------------------------------------------------------------


def test_main_exits_nonzero_and_prints_to_stderr_on_no_model_version(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_eval_demo_student(
        db_session, seeded_classroom, with_facts=False, period_id=seeded_academic_period.id
    )
    monkeypatch.setattr(predict_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(
        predict_module, "get_settings", lambda: SimpleNamespace(ml_artifact_dir=str(tmp_path))
    )

    with pytest.raises(SystemExit) as exc_info:
        predict_module.main([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No MLModelVersion rows" in captured.err
    assert db_session.query(MLPredictionModel).count() == 0


def test_main_exits_nonzero_and_prints_to_stderr_on_no_eval_demo_rows(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )
    monkeypatch.setattr(predict_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(
        predict_module, "get_settings", lambda: SimpleNamespace(ml_artifact_dir=str(tmp_path))
    )

    with pytest.raises(SystemExit) as exc_info:
        predict_module.main([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No EVAL_DEMO students" in captured.err
    assert db_session.query(MLPredictionModel).count() == 0


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
    _train_a_model(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user, tmp_path
    )
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )
    # A second EVAL_DEMO student with no facts at all — the summary's
    # missing-facts count (spec I/O Matrix "EVAL_DEMO student missing some
    # facts": "Noted in printed summary, not fatal") must reflect exactly
    # this one student, not 0.
    _seed_eval_demo_student(
        db_session, seeded_classroom, with_facts=False, period_id=seeded_academic_period.id
    )
    monkeypatch.setattr(predict_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(
        predict_module, "get_settings", lambda: SimpleNamespace(ml_artifact_dir=str(tmp_path))
    )

    with pytest.raises(SystemExit) as exc_info:
        predict_module.main([])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Scored 2 EVAL_DEMO student(s)" in captured.out
    assert "(1 with missing facts imputed)" in captured.out
    assert db_session.query(MLPredictionModel).count() == 2
