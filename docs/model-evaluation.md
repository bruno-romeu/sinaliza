# Avaliação do modelo experimental

Este documento descreve **o que o código deste repositório de fato faz** ao
treinar e avaliar o modelo, e o que os números resultantes não provam. Cada
afirmação técnica aponta para o arquivo que a sustenta. Onde o pipeline diverge
do que o `AGENTS.md` pede, a divergência está registrada em §Limites, não
maquiada.

Documento exigido por `AGENTS.md` §Documentação.

## 1. Objetivo declarado do experimento

O `AGENTS.md` §"Machine Learning" fixa o objetivo em uma frase:

> avaliar se um pipeline consegue distinguir padrões simulados construídos no
> dataset.

Não é avaliar capacidade de prever evasão escolar real. Não é demonstrar
eficácia pedagógica. O dataset é sintético e cada estudante fictício recebeu um
**perfil de trajetória com regra conhecida** (`SyntheticProfile`, escrito pelo
gerador em `backend/app/synthetic/population.py`). A pergunta do experimento é:
um classificador treinado sobre um recorte desses dados consegue recuperar,
num recorte que ele nunca viu, o perfil que o gerador escreveu?

Essa é uma pergunta sobre o pipeline, não sobre estudantes. A resposta — boa ou
ruim — não autoriza nenhuma afirmação sobre pessoas reais.

O alvo da classificação é o próprio `SyntheticProfile`, com quatro valores
(`backend/app/domain/student.py`):

| rótulo | proporção gerada |
|---|---|
| `STABLE` | 0,70 |
| `FALLING_ATTENDANCE` | 0,12 |
| `COMBINED_DETERIORATION` | 0,10 |
| `FALLING_GRADES` | 0,08 |

(`SYNTHETIC_PROFILE_PROPORTIONS`, `backend/app/synthetic/calibration.py`.)

Os rótulos são **desbalanceados por construção** — 70% da base é `STABLE`.
É por isso que Accuracy não serve aqui, como a §4 detalha.

## 2. O split `TRAIN` / `EVAL_DEMO`

O `AGENTS.md` §"Atalhos proibidos" veda "treinar e avaliar no mesmo conjunto".
A razão não é formal: um `RandomForestClassifier` memoriza suas amostras de
treino com folga, e medir sobre elas devolve um número que reflete memorização,
não reconhecimento de padrão. O número ficaria alto e não significaria nada.

A separação é feita **na geração do dataset**, não no momento do treino
(`backend/app/synthetic/population.py`):

- Cada estudante recebe `dataset_split = TRAIN` ou `EVAL_DEMO`. Os valores são
  colunas da própria tabela `students`, não um parâmetro de uma chamada de
  `train_test_split`.
- A atribuição é determinística: a ordem vem de
  `derived_key(seed, "split", student_id)`, então depende só de `(seed,
  student_id)` — nunca da ordem de inserção. Mesma seed, mesmo split.
- A proporção padrão é `TRAIN_EVAL_SPLIT_RATIO = 0.7`
  (`backend/app/synthetic/calibration.py`), com a ressalva registrada ali: esse
  número é decisão de metodologia, não parâmetro calibrado contra base pública.
- A divisão é aplicada **por turma**, com o número de `TRAIN` de cada turma
  limitado a `[1, tamanho - 1]`: toda turma contém os dois recortes. Sem isso,
  uma turma inteira poderia cair num só lado e o recorte de avaliação
  carregaria o efeito da turma junto com o do perfil.

Cada lado é lido por um repositório próprio, e nenhum dos dois enxerga o outro:

- `TrainingRepository` (`backend/app/ml/training_repository.py`) lê **apenas**
  `dataset_split == TRAIN` com `synthetic_profile` não nulo. É a única porta de
  leitura do treino.
- `EvaluationRepository` (`backend/app/ml/evaluation_repository.py`) lê
  **apenas** `dataset_split == EVAL_DEMO`, e só linhas com rótulo — sem rótulo
  não há contra o quê comparar a predição.

Nenhum dos dois chama `filter_as_of`/`filter_eval_demo_students`
(`backend/app/infrastructure/repositories/base.py`): aquelas são as invariantes
do caminho web, e a avaliação lê o desfecho completo do ano, sem truncar em
"hoje".

## 3. As features

Quatro agregados por estudante, declarados em um lugar só — `FEATURE_COLUMNS`
em `backend/app/ml/feature_aggregation.py`:

| coluna | significado | ausente quando |
|---|---|---|
| `attendance_rate` | presenças / total de registros de chamada | `None` se o estudante não tem registro de chamada |
| `grade_average` | média das notas | `None` se não tem nota |
| `assignment_completion_rate` | entregues / total de atividades | `None` se não tem entrega registrada |
| `observation_count` | nº de observações pedagógicas | `0` (é contagem; "nenhuma" é valor real) |

A ordem dessa tupla é o contrato: `train`, `evaluate` e `predict` montam a
matriz por `feature_vector(row)`, que itera `FEATURE_COLUMNS`, e nenhum dos três
lista nomes de feature à mão. Reordenar a declaração reordena as três matrizes
juntas (decisão `docs/decisions/0002`).

Valores `None` não excluem a linha: o `SimpleImputer(strategy="mean")` dentro do
pipeline os preenche. A contagem de linhas com algum fato ausente é reportada
junto da métrica (`missing_facts_count`), para que uma métrica calculada sobre
muitos valores imputados não passe por métrica calculada sobre dados completos.

## 4. O que é medido, e o que não é

Calculado por `run_evaluation` (`backend/app/ml/evaluate.py`), sobre o recorte
`EVAL_DEMO` inteiro:

- **Precision, Recall e F1**, macro-averaged, `zero_division=0`, sobre o
  conjunto fixo dos quatro rótulos de `SyntheticProfile`.
- **Matriz de confusão** 4×4, com o mesmo conjunto fixo de rótulos — uma classe
  ausente aparece como linha/coluna zerada em vez de sumir da tabela.
- **ROC-AUC** e **PR-AUC**, one-vs-rest, macro. Restritas aos rótulos
  efetivamente presentes em `y_true`: uma coluna one-vs-rest para um rótulo sem
  nenhum positivo tem AUC indefinida e envenenaria a média macro. Com menos de
  duas classes presentes, as duas são reportadas como *não computáveis*, não
  como zero.

**Accuracy não é calculada — em lugar nenhum.** O `AGENTS.md` §"Atalhos
proibidos" veda escolher modelo apenas por Accuracy, e com 70% da base em
`STABLE` um classificador que respondesse `STABLE` para todo mundo marcaria 0,70
de Accuracy sem ter reconhecido padrão algum. Esse mesmo classificador teria
Recall macro de 0,25 e F1 macro próximo de 0,21. A média macro é a escolha que
torna o atalho visível: ela pesa as quatro classes igualmente, então ignorar as
três minoritárias custa caro na métrica.

A matriz de confusão está no relatório pelo mesmo motivo: ela mostra **para
onde** o erro vai — confundir `FALLING_GRADES` com `COMBINED_DETERIORATION` e
confundir qualquer coisa com `STABLE` são erros de naturezas diferentes, e um
número agregado esconde a diferença.

## 5. O pipeline

Um único `Pipeline` do Scikit-Learn (`backend/app/ml/pipeline.py`), como o
`AGENTS.md` §Pipeline pede — preprocessing fundido ao modelo, para que a
inferência não possa reimplementar o preprocessing de outro jeito:

```text
ColumnTransformer(SimpleImputer(strategy="mean"))
→ RandomForestClassifier(n_estimators=100, random_state=42)
```

`random_state` fixo: duas execuções sobre o mesmo dataset produzem o mesmo
modelo. O artefato é serializado com `joblib` sob um nome versionado, e
`evaluate`/`predict` fazem `joblib.load` do arquivo — **nunca** re-treinam.

## 6. Procedência: o que fica registrado

`AGENTS.md` §"Versionamento de modelo". Cada execução de `python -m app.ml.train`
insere uma linha em `ml_model_version` com:

| campo | escrito por | o que permite reproduzir |
|---|---|---|
| `version` | `train` | identifica a execução; é `UNIQUE`, e é o valor aceito por `--model-version` |
| `artifact_path` | `train` | o `.joblib` exato que foi avaliado |
| `trained_at` / `created_at` | `train` | quando |
| `training_dataset_version` | `train` | `population_fingerprint` do banco **no momento da leitura** — SHA-256 sobre o conteúdo das tabelas geradas. Dois treinos sobre conteúdos diferentes nunca compartilham esse valor, mesmo que a seed de geração seja a mesma |
| `feature_schema_version` | `train` | SHA-256 sobre os nomes ordenados de `FEATURE_COLUMNS`. Muda quando uma feature é acrescentada, removida, renomeada ou reordenada |
| `metrics` (JSONB) | `evaluate` | o relatório completo da avaliação |

`metrics` é escrito **só** pelo `evaluate`, nunca pelo treino: a métrica só
passa a existir depois de uma avaliação sobre o corte `EVAL_DEMO`. Um modelo
recém-treinado tem `metrics = NULL`, e isso é honesto.

O JSON gravado carrega, além dos números: `metrics_schema_version`,
`evaluated_at`, `dataset_split`, `evaluation_dataset_version` (o fingerprint do
dataset **da avaliação**), `feature_schema_version`, `feature_columns`, `labels`,
`averaging`, `sample_count`, `missing_facts_count` e o **disclaimer verbatim**.
Métrica sem o dataset a que se refere não é procedência; e o disclaimer viaja
dentro do JSON para que o número nunca seja lido sem a ressalva, seis meses
depois, por quem não rodou o comando. Formato completo e alternativas
descartadas: `docs/decisions/0001-procedencia-do-ml-model-version.md`.

Reavaliar a mesma versão **sobrescreve** `metrics`; não há histórico de
avaliações. `evaluation_dataset_version` dentro do JSON diz sobre qual dataset o
valor guardado vale.

As três colunas de procedência são anuláveis e não houve backfill: uma linha
gravada antes delas existirem não tem como saber qual dataset a treinou, e
escrever ali o valor de hoje seria procedência fabricada. `NULL` significa "não
registrado".

### Guarda de esquema de features

`require_matching_feature_schema()` (`backend/app/ml/feature_aggregation.py`)
compara o `feature_schema_version` gravado na versão de modelo com o do código
em execução, antes do `joblib.load`. Divergente: recusa com erro explícito e
código de saída não-zero. Nulo (linha legada): prossegue — desconhecido não é
divergente.

Isso cobre o caso que nenhuma guarda de tempo de import alcança: o artefato já
está em disco, ajustado sob a ordem antiga de colunas, e `joblib.load` não sabe
que as colunas andaram. Pontuar assim produziria números plausíveis para
features trocadas.

A guarda vale igualmente para a seleção explícita: pedir uma versão pelo nome
diz *qual* artefato usar, nunca *apesar de quê*.

## 7. Como reproduzir

```bash
cd backend

# 1. gerar o dataset sintético (determinístico pela seed)
uv run python -m app.synthetic.generate --seed 42

# 2. treinar sobre o corte TRAIN
uv run python -m app.ml.train
#    imprime version, artifact_path, training_dataset_version,
#    feature_schema_version

# 3. avaliar sobre o corte EVAL_DEMO
uv run python -m app.ml.evaluate
#    a versão mais recente; o relatório vai para o stdout e para `metrics`

# 3'. reavaliar uma versão específica (a `version` impressa no passo 2)
uv run python -m app.ml.evaluate --model-version 20261105T143022123456-a1b2c3d4

# 4. (opcional) gerar scores experimentais para o corte EVAL_DEMO
uv run python -m app.ml.predict [--model-version <version>]
```

Sem `--model-version`, os dois últimos comandos usam a versão mais recente por
`trained_at` — o comportamento que sempre existiu. Uma `version` inexistente
falha com mensagem no stderr e saída não-zero, sem escrever nada.

Nenhum desses comandos faz parte do processo web: `app/ml/` não tem rota, não
está em `composition.py` e não é chamado por scheduler nenhum.

Consultar o que ficou registrado:

```sql
SELECT version, trained_at, training_dataset_version, feature_schema_version,
       metrics->>'f1' AS f1_macro, metrics->>'sample_count' AS n
FROM ml_model_version
ORDER BY trained_at DESC;
```

## 8. Sobre o score de `predict`

`python -m app.ml.predict` grava um `MLPrediction` por estudante do corte
`EVAL_DEMO`, com `score = 1 - P(STABLE)` segundo o `predict_proba` do pipeline.

Esse valor é **dado experimental de pesquisa**. Ele não é exposto por nenhum
endpoint nem por nenhuma tela (verificado: `MLPrediction` não aparece em
`backend/app/presentation/` nem em `frontend/src/`), e não deve ser. O
`AGENTS.md` §"Score de modelo" é explícito: `0.82` não é "82% de chance de
evasão". No produto, o que aparece são mudanças de trajetória e evidências —
computadas por outro caminho, que não passa pelo modelo.

O mesmo vale para `metrics`: resultado de modelo não vira afirmação sobre
estudante.

## 9. Limites — o que estes números NÃO provam

Apresentação exigida pelo `AGENTS.md` §"Avaliação de ML": o resultado é
**desempenho sobre o dataset sintético utilizado**, nunca "precisão do sistema
em prever evasão escolar no mundo real".

Em ordem de importância:

1. **A tarefa é parcialmente circular.** O rótulo que o modelo tenta recuperar
   foi escrito no dataset pelo próprio gerador, e as features são agregados dos
   fatos que o mesmo gerador produziu segundo aquela regra. Um resultado alto
   diz que o pipeline recupera uma regra conhecida que está lá por construção —
   não que o fenômeno exista assim na realidade. Um resultado baixo seria mais
   informativo que um alto: indicaria que o pipeline não enxerga nem o padrão
   que foi deliberadamente posto ali.

2. **Dados sintéticos, ~200 estudantes fictícios, um ano letivo.** Nenhum dado
   real, por proibição explícita do `AGENTS.md` §Privacidade. Com os padrões do
   gerador (200 estudantes, `train_ratio = 0.7`), o recorte de avaliação tem
   ordem de 60 estudantes — e, pelas proporções da §1, cada classe minoritária
   chega à avaliação com **menos de dez exemplos**. A métrica macro sobre elas
   tem variância alta: uma única predição trocada move o F1 daquela classe em
   mais de dez pontos percentuais. Não leia esses números com precisão que eles
   não têm.

3. **Uma única partição, uma única execução.** Não há validação cruzada, não há
   repetição com seeds diferentes, não há intervalo de confiança. O número é a
   medida de um split; não se sabe quanto ele varia entre splits.

4. **Nenhuma comparação entre modelos foi feita** — divergência com o
   `AGENTS.md` §Modelos, que pede começar simples (`LogisticRegression`,
   `RandomForestClassifier`) e **comparar** antes de adicionar modelos
   complexos. O `build_pipeline()` carrega um `RandomForestClassifier` desde a
   primeira versão, e nenhum baseline foi medido contra ele. Não há, portanto,
   evidência registrada de que a floresta seja a escolha certa aqui, nem
   sequer de que ela supere um classificador trivial. Fechar isso é escopo
   próprio: exige medir pelo menos uma `LogisticRegression` sob o mesmo split e
   registrar a comparação.

5. **As features são instantâneas, não temporais** — divergência com o
   `AGENTS.md` §Features, que prefere `attendance_trend`, `grade_delta`,
   `missing_assignment_delta`, `consecutive_absences` e classifica
   `attendance_current`/`grade_current` como "menos interessantes
   isoladamente". As quatro features atuais são agregados do ano inteiro, sem
   nenhuma noção de evolução. Isso é relevante justamente porque os perfis
   sintéticos são definidos por **queda ao longo do tempo**: o modelo está
   tentando reconhecer um fenômeno temporal a partir de médias que achatam o
   tempo. É a limitação metodológica mais provável por trás de qualquer
   desempenho fraco nas classes de deterioração.

6. **Sem ajuste de hiperparâmetros.** `n_estimators=100`, demais valores nos
   padrões do Scikit-Learn. Não houve busca, e portanto também não houve o
   risco associado — mas o número também não é o melhor que este modelo daria.

7. **Sem histórico de avaliações.** Reavaliar sobrescreve `metrics`; não é
   possível, hoje, comparar duas avaliações da mesma versão ao longo do tempo
   direto no banco.

8. **Desequilíbrio não tratado no treino.** Não há `class_weight`, nem
   reamostragem. A métrica macro expõe o efeito disso; o pipeline não o
   compensa.

Nada aqui autoriza afirmar que o sistema prevê evasão escolar, que um estudante
tem risco, ou que o acompanhamento pedagógico deva seguir a saída do modelo. O
produto trata de evidência, trajetória e decisão humana; o modelo é um
experimento mantido ao lado, com procedência registrada e limites declarados.

## Referências no repositório

- `AGENTS.md` — §Machine Learning, §Avaliação de ML, §Score de modelo,
  §Versionamento de modelo, §Features, §Atalhos proibidos
- `docs/decisions/0001-procedencia-do-ml-model-version.md`
- `docs/decisions/0002-ordem-de-features-derivada-de-feature-columns.md`
- `docs/spec-5-1-pipeline-pre-processamento-e-treino-do-modelo-offline.md`
- `docs/spec-5-2-geracao-de-score-experimental-como-dado-de-pesquisa.md`
- `docs/spec-5-3-avaliacao-do-modelo-com-split-de-dataset-sem-vazamento.md`
- `docs/spec-ml-model-provenance.md`
- `docs/spec-ml-avaliacao-documentada.md`
- `backend/tests/test_ml_train.py`, `test_ml_evaluate.py`, `test_ml_predict.py`,
  `test_ml_model_provenance.py`
