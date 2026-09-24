# Architecture Spine Review — Sinaliza (2026-09-17)

**Documento revisado:** `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md`
**Revisado contra:** `docs/prds/prd-sinaliza-2026-09-16/prd.md`, `docs/data-model.md`, `AGENTS.md`
**Data da revisão:** 2026-09-17
**Papel do revisor:** revisão de spine de arquitetura (altitude "contrato de consistência para o nível abaixo" — épicos/histórias/implementação), não uma revisão de design completa.

> Nota: já existia um `review-rubric.md` neste diretório, escrito contra uma versão anterior da spine (numeração de AD diferente — ex.: "AD-4" era dataset split, hoje é pipeline de ML). Grande parte do que aquele review apontava já foi corrigido na versão atual (constraint de duplicidade de presença, `PedagogicalObservation` definida em `data-model.md`, desvio Next.js→Vite sinalizado em Deferred). Este documento substitui aquele e reavalia a spine **como ela está agora**, incluindo um efeito colateral da correção: os números de AD citados em `docs/data-model.md` ficaram dessincronizados da spine atual (achado #2 abaixo).

## Veredito

A spine é estruturalmente sólida — a lógica de "Prevents" por AD é incomumente explícita, os dois `[NOTE FOR PM]` do PRD foram resolvidos, o mapeamento de capacidades cobre 100% dos RF, e o Deferred está bem delimitado na maioria dos itens. Mas ela tem uma contradição interna de schema (tipo de dado de uma FK), uma dessincronia factual com seu próprio documento-irmão (`data-model.md`) causada por uma renumeração de AD não propagada, uma lacuna de cobertura em RF-04/RNF-11 (nenhum AD garante a constraint de duplicidade que `data-model.md` já implementa citando um AD errado), e um ponto cego operacional (deploy/backup/monitoramento) que nem foi decidido nem declarado Deferred. Nenhum desses problemas exige redesenho — são todos correções de uma ou poucas frases — mas são exatamente o tipo de coisa que faria um segundo implementador (ou o próprio autor, em outra sessão) divergir de forma incompatível.

## Resumo dos achados

| # | Achado | Severidade | Item do checklist |
|---|---|---|---|
| 1 | `AD-7` define `trajectory_change_sources.source_id` como `BIGINT`, mas a Consistency Conventions da mesma spine fixa `IDs = UUID v4` para todo o sistema — uma FK que não pode fisicamente apontar para as tabelas-fonte (`AttendanceRecord.id` etc., todas UUID) | **Alta** | #2 |
| 2 | `docs/data-model.md` cita "arquitetura, AD-4" para dataset split e "AD-7"/"AD-11" para duplicidade de presença e `PedagogicalObservation` — nenhuma dessas citações corresponde ao conteúdo real dos ADs de mesmo número na spine atual (AD-4 hoje é pipeline de ML; AD-11 não existe) | **Alta** | #5, #7 |
| 3 | `source_type` do join table diverge entre os dois documentos: `AD-7` usa `'ATTENDANCE'`; `data-model.md` usa `ATTENDANCE_RECORD` | **Alta** | #5 |
| 4 | Nenhum AD garante, no corpo da spine, a constraint de banco `UNIQUE(student_id, classroom_id, date)` que RF-04+RNF-11 exigem — `data-model.md` já a implementa, mas atribuindo a decisão a um AD (AD-7) que não fala sobre isso | **Média** | #1, #6 |
| 5 | Título do AD-7 promete integridade "em nível de schema, não só de aplicação", mas a regra descrita ("a aplicação insere... na mesma transação atômica, validando...") é garantia transacional/de aplicação, não uma constraint de schema (Postgres não expressa "≥1 filho obrigatório" sem trigger/constraint diferida, nenhuma das duas é mencionada) | **Média** | #2 |
| 6 | O item Deferred de cache/materialização da home não reafirma que qualquer solução futura continua proibida de usar job agendado — a saída "óbvia" de engenharia (materialização com refresh em cron) violaria diretamente RNF-06/AD-2, a regra mais repetida do projeto | **Média** | #3 |
| 7 | Front-matter declara `binds: RNF-01..RNF-14`, mas RNF-02, RNF-07, RNF-08 e RNF-10 têm zero menções no corpo da spine (nem AD, nem Capability Map, nem Deferred) | **Média** | #5, #6, #7 |
| 8 | Versionamento de modelo de ML: só `model_version` é mencionado; `training_dataset_version`, `feature_schema_version`, `metrics`, `artifact_path` (mandato explícito de AGENTS.md) não são decididos nem declarados Deferred | **Média** | #7 |
| 9 | Dimensão operacional (processo de deploy, backup/restore do único Postgres, monitoramento) não está decidida nem no Deferred — silêncio total | **Média** | #7 |
| 10 | `AD-8` filtra visibilidade só por `responsible_user_id = current_user.id`; a leitura literal de RF-22 ("...ao usuário responsável **e à** coordenação pedagógica") é ambígua sobre se qualquer coordenador deveria ver o registro — a spine resolve na direção mais restritiva sem declarar que essa é uma escolha interpretativa | **Baixa-Média** | #2 |
| 11 | Tabela de Stack fixa versões de patch/minor exatas (`0.141.x`, `18.6`, `19.3.x`) para uma data ~2 meses antes da entrega, sem o mesmo selo `[ASSUMPTION]` usado em outras suposições da spine, apesar de igualmente especulativas | **Baixa** | #4 |
| 12 | `data-model.md` (`TrajectoryChange.type`, marcado como rascunho sujeito a revisão) usa uma taxonomia de 4 valores diferente da de `AD-3` (inclui `COMBINED_DETERIORATION` em vez de um tipo para `pedagogical_observation_present`) — não é contradição fechada porque o próprio arquivo se declara tentativo, mas a spine não cruza essa referência | **Baixa** | #5 |
| 13 | Contrato de interface do `SignalEvaluator`/`ConvergenceRule` (o que um evaluator retorna, como se compõe) não é fixado nem declarado Deferred — só o valor do limiar é explicitamente adiado | **Baixa** | #1, #3 |

---

## 1. Pontos de divergência real fixados — e o que falta

A spine acerta os divergence points mais óbvios: enum fechado de status, evidência como FK real, split de dataset decidido na geração (não em query time), truncagem `as_of()` centralizada, hospedagem de VM única sem scale-to-zero. Dois pontos que dois builders (ou o mesmo autor em duas sessões) ainda divergiriam:

- **Constraint de duplicidade de presença (RF-04 + RNF-11).** RNF-11 exige explicitamente que a duplicidade "continue impedida em nível de banco... não apenas na camada de aplicação". Nenhum AD da spine atual declara essa constraint — nem AD-10 (que cobre a forma de dado de `AttendanceRecord`, mas só a distinção justificada/não justificada, não a unicidade), nem AD-7 (integridade de evidência, tema diferente). `data-model.md` já resolveu isso (`UNIQUE(student_id, classroom_id, date)`), mas atribui a decisão a "arquitetura, AD-7" — um AD que, na spine atual, não fala sobre isso. Um segundo builder lendo só a spine (sem notar a nota lateral de `data-model.md`) não teria de onde tirar essa exigência. **(Média)**

- **Contrato de interface de detecção de sinal.** O Design Paradigm nomeia "Pipeline pattern" para dois pontos: detecção de sinal e pré-processamento+ML. AD-4 fixa completamente o ponto de ML (artefato único, singleton, CLI offline). Para detecção de sinal, AD-3 fixa a contagem/threshold estrutural (exatamente 4 categorias, ≥2 disparam no mesmo `AcademicPeriod`) mas não fixa o contrato do `SignalEvaluator` (retorna bool? enum de severidade? como o `ConvergenceRule` compõe múltiplos evaluators?). É legítimo adiar o valor do limiar (o PRD já marca isso como `[ASSUMPTION]`); não há o mesmo tratamento explícito para a forma da interface — ela simplesmente não aparece em lugar nenhum, nem decidida nem em Deferred. Dado que a contagem/threshold já está bem especificada, esse é um risco menor do que pareceria à primeira vista, mas ainda vale uma frase. **(Baixa-Média)**

## 2. Enforceability — a Rule de cada AD realmente impede o que promete?

A maioria dos ADs é sólida (enum nativo do Postgres em AD-6, decisão de VM única em AD-9, forma de dado em AD-10). Três problemas concretos:

- **AD-7 — contradição de tipo de dado com a própria spine.** A Rule define `trajectory_change_sources(..., source_id BIGINT)`. Mas a linha de Consistency Conventions da mesma spine fixa `IDs = UUID v4` como convenção universal — as tabelas-fonte referenciadas por `source_id` (`AttendanceRecord`, `Grade`, `AssignmentSubmission`, `PedagogicalObservation`) teriam, portanto, PKs `UUID`. Uma coluna `BIGINT` não pode ser FK de uma PK `UUID`; um implementador seguindo a Rule ao pé da letra criaria uma tabela cujo schema não fecha, e teria de decidir sozinho — sem orientação da spine — se o certo é corrigir `source_id` para `UUID` ou reabrir a convenção de IDs. Esse é exatamente o tipo de "regra plausível na leitura, mas inconsistente na implementação" que o checklist pede para caçar. **(Alta)**

- **AD-7 — o título promete mais do que a Rule garante.** O nome do AD é "Integridade de evidência garantida em nível de schema, não só de aplicação". A Rule descrita, porém, é: a aplicação insere `TrajectoryChange` + suas `trajectory_change_sources` "na mesma transação atômica, validando que cada `source_id` existe... antes do commit". Isso é disciplina de aplicação/transação — não uma constraint de schema. Postgres não tem uma forma nativa de expressar "esta linha-pai deve ter ao menos uma linha-filha" sem um trigger ou uma constraint diferida (nenhum dos dois é mencionado). A metade "FK NOT NULL em `FollowUpEvidence.trajectory_change_id`" é, sim, verdadeiramente schema-enforced; a metade "nunca menos de 1 fonte por mudança" não é. Um implementador adversarial-mas-complacente poderia (por engano ou pressa) inserir a `TrajectoryChange` numa transação e as fontes em outra chamada separada, violando a intenção sem violar nenhuma constraint de banco de fato existente. **(Média)**

- **AD-4/AD-5/AD-8 — mecanismo de enforcement é "todo mundo lembra de filtrar".** Split de dataset (AD-5) e escopo de visibilidade (AD-8) dependem de cada query/repositório aplicar o filtro manualmente; nenhum AD manda centralizar isso num único método de repositório, view ou política equivalente a RLS. Para um autor solo ao longo de ~8 semanas de build, um endpoint esquecido reabre exatamente o vazamento que o AD existe para prevenir — a Rule declara a intenção, mas não impede mecanicamente o esquecimento. Vale uma frase do tipo "o filtro vive em um único método de repositório por entidade, nunca inline por endpoint".

- **AD-8 — leitura mais restritiva que o texto literal de RF-22.** RF-22 pede visibilidade restrita "ao usuário responsável **e à** coordenação pedagógica" — uma leitura possível é que qualquer usuário com o papel coordenação pedagógica (não só o responsável) devesse ver o registro, já que hoje só existe esse papel. AD-8 implementa apenas `FollowUp.responsible_user_id = current_user.id`, isto é, restringe entre contas individuais mesmo que todas compartilhem o mesmo `role`. Isso é uma escolha defensável (e a nota de RF-22 sobre ser "estrutural, não uma barreira entre papéis" sugere que a intenção era sobre papéis, não sobre contas individuais) — mas a spine não registra que essa ambiguidade existe nem por que resolveu na direção mais restritiva. **(Baixa-Média)**

## 3. Deferred — algo aí poderia gerar divergência incompatível?

Sete dos oito itens são bem delimitados (cada um diz por que é seguro adiar e o que continua valendo se for construído depois). Um item é uma exceção real:

- **Cache/materialização do fan-out da home.** O texto diz "só otimizar se uma medição real... mostrar risco" — mas não repete a restrição que motiva o resto da spine: **qualquer** solução futura continua proibida de usar job agendado (RNF-06, e a própria razão de AD-2/AD-9 existirem). A saída de engenharia mais óbvia para "cache que não pode recomputar a cada request" é uma materialized view com refresh em cron — que violaria diretamente a regra mais repetida do projeto (aparece em AGENTS.md, RNF-06, AD-2 e AD-9). Sem essa frase, dois builders futuros (ou o autor em duas sessões distantes) poderiam divergir de forma incompatível com o próprio projeto. **(Média)**

Os demais itens (limiares numéricos, tela de score, log de acesso, DNS, capacidade Ampere A1, correção de `data-model.md`, Next.js vs. React) estão corretamente delimitados — cada um amarra a forma já decidida e só adia o valor/decisão operacional secundária.

## 4. Plausibilidade de stack/tecnologia

Nenhuma escolha lê como um chute infundado — Python 3.13, FastAPI 0.14x, PostgreSQL 18, React 19, Node 22 LTS, Vite 8 são todos consistentes com as trajetórias reais dessas ferramentas (mesmo que alguns pudessem já estar uma versão minor à frente na data real de implementação). O único ponto fraco: a tabela de Stack fixa patches exatos (`0.141.x`, `18.6`, `19.3.x`) sem o mesmo selo `[ASSUMPTION]` que a spine usa em outros lugares para decisões igualmente especulativas (ex.: "IDs = UUID v4 `[ASSUMPTION]`"). Para um documento datado ~2 meses antes da entrega final, pinos de patch tão exatos são inerentemente uma aposta — vale marcar a tabela inteira como "versão estável mais recente no momento da implementação; ajustar conforme disponibilidade" em vez de apresentá-los como fato fixo. **(Baixa)**

## 5. Ratifica ou corrige `docs/data-model.md`?

Onde a spine ratifica o rascunho, ratifica corretamente: `TrajectoryChangeSource` como FK real, `dataset_split` na geração (não em query time), enum fechado de `FollowUp.status`, `Grade.value` em escala 0–10, `AttendanceRecord.status` com justificada/não justificada. Onde deveria corrigir, a correção existe em texto (Consistency Conventions, "Correção sinalizada") — mas essa correção já está **desatualizada em relação ao próprio arquivo**: `data-model.md` já mostra `role: COORDENACAO_PEDAGOGICA` (valor único), não mais `PROFESSOR | COORDENACAO`. O Deferred item #7 da spine ("`docs/data-model.md` desatualizado") também descreve um estado que já não existe no arquivo.

O problema maior não é que a correção ficou obsoleta — é *por que* ela ficou obsoleta: `data-model.md` foi atualizado citando números de AD (`AD-1, AD-4, AD-7, AD-10, AD-11`) que **não correspondem ao conteúdo da spine atual**:

- "Split de dataset... (arquitetura, **AD-4**)" — na spine atual, AD-4 é o pipeline de ML como artefato único; split de dataset é **AD-5**.
- "`PedagogicalObservation` trazida para o MVP... (arquitetura, AD-8/**AD-11**)" — **AD-11 não existe** na spine atual (ela vai até AD-10).
- "Duplicidade de presença em nível de banco... (arquitetura, **AD-7**)" — AD-7 atual é sobre integridade de `TrajectoryChangeSource`, não sobre `AttendanceRecord`.

Isso é forte evidência de que a spine passou por uma renumeração de ADs depois que `data-model.md` foi atualizado contra uma versão anterior, e a sincronização não foi refeita. Um implementador que confie nas citações de `data-model.md` para entender "por que este campo é assim" vai abrir o AD errado. **(Alta)**

Além da numeração, há uma divergência literal de valor de enum entre os dois documentos: `AD-7` define `source_type ENUM('ATTENDANCE', 'GRADE', 'ASSIGNMENT_SUBMISSION', 'PEDAGOGICAL_OBSERVATION')`; `data-model.md` define `source_type: ATTENDANCE_RECORD | GRADE | ASSIGNMENT_SUBMISSION | PEDAGOGICAL_OBSERVATION`. `ATTENDANCE` ≠ `ATTENDANCE_RECORD`. Dois builders implementando a partir de cada documento respectivamente produziriam migrations incompatíveis. **(Alta)**

Um último ponto, de severidade menor porque o próprio `data-model.md` já se declara tentativo: o enum `TrajectoryChange.type` do rascunho (`ATTENDANCE_DROP | GRADE_DROP | MISSING_ASSIGNMENTS_INCREASE | COMBINED_DETERIORATION`) não mapeia 1:1 para as 4 categorias de sinal de AD-3 (que incluem `pedagogical_observation_present`, ausente do enum, e não incluem um tipo "combinado"). Vale uma frase de reconciliação quando a spine for revisada. **(Baixa)**

## 6. Capability → Architecture Map cobre o PRD?

Todas as 10 áreas funcionais (§4.1–§4.10) têm linha, e todos os RF-01 a RF-23 aparecem em algum lugar do mapa ou dos Binds — cobertura de RF é completa.

RNF é onde a cobertura falha parcialmente: de RNF-01 a RNF-14, apenas RNF-02, RNF-07, RNF-08 e RNF-10 têm zero menção em qualquer AD, na Capability Map ou no Deferred (RNF-01, 03, 04, 05, 06, 09, 11, 12, 13, 14 estão todos referenciados em algum Binds ou trecho de prosa). Isso é uma melhora real frente a uma revisão anterior desta mesma spine (que apontava 6 RNFs órfãos) — mas o front-matter ainda declara `binds: ['RF-01..RF-23', 'RNF-01..RNF-14']` como se a cobertura fosse total. RNF-02 (usabilidade responsiva), RNF-08 (acessibilidade) e RNF-10 (compatibilidade de navegador) são plausivelmente delegáveis a `DESIGN.md`/`EXPERIENCE.md` — a própria spine já faz esse gesto para as RF de interface ("governam forma/comportamento; esta spine não repete") — mas o mesmo pointer não existe explicitamente para essas três RNFs. RNF-07 (dados exclusivamente sintéticos) tem a intenção honrada em substância por AD-4/AD-5/RNF-13, mesmo sem citação literal do número. **(Média)**

## 7. Dimensões estruturais desta altitude — decididas, adiadas com razão, ou silenciosas?

- **Paradigma e fronteiras de camada:** decididos, com diagrama e regra de dependência explícita. Bom.
- **Integridade de dados:** majoritariamente decidida (enums nativos, FK real, transação atômica) — mas com a contradição de tipo (achado #1) e o exagero de enforcement (achado #5) já descritos acima.
- **Versionamento de pipeline de ML:** parcialmente decidido. AD-4 fixa "artefato único, treinado offline, carregado uma vez" com bastante força — mas só menciona `model_version` entre os campos que AGENTS.md manda persistir (`model_version`, `training_dataset_version`, `feature_schema_version`, `metrics`, `artifact_path`, `created_at`). Os demais campos não aparecem nem decididos nem em Deferred — e o schema de `MLModelVersion`/`MLPrediction` está explicitamente fora do rascunho atual de `data-model.md` ("Etapa 4"). Isso é silêncio, não decisão adiada com razão. **(Média)**
- **Deploy/hospedagem/ambientes:** a topologia está muito bem decidida (AD-9: VM única, 3 containers, sem scale-to-zero) e o ambiente único (produção=demo, dev espelha via docker-compose) está declarado em prosa. Mas processo de deploy (como o código sai da máquina do autor para a VM — `git pull` manual? script SSH? CI?), backup/restore do único Postgres (não há banco gerenciado de segurança), e monitoramento/observação de saúde da VM antes de uma demonstração ao vivo **não aparecem nem como decisão nem como item de Deferred** — silêncio total numa dimensão que a spine deveria pelo menos reconhecer e adiar explicitamente (mesmo que a resposta seja "fora de escopo para o TCC"). Dado que há um prazo rígido (23/11/2026) e nenhuma rede de segurança de banco gerenciado, isso é um risco real de projeto, não só de documentação. **(Média)**
- **Operações (observabilidade/alertas):** mesmo ponto acima — silêncio.

---

## Correções recomendadas (ordem de prioridade)

1. Corrigir `AD-7`: `source_id` de `trajectory_change_sources` deve ser `UUID`, não `BIGINT` (ou documentar explicitamente uma exceção à convenção `IDs = UUID v4`, com justificativa).
2. Resincronizar as citações de AD em `docs/data-model.md` com a numeração atual da spine (dataset split → AD-5, não AD-4; duplicidade de presença → precisa de um AD novo ou extensão de AD-10, não AD-7; `PedagogicalObservation` → não existe AD-11) e atualizar/remover o Deferred item #7 da spine, que já não reflete o estado do arquivo.
3. Unificar o valor do enum `source_type` entre `AD-7` (`'ATTENDANCE'`) e `data-model.md` (`ATTENDANCE_RECORD`).
4. Adicionar um AD (ou estender AD-10/Consistency Conventions) que fixe a constraint `UNIQUE(student_id, classroom_id, date)` em `AttendanceRecord` — hoje só existe no rascunho de dados, não na spine.
5. Reescrever o título ou a Rule de AD-7 para não prometer "nível de schema" onde a garantia real é transacional/de aplicação.
6. Acrescentar uma frase ao item Deferred de cache/materialização reafirmando que qualquer solução futura continua proibida de usar job agendado (RNF-06/AD-2).
7. Fechar a lacuna de RNF-02/07/08/10 no Capability Map (mesmo que só como "ver DESIGN.md/EXPERIENCE.md" ou "ver AGENTS.md") ou estreitar a declaração de `binds` no front-matter para o que de fato está coberto.
8. Decidir ou adiar explicitamente (com razão) os campos de versionamento de ML além de `model_version`, e o processo de deploy/backup/monitoramento da VM única.
