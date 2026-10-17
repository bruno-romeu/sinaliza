"""The offline evaluation CLI — `python -m app.ml.evaluate` (spec-5-3).

Mirrors `app/ml/predict.py`'s shape: opens its own `SessionLocal()` directly,
never wired into `composition.py`/FastAPI `Depends`, never invoked by the web
process or a scheduler. Loads the single most recently trained
`MLModelVersion`'s artifact via `joblib.load` (never refits), scores the full
`EVAL_DEMO` cut read through `EvaluationRepository` (ground-truth labels, no
`as_of()` truncation), and prints a precision/recall/F1/confusion-matrix/
ROC-AUC/PR-AUC report to stdout.

This is a pure stdout-reporting CLI — no persistence, matching the
`train`/`predict` precedent (spec Never). Every printed report states,
verbatim, that it measures "ability to recognize simulated patterns in the
synthetic dataset," never real-world predictive validity.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.student import SyntheticProfile
from app.infrastructure.db.base import SessionLocal
from app.infrastructure.db.models import MLModelVersionModel
from app.ml.evaluation_repository import EvaluationRepository

#: The fixed label set for precision/recall/F1/confusion-matrix — every
#: `SyntheticProfile` member, in a stable order, so an absent class shows as
#: a zero row/column instead of crashing (spec Boundaries).
_ALL_LABELS: list[str] = [profile.value for profile in SyntheticProfile]

#: Printed verbatim on every report (spec Boundaries: "Every printed report
#: includes, verbatim, the phrase..."). Never claims real-world predictive
#: validity.
DISCLAIMER = (
    "These metrics measure the model's ability to recognize simulated "
    "patterns in the synthetic dataset. They are NOT a measure of "
    "real-world predictive validity."
)

_NOT_COMPUTABLE = "not computable (fewer than 2 classes present in the evaluation labels)"


class NoModelVersionError(RuntimeError):
    """Raised when `ml_model_version` is empty — there is no trained artifact
    to evaluate with (spec I/O Matrix "No MLModelVersion exists"). The CLI
    catches this, prints to stderr and exits non-zero."""


class NoEvaluationDataError(RuntimeError):
    """Raised when zero labeled `EVAL_DEMO` students exist (spec I/O Matrix
    "No labeled EVAL_DEMO rows"). The CLI catches this, prints to stderr and
    exits non-zero."""


@dataclass(frozen=True)
class EvaluationReport:
    """The full printable evaluation result. `roc_auc`/`pr_auc` are `None`
    when fewer than 2 distinct classes are present in `y_true` (spec I/O
    Matrix "Only one class present in EVAL_DEMO labels") — reported as "not
    computable" rather than raising."""

    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]]
    roc_auc: float | None
    pr_auc: float | None
    missing_facts_count: int
    sample_count: int
    disclaimer: str = DISCLAIMER


def run_evaluation(session: Session) -> EvaluationReport:
    """Scores the full labeled `EVAL_DEMO` cut with the latest
    `MLModelVersion`'s fitted `Pipeline` and computes the evaluation report.
    Takes a `Session` (not `SessionLocal` directly) so the test suite can
    drive it inside its own rolled-back transaction, mirroring
    `app.ml.predict.run_prediction`'s precedent. Never refits the pipeline —
    `joblib.load`s the artifact verbatim and only calls `.predict`/
    `.predict_proba`."""
    model_version_row = session.execute(
        select(MLModelVersionModel)
        .order_by(MLModelVersionModel.trained_at.desc(), MLModelVersionModel.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if model_version_row is None:
        raise NoModelVersionError(
            "No MLModelVersion rows were found — nothing to evaluate. "
            "Run `python -m app.ml.train` first."
        )

    evaluation_rows = EvaluationRepository(session).fetch_evaluation_rows()
    if not evaluation_rows:
        raise NoEvaluationDataError(
            "No labeled EVAL_DEMO students were found — nothing to evaluate. "
            "Run `python -m app.synthetic.generate` first."
        )

    pipeline = joblib.load(model_version_row.artifact_path)

    feature_matrix = [
        [
            row.attendance_rate,
            row.grade_average,
            row.assignment_completion_rate,
            row.observation_count,
        ]
        for row in evaluation_rows
    ]
    y_true = [row.label.value for row in evaluation_rows]

    y_pred = pipeline.predict(feature_matrix)

    precision, recall, f1, _support = precision_recall_fscore_support(
        y_true, y_pred, labels=_ALL_LABELS, average="macro", zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=_ALL_LABELS)

    distinct_true_labels = set(y_true)
    roc_auc: float | None = None
    pr_auc: float | None = None
    if len(distinct_true_labels) >= 2:
        # Restricted to labels actually present in y_true (not the fixed
        # `_ALL_LABELS` 4-label set the confusion matrix uses) — a one-vs-rest
        # column for a label with zero true instances has no positives at
        # all, which makes that column's AUC undefined (NaN) and would
        # silently poison the macro average across every column.
        present_labels = [label for label in _ALL_LABELS if label in distinct_true_labels]

        probabilities = pipeline.predict_proba(feature_matrix)
        # `pipeline.classes_` may not be ordered/sized like `present_labels`
        # if TRAIN happened to omit a class — reindex probability columns
        # onto `present_labels` order, filling an absent class's column with
        # 0.0, so binarized `y_true` and the probability matrix line up
        # positionally.
        pipeline_classes = list(pipeline.classes_)
        probability_columns = [
            probabilities[:, pipeline_classes.index(label)]
            if label in pipeline_classes
            else np.zeros(len(evaluation_rows))
            for label in present_labels
        ]

        y_true_binarized = label_binarize(y_true, classes=present_labels)
        if len(present_labels) == 2:
            # `label_binarize` collapses the 2-class case to a single column
            # marking `present_labels[1]` as the positive class — match it to
            # that same single probability column instead of a 2D "macro over
            # 2 columns" average.
            y_true_for_auc = y_true_binarized.ravel()
            scores_for_auc = probability_columns[1]
            roc_auc = float(roc_auc_score(y_true_for_auc, scores_for_auc))
            pr_auc = float(average_precision_score(y_true_for_auc, scores_for_auc))
        else:
            aligned_probabilities = np.column_stack(probability_columns)
            roc_auc = float(roc_auc_score(y_true_binarized, aligned_probabilities, average="macro"))
            pr_auc = float(
                average_precision_score(y_true_binarized, aligned_probabilities, average="macro")
            )

    missing_facts_count = sum(
        1
        for row in evaluation_rows
        if row.attendance_rate is None
        or row.grade_average is None
        or row.assignment_completion_rate is None
    )

    return EvaluationReport(
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        confusion_matrix=matrix.tolist(),
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        missing_facts_count=missing_facts_count,
        sample_count=len(evaluation_rows),
    )


def _format_report(report: EvaluationReport) -> str:
    roc_auc_text = f"{report.roc_auc:.4f}" if report.roc_auc is not None else _NOT_COMPUTABLE
    pr_auc_text = f"{report.pr_auc:.4f}" if report.pr_auc is not None else _NOT_COMPUTABLE

    header = "    ".join(_ALL_LABELS)
    matrix_lines = "\n".join(
        f"  {label:<24} " + "  ".join(str(value) for value in row)
        for label, row in zip(_ALL_LABELS, report.confusion_matrix)
    )

    return (
        f"{report.disclaimer}\n\n"
        f"Evaluated {report.sample_count} EVAL_DEMO student(s) "
        f"({report.missing_facts_count} with missing facts imputed).\n\n"
        f"Precision (macro): {report.precision:.4f}\n"
        f"Recall (macro):    {report.recall:.4f}\n"
        f"F1 (macro):        {report.f1:.4f}\n"
        f"ROC-AUC (macro, one-vs-rest): {roc_auc_text}\n"
        f"PR-AUC (macro, one-vs-rest):  {pr_auc_text}\n\n"
        f"Confusion matrix (rows=true, columns=predicted):\n"
        f"  {'':<24} {header}\n"
        f"{matrix_lines}\n"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m app.ml.evaluate",
        description=(
            "Score the full labeled EVAL_DEMO cut with the most recently "
            "trained MLModelVersion's artifact and print a leakage-free "
            "evaluation report (precision/recall/F1/confusion-matrix/"
            "ROC-AUC/PR-AUC). Measures ability to recognize simulated "
            "patterns in the synthetic dataset, not real-world predictive "
            "validity. Pure stdout reporting — nothing is persisted."
        ),
    )


def main(argv: list[str] | None = None) -> None:
    _build_arg_parser().parse_args(argv)
    # Return value unused (evaluate reads the artifact path off the selected
    # MLModelVersion row, not settings.ml_artifact_dir like train.py/predict.py
    # do) — called anyway as a fail-fast config/env validation step, mirroring
    # the same call in those two CLIs.
    get_settings()

    with SessionLocal() as session:
        try:
            report = run_evaluation(session)
        except (NoModelVersionError, NoEvaluationDataError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

    print(_format_report(report))
    sys.exit(0)


if __name__ == "__main__":
    main()
