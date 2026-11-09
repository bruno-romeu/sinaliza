---
id: SPEC-features-temporais-de-trajetoria
companions: []
sources:
  - docs/model-evaluation.md
  - docs/decisions/0002-ordem-de-features-derivada-de-feature-columns.md
  - docs/spec-comparacao-de-modelos-baseline.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Features temporais: dar ao modelo a inclinacao que define os perfis

## Why

As quatro entradas de `FEATURE_COLUMNS` — `attendance_rate`, `grade_average`,
`assignment_completion_rate`, `observation_count` — sao agregados do ano
inteiro. Nenhuma delas tem nocao de evolucao. O `AGENTS.md` §Features prefere
nominalmente `attendance_trend`, `grade_delta`, `missing_assignment_delta` e
`consecutive_absences`, e classifica os agregados instantaneos como "menos
interessantes isoladamente".

O desalinhamento com o documento e o sintoma; o problema real esta no gerador.
Lendo `backend/app/synthetic/profiles.py`, **todo perfil nao-`STABLE` e
definido por uma rampa no tempo**:

- `attendance_is_present` interpola a probabilidade diaria de presenca de
  `DAILY_ATTENDANCE_RATE_BASELINE` ate `DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR`
  pelo indice do dia letivo (`FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`);
- `grade_value` desloca o quantil habitual do estudante por
  `quantile * (1 - progress)` ao longo dos periodos, de modo que no ultimo
  periodo o quantil tende a 0 (`FALLING_GRADES`, `COMBINED_DETERIORATION`);
- `assignment_submission_status` interpola a taxa de nao-entrega de
  `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE` ate
  `..._AT_RISK_CEILING` pelo indice do periodo (**so**
  `COMBINED_DETERIORATION`).

Uma media anual sobre uma rampa linear devolve aproximadamente o ponto medio da
rampa. Ela preserva *alguma* informacao — um estudante em queda termina com
media menor que um estavel — mas achata precisamente a grandeza que **define** o
perfil, que e a inclinacao. O modelo esta sendo pedido para reconhecer um
fenomeno temporal a partir de numeros que apagaram o tempo.

Isso nao e hipotese sobre o mundo: e leitura do gerador. O sinal temporal
existe no dataset por construcao e hoje nao chega ao modelo. `model-evaluation.md`
§9.5 ja registra isso como "a limitacao metodologica mais provavel por tras de
qualquer desempenho fraco nas classes de deterioracao".

Ha ainda um caso que as features atuais nao conseguem separar nem em
principio: `COMBINED_DETERIORATION` difere de `FALLING_ATTENDANCE` +
`FALLING_GRADES` justamente pela rampa de nao-entrega, e
`assignment_completion_rate` medio dilui essa rampa sobre o ano inteiro.

## Capabilities

**CAP-1 — Quatro features temporais calculadas a partir dos fatos datados.**
*Intent:* `FEATURE_COLUMNS` passa a incluir `attendance_trend`,
`consecutive_absences`, `grade_delta` e `missing_assignment_delta`, calculadas
sobre as sequencias cronologicas que as tabelas de fato ja guardam.
*Success:* `fetch_feature_rows()` devolve as oito features; os tres row types
(`TrainingRow`, `ScoringRow`, `EvaluationRow`) e o `FeatureRow` declaram campo
para cada uma, e `require_feature_fields` passa para os quatro.

**CAP-2 — Calculo temporal puro e testavel sem banco.**
*Intent:* a logica de "segunda metade menos primeira metade", "maior corrida de
faltas" e "ultimo periodo menos primeiro periodo" vive em funcoes puras sobre
sequencias, separadas do SQL que as alimenta.
*Success:* existe um modulo de funcoes puras, sem import de SQLAlchemy, com
testes unitarios que cobrem historico vazio, historico de um ponto so e
historico normal, sem tocar no banco.

**CAP-3 — Comparacao de features medida, nao suposta.**
*Intent:* o conjunto novo e medido contra o antigo no mesmo corte
`TRAIN`/`EVAL_DEMO`, e o resultado honesto vai para `docs/model-evaluation.md`
— inclusive se as features temporais nao melhorarem.
*Success:* `docs/model-evaluation.md` registra as metricas dos dois conjuntos
de features para os mesmos candidatos de modelo, e §9.5 deixa de descrever as
features como puramente instantaneas.

**CAP-4 — A guarda de esquema de features se comporta como projetada.**
*Intent:* artefatos `.joblib` treinados sob as quatro features antigas passam a
ser recusados, com erro claro e acionavel, em vez de pontuados com colunas
trocadas.
*Success:* `require_matching_feature_schema()` recusa um
`MLModelVersion` com `feature_schema_version` antigo; a mensagem nomeia os dois
esquemas e manda retreinar; `python -m app.ml.evaluate` sai com codigo
nao-zero sem escrever `metrics`.

## Constraints

- **`FEATURE_SCHEMA_VERSION` muda sozinho.** E derivado de `FEATURE_COLUMNS`
  (decisao `0002`). Nada de constante editada a mao; nada de "congelar" o valor
  antigo para nao quebrar artefato.
- **A guarda nao e contornada.** Artefato antigo recusado e o comportamento
  correto. Nao ha fallback, nao ha flag `--skip-schema-check`, nao ha backfill
  de `feature_schema_version` em linhas antigas.
- **As quatro features novas sao derivadas de fatos que ja existem.** Presenca
  tem `date`; nota tem `date` e `period_id` (com `order_index`); entrega tem
  `date`. Nenhuma tabela nova, nenhuma migration, nenhum campo novo no gerador.
- **Nenhuma feature sensivel.** As oito features sao contagens e taxas de
  fatos escolares. Nada demografico, nada familiar, nada de saude —
  `AGENTS.md` §Features e §Privacidade.
- **Ausencia continua sendo `None` para taxas/deltas e `0` para contagens.**
  `attendance_trend`, `grade_delta` e `missing_assignment_delta` sao `None`
  quando nao ha pontos suficientes para calcular uma diferenca;
  `consecutive_absences` e `0` sem registros, pela mesma logica que ja rege
  `observation_count` (nenhuma falta e um valor real, nao um valor ausente).
  O `SimpleImputer` do pipeline continua preenchendo os `None`.
- **`missing_facts_count` continua medindo o que mede.** Ele conta linhas com
  fato ausente; a definicao atual olha as tres taxas originais. Ampliar ou nao
  o criterio e decisao a registrar, nao efeito colateral silencioso.
- **Nada exposto por API ou frontend.** As features sao internas ao
  `app/ml/`; nenhuma delas vira numero em tela.
- **Nao gerar ranking.** Feature temporal nova nao autoriza ordenar
  estudantes por nada.

## Non-goals

- **Nao substituir a deteccao de mudanca do produto.** `app/application/
  trajectory/` e `TrajectoryChange` seguem seu proprio caminho, baseado em
  evidencia e janela rolante. Estas features sao entrada de um modelo
  experimental e nao alimentam nem sao alimentadas por aquele fluxo.
- **Nao remover as quatro features antigas.** O conjunto novo e o antigo mais
  quatro; remover o nivel absoluto junto com a adicao da inclinacao
  impossibilitaria atribuir a diferenca medida a uma das duas mudancas.
- **Nao introduzir janela rolante parametrizavel** (ex. "ultimas 8 semanas").
  A particao em metades e por periodo e derivada do proprio gerador, que
  interpola sobre o ano inteiro; uma janela fixa em semanas seria um parametro
  a calibrar sem referencia.
- **Nao tratar desbalanceamento, nao ajustar hiperparametros, nao fazer
  validacao cruzada.** §9.3, §9.6 e §9.8 do `model-evaluation.md` continuam
  abertos.
- **Nao mexer no gerador sintetico.** Nenhuma mudanca em `app/synthetic/`.

## Success signal

Com o banco gerado por `--seed 42`:

```bash
uv run python -m app.ml.evaluate     # recusa o artefato antigo, saida != 0
uv run python -m app.ml.train        # novo feature_schema_version
uv run python -m app.ml.evaluate     # metricas sob as oito features
uv run python -m app.ml.compare      # os candidatos sob o conjunto novo
```

e `docs/model-evaluation.md` contendo as duas colunas — conjunto antigo e
conjunto novo — para os mesmos candidatos, com a leitura do que a diferenca
significa. Especificamente: se o F1 macro de `COMBINED_DETERIORATION` subir,
isso confirma que `missing_assignment_delta` carrega o eixo que separava esse
perfil dos de um eixo so. Se nao subir, isso tambem e resultado e vai para o
documento com essa clareza.

## Assumptions

1. **`attendance_trend` como diferenca entre metades, nao como coeficiente de
   regressao.** A rampa do gerador e linear, entao a diferenca entre a taxa de
   presenca da segunda metade e a da primeira e proporcional a inclinacao e tem
   a mesma capacidade de separacao, com uma implementacao que um leitor de TCC
   entende sem derivar minimos quadrados. Um `polyfit` de grau 1 daria
   essencialmente a mesma ordenacao com mais maquinario.
2. **`consecutive_absences` acrescenta algo a `attendance_trend`.** E
   correlacionado, nao redundante: a maior corrida de faltas consecutivas
   depende de como as faltas se agrupam, nao so de quantas existem. Com a
   probabilidade de presenca caindo ate o piso, as corridas no fim do ano se
   alongam de forma nao-linear. E tambem a feature que o `AGENTS.md` nomeia
   literalmente. Se a medicao mostrar que ela nao contribui, isso vai para o
   documento.
3. **`grade_delta` usa periodos, nao datas.** A rampa de nota do gerador e
   indexada por periodo (`_progress(period_index, total_periods)`), entao
   comparar o primeiro periodo com notas contra o ultimo periodo com notas e a
   leitura que corresponde a regra geradora. Ordena-se por
   `AcademicPeriod.order_index`, nunca por `date` do lancamento.
4. **`missing_assignment_delta` usa metades por data de entrega.** A rampa de
   nao-entrega tambem e indexada por periodo, mas a submissao carrega `date`
   diretamente e a atividade carrega `period_id`; usar as metades da sequencia
   cronologica de submissoes do estudante evita um join a mais e, com entregas
   distribuidas uniformemente pelos periodos, aproxima a mesma particao.
5. **Historico curto e caso real no dataset, ainda que raro.** Um estudante com
   uma unica nota, ou com notas em um unico periodo, nao tem delta definido.
   `None` + imputacao e o tratamento consistente com o que ja existe, e e
   preferivel a inventar `0.0`, que afirmaria "nao houve mudanca" quando o que
   houve foi ausencia de dado.

## Open questions

1. **`missing_facts_count` deve passar a contar os deltas ausentes?** Contar
   tornaria o numero mais fiel a "linhas com algum valor imputado"; nao contar
   mantem a serie comparavel com as metricas ja gravadas em `metrics` de
   versoes anteriores. A decisao precisa ser explicita no documento, qualquer
   que seja.
2. **Oito features sobre ~140 linhas de treino e muita feature?** A razao
   linhas/features cai de 35 para 17,5. Para `RandomForestClassifier` isso e
   confortavel; para `LogisticRegression` com quatro classes e menos. A
   comparacao de modelos (spec irma) e o instrumento que torna esse efeito
   visivel em vez de suposto.
