# 0002 — Ordem de features derivada de `FEATURE_COLUMNS`, não repetida à mão

- **Data:** 2026-11-04
- **Status:** aceita
- **Fecha:** `epic-5-retro-item-1` (`[fix-now]`, aberto desde 2026-10-20)

## Contexto

`FEATURE_COLUMNS` (`app/ml/feature_aggregation.py`) declara quais features
existem e em que ordem. `build_pipeline()` já derivava dela o número de colunas,
e `prediction_repository.py` tinha uma guarda de import comparando-a com uma
tupla literal.

Mas `train.py`, `evaluate.py` e `predict.py` montavam a matriz de features com a
ordem dos campos **escrita à mão**:

```python
feature_matrix = [
    [row.attendance_rate, row.grade_average, row.assignment_completion_rate, row.observation_count]
    for row in rows
]
```

Reordenar `FEATURE_COLUMNS` faria os três alimentarem o pipeline com colunas
trocadas **silenciosamente**: o modelo treina, as métricas saem, tudo errado. A
retro registrou duas saídas possíveis.

## Opção A — replicar a guarda de `prediction_repository` nos três CLIs

Copiar o `if tuple(FEATURE_COLUMNS) != (...): raise` para `train.py` e
`evaluate.py`.

Descartada. Três razões:

1. **Trata o sintoma.** A ordem continuaria repetida em quatro lugares; a guarda
   só avisaria que as cópias divergiram.
2. **Congela o esquema.** A guarda compara com uma tupla literal, então proíbe
   também *acrescentar* uma quinta feature — uma mudança legítima passaria a
   exigir editar quatro literais em lockstep, que é a mesma tarefa manual de
   antes, agora com um `raise` por cima.
3. **Não pega o caso que importa mais.** Um artefato `.joblib` já serializado
   sob a ordem antiga continua em disco. Nenhuma guarda de import compara o
   código de hoje com o pipeline de ontem.

## Opção B (escolhida) — os três CLIs iteram `FEATURE_COLUMNS`

A ordem passa a existir num lugar só. `feature_aggregation.feature_vector(row)`
devolve `[getattr(row, coluna) for coluna in FEATURE_COLUMNS]`, e é por ela que
`train`/`evaluate`/`predict` montam a matriz. Reordenar a declaração reordena as
três matrizes juntas: a consistência passa a ser por construção, não por
vigilância.

Resta o que a iteração sozinha não resolve, e por isso a decisão tem três peças:

1. **`feature_vector()`** — consistência entre os três CLIs.
2. **`require_feature_fields(RowType)`** — substitui a guarda literal de
   `prediction_repository` e passa a valer também para `TrainingRow` e
   `EvaluationRow`. Verifica estruturalmente que toda entrada de
   `FEATURE_COLUMNS` existe como campo da linha, então renomear uma coluna só de
   um lado falha no import do repositório, com mensagem clara, em vez de virar
   `AttributeError` no meio da construção da matriz. Continua `if`/`raise` e
   nunca `assert` — `assert` é removido sob `python -O` (o motivo já documentado
   na guarda original). Diferente da literal, **não** impede acrescentar uma
   feature nova.
3. **`feature_schema_version` persistido + `require_matching_feature_schema()`** —
   fecha o caso do artefato antigo. `predict`/`evaluate` comparam o esquema
   gravado na `MLModelVersion` com o do código em execução e recusam, com código
   de saída não-zero, em vez de pontuar com colunas trocadas. Ver decisão 0001.

Sem a peça 3, a opção B seria até *mais perigosa* que a A: tornaria a reordenação
inofensiva para código novo e deixaria os artefatos antigos silenciosamente
errados.

## Prova

`tests/test_ml_model_provenance.py`:

- `test_feature_vector_follows_feature_columns_order` — reordenar
  `FEATURE_COLUMNS` reordena o vetor produzido.
- `test_reordering_feature_columns_changes_the_feature_schema_version`.
- `test_require_feature_fields_rejects_a_row_missing_a_declared_feature`.
- `test_prediction_refuses_an_artifact_fitted_under_another_feature_schema`.
- `test_prediction_still_works_for_a_row_predating_the_provenance_columns`.

## O que não foi feito

Nenhuma mudança no `Pipeline`, no modelo (`RandomForestClassifier`) ou no
conjunto de features. Acrescentar features temporais — que o `AGENTS.md`
prefere a features instantâneas — é mudança de escopo próprio, não um apêndice
de uma correção de drift.
