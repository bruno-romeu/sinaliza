---
id: SPEC-qa-adversarial
companions: []
sources:
  - AGENTS.md
  - docs/deferred-work.md
  - docs/model-evaluation.md
  - docs/architecture.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# QA adversarial: defeitos encontrados por quem nao escreveu o codigo

## Why

Onze agentes implementaram banco, ORM, rotas, rate limit, seguranca, ML,
responsividade, UI, UX, acessibilidade, higiene e desempenho. Cada um escreveu
os proprios testes. Quem escreve o codigo escolhe os testes que ele passa:
nenhuma das 551 assercoes existentes foi escrita por alguem tentando quebrar o
sistema.

Esta passagem atacou catorze superficies e encontrou **cinco defeitos**. Nao
encontrou nenhuma violacao do `AGENTS.md`, nenhum contorno do 403 de
`GET /follow-ups/{id}`, e nenhuma variante do bug de escrita obsoleta do
`Presenca.tsx` em outra tela. Esses resultados negativos sao parte da entrega:
eles dizem onde o sistema e solido.

Os cinco defeitos se agrupam em tres causas distintas.

**Causa 1 — `DataError` nao tem tradutor (D1, D2).** `app/presentation/errors.py`
registra handler para `AppError`, `IntegrityViolationError` e
`RepositoryIntegrityError`. `sqlalchemy.exc.DataError` — a familia "o valor nao
cabe/nao e representavel no tipo da coluna" — nao tem nenhum, entao escapa como
500. Dois gatilhos alcancaveis foram confirmados:

- **D1.** `GET /home` e `GET /home/search` validam `page_size` com
  `ge=1, le=MAX_*`, mas validam `page`/`changes_page`/`follow_ups_page` **so
  com `ge=1`**. `offset = (page - 1) * page_size` passa de `bigint` e o Postgres
  responde `NumericValueOutOfRange`. Medido: `?page=9223372036854775807` e
  `?page=99999999999999999999` quebram as tres rotas; `?page=184467440737095517`
  (com `page_size=5`) ainda cabe e devolve 200 vazio. O limite superior existe
  para o irmao `page_size` na mesma assinatura e falta para `page`.
- **D2.** Um byte NUL (`\u0000`) em `PedagogicalObservationCreateRequest.text`
  ou em `RegisterFollowUpActionRequest.description` chega intacto ao `INSERT`
  (`strip_whitespace`/`min_length` nao o removem) e o psycopg recusa:
  `PostgreSQL text fields cannot contain NUL (0x00) bytes`. Mesmo 500.

**Causa 2 — a procedencia do artefato de ML nao e verificada antes de abrir o
arquivo (D3).** `app/ml/predict.py` trata com mensagem limpa e `exit 1` todos
os modos de falha que conhece: tabela vazia, versao inexistente, sem dados
`EVAL_DEMO`, esquema de features divergente. Nao trata o caso de o
`artifact_path` gravado na linha nao existir mais no disco: `joblib.load`
levanta `FileNotFoundError` cru. Arquivo corrompido e pior — `KeyError: 110`,
que nao diz nada a ninguem.

O cenario nao e hipotetico: `docker-compose.yml` declara `postgres_data` como
volume nomeado, e **nao declara volume nenhum para `/app/ml_artifacts`**, que o
`backend/Dockerfile` cria dentro da camada gravavel da imagem. Treinar dentro
do container grava a linha `ml_model_version` no volume que sobrevive e o
`.joblib` na camada que nao sobrevive. Um `docker compose up --build` deixa
toda linha de modelo apontando para um arquivo que nao existe, e o comando de
pontuacao responde com traceback em vez de "retreine".

Medido na pilha que esta no ar agora: `ml_model_version` tem **zero linhas** e
`/app/ml_artifacts` esta **vazio** no `sinaliza-backend-1`. Ou seja, o defeito
nao esta mordendo a demonstracao hoje — ele morde na primeira vez que alguem
treinar dentro do container e depois reconstruir a imagem, que e exatamente o
fluxo de um ensaio.

**Causa 3 — a unicidade do acompanhamento aberto nao existe no banco (D4).**
`spec-ui-1` adicionou o reaproveitamento justamente porque "todo clique criava
outro `FollowUp`, entao um duplo clique deixava casos abertos duplicados". A
implementacao e `find_open_for_student` seguido de `save_with_evidence` —
leitura-depois-escrita sem transacao serializavel e **sem indice unico parcial
no banco**. Confirmado: duas linhas `follow_ups` com o mesmo `student_id`,
mesmo `responsible_user_id` e status diferente de `ENCERRADO` sao aceitas pelo
Postgres. O botao da tela de trajetoria se desabilita enquanto salva, entao o
duplo clique numa aba esta coberto; **duas abas na mesma trajetoria nao**.

**D5 — data sem faixa, aceita e invisivel.** `AttendanceCreateRequest.date`,
`GradeCreateRequest.date` e `AssignmentSubmissionCreateRequest.date` nao tem
limite nenhum, e o `<input type="date">` do `Presenca.tsx` tambem nao tem
`min`/`max`. `2999-12-31` e `0001-01-01` sao gravados com 201. Pior: o Pydantic
coage silenciosamente um **inteiro** a data (`{"date": 0}` vira `1970-01-01`,
tempo Unix), entao um cliente que mande o tipo errado nao recebe 422 — recebe
201 e um fato escolar errado. Como toda leitura de trajetoria e truncada em
`as_of()` e nao existe endpoint de releitura de presenca/nota/entrega, o
registro com ano errado e confirmado com "Registro salvo." e depois **nunca
mais aparece em lugar nenhum**, nem para ser corrigido.

## Capabilities

- **CAP-1** — Cada um dos cinco defeitos tem um teste automatizado que o
  demonstra.
  *intent*: a afirmacao "existe este defeito" e verificavel por `pytest`, nao
  por relato.
  *success*: `backend/tests/test_qa_*.py` contem um teste por defeito; cada um
  falha contra o codigo de hoje e passa quando o defeito for corrigido, e esta
  marcado `xfail(strict=True)` com o motivo escrito.

- **CAP-2** — Cada resultado negativo tem um teste que o fixa como invariante.
  *intent*: "atacamos isto e nao quebrou" so vale se a proxima mudanca nao
  puder quebrar em silencio.
  *success*: existem testes passando para o escopo cruzado de `FollowUp` (403
  em leitura, acao e status), para a imutabilidade do `GET /home/search` diante
  de curingas `LIKE`, e para as fronteiras que ja respondem 422 limpo
  (`window_days`, UUID malformado, `Decimal` nao finito, data impossivel).

- **CAP-3** — Nenhum teste existente passa a falhar.
  *intent*: a passagem adversarial mede, nao reescreve.
  *success*: `uv run pytest -q` continua com os mesmos 551 testes passando,
  mais os novos.

## Constraints

- **Testes, nao correcoes.** Defeito encontrado vira teste `xfail(strict=True)`
  com motivo, nunca patch no codigo de producao. Quem corrige e decisao do
  usuario.
- **Prefixo `test_qa_`** em todo arquivo novo, para nao colidir com os 34
  arquivos existentes.
- **Banco de teste isolado na porta 5437** (`sinaliza-test-postgres-4`). Nunca
  5433/5435/5436. O banco de demonstracao (`sinaliza-postgres-1`) e somente
  leitura.
- **`POST /auth/login` aceita 10 tentativas por 300s.** Reaproveitar sessao
  dentro de cada teste em vez de logar em laco.
- **`docs/deferred-work.md` e `docs/sprint-status.yaml` nao sao editados aqui.**
  A autoridade neles e do usuario; esta passagem reporta.
- **Rigor calibrado a MVP de TCC com dados sinteticos.** Um defeito so entra se
  o cenario concreto em que ele morde puder ser escrito. "Seria problema com mil
  usuarios" nao entra — o `AGENTS.md` veda security theater explicitamente.

## Non-goals

- Nao aumentar cobertura. A meta e defeito, nao percentual.
- Nao corrigir os 45 warnings pre-existentes do lint do frontend.
- Nao reportar divida ja catalogada sem `resolved:` em `docs/deferred-work.md`
  como se fosse achado novo (guarda de escrita obsoleta do `Presenca.tsx`,
  `GET /home` x `list_active`, CSP sem `script-src`, indices redundantes,
  `LogisticRegression` ausente ate a onda de comparacao).
- Nao propor arquitetura nova. O escopo e medir o que existe.

## Success signal

Um leitor do PR consegue dizer, sem rodar nada, **o que foi atacado, com que
evidencia, e o que resistiu** — e consegue reproduzir cada defeito rodando um
unico teste nomeado.

## Assumptions

- O deploy real serve com `uvicorn`, onde uma excecao nao tratada vira HTTP 500;
  o `TestClient` do Starlette repropaga a excecao em vez de devolver 500, entao
  os testes de D1/D2 afirmam a excecao, nao o status.
- Dois usuarios so existem em teste: o seed de producao cria um. D4 e os testes
  de escopo cruzado semeiam o segundo usuario diretamente.

## Open questions

- D4 se corrige com indice unico parcial + `ON CONFLICT`, ou a duplicata de duas
  abas e aceitavel num MVP de um operador? Decisao de produto.
- D5 se corrige com faixa de data no schema (qual faixa?) ou com endpoint de
  releitura, que `docs/deferred-work.md` ja adia desde a Story 1.3? As duas
  opcoes mudam escopo.
