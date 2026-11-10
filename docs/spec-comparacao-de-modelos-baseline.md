---
id: SPEC-comparacao-de-modelos-baseline
companions: []
sources:
  - docs/model-evaluation.md
  - docs/decisions/0001-procedencia-do-ml-model-version.md
  - docs/decisions/0002-ordem-de-features-derivada-de-feature-columns.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Comparacao de modelos: medir o piso e o simples contra a floresta

## Why

O `AGENTS.md` §Modelos manda comecar simples e **comparar** antes de adotar
algo mais complexo. O `build_pipeline()` carrega um
`RandomForestClassifier(n_estimators=100, random_state=42)` desde a primeira
versao do codigo e nenhum baseline jamais foi medido contra ele — `grep` por
`LogisticRegression`/`DummyClassifier` em `backend/` so retorna resultados
dentro do `.venv`. O proprio `docs/model-evaluation.md` §9.4 registra a
divergencia como item aberto.

O efeito pratico: "por que floresta aleatoria?" nao tem resposta registrada.
Nem sequer existe evidencia de que a floresta supere um classificador trivial.
Numa defesa de TCC isso e uma pergunta de uma frase sem resposta de uma frase.

Agrava o problema o desbalanceamento declarado em
`SYNTHETIC_PROFILE_PROPORTIONS`: 70% da base e `STABLE`. Um classificador que
respondesse `STABLE` para todo mundo marcaria 0,70 de Accuracy sem reconhecer
padrao algum. O `model-evaluation.md` §4 ja antecipa esse numero no papel, mas
nunca o mediu. Medi-lo converte um argumento em um dado.

Existe ainda um vies tecnico latente na comparacao. O pipeline atual e
`SimpleImputer` -> classificador, sem escalonamento. Arvores nao se importam
com escala; `LogisticRegression` se importa muito, e as features convivem em
escalas incompativeis (taxas em `[0,1]`, notas em `[0,10]`, contagens inteiras
sem teto). Comparar uma regressao logistica sem escalonar seria comparar com a
mao pesada de um lado da balanca — produziria o resultado "a floresta ganha"
por motivo errado.

## Capabilities

**CAP-1 — Comando reproduzivel de comparacao.**
*Intent:* existir um comando que ajusta cada modelo candidato sobre o corte
`TRAIN` e o avalia sobre o corte `EVAL_DEMO`, imprimindo uma tabela comparativa
com as mesmas metricas que `app/ml/evaluate.py` ja calcula.
*Success:* `uv run python -m app.ml.compare` roda sobre um banco gerado e
imprime, para cada candidato, Precision/Recall/F1 macro, ROC-AUC, PR-AUC e a
matriz de confusao 4x4, mais o disclaimer verbatim. Duas execucoes seguidas
sobre o mesmo banco produzem saida identica.

**CAP-2 — Conjunto de candidatos com piso explicito.**
*Intent:* a comparacao inclui, no minimo, dois pisos triviais
(`DummyClassifier`), o modelo simples que o `AGENTS.md` nomeia
(`LogisticRegression`) e o modelo em producao (`RandomForestClassifier`), cada
um com o pre-processamento que lhe e adequado.
*Success:* a tabela impressa lista `dummy_most_frequent`,
`dummy_stratified`, `logistic_regression` e `random_forest`, e o candidato
`random_forest` e construido por `build_pipeline()` — a funcao de producao, nao
uma replica.

**CAP-3 — Comparacao registrada na documentacao.**
*Intent:* o resultado medido vira texto em `docs/model-evaluation.md`, com a
leitura honesta do que ele mostra, inclusive se a floresta nao vencer.
*Success:* `docs/model-evaluation.md` ganha uma secao com a tabela medida, a
justificativa da `strategy` escolhida para cada `DummyClassifier`, e §9.4
deixa de descrever a comparacao como inexistente.

**CAP-4 — Metricas calculadas por um caminho so.**
*Intent:* a comparacao nao reimplementa Precision/Recall/F1/matriz/AUC; reusa
o mesmo codigo que `run_evaluation` usa, para que os numeros das duas saidas
sejam comparaveis por construcao.
*Success:* existe uma funcao pura de calculo de relatorio, chamada tanto por
`run_evaluation` quanto por `app/ml/compare.py`, e nenhuma chamada a
`precision_recall_fscore_support` fora dela.

## Constraints

- **Nao treinar e avaliar no mesmo conjunto.** Cada candidato ajusta sobre
  `TrainingRepository` (`dataset_split == TRAIN`) e e avaliado sobre
  `EvaluationRepository` (`dataset_split == EVAL_DEMO`). O corte ja existe nas
  colunas da tabela `students`; a comparacao nao cria outro.
- **Accuracy nao entra na tabela.** `AGENTS.md` §"Atalhos proibidos" veda
  escolher modelo por ela. A Accuracy do `dummy_most_frequent` pode ser citada
  **no texto** de `model-evaluation.md` como demonstracao do atalho, nunca como
  coluna de decisao.
- **`LogisticRegression` recebe `StandardScaler`.** Sem ele a comparacao e
  enviesada a favor da floresta por motivo de escala, nao de capacidade.
  `max_iter=1000` para que a nao-convergencia nao seja confundida com
  desempenho ruim.
- **`random_state=42` em todo candidato estocastico**, inclusive
  `dummy_stratified`. A comparacao precisa ser reexecutavel com o mesmo
  resultado.
- **`app.ml.compare` nao escreve no banco.** Nenhuma linha `MLModelVersion`,
  nenhum `.joblib` em disco, nenhum `MLPrediction`. A tabela de procedencia
  guarda modelos treinados para uso; um candidato de comparacao nunca sera
  usado para pontuar ninguem, e registra-lo ali poluiria a procedencia com
  modelos descartaveis. A saida e stdout mais o texto no documento.
- **Nao adicionar XGBoost/LightGBM.** Proibicao nominal do `AGENTS.md`.
- **Nada disso e exposto por API ou frontend.** `app/ml/` continua sem rota,
  sem entrada em `composition.py` e sem scheduler.
- **O resultado e "desempenho sobre o dataset sintetico utilizado"**, nunca
  validade preditiva real. O disclaimer verbatim ja existente acompanha a
  saida da comparacao.

## Non-goals

- **Nao e selecao automatica de modelo.** O comando mede e imprime; trocar o
  classificador de `build_pipeline()` e decisao humana registrada, nao efeito
  colateral de rodar a comparacao.
- **Nao ha ajuste de hiperparametros.** Nenhum `GridSearchCV`. Cada candidato
  roda nos valores declarados. §9.6 do `model-evaluation.md` continua valendo.
- **Nao ha validacao cruzada nem repeticao com seeds diferentes.** Uma unica
  particao, como hoje. §9.3 continua valendo e a comparacao herda essa
  limitacao — o que ela permite dizer e "neste split", nao "em geral".
- **Nao ha historico de comparacoes no banco.** Sem tabela nova.
- **Nao ha tratamento de desbalanceamento** (`class_weight`, reamostragem).
  §9.8 continua aberto; introduzi-lo aqui misturaria duas perguntas.

## Success signal

Rodar, sobre um banco gerado com `--seed 42`:

```bash
uv run python -m app.ml.compare
```

e obter uma tabela em que cada linha e um candidato e as colunas sao
Precision/Recall/F1 macro + AUCs, com as matrizes de confusao abaixo. O numero
de `random_forest` coincide com o que `python -m app.ml.evaluate` reporta para
um modelo treinado no mesmo banco — mesma metrica, mesmo corte, mesmo codigo de
calculo.

E, em `docs/model-evaluation.md`, a pergunta "por que floresta aleatoria?"
tendo uma resposta de uma frase sustentada por uma tabela — ou, se a floresta
nao vencer, a constatacao disso com a mesma clareza.

## Assumptions

1. **`stratified` e o piso certo para F1 macro; `most_frequent` e o piso certo
   para expor o atalho da Accuracy.** Por isso os dois entram.
   `most_frequent` prediz sempre `STABLE`: Accuracy alta, Recall macro 0,25,
   F1 macro degenerado — e exatamente a demonstracao que §4 do
   `model-evaluation.md` faz no papel. Mas ele e degenerado demais para servir
   de nulo honesto numa metrica macro, porque tres das quatro classes recebem
   F1 zero por construcao. `stratified` sorteia respeitando as proporcoes
   observadas no treino: acerta cada classe na taxa do acaso informado, que e o
   nulo contra o qual um modelo precisa provar que aprendeu alguma coisa.
   `prior` nao entra: em predicao dura ele e identico a `most_frequent` (difere
   so em `predict_proba`), e uma terceira linha com os mesmos numeros de outra
   linha e ruido na tabela.
2. **Fixar o pre-processamento por candidato nao quebra a comparacao.** Cada
   candidato e um `Pipeline` completo; o que se compara e "pipeline inteiro
   contra pipeline inteiro", que e a unidade que importa na pratica. A
   alternativa — um unico pre-processamento comum — penalizaria um dos lados.
3. **O corte `EVAL_DEMO` com ~60 estudantes basta para ordenar candidatos
   grosseiramente, nao para medi-los com precisao.** §9.2 ja registra que cada
   classe minoritaria chega a avaliacao com menos de dez exemplos. A
   comparacao herda essa variancia e o documento precisa dize-lo junto da
   tabela.

## Open questions

1. **Se a floresta nao vencer a regressao logistica, troca-se o
   `build_pipeline()`?** A decisao e humana e fica fora desta spec. O que esta
   spec garante e que a pergunta passa a ter dado. Se houver troca, ela e uma
   `docs/decisions/` propria, com o custo de invalidar artefatos ja treinados.
2. **A comparacao deve rodar no CI?** Hoje nao ha banco gerado em CI, e gerar
   200 estudantes a cada push e caro para o retorno. Fica como comando manual
   reproduzivel; os testes cobrem a mecanica (candidatos declarados, ausencia
   de escrita no banco, determinismo) sem depender de um dataset completo.
