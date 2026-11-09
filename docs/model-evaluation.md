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

Por que um `RandomForestClassifier`, e não outro modelo? A §6 responde com
medição. Até ela existir, não havia resposta registrada.

## 6. Comparação de modelos

O `AGENTS.md` §Modelos manda começar simples e **comparar** antes de adotar
algo mais complexo. Por muito tempo este repositório não tinha essa
comparação: o `build_pipeline()` carregava uma floresta aleatória desde a
primeira versão e nenhum baseline fora medido contra ela.

A comparação é **código permanente**, não uma medição de uma tarde:

```bash
uv run python -m app.ml.compare
```

A escolha de transformar em comando foi deliberada. Um número medido uma vez e
colado num documento não é verificável por quem lê — numa defesa, "por que
floresta aleatória?" se responde rodando o comando, e quem duvidar do número
pode reproduzi-lo. O comando ajusta cada candidato sobre o corte `TRAIN`,
avalia sobre o corte `EVAL_DEMO`, e **não escreve nada**: nenhuma linha em
`ml_model_version`, nenhum `.joblib`, nenhuma predição. Um candidato de
comparação nunca vai pontuar ninguém, e registrá-lo na tabela de procedência a
encheria de modelos descartáveis.

As métricas são calculadas pela mesma função que `evaluate` usa
(`compute_report`, extraída de `run_evaluation` para este fim). Duas
implementações de F1 macro que divergissem tornariam "o candidato X venceu"
infalsificável — a diferença poderia ser sempre a métrica, nunca o modelo.

### Os candidatos, e por que cada um

| candidato | papel | pré-processamento |
|---|---|---|
| `dummy_most_frequent` | o piso degenerado: responde sempre `STABLE` | imputação |
| `dummy_stratified` | o piso honesto: sorteia nas proporções do treino | imputação |
| `logistic_regression` | o modelo simples que o `AGENTS.md` nomeia | imputação + padronização |
| `random_forest` | o que está em produção (`build_pipeline()` em pessoa) | imputação |

Duas escolhas precisam de argumento.

**Por que duas `strategy` de `DummyClassifier`, e não uma.** Elas respondem
perguntas diferentes. `most_frequent` prediz sempre a classe majoritária e
existe para tornar *medido* o argumento que a §4 fazia no papel: ele marca
Accuracy de 0,7167 (43 dos 60 estudantes do corte são `STABLE`) sem reconhecer
padrão nenhum, enquanto seu F1 macro é 0,2087. É a demonstração de por que o
`AGENTS.md` veda escolher modelo por Accuracy. Mas justamente por ser
degenerado — três das quatro classes recebem F1 zero por construção — ele é um
nulo fraco demais para uma métrica macro: qualquer modelo o supera sem provar
nada. `stratified` sorteia respeitando as proporções observadas no treino, ou
seja, acerta cada classe na taxa do acaso informado. É contra esse piso que
"o modelo aprendeu alguma coisa" precisa ser demonstrado. `prior` não entra:
em predição dura ele é idêntico a `most_frequent` (difere só em
`predict_proba`), e uma linha repetindo os números de outra é ruído.

**Por que a regressão logística recebe `StandardScaler` e a floresta não.**
Árvores são invariantes a escala monotônica; regressão logística não é, e as
features convivem em escalas incompatíveis (taxas em `[0,1]`, notas em
`[0,10]`, contagens sem teto). Sem padronizar, a regularização L2 penaliza
desproporcionalmente os coeficientes das colunas de menor amplitude. Comparar
a floresta contra uma regressão logística não-escalonada seria pesar um lado
da balança e chamar o resultado de evidência. Cada candidato é, portanto, um
`Pipeline` inteiro — compara-se o que iria para produção, pré-processamento
incluído.

Nenhum modelo de gradient boosting aparece. O `AGENTS.md` §"Atalhos proibidos"
veda XGBoost/LightGBM nominalmente, e a regra é anterior à medição: não é
"medimos e não precisou", é "não é para adicionar". Há um teste que falha se
alguém acrescentar um.

### O resultado

Dataset gerado com `--seed 42`, 200 estudantes, 60 no corte `EVAL_DEMO`,
nenhum fato ausente. Médias macro sobre os quatro rótulos:

| candidato | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| `dummy_most_frequent` | 0,1792 | 0,2500 | 0,2087 | 0,5000 | 0,2500 |
| `dummy_stratified` | 0,2022 | 0,1940 | 0,1970 | 0,4696 | 0,2489 |
| `logistic_regression` | **0,9611** | 0,8250 | **0,8685** | **0,9974** | **0,9717** |
| `random_forest` | 0,8231 | **0,8642** | 0,8288 | 0,9870 | 0,8857 |

**A floresta não ganhou.** A regressão logística — o modelo simples, o que o
`AGENTS.md` mandava tentar primeiro — supera o `RandomForestClassifier` em
Precision macro (0,9611 contra 0,8231), em F1 macro (0,8685 contra 0,8288), em
ROC-AUC e em PR-AUC. A floresta só vence em Recall macro (0,8642 contra
0,8250).

A matriz de confusão mostra de onde vem a diferença:

```text
  logistic_regression            STABLE  F_ATT  F_GRA  COMB
    STABLE                           43      0      0     0
    FALLING_ATTENDANCE                0      8      0     0
    FALLING_GRADES                    2      0      2     0
    COMBINED_DETERIORATION            0      1      0     4

  random_forest                  STABLE  F_ATT  F_GRA  COMB
    STABLE                           39      0      4     0
    FALLING_ATTENDANCE                0      8      0     0
    FALLING_GRADES                    1      0      3     0
    COMBINED_DETERIORATION            0      1      0     4
```

Os dois erram o mesmo `COMBINED_DETERIORATION` (confundido com
`FALLING_ATTENDANCE`) e acertam `FALLING_ATTENDANCE` inteiro. A diferença está
em `STABLE`: a floresta marca **quatro** estudantes estáveis como
`FALLING_GRADES`, a regressão logística nenhum. Em troca, a regressão perde um
`FALLING_GRADES` a mais para `STABLE`. É um troco entre falso positivo e falso
negativo — e num produto cuja saída é "trazer o caso para revisão pedagógica",
chamar quatro estudantes estáveis de "notas em queda" é o erro mais caro dos
dois.

A leitura mais provável do porquê: as quatro features são agregados anuais
aproximadamente monotônicos em relação ao rótulo, e fronteiras lineares bastam
para separá-los. A floresta, com 100 árvores sobre ~140 linhas de treino,
fragmenta um espaço que não precisava ser fragmentado.

**O que isso não autoriza a dizer.** Que a regressão logística é "o modelo
certo". Isto é uma única partição, uma única seed, ~60 estudantes de avaliação
com menos de dez exemplos por classe minoritária (§10.2, §10.3). Trocar o
`build_pipeline()` com base nesta medição exigiria, no mínimo, verificar se a
vantagem sobrevive a outras seeds — e é decisão humana registrada, não efeito
de rodar o comando. O que esta seção fecha é a ausência de evidência: a
pergunta "por que floresta?" passou a ter dado em vez de silêncio, e o dado
não favorece a resposta que o código vinha dando.

**O que ela confirma.** Que os dois pisos triviais ficam em F1 macro ~0,20
enquanto os dois modelos reais passam de 0,82. O pipeline *reconhece* o padrão
simulado — ele não está apenas explorando o desbalanceamento. Esse era o
objetivo declarado na §1, e ele é atingido pelos dois modelos, não só por um.

## 7. Procedência: o que fica registrado

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

## 8. Como reproduzir

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

# 5. comparar os modelos candidatos sob o mesmo corte (§6)
uv run python -m app.ml.compare
#    não escreve nada: nem MLModelVersion, nem artefato, nem predição
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

## 9. Sobre o score de `predict`

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

## 10. Limites — o que estes números NÃO provam

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

4. **A comparação entre modelos existe, mas sobre uma única partição.** A §6
   mede quatro candidatos sob o mesmo corte e registra o resultado: a
   `LogisticRegression` supera o `RandomForestClassifier` em F1 macro, e o
   `build_pipeline()` continua carregando a floresta. Essa diferença entre o
   que foi medido e o que o código faz é consciente e está documentada — uma
   troca de classificador com base em um split, uma seed e ~60 estudantes de
   avaliação seria tão pouco fundamentada quanto a escolha original. O que não
   existe mais é a ausência de evidência; o que ainda não existe é evidência
   suficiente para decidir.

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
- `docs/decisions/0003-comparacao-de-modelos-como-comando-reproduzivel.md`
- `docs/spec-comparacao-de-modelos-baseline.md`
- `docs/spec-5-1-pipeline-pre-processamento-e-treino-do-modelo-offline.md`
- `docs/spec-5-2-geracao-de-score-experimental-como-dado-de-pesquisa.md`
- `docs/spec-5-3-avaliacao-do-modelo-com-split-de-dataset-sem-vazamento.md`
- `docs/spec-ml-model-provenance.md`
- `docs/spec-ml-avaliacao-documentada.md`
- `backend/tests/test_ml_train.py`, `test_ml_evaluate.py`, `test_ml_predict.py`,
  `test_ml_model_provenance.py`
