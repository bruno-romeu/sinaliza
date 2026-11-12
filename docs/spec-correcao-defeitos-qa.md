---
id: SPEC-correcao-defeitos-qa
companions: []
sources:
  - AGENTS.md
  - docs/spec-qa-adversarial.md
  - backend/tests/test_qa_hostile_input.py
  - backend/tests/test_qa_ml_cli_failure_modes.py
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Correcao dos defeitos D1, D2, D3 e D5 da passagem adversarial de QA

## Why

A passagem adversarial (`docs/spec-qa-adversarial.md`) deixou cinco defeitos
provados por teste `xfail(strict=True)` e deliberadamente **nao** corrigidos.
Esta onda fecha quatro deles — D1, D2, D3 e D5. D4 (acompanhamento duplicado)
e corrigido em paralelo por outro agente e nao e tocado aqui.

Os quatro se agrupam em tres causas.

**Causa 1 — `sqlalchemy.exc.DataError` nao tem tradutor (D1, D2).**
`app/presentation/errors.py` mapeia `AppError`, `IntegrityViolationError` e
`RepositoryIntegrityError`. A familia "o valor nao e representavel no tipo da
coluna" — SQLSTATE classe 22, `DataError` — nao tem handler nenhum, entao
escapa como 500 sob uvicorn. Dois gatilhos alcancaveis:

- **D1.** `GET /home` e `GET /home/search` validam `page_size` com
  `ge=1, le=MAX_*` e validam `page`/`changes_page`/`follow_ups_page` **so com
  `ge=1`**. `offset = (page - 1) * page_size` estoura o `bigint`. Reproduzido
  contra a pilha real: `?changes_page=9223372036854775807` e
  `?changes_page=99999999999999999999` dao 500; `?changes_page=184467440737095517`
  ainda da 200.
- **D2.** Um byte NUL (`\u0000`) atravessa
  `StringConstraints(strip_whitespace=True, min_length=1)` intacto e o psycopg
  recusa o `INSERT`. Mesmo 500, por texto livre que qualquer outro valor
  invalido receberia 422.

**Causa 2 — a existencia do artefato de ML nao e verificada antes de abri-lo
(D3).** `app/ml/predict.py` trata com mensagem acionavel e `exit 1` todos os
modos de falha que conhece (tabela vazia, versao inexistente, sem dados
`EVAL_DEMO`, esquema de features divergente) menos o `artifact_path` ausente:
`joblib.load` levanta `FileNotFoundError` cru, e um artefato truncado levanta
`KeyError: 110`. O cenario e real porque `docker-compose.yml` declara
`postgres_data` como volume nomeado e **nao declara volume nenhum** para
`/app/ml_artifacts`: treinar dentro do container grava a linha
`ml_model_version` onde sobrevive e o `.joblib` onde nao sobrevive, e um
`docker compose up --build` orfana toda linha de procedencia.

**Causa 3 — data de fato escolar sem faixa (D5).** Nenhum dos tres schemas de
data tem limite e o `<input type="date">` do `Presenca.tsx` nao tem
`min`/`max`. `2999-12-31` e `0001-01-01` dao 201. Pior, o Pydantic coage
inteiro a data (`{"date": 0}` vira `1970-01-01`) e devolve 201. Como toda
leitura e truncada em `as_of()` (`filter_as_of`, aplicado as quatro colunas de
data de fato) e nao existe endpoint de releitura, o registro com ano errado e
confirmado com "Registro salvo." e nunca mais aparece — nem para ser
corrigido.

## Capabilities

- **CAP-1** — `page`, `changes_page` e `follow_ups_page` tem teto declarado.
  *intent*: o numero de pagina e validado na mesma assinatura e com a mesma
  forma que o `page_size` irmao ja usa, antes de virar `OFFSET`.
  *success*: os quatro casos parametrizados de
  `test_qa_oversized_page_answers_422_instead_of_crashing` respondem 422, sem
  `xfail`, e os casos negativos de `page=0`/`page=-1` continuam 422.

- **CAP-2** — Um `DataError` que escape a validacao de borda responde no
  envelope, nunca 500.
  *intent*: a correcao de D1/D2 nao pode depender de cada rota futura lembrar
  de declarar o teto certo; o mesmo argumento que ja justifica o backstop de
  `RepositoryIntegrityError` no proprio `errors.py`.
  *success*: `app/presentation/errors.py` registra handler para
  `sqlalchemy.exc.DataError` devolvendo 422 no envelope
  `{"error": {"code", "message"}}`, sem nome de tabela nem de coluna no corpo.

- **CAP-3** — Byte NUL em texto livre e recusado com 422.
  *intent*: texto que o Postgres nao consegue armazenar e entrada invalida, e
  deve ser dito como tal na borda, nao descoberto no `INSERT`.
  *success*: `test_qa_nul_byte_in_observation_text_answers_422_instead_of_crashing`
  passa sem `xfail`, e o teste de ida e volta de Unicode/bidi continua 201.

- **CAP-4** — Artefato de ML ausente ou corrompido produz mensagem acionavel e
  `exit 1`.
  *intent*: quem roda o comando descobre o que fazer (retreinar), nao um
  traceback.
  *success*: os dois testes `test_qa_*_artifact_file_raises_an_actionable_ml_error`
  passam sem `xfail`; a checagem corre **depois** de
  `require_matching_feature_schema`, para o teste de ordem continuar valendo;
  nenhuma linha `MLPrediction` e escrita.

- **CAP-5** — Os artefatos de ML persistem entre reconstrucoes da imagem.
  *intent*: a procedencia gravada no banco aponta para um arquivo que continua
  existindo.
  *success*: `docker-compose.yml` declara um volume nomeado montado em
  `/app/ml_artifacts` do servico `backend`.

- **CAP-6** — Data de fato escolar tem faixa e tipo estritos.
  *intent*: um erro de digitacao no ano e recusado na hora, em vez de gravado e
  tornado invisivel pela truncagem de leitura.
  *success*: os tres testes de D5 passam sem `xfail`; `Presenca.tsx` declara
  `min`/`max` no `<input type="date">`; os registros validos que a suite ja
  grava continuam 201.

- **CAP-7** — Nenhum teste existente passa a falhar e a contagem de `xfailed`
  cai.
  *success*: `uv run pytest -q` sai de `589 passed, 11 xfailed` para
  `599 passed, 1 xfailed` (o unico restante e o D4, de outro agente).

## Constraints

- **Faixa de data ancorada em `as_of()`, nao em `academic_periods`.** Ver
  "Decisao: a faixa de datas de D5".
- **Teto superior de fato ocorrido = `as_of()`; de `due_date` = `as_of()` + 1
  ano.** Um fato nao acontece em dia que nao chegou; um prazo legitimamente
  sim.
- **Nada de migration nesta onda.** A `0017` pertence ao agente de D4.
- **Fronteira de arquivos.** Nao se toca em
  `backend/tests/test_qa_authorization_and_state.py`,
  `backend/app/infrastructure/db/models.py` nem no caminho de `FollowUp`.
- **`docs/deferred-work.md` e `docs/sprint-status.yaml` nao sao editados aqui.**
- **O `xfail` sai, a explicacao fica.** O motivo do defeito migra para a
  docstring do teste: e a memoria de por que o teste existe.
- **Controller fino (`AGENTS.md` §API).** A faixa de data e validacao de
  schema, nao regra de servico; nenhuma leitura de banco entra no caminho de
  validacao.

## Non-goals

- Nao corrigir D4 (acompanhamento duplicado).
- Nao criar endpoint de releitura/correcao de presenca, nota ou entrega — e a
  outra metade da mordida de D5, mas e RF nova, nao correcao de defeito.
- Nao redesenhar UI. No frontend, so `min`/`max` no input de data.
- Nao consertar divida aberta de `docs/deferred-work.md` que nao seja um
  destes quatro defeitos.
- Nao corrigir os 45 warnings pre-existentes do lint do frontend.
- Nao mudar contrato de API alem do que a correcao exige.

## Decisao: a faixa de datas de D5

**Escolhido:** faixa ancorada em `as_of()`, declarada em
`app/presentation/schemas/school_dates.py` e reusada pelos tres schemas:

- `as_of() - 5 anos` <= data <= `as_of()` para fato ocorrido (presenca, nota,
  entrega);
- `as_of() - 5 anos` <= `due_date` <= `as_of() + 1 ano` para prazo de
  atividade;
- recusa explicita de valor numerico em todos, para que inteiro nao seja
  coagido a data.

`Field(strict=True)` foi a primeira tentativa e **nao serve**: o FastAPI
desserializa o corpo e valida o `dict` resultante em modo Python, onde
`strict` recusa tambem a string ISO-8601 que todo cliente legitimo manda —
medido, 22 testes existentes quebraram. A guarda que fecha o buraco sem
fechar a porta e um `BeforeValidator` que recusa `bool`/`int`/`float`.

O teto nao e numero escolhido a dedo: e exatamente a regra de leitura que o
proprio projeto ja aplica. `filter_as_of` trunca em `as_of()` as quatro
colunas de data de fato (`AttendanceRecordModel.date`, `GradeModel.date`,
`AssignmentSubmissionModel.date`, `AssignmentModel.due_date`). Escrever um
fato datado depois de `as_of()` e escrever algo que o sistema, pela sua
propria regra, nunca vai ler. A guarda diz literalmente "nao gravamos o que
nao conseguiriamos ler". `due_date` e a excecao justificada: cadastrar
atividade antes do prazo e o fluxo natural do professor, e a truncagem faz a
atividade aparecer quando a data chega — isso e comportamento pretendido, nao
defeito. O piso de 5 anos e folgado em relacao ao horizonte do MVP ("um ano
letivo", `AGENTS.md`) e recusa tanto `0001-01-01` quanto o `1970-01-01` que a
coercao de inteiro produzia.

**Descartado — faixa fixa em constante** (ex.: `2000-01-01 .. 2100-12-31`):
nao fecha a mordida descrita. O caso real e digitar 2027 em vez de 2026, e uma
constante larga aceita 2027 exatamente como hoje.

**Descartado — faixa derivada de `academic_periods`.** Investigado, e nao
serve:
1. `AttendanceRecordModel` **nao tem** `period_id` — so `Grade` e `Assignment`
   tem. Para presenca seria preciso perguntar "algum periodo contem esta
   data?", o que mete leitura de banco e um erro de aplicacao novo dentro do
   caminho de validacao de um POST, contra `AGENTS.md` §API.
2. `academic_periods` e conjunto de **fixture de desenvolvimento**
   (`ListAcademicPeriodsService`: "lists every dev-fixture academic period"),
   e os periodos semeados cobrem 2026-07-27..2026-09-25. Amarrar fato a
   periodo cadastrado transformaria a guarda de digitacao num portao de
   calendario que os dados do MVP nao conseguem honrar — a data de hoje nao
   cai em periodo nenhum.
3. Grade e Assignment ficariam com regra mais estrita que presenca sem que o
   usuario conseguisse prever a diferenca.

**Descartado — endpoint de releitura/correcao.** E a resposta certa para a
outra metade de D5 ("nem para ser corrigido"), ja adiada em
`docs/deferred-work.md` desde a Story 1.3. E RF nova, com rota, servico e
tela; nao cabe numa onda de correcao de defeito.

## Decisao: handler de backstop para `DataError`

**Acrescentado.** O proprio `app/presentation/errors.py` ja documenta o
argumento para o backstop de `RepositoryIntegrityError`: "the mapping must not
depend on every current *and future* write service remembering to wrap its
repository call". Vale igual aqui — o `le=` fecha o caminho conhecido de D1,
mas depende de cada `Query(...)` futuro lembrar do teto, e D2 e um gatilho
**diferente** da mesma familia que nenhum `le=` alcanca. `DataError` e a
classe 22 do SQLSTATE ("data exception"): todo membro dela significa "o valor
enviado nao e representavel", que e 422 por definicao — nao ha caso em que 500
seja a resposta honesta. O corpo nao carrega nome de tabela, coluna nem
constraint, seguindo a politica que o modulo ja aplica.

Nao e substituto das correcoes estreitas: `le=` e NUL recusado no schema dao
mensagem de campo util; o handler so garante que nenhum caso ainda nao
imaginado vire 500.

## Success signal

`uv run pytest -q` reporta `599 passed, 1 xfailed`; `?changes_page=99999999999999999999`
responde 422 contra a pilha real em `http://localhost`; `docker compose config`
mostra o volume de `/app/ml_artifacts`; e cada teste que deixou de ser `xfail`
continua explicando no docstring o defeito que o fez nascer.

## Assumptions

- `SINALIZA_DEMO_AS_OF` fica **desligado** no deploy real (comentario do
  `docker-compose.yml`), entao a faixa de datas do backend coincide com o
  "hoje" do navegador que o frontend usa em `min`/`max`.
- O fuso do navegador (UTC-3) nunca produz um "hoje" local **depois** do
  `as_of()` em UTC, entao o `max` do input nao recusa data que o backend
  aceitaria.

## Open questions

- O piso de 5 anos e generoso de proposito. Se o TCC quiser importar historico
  antigo algum dia, e o numero a rever.
