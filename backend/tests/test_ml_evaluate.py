"""DB-backed tests covering every row of spec-5-3's I/O & Edge-Case Matrix.

Calls `run_evaluation(db_session)` directly against the `db_session` fixture
(never subprocess), mirroring `test_ml_predict.py`'s precedent of seeding
rows directly and driving the real `Session`-taking function.
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
    PedagogicalObservationModel,
    StudentModel,
    UserModel,
)
from app.ml import evaluate as evaluate_module
from app.ml.evaluate import (
    DISCLAIMER,
    NoEvaluationDataError,
    NoModelVersionError,
    run_evaluation,
)
from app.ml.pipeline import build_pipeline
from app.ml.train import run_training


class _SessionContext:
    """Minimal stand-in for `SessionLocal()`'s context-manager protocol,
    mirroring `test_ml_predict.py`'s `_SessionContext`."""

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


def _seed_eval_demo_student(
    db_session: Session,
    classroom: ClassroomModel,
    *,
    profile: SyntheticProfile | None,
    with_facts: bool,
    period_id,
    assignment: AssignmentModel | None = None,
    author_user_id=None,
    grade_value: float = 6.0,
) -> StudentModel:
    student = StudentModel(
        name="Estudante EVAL_DEMO", dataset_split=DatasetSplit.EVAL_DEMO, synthetic_profile=profile
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
                    value=grade_value,
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
        SyntheticProfile.COMBINED_DETERIORATION,
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


def _seed_model_version_trained_on_subset_of_labels(
    db_session: Session, tmp_path: Path, version_label: str, trained_at: datetime
) -> MLModelVersionModel:
    """Fits a tiny real `Pipeline` on only 2 of the 4 `SyntheticProfile`
    labels, so `pipeline.classes_` is a strict subset of `_ALL_LABELS` —
    exercises `run_evaluation()`'s class-reindexing/zero-fill branch, which a
    model trained on all 4 labels (`_seed_model_version`/`_train_a_model`)
    never reaches."""
    pipeline = build_pipeline()
    feature_matrix = [
        [0.9, 7.0, 1.0, 2],
        [0.85, 6.5, 0.9, 1],
        [0.1, 3.0, 0.2, 0],
        [0.15, 3.5, 0.3, 0],
    ]
    labels = [
        SyntheticProfile.STABLE.value,
        SyntheticProfile.STABLE.value,
        SyntheticProfile.FALLING_ATTENDANCE.value,
        SyntheticProfile.FALLING_ATTENDANCE.value,
    ]
    pipeline.fit(feature_matrix, labels)
    assert set(pipeline.classes_.tolist()) == {
        SyntheticProfile.STABLE.value,
        SyntheticProfile.FALLING_ATTENDANCE.value,
    }
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
# Matrix row: happy path
# ---------------------------------------------------------------------------


def test_happy_path_prints_metrics_confusion_matrix_and_disclaimer(
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
    for profile in (
        SyntheticProfile.STABLE,
        SyntheticProfile.FALLING_ATTENDANCE,
        SyntheticProfile.FALLING_GRADES,
        SyntheticProfile.COMBINED_DETERIORATION,
    ):
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    report = run_evaluation(db_session)

    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert 0.0 <= report.f1 <= 1.0
    assert len(report.confusion_matrix) == 4
    assert all(len(row) == 4 for row in report.confusion_matrix)
    assert sum(sum(row) for row in report.confusion_matrix) == 4
    assert report.roc_auc is not None
    assert report.pr_auc is not None
    assert 0.0 <= report.roc_auc <= 1.0
    assert 0.0 <= report.pr_auc <= 1.0
    assert report.disclaimer == DISCLAIMER
    assert "simulated patterns in the synthetic dataset" in report.disclaimer


# ---------------------------------------------------------------------------
# Matrix row: no MLModelVersion exists
# ---------------------------------------------------------------------------


def test_no_model_version_raises(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
) -> None:
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=SyntheticProfile.STABLE,
        with_facts=False,
        period_id=seeded_academic_period.id,
    )

    with pytest.raises(NoModelVersionError):
        run_evaluation(db_session)


# ---------------------------------------------------------------------------
# Matrix row: no labeled EVAL_DEMO rows
# ---------------------------------------------------------------------------


def test_no_labeled_eval_demo_rows_raises(
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
    # An EVAL_DEMO student with no label is excluded, same as a TRAIN row
    # with no label — the usable set is empty.
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=None,
        with_facts=True,
        period_id=seeded_academic_period.id,
    )

    with pytest.raises(NoEvaluationDataError):
        run_evaluation(db_session)


def test_zero_eval_demo_rows_raises(
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

    with pytest.raises(NoEvaluationDataError):
        run_evaluation(db_session)


# ---------------------------------------------------------------------------
# Matrix row: only one class present in EVAL_DEMO labels
# ---------------------------------------------------------------------------


def test_single_class_eval_set_reports_metrics_and_not_computable_auc(
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
    for _ in range(2):
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=SyntheticProfile.STABLE,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    report = run_evaluation(db_session)

    assert report.roc_auc is None
    assert report.pr_auc is None
    assert len(report.confusion_matrix) == 4
    assert 0.0 <= report.precision <= 1.0


# ---------------------------------------------------------------------------
# `pipeline.classes_` a strict subset of all 4 SyntheticProfile labels
# (TRAIN omitted a class) — exercises the class-reindexing/zero-fill branch
# ---------------------------------------------------------------------------


def test_model_trained_on_label_subset_still_computes_valid_auc_metrics(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    _seed_model_version_trained_on_subset_of_labels(
        db_session, tmp_path, "subset", datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    # EVAL_DEMO labels span >=2 classes, including FALLING_GRADES — a label
    # absent from the trained pipeline's `classes_` — so `_ALL_LABELS`'
    # corresponding probability column must be zero-filled rather than
    # raising/misaligning.
    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_GRADES):
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    report = run_evaluation(db_session)

    assert isinstance(report.roc_auc, float)
    assert isinstance(report.pr_auc, float)
    assert 0.0 <= report.roc_auc <= 1.0
    assert 0.0 <= report.pr_auc <= 1.0


# ---------------------------------------------------------------------------
# Matrix row: EVAL_DEMO row missing facts
# ---------------------------------------------------------------------------


def test_eval_demo_row_missing_facts_is_scored_not_skipped(
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
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=SyntheticProfile.FALLING_ATTENDANCE,
        with_facts=False,
        period_id=seeded_academic_period.id,
    )
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=SyntheticProfile.STABLE,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )

    report = run_evaluation(db_session)

    assert report.sample_count == 2
    assert report.missing_facts_count == 1


# ---------------------------------------------------------------------------
# `main()` CLI entry point: stderr+exit(1) and stdout-report+exit(0) paths
# ---------------------------------------------------------------------------


def test_main_exits_nonzero_and_prints_to_stderr_on_no_model_version(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=SyntheticProfile.STABLE,
        with_facts=False,
        period_id=seeded_academic_period.id,
    )
    monkeypatch.setattr(evaluate_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(evaluate_module, "get_settings", lambda: SimpleNamespace())

    with pytest.raises(SystemExit) as exc_info:
        evaluate_module.main([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No MLModelVersion rows" in captured.err


def test_main_exits_nonzero_and_prints_to_stderr_on_no_evaluation_data(
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
    monkeypatch.setattr(evaluate_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(evaluate_module, "get_settings", lambda: SimpleNamespace())

    with pytest.raises(SystemExit) as exc_info:
        evaluate_module.main([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No labeled EVAL_DEMO students" in captured.err


def test_main_exits_zero_and_prints_report_on_success(
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
    for profile in (SyntheticProfile.STABLE, SyntheticProfile.FALLING_GRADES):
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )
    monkeypatch.setattr(evaluate_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(evaluate_module, "get_settings", lambda: SimpleNamespace())

    with pytest.raises(SystemExit) as exc_info:
        evaluate_module.main([])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Precision (macro):" in captured.out
    assert "Recall (macro):" in captured.out
    assert "F1 (macro):" in captured.out
    assert "Confusion matrix" in captured.out
    assert "ROC-AUC" in captured.out
    assert "PR-AUC" in captured.out
    assert "ability to recognize simulated patterns in the synthetic dataset" in captured.out
    assert "accurate predictor of dropout" not in captured.out
