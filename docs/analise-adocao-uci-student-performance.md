# Análise: adoção do Student Performance Dataset (UCI) no Sinaliza

Documento de decisão. Avalia **se e como** o *Student Performance Dataset*
(Cortez & Silva, 2008; UCI ML Repository, id 320) deveria entrar no projeto, e
compara as rotas possíveis contra o problema que motivou a pergunta: a
**circularidade do experimento de ML**, registrada em
`docs/model-evaluation.md` §10.1 e §10.5.

Escrito para quem ainda vai decidir. A recomendação está na §10; o argumento
contra ela, na §11.

> **Conclusão antecipada.** Nenhuma das três rotas propostas (A, B, C) reduz a
> circularidade. A rota A custa uma épica e entrega um produto que faz menos;
> a rota B importa dado sensível e troca uma regra geradora conhecida por
> outra pior; a rota C, **medida**, rende no máximo um parâmetro, e o rebaixa
> em relevância em vez de fortalecê-lo. O que ataca a circularidade é uma
> quarta rota, que não usa dado real nenhum: §8.

---

## 1. Procedência desta análise

A distinção abaixo vale para cada número deste documento.

### 1.1. Inspeção direta (dados baixados e medidos aqui)

O dataset foi baixado de
`https://archive.ics.uci.edu/static/public/320/student+performance.zip`
e inspecionado em pasta temporária isolada, fora do repositório. **Nenhuma
linha, nem nenhuma fatia, foi versionada** — `AGENTS.md` §Privacidade, e a
proibição vale independentemente da decisão que este documento informa.

Verificado diretamente:

- arquivos, contagens e colunas de `student-mat.csv` e `student-por.csv`;
- distribuição de `absences`, `G1`, `G2`, `G3`;
- o artefato `G3 == 0 ⇒ absences == 0` (§3.3);
- o merge dos dois arquivos pela chave do `student-merge.R` oficial, e a
  (dis)concordância entre disciplinas para o mesmo estudante (§3.4);
- correlações `absences×G3`, `G1×G3`, `G2×G3`;
- a distribuição de `G3` reescalada para 0–10 contra as faixas de
  `GRADE_DISTRIBUTION`;
- o dicionário de atributos oficial (`student.txt`, distribuído no zip).

Também por inspeção direta, no repositório: `backend/app/synthetic/` inteiro,
`backend/app/ml/` inteiro, `backend/tests/` (contagem e conteúdo dos testes
citados), `docs/model-evaluation.md`, `docs/data-model.md`, `AGENTS.md`.

### 1.2. Segunda mão (não verificado aqui)

- **Licença.** O UCI publica o conjunto sob CC BY 4.0 e o artigo original
  (Cortez & Silva, 2008) é a citação exigida. Não conferi a página de licença;
  se alguma rota for adotada, conferir antes.
- **Os resultados publicados** de Cortez & Silva (classificação binária em
  `G3 ≥ 10`, acurácias altas) são conhecidos de literatura, não medidos aqui.
  O que **foi** medido aqui e é relevante a eles está na §3.5.
- **O OULAD** (Open University Learning Analytics Dataset), citado na §8.4
  como alternativa estrutural, **não foi baixado**: o endpoint histórico de
  download responde `301` para uma landing page sem link direto. Tudo o que
  este documento diz sobre a estrutura do OULAD é de segunda mão e precisa de
  verificação antes de virar decisão.
- A proposta aprovada pela banca não foi lida aqui; o texto citado na issue #65
  (*"todos os dados utilizados são sintéticos"*) é tomado como verdadeiro.

---

## 2. O problema que a decisão precisa resolver

O experimento de ML do Sinaliza é circular, e isso já está escrito
(`docs/model-evaluation.md` §10.1, §10.5):

> as quatro features temporais foram escolhidas lendo
> `app/synthetic/profiles.py` — uma rampa de presença, uma rampa de quantil de
> nota por período, uma rampa de não-entrega — e cada uma mede exatamente o
> eixo que o gerador move.

O F1 macro de 1,0000 da regressão logística não é mérito: é a medida de quão
bem features derivadas de uma regra recuperam aquela regra. Confirmei lendo
`profiles.py` e `temporal_features.py` que a descrição é literal —
`half_split_delta` mede a diferença entre metades porque "a rampa do gerador é
linear" (docstring de `temporal_features.py`), ou seja, a implementação da
feature cita a implementação do gerador como justificativa.

**O critério de avaliação deste documento, então, é um só:** a rota produz uma
situação em que o modelo é medido contra algo que o autor das features não
escreveu?

Note o que esse critério implica. "Importar dado real" e "reduzir a
circularidade" **não são a mesma coisa**. Uma rota pode fazer a primeira sem
fazer a segunda — e, como a §6 mostra, a rota B faz exatamente isso. E uma
rota pode fazer a segunda sem dado real nenhum: §8.

---

## 3. O dataset, medido

### 3.1. Forma

| | `student-mat.csv` | `student-por.csv` |
|---|---|---|
| linhas | 395 | 649 |
| colunas | 33 | 33 |
| estudantes distintos emparelhados entre os dois arquivos | colspan → | 366 (382 pares pelo merge oficial, com duplicação de chave) |

Uma linha por estudante por disciplina. **Corte transversal, sem data em
lugar nenhum do arquivo.** Não existe coluna de data, de aula, de período
calendário, de atividade, nem de observação.

A população real combinada é de ordem de **662 estudantes distintos**, não
395 + 649 = 1.044: os dois arquivos descrevem majoritariamente as mesmas
pessoas em duas disciplinas (§3.4).

### 3.2. As 33 colunas, por natureza

**Sensíveis sob `AGENTS.md` §Privacidade e §Features** (13):
`sex`, `age`, `address` (urbano/rural), `famsize`, `Pstatus` (coabitação dos
pais), `Medu`, `Fedu` (escolaridade de mãe e pai), `Mjob`, `Fjob` (emprego de
mãe e pai), `guardian`, `famrel` (qualidade da relação familiar), `Dalc`,
`Walc` (consumo de álcool em dias úteis e fim de semana), `health` (estado de
saúde autodeclarado).

São **dado de saúde e informação familiar real** sobre adolescentes reais de
duas escolas portuguesas — as duas categorias nomeadas literalmente na lista
do `AGENTS.md` §Privacidade ("nunca commitar"). Distribuições medidas (Mat.):
`health` 1→47, 2→45, 3→91, 4→66, 5→146; `Pstatus` A→41 (pais separados);
`Dalc` 3+→44; `famrel` 1–2→26.

**Comportamentais/contextuais, menos sensíveis mas ainda não-escolares** (12):
`school`, `reason`, `traveltime`, `studytime`, `freetime`, `goout`,
`romantic`, `activities`, `nursery`, `internet`, `higher`, `paid`.

**Escolares** (8): `failures` (reprovações anteriores), `schoolsup`, `famsup`,
`absences`, `G1`, `G2`, `G3`, mais `school`.

Ou seja: **das 33 colunas, 7 são fato escolar.** O valor do dataset na
literatura está justamente nas outras 26. Usá-lo sem elas é jogar fora o que
ele tem de diferente; usá-lo com elas é construir um sistema que infere
trajetória escolar a partir do emprego da mãe e do consumo de álcool do
estudante. A issue #65 está certa nesse ponto, e ele continua de pé depois da
inspeção.

### 3.3. `absences` não é frequência, e o que ela esconde

Medido:

| | Mat. | Port. |
|---|---|---|
| `absences` min / máx | 0 / 75 | 0 / 32 |
| média / mediana | 5,71 / 4 | 3,66 / 2 |
| **exatamente zero** | **115 (29,1%)** | **244 (37,6%)** |
| valores ímpares | 41 (10,4%) | 51 (7,9%) |

Três leituras, todas com consequência:

1. **A unidade não é o dia.** Mais de 90% dos valores são pares. A contagem é
   de aulas (blocos de duas horas) **daquela disciplina**, não de dias letivos
   da escola. O domínio do Sinaliza (`AttendanceRecord` com
   `UNIQUE(student_id, classroom_id, date)`) não tem onde encaixar isso.
2. **Não há denominador.** O arquivo não diz quantas aulas houve. Sem total,
   `absences` **não produz uma taxa de frequência** — e portanto não calibra
   `DAILY_ATTENDANCE_RATE_BASELINE`. Isto refuta diretamente o ganho que a
   issue #65 atribui à rota C (§12, item 2).
3. **Um terço dos estudantes tem zero.** Combinado com o item seguinte, isso
   não é "população assídua": é ausência de registro.

#### O artefato que decide a rota B

Medido, e é o achado mais importante deste documento:

```text
student-mat.csv:  G3 == 0 → n = 38;  absences = {0: 38}      (100%)
                  G2 == 0 → n = 13;  absences = {0: 13}      (100%)
student-por.csv:  G3 == 0 → n = 15;  absences = {0: 15}      (100%)
                  G2 == 0 → n =  7;  absences = {0:  7}      (100%)
```

**Todo estudante com nota final zero tem exatamente zero faltas registradas.**
Nenhuma exceção, nos dois arquivos. Entre os estudantes com `G3 > 0`, zero
faltas aparece em 77/357 (Mat.) e 229/634 (Port.) — ou seja, o zero existe nos
dois grupos, mas no grupo `G3 == 0` ele é **universal**.

A leitura é que `G3 == 0` marca estudante que saiu ou não foi avaliado, e para
quem o registro de faltas simplesmente não foi preenchido. É um artefato de
coleta, não um fenômeno.

A consequência é brutal e mensurável:

```text
corr(absences, G3), todos os estudantes:  +0,034 (Mat.)   −0,091 (Port.)
corr(absences, G3), só G3 > 0:            −0,213 (Mat.)   −0,196 (Port.)
```

O sinal **inverte** quando o artefato entra. `G3 == 0` é a única coluna do
dataset com forma de evasão — e ela está perfeitamente confundida com "zero
faltas". Qualquer alvo derivado dela ensina ao modelo que **ausência de faltas
prediz abandono**, exatamente o inverso do sinal pedagógico, com separação
perfeita e por motivo errado. Em uma defesa, essa é a pergunta que derruba o
capítulo.

### 3.4. O mesmo estudante, duas disciplinas: o construto não é estável

Fiz o merge pela chave do `student-merge.R` oficial (13 atributos
demográficos). Resultado: 382 pares, **366 chaves distintas**. Para esses 366
estudantes, medindo "notas em queda" como `G3 < G1`:

| | |
|---|---|
| cai em Matemática | 142 (**38,8%**) |
| cai em Português | 70 (**19,1%**) |
| cai nas duas | 32 |
| **concordância do rótulo entre as duas disciplinas** | **59,6%** |

As mesmas pessoas, o mesmo ano, a mesma escola: a prevalência de "queda"
**dobra** conforme o arquivo que você abrir, e o rótulo concorda consigo mesmo
em 59,6% — pouco acima dos ~50% do acaso para um rótulo com essa prevalência.

E as faltas do mesmo estudante nos dois arquivos:

```text
|absences_mat − absences_por|:  média 3,86   mediana 2,0   máx 60
                                idênticas em apenas 27,3% dos casos
```

Confirma a §3.3: `absences` é por disciplina, não por estudante. Não existe
"a frequência escolar" deste estudante neste dataset.

### 3.5. As notas, e o que calibrariam

`G3` em 0–20, reescalado para 0–10 e repartido nas faixas de
`GRADE_DISTRIBUTION` (`backend/app/synthetic/calibration.py`):

| faixa (0–10) | hoje (SAEB) | UCI Mat. | UCI Port. |
|---|---|---|---|
| Insuficiente (0–4,9) | **0,59** | 0,329 | 0,154 |
| Básico (5,0–6,9) | 0,24 | 0,418 | 0,547 |
| Proficiente (7,0–8,4) | 0,13 | 0,192 | 0,228 |
| Avançado (8,5–10,0) | 0,04 | 0,061 | 0,071 |

Os dois arquivos do UCI diferem entre si por **mais de um fator 2** na faixa
Insuficiente (0,329 contra 0,154) — mesmas escolas, majoritariamente as mesmas
pessoas. E ambos ficam longe da âncora brasileira atual.

Também medido, e relevante para quem for citar a literatura do dataset:

```text
corr(G1, G3) = 0,801 (Mat.)  /  0,826 (Port.)
corr(G2, G3) = 0,905 (Mat.)  /  0,919 (Port.)
```

Os resultados publicados sobre este dataset que incluem `G2` entre as entradas
estão, em boa medida, prevendo a nota final a partir da nota do segundo
período. Citar essas acurácias como benchmark convida exatamente essa objeção.

---

## 4. Critério de encaixe: o que cada tabela do Sinaliza receberia

Volumes atuais do banco de demonstração, confirmados lendo
`backend/app/synthetic/facts.py` e `generate.py` (200 estudantes, 4
disciplinas — `SUBJECTS`, 4 períodos, ~210 dias letivos):

| tabela | hoje | o que o UCI fornece |
|---|---|---|
| `students` | 200 | 395 (Mat.) ou 649 (Port.), ~662 distintos combinados |
| `grades` | 3.200 (datadas, 4 disciplinas × 4 períodos) | **3 por estudante, sem data, uma disciplina**, escala 0–20 |
| `attendance_records` | **~42.000 (datadas)** | **um inteiro por estudante *por disciplina*, sem denominador** |
| `assignments` / `assignment_submissions` | 3.200 | **nada** |
| `pedagogical_observations` | 800 | **nada** |
| `academic_periods` | 4, com `start_date`/`end_date`/`order_index` | implícitos em G1/G2/G3, sem datas |
| `follow_ups` e derivados | processo humano | nada, por definição |

Duas das cinco tabelas de fato ficam **sem fonte alguma**. A maior delas —
42.000 linhas datadas — teria que ser fabricada a partir de um escalar que
nem sequer está na unidade certa (§3.3). Isso é sintetizar de qualquer forma,
com procedência **pior** que a de hoje: hoje a regra está escrita, testada e
versionada em `profiles.py`; ali estaria escrita num script de ETL para
preencher um buraco.

---

## 5. Rota A — UCI como fonte dos fatos

**O que é.** Substituir o gerador: importar os registros do UCI como
estudantes, notas e faltas.

**Encaixe.** §4. Duas tabelas vazias, uma fabricada, notas reduzidas a 3
pontos sem data em uma disciplina.

**Features temporais.** Das quatro, sobrevive **uma, degenerada**:

| feature | sob rota A |
|---|---|
| `attendance_trend` | **impossível** — exige série cronológica de chamadas |
| `consecutive_absences` | **impossível** — exige saber *quais* dias, não quantos |
| `missing_assignment_delta` | **impossível** — não há entrega nenhuma |
| `grade_delta` | sobrevive como `G3 − G1`, 3 pontos, 1 disciplina, `order_index` fabricado |

São exatamente as três que levaram o F1 macro da floresta de 0,8288 para
0,9824 (`docs/model-evaluation.md` §6). A rota A as desliga.

**Circularidade: não reduz — troca de problema.** O rótulo deixa de ser
`SyntheticProfile` e passa a ser alguma função de `G3`. O modelo deixa de ser
circular e passa a ser **irrelevante**: prevê desempenho final a partir de
desempenho parcial, com `corr(G2, G3) = 0,905` fazendo o trabalho. Não é um
experimento sobre trajetória; é regressão de nota.

**`AGENTS.md` violado.**

| seção | violação |
|---|---|
| §Privacidade | "dados reais são proibidos por padrão"; dado de saúde (`health`), informação familiar (`famrel`, `Pstatus`, `Medu`/`Fedu`, `Mjob`/`Fjob`) de adolescentes reais, versionados ou carregados no banco de demo |
| §Limites do MVP | "dados sintéticos"; "não adicionar dados reais" |
| §Dados sintéticos | "nunca misturar dataset sintético com dados reais" |
| §Features | features sensíveis sem necessidade; ou, sem elas, um dataset esvaziado |
| §Machine Learning | o objetivo declarado ("distinguir padrões simulados construídos no dataset") deixa de existir |
| §Missão / §UX | sem evento datado não há linha do tempo, e sem linha do tempo não há trajetória — que **é** o produto |

Mudança necessária em cada uma: reescrever §Privacidade e §Limites do MVP para
permitir dado real; reescrever §Features para admitir variável socioeconômica;
reescrever §Machine Learning para um objetivo novo. Isto é **reescrever o
contrato do projeto**, não ajustá-lo.

**Risco de quebra.** `backend/tests/` tem **489 funções `def test_`** (a
contagem de ~556 inclui a expansão por `parametrize`). Em risco direto:

| conjunto | arquivos | nº de funções |
|---|---|---|
| importam `app.synthetic` | `test_synthetic_calibration` (29), `test_synthetic_profiles` (27), `test_synthetic_observations` (22), `test_synthetic_generation` (17), `test_synthetic_facts_generation` (12), `test_ml_model_provenance` (10), `test_synthetic_dataset_split` (8), `test_ui_package_3` (6) | **131** |
| importam `app.ml` | `test_ml_temporal_features` (22), `test_ml_evaluate` (16), `test_ml_predict` (15), `test_ml_feature_aggregation` (12), `test_ml_compare` (12), `test_ml_model_provenance` (10), `test_qa_ml_cli_failure_modes` (8), `test_ml_train` (8) | **103** |
| união (descontado `test_ml_model_provenance`, nos dois) | | **224** |

Mais os que dependem de fato datado via fixture: `test_trajectory` (18),
`test_trajectory_detail` (17), `test_convergence_domain` (27),
`test_trajectory_domain` (8), `test_live_demo_no_future_leakage` (5) — 75
funções que sobrevivem apenas enquanto as fixtures continuarem fabricando
datas, ou seja, apenas enquanto o produto continuar sendo demonstrado com
dado sintético ao lado do real.

**Ordem de grandeza: ~224 funções de teste a reescrever, até ~299 a revisar.**

**Esforço.** Uma épica, não uma onda. Fases: (1) licença, citação e
renegociação com a banca; (2) ETL isolado e decisão sobre as 26 colunas não
escolares; (3) remapeamento do domínio para aceitar fato não datado —
migration, repositórios, invariantes de `filter_as_of`; (4) redesenho das
features e do alvo; (5) reescrita de `calibration.py`,
`docs/model-evaluation.md`, `docs/data-model.md` e das seções de privacidade e
ML do `AGENTS.md`; (6) reescrita dos ~224 testes. Cinco a oito ondas,
otimistamente.

**Defesa: ganha e perde.** Ganha a frase "usamos uma base pública consagrada".
Perde: a linha do tempo, as features temporais, o objetivo declarado do
experimento, a coerência com a proposta aprovada, e a tese de que o produto é
sobre trajetória. Troca um argumento forte ("este é um experimento sobre o
pipeline, honestamente delimitado") por um fraco ("prevemos a nota final a
partir da nota do segundo período, em uma escola portuguesa de 2008").

**Veredicto: rejeitar.**

---

## 6. Rota B — híbrido: alvo derivado do UCI, fatos gerados

**O que é.** Usar o UCI para derivar um rótulo que o gerador não conhece, e
gerar os fatos datados condicionados a esse rótulo.

Esta é a rota mais interessante das três no papel, porque é a única que tenta
atacar a circularidade diretamente. Ela falha por três motivos independentes,
cada um suficiente.

**(1) Não existe alvo defensável no dataset.** Os três candidatos:

| candidato | prevalência | problema medido |
|---|---|---|
| `G3 == 0` (saída/não avaliado) | 9,6% Mat., 2,3% Port. | **perfeitamente confundido com `absences == 0`** (§3.3). O alvo ensina "sem faltas ⇒ abandona" |
| `G3 < 10` (reprovação) | 32,9% Mat., 15,4% Port. | não é evasão; é desempenho. Muda o objeto do TCC |
| `G3 < G1` (queda) | 38,8% vs 19,1% para **as mesmas 366 pessoas** | o construto não é estável nem dentro do estudante (concordância 59,6%, §3.4) |

Nenhum é "evasão". O dataset não tem rótulo de evasão, e o mais próximo é um
artefato de coleta.

**(2) A circularidade volta, por uma porta pior.** Para condicionar os fatos
datados ao alvo, é preciso **escrever uma regra** que traduza o alvo em
rampas de presença, nota e entrega. Essa regra é o novo `profiles.py`. A
pergunta do §2 — "o modelo é medido contra algo que o autor das features não
escreveu?" — continua respondida com **não**: alguém escreveu a regra, e as
features continuam medindo a regra. A única mudança é que a regra deixou de
estar num módulo puro, documentado, determinístico e com 27 testes
(`test_synthetic_profiles.py`), e passou a estar num ajuste sobre 395 linhas
de uma escola portuguesa. **Procedência pior, circularidade igual.**

**(3) O dado sensível entra mesmo assim.** Para que o alvo "não seja conhecido
pelo gerador", ele tem de carregar estrutura que o gerador não tem — e a única
estrutura que o UCI oferece além das notas são as 26 colunas da §3.2. Um
modelo de condicionamento ajustado sobre `Medu`, `Fjob`, `Dalc`, `famrel` e
`health` e **versionado** no repositório é informação familiar e de saúde real
transformada em coeficiente, não anonimizada por transformação. O
`AGENTS.md` §Privacidade e §Features são violados com uma camada de abstração
a mais, não a menos — e a camada a mais é precisamente "esconder a origem de
um sinal" (§Atalhos proibidos).

**Encaixe / features / testes.** Melhores que A: os fatos continuam datados,
as quatro features temporais sobrevivem, e a quebra se concentra em
`app/synthetic/` (131 funções) mais `test_synthetic_calibration` inteiro.
Estimativa: **~140 funções**, duas a três ondas.

**Defesa: ganha e perde.** Ganha a aparência de ancoragem externa. Perde na
primeira pergunta técnica: "qual é o alvo, e por que ele está correlacionado
negativamente com faltas?".

**Veredicto: rejeitar.** Mais caro que C, mais arriscado que A em
credibilidade, e não resolve o que se propõe a resolver.

---

## 7. Rota C — referência de calibração

**O que é.** Ler estatísticas agregadas do UCI e transformá-las em parâmetros
em `backend/app/synthetic/calibration.py`, como já se faz com o Censo Escolar.

É a rota que a issue #65 recomenda, e é a que esta análise mais corrige.

**Quantos parâmetros existem para fortalecer.** Medido no módulo:
`confidence=Confidence.NONE` aparece **7 vezes**, não oito. E um dos sete,
`TRAIN_EVAL_SPLIT_RATIO`, o próprio módulo declara fora de escopo de
calibração ("nenhuma base pública, de nenhum país, mediria uma proporção de
split de treino/avaliação"). Restam **6 candidatos**.

**Quais deles o UCI de fato alcança.** Um a um:

| parâmetro | UCI pode calibrar? | por quê (medido) |
|---|---|---|
| `DAILY_ATTENDANCE_RATE_BASELINE` | **não** | `absences` não tem denominador e não é diária; é por disciplina, em blocos de aula (§3.3). O mesmo estudante tem números diferentes nos dois arquivos, idênticos em só 27,3% dos casos (§3.4) |
| `DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR` | **não** | idem, e não há definição de "em risco" no dataset |
| `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE` | **não** | não existe coluna de atividade |
| `ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE` | **não** | idem |
| `ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING` | **não** | idem |
| `SYNTHETIC_PROFILE_PROPORTIONS` | **não** | não há rótulo de perfil nem de evasão; o proxy mais próximo (`G3 < G1`) vale 38,8% ou 19,1% conforme o arquivo, para as mesmas pessoas (§3.4) |
| `GRADE_DISTRIBUTION` (já `MEDIUM`, não `NONE`) | **tecnicamente sim** | §3.5 — e o resultado é pior que o atual |

**Então a rota C, como descrita na issue #65, é quase vazia.** Os três ganhos
que ela promete — "frequência diária, entrega de atividade, mistura de
perfis" — são exatamente os três que o dataset **não mede**. O único parâmetro
que ele toca é o que já tem âncora.

**E tocar nele é um rebaixamento, não um reforço.** Trocar a faixa
Insuficiente de 0,59 (SAEB 2023, Brasil, amostral nacional) por 0,329 (UCI
Matemática) ou 0,154 (UCI Português) significa: substituir uma âncora
brasileira recente por uma portuguesa de 2008, de dois colégios, que
**discorda de si mesma por um fator 2** entre disciplinas. O gerador passaria
a desenhar um corpo discente em que a reprovação é metade da brasileira, numa
demonstração para uma banca brasileira.

**Teto honesto da rota C.** Mesmo que se aceitasse o número, o `kind` não
poderia virar `CALIBRATED`. O vocabulário do módulo é explícito: `CALIBRATED`
é "valor retirado de uma estatística pública **brasileira**", e `NO_PUBLIC_SOURCE`
diz textualmente "nenhuma base federal, estadual ou agregadora (INEP, IBGE,
QEdu) mede esta variável". O UCI não é uma estatística pública publicada: é
**microdado de pessoa**, 395 adolescentes reais, do qual *nós* calcularíamos o
agregado. A procedência mudaria de natureza — de "o INEP publicou X" para
"nós computamos X a partir dos registros de 395 adolescentes portugueses de
2008". Com honestidade, isso é `DESIGN_ASSUMPTION` com `Confidence.LOW`, não
`CALIBRATED`/`HIGH`. **A rota C, bem feita, move um parâmetro de `NONE` para
`LOW` — e nenhum dos seis que precisam de ajuda.**

**Circularidade: não reduz, em nada.** Calibrar um parâmetro do gerador muda
*os números* da regra geradora; não muda o fato de que as features foram
escritas lendo a regra. O F1 continuaria em ~1,00, pelo mesmo motivo de hoje.
Esta é a observação central: **a rota C é barata porque não muda nada que
importe para o problema da §2.**

**`AGENTS.md`.** É a rota mais conforme das três — nenhum registro de pessoa é
versionado nem carregado no banco. Mas duas tensões reais:

- §Privacidade: o download e a inspeção acontecem, e um `source` apontando
  para microdado de adolescentes muda o caráter da declaração de procedência
  num módulo cujo teste `test_no_parameter_carries_person_level_data` existe
  justamente para garantir que ali só há agregado publicado.
- §Dados sintéticos ("nunca misturar dataset sintético com dados reais"): um
  parâmetro derivado de dado real dentro do gerador sintético é mistura por
  derivação. Defensável — o Censo já é isso — mas o Censo é agregado
  publicado, e isto não é.

**Risco de quebra.** Pequeno e localizado, e por isso vale listar
nominalmente (lendo `tests/test_synthetic_calibration.py`):

- `test_grade_distribution_is_a_documented_proxy_not_calibrated_data` —
  asserção direta `insufficient.share == anchor.value`, fixando a faixa
  Insuficiente na âncora SAEB. **Quebra** se o número mudar.
- `test_parameters_with_no_anchor_at_all_claim_no_confidence` — parametrizado
  sobre 6 nomes, assert `confidence is NONE` **e** `source_refs == ()`. Quebra
  (uma vez por nome promovido) se qualquer um deles ganhar fonte.
- `test_parameters_without_a_brazilian_public_source_are_design_assumptions` —
  parametrizado sobre os mesmos 7 nomes.
- `test_sourced_values_match_the_published_statistics` — fixa valores
  literais; precisaria de entrada nova.
- `test_calibrated_parameters_cite_a_source_and_claim_real_confidence`.
- Mais `test_synthetic_profiles.py` (27) e `test_synthetic_generation.py` (17)
  no que dependa do valor numérico, e qualquer fixture que assuma a
  distribuição de notas atual.

**Estimativa: 5 a 12 funções quebram de fato; ~45 exigem leitura.** Uma onda
curta — a issue acerta aqui.

**Defesa: ganha e perde.** Ganha pouco: um parâmetro a mais com fonte, de
relevância discutível. Perde: a nitidez da frase "toda calibração vem de base
pública brasileira", que hoje é verdadeira e fácil de defender.

**Veredicto: não vale uma onda na forma proposta.** Ver §7.1.

### 7.1. Rota C reduzida — o uso que sobra, e que custa quinze minutos

O UCI tem um valor real para este TCC, e ele **não é numérico**. Ele é o
dataset público mais citado em "predição de desempenho estudantil", e a
inspeção acima mostra que ele é **transversal, sem evento datado, sem
atividade, sem observação, e com o único rótulo parecido com evasão
corrompido por artefato de coleta**.

Isso é exatamente o argumento de que a escolha de sintetizar é correta e não
preguiçosa. Entra em `docs/model-evaluation.md` §10 e na revisão de literatura
como **trabalho relacionado examinado e descartado, com medição própria** —
na mesma forma que `docs/research/technical-bases-publicas-dados-educacionais-calibr-2026-09-17/research.md`
já usa para os microdados do INEP.

Custo: um parágrafo e uma citação. Ganho na defesa: a pergunta "por que não
usou uma base real?" passa a ter resposta medida em vez de resposta de
princípio. **Esta é a única parte da proposta do UCI que recomendo adotar.**

---

## 8. Rota D — avaliação fora da regra geradora

A rota que nenhuma das três é, e que ataca o problema da §2 diretamente.

### 8.1. A ideia

A circularidade não vem de os dados serem sintéticos. Vem de **as features
terem sido escritas lendo a regra, e o modelo ser medido contra aquela mesma
regra**. Trocar a origem dos dados não desfaz isso (§6.2); trocar **o que está
do outro lado da medição** desfaz.

Concretamente: manter o gerador e as features como estão, e acrescentar
**variantes do gerador que as features não foram escritas para enxergar**.
Treinar no gerador canônico; avaliar nas variantes. Reportar o F1 por
variante.

Variantes propostas, todas derivadas de perguntas pedagógicas legítimas, não
de ruído artificial:

| variante | regra | o que testa |
|---|---|---|
| `step_change` | a queda acontece de uma vez, num ponto do ano, em vez de rampa linear | `half_split_delta` foi construída *porque* "a rampa do gerador é linear". Com degrau, a meia-diferença ainda separa? |
| `late_onset` | a queda começa no último terço do ano | metade dos pontos da segunda metade ainda é estável; a feature dilui |
| `recovery` | cai e depois recupera parcialmente | `attendance_trend` tende a ~0; `consecutive_absences` não. Mede se as quatro features são redundantes ou complementares |
| `noisy_profile` | rampa com ruído por turma | robustez |
| `overlapping` | um estudante com dois eixos em queda fraca, abaixo do limiar de `COMBINED_DETERIORATION` | o esquema de 4 rótulos mutuamente exclusivos é uma suposição (§10.5 do `model-evaluation.md`); isto a torna mensurável |

### 8.2. Por que isso resolve o que as outras não resolvem

Porque produz um número que **pode ser baixo**. Hoje o experimento não tem
como falhar: as features invertem a regra por construção. Sob a rota D, se o
F1 cair de 1,0000 para, digamos, 0,55 em `step_change`, isso é um resultado
**informativo e publicável**: diz que o desempenho atual é específico da forma
da rampa, o que é a hipótese que §10.1 e §10.5 levantam no papel e ninguém
mediu. Se não cair, é evidência real de que as features capturam "queda" e não
"a rampa do `profiles.py`".

Os dois desfechos valem a defesa. **Nenhuma das rotas A, B ou C tem essa
propriedade.**

### 8.3. Custo e conformidade

- **Encaixe de formato:** perfeito — o domínio não muda em nada.
- **Features temporais:** todas as quatro sobrevivem; é precisamente elas que
  estão sob teste.
- **Circularidade: reduz, e é a única rota avaliada que reduz.**
- **`AGENTS.md`:** nenhuma seção violada. §Dados sintéticos ("cada perfil
  sintético deve possuir regra conhecida") é *reforçada*: cada variante é uma
  regra conhecida a mais, determinística e com seed. §Avaliação de ML é
  atendida melhor. §Privacidade intocada.
- **Risco de quebra:** baixíssimo. As variantes entram atrás de um parâmetro
  novo com default igual ao comportamento atual; nenhum teste existente muda
  de resultado. Trabalho novo: testes das variantes (~15 a 25 funções novas) e
  uma seção nova em `docs/model-evaluation.md`.
- **Esforço: uma onda, duas no máximo.** Fases: (1) decisão registrada em
  `docs/decisions/` sobre quais variantes e por quê — escrita **antes** de
  medir, para que o resultado não seja escolhido depois; (2) variantes em
  `profiles.py` atrás de flag, com testes; (3) comando de avaliação cruzada
  reportando F1 por variante; (4) §11 nova em `docs/model-evaluation.md`.
- **Defesa:** ganha a resposta para a pergunta mais perigosa que a banca pode
  fazer — "o seu F1 de 1,0 não é só o modelo redescobrindo o seu próprio
  gerador?". Hoje a resposta é "sim, e está documentado". Sob a rota D a
  resposta passa a ser "sim, e medimos quanto disso sobrevive quando o gerador
  muda de forma: aqui estão os números". Perde: nada.

### 8.4. Uma nota de segunda mão, para registro

Se, apesar de tudo, a prioridade for *dado real datado*, o Student Performance
é o dataset errado — ele não tem data em lugar nenhum (§3.1). O candidato
estrutural correto seria o **OULAD** (Open University Learning Analytics
Dataset), que, **pelo que se descreve publicamente e não foi verificado
aqui**, traz interações datadas, entregas de avaliação com `date_submitted`, e
um desfecho que inclui desistência. Isso o tornaria, em tese, capaz de
calibrar justamente os parâmetros que o UCI não alcança (§7).

Três ressalvas, todas sérias: (a) **não consegui baixá-lo** — o endpoint
histórico responde `301` para uma landing page, então nada acima é inspeção
direta; (b) é ensino superior a distância, não educação básica presencial, o
que torna "frequência" um conceito diferente; (c) continua sendo dado real de
pessoas, então o bloqueio do §Privacidade sobre versionar permanece idêntico —
só o uso como referência agregada (rota C) seria discutível. **Não recomendo
investigar antes da rota D**, mas registro para que a opção não se perca.

---

## 9. Tabela comparativa

| critério | **A** (fonte dos fatos) | **B** (alvo UCI, fatos gerados) | **C** (calibração) | **C reduzida** (§7.1) | **D** (variantes do gerador) |
|---|---|---|---|---|---|
| **1. Encaixe de formato** | 2 de 5 tabelas sem fonte; `attendance` fabricada de escalar na unidade errada | fatos continuam datados; só o alvo vem de fora | não toca o schema | não toca nada | não toca o schema |
| **2. Features temporais** | 1 de 4 sobrevive, degenerada | 4 de 4 | 4 de 4 | 4 de 4 | 4 de 4, e são o objeto do teste |
| **3. Circularidade** | troca por irrelevância (`corr(G2,G3)=0,905`) | **mantém** — a regra só muda de autor e piora de procedência | **mantém, integralmente** | mantém (mas declara melhor) | **reduz — única que reduz** |
| **4. `AGENTS.md`** | §Privacidade, §Limites, §Dados sintéticos, §Features, §ML, §Missão | §Privacidade, §Features, §Atalhos proibidos | tensão em §Privacidade e §Dados sintéticos | conforme | **conforme; reforça §Dados sintéticos** |
| **5. Risco de quebra** | ~224 funções reescritas, até ~299 revisadas | ~140 | 5–12 quebram, ~45 a revisar | 0 | ~0; +15–25 testes novos |
| **6. Esforço** | 5–8 ondas (uma épica) | 2–3 ondas | 1 onda curta | ~15 min | 1–2 ondas |
| **7. Defesa** | perde a trajetória, o objetivo do experimento e a proposta aprovada | cai na 1ª pergunta sobre o alvo | ganha ~nada; perde a nitidez da calibração brasileira | **ganha resposta medida para "por que não usou base real?"** | **ganha resposta para a pergunta mais perigosa** |

---

## 10. Recomendação

**Não adotar o Student Performance Dataset como fonte (A) nem como alvo (B)
nem como calibração numérica (C).** Adotar apenas a rota **C reduzida**
(§7.1): citá-lo, com as medições deste documento, como base pública examinada
e descartada — custo de um parágrafo. E, no lugar do que a rota C prometia
entregar, executar a rota **D** (§8).

O argumento, em três passos:

1. **O problema declarado é a circularidade.** Está escrito em
   `docs/model-evaluation.md` §10.1 e §10.5, e é o motivo pelo qual a pergunta
   sobre o UCI foi feita.
2. **Medido, o UCI não tem como reduzi-la.** As rotas A e B trocam a
   circularidade por problemas piores (irrelevância e procedência degradada); a
   rota C não a toca sequer de leve, porque calibrar um parâmetro da regra não
   muda o fato de as features terem sido derivadas da regra. E a rota C,
   medida, nem sequer entrega o que promete: dos 6 parâmetros sem fonte, o UCI
   alcança **zero** (§7).
3. **Uma onda gasta na rota D entrega o que três rotas com dado real não
   entregam**, sem tocar em privacidade, sem renegociar com a banca, sem pôr
   224 testes em risco, e com a propriedade — rara neste projeto — de poder
   produzir um número ruim que valha a pena publicar.

A rota C reduzida e a rota D são **independentes e compatíveis**: a primeira é
documentação, a segunda é código. Podem ser feitas na mesma semana, por
agentes diferentes.

---

## 11. O que me faria mudar de ideia

Honestamente, e em ordem de força:

1. **Se a banca já tiver exigido, por escrito, "dados reais".** Nenhuma
   análise técnica vence um requisito de avaliação. Nesse caso a rota correta
   não é nenhuma destas: é procurar um dataset **datado** (§8.4), porque adotar
   um transversal destrói o produto para satisfazer a letra do requisito.
2. **Se o objeto do TCC mudar de "trajetória" para "desempenho".** Sob esse
   objetivo a rota A deixa de ser absurda — `G3` vira alvo legítimo e o
   dataset é adequado. Mas isso é outro TCC, e a proposta aprovada não é essa.
3. **Se o OULAD (§8.4) for baixado e confirmar a estrutura descrita.** Aí
   existiria, pela primeira vez, uma rota C que de fato calibra
   `DAILY_ATTENDANCE_RATE_*` e `ASSIGNMENT_NON_DELIVERY_RATE_*` contra
   medição. Continuaria sem reduzir a circularidade — seria um complemento da
   rota D, nunca um substituto.
4. **Se a rota D for executada e o F1 não cair em nenhuma variante.** Isso
   esgotaria o que o gerador consegue testar sobre si mesmo, e aí a pressão
   por validação externa passaria a ser legítima em vez de cosmética.
5. **Se eu estiver errado sobre o artefato `G3 == 0`.** Minha leitura é
   inferência a partir de uma coincidência perfeita em 53 linhas (38 + 15); a
   coincidência é fato medido, a interpretação ("saiu / não foi avaliado") é
   minha. Uma fonte primária que explique o zero de outro jeito enfraquece a
   objeção mais forte contra a rota B — mas não a elimina, porque a instabilidade
   entre disciplinas (§3.4) é independente dela.

---

## 12. Onde a issue #65 erra

A issue acerta no essencial — o bloqueio de privacidade, o desencaixe
transversal × datado, três das quatro features perdidas, o custo de uma épica.
Os pontos abaixo são correções, não refutações, exceto o item 2, que é uma
refutação da sua recomendação.

1. **"oito parâmetros hoje com `confidence=NONE`"** → são **7**
   (`grep -c 'confidence=Confidence.NONE'`), e um deles
   (`TRAIN_EVAL_SPLIT_RATIO`) o próprio módulo declara fora do escopo de
   calibração pública. Candidatos reais: **6**.

2. **"Ganho: fortalece parte dos oito parâmetros... (frequência diária,
   entrega de atividade, mistura de perfis)"** → **nenhum dos três é
   calibrável a partir deste dataset** (§7). `absences` não é frequência
   diária, não tem denominador e é por disciplina (medido: o mesmo estudante
   tem valores idênticos nos dois arquivos em apenas 27,3% dos casos); não
   existe coluna de atividade; não existe rótulo de perfil, e o proxy mais
   próximo vale 38,8% ou 19,1% conforme o arquivo, para as mesmas 366 pessoas.
   **A rota C recomendada pela issue é quase inteiramente vazia**, e o único
   parâmetro que o dataset toca (`GRADE_DISTRIBUTION`) sairia pior.

3. **"Uma onda curta. Ganho: fortalece..."** → o custo está certo; o ganho,
   não. E, mais importante, a issue **não submete a rota C ao critério que ela
   mesma estabelece**: C não reduz a circularidade em nada. Uma onda barata que
   não resolve o problema declarado continua sendo uma onda gasta.

4. **"~395 (Matemática) ou ~649 (Português)"** → correto por arquivo, mas os
   dois descrevem majoritariamente **as mesmas pessoas**: 382 pares / 366
   chaves distintas pelo merge oficial. A população distinta combinada é de
   ordem de 662, não 1.044.

5. **"`attendance_records`: um inteiro `absences` por estudante"** →
   subestimado. É um inteiro por estudante **por disciplina**, em blocos de
   aula e não em dias (>90% dos valores são pares), com 29–38% exatamente zero.
   Não é só "sem data": está na unidade errada.

6. **Omissão decisiva: o artefato `G3 == 0 ⇒ absences == 0`** (53 de 53 linhas,
   nos dois arquivos). É o fato que mata a rota B de forma independente de
   qualquer outro argumento, e a issue não o menciona porque a issue não
   inspecionou os dados. A correlação `absences × G3` **inverte de sinal**
   quando o artefato entra (+0,034 → −0,213).

7. **Omissão: `corr(G2, G3) = 0,905`.** Relevante para quem citar a literatura
   do dataset como benchmark.

8. **Enquadramento.** A issue trata o bloqueio de privacidade como o que
   "decide sozinho". Ele decide sobre A e B. Mas mesmo **sem** bloqueio algum
   de privacidade, A, B e C continuariam sendo rotas ruins pelos motivos
   técnicos das §§5–7. É um argumento mais forte e menos dependente de uma
   regra que uma banca poderia, em tese, flexibilizar.

---

## 13. Riscos não levantados por ninguém

1. **A rota C contamina o vocabulário de procedência.** `calibration.py`
   define `CALIBRATED` como estatística pública *brasileira*, e
   `NO_PUBLIC_SOURCE` nomeia INEP/IBGE/QEdu. Um `source` apontando para
   microdado de 395 adolescentes portugueses entra num módulo cujo teste
   `test_no_parameter_carries_person_level_data` existe para garantir que ali
   só há agregado publicado. O número até pode ser agregado; a **declaração**
   muda de natureza. O módulo inteiro vale pela nitidez dessa distinção.

2. **Risco de citação cruzada na defesa.** Se o UCI for citado como âncora de
   calibração e a banca conhecer o dataset, a pergunta natural é "por que a
   distribuição de notas de dois colégios portugueses em 2008 calibra uma
   demonstração brasileira em 2026?". Não há boa resposta.

3. **A rota A destrói uma capacidade que não volta.** O gerador é o que torna
   possível `test_live_demo_no_future_leakage`, o truncamento em "hoje"
   (`filter_as_of`) e a demonstração ao vivo. Fatos reais sem data não
   truncam. Se a rota A for tentada, o gerador deve ser **mantido**, nunca
   removido — ver §14.

4. **Licença e citação.** CC BY 4.0 (segunda mão, §1.2) exige atribuição
   explícita a Cortez & Silva (2008) em qualquer uso, **inclusive na rota C
   reduzida**. Barato, mas tem de estar lá.

5. **Risco de confirmação na própria rota D.** Se as variantes forem escolhidas
   *depois* de medir, elas viram vitrine. Por isso a §8.3 pede que a decisão
   sobre quais variantes exista em `docs/decisions/` **antes** da medição. É o
   mesmo princípio que levou `docs/decisions/0003` a transformar a comparação
   de modelos em comando reproduzível.

6. **Risco de escopo na rota D.** "Variantes do gerador" é um buraco sem fundo.
   Fixar cinco, no documento de decisão, e não acrescentar uma sexta depois sem
   nova decisão registrada.

7. **O banco de demonstração.** Mesmo na rota C, alguém vai querer "ver os
   dados". O dataset não pode ser carregado em nenhum dos três containers de
   Postgres, nem em fixture, nem em seed — a inspeção acontece fora, por um
   humano, e só o número agregado atravessa, como `calibration.py` já
   determina ("consultada **offline**, por um humano... nunca persistida no
   banco do sistema").

---

## 14. Caminho de reversão

Se a rota escolhida der errado no meio:

**Rota C reduzida.** Reversão trivial: é um parágrafo em
`docs/model-evaluation.md` e uma citação. `git revert` do commit.

**Rota D.** Reversão barata **se e somente se** as variantes entrarem atrás de
um parâmetro com default igual ao comportamento atual. Com esse cuidado, o
gerador canônico nunca muda, nenhum teste existente depende das variantes, e
abandonar a rota é remover um módulo e uma seção de documento. **Condição de
entrada da onda:** o primeiro commit deve demonstrar que o dataset gerado com
os defaults tem `population_fingerprint` **idêntico** ao de hoje. Se o
fingerprint mudar, a variante vazou para o caminho canônico e a reversão
deixou de ser barata.

**Rota C numérica.** Reversível por `git revert` enquanto for só
`calibration.py` + testes. Ponto de não retorno: o momento em que um dataset
gerado sob a nova distribuição for usado para treinar uma versão de modelo
registrada em `ml_model_version`. A partir dali, `training_dataset_version`
aponta para um conteúdo que o código revertido não reproduz mais, e a linha de
procedência fica órfã (`docs/model-evaluation.md` §7: "não houve backfill...
escrever ali o valor de hoje seria procedência fabricada"). **Reverter antes de
treinar, ou aceitar uma linha órfã e documentá-la.**

**Rota A.** Praticamente irreversível por `git revert` depois da fase 3
(remapeamento do domínio para fato não datado), porque a migration que afrouxa
`AttendanceRecord` e os repositórios reescritos atravessam dezenas de arquivos.
Reversão realista = branch longo, nunca mesclado, com `master` preservando o
gerador. **Regra de segurança: `app/synthetic/` não é removido em nenhuma fase
da rota A.** Enquanto ele existir e os testes dele passarem, existe caminho de
volta; no dia em que for apagado, não existe mais.

**Rota B.** Mesma regra: o `profiles.py` canônico fica, e o condicionamento
pelo alvo externo entra como um perfil adicional, nunca como substituição.

---

## 15. Como reproduzir as medições

Os dados **não estão** no repositório e não devem estar. Para refazer:

1. Baixar `https://archive.ics.uci.edu/static/public/320/student+performance.zip`
   para uma pasta temporária **fora** do repositório (o zip contém outro zip,
   com `student-mat.csv`, `student-por.csv`, `student-merge.R` e `student.txt`).
2. As medições deste documento são contagens, médias, correlações de Pearson e
   um merge pelas 13 colunas de `student-merge.R`. Nenhuma biblioteca além da
   padrão é necessária; os scripts usados foram descartáveis e ficaram fora do
   repositório por decisão de privacidade.
3. Apagar a pasta ao terminar.

Números do repositório (reproduzíveis aqui):

```bash
cd backend
grep -c 'confidence=Confidence.NONE' app/synthetic/calibration.py     # 7
grep -rc '^\s*\(async \)\?def test_' tests/*.py | awk -F: '{s+=$2} END {print s}'   # 489
grep -ln 'app\.synthetic' tests/*.py   # 8 arquivos, 131 funções
grep -ln 'app\.ml'        tests/*.py   # 8 arquivos, 103 funções
```

---

## Referências

- Cortez, P.; Silva, A. (2008). *Using Data Mining to Predict Secondary School
  Student Performance*. UCI ML Repository, id 320. CC BY 4.0 (licença não
  verificada aqui — §1.2).
- `AGENTS.md` — §Privacidade, §Features, §Machine Learning, §Dados sintéticos,
  §Controle de escopo, §Atalhos proibidos.
- `docs/model-evaluation.md` — §1, §3, §6, §10.1, §10.5.
- `docs/research/technical-bases-publicas-dados-educacionais-calibr-2026-09-17/research.md`
  — o precedente de base pública examinada e descartada.
- `docs/decisions/0003-comparacao-de-modelos-como-comando-reproduzivel.md`,
  `0004-features-temporais-derivadas-da-regra-geradora.md`.
- Issue [#65](https://github.com/bruno-romeu/sinaliza/issues/65) — a análise
  preliminar que este documento verifica e corrige (§12).
- `backend/app/synthetic/calibration.py`, `profiles.py`, `facts.py`;
  `backend/app/ml/temporal_features.py`, `feature_aggregation.py`;
  `backend/tests/test_synthetic_calibration.py`.
