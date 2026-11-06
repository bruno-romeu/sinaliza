"""The offline evaluation CLI — `python -m app.ml.evaluate` (spec-5-3).

Mirrors `app/ml/predict.py`'s shape: opens its own `SessionLocal()` directly,
never wired into `composition.py`/FastAPI `Depends`, never invoked by the web
process or a scheduler. Loads a `MLModelVersion`'s artifact via `joblib.load`
(never refits) — a `--model-version` nomeada, ou a mais recente quando o
argumento é omitido —, scores the full
`EVAL_DEMO` cut read through `EvaluationRepository` (ground-truth labels, no
`as_of()` truncation), and prints a precision/recall/F1/confusion-matrix/
ROC-AUC/PR-AUC report to stdout.

O relatório é impresso **e** gravado em `ml_model_version.metrics` (JSONB) da
versão avaliada. Era só stdout até a migration 0015: a métrica vivia apenas no
terminal de quem rodou o comando, e o `AGENTS.md` §Versionamento de modelo
exige `metrics` entre os campos persistidos. Nenhuma outra linha é criada —
`run_evaluation` atualiza a `MLModelVersion` que avaliou, e nada mais.

Every printed report states, verbatim, that it measures "ability to recognize
simulated patterns in the synthetic dataset," never real-world predictive
validity — e o mesmo texto vai dentro do JSON gravado, para que o número nunca
seja lido sem a ressalva.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.student import SyntheticProfile
from app.infrastructure.db.base import SessionLocal
from app.ml.evaluation_repository import EvaluationRepository
from app.ml.feature_aggregation import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
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
from app.synthetic.fingerprint import population_fingerprint

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

#: Versão do formato do JSON gravado em `ml_model_version.metrics`. Explícita
#: desde a primeira versão para que um relatório guardado hoje continue
#: interpretável quando o conteúdo mudar (por exemplo, se métricas por classe
#: forem acrescentadas às macro de hoje) — mesmo papel de
#: `synthetic.generate.GENERATOR_VERSION`.
METRICS_SCHEMA_VERSION = 1


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
    #: Preenchidos ao persistir; não participam do texto impresso.
    evaluated_at: datetime | None = None
    evaluation_dataset_version: str | None = None

    def as_metrics_payload(self) -> dict[str, Any]:
        """O relatório no formato gravado em `ml_model_version.metrics`.

        Carrega o `disclaimer` **verbatim** dentro do próprio JSON de
        propósito: a métrica passa a existir fora do terminal de quem rodou o
        comando, e `AGENTS.md` exige que ela nunca seja lida como "precisão em
        prever evasão escolar". A ressalva viaja colada ao número em vez de
        depender de quem consulta lembrar dela.

        Registra também sobre o quê a métrica foi medida — corte, rótulos,
        esquema de features e fingerprint do dataset de avaliação — porque uma
        métrica sem o dataset a que se refere não é procedência."""
        return {
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "dataset_split": "EVAL_DEMO",
            "evaluation_dataset_version": self.evaluation_dataset_version,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_columns": list(FEATURE_COLUMNS),
            "labels": list(_ALL_LABELS),
            "averaging": "macro",
            "sample_count": self.sample_count,
            "missing_facts_count": self.missing_facts_count,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "confusion_matrix": self.confusion_matrix,
            "disclaimer": self.disclaimer,
        }


def run_evaluation(session: Session, model_version: str | None = None) -> EvaluationReport:
    """Scores the full labeled `EVAL_DEMO` cut with a `MLModelVersion`'s fitted
    `Pipeline` and computes the evaluation report. Takes a `Session` (not
    `SessionLocal` directly) so the test suite can drive it inside its own
    rolled-back transaction, mirroring `app.ml.predict.run_prediction`'s
    precedent. Never refits the pipeline — `joblib.load`s the artifact verbatim
    and only calls `.predict`/`.predict_proba`. Ao final, grava o relatório em
    `metrics` da própria `MLModelVersion` avaliada (nenhuma linha nova é
    criada).

    `model_version` nomeia a `version` a avaliar; `None` (o padrão) mantém o
    comportamento anterior — a mais recente por `trained_at`. Poder apontar uma
    versão específica é o que torna "reavalie este modelo" um comando, agora que
    a procedência de cada versão está no banco."""
    model_version_row = select_model_version(session, model_version)
    if model_version_row is None:
        if model_version is not None:
            raise ModelVersionNotFoundError(model_version_not_found_message(model_version))
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

    require_matching_feature_schema(
        model_version_row.version, model_version_row.feature_schema_version
    )

    pipeline = joblib.load(model_version_row.artifact_path)

    feature_matrix = [feature_vector(row) for row in evaluation_rows]
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

    report = EvaluationReport(
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        confusion_matrix=matrix.tolist(),
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        missing_facts_count=missing_facts_count,
        sample_count=len(evaluation_rows),
        evaluated_at=datetime.now(UTC),
        evaluation_dataset_version=population_fingerprint(session),
    )

    # O relatório deixa de viver só no stdout: fica na própria
    # `MLModelVersion` avaliada (`AGENTS.md` §Versionamento de modelo exige
    # `metrics` entre os campos persistidos). Reavaliar a mesma versão
    # sobrescreve — `evaluation_dataset_version` dentro do JSON diz sobre qual
    # dataset a métrica guardada vale, então o valor nunca é ambíguo.
    model_version_row.metrics = report.as_metrics_payload()
    session.commit()

    return report


def _format_report(report: EvaluationReport) -> str:
    roc_auc_text = f"{report.roc_auc:.4f}" if report.roc_auc is not None else _NOT_COMPUTABLE
    pr_auc_text = f"{report.pr_auc:.4f}" if report.pr_auc is not None else _NOT_COMPUTABLE

    header = "    ".join(_ALL_LABELS)
    matrix_lines = "\n".join(
        f"  {label:<24} " + "  ".join(str(value) for value in row)
        for label, row in zip(_ALL_LABELS, report.confusion_matrix, strict=False)
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
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.evaluate",
        description=(
            "Score the full labeled EVAL_DEMO cut with a trained "
            "MLModelVersion's artifact and print a leakage-free "
            "evaluation report (precision/recall/F1/confusion-matrix/"
            "ROC-AUC/PR-AUC). Measures ability to recognize simulated "
            "patterns in the synthetic dataset, not real-world predictive "
            "validity. The report is printed and also stored on the evaluated "
            "MLModelVersion's metrics column."
        ),
    )
    parser.add_argument(
        "--model-version",
        metavar="VERSION",
        default=None,
        help=(
            "Evaluate this MLModelVersion.version specifically (the value "
            "`python -m app.ml.train` prints). Omit to evaluate the most "
            "recently trained one. An artifact fitted under a different "
            "feature schema is refused either way."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_arg_parser().parse_args(argv)
    # Return value unused (evaluate reads the artifact path off the selected
    # MLModelVersion row, not settings.ml_artifact_dir like train.py/predict.py
    # do) — called anyway as a fail-fast config/env validation step, mirroring
    # the same call in those two CLIs.
    get_settings()

    with SessionLocal() as session:
        try:
            report = run_evaluation(session, args.model_version)
        except (
            NoModelVersionError,
            ModelVersionNotFoundError,
            NoEvaluationDataError,
            FeatureSchemaMismatchError,
        ) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

    print(_format_report(report))
    sys.exit(0)


if __name__ == "__main__":
    main()
