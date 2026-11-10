"""Procedência persistida do `MLModelVersion` e proteção contra drift de
`FEATURE_COLUMNS` (migration 0015 / epic-5-retro-item-1).

Dois invariantes, um arquivo, porque são o mesmo problema visto de dois lados:
só faz sentido gravar métricas de um modelo se as colunas que o alimentaram
forem as que ele espera — caso contrário o banco passa a guardar, com ar de
procedência, o resultado de um treino silenciosamente errado.

Reaproveita os helpers de semeadura de `test_ml_evaluate.py` em vez de criar
uma terceira cópia deles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.attendance import AttendanceStatus
from app.domain.student import SyntheticProfile
from app.infrastructure.db.models import (
    AssignmentModel,
    AttendanceRecordModel,
    ClassroomModel,
    MLModelVersionModel,
    StudentModel,
    UserModel,
)
from app.ml import feature_aggregation
from app.ml.evaluate import DISCLAIMER, METRICS_SCHEMA_VERSION, run_evaluation
from app.ml.feature_aggregation import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    FeatureSchemaMismatchError,
    _compute_feature_schema_version,
    feature_vector,
    require_feature_fields,
    require_matching_feature_schema,
)
from app.ml.predict import run_prediction
from app.ml.train import run_training
from app.synthetic.fingerprint import population_fingerprint
from tests.test_ml_evaluate import _seed_eval_demo_student, _seed_train_student


def _seed_train_cut(
    db_session: Session,
    classroom: ClassroomModel,
    period_id,
    assignment: AssignmentModel,
    user: UserModel,
) -> None:
    for profile in (
        SyntheticProfile.STABLE,
        SyntheticProfile.STABLE,
        SyntheticProfile.FALLING_ATTENDANCE,
        SyntheticProfile.FALLING_GRADES,
        SyntheticProfile.COMBINED_DETERIORATION,
    ):
        _seed_train_student(
            db_session,
            classroom,
            profile,
            with_facts=True,
            period_id=period_id,
            assignment=assignment,
            author_user_id=user.id,
        )


def _seed_eval_cut(
    db_session: Session,
    classroom: ClassroomModel,
    period_id,
    assignment: AssignmentModel,
    user: UserModel,
) -> None:
    for profile in (
        SyntheticProfile.STABLE,
        SyntheticProfile.FALLING_ATTENDANCE,
        SyntheticProfile.FALLING_GRADES,
        SyntheticProfile.COMBINED_DETERIORATION,
    ):
        _seed_eval_demo_student(
            db_session,
            classroom,
            profile=profile,
            with_facts=True,
            period_id=period_id,
            assignment=assignment,
            author_user_id=user.id,
        )


# ---------------------------------------------------------------------------
# train.py grava a procedência (AGENTS.md §Versionamento de modelo)
# ---------------------------------------------------------------------------


def test_training_persists_dataset_fingerprint_and_feature_schema(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    """Antes da migration 0015, dado um `MLModelVersion` no banco não havia
    como responder qual dataset o treinou. Agora há."""
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )

    model_version = run_training(db_session, tmp_path)

    row = db_session.get(MLModelVersionModel, model_version.id)
    assert row is not None
    assert row.training_dataset_version == population_fingerprint(db_session)
    assert row.feature_schema_version == FEATURE_SCHEMA_VERSION
    # Métrica não nasce com o treino: treinar e avaliar no mesmo conjunto é
    # proibido, então `metrics` só existe depois de um `evaluate`.
    assert row.metrics is None


def test_training_dataset_version_changes_when_the_dataset_changes(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    """O valor gravado identifica o conteúdo lido, não a intenção da geração:
    um fato acrescentado entre dois treinos produz fingerprints diferentes."""
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    first = run_training(db_session, tmp_path)

    student = db_session.query(StudentModel).first()
    assert student is not None
    db_session.add(
        AttendanceRecordModel(
            student_id=student.id,
            classroom_id=seeded_classroom.id,
            date=date(2026, 4, 20),
            status=AttendanceStatus.ABSENT_UNJUSTIFIED,
        )
    )
    db_session.commit()

    second = run_training(db_session, tmp_path)

    assert first.training_dataset_version != second.training_dataset_version
    # O esquema de features não mudou, então esse campo não pode ter mudado.
    assert first.feature_schema_version == second.feature_schema_version


# ---------------------------------------------------------------------------
# evaluate.py persiste o relatório, não só o imprime
# ---------------------------------------------------------------------------


def test_evaluation_persists_the_report_with_the_disclaimer_attached(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    model_version = run_training(db_session, tmp_path)
    _seed_eval_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )

    report = run_evaluation(db_session)

    row = db_session.get(MLModelVersionModel, model_version.id)
    assert row is not None
    metrics = row.metrics
    assert metrics is not None
    assert metrics["metrics_schema_version"] == METRICS_SCHEMA_VERSION
    assert metrics["precision"] == report.precision
    assert metrics["recall"] == report.recall
    assert metrics["f1"] == report.f1
    assert metrics["confusion_matrix"] == report.confusion_matrix
    assert metrics["sample_count"] == report.sample_count
    assert metrics["dataset_split"] == "EVAL_DEMO"
    assert metrics["averaging"] == "macro"
    assert metrics["feature_columns"] == list(FEATURE_COLUMNS)
    assert metrics["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert metrics["evaluation_dataset_version"] == population_fingerprint(db_session)
    assert metrics["evaluated_at"] is not None
    # A ressalva viaja dentro do JSON: a métrica agora existe fora do terminal
    # de quem rodou o comando e nunca pode ser lida como validade preditiva
    # real (`AGENTS.md`).
    assert metrics["disclaimer"] == DISCLAIMER
    assert "synthetic dataset" in metrics["disclaimer"]


def test_reevaluation_overwrites_metrics_with_the_newer_dataset(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    """Reavaliar a mesma versão sobrescreve: `evaluation_dataset_version`
    dentro do JSON é o que diz sobre qual dataset a métrica guardada vale."""
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    model_version = run_training(db_session, tmp_path)
    _seed_eval_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    run_evaluation(db_session)
    first_metrics = dict(db_session.get(MLModelVersionModel, model_version.id).metrics)

    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        profile=SyntheticProfile.STABLE,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )
    run_evaluation(db_session)
    second_metrics = db_session.get(MLModelVersionModel, model_version.id).metrics

    assert second_metrics["sample_count"] == first_metrics["sample_count"] + 1
    assert (
        second_metrics["evaluation_dataset_version"] != first_metrics["evaluation_dataset_version"]
    )


# ---------------------------------------------------------------------------
# epic-5-retro-item-1: reordenar FEATURE_COLUMNS tem de ser detectado
# ---------------------------------------------------------------------------


def test_feature_vector_follows_feature_columns_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prova de que os três CLIs seguem `FEATURE_COLUMNS`: nenhum deles
    monta a matriz à mão, todos passam por `feature_vector()`. Reordenar a
    declaração reordena a matriz, em vez de deixar o pipeline receber colunas
    trocadas sem reclamar."""

    @dataclass(frozen=True)
    class _Row:
        attendance_rate: float
        grade_average: float
        assignment_completion_rate: float
        observation_count: int
        attendance_trend: float
        consecutive_absences: int
        grade_delta: float
        missing_assignment_delta: float

    row = _Row(0.9, 7.5, 1.0, 3, -0.2, 4, -1.5, 0.3)
    expected = [0.9, 7.5, 1.0, 3, -0.2, 4, -1.5, 0.3]
    assert feature_vector(row) == expected

    monkeypatch.setattr(feature_aggregation, "FEATURE_COLUMNS", tuple(reversed(FEATURE_COLUMNS)))
    assert feature_vector(row) == list(reversed(expected))


def test_reordering_feature_columns_changes_the_feature_schema_version() -> None:
    """Reordenação muda o identificador — é o que permite recusar um artefato
    serializado sob a ordem antiga."""
    reordered = tuple(reversed(FEATURE_COLUMNS))
    assert _compute_feature_schema_version(reordered) != FEATURE_SCHEMA_VERSION
    assert _compute_feature_schema_version(FEATURE_COLUMNS) == FEATURE_SCHEMA_VERSION


def test_require_feature_fields_rejects_a_row_missing_a_declared_feature() -> None:
    """Renomear uma coluna só de um lado falha no import do repositório, não
    no meio da construção da matriz."""

    @dataclass(frozen=True)
    class _IncompleteRow:
        attendance_rate: float
        grade_average: float

    with pytest.raises(RuntimeError, match="FEATURE_COLUMNS"):
        require_feature_fields(_IncompleteRow)


def test_require_matching_feature_schema_refuses_a_drifted_artifact() -> None:
    with pytest.raises(FeatureSchemaMismatchError, match="FEATURE_COLUMNS changed"):
        require_matching_feature_schema("20260101T000000-abcdef12", "sha256:000000000000")

    # `None` = linha anterior à migration 0015: desconhecido, não divergente.
    require_matching_feature_schema("20260101T000000-abcdef12", None)
    require_matching_feature_schema("20260101T000000-abcdef12", FEATURE_SCHEMA_VERSION)


def test_prediction_refuses_an_artifact_fitted_under_another_feature_schema(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    """O caso que nenhuma guarda de import pega: o artefato já está em disco,
    ajustado sob a ordem antiga, e `joblib.load` não sabe que as colunas
    andaram. Sem isto, `predict` produziria scores plausíveis para features
    trocadas."""
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    model_version = run_training(db_session, tmp_path)
    _seed_eval_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )

    row = db_session.get(MLModelVersionModel, model_version.id)
    row.feature_schema_version = _compute_feature_schema_version(tuple(reversed(FEATURE_COLUMNS)))
    db_session.commit()

    with pytest.raises(FeatureSchemaMismatchError):
        run_prediction(db_session)


def test_prediction_still_works_for_a_row_predating_the_provenance_columns(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
) -> None:
    """Sem backfill, linhas antigas têm `feature_schema_version` nulo. Recusar
    nesse caso seria bloquear por um palpite, não por evidência."""
    _seed_train_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )
    model_version = run_training(db_session, tmp_path)
    _seed_eval_cut(
        db_session, seeded_classroom, seeded_academic_period.id, seeded_assignment, seeded_user
    )

    row = db_session.get(MLModelVersionModel, model_version.id)
    row.feature_schema_version = None
    row.training_dataset_version = None
    db_session.commit()

    predictions = run_prediction(db_session)

    assert len(predictions) == 4
    assert all(prediction.model_version_id == model_version.id for prediction in predictions)
