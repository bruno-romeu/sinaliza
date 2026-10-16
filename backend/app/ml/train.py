"""The offline model-training CLI — `python -m app.ml.train`.

Mirrors `app/synthetic/generate.py`'s shape (spec Code Map): opens its own
`SessionLocal()` directly, never wired into `composition.py`/FastAPI
`Depends`, never invoked by the web process or a scheduler (AD-3). Reads
exclusively through `TrainingRepository` (AD-11), fits the single
`build_pipeline()` `Pipeline` (RNF-03), serializes it under
`settings.ml_artifact_dir`, and inserts exactly one `MLModelVersion` row per
successful run (RF-17) — never overwriting a prior row or artifact file.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.ml_model_version import MLModelVersion
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import MLModelVersionModel
from app.ml.pipeline import build_pipeline
from app.ml.training_repository import TrainingRepository


class NoTrainingDataError(RuntimeError):
    """Raised when zero `TRAIN` rows have a non-null `synthetic_profile` —
    there is nothing to fit a `Pipeline` on (spec I/O Matrix "No usable
    training rows" / "TRAIN row missing label" rows, the latter only fatal
    once it empties the set). The CLI catches this, prints to stderr and
    exits non-zero, writing neither an artifact file nor an `MLModelVersion`
    row."""


def _version_string(now: datetime) -> str:
    """`datetime.now(timezone.utc).strftime(...)` (spec Design Notes) plus a
    short random suffix — two runs landing in the same microsecond tick
    (observed in practice, not just theoretically) would otherwise collide
    on `ml_model_version.version`'s UNIQUE constraint and raise an uncaught
    `IntegrityError` instead of failing cleanly; the suffix makes uniqueness
    not depend on clock resolution alone."""
    return f"{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"


def run_training(session: Session, artifact_dir: Path | str) -> MLModelVersion:
    """Fits one `Pipeline` on the `TRAIN` cut and persists it. Takes a
    `Session` (not `SessionLocal` directly) so the test suite can drive it
    inside its own rolled-back transaction, mirroring
    `app.synthetic.generate.run_generation`'s precedent."""
    rows = TrainingRepository(session).fetch_training_rows()
    if not rows:
        raise NoTrainingDataError(
            "No TRAIN students with a non-null synthetic_profile were found — "
            "nothing to train on. Run `python -m app.synthetic.generate` first."
        )

    feature_matrix = [
        [
            row.attendance_rate,
            row.grade_average,
            row.assignment_completion_rate,
            row.observation_count,
        ]
        for row in rows
    ]
    labels = [row.label.value for row in rows]

    pipeline = build_pipeline()
    pipeline.fit(feature_matrix, labels)

    resolved_artifact_dir = Path(artifact_dir)
    resolved_artifact_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    version = _version_string(now)
    # Versioned filename (never a fixed name) so a second run can never
    # overwrite a prior artifact file (spec Never).
    artifact_path = resolved_artifact_dir / f"model-{version}.joblib"
    joblib.dump(pipeline, artifact_path)

    model_version = MLModelVersion(
        id=uuid.uuid4(),
        version=version,
        artifact_path=str(artifact_path),
        trained_at=now,
        created_at=now,
    )
    session.add(
        MLModelVersionModel(
            id=model_version.id,
            version=model_version.version,
            artifact_path=model_version.artifact_path,
            trained_at=model_version.trained_at,
            created_at=model_version.created_at,
        )
    )
    session.commit()

    return model_version


def _build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m app.ml.train",
        description=(
            "Fit a single sklearn Pipeline on the synthetic TRAIN cut and "
            "persist a versioned artifact + MLModelVersion row."
        ),
    )


def main(argv: list[str] | None = None) -> None:
    _build_arg_parser().parse_args(argv)
    settings = get_settings()

    with SessionLocal() as session:
        try:
            model_version = run_training(session, settings.ml_artifact_dir)
        except NoTrainingDataError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        summary = (
            f"Trained model version={model_version.version} "
            f"artifact_path={model_version.artifact_path}"
        )

    print(summary)
    sys.exit(0)


if __name__ == "__main__":
    main()
