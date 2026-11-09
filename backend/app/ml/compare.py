"""A CLI de comparação de modelos — `python -m app.ml.compare`
(spec-comparacao-de-modelos-baseline).

O `AGENTS.md` §Modelos manda comparar antes de adotar. Este comando é a
comparação, feita código permanente em vez de medição de uma tarde: ele ajusta
cada candidato de `app/ml/candidates.py` sobre o corte `TRAIN` e o avalia sobre
o corte `EVAL_DEMO`, imprimindo uma tabela. Ser um comando é o ponto — numa
defesa, "por que floresta aleatória?" se responde rodando isto, não citando um
número que alguém mediu uma vez.

Mesma forma dos outros CLIs de `app/ml/`: abre seu próprio `SessionLocal()`,
não está em `composition.py`, não tem rota e nenhum scheduler o chama.

**Não escreve nada.** Nenhuma linha `MLModelVersion`, nenhum `.joblib` em
disco, nenhum `MLPrediction`. `ml_model_version` guarda modelos treinados para
serem usados; um candidato de comparação nunca pontuará ninguém, e registrá-lo
ali encheria a tabela de procedência de modelos descartáveis. A saída é o
stdout, e o resultado medido vai para `docs/model-evaluation.md` à mão, junto
da leitura do que ele significa.

Sem vazamento: ajuste e avaliação leem repositórios diferentes, sobre colunas
`dataset_split` diferentes da tabela `students` — exatamente a separação que
`train`/`evaluate` já usam. O `AGENTS.md` §"Atalhos proibidos" veda treinar e
avaliar no mesmo conjunto, e a comparação não afrouxa isso para caber numa
tabela.

Accuracy não aparece na tabela, pelo mesmo motivo que não aparece em
`evaluate`: o `AGENTS.md` veda escolher modelo por ela. O candidato
`dummy_most_frequent` existe justamente para que o leitor veja o que uma
métrica macro faz com um classificador que a Accuracy premiaria.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure.db.base import SessionLocal
from app.ml.candidates import CANDIDATE_BUILDERS
from app.ml.evaluate import (
    ALL_LABELS,
    DISCLAIMER,
    EvaluationReport,
    NoEvaluationDataError,
    compute_report,
)
from app.ml.evaluation_repository import EvaluationRepository
from app.ml.feature_aggregation import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION, feature_vector
from app.ml.train import NoTrainingDataError
from app.ml.training_repository import TrainingRepository

_NOT_COMPUTABLE = "n/a"


@dataclass(frozen=True)
class CandidateResult:
    """O relatório de um candidato, com o nome pelo qual ele aparece na
    tabela."""

    name: str
    report: EvaluationReport


def run_comparison(session: Session) -> list[CandidateResult]:
    """Ajusta cada candidato sobre `TRAIN` e o avalia sobre `EVAL_DEMO`,
    devolvendo um resultado por candidato na ordem declarada em
    `CANDIDATE_BUILDERS`.

    Recebe uma `Session` (e não `SessionLocal` diretamente) pelo mesmo motivo
    que `run_training`/`run_evaluation`: a suíte de testes dirige a função
    dentro da própria transação revertida.

    As duas leituras acontecem uma vez só, antes do laço: os candidatos são
    medidos sobre exatamente as mesmas linhas, de modo que a diferença entre
    duas linhas da tabela seja o modelo e nada mais."""
    training_rows = TrainingRepository(session).fetch_training_rows()
    if not training_rows:
        raise NoTrainingDataError(
            "No TRAIN students with a non-null synthetic_profile were found — "
            "nothing to fit the candidates on. Run "
            "`python -m app.synthetic.generate` first."
        )

    evaluation_rows = EvaluationRepository(session).fetch_evaluation_rows()
    if not evaluation_rows:
        raise NoEvaluationDataError(
            "No labeled EVAL_DEMO students were found — nothing to evaluate "
            "the candidates against. Run `python -m app.synthetic.generate` first."
        )

    # Ordem lida de `FEATURE_COLUMNS` via `feature_vector`, nunca escrita à
    # mão (decisão 0002) — a mesma função que `train`/`evaluate`/`predict`
    # usam, então os candidatos enxergam as colunas na mesma ordem que o
    # modelo de produção.
    feature_matrix = [feature_vector(row) for row in training_rows]
    labels = [row.label.value for row in training_rows]

    results: list[CandidateResult] = []
    for name, builder in CANDIDATE_BUILDERS:
        pipeline = builder()
        pipeline.fit(feature_matrix, labels)
        results.append(CandidateResult(name=name, report=compute_report(pipeline, evaluation_rows)))
    return results


def _format_metric(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else _NOT_COMPUTABLE


def format_comparison(results: list[CandidateResult]) -> str:
    """A tabela mais as matrizes de confusão.

    As matrizes vêm junto de propósito: a tabela diz *quanto* cada candidato
    erra, e a matriz diz **para onde** o erro vai. Confundir `FALLING_GRADES`
    com `COMBINED_DETERIORATION` e confundir qualquer coisa com `STABLE` são
    erros de naturezas diferentes, e o F1 macro agregado esconde a
    diferença."""
    sample_count = results[0].report.sample_count if results else 0
    missing_facts_count = results[0].report.missing_facts_count if results else 0

    header = (
        f"{'candidate':<22} {'precision':>10} {'recall':>10} "
        f"{'f1':>10} {'roc_auc':>10} {'pr_auc':>10}"
    )
    rows = "\n".join(
        f"{result.name:<22} "
        f"{result.report.precision:>10.4f} "
        f"{result.report.recall:>10.4f} "
        f"{result.report.f1:>10.4f} "
        f"{_format_metric(result.report.roc_auc):>10} "
        f"{_format_metric(result.report.pr_auc):>10}"
        for result in results
    )

    matrices = "\n\n".join(
        f"  {result.name} (rows=true, columns=predicted):\n"
        + "\n".join(
            f"    {label:<24} " + "  ".join(f"{value:>3}" for value in matrix_row)
            for label, matrix_row in zip(ALL_LABELS, result.report.confusion_matrix, strict=False)
        )
        for result in results
    )

    return (
        f"{DISCLAIMER}\n\n"
        f"Fitted on the TRAIN cut, scored on {sample_count} labeled EVAL_DEMO "
        f"student(s) ({missing_facts_count} with missing facts imputed).\n"
        f"Feature schema: {FEATURE_SCHEMA_VERSION} ({', '.join(FEATURE_COLUMNS)})\n"
        f"All averages are macro over the four SyntheticProfile labels. "
        f"Accuracy is deliberately absent (AGENTS.md).\n\n"
        f"{header}\n"
        f"{'-' * len(header)}\n"
        f"{rows}\n\n"
        f"Confusion matrices - column order: {', '.join(ALL_LABELS)}\n\n"
        f"{matrices}\n"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m app.ml.compare",
        description=(
            "Fit every candidate model on the synthetic TRAIN cut, score each "
            "on the labeled EVAL_DEMO cut, and print a comparison table "
            "(precision/recall/F1 macro, ROC-AUC, PR-AUC, confusion matrices). "
            "Measures ability to recognize simulated patterns in the synthetic "
            "dataset, not real-world predictive validity. Writes nothing: no "
            "MLModelVersion row, no artifact file, no prediction."
        ),
    )


def main(argv: list[str] | None = None) -> None:
    _build_arg_parser().parse_args(argv)
    # Valor não usado — a comparação não escreve artefato e portanto não lê
    # `ml_artifact_dir`. Chamado assim mesmo como validação de configuração
    # que falha cedo, espelhando `train`/`evaluate`/`predict`.
    get_settings()

    with SessionLocal() as session:
        try:
            results = run_comparison(session)
        except (NoTrainingDataError, NoEvaluationDataError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

    print(format_comparison(results))
    sys.exit(0)


if __name__ == "__main__":
    main()
