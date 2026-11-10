"""QA adversarial — o caminho de ML quando o artefato nao coopera.

`app/ml/predict.py` e `app/ml/evaluate.py` tratam com mensagem acionavel e
`exit 1` todos os modos de falha que conhecem: `ml_model_version` vazia,
`--model-version` inexistente, nenhum estudante `EVAL_DEMO`, esquema de
features divergente. Este arquivo ataca o modo de falha que ficou de fora
(D3) e confirma, ao lado dele, que os outros realmente sao limpos — a
afirmacao "a guarda funciona" so vale testada contra o codigo, nao lida na
docstring.

Por que D3 morde de verdade: `docker-compose.yml` declara `postgres_data`
como volume nomeado e **nao declara volume para `/app/ml_artifacts`**, que o
`backend/Dockerfile` cria dentro da camada gravavel da imagem. Treinar dentro
do container grava a linha em um lugar que sobrevive e o `.joblib` em um que
nao sobrevive. Depois de `docker compose up --build`, toda linha de modelo
aponta para um arquivo ausente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AssignmentModel,
    ClassroomModel,
    MLPredictionModel,
    UserModel,
)
from app.ml.feature_aggregation import FeatureSchemaMismatchError
from app.ml.model_version_selection import ModelVersionNotFoundError, NoModelVersionError
from app.ml.predict import NoScoringDataError, run_prediction
from tests.test_ml_predict import _seed_eval_demo_student, _seed_model_version


@pytest.fixture()
def model_version_and_student(
    db_session: Session,
    seeded_classroom: ClassroomModel,
    seeded_academic_period,
    seeded_assignment: AssignmentModel,
    seeded_user: UserModel,
    tmp_path: Path,
):
    version = _seed_model_version(db_session, tmp_path, "qa", datetime(2026, 1, 1, tzinfo=UTC))
    _seed_eval_demo_student(
        db_session,
        seeded_classroom,
        with_facts=True,
        period_id=seeded_academic_period.id,
        assignment=seeded_assignment,
        author_user_id=seeded_user.id,
    )
    return version


# ---------------------------------------------------------------------------
# D3 — artefato ausente e artefato corrompido escapam como traceback
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D3: o `artifact_path` gravado na linha `ml_model_version` pode nao "
        "existir mais no disco — `/app/ml_artifacts` nao e volume no "
        "`docker-compose.yml`, enquanto `postgres_data` e. `joblib.load` "
        "levanta `FileNotFoundError` cru em vez do par "
        "'mensagem acionavel + exit 1' que todos os outros modos de falha "
        "deste CLI recebem. Fecha com uma checagem de existencia ao lado de "
        "`require_matching_feature_schema`, levantando um erro proprio que o "
        "`main` ja captura."
    ),
)
def test_qa_missing_artifact_file_raises_an_actionable_ml_error(
    db_session: Session, model_version_and_student
) -> None:
    Path(model_version_and_student.artifact_path).unlink()

    with pytest.raises(
        (NoModelVersionError, ModelVersionNotFoundError, NoScoringDataError)
    ) as excinfo:
        run_prediction(db_session)
    assert "train" in str(excinfo.value).lower()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D3 (segunda metade): um artefato truncado ou corrompido no disco faz "
        "o `joblib.load` levantar `KeyError: 110`, que nao diz nada a quem "
        "roda o comando. Mesma correcao: um erro proprio, capturado pelo "
        "`main`, nomeando o arquivo e a versao."
    ),
)
def test_qa_corrupt_artifact_file_raises_an_actionable_ml_error(
    db_session: Session, model_version_and_student
) -> None:
    Path(model_version_and_student.artifact_path).write_bytes(b"isto nao e um joblib")

    with pytest.raises(
        (NoModelVersionError, ModelVersionNotFoundError, NoScoringDataError)
    ) as excinfo:
        run_prediction(db_session)
    assert "train" in str(excinfo.value).lower()


def test_qa_no_prediction_row_is_written_when_the_artifact_is_missing(
    db_session: Session, model_version_and_student
) -> None:
    """A metade boa de D3: por pior que seja a mensagem, a falha acontece
    antes de qualquer `INSERT`. Nenhum `MLPrediction` parcial fica para tras."""
    Path(model_version_and_student.artifact_path).unlink()

    with pytest.raises(Exception):  # noqa: B017 — o tipo cru e exatamente o defeito
        run_prediction(db_session)
    assert db_session.query(MLPredictionModel).count() == 0


# ---------------------------------------------------------------------------
# Resultados negativos: as guardas que de fato existem
# ---------------------------------------------------------------------------


def test_qa_unknown_model_version_names_itself_and_writes_nothing(
    db_session: Session, model_version_and_student
) -> None:
    with pytest.raises(ModelVersionNotFoundError) as excinfo:
        run_prediction(db_session, "nao-existe")
    message = str(excinfo.value)
    assert "nao-existe" in message
    assert "app.ml.train" in message
    assert db_session.query(MLPredictionModel).count() == 0


def test_qa_naming_a_version_explicitly_does_not_bypass_the_schema_guard(
    db_session: Session, model_version_and_student
) -> None:
    """Escolher a versao diz *qual* artefato usar, nunca *apesar de que*. Um
    artefato ajustado sob outro esquema de features e recusado mesmo quando
    foi pedido pelo nome — a tentacao natural de quem implementa seria tratar
    `--model-version` como permissao."""
    model_version_and_student.feature_schema_version = "sha256:deadbeefcafe"
    db_session.commit()

    with pytest.raises(FeatureSchemaMismatchError) as excinfo:
        run_prediction(db_session, model_version_and_student.version)
    assert "sha256:deadbeefcafe" in str(excinfo.value)
    assert db_session.query(MLPredictionModel).count() == 0


def test_qa_schema_guard_runs_before_the_artifact_is_even_opened(
    db_session: Session, model_version_and_student
) -> None:
    """A ordem importa: com o esquema divergente **e** o arquivo ausente, o
    erro tem de ser o do esquema. Se `joblib.load` viesse antes, a mensagem
    acionavel seria substituida pelo traceback de arquivo ausente."""
    model_version_and_student.feature_schema_version = "sha256:deadbeefcafe"
    db_session.commit()
    Path(model_version_and_student.artifact_path).unlink()

    with pytest.raises(FeatureSchemaMismatchError):
        run_prediction(db_session, model_version_and_student.version)


def test_qa_null_metrics_never_block_scoring(
    db_session: Session, model_version_and_student
) -> None:
    """`metrics` e preenchido por `app.ml.evaluate`, nao por `train`. Um
    modelo ainda nao avaliado tem `metrics` nulo, e isso nao pode impedir a
    pontuacao — sao dois comandos independentes."""
    model_version_and_student.metrics = None
    db_session.commit()

    predictions = run_prediction(db_session)
    assert len(predictions) == 1
    assert 0.0 <= predictions[0].score <= 1.0


def test_qa_persisted_score_stays_an_internal_research_number(
    db_session: Session, model_version_and_student
) -> None:
    """`AGENTS.md` ("Score de modelo"): `predict_proba()` pode ser persistido
    como dado experimental, nunca exibido como probabilidade de evasao. O
    teste de exposicao da API ja garante que nenhuma rota devolve o score;
    aqui se fixa o outro lado — a linha persistida aponta para a versao de
    modelo que a produziu, que e o que a torna dado de pesquisa e nao numero
    solto."""
    predictions = run_prediction(db_session)
    rows = db_session.query(MLPredictionModel).all()
    assert len(rows) == len(predictions) == 1
    assert rows[0].model_version_id == model_version_and_student.id
