---
id: SPEC-acompanhamento-aberto-unico-no-banco
companions: []
sources:
  - docs/spec-qa-adversarial.md
  - docs/spec-ui-1-pacote-backend-design-system.md
  - docs/spec-4-1-abertura-de-acompanhamento-vinculado-a-evidencias.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the
> complete, preservation-validated contract for what to build, test, and
> validate.

# Acompanhamento aberto único: a verificação sai da aplicação e entra no banco (D4)

## Why

`spec-ui-1` acrescentou o reaproveitamento de `POST /follow-ups` **porque
acompanhamento duplicado era defeito**: antes dela, todo clique em "Abrir
acompanhamento" criava outro `FollowUp`, e o estudante acabava com dois
processos abertos. A regra escolhida foi: se já existe um acompanhamento não
encerrado para aquele estudante e aquele responsável, devolva o existente
(HTTP 200) em vez de criar outro (HTTP 201).

A regra está certa. A implementação dela é que não é uma regra — é uma
sequência: `find_open_for_student` (SELECT) e depois `save_with_evidence`
(INSERT), sem nenhuma restrição no banco entre as duas. Duas requisições que
leiam antes de qualquer uma escrever passam ambas pela verificação e inserem
as duas. A verificação é uma janela de corrida, não uma garantia.

O cenário foi medido pela passagem adversarial de QA (`docs/spec-qa-adversarial.md`,
Causa 3): a mesma trajetória aberta em **duas abas**, clique em "Abrir
acompanhamento" nas duas no mesmo segundo. O botão da tela só se desabilita
por aba, então o duplo clique numa aba está coberto e duas abas não estão.
Resultado: **dois cards idênticos na Home, com a evidência dividida entre
eles** — cada processo citando metade do caso, e nenhum dos dois contando a
história inteira.

Num produto cujo argumento central é que `FollowUp` é processo humano
rastreável (`AGENTS.md` §Acompanhamento), isso não é cosmético: é a rastreabilidade
se partindo em dois.

O defeito existe desde a Story 4.1 e foi encontrado por um agente de QA que
não escreveu o código. A `docs/spec-qa-adversarial.md` o deixou como pergunta
de produto em aberto ("índice único parcial + `ON CONFLICT`, ou a duplicata de
duas abas é aceitável num MVP de um operador?"). Esta spec responde: fecha, e
fecha devolvendo o acompanhamento que ganhou a corrida, não um erro.

## Capabilities

- **CAP-1 — O banco recusa o segundo acompanhamento aberto.**
  intent: Migration `0017` cria um índice único **parcial**
  `uq_follow_up_open_per_student_and_owner` sobre
  `(student_id, responsible_user_id)` com predicado
  `WHERE status <> 'ENCERRADO'`, e `FollowUpModel` o declara em
  `__table_args__` para que o schema declarado e o banco não divirjam (a
  suíte constrói o schema por `Base.metadata.create_all`, não por Alembic).
  O predicado é **exatamente** o mesmo que `find_open_for_student` já usa, de
  modo que a restrição do banco e a verificação da aplicação não possam
  divergir sobre o que é "em aberto".
  success: Dois `INSERT` em `follow_ups` com o mesmo `student_id`, o mesmo
  `responsible_user_id` e qualquer status diferente de `ENCERRADO` falham no
  `commit` — afirmado por teste contra Postgres real, nos dois sentidos da
  migration.

- **CAP-2 — Perder a corrida cai no reaproveitamento, não em erro de tela.**
  intent: `OpenFollowUpService` passa a tratar o `DuplicateRecordError`
  levantado pelo `save_with_evidence` como o que ele significa: outra
  requisição acabou de abrir o acompanhamento deste estudante. O serviço
  relê `find_open_for_student`, vincula a evidência clicada se ela ainda não
  estiver vinculada, e devolve o vencedor com `created=False` — ou seja, o
  mesmo caminho e a mesma resposta (HTTP 200) do reaproveitamento que
  `spec-ui-1` especificou. Se a releitura não encontrar nada (o vencedor foi
  encerrado no intervalo), o erro é repropagado: inventar um segundo
  acompanhamento ali seria recriar o defeito.
  success: Duas aberturas concorrentes do mesmo (estudante, responsável)
  produzem **um** `FollowUp`, as duas respostas apontam para ele, e nenhuma
  das duas abas vê mensagem de erro.

- **CAP-3 — A corrida é demonstrada, não só o caminho feliz.**
  intent: O `xfail(strict=True)` do D4 em
  `tests/test_qa_authorization_and_state.py` perde o marcador e mantém o
  docstring que explica por que o teste existe. Ao lado dele entram testes
  que exercitam a corrida de verdade — duas sessões concorrentes sobre a
  mesma conexão de teste, e uma segunda inserção direta que contorna o
  `SELECT` da aplicação —, não apenas o reaproveitamento sequencial que já
  tinha cobertura.
  success: `xfailed` cai para o valor anterior menos um, nenhum `xpassed`
  aparece, e os novos testes falham se o índice for removido.

- **CAP-4 — A migration não apaga processo humano por conta própria.**
  intent: `upgrade()` verifica antes de criar o índice se já existem pares
  `(student_id, responsible_user_id)` com mais de uma linha não encerrada. Se
  existirem, a migration **para** com uma mensagem que nomeia os pares e diz
  o que fazer (encerrar um dos acompanhamentos, decisão humana), em vez de
  escolher uma linha para apagar. `downgrade()` apenas derruba o índice.
  success: Num banco com duplicata, `alembic upgrade head` falha com a
  mensagem em vez de `UniqueViolation` crua ou de perda de linha; num banco
  limpo, sobe sem ruído.

## Constraints

- **A unicidade é por `(estudante, responsável) em aberto`, não por
  estudante.** Um estudante pode legitimamente ter vários acompanhamentos ao
  longo do ano — abriu, conduziu, encerrou, meses depois abriu outro — e o
  escopo por responsável já é o que `find_open_for_student`,
  `GetFollowUpService` e `ChangeFollowUpStatusService` aplicam (RF-22,
  `epic-4-retro-item-18`). `test_qa_opening_a_follow_up_never_reuses_another_users_case`
  fixa que duas coordenações abrem casos distintos para o mesmo estudante:
  uma unicidade só por `student_id` quebraria esse teste e essa regra.
- **`ENCERRADO` não é estado terminal no código**, e o predicado foi escrito
  sabendo disso. `ChangeFollowUpStatusService` não tem regra de adjacência:
  qualquer um dos quatro estados é alvo válido a partir de qualquer outro
  (`AD-6`, spec 4.2 "No adjacency rules"). Então reabrir um `ENCERRADO`
  quando já existe outro aberto para o mesmo par passa a ser recusado pelo
  banco — o que é a mesma regra aplicada ao mesmo caso, não uma regra nova.
- **Nenhum estado de `FollowUp` muda, e nenhum é criado.** `AGENTS.md`
  §Acompanhamento é explícito, e os quatro valores continuam exatamente como
  estão.
- **Uma única migration nesta onda.** `0016` é a cabeça; a cadeia do Alembic é
  linear e duas migrations paralelas colidem no `down_revision` — o git
  mescla isso "limpo" antes de quebrar em runtime.
- **Nada de tabela nova, nada de desnormalização, nada de dependência nova**
  (`AGENTS.md` §Atalhos proibidos).
- **Nada de `frontend/`.** Desabilitar o botão entre abas não resolve corrida
  — o `localStorage`/`BroadcastChannel` que faria isso continuaria sendo uma
  verificação sem garantia, pela mesma razão que o `SELECT` é.
- **O banco de demonstração não é alterado por este PR.** Verificado: 5
  linhas em `follow_ups`, **nenhum** par duplicado em aberto, então a
  migration sobe nele sem tocar em dado.

## Non-goals

- **Não fechar a duplicação de `FollowUpEvidence`.**
  `follow_up_evidence` não tem unicidade em
  `(follow_up_id, trajectory_change_id)`, então duas abas que caiam no
  caminho de reaproveitamento ao mesmo tempo ainda podem gravar duas linhas
  de evidência para a mesma mudança. É da mesma classe (leitura-depois-escrita
  sem restrição), mas é outro defeito, com outra janela e outro efeito
  (evidência repetida na mesma tela, não dois processos). Fica catalogado,
  não feito aqui.
- **Não transformar o 409 de reabertura em erro de domínio próprio.** Reabrir
  um `ENCERRADO` com outro aberto no mesmo par responde `409 duplicate_record`
  pelo envelope que `presentation/errors.py` já tem. A mensagem é genérica;
  dar a ela um código próprio é decisão de produto sobre uma tela que ainda
  não existe.
- **Não introduzir transação serializável nem `SELECT ... FOR UPDATE`.** O
  índice é mais barato, é declarativo e vale para todo caminho de escrita,
  inclusive um que esqueça de ler antes.
- **Não mexer em `docs/deferred-work.md` nem `docs/sprint-status.yaml`.**
- **Não tocar em `app/ml/`, `docker-compose.yml`, nos routers de paginação e
  faixa de data, nem em `tests/test_qa_hostile_input.py` /
  `tests/test_qa_ml_cli_failure_modes.py`** — outro agente trabalha neles
  nesta onda.

## Success signal

`uv run pytest -q`, `uv run ruff check .` e `uv run ruff format --check .`
passam; o ciclo `upgrade` → `downgrade` → `upgrade` da migration `0017`
passa; o teste do D4 passa sem marcador `xfail`; e duas aberturas concorrentes
do mesmo (estudante, responsável) produzem um único `FollowUp`, devolvido às
duas requisições.

## Assumptions

- `0016` continua sendo a cabeça da cadeia quando este PR for mesclado — o
  outro agente desta onda não cria migration.
- O banco de demonstração em produção é o `sinaliza-postgres-1` inspecionado
  aqui. Outra instância com duplicata histórica vai bater na guarda da CAP-4,
  que é o comportamento desejado.

## Open questions

- Nenhuma. A pergunta que `docs/spec-qa-adversarial.md` deixou aberta
  ("corrigir ou aceitar a duplicata?") está respondida pelo Why.
