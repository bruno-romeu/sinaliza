"""The offline scoring CLI — `python -m app.ml.predict`.

Mirrors `app/ml/train.py`'s shape (spec Code Map): opens its own
`SessionLocal()` directly, never wired into `composition.py`/FastAPI
`Depends`, never invoked by the web process or a scheduler. Loads a
`MLModelVersion`'s artifact via `joblib.load` (never refits or reimplements
preprocessing) — a `--model-version` nomeada, ou a mais recente quando o
argumento é omitido —, scores every `EVAL_DEMO` student read
through `PredictionRepository`, and inserts one `MLPrediction` row per
student with the probability the model associates with a non-`STABLE`
profile.

Re-running this command is deliberately non-destructive and non-deduping
(spec Never): each run is a fresh, independent batch of `MLPrediction` rows
tied to whichever `MLModelVersion` aquela execução selecionou — a nomeada por
`--model-version`, ou a mais recente quando o argumento é omitido. Era "a mais
recente naquele momento" até o `--model-version` existir (PR #54); a frase
deixou de valer quando a seleção explícita entrou.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.ml_prediction import MLPrediction
from app.domain.student import SyntheticProfile
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import MLPredictionModel
from app.ml.feature_aggregation import (
    FeatureSchemaMismatchError,
    feature_vector,
    require_matching_feature_schema,
)
from app.ml.model_version_selection import (
    ModelVersionNotFoundError,
    NoModelVersionError,
    model_version_not_found_message,
    select_model_version,
)
from app.ml.prediction_repository import PredictionRepository


class UnusableArtifactError(RuntimeError):
    """Raised when the `artifact_path` on the selected `MLModelVersion` row
    cannot be loaded — the file is gone, or it is there but is not a readable
    joblib. The CLI catches this, prints to stderr and exits non-zero,
    writing no `MLPrediction` rows.

    O caso não é hipotético: a linha `ml_model_version` e o `.joblib` moram em
    lugares com durabilidades diferentes. Até esta correção o
    `docker-compose.yml` declarava volume para o banco e **nenhum** para
    `/app/ml_artifacts`, então um `docker compose up --build` orfanava toda
    linha de procedência. O volume agora existe; esta guarda cobre o que
    sobra — um volume removido à mão, um artefato copiado pela metade, um
    banco restaurado de outra máquina. Sem ela, `joblib.load` respondia
    `FileNotFoundError` cru, ou `KeyError: 110` para arquivo corrompido, que
    não diz nada a quem rodou o comando (D3 de
    `docs/spec-qa-adversarial.md`)."""


class NoScoringDataError(RuntimeError):
    """Raised when zero `EVAL_DEMO` students exist (spec I/O Matrix "No
    EVAL_DEMO rows"). The CLI catches this, prints to stderr and exits
    non-zero, writing no `MLPrediction` rows."""


def _load_pipeline(version: str, artifact_path: str) -> Any:
    """`joblib.load` com as duas falhas de artefato traduzidas para
    `UnusableArtifactError`, na mesma forma 'mensagem acionável + nome do
    arquivo + o que fazer' que os outros modos de falha deste CLI já usam.

    A checagem de existência é explícita (e não só o `except OSError`) para
    que o caminho mais provável — o arquivo sumiu — tenha a mensagem mais
    direta. O `except Exception` largo cobre o artefato corrompido, cuja
    exceção depende do formato do lixo que está no arquivo: `joblib` responde
    `KeyError: 110` a um arquivo truncado, `UnpicklingError` a outros, e
    nenhuma delas é contrato público."""
    path = Path(artifact_path)
    if not path.is_file():
        raise UnusableArtifactError(
            f"The artifact for MLModelVersion {version!r} is missing from disk "
            f"({artifact_path}). Nothing was scored. Run `python -m app.ml.train` "
            "to produce a new version, or restore the artifact directory."
        )
    try:
        return joblib.load(path)
    except Exception as exc:  # noqa: BLE001 — ver docstring
        raise UnusableArtifactError(
            f"The artifact for MLModelVersion {version!r} could not be loaded "
            f"({artifact_path}): {type(exc).__name__}: {exc}. Nothing was scored. "
            "Run `python -m app.ml.train` to produce a new version, or restore "
            "the artifact directory."
        ) from exc


def run_prediction(
    session: Session,
    model_version: str | None = None,
) -> list[MLPrediction]:
    """Scores every `EVAL_DEMO` student with a `MLModelVersion`'s fitted
    `Pipeline` and persists one `MLPrediction` row each. Takes a
    `Session` (not `SessionLocal` directly) so the test suite can drive it
    inside its own rolled-back transaction, mirroring
    `app.ml.train.run_training`'s precedent.

    Não recebe `artifact_dir`, ao contrário de `run_training`: o caminho do
    artefato a carregar vem da própria linha `MLModelVersionModel`
    selecionada, nunca de um diretório que o chamador passe. O parâmetro
    existiu até esta onda só por paridade de assinatura com `run_training`
    (`spec-5-2` Code Map) e era ignorado — uma assinatura que anuncia uma
    entrada que a função não lê descreve mal o que a função faz.
    `app.ml.evaluate.run_evaluation`, escrita depois, já nasceu sem ele.

    `model_version` nomeia a `version` a usar; `None` (o padrão) mantém o
    comportamento anterior — a mais recente por `trained_at`."""
    model_version_row = select_model_version(session, model_version)
    if model_version_row is None:
        if model_version is not None:
            raise ModelVersionNotFoundError(model_version_not_found_message(model_version))
        raise NoModelVersionError(
            "No MLModelVersion rows were found — nothing to score with. "
            "Run `python -m app.ml.train` first."
        )

    scoring_rows = PredictionRepository(session).fetch_scoring_rows()
    if not scoring_rows:
        raise NoScoringDataError(
            "No EVAL_DEMO students were found — nothing to score. "
            "Run `python -m app.synthetic.generate` first."
        )

    # Antes de carregar: o artefato foi ajustado sob o mesmo esquema de
    # features que este código declara? Se não, recusar é a única resposta
    # honesta — as colunas não significam mais o que o pipeline espera.
    require_matching_feature_schema(
        model_version_row.version, model_version_row.feature_schema_version
    )

    pipeline = _load_pipeline(model_version_row.version, model_version_row.artifact_path)
    classes = pipeline.classes_.tolist()
    stable_index = classes.index(SyntheticProfile.STABLE.value)

    feature_matrix = [feature_vector(row) for row in scoring_rows]
    probabilities = pipeline.predict_proba(feature_matrix)

    now = datetime.now(UTC)
    predictions: list[MLPrediction] = []
    for row, probability_row in zip(scoring_rows, probabilities, strict=False):
        score = 1 - float(probability_row[stable_index])
        prediction = MLPrediction(
            id=uuid.uuid4(),
            student_id=row.student_id,
            model_version_id=model_version_row.id,
            score=score,
            created_at=now,
        )
        session.add(
            MLPredictionModel(
                id=prediction.id,
                student_id=prediction.student_id,
                model_version_id=prediction.model_version_id,
                score=prediction.score,
                created_at=prediction.created_at,
            )
        )
        predictions.append(prediction)

    session.commit()
    return predictions


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.predict",
        description=(
            "Score every EVAL_DEMO student with a trained MLModelVersion's "
            "artifact and persist one MLPrediction row each."
        ),
    )
    parser.add_argument(
        "--model-version",
        metavar="VERSION",
        default=None,
        help=(
            "Score with this MLModelVersion.version specifically (the value "
            "`python -m app.ml.train` prints). Omit to use the most recently "
            "trained one. An artifact fitted under a different feature schema "
            "is refused either way."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)
    # Return value unused (predict reads the artifact path off the selected
    # MLModelVersion row, not settings.ml_artifact_dir like train.py does) —
    # called anyway as a fail-fast config/env validation step, the same call
    # `app.ml.evaluate.main` makes for the same reason.
    get_settings()

    with SessionLocal() as session:
        try:
            predictions = run_prediction(session, args.model_version)
        except (
            NoModelVersionError,
            ModelVersionNotFoundError,
            NoScoringDataError,
            FeatureSchemaMismatchError,
            UnusableArtifactError,
        ) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        # Re-reads the same already-scored EVAL_DEMO cut (read-only, no
        # mutation happened in between) purely to report how many students
        # had some fact missing — noted in the summary, never fatal (spec
        # I/O Matrix "EVAL_DEMO student missing some facts").
        scoring_rows_by_student = {
            row.student_id: row for row in PredictionRepository(session).fetch_scoring_rows()
        }
        missing_facts_count = sum(
            1
            for prediction in predictions
            for row in [scoring_rows_by_student.get(prediction.student_id)]
            if row is not None
            and (
                row.attendance_rate is None
                or row.grade_average is None
                or row.assignment_completion_rate is None
            )
        )
        summary = (
            f"Scored {len(predictions)} EVAL_DEMO student(s) with "
            f"model_version_id={predictions[0].model_version_id} "
            f"({missing_facts_count} with missing facts imputed)."
        )

    print(summary)
    sys.exit(0)


if __name__ == "__main__":
    main()
