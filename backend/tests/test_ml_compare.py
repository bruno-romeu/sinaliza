"""Testes de `python -m app.ml.compare` (spec-comparacao-de-modelos-baseline).

Cobrem a mecânica da comparação — quais candidatos entram, que ela não escreve
no banco, que é determinística e que recusa um banco sem dados — e não os
*valores* medidos. O número que a comparação produz depende do dataset gerado
(200 estudantes) e vive em `docs/model-evaluation.md`; prendê-lo num assert
transformaria qualquer mudança legítima no gerador em teste vermelho.

Reusa os helpers de semeadura de `test_ml_evaluate.py` em vez de duplicá-los:
são as mesmas linhas `TRAIN`/`EVAL_DEMO` que aquele módulo já sabe montar.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.domain.student import SyntheticProfile
from app.infrastructure.db.models import (
    AssignmentModel,
    ClassroomModel,
    MLModelVersionModel,
    MLPredictionModel,
    UserModel,
)
from app.ml.candidates import CANDIDATE_NAMES, build_candidate
from app.ml.compare import format_comparison, run_comparison
from app.ml.evaluate import DISCLAIMER, NoEvaluationDataError
from app.ml.feature_aggregation import FEATURE_COLUMNS
from app.ml.train import NoTrainingDataError
from tests.test_ml_evaluate import _seed_eval_demo_student, _seed_train_student

_PROFILES = (
    SyntheticProfile.STABLE,
    SyntheticProfile.STABLE,
    SyntheticProfile.FALLING_ATTENDANCE,
    SyntheticProfile.FALLING_GRADES,
    SyntheticProfile.COMBINED_DETERIORATION,
)


def _seed_both_cuts(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    for profile in _PROFILES:
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )
    for profile in _PROFILES:
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )


def test_candidate_list_covers_floor_simple_and_production_model() -> None:
    """O `AGENTS.md` §Modelos pede o piso, o simples e o que está em uso. Este
    teste é o que impede alguém remover silenciosamente um deles da tabela e
    deixar a comparação sem o termo de comparação que a torna um argumento."""
    assert CANDIDATE_NAMES == (
        "dummy_most_frequent",
        "dummy_stratified",
        "logistic_regression",
        "random_forest",
    )


def test_no_gradient_boosting_candidate_is_declared() -> None:
    """`AGENTS.md` §"Atalhos proibidos" veda XGBoost/LightGBM nominalmente. A
    proibição é anterior à medição, então ela é testada e não apenas
    comentada."""
    for name in CANDIDATE_NAMES:
        classifier = build_candidate(name).named_steps["classifier"]
        assert "XGB" not in type(classifier).__name__
        assert "LGBM" not in type(classifier).__name__


def test_logistic_regression_candidate_is_scaled() -> None:
    """Sem `StandardScaler` a regressão logística sai pior por motivo de
    escala, não de capacidade, e a comparação passaria a favorecer a floresta
    por um artefato de pré-processamento."""
    preprocessor = build_candidate("logistic_regression").named_steps["preprocessor"]
    _name, transformer, _columns = preprocessor.transformers[0]
    assert "scaler" in transformer.named_steps


def test_random_forest_candidate_is_the_production_pipeline() -> None:
    """O candidato `random_forest` tem de ser o `build_pipeline()` de
    produção. Uma réplica declarada à parte poderia divergir do que
    `train.py` serializa, e a comparação mediria um modelo que não roda."""
    from app.ml.pipeline import build_pipeline

    assert type(build_candidate("random_forest").named_steps["classifier"]) is type(
        build_pipeline().named_steps["classifier"]
    )


def test_every_candidate_sees_every_feature_column() -> None:
    """A largura do pré-processamento é derivada de `FEATURE_COLUMNS`
    (decisão 0002) em todos os candidatos, não escrita à mão em cada um."""
    for name in CANDIDATE_NAMES:
        _name, _transformer, columns = (
            build_candidate(name).named_steps["preprocessor"].transformers[0]
        )
        assert list(columns) == list(range(len(FEATURE_COLUMNS)))


def test_run_comparison_returns_one_result_per_candidate(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    _seed_both_cuts(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user
    )

    results = run_comparison(db_session)

    assert [result.name for result in results] == list(CANDIDATE_NAMES)
    # Todos medidos sobre exatamente as mesmas linhas: se um candidato tivesse
    # visto outro recorte, a diferença entre duas linhas da tabela deixaria de
    # ser o modelo.
    assert len({result.report.sample_count for result in results}) == 1
    assert results[0].report.sample_count == len(_PROFILES)


def test_run_comparison_writes_nothing_to_the_database(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    """`ml_model_version` guarda modelos treinados para serem usados. Um
    candidato de comparação nunca pontuará ninguém; registrá-lo ali encheria a
    procedência de modelos descartáveis."""
    _seed_both_cuts(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user
    )

    run_comparison(db_session)

    assert db_session.query(MLModelVersionModel).count() == 0
    assert db_session.query(MLPredictionModel).count() == 0


def test_run_comparison_is_deterministic(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    """`random_state` fixo em todo candidato estocástico — inclusive no
    `DummyClassifier` `stratified`, que sorteia. Uma comparação que muda de
    resultado a cada execução não sustenta uma afirmação."""
    _seed_both_cuts(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user
    )

    first = run_comparison(db_session)
    second = run_comparison(db_session)

    assert [r.report.f1 for r in first] == [r.report.f1 for r in second]
    assert [r.report.confusion_matrix for r in first] == [r.report.confusion_matrix for r in second]


def test_run_comparison_refuses_an_empty_train_cut(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    for profile in _PROFILES:
        _seed_eval_demo_student(
            db_session,
            seeded_classroom,
            profile=profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    with pytest.raises(NoTrainingDataError):
        run_comparison(db_session)


def test_run_comparison_refuses_an_empty_eval_cut(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    for profile in _PROFILES:
        _seed_train_student(
            db_session,
            seeded_classroom,
            profile,
            with_facts=True,
            period_id=seeded_academic_period.id,
            assignment=seeded_assignment,
            author_user_id=seeded_user.id,
        )

    with pytest.raises(NoEvaluationDataError):
        run_comparison(db_session)


def test_formatted_comparison_carries_the_disclaimer_and_omits_accuracy(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    """O `AGENTS.md` §"Avaliação de ML" exige a ressalva junto do número, e
    §"Atalhos proibidos" veda escolher modelo por Accuracy — que portanto não
    aparece como coluna."""
    _seed_both_cuts(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user
    )

    output = format_comparison(run_comparison(db_session))

    assert DISCLAIMER in output
    assert "accuracy" not in output.lower().replace(
        "accuracy is deliberately absent (agents.md).", ""
    )
    for name in CANDIDATE_NAMES:
        assert name in output


def test_formatted_comparison_is_ascii(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
) -> None:
    """O terminal Windows do projeto corrompe não-ASCII. O relatório de
    `evaluate` já é ASCII puro; este mantém a mesma propriedade em vez de sair
    com travessões quebrados na defesa."""
    _seed_both_cuts(
        db_session, seeded_classroom, seeded_academic_period, seeded_assignment, seeded_user
    )

    format_comparison(run_comparison(db_session)).encode("ascii")
