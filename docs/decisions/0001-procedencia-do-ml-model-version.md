# 0001 — Procedência persistida do `MLModelVersion`

- **Data:** 2026-11-04
- **Status:** aceita
- **Contexto no repositório:** `docs/spec-ml-model-provenance.md`, `docs/deferred-work.md` (entrada da onda de hardening sobre `MLModelVersionModel`), `epic-5-retro-item-1`

## Contexto

O `AGENTS.md` §"Versionamento de modelo" exige persistir seis campos por versão
de modelo: `model_version`, `training_dataset_version`, `feature_schema_version`,
`metrics`, `artifact_path`, `created_at`. A tabela criada pela migration 0011
persistia quatro. As métricas eram calculadas por `app/ml/evaluate.py` e
impressas no stdout; nada as gravava.

A consequência era verificável: dado um `MLModelVersion` no banco, não havia
como responder qual dataset o treinou nem como ele se saiu. Isso é relevante
além da higiene — o TCC defende reprodutibilidade do experimento, e o próprio
banco não sustentava a afirmação.

## Decisão 1 — `training_dataset_version` é o `population_fingerprint`

`app/ml/train.py` grava `population_fingerprint(session)`
(`app/synthetic/fingerprint.py`): SHA-256 sobre o conteúdo das tabelas geradas,
lido em ordem estável.

Por quê este valor:

- Já existe, já é testado para determinismo (mesma seed → hash idêntico, seed
  diferente → hash diferente) e **ainda não era persistido em lugar nenhum** —
  `generate.py` apenas o imprimia. Reaproveitá-lo não acrescenta mecanismo novo.
- É calculado **depois** da leitura do `TrainingRepository`, então descreve o
  conteúdo que aquele treino efetivamente viu.

Alternativa descartada: apontar para `synthetic_generation_runs` (seed +
`generator_version`). Isso registra a *intenção* da geração, não o estado do
banco: um fato editado depois da geração — pela própria aplicação web, que
escreve presença e notas — não mudaria a seed, e dois treinos sobre dados
diferentes ficariam com a mesma "versão de dataset". O fingerprint muda.

Limite conhecido e aceito: o fingerprint cobre a população inteira, incluindo o
corte `EVAL_DEMO`, não só o `TRAIN`. Não é um valor "do conjunto de treino"; é
o estado do dataset no momento do treino, do qual o corte `TRAIN` é função
determinística. Para o propósito — reproduzir o experimento — é o identificador
mais útil, e serve igualmente para registrar o dataset de avaliação.

## Decisão 2 — `feature_schema_version` é derivado de `FEATURE_COLUMNS`

`sha256:` + os 12 primeiros hex de `sha256("|".join(FEATURE_COLUMNS))`,
calculado em `app/ml/feature_aggregation.py`.

Por quê derivado e não uma constante mantida à mão (como `GENERATOR_VERSION`):
uma constante que alguém esquece de bumpar ao mexer nas features é exatamente a
classe de drift silencioso que `epic-5-retro-item-1` abriu. Um valor derivado
muda sozinho quando uma feature é acrescentada, removida, renomeada **ou
reordenada**.

É isso que permite a `predict`/`evaluate` recusarem um artefato serializado sob
outra ordem de colunas — o único ponto do problema de drift que nenhuma guarda
de tempo de import alcança, porque a divergência é entre o código de hoje e um
`.joblib` gravado ontem.

Custo: o valor não é legível por humanos. Aceito — quem precisa saber quais
features são lê `feature_columns` dentro de `metrics`, que é gravado por
extenso.

## Decisão 3 — formato de `metrics` (JSONB), escrito pelo `evaluate`

`metrics` é `JSONB` (não `JSON`): o relatório precisa ser consultável por campo
(`metrics->>'f1'`) sem reparsear texto.

Quem escreve é `python -m app.ml.evaluate`, **nunca** o treino: treinar e
avaliar no mesmo conjunto é proibido (`AGENTS.md` §Atalhos proibidos), então a
métrica só passa a existir depois de uma avaliação sobre o corte `EVAL_DEMO`.
Um `MLModelVersion` recém-treinado tem `metrics = NULL`, e isso é honesto.

Formato (versionado em `metrics_schema_version`, hoje `1`):

```json
{
  "metrics_schema_version": 1,
  "evaluated_at": "2026-11-04T12:00:00+00:00",
  "dataset_split": "EVAL_DEMO",
  "evaluation_dataset_version": "<population_fingerprint na avaliação>",
  "feature_schema_version": "sha256:...",
  "feature_columns": ["attendance_rate", "..."],
  "labels": ["STABLE", "..."],
  "averaging": "macro",
  "sample_count": 40,
  "missing_facts_count": 2,
  "precision": 0.0, "recall": 0.0, "f1": 0.0,
  "roc_auc": null, "pr_auc": null,
  "confusion_matrix": [[...]],
  "disclaimer": "These metrics measure the model's ability to recognize simulated patterns in the synthetic dataset. They are NOT a measure of real-world predictive validity."
}
```

Dois pontos não negociáveis nesse formato:

1. **O disclaimer viaja dentro do JSON, verbatim.** A métrica passa a existir
   fora do terminal de quem rodou o comando; quem a consultar daqui a seis meses
   precisa receber a ressalva junto do número, não depender de lembrar dela.
2. **A métrica carrega sobre o quê foi medida** — corte, rótulos, esquema de
   features e fingerprint do dataset de avaliação. Métrica sem o dataset a que
   se refere não é procedência.

`roc_auc`/`pr_auc` podem ser `null` (menos de duas classes presentes), o mesmo
"não computável" que o relatório impresso já reportava.

Reavaliar a mesma versão **sobrescreve** `metrics`. Não há ambiguidade porque
`evaluation_dataset_version` dentro do JSON diz sobre qual dataset o valor
guardado vale. Uma tabela `ml_evaluation` com histórico de avaliações foi
descartada: o problema era "a métrica não existe no banco", não "falta histórico
de avaliações", e uma tabela nova custaria FK, migration e superfície de leitura
para uma necessidade que ninguém demonstrou.

## Decisão 4 — colunas `NULL`-áveis, sem backfill

As três são `nullable=True` e a migration 0015 não preenche nada.

Uma linha de `MLModelVersion` gravada antes da migration não tem como saber qual
fingerprint de dataset a treinou nem sob qual esquema de features. Escrever ali
o fingerprint de hoje, ou o `FEATURE_SCHEMA_VERSION` de hoje, seria **procedência
fabricada** — o oposto exato do que a coluna existe para sustentar. `NULL`
significa "não registrado", e o código trata esse caso explicitamente:
`require_matching_feature_schema` deixa passar um `NULL` (desconhecido ≠
divergente) e recusa apenas uma divergência de fato.

Linhas novas sempre nascem com `training_dataset_version` e
`feature_schema_version` preenchidos, pelo `train.py`. A nulidade é uma
concessão ao passado, não uma permissão para o futuro.

## Limites

- Nada disso chega ao produto. `metrics` não é exposto por API nem pelo
  frontend: resultado de modelo é dado experimental, nunca afirmação sobre
  estudante (`AGENTS.md` §Score de modelo).
- As métricas persistidas são desempenho sobre o dataset sintético utilizado,
  nunca precisão em prever evasão escolar no mundo real.
