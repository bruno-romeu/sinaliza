# Análise das Funções Propostas versus Implementadas

Projeto **Sinaliza — Sistema de Apoio ao Acompanhamento da Trajetória Escolar**
Bruno Romeu da Silva — Tecnologia em Análise e Desenvolvimento de Sistemas, ULBRA

---

## Como ler este documento

A coluna **Função proposta** reúne tudo o que as etapas anteriores previram: o
texto da **Proposta**, os requisitos funcionais e não funcionais do
**Levantamento de Requisitos** e as entidades e campos desenhados na etapa de
**Projeto** (`docs/data-model.md`). A coluna **Requisito** traz a numeração
RF/RNF consolidada em `docs/prd.md`, que renumera
sem reinterpretar o documento aprovado; funções que vieram da etapa de Projeto e
não têm RF próprio estão marcadas como tal.

A coluna **Observação** sempre aponta para **onde a função está no código** e
para **o teste que a prova**. A intenção é que qualquer linha marcada
`Implementada` possa ser conferida abrindo dois arquivos, e não apenas aceita. A
suíte automatizada tem **608 testes no backend** (`pytest`) e **62 no frontend**
(`vitest`), ambos executados a cada alteração pelo CI do repositório.

Onde uma função **não** foi implementada, ou foi implementada apenas em parte, o
item 2 registra o motivo técnico e o que faltaria para concluí-la. Nenhum item
foi marcado `Implementada` apoiado em intenção: o critério usado foi a
existência de código executável e de teste que o exercite.

---

## 1. Funções Propostas versus Implementadas

### 1.1 Autenticação e acesso

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Exigir autenticação (login e senha) para acesso | RF-01, RNF-05 | Implementada | `backend/app/presentation/auth/router.py`; senha com bcrypt em `app/infrastructure/security/bcrypt_hasher.py`. Testes: `tests/test_auth_login.py`; `tests/test_api_exposure_contract.py::test_every_documented_route_except_login_requires_a_bearer_token`. |
| Perfil único de usuário: Coordenação Pedagógica | RF-02 | Implementada | Enum `UserRole` com um único valor `COORDENACAO_PEDAGOGICA` (`app/domain/user.py:17`). Nenhum caminho de código cria um segundo papel. |

### 1.2 Frequência

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Registrar presença ou falta por estudante, data e turma | RF-03 | Implementada | `app/presentation/attendance/router.py`; tela `frontend/src/pages/Lancamento/Presenca.tsx`. Teste: `tests/test_attendance.py`. |
| Impedir duplicidade de registro (estudante, turma, data) | RF-04, RNF-11 | Implementada | Constraint `UNIQUE(student_id, classroom_id, date)` no banco, traduzida em HTTP 409 — não apenas checagem de aplicação. Testes: `tests/test_attendance.py`; `tests/test_repository_integrity_errors.py::test_duplicate_attendance_raises_unique_violation_naming_the_constraint`. |

### 1.3 Notas

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Registrar notas por disciplina e período letivo | RF-05 | Implementada | `app/presentation/grades/router.py`; escala 0–10 fixada com `CHECK` no banco. Testes: `tests/test_grades.py`; `frontend/src/pages/Lancamento/Notas.test.tsx`. |
| Consultar os lançamentos já registrados (notas e entregas) | Decorrente de RF-05 e RF-07 — sem RF próprio | Não implementada | Não existe `GET /grades` nem listagem de `AssignmentSubmission`. **Exclusão deliberada de escopo**, não lacuna acidental — ver 2.1. |
| Disciplina como entidade própria do modelo (`Subject`) | Etapa de Projeto — apontado na avaliação | Não implementada | `Grade.subject` e `Assignment.subject` seguem como `String(255)` (`app/infrastructure/db/models.py:209` e `:235`). Ver 2.2. |

### 1.4 Atividades

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Cadastrar atividades vinculadas a turma, disciplina e período letivo | RF-06 | Implementada | `app/presentation/assignments/router.py`; tela `frontend/src/pages/Lancamento/Atividades.tsx`. Testes: `tests/test_assignments.py`; `Atividades.test.tsx`. |
| Registrar status de entrega por estudante (entregue, não entregue, parcial) | RF-07 | Implementada | Mesmo router; enum fechado `AssignmentSubmissionStatus`. Teste: `tests/test_assignments.py`. |

### 1.5 Registros pedagógicos

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Registrar observações em texto livre sobre um estudante | RF-08 | Implementada | `app/presentation/observations/router.py`; tela `Observacoes.tsx`, que orienta a descrever fato observável em vez de classificar o estudante. Teste: `tests/test_observations.py` (8 casos). |
| Manter referência ao registro original em qualquer sinal derivado | RF-09, RNF-11 | Implementada | `TrajectoryChangeSource` é chave estrangeira real, gravada na mesma transação da mudança — nenhuma `TrajectoryChange` existe sem ao menos uma fonte. Teste: `tests/test_trajectory.py::test_trajectory_two_confirmed_signals_creates_trajectory_change_with_sources`. |
| Extração de sinais do texto por NLP, com revisão humana (`ExtractedSignal`, `SignalReview`) | Etapa de Projeto — previsto como etapa futura em `docs/data-model.md` | Não implementada | Ver 2.3. |

### 1.6 Trajetória

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Calcular indicadores de trajetória em janela de tempo rolante | RF-10 | Implementada | `app/domain/trajectory.py`, exposto por `GET /students/{id}/trajectory` com `window_days` parametrizável. Testes: `tests/test_trajectory_domain.py`; `tests/test_trajectory.py` (18 casos, incluindo bordas de período e determinismo). |
| Detectar mudanças relevantes referenciando os registros que as sustentam | RF-11 | Implementada | `app/domain/convergence.py`, com limiares nomeados e explícitos (`_ATTENDANCE_RATE_THRESHOLD = 0.75`, `_ATTENDANCE_TREND_THRESHOLD = -0.10`, `_GRADE_DROP_BELOW_HABITUAL = 1.0`, `_MISSING_ABOVE_HABITUAL = 2`) e regra de convergência que exige um eixo central. Teste: `tests/test_convergence_domain.py` (27 casos, **incluindo negativos explícitos** — nota baixa porém estável, falta isolada, observação neutra). |
| `TrajectorySnapshot` como tabela persistida | Etapa de Projeto — `docs/data-model.md` | Não implementada (decisão registrada) | O indicador é calculado dentro da própria requisição que o lê (AD-1), nunca por job em segundo plano nem por tabela materializada. Ver 2.4. |

### 1.7 Acompanhamento

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Abrir um acompanhamento para um estudante | RF-12 | Implementada | `app/presentation/follow_ups/router.py`; abertura sempre vinculada a uma evidência. Unicidade de acompanhamento aberto garantida por índice parcial no banco (migration `0017`). Testes: `tests/test_follow_ups.py`; `tests/test_ui_package_1.py`. |
| Registrar ações e alterar o status entre os quatro estados previstos | RF-13 | Implementada | `PATCH /follow-ups/{id}/status` e `POST /follow-ups/{id}/actions`. Testes: `tests/test_follow_ups.py`; `frontend/src/pages/Acompanhamento.test.tsx::'shows a native <select> with exactly the 4 closed status values'`. Não existe estado equivalente a "alto risco". |
| Manter histórico de ações e evidências de cada acompanhamento | RF-14 | Implementada | `FollowUpAction` e `FollowUpEvidence` são somente-inserção (`GRANT INSERT, SELECT` / `REVOKE UPDATE, DELETE`, migration 0014); exibidos em ordem cronológica. Testes: `tests/test_follow_ups.py`; `Acompanhamento.test.tsx::'shows every registered action in chronological order'`. *Defeito de interface conhecido: uma ação recém-registrada só aparece na lista após recarregar a página (`deferred-work` (removido da arvore; ver historico do repositorio)`, item `epic-4-retro-item-16`).* |
| Campos `reason` e `next_review_date` do acompanhamento | Etapa de Projeto — `docs/data-model.md` | Não implementada | Colunas existem e permanecem sempre `NULL`; nenhuma tela as captura. Ver 2.5. |

### 1.8 Privacidade e acesso a registros

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Restringir a visibilidade do registro pedagógico ao responsável pelo acompanhamento e à coordenação | RF-22 | Implementada parcialmente | A **leitura** é escopada: `GET /follow-ups/{id}` devolve 403 a quem não é o responsável, e a checagem vem depois da de inexistência, para o 403 não virar oráculo de existência. Testes: `tests/test_follow_ups.py::test_register_follow_up_action_by_non_responsible_user_returns_403`; `Acompanhamento.test.tsx::'trata 403 como escopo'`. A **listagem** da página inicial ainda não é escopada. Ver 2.6. |
| Política de retenção de dados e registro de acesso aos registros pedagógicos | RNF-12 | Não implementada | Nenhuma tabela de log de acesso e nenhuma rotina de expurgo existem no código (verificado por busca em `backend/app` e `backend/alembic`). Ver 2.7. |

### 1.9 Machine Learning (experimental)

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Gerar, a partir do dataset sintético, um score experimental associado a padrões de evasão | RF-15 | Implementada | `app/ml/train.py` e `app/ml/predict.py`, executados como comando (`python -m app.ml.train`), nunca dentro de requisição HTTP. Testes: `tests/test_ml_train.py`; `tests/test_ml_predict.py`. |
| Tratar o score sempre como dado experimental, nunca como fato ou probabilidade real | RF-16, RF-21, RNF-07 | Implementada | O score é persistido em `MLPrediction` e **não é alcançável por nenhuma rota**. Teste de contrato: `tests/test_api_exposure_contract.py::test_no_route_exposes_an_ml_prediction_score` e `::test_no_response_schema_exposes_the_synthetic_dataset_answer_key`. |
| Versionar o modelo e associar cada predição à sua versão | RF-17 | Implementada | `MLModelVersion` guarda `version`, `artifact_path`, `training_dataset_version`, `feature_schema_version` e `metrics` (JSONB); `MLPrediction` aponta para a versão usada, com FK `RESTRICT` para que apagar a versão não torne o score inauditável. Teste: `tests/test_ml_model_provenance.py` (10 casos). |
| Dois recortes de dataset, sem vazamento de treino nem de futuro | RF-23 | Implementada | `Student.dataset_split` decidido na geração, nunca em tempo de consulta. Testes: `tests/test_synthetic_dataset_split.py`; `tests/test_live_demo_no_future_leakage.py` (inclui recuar o "hoje" da demonstração e verificar que a mudança some). |
| Manter `dataset_split` e `synthetic_profile` fora da entidade `Student` | Etapa de Projeto — apontado na avaliação | Não implementada | Ambos permanecem em `students` (`models.py:106-109`). Há mitigação testada, mas a separação pedida não foi feita. Ver 2.8. |

### 1.10 Interface

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Página inicial com mudanças recentes e acompanhamentos em andamento | RF-18 | Implementada | `frontend/src/pages/Home.tsx`, com paginação em ambas as listas e busca por nome/turma. Testes: `Home.test.tsx` (15 casos); `tests/test_home.py`. |
| Trajetória do estudante, com linha do tempo, evidências e registros | RF-19 | Implementada | `frontend/src/pages/EstudanteTrajetoria.tsx`: gráfico temporal com faixa habitual do próprio estudante, cartão de evidências, linha do tempo de registros e "fator preocupante" recolhido por padrão. Testes: `EstudanteTrajetoria.test.tsx` (11 casos); `src/components/ui/spec-ui-3.test.tsx`. |
| Tela de acompanhamento, com status, ações registradas e evidências vinculadas | RF-20 | Implementada | `frontend/src/pages/Acompanhamento.tsx`. Teste: `Acompanhamento.test.tsx` (17 casos). |
| Nunca exibir ranking por risco, score de evasão ou KPI de "alunos de alto risco" | RF-21 | Implementada | Busca por `ranking`, `score`, `risco` e `percentil` em `frontend/src` não devolve nenhum elemento de interface — apenas comentários que registram a proibição e o texto da tela de observações que **desaconselha** esse vocabulário ao usuário. Garantia complementar no contrato da API (ver RF-16). |

### 1.11 Requisitos não funcionais

| Função proposta | Requisito | Status | Observação |
|---|---|---|---|
| Responder às interações em no máximo 5 segundos | RNF-01 | Implementada | Custo de consulta fixado por teste: `tests/test_repository_query_counts.py::test_get_home_query_count_does_not_grow_with_page_size`. Verificação em ambiente real por `deploy/smoke-test.sh`. *Dívida registrada: `GET /follow-ups/{id}` ainda resolve evidências em N+1 — o N é o número de evidências citadas por uma pessoa, não um parâmetro do cliente (`deferred-work` (removido da arvore; ver historico do repositorio)`).* |
| Interface responsiva, adaptando-se a desktop e tablet | RNF-02 | Implementada | 18 media queries em `frontend/src/styles`; comportamento conferido em 9 larguras durante a onda de frontend. Não há teste automatizado de viewport. |
| Mesmo pipeline de pré-processamento e inferência usado no treinamento | RNF-03 | Implementada | Pipeline único do Scikit-Learn em `app/ml/candidates.py`, serializado e recarregado; `require_matching_feature_schema()` recusa artefato cujo esquema de features divergiu. Testes: `tests/test_ml_model_provenance.py::test_prediction_refuses_an_artifact_fitted_under_another_feature_schema` e `::test_explicit_version_does_not_bypass_the_feature_schema_guard`. |
| Disponibilidade durante desenvolvimento e demonstração | RNF-04 | Implementada | Três contêineres com `restart: unless-stopped` em VM que não hiberna; `deploy/verify-always-on.sh` confere o estado. |
| Acesso protegido por autenticação, com senha armazenada de forma criptografada | RNF-05 | Implementada | bcrypt; limitação de tentativas por janela deslizante em `app/presentation/rate_limit.py` (`tests/test_rate_limit.py`). Teste: `tests/test_api_exposure_contract.py::test_login_response_never_echoes_the_password_or_its_hash`. |
| PostgreSQL, FastAPI, React/Next.js, Scikit-Learn, hospedagem gratuita, sem jobs agendados | RNF-06 | Implementada parcialmente | Pilha tecnológica conforme o proposto; **nenhum job agendado** — trajetória e detecção são calculadas dentro da requisição que as lê (AD-1), e treino/avaliação são comandos disparados por pessoa. A cláusula de **hospedagem gratuita** não foi cumprida: o sistema está numa VM paga da Azure. Ver 2.9. |
| Operar exclusivamente com dados sintéticos | RNF-07 | Implementada | Gerador determinístico com seed (`app/synthetic/`); nenhum dado real em fixtures ou migrations. Testes: `tests/test_synthetic_generation.py`; `tests/test_synthetic_profiles.py`. |
| Acessibilidade com WCAG 2.1 AA como referência | RNF-08 | Implementada parcialmente | Entregue e testado: link de pulo antes de qualquer link do cabeçalho, foco levado ao `<main>`, título de documento por rota, regiões `aria-live` (`src/components/ui/Page.test.tsx`), nenhuma informação comunicada só por cor. As seis razões de contraste do gráfico SVG foram medidas e registradas em comentário no CSS. **A medição com axe-core não está versionada como teste**, logo não protege contra regressão. Ver 2.10. |
| Código em camadas, com testes cobrindo detecção de mudança e pipeline de ML | RNF-09 | Implementada | Camadas `domain` / `application` / `infrastructure` / `presentation` separadas por diretório, com portas explícitas. 608 testes no backend e 62 no frontend; ruff, ESLint, Prettier e `tsc --noEmit` como gate do CI (`.github/workflows/ci.yml`). |
| Funcionar nas versões estáveis de Chrome, Firefox e Edge | RNF-10 | Implementada parcialmente | O E2E do CI roda apenas em Chromium (`frontend/playwright.config.ts`). Ver 2.11. |
| Integridade referencial entre mudança exibida e registros de origem | RNF-11 | Implementada | As 24 chaves estrangeiras do schema foram classificadas com `ondelete` explícito e justificado (migration `0014`), com teste que exercita **cada regra contra um DELETE real**. Testes: `tests/test_repository_integrity_errors.py`; `tests/test_api_exposure_contract.py::test_foreign_key_violation_answers_409_in_the_error_envelope_not_500`. |
| Origem e governança dos dados; geração calibrada por base pública | RNF-13 | Implementada | `app/synthetic/calibration.py`: cada constante do gerador carrega `source`, `confidence` e `kind` como **dado testável**, calibrada pelo **Censo Escolar 2023 (MEC/INEP)**, com SAEB e PNAD Contínua registrados como referência pública e as suposições de projeto declaradas como tais. Teste: `tests/test_synthetic_calibration.py` (29 casos, incluindo um que impede parâmetro só-referência de alimentar o gerador). `SyntheticGenerationRun` persiste seed e versão do gerador. |
| Fronteira do score experimental e método de avaliação do ML | RNF-14 | Implementada | `python -m app.ml.evaluate` imprime e persiste precision, recall, F1 e matriz de confusão com a ressalva anexada ao relatório; `python -m app.ml.compare` reproduz a comparação entre modelos. Testes: `tests/test_ml_evaluate.py` (16 casos); `tests/test_ml_compare.py`. Limites documentados em `docs/model-evaluation.md`. |

### 1.12 Distribuição

| Status | Funções |
|---|---|
| Implementada | 32 |
| Implementada parcialmente | 4 |
| Não implementada | 7 |
| **Total** | **43** |

---

## 2. Justificativa para Funções Não Implementadas

### 2.1 Consulta dos lançamentos já registrados (notas e entregas)

**Motivo técnico.** Esta não é uma lacuna por esquecimento: é uma **exclusão de
escopo escrita antes da implementação**. O documento de intenção congelado das
Stories 1.3 e 1.4 declara explicitamente que as duas entidades são de escrita
apenas — *"there is no read-back/listing endpoint in this MVP, same write-only
shape as attendance/grades"* —, seguindo o mesmo formato que a presença já tinha
adotado na Story 1.2. A razão de desenho é que a Épica 1 existe para **capturar
fatos brutos** que a Épica 3 consome ao calcular a trajetória; o produto não tem,
no MVP, uma tela de "diário de classe" para revisão e correção de lançamentos.

A consequência prática é mais estreita do que parece: notas e entregas **não
são invisíveis** no sistema. Elas aparecem agregadas nos indicadores de
trajetória e, quando sustentam uma mudança detectada, aparecem individualmente
como evidência datada na tela do estudante (`EvidenceItemOut.source_type` aceita
`GRADE` e `ASSIGNMENT_SUBMISSION`). O que não existe é a consulta direta "mostre
todas as notas lançadas nesta turma e disciplina".

**O que seria necessário para concluir.** Acrescentar aos repositórios
`SqlAlchemyGradeRepository` e `SqlAlchemyAssignmentSubmissionRepository` um
método de listagem por turma, disciplina e período (ambos hoje expõem apenas
`save`); um caso de uso de consulta em `app/application/`; dois endpoints
`GET` com paginação, no mesmo formato já usado pela busca da página inicial; e
uma tela de consulta sob `/lancamento`. É trabalho de uma história de tamanho
normal, sem mudança de schema.

### 2.2 Disciplina como entidade própria (`Subject`)

**Motivo técnico.** A avaliação da etapa de Projeto apontou corretamente que a
disciplina aparece como texto em `Grade` e em `Assignment`, e que uma entidade
`Subject` evitaria que a mesma disciplina fosse escrita de formas diferentes. A
observação está certa e **não foi atendida**.

O que a sustentou até aqui foi uma decisão de simplificação registrada em
`docs/data-model.md` ("Sem `Assessment`: simplificado — `subject`/`date`
diretamente em `Grade`"), tomada para reduzir indireção na primeira fatia
vertical. Essa decisão resolvia o caso de `Assessment`, mas foi aplicada por
extensão a `Subject` sem que o risco específico que a avaliação levantou — a
divergência de grafia — fosse enfrentado. Com dados sintéticos o risco não se
materializa, porque o gerador escreve sempre a mesma lista de nomes; ele se
materializaria no momento em que uma pessoa digitasse a disciplina à mão, que é
exatamente o que a tela de lançamento permite hoje.

**O que seria necessário para concluir.** Uma migration criando `subjects`
(`id`, `name` único, `classroom_id` ou escopo equivalente); substituição das
colunas `subject String(255)` de `grades` e `assignments` por `subject_id` com
chave estrangeira `RESTRICT`; backfill das linhas existentes agrupando por nome
normalizado; troca do campo de texto por um `<select>` nas telas de notas e de
atividades; e ajuste dos geradores sintéticos e das fixtures. O custo não é a
migration em si, e sim o backfill e a revisão dos testes que hoje constroem
`Grade` com uma string literal.

### 2.3 Extração de sinais por NLP (`ExtractedSignal`, `SignalReview`)

**Motivo técnico.** O modelo de dados listou as duas entidades explicitamente
como **etapa futura**, fora do rascunho que cobre as Etapas 1 a 3. A decisão de
não construí-las é consistente com o princípio central do projeto: um sinal
extraído automaticamente de texto não pode virar fato confirmado sem revisão
humana, e implementar o fluxo completo exigiria **também** construir a tela de
revisão, o versionamento de provedor/modelo e um conjunto rotulado para medir
precision/recall por categoria — sem o qual a extração seria exatamente aquilo
que o projeto recusa, uma afirmação sem evidência medida.

Nenhum requisito do Levantamento aprovado exige NLP. O registro pedagógico
participa da detecção de mudança por outro caminho, mais honesto e já
implementado: a própria coordenação marca a observação como registrando uma
preocupação (`registers_concern`), e esse sinal entra na convergência com peso
igual aos numéricos, mantendo a autoria humana explícita.

**O que seria necessário para concluir.** Duas tabelas novas
(`extracted_signals` com `source_observation_id`, `signal_type`, `value`,
`provider`, `model`, `review_status`; e `signal_reviews`); um adaptador de
provedor de LLM com saída estruturada validada; uma tela de revisão que
transforme sinal sugerido em confirmado; e um conjunto rotulado versionado com
métricas por categoria. É escopo de uma épica inteira, não de uma história.

### 2.4 `TrajectorySnapshot` como tabela persistida

**Motivo técnico.** Esta é uma função **deliberadamente não implementada**, e a
razão é um requisito: RNF-06 proíbe jobs agendados. Persistir um snapshot só faz
sentido se algo o produzir periodicamente; sem cron, a tabela seria preenchida
pela própria requisição que a leria, e passaria a ser um cache cuja invalidação
nada garante. A decisão arquitetural AD-1 fixou o oposto: o indicador é
**calculado dentro da requisição que lê a trajetória**, e apenas a `TrajectoryChange`
— que precisa de identidade estável para ser citada como evidência de um
acompanhamento — é persistida, por upsert com chave natural
`(student_id, type, period_id)`, congelado assim que uma `FollowUpEvidence`
passa a citá-lo.

Essa resposta também é o que o sistema tem a dizer à pergunta *"quem ou o que
detecta uma mudança de trajetória?"*: nada em segundo plano. A detecção acontece
no momento em que alguém abre a trajetória, e o congelamento está provado em
`tests/test_follow_ups.py::test_recompute_after_follow_up_evidence_exists_keeps_change_frozen`.

**O que seria necessário para concluir**, caso se decidisse persistir: uma
tabela `trajectory_snapshots` com `snapshot_date` e `window_days` como parte da
chave, um disparador de recálculo (job agendado, o que exigiria revisar RNF-06,
ou gravação oportunista na leitura) e uma política de invalidação quando um fato
anterior for corrigido. O custo real é a invalidação, não a tabela.

### 2.5 Campos `reason` e `next_review_date` do acompanhamento

**Motivo técnico.** As duas colunas foram desenhadas na etapa de Projeto e
criadas no banco, mas permanecem sempre `NULL`: nenhuma tela as captura e nenhuma
consulta as lê. O motivo é que a abertura do acompanhamento no MVP é
**sempre vinculada a uma evidência concreta** — a `TrajectoryChange` citada —, e
um campo `reason` em texto livre ao lado dessa evidência convidaria a registrar
a justificativa como opinião solta em vez de apontar o dado-fonte, que é o
princípio do produto. `next_review_date` dependeria de alguma forma de lembrete,
e lembrete sem job agendado (RNF-06) só funcionaria como coluna ordenada numa
listagem, funcionalidade que não foi pedida.

Vale registrar que a documentação da Épica 4 chegou a afirmar que
`next_review_date` era lido por uma consulta da página inicial; isso **nunca foi
verdade**, e a correção está registrada em `deferred-work` (removido da arvore; ver historico do repositorio)`
(`epic-4-retro-item-19`).

**O que seria necessário para concluir.** Para `reason`: um campo opcional no
formulário de abertura e sua exibição na tela do acompanhamento — pequeno, mas
depende de decidir antes se o campo não enfraquece a disciplina de evidência.
Para `next_review_date`: um seletor de data na abertura, ordenação por data na
listagem de acompanhamentos em andamento e um destaque visual para os vencidos,
sem notificação ativa.

### 2.6 Escopo de acesso na listagem da página inicial (RF-22 parcial)

**Motivo técnico.** A metade do requisito que protege o conteúdo sensível está
implementada: o texto de uma observação pedagógica citada como evidência só é
legível por quem responde pelo acompanhamento, e um terceiro recebe 403. O que
não está escopado é a **listagem**: `GET /home` chama
`FollowUpRepository.list_active`, cujo `select` filtra apenas por
`status != ENCERRADO`, sem cláusula sobre `responsible_user_id`. Com dois ou mais
usuários, a página inicial exibiria cartões de acompanhamentos alheios que
responderiam 403 ao serem abertos.

A razão de não ter sido corrigido é que **não é um defeito, é uma decisão de
produto ainda não tomada**. Ou a coordenação enxerga todos os acompanhamentos da
escola — e então é o 403 da leitura que está errado para o papel
`COORDENACAO_PEDAGOGICA` —, ou cada responsável enxerga os seus — e então a
listagem precisa do mesmo filtro. Escolher no código sem decidir no produto
esconderia a pergunta em vez de respondê-la. Hoje a inconsistência é
inalcançável: existe um único usuário semeado, e o cartão da página inicial
carrega nome do estudante e status, nunca o texto da observação.

**O que seria necessário para concluir.** Registrar a decisão de produto em
`docs/decisions/`; se a escolha for "cada responsável vê os seus", acrescentar
`where(FollowUpModel.responsible_user_id == requesting_user_id)` em
`list_active` e um teste com dois usuários semeados; se for "a coordenação vê
tudo", relaxar o 403 da leitura para o mesmo papel e ajustar o teste
correspondente. Em ambos os casos é alteração pequena — o que falta é a decisão,
não o código.

### 2.7 Retenção de dados e registro de acesso (RNF-12)

**Motivo técnico.** RNF-12 foi escrito como **requisito documentado**, não como
funcionalidade a construir, e o PRD classificou o log de acesso explicitamente
como *Should* fora do escopo do MVP. A parte do requisito que virou código foi
RF-22 (restrição de visibilidade). A parte que permaneceu apenas em texto —
política de retenção e trilha de acesso — não tem nenhuma linha de código:
busca por `access_log`, `audit`, `retention` e `purge` em `backend/app` e
`backend/alembic` não encontra nada além de comentários sobre valor de
auditoria das entidades de acompanhamento.

É justo dizer que esta é a lacuna mais relevante da entrega do ponto de vista de
privacidade, e o argumento de que o banco é 100% fictício a atenua sem a
eliminar: o que se demonstra num TCC é o desenho, e um desenho que registra quem
leu o registro pedagógico de um estudante é materialmente diferente de um que
não registra. O que a implementação **tem** hoje é a precondição desse log: todo
acesso já passa por um usuário autenticado identificado, e o ponto de leitura
sensível é único e nomeado (`GetFollowUpService`), de modo que não haveria que
instrumentar dezenas de caminhos.

**O que seria necessário para concluir.** Para o log: uma tabela
`pedagogical_record_access_log` (`id`, `user_id`, `student_id`,
`observation_id`, `accessed_at`, `context`), somente-inserção pelo mesmo
mecanismo de `GRANT`/`REVOKE` já usado em `follow_up_actions`, escrita dentro de
`GetFollowUpService` e do detalhe de trajetória, com teste afirmando que uma
leitura bem-sucedida grava exatamente uma linha e que um 403 **não** grava. Para
a retenção: uma decisão registrada definindo prazo por tipo de dado, um comando
de expurgo (não um job, por RNF-06) e um teste sobre uma base com datas
forjadas. O log é trabalho de uma história; a retenção exige a decisão antes do
código.

### 2.8 `dataset_split` e `synthetic_profile` dentro de `Student`

**Motivo técnico.** A avaliação da etapa de Projeto apontou que os dois campos
são informação do experimento de ML misturada aos dados do estudante, e que
separá-los permitiria que o sistema funcionasse também com dados reais sem esses
campos. Os dois **continuam em `students`** (`models.py:106-109`).

A decisão em contrário está registrada em `docs/data-model.md` e tem um
argumento técnico concreto: a avaliação do modelo precisa comparar, estudante a
estudante, o desfecho conhecido com o que o pipeline produziu, e um JOIN a mais
em toda validação não pagaria o isolamento que compraria. Em troca, o projeto
impôs ao rótulo a mesma fronteira que impõe ao score de ML — ele **nunca sai na
API** —, e essa troca não ficou como promessa: está provada por três testes de
contrato (`tests/test_api_exposure_contract.py::test_no_response_schema_exposes_the_synthetic_dataset_answer_key`,
`::test_trajectory_routes_never_return_synthetic_profile_for_a_labelled_student`
e `::test_student_search_never_returns_a_train_split_student`).

Ou seja: o risco de **vazamento do gabarito** foi fechado; o que a separação
pedida fecharia e esta solução não fecha é o risco de **modelagem** — a entidade
`Student` do domínio continua carregando dois campos que só existem porque o
dataset é sintético, e portanto o modelo de dados, lido isoladamente, não
sustenta a afirmação de que o sistema operaria sem alteração sobre dados reais.
Reconhecer isso é mais exato do que afirmar que a mitigação tornou o apontamento
improcedente.

**O que seria necessário para concluir.** Uma tabela `student_experiment_labels`
(`student_id` como chave primária e estrangeira, `dataset_split`,
`synthetic_profile`, `generation_run_id`), com remoção das duas colunas de
`students`; ajuste de `TrainingRepository`, `EvaluationRepository` e dos filtros
de visibilidade do recorte de treino, que hoje leem o campo direto de `students`;
e migration com backfill. A dificuldade está nos filtros: a exclusão do recorte
de treino hoje é uma cláusula simples em várias consultas de produto, e passaria
a exigir um JOIN em cada uma — razão pela qual os testes de contrato acima
precisariam ser mantidos intactos como rede de segurança da própria migração.

### 2.9 Hospedagem em serviço gratuito (RNF-06 parcial)

**Motivo técnico.** RNF-06 prevê hospedagem em serviço gratuito. O sistema está
publicado numa **VM paga da Azure** (`deploy/azure/README.md`), e o runbook
declara o custo abertamente. O desvio tem duas causas encadeadas, ambas
documentadas no momento em que ocorreram:

1. O Plano A/B da Épica 6 era a camada *Always Free* da Oracle Cloud. Ela **não
   tinha capacidade** na região do Brasil, e o runbook de provisionamento
   registra a tentativa e a falha.
2. O Plano C — PaaS gratuito (Render, Neon, Vercel) — está documentado em
   `deploy/plan-c-contingency-runbook.md` e foi descartado por **conflito com
   outro requisito**: serviço gratuito hiberna por inatividade, e a primeira
   requisição depois da hibernação paga uma penalidade que pode ultrapassar os
   5 segundos de RNF-01. Como a aplicação será aberta por um avaliador em
   horário que não controlamos, "lento ao acordar" é indistinguível de
   "quebrado".

A escolha foi, portanto, entre descumprir a cláusula de gratuidade de RNF-06 e
descumprir RNF-01 no exato momento da avaliação. Optou-se pela primeira, com a
contrapartida de que o custo é visível e controlado (`deploy/azure/power.sh` para
desalocar fora do período de avaliação, e alerta de orçamento recomendado no
runbook). O restante de RNF-06 é cumprido integralmente: PostgreSQL, FastAPI,
React, Scikit-Learn e **nenhum job agendado**.

**O que seria necessário para concluir.** Reinstalar a stack sobre uma camada
sempre-gratuita que não hiberne — na prática, aguardar capacidade *Always Free*
da Oracle na região e reexecutar `deploy/vm-provisioning-runbook.md`, que já está
escrito e é independente de provedor a partir do passo de bootstrap do Docker. A
alternativa (Plano C) só seria aceitável se RNF-01 fosse reescrito para excluir a
primeira requisição após inatividade.

### 2.10 Acessibilidade: medição não versionada (RNF-08 parcial)

**Motivo técnico.** O conteúdo de RNF-08 foi entregue e é testado: link de pulo
posicionado antes de qualquer link do cabeçalho, foco conduzido ao `<main>` sem
criar uma parada extra na tabulação, título de documento próprio por rota
(WCAG 2.4.2), contagem de resultados anunciada por `aria-live`, formulários com
rótulos associados e nenhuma informação de mudança comunicada apenas por cor. As
razões de contraste dos rótulos dentro do `<svg>` do gráfico — o único ponto que
o axe-core não consegue avaliar — foram medidas manualmente nos dois temas, e a
pior delas, 5,68:1, passa o limiar severo de 4,5:1; os números estão registrados
em comentário no próprio CSS, com o gatilho para refazer a medição caso as
variáveis de cor mudem.

O que **não** existe é a execução do axe-core como teste versionado. A varredura
que apurou "0 violações de AA" nos dois temas foi feita uma vez, com axe-core
4.10.2, contra um build do `master`, e o resultado foi registrado em documento —
mas `axe-core` não é dependência do `package.json` e nenhum arquivo de teste o
invoca. Em consequência, a afirmação de conformidade é **verdadeira na data em
que foi medida e desprotegida contra regressão**: uma alteração de cor ou de
marcação amanhã não seria barrada por nada.

**O que seria necessário para concluir.** Acrescentar `@axe-core/playwright` às
dependências de desenvolvimento do frontend e um arquivo de teste E2E que
percorra as três telas principais nos dois temas, falhando em qualquer violação
de nível AA; e incluir esse teste no job de E2E do CI, que já sobe a stack
completa. É trabalho pequeno, e o valor está menos na primeira execução — cujo
resultado já é conhecido — do que em tornar o resultado permanente.

### 2.11 Compatibilidade entre navegadores (RNF-10 parcial)

**Motivo técnico.** RNF-10 pede funcionamento nas versões estáveis de Chrome,
Firefox e Edge. O `frontend/playwright.config.ts` declara **um único projeto,
`chromium`**, e é esse o navegador que o job de E2E do CI exercita. Edge usa o
mesmo motor (Blink), então está coberto na prática pelo que importa em
renderização e API de plataforma; **Firefox (Gecko) não está coberto por nenhuma
verificação automatizada**.

A justificativa da escolha original foi de custo de execução: a stack completa
sobe em contêiner a cada execução do CI, e multiplicar os navegadores
multiplicaria esse tempo. Em um projeto sem CSS experimental e construído sobre
React com folhas de estilo convencionais, a probabilidade de divergência entre
Blink e Gecko é baixa — mas "baixa" não é o mesmo que "verificada", e o
requisito nomeia Firefox.

**O que seria necessário para concluir.** Acrescentar um projeto `firefox` à
lista `projects` do `playwright.config.ts` e instalar o navegador correspondente
no passo de E2E do CI (`npx playwright install --with-deps firefox`). São duas
linhas de configuração; o custo real é o tempo adicional de execução da suíte
E2E, que hoje já é o job mais longo do pipeline.

---

## 3. Observações complementares

Alguns pontos levantados nas avaliações anteriores não apenas foram atendidos
como geraram artefatos verificáveis, e cabe registrá-los junto da tabela porque
explicam escolhas que de outra forma pareceriam arbitrárias:

- **Método de geração do dataset, calibrado por base pública.** Além de
  documentado, o método virou dado executável: cada constante do gerador em
  `backend/app/synthetic/calibration.py` carrega `source`, `confidence` e `kind`,
  calibrada pelo Censo Escolar 2023 (MEC/INEP), e um teste impede que um
  parâmetro classificado como mera referência pública alimente a geração. As
  suposições de projeto estão declaradas como tais, com a razão pela qual não há
  fonte pública — notas, por exemplo, não são coletadas pelo Censo.

- **Limiares de detecção explícitos.** Estão nomeados em
  `backend/app/domain/convergence.py` e são os quatro citados na linha de RF-11,
  com a regra de convergência exigindo um eixo central como proteção contra
  ruído — um sinal isolado não produz mudança, apenas um "fator preocupante"
  silencioso na trajetória do estudante.

- **Casos de teste com trajetórias conhecidas, incluindo os que não devem gerar
  sinal.** `tests/test_convergence_domain.py` tem negativos explícitos: nota
  baixa porém estável, contagem de atividades que o estudante sempre teve,
  observação neutra, e convergência com exatamente um sinal confirmado.

- **Os quatro NFRs acrescentados viraram código verificável**, e não parágrafos:
  integridade como 24 chaves estrangeiras classificadas e testadas contra DELETE
  real; manutenibilidade como separação por camadas com 670 testes somados e
  gate de lint no CI; acessibilidade e compatibilidade com as ressalvas
  registradas em 2.10 e 2.11.

- **Quem detecta a mudança.** Ninguém em segundo plano: a detecção acontece
  dentro da requisição que lê a trajetória (AD-1), e a mudança é congelada assim
  que passa a ser citada como evidência de um acompanhamento, para que o
  histórico humano não seja reescrito por um recálculo posterior.
