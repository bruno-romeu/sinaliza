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
tied to whichever `MLModelVersion` was latest at that moment.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime

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
    model_version_not_found_message,
    select_model_version,
)
from app.ml.prediction_repository import PredictionRepository


class NoModelVersionError(RuntimeError):
    """Raised when `ml_model_version` is empty — there is no trained artifact
    to score with (spec I/O Matrix "No MLModelVersion exists"). The CLI
    catches this, prints to stderr and exits non-zero, writing no
    `MLPrediction` rows."""


class NoScoringDataError(RuntimeError):
    """Raised when zero `EVAL_DEMO` students exist (spec I/O Matrix "No
    EVAL_DEMO rows"). The CLI catches this, prints to stderr and exits
    non-zero, writing no `MLPrediction` rows."""


def run_prediction(
    session: Session,
    artifact_dir: object = None,
    model_version: str | None = None,
) -> list[MLPrediction]:
    """Scores every `EVAL_DEMO` student with a `MLModelVersion`'s fitted
    `Pipeline` and persists one `MLPrediction` row each. Takes a
    `Session` (not `SessionLocal` directly) so the test suite can drive it
    inside its own rolled-back transaction, mirroring
    `app.ml.train.run_training`'s precedent. `artifact_dir` is accepted only
    for call-shape parity with `run_training` (spec Code Map) but unused —
    the artifact path to load comes from the selected `MLModelVersionModel`
    row itself, never from a directory the caller passes in.

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

    pipeline = joblib.load(model_version_row.artifact_path)
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
    settings = get_settings()

    with SessionLocal() as session:
        try:
            predictions = run_prediction(session, settings.ml_artifact_dir, args.model_version)
        except (
            NoModelVersionError,
            ModelVersionNotFoundError,
            NoScoringDataError,
            FeatureSchemaMismatchError,
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
