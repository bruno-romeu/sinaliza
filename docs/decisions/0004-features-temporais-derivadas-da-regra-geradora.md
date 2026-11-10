# 0004 — Features temporais derivadas da regra geradora, e o custo de acrescentá-las

- **Data:** 2026-11-09
- **Status:** aceita
- **Fecha:** `docs/model-evaluation.md` §Limites item 5 (features instantâneas
  num problema temporal)
- **Spec:** `docs/spec-features-temporais-de-trajetoria.md`

## Contexto

`FEATURE_COLUMNS` tinha quatro entradas, todas agregados do ano inteiro:
`attendance_rate`, `grade_average`, `assignment_completion_rate`,
`observation_count`. O `AGENTS.md` §Features prefere nominalmente
`attendance_trend`, `grade_delta`, `missing_assignment_delta` e
`consecutive_absences`, e chama os agregados instantâneos de "menos
interessantes isoladamente".

O desalinhamento com o documento era o sintoma. O problema estava no gerador:
**todo perfil sintético não-`STABLE` é definido por uma rampa no tempo**
(`app/synthetic/profiles.py`). A média anual de uma rampa linear devolve
aproximadamente o ponto médio dela — preserva o nível, apaga a inclinação, que
é a grandeza que define o perfil.

## Decisão

**As quatro features temporais são escolhidas a partir da leitura de
`profiles.py`, uma por eixo que o gerador move — não de uma lista genérica de
boas práticas.**

| feature | eixo do gerador que ela mede |
|---|---|
| `attendance_trend` | `attendance_is_present` interpola a probabilidade diária de presença até um piso pelo índice do dia letivo |
| `consecutive_absences` | a mesma rampa, lida pelo agrupamento das faltas em vez de pela sua contagem |
| `grade_delta` | `grade_value` multiplica o quantil por `(1 - progress)` ao longo dos períodos |
| `missing_assignment_delta` | `assignment_submission_status` interpola a não-entrega até um teto — e **só** para `COMBINED_DETERIORATION` |

A última é a que importa mais estruturalmente:
`COMBINED_DETERIORATION` difere de `FALLING_ATTENDANCE` e `FALLING_GRADES`
exatamente por esse eixo, e `assignment_completion_rate` dilui a rampa sobre o
ano inteiro. Sem ela, aquele perfil não era separável nem em princípio.

Decisões subordinadas:

**1. Diferença entre metades, não coeficiente de regressão linear.** A rampa do
gerador é linear, então a diferença entre metades é proporcional à inclinação e
ordena os perfis igual. Um `polyfit` de grau 1 daria essencialmente a mesma
separação com mais maquinário entre o dado e o leitor. Com número ímpar de
pontos, o ponto do meio cai na segunda metade — convenção arbitrária, declarada
e testada para que não mude sem alguém perceber.

**2. `grade_delta` por `AcademicPeriod.order_index`, nunca pela data do
lançamento.** A rampa de nota é indexada por período; uma nota lançada com
atraso move a data sem mover o período a que pertence.

**3. As quatro features antigas ficaram.** O conjunto novo é o antigo *mais*
quatro. Removê-las junto impossibilitaria atribuir a diferença medida a uma das
duas mudanças — e separar isso era o ponto de medir.

**4. Delta sem pontos suficientes é `None`, nunca `0.0`.** `0.0` afirmaria "não
houve mudança"; o que houve foi ausência de dado. `consecutive_absences` é `0`
sem registros, porque é contagem — mesma convenção que já regia
`observation_count`.

**5. `missing_facts_count` não foi ampliado.** Ele continua olhando as três
taxas originais. Ampliá-lo tornaria o número mais fiel a "linhas com algum valor
imputado", mas quebraria a comparabilidade com as métricas já gravadas em
`metrics` sob a definição antiga. Um número de procedência que muda de
significado sem mudar de nome é pior que um de escopo estreito e declarado.

## Consequências

- **`FEATURE_SCHEMA_VERSION` mudou sozinho**, de `sha256:43f28fee098d` para
  `sha256:4276794409d7`. É derivado de `FEATURE_COLUMNS` (decisão 0002), como
  projetado.
- **Todo artefato `.joblib` treinado antes disto passou a ser recusado** por
  `require_matching_feature_schema()`, com erro nomeando os dois esquemas e
  mandando retreinar, e saída não-zero. Isso é a guarda funcionando, não um
  bug: o artefato antigo está em disco ajustado sob quatro colunas, e
  `joblib.load` não sabe que agora são oito. Não há flag para contornar, e não
  houve backfill.
- **O desempenho subiu muito**: F1 macro da floresta de 0,8288 para 0,9824, o
  da regressão logística de 0,8685 para 1,0000 (`model-evaluation.md` §6). Isso
  confirma que o desempenho anterior era limitação de representação, não do
  pipeline.
- **E isso agrava a circularidade declarada em §10.1.** As features foram
  derivadas da regra geradora e medem a recuperação daquela regra. Um F1 de
  1,0000 sobre dados sintéticos é um resultado sobre o pipeline, nunca sobre
  estudantes, e o documento diz isso junto do número em vez de depois dele.
- **Um defeito latente do pipeline ficou alcançável e foi corrigido.**
  `SimpleImputer(strategy="mean")` descarta silenciosamente uma coluna sem
  nenhum valor observado no ajuste, encolhendo a largura do pipeline abaixo do
  que `FEATURE_COLUMNS` declara. A guarda de esquema não alcança esse caso: o
  esquema confere, foi o ajuste que encolheu. Com os agregados antigos era
  quase impossível (qualquer fato preenchia a coluna); `grade_delta` exige dois
  períodos com nota, e conjuntos pequenos caem nisso com facilidade.
  `keep_empty_features=True` em `pipeline.py` e `candidates.py`, com teste de
  regressão.
- A razão linhas/features no treino caiu de ~35 para ~17,5. Não houve efeito
  visível nesta medição, mas a observação fica registrada: a comparação de
  modelos (`app/ml/compare.py`) é o instrumento que tornaria esse efeito
  visível se ele aparecer.
