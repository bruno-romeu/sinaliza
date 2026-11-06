---
id: SPEC-higiene-codigo-backend
companions: []
sources:
  - docs/deferred-work.md
  - docs/spec-5-2-geracao-de-score-experimental-como-dado-de-pesquisa.md
  - docs/spec-ml-avaliacao-documentada.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Higiene de código do backend: código morto, docstrings defasadas e um homônimo

## Why

Três problemas distintos, todos no `backend/`, todos de higiene — nenhum deles
muda o que o sistema faz.

**Primeiro: código morto medido, não suposto.** Uma varredura com `ruff
--select ARG,ERA`, `vulture` e dois scripts de contagem de referências sobre
todo `app/` (cruzando `app/`, `tests/` e `alembic/`) devolveu exatamente cinco
candidatos reais, depois de descartados os falsos positivos de framework:

- `run_prediction(session, artifact_dir, model_version)` aceita `artifact_dir`
  e nunca o lê — o caminho do artefato vem da linha `MLModelVersionModel`
  selecionada. Já catalogado como item aberto em `docs/deferred-work.md`,
  mantido por "paridade de assinatura" com `run_training` (`spec-5-2`, Code
  Map). Paridade de assinatura não é comportamento: é um parâmetro que mente
  sobre o que a função usa.
- `_build_assignment_submissions(population, ...)` em `app/synthetic/facts.py`
  recebe `population` e nunca o usa; é função privada com um único call site no
  mesmo módulo.
- `MAX_CHANGES_PAGE_SIZE`, `MAX_FOLLOW_UPS_PAGE_SIZE` (`get_home.py`) e
  `MAX_PAGE_SIZE` (`search_students.py`) têm **zero** referências em todo o
  repositório, enquanto o teto que elas nomeiam está escrito como literal
  `le=100` em `app/presentation/home/router.py`. O valor coincide; o nome que o
  explica está solto ao lado, sem ligação.

**Segundo: docstrings que mentem.** Este repositório usa docstrings longas que
explicam *por quê* — padrão deliberado, a preservar. O problema é que algumas
descrevem comportamento que não existe mais, e uma docstring errada é pior que
nenhuma, porque é lida com confiança:

- `app/presentation/auth/dependencies.py` abre com "scaffolded in this story" e
  "Not applied to any route yet". `get_current_user` está hoje em
  `Depends(...)` de **oito** routers (`assignments`, `attendance`,
  `follow_ups`, `grades`, `home`, `observations`, `trajectory`, e por rota em
  `follow_ups`/`observations`/`trajectory`). O mesmo texto se repete em
  `tests/test_auth_login.py`. É o item `epic-1-retro-item-6`.
- `app/config.py` afirma que "Story 5.2's live-inference loader will read this
  same setting to locate an `MLModelVersion.artifact_path`". A Story 5.2
  entregou `app/ml/predict.py`, que **não** lê `ml_artifact_dir` — é
  exatamente o parâmetro morto acima. A frase está errada em dois eixos:
  tempo futuro e fato.
- `app/domain/ml_model_version.py` e `app/infrastructure/db/models.py` dizem
  que a Story 5.2 "will later `joblib.load`" o artefato. Ela já carrega, em
  `predict.py` e `evaluate.py`.
- `app/ml/predict.py` descreve cada execução como "tied to whichever
  `MLModelVersion` was latest at that moment". Desde o `--model-version`
  (PR #54), pode ser uma versão nomeada.

**Terceiro: um homônimo que é armadilha.** `app/ml/predict.py` e
`app/ml/evaluate.py` definem, cada um, sua própria classe `NoModelVersionError`
para o mesmo fato ("a tabela `ml_model_version` está vazia"). São duas classes
independentes com o mesmo nome. Um `except NoModelVersionError` importado do
módulo errado não captura e não avisa — falha silenciosa por nome. O próprio
`app/ml/model_version_selection.py` — módulo que já existe para concentrar a
seleção de versão — trata o conceito como singular na sua docstring
("Distinta de `NoModelVersionError` (tabela vazia) de propósito"). O código
contradiz a intenção já escrita.

## Capabilities

- **CAP-1**
  - **intent:** `run_prediction` declara apenas os argumentos que usa.
  - **success:** A assinatura é `run_prediction(session, model_version=None)`;
    nenhum call site em `app/` ou `tests/` passa um diretório de artefatos; a
    suíte continua com a mesma contagem de testes e `python -m app.ml.predict`
    mantém saída e códigos de saída idênticos.

- **CAP-2**
  - **intent:** `_build_assignment_submissions` declara apenas os argumentos
    que usa.
  - **success:** `population` sai da assinatura e do único call site; os testes
    de geração sintética (incluindo os de determinismo por seed) passam sem
    alteração, provando que o fato gerado é byte a byte o mesmo.

- **CAP-3**
  - **intent:** O teto de paginação tem **um** lugar onde é declarado, e esse
    lugar é a constante que já leva o nome dele.
  - **success:** `le=MAX_CHANGES_PAGE_SIZE`, `le=MAX_FOLLOW_UPS_PAGE_SIZE` e
    `le=MAX_PAGE_SIZE` substituem os três literais `le=100` em
    `app/presentation/home/router.py`; o contrato HTTP não muda (os valores são
    iguais a 100), o que o teste de exposição de API confirma.

- **CAP-4**
  - **intent:** Nenhuma docstring do backend afirma, sobre o código de hoje,
    algo que o código de hoje não faz.
  - **success:** As cinco afirmações listadas em Why passam a descrever o
    comportamento atual, cada uma verificada contra o símbolo que a sustenta;
    o comprimento e o registro explicativo ("por quê") das docstrings são
    preservados — nenhuma é encurtada para virar descrição do "o quê".

- **CAP-5**
  - **intent:** "Não existe nenhuma `MLModelVersion` treinada" é **um** tipo de
    erro no backend, não dois com o mesmo nome.
  - **success:** `NoModelVersionError` passa a ser definida uma única vez, em
    `app/ml/model_version_selection.py`, ao lado de `ModelVersionNotFoundError`
    que já mora lá; `predict.py` e `evaluate.py` a importam; as mensagens
    específicas de cada CLI continuam distintas, porque são passadas no `raise`,
    não na classe; `pytest.raises(NoModelVersionError)` continua passando nos
    dois arquivos de teste.

## Constraints

- **Esta onda não muda comportamento.** Se uma remoção alterar o que o sistema
  faz, ela não é remoção de código morto — é mudança, e fica fora. O critério
  operacional é a suíte: 500 testes passando antes, 500 depois.
- **Prova antes de remoção.** Nenhum símbolo sai sem evidência de que não é
  alcançado: contagem de referências cruzando `app/`, `tests/` e `alembic/`,
  mais leitura do corpo da função. Remoção sem prova é aposta
  (`AGENTS.md` §"Atalhos proibidos").
- **Falsos positivos de framework não são código morto.** Funções registradas
  por decorator do FastAPI, `dispatch` de `BaseHTTPMiddleware`, campos de
  modelo Pydantic/SQLAlchemy e membros de `Enum` aparecem como não-usados em
  qualquer ferramenta estática e **permanecem**.
- **Docstrings longas são o padrão do projeto, não o alvo.** Corrigir uma
  afirmação defasada nunca é pretexto para encurtar a docstring ou trocar o
  "por quê" pelo "o quê" (`AGENTS.md` §"Definição de uma boa mudança").
- **Sem logging.** Acrescentar logging está fora do escopo e é decisão pendente
  do usuário.
- **Sem refatoração arquitetural.** Mover código entre camadas não é higiene.
  O único movimento de símbolo autorizado é CAP-5, e só porque o módulo de
  destino já existe para esse fim e o homônimo é uma armadilha de captura, não
  uma questão de estilo.
- **`frontend/` é território de outro agente.** Nada nele é tocado.
- **`docs/deferred-work.md` e `docs/sprint-status.yaml` não são editados** nesta
  onda; o fechamento do item do `artifact_dir` é reportado, não registrado.

## Non-goals

- Fechar qualquer um dos outros itens abertos de `docs/deferred-work.md` — em
  particular o escopo de `GET /home` por `responsible_user_id`, a CSP sem
  `script-src`, os três índices redundantes e a varredura de media queries do
  CSS. Cada um tem razão escrita para estar aberto.
- Remover `app/domain/synthetic_generation_run.py`. A dataclass não tem nenhum
  construtor no repositório, mas é o modelo de domínio de uma tabela que
  existe, e a camada de domínio espelhar o schema é decisão de arquitetura
  (AD-2), documentada em `docs/data-model.md`. Removê-la é escolha de
  layering, não higiene — fica reportada.
- Remover o campo `metrics` de `app/domain/ml_model_version.py`, pelo mesmo
  motivo: é completude do modelo de domínio, exigida pelo `AGENTS.md`
  §"Versionamento de modelo".
- Remover `app/application/home/errors.py`. A docstring diz que o módulo
  "intentionally defines nothing yet" — e isso continua verdade, então não é
  docstring defasada.
- Acrescentar testes novos. A onda é higiene; a suíte existente é o
  instrumento de verificação, não o objeto da mudança.

## Success signal

`uv run pytest -q` devolve **500 passed** (o mesmo número de antes, não um a
menos), `uv run ruff check .` e `uv run ruff format --check .` passam, e o
diff final contém apenas: cinco símbolos ou parâmetros a menos, cinco
afirmações de docstring corrigidas, uma classe no lugar de duas homônimas — e
nenhuma linha que altere o que um endpoint, um CLI ou o gerador sintético
produzem.

## Assumptions

- O baseline medido neste worktree (500 passed, ruff limpo, format limpo) é o
  estado de `master` em `5201e7d`, não um estado local; os quatro testes de
  `test_synthetic_dataset_split.py` descritos como falhando em
  `docs/deferred-work.md` **passam** hoje, então aquela entrada já está
  desatualizada.
- `le=100` nos três `Query(...)` de `app/presentation/home/router.py` foi
  escrito como duplicata das constantes `MAX_*`, e não como um teto deliberado
  que apenas coincide com elas — inferido da proximidade literal e do fato de
  as constantes `DEFAULT_*` irmãs já serem importadas pelo mesmo router.

## Open questions

- `app/domain/follow_up.py` afirma que `reason`/`next_review_date` "são sempre
  `NULL` nesta story — nenhuma UI os captura ainda". `reason` continua
  `None` em `OpenFollowUpService`, e `next_review_date` é tema de um item
  aberto que não é desta onda (`epic-4-retro-item-19`). A frase é verdadeira
  mas tem escopo histórico ("nesta story"); corrigi-la encostaria num item de
  outra autoridade. Reportada, não alterada.
