---
id: SPEC-ml-model-provenance
companions: []
sources:
  - docs/deferred-work.md
  - docs/sprint-status.yaml
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Procedência persistida do MLModelVersion e fim do drift de FEATURE_COLUMNS

## Why

Mandato + dor concreta. O `AGENTS.md` §"Versionamento de modelo" exige persistir seis campos por versão de modelo; `MLModelVersionModel` persiste quatro. Faltam `training_dataset_version`, `feature_schema_version` e `metrics`. As métricas são calculadas por `app/ml/evaluate.py` e **só vão para o stdout** — nada as grava. A consequência é verificável: dado um `MLModelVersion` no banco, não há como responder qual dataset o treinou nem como ele se saiu. O TCC defende a reprodutibilidade do experimento, e hoje o próprio banco não sustenta a afirmação.

Em paralelo, `FEATURE_COLUMNS` (`app/ml/feature_aggregation.py:39`) só está protegido contra reordenação em `prediction_repository.py`. `train.py:64-67`, `evaluate.py:118-121` e `predict.py:80-88` montam a matriz de features com a ordem dos campos escrita à mão. Reordenar `FEATURE_COLUMNS` passaria a alimentar o pipeline com colunas trocadas **silenciosamente**: o modelo treina, as métricas saem, tudo errado — e a métrica errada seria agora persistida, o que torna os dois problemas o mesmo problema.

## Capabilities

- **CAP-1**
  - **intent:** `python -m app.ml.train` registra, na `MLModelVersion` que cria, qual estado de dataset ele leu.
  - **success:** Após `run_training`, a linha tem `training_dataset_version` não nula e igual ao `population_fingerprint` do banco naquele momento; duas execuções sobre o mesmo dataset gravam o mesmo valor, e uma execução após o dataset mudar grava valor diferente.

- **CAP-2**
  - **intent:** `python -m app.ml.train` registra qual esquema de features o artefato foi treinado para consumir.
  - **success:** A linha tem `feature_schema_version` não nula e igual ao valor derivado de `FEATURE_COLUMNS`; reordenar ou renomear `FEATURE_COLUMNS` muda esse valor.

- **CAP-3**
  - **intent:** `python -m app.ml.evaluate` persiste o relatório que produz, além de imprimi-lo.
  - **success:** Após `run_evaluation`, `ml_model_version.metrics` da versão avaliada contém o relatório completo (precision/recall/F1/matriz de confusão/ROC-AUC/PR-AUC, contagens, rótulos e o disclaimer verbatim); o stdout permanece byte a byte o que era.

- **CAP-4**
  - **intent:** Treino, avaliação e inferência montam a matriz de features a partir de uma única declaração de ordem.
  - **success:** Nenhum dos três CLIs lista nomes de feature à mão; reordenar `FEATURE_COLUMNS` reordena as três matrizes juntas, provado por teste.

- **CAP-5**
  - **intent:** Inferência e avaliação recusam um artefato treinado sob um esquema de features diferente do atual.
  - **success:** Com `feature_schema_version` persistido divergente do atual, `predict`/`evaluate` levantam erro explícito e saem com código não-zero em vez de pontuar; com valor nulo (linha legada), prosseguem.

## Constraints

- As três colunas são **nullable, sem backfill**: linhas treinadas antes da coluna existir não têm como saber qual dataset as treinou, e inventar um valor seria procedência fabricada — o oposto do objetivo.
- `metrics` é escrito por `evaluate.py`, nunca por `train.py`: treinar e avaliar no mesmo conjunto é proibido pelo `AGENTS.md`, então a métrica só existe após um `evaluate` sobre o corte `EVAL_DEMO`.
- O disclaimer viaja **dentro** do JSON persistido: a métrica nunca deve poder ser lida fora do contexto "dataset sintético".
- Guardas são `if`/`raise`, nunca `assert` — `assert` é removido sob `python -O` (precedente documentado em `prediction_repository.py`).
- `feature_schema_version` é **derivado** de `FEATURE_COLUMNS`, não uma constante mantida à mão: uma constante que alguém esquece de bumpar é exatamente a classe de drift que esta história fecha.
- Nenhum modelo novo, nenhum XGBoost/LightGBM, nenhuma mudança no `Pipeline` sklearn.

## Non-goals

- Tabela `ml_evaluation` separada com histórico de avaliações. O item diferido pede coluna JSONB; reavaliar sobrescreve, e `evaluation_dataset_version` dentro do JSON diz sobre qual dataset a métrica guardada vale.
- Expor `metrics` por API ou no frontend. O `AGENTS.md` é explícito: resultado de modelo não vira afirmação sobre estudante.
- Backfill de linhas existentes de `MLModelVersion`.
- Persistir métricas por classe (hoje o relatório é macro); o formato JSON é versionado (`metrics_schema_version`) justamente para que isso possa ser acrescentado depois.

## Success signal

Dado um `MLModelVersion` qualquer gravado a partir desta mudança, um `SELECT` responde: qual fingerprint de dataset o treinou, sob qual esquema de features, e — se avaliado — como se saiu, com o disclaimer colado à métrica. E reordenar `FEATURE_COLUMNS` faz a suíte falhar em vez de produzir um modelo silenciosamente errado.

## Assumptions

- `population_fingerprint` cobre a população inteira (ambos os cortes), não só o `TRAIN`. Assumido adequado: o corte `TRAIN` é função determinística desse estado, e o mesmo valor serve para registrar o dataset de avaliação.
- `app/ml/` importar de `app/synthetic/` é aceitável: ambos são ferramental offline, fora do caminho web (AD-3 veda `presentation/`, não irmãos offline).
