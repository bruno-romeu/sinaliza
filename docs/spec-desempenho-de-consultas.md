---
id: SPEC-desempenho-de-consultas
companions: []
sources:
  - docs/deferred-work.md
  - docs/architecture.md
  - docs/data-model.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Desempenho de consultas: três índices redundantes e o N+1 de nome de estudante na Home

## Why

Este é o único item da lista original de trabalho que nunca teve passagem
dedicada: ninguém olhou plano de execução, N+1 ou índice faltando. O que
existe hoje nessa direção foi achado por acidente, não por varredura.

A varredura foi feita e mediu **três coisas distintas**, com conclusões
diferentes.

**Primeiro: os três índices redundantes (achado já catalogado, confirmado e
em parte corrigido).** `ix_enrollments_student_id`,
`ix_attendance_records_student_id` e `ix_trajectory_changes_student_id` são
prefixos à esquerda de um índice UNIQUE da mesma tabela que **começa
exatamente por `student_id`** — a condição que torna a cobertura válida.
Confirmado por comparação de catálogo própria, não aceito do registro
anterior: uma consulta sobre `pg_index` comparando `indkey` **e** `indclass`
como arrays (não como `LIKE`, que casaria `{2}` com `{20,3}`) devolve
exatamente esses três e mais nenhum em todo o schema.

Mas a justificativa catalogada em `docs/deferred-work.md` estava **mais forte
do que a medição sustenta**, em dois pontos:

- *"o planner nunca os escolhe"* — falso como afirmação geral. Uma busca
  `WHERE student_id = ?` **sem** predicado de data em `attendance_records`
  escolhe sim `ix_attendance_records_student_id`, porque ele é menor (680 kB
  contra 4416 kB do índice único). O que é verdade — e foi medido — é mais
  estreito: **nenhuma das consultas que a aplicação de fato emite** tem essa
  forma. Todas as leituras de `attendance_records` por estudante também
  restringem `date`, e aí o índice único atende o predicado composto inteiro.
- *"escrita duplicada em todo INSERT"* — real em princípio, **não mensurável
  aqui**. Três inserções de 10.000 linhas em `attendance_records` com e sem os
  três índices dão 459/241/187 ms contra 240/248/313 ms: faixas sobrepostas,
  nenhum sinal.

Então a remoção **não é uma melhoria de desempenho** e o PR não deve afirmar
que é. É higiene de schema: 728 kB no banco de dev e um índice a menos para
manter, com cobertura provada.

**Segundo: o N+1 do `GET /home`.** `GetHomeService.execute` resolve o nome do
estudante dentro de dois laços — um por `TrajectoryChange` e um por
`FollowUp` —, chamando `StudentRepositoryPort.get_by_id` uma vez por linha. A
contagem de queries é `4 + N + M`, linear no tamanho de página, e o tamanho de
página é **controlado pelo cliente** até 100 em cada lista
(`MAX_CHANGES_PAGE_SIZE`/`MAX_FOLLOW_UPS_PAGE_SIZE`). Medido contra uma cópia
do banco de demonstração: 10 queries no padrão (5+5) e 21 em
`?changes_page_size=100&follow_ups_page_size=100` — 21 e não 204 só porque o
dataset tem 16 mudanças e 1 acompanhamento. É defeito estrutural mesmo rodando
rápido: cresce linearmente com dado que ainda não existe.

**Terceiro: índices faltando — não há.** Capturadas as 32 instruções distintas
que as telas reais emitem (Home, busca, trajetória, detalhe de trajetória,
acompanhamento, lançamento), cada uma foi submetida a
`EXPLAIN (ANALYZE, BUFFERS)` com os **parâmetros reais** contra a cópia do
banco de dev. A mais cara do conjunto executa em **0,450 ms**
(`GET /home/search`); a maior tabela (`attendance_records`, 42.000 linhas)
responde em 0,055 ms por `Index Scan` no índice único. Não há Seq Scan que um
índice resolveria: onde o planner varre, varre tabela de 1 a 200 linhas, e
varrer está correto. Nenhum índice novo é acrescentado, e esse resultado
negativo é entrega, não omissão.

## Capabilities

- **CAP-1 — Migration 0016 remove os três índices redundantes.**
  intent: Uma única migration nova (`0016`, `down_revision = "0015"`) derruba
  `ix_enrollments_student_id`, `ix_attendance_records_student_id` e
  `ix_trajectory_changes_student_id`; `downgrade()` os recria idênticos. As
  três colunas em `app/infrastructure/db/models.py` deixam de declarar
  `index=True`, para que o schema declarado e o banco não divirjam.
  success: `alembic upgrade head` → `downgrade -1` → `upgrade head` passa, e
  um teste afirma contra o catálogo (`pg_index`/`to_regclass`) que os três
  índices somem no `upgrade` e voltam no `downgrade`, em vez de afirmar só
  sobre tabelas.

- **CAP-2 — A cobertura é provada, não assumida.**
  intent: Um teste verifica, no próprio banco, que cada índice removido tinha
  um índice UNIQUE da mesma tabela cujo `indkey` começa pelo `indkey` do
  removido — a propriedade que torna a remoção segura — em vez de confiar em
  uma lista escrita à mão que envelhece junto com o schema.
  success: O teste falha se alguém acrescentar um índice não-único que seja
  prefixo à esquerda de um único na mesma tabela, ou se um dos índices únicos
  deixar de começar por `student_id`.

- **CAP-3 — `GET /home` resolve nomes de estudante em lote.**
  intent: `StudentRepositoryPort` ganha uma resolução em lote
  (`get_names_by_ids`), sujeita ao mesmo filtro `dataset_split = EVAL_DEMO`
  (AD-11) de `get_by_id`, e `GetHomeService` passa a chamá-la uma vez por
  lista em vez de uma vez por linha. O comportamento de pular a linha quando o
  estudante não resolve é preservado exatamente — inclusive o caso de um
  `student_id` `TRAIN`, que continua não aparecendo na Home.
  success: A contagem de queries do `GET /home` deixa de depender do tamanho
  de página: 6 queries constantes, com `?changes_page_size=100&
  follow_ups_page_size=100` igual ao padrão. Um teste conta as queries com um
  listener de evento do SQLAlchemy e falha se a contagem voltar a crescer com
  o número de linhas.

## Constraints

- **Consulta otimizada devolve exatamente o mesmo resultado.** Não é promessa,
  é condição de aceite: a comparação foi feita sobre 78 resultados de caminho
  de leitura (os 60 estudantes `EVAL_DEMO`, as 8 turmas, 5 buscas, 4 páginas
  de Home e o acompanhamento), com e sem os três índices, e o SHA-256 do dump
  canônico é o mesmo.
- **Nenhum índice novo sem medição que o justifique.** Todo índice custa
  escrita; o dataset tem ~200 estudantes sintéticos e o planner escolhe Seq
  Scan **corretamente** em tabela pequena.
- **Nada de cache, Redis ou dependência nova** (`AGENTS.md` §Atalhos
  proibidos: "adicionar tecnologia sem necessidade"). A correção do N+1 é
  trocar N queries por uma, não memorizar resultado.
- **Nada de desnormalização nem tabela de agregação.**
- **Uma única migration nesta onda.** `0015` é a cabeça; duas migrations
  paralelas colidem no `down_revision` e o git mescla isso "limpo" antes de
  quebrar em runtime.
- **O banco de demonstração (`sinaliza-postgres-1`) é somente leitura.** Toda
  medição que precisou escrever (benchmark de INSERT, `pg_stat_reset`, DROP
  INDEX experimental) rodou contra uma **cópia** restaurada por `pg_dump` em
  um banco separado (`sinaliza_perf`) no Postgres de teste isolado.

## Non-goals

- **Não reestruturar o N+1 do `GET /follow-ups/{id}`.** O laço sobre
  `FollowUpEvidence` em `GetFollowUpService.execute` emite ~7 queries por
  linha de evidência (uma `get_by_id` mais a resolução de evidências). É da
  mesma classe, mas o N é o número de mudanças que um humano citou como
  evidência — não um parâmetro de query. Medido: 9 queries com a única
  evidência que existe no dataset. Corrigi-lo exige transformar
  `resolve_evidence` em uma resolução multi-mudança, que é mudança de forma em
  código compartilhado por duas telas; fica catalogado, não feito aqui.
- **Não reestruturar as 4 chamadas de `_series_point`** em
  `GetStudentTrajectoryDetailService` (16 das 39 queries do detalhe). É laço
  por período, limitado por `_MAX_PERIODS_IN_SERIES = 4`, não por dado — não
  cresce. Juntar as leituras exigiria mudar a fronteira entre o serviço e
  `compute_trajectory_indicators`, que é pura de propósito (AD-12).
- **Não mexer em `app/ml/`, `app/synthetic/`, `frontend/`** nem em outros
  documentos de `docs/` (há outro agente nessas áreas nesta onda).
- **Não tocar `docs/deferred-work.md` nem `docs/sprint-status.yaml`.**
- **Não remover `ix_attendance_records_classroom_id`** nem os demais índices
  de FK com 0 varreduras. Eles não são prefixo de índice único nenhum
  (`indkey` `{3}` contra `{2,3,4}`), então nada os cobre, e "nunca varrido no
  workload de leitura de hoje" não é o mesmo que redundante.

## Success signal

`uv run pytest -q`, `uv run ruff check .` e `uv run ruff format --check .`
passam; o ciclo upgrade/downgrade/upgrade da migration `0016` passa; o
`GET /home` responde em 6 queries tanto no tamanho de página padrão quanto em
100/100 (contra 10 e 21 antes); e os 78 resultados de caminho de leitura têm o
mesmo SHA-256 antes e depois.

## Assumptions

- A `0015_ml_model_version_provenance` continua sendo a cabeça da cadeia
  quando este PR for mergeado — o outro agente desta onda não mexe em schema.
- O banco de demonstração reflete o dataset que a banca verá (~200
  estudantes, 42.000 presenças, 16 mudanças de trajetória). As conclusões de
  "rápido o bastante" valem **para esse tamanho**, e o PR diz isso.

## Open questions

- Nenhuma. As duas perguntas que apareceram durante a medição foram
  respondidas e viraram escopo ou não-escopo acima.
