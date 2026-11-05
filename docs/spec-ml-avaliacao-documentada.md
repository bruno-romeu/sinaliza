---
id: SPEC-ml-avaliacao-documentada
companions: []
sources:
  - docs/decisions/0001-procedencia-do-ml-model-version.md
  - docs/decisions/0002-ordem-de-features-derivada-de-feature-columns.md
  - docs/spec-ml-model-provenance.md
  - docs/spec-5-3-avaliacao-do-modelo-com-split-de-dataset-sem-vazamento.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Documento de avaliação do ML e seleção explícita de versão de modelo

## Why

Dois problemas que só se tornaram visíveis depois que o PR #49 passou a
persistir procedência.

**Primeiro:** `docs/model-evaluation.md` **não existe**, apesar de o
`AGENTS.md` §Documentação listá-lo entre os documentos a manter atualizados
(confirmado por `ls docs/`). Com métrica agora gravada em
`ml_model_version.metrics`, existe resultado experimental registrado no banco e
**nenhum documento** que explique a estratégia de avaliação, os limites do
dataset sintético ou a ressalva que o `AGENTS.md` §"Avaliação de ML" exige
("desempenho sobre o dataset sintético utilizado", nunca "precisão do sistema em
prever evasão escolar no mundo real"). Para um TCC que defende
reprodutibilidade, é o documento que a banca procura primeiro.

**Segundo:** `app/ml/predict.py:63-67` e `app/ml/evaluate.py:155-159` selecionam
o `MLModelVersion` "mais recente" por `trained_at desc, id desc`. Não há como
avaliar ou pontuar com uma versão específica. A procedência está persistida, mas
a pergunta natural da banca — *"mostre este modelo específico sendo
reavaliado"* — não tem comando que a responda. A coluna `version` já é `UNIQUE`,
então fechar não exige mudança de schema.

## Capabilities

- **CAP-1**
  - **intent:** `docs/model-evaluation.md` descreve a estratégia de avaliação
    **que o código de fato implementa** — objetivo do experimento, split
    `TRAIN`/`EVAL_DEMO`, métricas calculadas, procedência registrada e limites.
  - **success:** Cada afirmação técnica do documento aponta para o arquivo e o
    símbolo que a sustentam (`train.py`, `evaluate.py`, `pipeline.py`,
    `feature_aggregation.py`, `population.py`), e o documento declara
    explicitamente o que os números **não** provam.

- **CAP-2**
  - **intent:** O documento registra as divergências conhecidas entre o que o
    `AGENTS.md` pede e o que o pipeline hoje faz, em vez de descrevê-las como
    resolvidas.
  - **success:** Existe uma seção nomeada de limitações que cita, no mínimo: a
    ausência de comparação entre modelos (§"Modelos" pede comparar
    `LogisticRegression` × `RandomForestClassifier`), e features instantâneas em
    vez de temporais (§"Features" prefere `attendance_trend`/`grade_delta`).

- **CAP-3**
  - **intent:** `python -m app.ml.evaluate --model-version <v>` avalia aquela
    `MLModelVersion` específica.
  - **success:** Com `--model-version` apontando para uma versão que não é a mais
    recente, o relatório impresso e o `metrics` gravado pertencem à versão
    pedida; sem o argumento, continua sendo a mais recente por
    `trained_at desc, id desc`.

- **CAP-4**
  - **intent:** `python -m app.ml.predict --model-version <v>` pontua com aquela
    `MLModelVersion` específica.
  - **success:** As `MLPrediction` criadas apontam para o `model_version_id` da
    versão pedida; sem o argumento, continua sendo a mais recente.

- **CAP-5**
  - **intent:** Uma `version` inexistente falha limpo, como o resto dos CLIs.
  - **success:** Mensagem no stderr nomeando a versão pedida, exit code não-zero,
    nenhuma linha escrita (nenhuma `MLPrediction`, nenhum `metrics`
    sobrescrito).

## Constraints

- O documento é escrito **a partir do código**, não a partir do que um projeto
  de ML genérico teria. Uma métrica que o `evaluate.py` não calcula não entra no
  documento como se entrasse.
- O documento nunca apresenta o número como validade preditiva real. O texto do
  `DISCLAIMER` (`evaluate.py`) é a formulação canônica e é citado verbatim.
- O comportamento padrão **sem** `--model-version` não muda: mesma query, mesmo
  desempate (`trained_at desc, id desc`), mesmas mensagens de erro.
- A seleção explícita **não** contorna `require_matching_feature_schema()`: uma
  versão escolhida à mão sob esquema de features divergente continua sendo
  recusada, pelo mesmo erro e mesmo exit code. Escolher a versão é dizer *qual*
  artefato, nunca *apesar de quê*.
- Nenhuma mudança de schema: a seleção é por `version` (`UNIQUE`), não por id
  novo nem coluna nova.
- Nenhum modelo novo, nenhum XGBoost/LightGBM, nenhuma mudança no `Pipeline`
  sklearn nem no conjunto de features.
- `metrics` continua fora da API e do frontend.

## Non-goals

- Corrigir as divergências que o documento registra (comparação de modelos,
  features temporais). Documentar ≠ implementar; mudar o modelo é escopo
  próprio.
- Remover o parâmetro morto `artifact_dir` de `run_prediction` (item diferido
  separado).
- Tabela de histórico de avaliações: reavaliar continua sobrescrevendo `metrics`,
  com `evaluation_dataset_version` dentro do JSON dizendo sobre qual dataset o
  valor vale (decisão 0001).
- Seleção por `id`, por fingerprint de dataset ou por "melhor F1". Só por
  `version`.
- Editar `docs/deferred-work.md` ou `docs/sprint-status.yaml` — autoridade do
  usuário.

## Success signal

Um leitor que abre `docs/model-evaluation.md` sabe, sem ler o código, o que foi
medido, sobre qual corte, com quais métricas, o que está registrado no banco
para reproduzir, e o que o número não prova. E, com a `version` que o documento
cita, consegue rodar `python -m app.ml.evaluate --model-version <v>` e ver
aquele modelo exato sendo reavaliado.

## Assumptions

- A `version` é identificador suficiente para a banca: `train.py` a imprime no
  resumo do treino e ela é `UNIQUE`.
- `metrics` sobrescrito por uma reavaliação explícita é aceito (já era o
  comportamento da reavaliação implícita, decisão 0001).
