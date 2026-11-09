# 0003 — Comparação de modelos como comando reproduzível, não medição pontual

- **Data:** 2026-11-09
- **Status:** aceita
- **Fecha:** `docs/model-evaluation.md` §Limites item 4 (comparação entre
  modelos inexistente), aberto desde a primeira versão de `build_pipeline()`
- **Spec:** `docs/spec-comparacao-de-modelos-baseline.md`

## Contexto

O `AGENTS.md` §Modelos manda começar simples e **comparar** antes de adotar
algo mais complexo. O `build_pipeline()` carregava um
`RandomForestClassifier(n_estimators=100, random_state=42)` desde a primeira
versão do código e nenhum baseline jamais fora medido contra ele. A pergunta
"por que floresta aleatória?" não tinha resposta registrada.

Duas formas de fechar isso estavam disponíveis.

## Decisão

**A comparação é código permanente — `python -m app.ml.compare` — e não uma
medição pontual registrada no documento.**

A alternativa, medir uma vez num script descartável e colar a tabela em
`docs/model-evaluation.md`, foi descartada por um motivo específico ao
contexto: numa defesa de TCC a banca pode pedir para ver rodando. Um número
colado não é verificável por quem lê; um comando é. O custo é um módulo a mais
em `app/ml/` com seus testes, e esse custo é baixo porque o comando reusa os
repositórios e a função de métrica que já existiam.

Três decisões subordinadas:

**1. O comando não escreve nada no banco.** Nenhuma linha `MLModelVersion`,
nenhum `.joblib`, nenhum `MLPrediction`. `ml_model_version` é a tabela de
procedência de modelos treinados para serem usados; um candidato de comparação
nunca vai pontuar estudante nenhum. Registrá-lo ali encheria a procedência de
modelos descartáveis e tornaria a consulta "quais modelos existiram" inútil.
A saída é stdout; o resultado medido vai para o documento à mão, junto da
leitura do que significa.

**2. Duas `strategy` de `DummyClassifier`, não uma.** `most_frequent` e
`stratified` respondem perguntas diferentes, e as duas importam.
`most_frequent` torna medido o argumento que `model-evaluation.md` §4 fazia no
papel — Accuracy 0,7167 com F1 macro 0,2087 — e é a demonstração de por que o
`AGENTS.md` veda escolher modelo por Accuracy. Mas é degenerado para média
macro: três das quatro classes recebem F1 zero por construção, então qualquer
modelo o supera sem provar nada. `stratified` sorteia nas proporções do treino
e é o nulo contra o qual "aprendeu alguma coisa" precisa ser demonstrado.
`prior` foi descartado: em predição dura é idêntico a `most_frequent`.

**3. Cada candidato é um `Pipeline` inteiro, com o pré-processamento que lhe
convém.** `LogisticRegression` recebe `StandardScaler`; as árvores não. A
alternativa — um pré-processamento comum a todos — penalizaria a regressão
logística por motivo de escala, não de capacidade, e produziria o resultado
"a floresta ganha" por artefato. O candidato `random_forest` é construído por
`build_pipeline()` em pessoa, nunca por uma réplica que poderia divergir do que
`train.py` serializa.

## Consequências

- A função de cálculo de métricas foi extraída de `run_evaluation` para
  `compute_report`, chamada pelos dois caminhos. Duas implementações de F1
  macro que divergissem tornariam qualquer comparação infalsificável.
- `app/ml/candidates.py` passa a ser a lista fechada do que entra na
  comparação. Um teste falha se um modelo de gradient boosting for
  acrescentado (`AGENTS.md` veda nominalmente).
- O comando não roda em CI: não há banco gerado lá, e gerar 200 estudantes a
  cada push custa mais do que rende. Os testes cobrem a mecânica — candidatos
  declarados, ausência de escrita, determinismo, saída ASCII — sem depender do
  dataset completo.
- **A medição mostrou que a floresta não vence.** A `LogisticRegression` tem F1
  macro maior. O `build_pipeline()` **não foi trocado**: uma decisão de modelo
  baseada em um único split, uma única seed e ~60 estudantes de avaliação seria
  tão pouco fundamentada quanto a escolha original. A divergência entre o
  medido e o código está registrada em `model-evaluation.md` §6 e §10.4, em vez
  de resolvida às pressas. Trocar o classificador exige, no mínimo, verificar
  se a vantagem sobrevive a outras seeds — e seria uma decisão própria.
