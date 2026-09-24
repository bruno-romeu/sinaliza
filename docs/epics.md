---
stepsCompleted: [step-01, step-02, step-03, step-04]
inputDocuments:
  - docs/prds/prd-sinaliza-2026-09-16/prd.md
  - docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md
  - docs/ux-designs/ux-sinaliza-2026-09-17/DESIGN.md
  - docs/ux-designs/ux-sinaliza-2026-09-17/EXPERIENCE.md
  - docs/data-model.md
---

# Sinaliza - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Sinaliza, decomposing the requirements from the PRD (`docs/prds/prd-sinaliza-2026-09-16/prd.md`), the Architecture Spine (`docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md`), the UX design contract (`DESIGN.md` + `EXPERIENCE.md`), and `docs/data-model.md` into implementable stories.

Requirement IDs preserve the PRD's own numbering (RF-NN, RNF-NN) rather than being renumbered, per PRD §8 SM-6 ("toda seção deste PRD é rastreável... verificado por conferência linha a linha") — renumbering would break traceability back to the already-approved Levantamento de Requisitos.

## Requirements Inventory

### Functional Requirements

**Autenticação e Acesso**
- RF-01: O sistema deve exigir autenticação (login e senha) para acesso.
- RF-02: O sistema possui um único perfil de usuário: Coordenação Pedagógica.

**Frequência**
- RF-03: O sistema deve registrar presença ou falta de cada estudante por data e turma.
- RF-04: O sistema deve impedir duplicidade de registro de presença para o mesmo estudante, turma e data.

**Notas**
- RF-05: O sistema deve registrar notas de estudantes por disciplina e período letivo.

**Atividades**
- RF-06: O sistema deve cadastrar atividades vinculadas a turma, disciplina e período letivo.
- RF-07: O sistema deve registrar o status de entrega de cada estudante para uma atividade (entregue, não entregue ou parcial).

**Registros Pedagógicos**
- RF-08: O sistema deve registrar observações em texto livre sobre um estudante.
- RF-09: O sistema deve manter a referência ao registro original em qualquer sinal derivado dele.

**Trajetória**
- RF-10: O sistema deve calcular indicadores de trajetória do estudante (frequência, notas, atividades pendentes) em uma janela de tempo rolante.
- RF-11: O sistema deve detectar mudanças relevantes na trajetória, como queda de frequência, queda de desempenho ou aumento de atividades não entregues, sempre referenciando os registros que as sustentam. Nunca por sinal isolado/fórmula única — exige convergência de ≥2 sinais independentes no mesmo bimestre. Um sinal isolado que não converge fica como "fator preocupante", sem subir às mudanças recentes da home.

**Acompanhamento**
- RF-12: A coordenação pedagógica deve poder abrir um acompanhamento para um estudante.
- RF-13: A coordenação pedagógica deve poder registrar ações e alterar o status de um acompanhamento entre em observação, ativo, aguardando retorno ou encerrado.
- RF-14: O sistema deve manter histórico de ações e evidências de cada acompanhamento.

**Privacidade e Acesso a Registros**
- RF-22: O sistema deve associar um usuário responsável a cada acompanhamento e restringir a visibilidade do registro pedagógico do estudante vinculado a esse acompanhamento ao usuário responsável e à coordenação pedagógica.

**Machine Learning (Experimental)**
- RF-15: O sistema deve gerar, a partir do dataset sintético, um score experimental associado a padrões de evasão.
- RF-16: Esse score deve ser tratado sempre como dado experimental, nunca como fato ou probabilidade real.
- RF-17: O sistema deve versionar o modelo utilizado e associar cada predição à sua versão.
- RF-23: O pipeline de ML deve ser treinado com um recorte de dados (Treino) nunca exposto na avaliação/demonstração, e avaliado/demonstrado com um segundo recorte (Avaliação/Operação/Demo) de trajetória completa e desfecho conhecido, truncado em "hoje" pela camada de aplicação quando usado ao vivo. Exatamente dois recortes — nunca três bases separadas.

**Interface**
- RF-18: O sistema deve exibir uma página inicial com mudanças recentes e acompanhamentos em andamento.
- RF-19: O sistema deve exibir a trajetória do estudante, com linha do tempo, evidências e registros.
- RF-20: O sistema deve exibir uma tela de acompanhamento, com status, ações registradas e evidências vinculadas.
- RF-21: A interface não deve exibir ranking de estudantes por risco, score de evasão ou KPIs do tipo "alunos de alto risco". Nenhuma funcionalidade do sistema (não só a tela) deve implementar comparação direta entre estudantes.

### NonFunctional Requirements

- RNF-01 (Desempenho): O sistema deve responder às interações do usuário em no máximo 5 segundos.
- RNF-02 (Usabilidade): A interface deve ser responsiva, adaptando-se a desktop e tablet.
- RNF-03 (Confiabilidade): O pipeline de pré-processamento e inferência do modelo de ML deve ser o mesmo utilizado no treinamento.
- RNF-04 (Disponibilidade): O sistema deve estar disponível durante desenvolvimento e demonstração, sem exigência de disponibilidade 24/7.
- RNF-05 (Segurança): Acesso protegido por autenticação login/senha, senha armazenada de forma criptografada. Perfil único.
- RNF-06 (Tecnologias): PostgreSQL, back-end Python/FastAPI, front-end React, Scikit-Learn para ML, hospedado em serviço gratuito, sem jobs agendados (cron).
- RNF-07 (Dados exclusivamente sintéticos): O sistema deve operar exclusivamente com dados sintéticos; nenhuma predição de ML apresentada como fato determinístico.
- RNF-08 (Acessibilidade): WCAG 2.1 AA como referência nas 3 telas principais (Home, Trajetória, Acompanhamento). Contraste mínimo, navegação completa por teclado, labels associados a campos, nenhuma informação comunicada só por cor.
- RNF-09 (Manutenibilidade): Código organizado em camadas (domínio, aplicação, apresentação), testes automatizados cobrindo a regra de detecção de mudança (RF-11) e o pipeline de pré-processamento/inferência de ML (RNF-03).
- RNF-10 (Compatibilidade): Funcionar nas versões estáveis mais recentes de Chrome, Firefox e Edge, em desktop e tablet.
- RNF-11 (Integridade): Integridade referencial entre toda mudança de trajetória exibida e os registros de origem que a sustentam; impedir estados de dado inconsistentes. Nenhum `TrajectoryChange` sem `source_record_id` válido; duplicidade de presença impedida em nível de banco; acompanhamento nunca fora do conjunto fechado de status.
- RNF-12 (Privacidade e Retenção de Dados): Acesso ao registro pedagógico restrito a quem abriu o acompanhamento e à coordenação (RF-22). Acesso do responsável legal só quando legalmente necessário — fora do MVP. Sem política de expurgo automático no MVP. Exportação por transferência escolar é intenção de design documentada, não funcionalidade do MVP.
- RNF-13 (Origem e Governança dos Dados): Duas origens de dados controladas — dataset sintético (gerador determinístico com seed fixa, calibrado por referência estatística a base pública, nunca misturada ao banco do sistema) e lançamento manual pela coordenação. Nenhum dado real de estudante commitado em nenhuma hipótese.
- RNF-14 (Fronteira do Score Experimental e Avaliação do ML): Avaliação usa precision, recall, F1 e matriz de confusão como métricas obrigatórias (ROC-AUC/PR-AUC adicionais). Resultados documentados estritamente como capacidade de reconhecer padrões simulados, nunca validade preditiva real. Split de dataset (RF-23) é pré-condição da avaliação.

### Additional Requirements

*Extraídas da Architecture Spine (`ARCHITECTURE-SPINE.md`) — decisões técnicas com impacto direto na quebra de histórias. Não há starter/greenfield template especificado (projeto do zero); portanto não há impacto sobre Epic 1 Story 1 além do setup estrutural padrão de camadas.*

- **AD-1 — Cálculo sob demanda, nunca por job agendado:** `TrajectorySnapshot`/`TrajectoryChange` calculados de forma síncrona dentro da própria requisição HTTP (`GET /home`, `GET /students/{id}/trajectory`). Upsert por `(student_id, type, period_id)` via `INSERT ... ON CONFLICT`; `DO NOTHING` se já evidenciado por um `FollowUp` (congelado); `DO UPDATE` caso contrário. Cada estudante recomputado em transação própria. `FollowUpEvidence` só é escrita por ação explícita da coordenação (`application/followup`), nunca auto-attach. "Fator preocupante" nunca é persistido — puramente efêmero na resposta HTTP. `TrajectoryChange` é evento imutável, nunca retrata um recálculo posterior.
- **AD-2 — Regra de dependência entre camadas:** `domain/` Python puro (sem FastAPI/SQLAlchemy/scikit-learn); `application/` só enxerga `domain/` e ports; `presentation/` só chama `application/`; `ml/` só lê domain/ports.
- **AD-3 — Treino/avaliação de ML nunca no caminho de requisição:** só via CLI offline (`python -m app.ml.train`). Pipeline scikit-learn único serializado, reutilizado sem alteração entre treino/inferência. Inferência ao vivo (se existir) carrega artefato uma vez por processo (singleton, `--workers 1`). Score nunca aparece em endpoint/schema de resposta do produto — vive atrás de boundary interno separado (`/research/*`).
- **AD-4 — Dois recortes de dataset, nunca três bases:** `Student.dataset_split` (enum `TRAIN` | `EVAL_DEMO`) atribuído na geração sintética. Toda consulta de treino filtra `TRAIN`; toda consulta da aplicação web filtra `EVAL_DEMO`; avaliação offline lê `EVAL_DEMO` sem truncagem de data.
- **AD-5 — Fonte única de verdade para "hoje":** utilitário `as_of()` em `domain/`, override só via `SINALIZA_DEMO_AS_OF`. Trunca apenas o caminho de leitura ao vivo (home, trajetória); nunca trunca o script de avaliação de ML.
- **AD-6 — Status de acompanhamento é enum fechado, histórico append-only:** `FollowUp.status` é ENUM nativo Postgres com 4 valores fechados. Transição só via método de application service. `follow_up_action` com `GRANT INSERT, SELECT` mas sem `UPDATE`/`DELETE` (backstop de banco).
- **AD-7 — Integridade de evidência por FK real + transação:** `FollowUpEvidence.trajectory_change_id` FK real `NOT NULL`. Único método de application service escreve `TrajectoryChange` + suas `TrajectoryChangeSource` na mesma transação; nenhum outro caminho de código tem permissão de `INSERT` em `trajectory_change`. `AttendanceRecord` com `UNIQUE(student_id, classroom_id, date)` em nível de banco.
- **AD-8 — Perfil único; visibilidade de registro pedagógico escopada por responsável:** modelo `User` único, sem enum de papel. Senha com hash (bcrypt/argon2), JWT bearer stateless. `SignalEvaluator`/`ConvergenceRule` sempre rodam sobre o conjunto completo não filtrado de registros pedagógicos — o filtro de visibilidade só se aplica à exibição do texto, e só depois que o registro vira fonte de evidência de um `FollowUp` real.
- **AD-9 — Hospedagem: VM única sempre ativa, sem scale-to-zero, sem cron:** Plano A (Oracle Cloud Ampere A1, docker-compose com Postgres/FastAPI/Nginx); Plano B (`VM.Standard.E2.1.Micro`, config mais apertada); Plano C (Render+Neon+Vercel free, com pré-aquecimento manual pré-demo). `restart: unless-stopped` nos três serviços; volume Docker nomeado para `PGDATA`.
- **AD-10 — Resolve os `[NOTE FOR PM]` do RF-03/RF-05:** `AttendanceRecord.status` enum (`PRESENT`, `ABSENT_JUSTIFIED`, `ABSENT_UNJUSTIFIED}`) — RF-11 conta toda falta igualmente no MVP. `Grade.value` `numeric(4,2)` escala 0.0–10.0, sem campo de aprovação/reprovação.
- **AD-11 — Invariantes de leitura enforced por repositório-base único:** `dataset_split = EVAL_DEMO` e `as_of()` aplicados por padrão em toda consulta de fatos via classe-base de repositório; só `ml/train`/`ml/evaluate` usam repositórios explicitamente diferentes. Filtro de visibilidade de registro pedagógico vive no mesmo método de leitura.
- **AD-12 — Contrato do pipeline de detecção de sinais:** `SignalEvaluator.evaluate(student_id, period_id) -> Signal(confirmed, kind, source_ids)` fixado para os 4 avaliadores (frequência, nota, atividades, registro pedagógico). `ConvergenceRule.evaluate(signals) -> TrajectoryChange | None` combina ≥2 `Signal.confirmed=True` no mesmo `period_id`. Cálculo de indicadores brutos é função pura em `domain/trajectory.py`, sem I/O.
- **Infraestrutura/convenções gerais:** Migrations via Alembic (nunca alteração manual de schema); PK = UUID v4; envelope de erro `{ "error": { "code", "message" } }`; tipos TypeScript do frontend gerados a partir do schema OpenAPI (nunca transcritos à mão); `FollowUp.next_review_date` consumido só por query ao vivo em `GET /home`.

### UX Design Requirements

*Extraídas de `DESIGN.md` (identidade visual/tokens) e `EXPERIENCE.md` (comportamento/estados/acessibilidade). Cada item é específico o suficiente para gerar uma história com acceptance criteria testáveis.*

- UX-DR1: Implementar o componente **Gráfico de trajetória** com faixa habitual preenchida em `border` + contorno `text-secondary` (representando o histórico do próprio aluno, nunca da turma), linha em `primary`, ponto de mudança em `attention` sempre com ícone+texto ao lado (nunca só cor), cantos `rounded.lg`, alvo de toque mínimo 44×44px. Eixo X em bimestres; eixo Y rotulado com o indicador real (frequência/notas/atividades), nunca "score" ou "risco".
- UX-DR2: O gráfico de trajetória deve ter alternativa textual/tabular equivalente (WCAG 1.1.1) — toggle "ver como tabela" ou elemento `sr-only` com a série bruta (bimestre × valor × faixa habitual min/max); SVG com `role="img"` e nome acessível resumindo a tendência.
- UX-DR3: O ponto de mudança no gráfico é um controle focável (`role="button"`, `tabindex="0"`), ativável por clique ou Enter/Espaço, com foco visível, que rola até o card de evidência correspondente.
- UX-DR4: Implementar o componente **Card de evidência**: selo restrito a ícone/círculo pequeno (`badge-fill`), rótulo de texto sempre sobre `surface` (nunca dentro da área colorida saturada), sempre expandido (nunca colapsado atrás de "ver mais"). Reaproveitado na Tela de Acompanhamento com link "Ver na trajetória de [aluno]".
- UX-DR5: Implementar o componente **Fator Preocupante**: fundo igual ao canvas (`bg`, não `surface`), sem selo colorido, texto em `text-secondary`; cabeçalho focável e expansível (`role="button"`, `tabindex="0"`, `aria-expanded`), fechado por padrão, foco permanece no cabeçalho após alternar.
- UX-DR6: Implementar o componente **Card de estado calmo**, exibido quando o aluno está dentro da faixa habitual, com selo em ícone `success` + rótulo textual (ex. "dentro da faixa habitual") — nunca uma tela vazia ou mensagem de erro; mesmo cuidado visual do estado com mudança.
- UX-DR7: Implementar o componente **Selo de status de acompanhamento** (pílula) com os 4 estados fechados (Em observação / Ativo / Aguardando retorno / Encerrado), cada um com fundo, texto e ícone próprios (nunca `attention` nem tom de "alto risco"); forma pílula (`rounded.full`) reservada exclusivamente a este componente.
- UX-DR8: O seletor de status de acompanhamento é implementado como `<select>` nativo, ou — se customizado — segue o padrão WAI-ARIA APG de listbox (Esc fecha, setas navegam entre as 4 opções, foco retorna ao gatilho); nunca um campo de texto livre para status.
- UX-DR9: Implementar a **Linha do tempo de registros**: lista vertical estática, somente leitura (data em `caption`, descrição em `body`, tag de tipo em `caption`), sem ícones de sentimento, sem cor por tipo de registro, sem hover/seleção.
- UX-DR10: Implementar a **Linha de mudança recente** na Home: nome do aluno + descrição curta + marcador de ícone (não bolinha de cor sozinha); área clicável cobre a linha inteira; clique abre a Trajetória direto na seção de evidência da mudança; lista ordenada por data de detecção, nunca por gravidade ou score.
- UX-DR11: Implementar o **Card de acompanhamento em andamento** na Home, usando o selo de status e nome do aluno; área de clique total (mesma regra da linha de mudança recente); nunca exibe contagem regressiva de urgência.
- UX-DR12: Implementar a **Busca de aluno** com label visível (não só placeholder), filtro por nome ou turma entre os ~200 estudantes, resultados como lista de itens focáveis por Tab, `aria-live="polite"` anunciando a contagem de resultados; é a única forma de chegar a um aluno "tranquilo" (sem mudança recente/acompanhamento ativo).
- UX-DR13: Implementar o **Formulário de ação/registro** (ação de acompanhamento, observação pedagógica): campo de texto/textarea com label associado sempre visível acima do campo; botão de envio desabilitado enquanto o campo estiver vazio — nunca registro em branco; toda ação registrada entra no histórico, nunca substitui uma anterior.
- UX-DR14: Implementar o componente **Botão**: semântica nativa `<button>`, foco sempre visível, alvo de toque mínimo 44×44px; variante primária (`primary`/texto `surface`, cantos `rounded.md`) e secundária (contorno `border`, texto `text`, mesmo fundo `surface`) — nunca uma segunda cor de marca.
- UX-DR15: Aplicar a paleta de cores e tokens de `DESIGN.md` (bg/surface/text/text-secondary/border/primary/attention/success, com variantes dark) de forma consistente em toda a interface — nunca vermelho (nem para erro de formulário), nunca gradiente, nunca segunda cor de marca, nunca escala visual "pior→melhor" entre alunos.
- UX-DR16: Aplicar o sistema tipográfico (display/heading/eyebrow/body/body-secondary/caption) com pilha de fontes de sistema; `eyebrow` (12px/700, letter-spacing 0.08em, maiúsculas) como principal recurso de hierarquia entre seções, no lugar de bordas/cor de fundo.
- UX-DR17: Layout em coluna única centralizada, largura máxima 900px, sem sidebar de navegação persistente; ritmo vertical generoso entre seções (52px); responsivo para desktop e tablet sem breakpoint especial — cards perdem padding lateral em telas menores mas mantêm a mesma ordem vertical.
- UX-DR18: Implementar os estados de UI de `EXPERIENCE.md` (State Patterns): "sem mudanças recentes" (Home, com contagem de acompanhamentos ativos ainda visível), "sem acompanhamentos ativos" (mensagem neutra), "busca sem resultado" (sem sugestões automáticas), "carregando" (skeleton, nunca spinner de tela cheia), "erro de carregamento" (mensagem factual + ação de tentar novamente), "registro duplicado" (mensagem factual junto ao campo, RF-04/RNF-11), "confirmação de salvamento" (texto breve, sem modal bloqueante), "aluno/acompanhamento não encontrado" (mensagem factual + voltar à Home, sem página 404 dedicada).
- UX-DR19: Toda ação destrutiva ou irreversível (ex.: encerrar acompanhamento) pede confirmação simples antes de efetivar.
- UX-DR20: Navegação completa por teclado nas 3 telas principais (Home, Trajetória, Acompanhamento), seguindo a ordem de leitura (gráfico → evidência → fator preocupante → linha do tempo → ação), sem armadilhas de foco; abrir/fechar o fator preocupante e mudar status de acompanhamento devem funcionar sem mouse.
- UX-DR21: Aplicar o tom de voz de `Voice and Tone` (curiosidade responsável, frases factuais sempre referenciando o registro-fonte) em todo microcopy de produto — nunca frases que soem como diagnóstico, previsão ou julgamento sobre o estudante (ex.: usar "Mudança recente: queda de frequência e aumento de atividades pendentes — 3º bimestre", nunca "82% de chance de evasão").
- UX-DR22: Implementar as 5 superfícies da Information Architecture (Login, Home, Trajetória do Estudante, Tela de Acompanhamento, Lançamento) com cabeçalho simples (nome do usuário autenticado + link de volta à Home), sem navegação lateral persistente.
- UX-DR23: Mensagens de erro de validação em formulários usam `aria-describedby` apontando para o campo — nunca só cor/ícone isolado.

### FR Coverage Map

- RF-01: Epic 1 - Autenticação obrigatória
- RF-02: Epic 1 - Perfil único (Coordenação Pedagógica)
- RF-03: Epic 1 - Registro de presença/falta
- RF-04: Epic 1 - Impedir duplicidade de registro de presença
- RF-05: Epic 1 - Registro de notas
- RF-06: Epic 1 - Cadastro de atividades
- RF-07: Epic 1 - Status de entrega de atividade
- RF-08: Epic 1 - Observações em texto livre
- RF-09: Epic 1 - Referência ao registro original
- RF-10: Epic 3 - Cálculo de indicadores de trajetória
- RF-11: Epic 3 - Detecção de mudança relevante por convergência de sinais
- RF-12: Epic 4 - Abertura de acompanhamento
- RF-13: Epic 4 - Registro de ações e mudança de status
- RF-14: Epic 4 - Histórico de ações e evidências
- RF-15: Epic 5 - Geração de score experimental
- RF-16: Epic 5 - Score como dado experimental
- RF-17: Epic 5 - Versionamento do modelo
- RF-18: Epic 3 - Página inicial
- RF-19: Epic 3 - Trajetória do estudante
- RF-20: Epic 4 - Tela de acompanhamento
- RF-21: Epic 3 - Proibição de ranking/score/KPI de risco
- RF-22: Epic 4 - Escopo de acesso ao registro pedagógico
- RF-23: Epic 5 - Split de dataset em dois recortes

*NFRs de acessibilidade/usabilidade/compatibilidade/integridade (RNF-02, RNF-08, RNF-09, RNF-10, RNF-11) são transversais — endereçadas como critérios de aceitação dentro das histórias de cada épico relevante, não mapeadas isoladamente aqui.*

## Epic List

### Epic 1: Autenticação e Registro da Rotina Pedagógica
A coordenação pedagógica autentica-se e registra os fatos observáveis do dia a dia (presença, notas, entrega de atividades, observações pedagógicas) para seus estudantes e turmas — a base sobre a qual toda detecção de trajetória será calculada. Realiza UJ-2 por completo.
**FRs covered:** RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-07, RF-08, RF-09

### Epic 2: Geração de Dataset Sintético Calibrado
Uma base sintética determinística, calibrada por referência estatística a dados públicos e particionada em recorte de treino e recorte de avaliação/demo, fornece volume histórico realista para demonstrar e avaliar o sistema sem qualquer dado real de estudante. Entrega o campo `Student.dataset_split` (AD-4) consumido pelo Epic 5.
**FRs covered:** nenhum RF numerado diretamente (RNF-07, RNF-13)

### Epic 3: Trajetória e Detecção de Mudança Convergente
A coordenação vê a página inicial com mudanças recentes, abre a trajetória de um estudante e visualiza indicadores, linha do tempo e evidências que sustentam cada mudança detectada por convergência de sinais — nunca por um sinal isolado ou fórmula única. Realiza UJ-1.
**FRs covered:** RF-10, RF-11, RF-18, RF-19, RF-21

### Epic 4: Acompanhamento Pedagógico
A partir da evidência revisada, a coordenação abre, conduz e encerra um acompanhamento, com histórico completo de ações e evidências, e o registro pedagógico do estudante fica com visibilidade restrita ao responsável e à coordenação. Realiza UJ-3.
**FRs covered:** RF-12, RF-13, RF-14, RF-20, RF-22

### Epic 5: Machine Learning Experimental
O sistema treina, versiona e avalia — offline, nunca no caminho de requisição — um modelo experimental que explora padrões associados à evasão no dataset sintético, sempre tratado como resultado de pesquisa, nunca como fato sobre o estudante real.
**FRs covered:** RF-15, RF-16, RF-17, RF-23

### Epic 6: Hospedagem e Publicação do Sistema
O sistema fica hospedado numa VM sempre ativa (sem scale-to-zero, sem cron), acessível para demonstração e avaliação pela banca até 23/11/2026.
**FRs covered:** nenhum RF numerado diretamente (RNF-04, RNF-06)

## Epic 1: Autenticação e Registro da Rotina Pedagógica

A coordenação pedagógica autentica-se e registra os fatos observáveis do dia a dia (presença, notas, entrega de atividades, observações pedagógicas) para seus estudantes e turmas — a base sobre a qual toda detecção de trajetória será calculada. Realiza UJ-2 por completo.

**FRs covered:** RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-07, RF-08, RF-09

*Nota de escopo: `EXPERIENCE.md` define exatamente 5 superfícies (Login, Home, Trajetória, Acompanhamento, Lançamento) — não existe tela de cadastro de turma/estudante no MVP. Turmas e estudantes usados no lançamento manual vêm de fixture/seed de desenvolvimento (Story 1.2) ou da geração sintética (Epic 2).*

### Story 1.1: Autenticação da coordenação pedagógica

As a coordenação pedagógica,
I want me autenticar com login e senha,
So that eu possa acessar o sistema com segurança.

**Acceptance Criteria:**

**Given** um usuário cadastrado com email e senha válidos
**When** ele envia login e senha corretos no formulário de autenticação
**Then** o sistema retorna um token JWT bearer válido e redireciona para a Home

**Given** um usuário envia senha incorreta
**When** a tentativa de login falha
**Then** o sistema exibe mensagem factual de erro ("Login ou senha inválidos.") sem indicar qual dos dois está errado, e nenhum token é emitido

**Given** a senha de um usuário
**When** ela é armazenada no banco
**Then** está protegida por hash (bcrypt/argon2) — nunca texto plano (RNF-05)

**Given** um usuário não autenticado
**When** ele tenta acessar qualquer rota do sistema além da tela de login
**Then** é redirecionado para a tela de login (RF-01)

**Given** o modelo de usuário
**When** consultado
**Then** possui um único valor possível de perfil (`COORDENACAO_PEDAGOGICA`), sem um segundo valor tipo "professor" (RF-02, AD-8)

**Given** o campo de formulário de login
**When** exibido
**Then** possui label associado visível (não só placeholder), foco visível e alvo de toque mínimo 44×44px (RNF-08, UX-DR14, UX-DR23)

**Given** um usuário autenticado em qualquer tela além do login
**When** a interface é renderizada
**Then** exibe um cabeçalho simples com o nome do usuário autenticado e um link de volta à Home, sem navegação lateral persistente (UX-DR22)

### Story 1.2: Registro de presença/falta por turma e data

As a coordenação pedagógica,
I want registrar a presença ou falta de cada estudante de uma turma em uma data,
So that o sistema tenha o fato bruto necessário para calcular a frequência na trajetória do estudante.

**Acceptance Criteria:**

**Given** uma turma com estudantes matriculados (via fixture/seed de desenvolvimento — não existe tela de cadastro de turma/estudante no MVP)
**When** a coordenação seleciona a turma e a data no Lançamento
**Then** vê a lista de estudantes matriculados com um seletor de status por estudante (Presente, Falta justificada, Falta não justificada) (RF-03, AD-10)

**Given** um lançamento de presença já salvo para um estudante/turma/data
**When** a coordenação tenta salvar outro lançamento para a mesma combinação
**Then** o sistema rejeita com mensagem factual junto ao campo ("Já existe registro de presença para este aluno, turma e data.") e não cria duplicidade (RF-04, UX-DR18)

**Given** a tabela `attendance_record`
**When** inspecionado o schema
**Then** existe uma constraint `UNIQUE(student_id, classroom_id, date)` em nível de banco — a duplicidade é impedida mesmo que a checagem de aplicação seja contornada (RNF-11, AD-7)

**Given** o formulário de lançamento de presença
**When** exibido
**Then** cada campo tem label associado visível e o botão de salvar segue a especificação de alvo de toque 44×44px (RNF-08, UX-DR13, UX-DR14)

**Given** um lançamento salvo com sucesso
**When** a operação completa
**Then** uma confirmação textual breve aparece ("Registro salvo.") sem modal bloqueante, permitindo lançar o próximo estudante sem interrupção (UX-DR18)

### Story 1.3: Registro de notas por disciplina e período letivo

As a coordenação pedagógica,
I want registrar a nota de um estudante em uma disciplina e período letivo,
So that o sistema tenha o fato bruto necessário para calcular a tendência de desempenho na trajetória.

**Acceptance Criteria:**

**Given** um estudante matriculado e um período letivo vigente
**When** a coordenação lança uma nota informando disciplina, valor e período
**Then** o registro é persistido com `value` em escala numérica 0.0–10.0 (`numeric(4,2)`), sem campo de aprovação/reprovação (RF-05, AD-10)

**Given** um valor de nota fora da faixa 0.0–10.0
**When** a coordenação tenta salvar
**Then** o sistema rejeita com mensagem de validação associada ao campo via `aria-describedby` (UX-DR23)

**Given** o formulário de lançamento de nota
**When** exibido
**Then** cada campo (disciplina, valor, período, data) tem label associado visível (RNF-08)

**Given** um lançamento de nota salvo com sucesso
**When** a operação completa
**Then** uma confirmação textual breve aparece sem modal bloqueante (UX-DR18)

### Story 1.4: Cadastro de atividades e registro de status de entrega

As a coordenação pedagógica,
I want cadastrar uma atividade vinculada a uma turma, disciplina e período letivo, e registrar o status de entrega de cada estudante,
So that o sistema tenha o fato bruto necessário para calcular a tendência de atividades pendentes na trajetória.

**Acceptance Criteria:**

**Given** uma turma, disciplina e período letivo
**When** a coordenação cadastra uma atividade informando data de entrega
**Then** a atividade é persistida e passa a estar disponível para registro de status de entrega dos estudantes matriculados (RF-06)

**Given** uma atividade cadastrada
**When** a coordenação registra o status de entrega de um estudante (entregue, não entregue ou parcial)
**Then** o registro `AssignmentSubmission` é persistido vinculado à atividade e ao estudante (RF-07)

**Given** o formulário de cadastro de atividade e de status de entrega
**When** exibido
**Then** cada campo tem label associado visível (RNF-08)

**Given** um cadastro/registro salvo com sucesso
**When** a operação completa
**Then** uma confirmação textual breve aparece sem modal bloqueante (UX-DR18)

### Story 1.5: Registro de observação pedagógica em texto livre

As a coordenação pedagógica,
I want registrar uma observação em texto livre sobre um estudante,
So that eu tenha um registro do que observei na rotina, disponível como evidência potencial para futuras mudanças de trajetória.

**Acceptance Criteria:**

**Given** um estudante matriculado
**When** a coordenação registra uma observação em texto livre sobre ele
**Then** o registro `PedagogicalObservation` é persistido com referência ao estudante, ao autor (`author_user_id`) e ao timestamp de criação (RF-08, RF-09)

**Given** o campo de texto da observação vazio
**When** a coordenação tenta salvar
**Then** o botão de salvar permanece desabilitado — não existe registro pedagógico em branco (UX-DR13)

**Given** uma observação recém-criada que ainda não foi citada como fonte de evidência de nenhum acompanhamento
**When** qualquer usuário autenticado a acessa
**Then** ela é visível normalmente — a restrição de visibilidade por responsável (RF-22) só se aplica depois que a observação é vinculada como evidência de um acompanhamento (implementado no Epic 4; aqui é apenas documentado, não implementado)

**Given** o formulário de observação
**When** exibido
**Then** o campo de texto tem label associado visível e o botão de salvar segue a especificação de botão (RNF-08, UX-DR13, UX-DR14)

## Epic 2: Geração de Dataset Sintético Calibrado

Uma base sintética determinística, calibrada por referência estatística a dados públicos e particionada em recorte de treino e recorte de avaliação/demo, fornece volume histórico realista para demonstrar e avaliar o sistema sem qualquer dado real de estudante. Entrega o campo `Student.dataset_split` (AD-4) consumido pelo Epic 5.

**FRs covered:** nenhum RF numerado diretamente (RNF-07, RNF-13)

### Story 2.1: Geração determinística de estudantes, turmas e matrículas

As a autor/avaliador do sistema,
I want gerar deterministicamente uma base de estudantes, turmas e matrículas via CLI com seed fixa,
So that eu possa reproduzir exatamente a mesma base sintética em qualquer execução, sem depender de dados reais.

**Acceptance Criteria:**

**Given** uma seed fixa configurada
**When** o comando de geração sintética é executado duas vezes com a mesma seed
**Then** os dois resultados são idênticos nas tabelas geradas (determinismo, RNF-13)

**Given** a execução do gerador
**When** estudantes e turmas são criados
**Then** cada estudante recebe um `dataset_split` (`TRAIN` ou `EVAL_DEMO`) atribuído no momento da geração, nunca em query time (AD-4)

**Given** os metadados de uma execução de geração
**When** persistidos
**Then** incluem a seed utilizada, a versão do gerador e a data de execução, para rastreabilidade (RNF-13)

**Given** nenhuma execução prévia do gerador
**When** o comando roda pela primeira vez
**Then** popula o banco com um volume coerente com ~200 estudantes distribuídos entre turmas e os dois recortes de dataset

### Story 2.2: Perfis de trajetória sintética conhecidos aplicados aos fatos observáveis

As a autor/avaliador do sistema,
I want que cada estudante sintético siga uma regra de perfil conhecida e documentada (ex. `falling_attendance`, `stable`, `combined_deterioration`),
So that eu possa validar a regra de detecção de mudança (RF-11, Epic 3) contra trajetórias com desfecho conhecido.

**Acceptance Criteria:**

**Given** um estudante sintético
**When** gerado
**Then** seu perfil é um valor de um enum documentado (nunca geração aleatória opaca) — cada perfil corresponde a uma regra determinística de evolução de frequência/notas/atividades ao longo do ano letivo (RNF-13)

**Given** o perfil `falling_attendance`
**When** os registros de presença do estudante são gerados
**Then** a taxa de presença decai de forma consistente com a regra documentada do perfil, de forma reproduzível com a mesma seed

**Given** o conjunto de perfis disponíveis
**When** inspecionado
**Then** inclui ao menos um perfil "estável" (sem mudança) e ao menos um perfil de "deterioração combinada" (frequência + nota + atividades juntos), cobrindo o espectro de casos que RF-11 precisa distinguir

**Given** os fatos gerados (presença, notas, atividades) para um estudante
**When** inspecionados
**Then** respeitam as mesmas constraints de integridade da Epic 1 (ex. `UNIQUE(student_id, classroom_id, date)` em presença) — a geração nunca produz dado inconsistente

### Story 2.3: Split de dataset em recorte de treino e recorte de avaliação/demo

As a autor/avaliador do sistema,
I want que o gerador particione os estudantes entre um recorte de treino e um recorte de avaliação/operação/demo,
So that o Epic 5 (ML) possa treinar sem nunca ver os dados usados para avaliação e demonstração, evitando vazamento de treino.

**Acceptance Criteria:**

**Given** a execução do gerador
**When** estudantes são criados
**Then** exatamente dois valores de `dataset_split` existem (`TRAIN`, `EVAL_DEMO`) — nunca uma terceira categoria ou base sintética separada (AD-4)

**Given** o recorte `EVAL_DEMO`
**When** gerado
**Then** cada estudante desse recorte tem trajetória completa e desfecho conhecido ao longo de todo o ano letivo sintético (pré-condição de RF-23 para o Epic 5)

**Given** o recorte `TRAIN`
**When** consultado por qualquer query da aplicação web (home, trajetória, lançamento)
**Then** nunca aparece — apenas o recorte `EVAL_DEMO` é servido ao vivo (AD-4, AD-11)

**Given** a proporção entre os dois recortes
**When** configurada
**Then** é documentada explicitamente no código do gerador como constante nomeada, não um número mágico sem explicação

### Story 2.4: Calibração de parâmetros por referência a base pública de dados educacionais

As a autor/avaliador do sistema,
I want calibrar os parâmetros de geração (distribuição de frequência, notas, perfis) por referência estatística a uma base pública de dados educacionais,
So that a base sintética seja estatisticamente plausível, sem nunca misturar dado real ao banco do sistema.

**Acceptance Criteria:**

**Given** um parâmetro de geração (ex. taxa média de frequência, distribuição de notas)
**When** documentado
**Then** registra sua proveniência — fonte da referência pública e nível de confiança — conforme `research.md` (RNF-13)

**Given** a base pública usada como referência
**When** o sistema roda em produção/demonstração
**Then** ela nunca é consultada em tempo de execução nem persistida no banco do sistema — usada só offline, na calibração das constantes do gerador (RNF-13)

**Given** um parâmetro sem base pública brasileira equivalente disponível (ex. distribuição de notas 0–10)
**When** documentado
**Then** é marcado explicitamente como suposição de design, não como dado calibrado

**Given** o dataset gerado
**When** qualquer registro é inspecionado
**Then** não contém nome, matrícula, telefone, endereço ou qualquer dado real de estudante — 100% fictício (RNF-13, RNF-07)

### Story 2.5: Registros pedagógicos sintéticos coerentes com o perfil do estudante

As a autor/avaliador do sistema,
I want gerar observações pedagógicas sintéticas coerentes com o perfil de cada estudante,
So that o registro pedagógico em texto livre também exista como sinal independente e testável na base sintética.

**Acceptance Criteria:**

**Given** um estudante com perfil `falling_attendance` ou `combined_deterioration`
**When** observações pedagógicas sintéticas são geradas para ele
**Then** o texto gerado é consistente com o perfil, usando um conjunto de templates determinísticos, nunca geração aberta/opaca

**Given** um estudante com perfil `stable`
**When** observações sintéticas são geradas
**Then** o texto reflete rotina normal, sem viés artificial de "alerta"

**Given** as observações pedagógicas sintéticas geradas
**When** persistidas
**Then** seguem a mesma estrutura de `PedagogicalObservation` da Epic 1 (student_id, author_user_id, text, created_at) — nenhuma tabela paralela para dado sintético

**Given** o texto de uma observação sintética
**When** comparado ao tom exigido em `EXPERIENCE.md.Voice and Tone`
**Then** é factual e descritivo, nunca um rótulo de julgamento ("aluno de risco")

## Epic 3: Trajetória e Detecção de Mudança Convergente

A coordenação vê a página inicial com mudanças recentes, abre a trajetória de um estudante e visualiza indicadores, linha do tempo e evidências que sustentam cada mudança detectada por convergência de sinais — nunca por um sinal isolado ou fórmula única. Realiza UJ-1.

**FRs covered:** RF-10, RF-11, RF-18 (parcial), RF-19, RF-21

*Nota de escopo: RF-18 pede "mudanças recentes e acompanhamentos em andamento" na Home — como `FollowUp` só existe a partir do Epic 4, este épico entrega a seção de mudanças recentes completa; o Epic 4 estende a mesma tela com a seção de acompanhamentos em andamento.*

### Story 3.1: Cálculo de indicadores de trajetória em janela rolante

As a coordenação pedagógica,
I want que o sistema calcule os indicadores de trajetória de um estudante (frequência, notas, atividades pendentes) numa janela de tempo rolante,
So that eu tenha uma visão objetiva da evolução recente do estudante, baseada nos fatos já registrados.

**Acceptance Criteria:**

**Given** os fatos observáveis de um estudante (presença, notas, atividades)
**When** a trajetória é solicitada (`GET /students/{id}/trajectory`)
**Then** o sistema calcula `attendance_rate`, `attendance_trend`, `grade_average`, `grade_trend`, `missing_assignments_count`, `missing_assignment_delta` numa janela rolante (`window_days`) — de forma síncrona, dentro da própria requisição, nunca por job agendado (RF-10, AD-1)

**Given** a função de cálculo de indicadores
**When** implementada
**Then** vive em `domain/trajectory.py` como função pura, sem I/O — testável isoladamente com casos sintéticos conhecidos (RNF-09, AD-12)

**Given** duas requisições concorrentes de trajetória para o mesmo estudante
**When** processadas
**Then** cada uma calcula de forma independente sem lock explícito, sem produzir resultado inconsistente entre si (AD-1)

**Given** a leitura de fatos para o cálculo
**When** executada
**Then** usa exclusivamente o recorte `EVAL_DEMO` do estudante e a data de referência de `as_of()` — nunca lê `TRAIN` nem dados além de "hoje" (AD-4, AD-5, AD-11)

### Story 3.2: Detecção de mudança relevante por convergência de sinais

As a coordenação pedagógica,
I want que o sistema detecte uma mudança relevante na trajetória do estudante somente quando houver convergência de pelo menos dois sinais independentes no mesmo bimestre,
So that eu confie que toda mudança sinalizada é uma evidência real, nunca um alarme de um único indicador isolado.

**Acceptance Criteria:**

**Given** os quatro `SignalEvaluator` (frequência, nota, atividades, registro pedagógico)
**When** avaliados para um estudante e período
**Then** cada um retorna `Signal(confirmed: bool, kind: str, source_ids: list)` seguindo a interface fixa da arquitetura (AD-12)

**Given** ao menos 2 sinais com `confirmed=True` no mesmo `period_id`
**When** avaliados pela `ConvergenceRule`
**Then** uma `TrajectoryChange` é criada/atualizada via `INSERT ... ON CONFLICT (student_id, type, period_id) DO UPDATE` — nunca um `SELECT` seguido de `INSERT`/`UPDATE` em duas etapas (RF-11, AD-1)

**Given** uma `TrajectoryChange` que já tem ao menos um `FollowUpEvidence` apontando para ela
**When** uma nova requisição recalcula o mesmo `period_id`
**Then** a linha permanece congelada (`DO NOTHING`) — descrição, `detected_at` e suas `TrajectoryChangeSource` não mudam mais (AD-1, RNF-11)

**Given** um único sinal confirmado sem convergência com nenhum outro no mesmo período
**When** avaliado
**Then** é devolvido na resposta HTTP como "fator preocupante", sem id estável e sem linha em nenhuma tabela (RF-11, AD-1)

**Given** uma `TrajectoryChange` criada
**When** persistida
**Then** suas `TrajectoryChangeSource` são escritas na mesma transação — nenhuma `TrajectoryChange` existe sem ao menos uma fonte (RF-09, RNF-11, AD-7)

**Given** um registro pedagógico em texto livre
**When** avaliado como sinal
**Then** conta com peso igual aos demais sinais (frequência, desempenho, atividades) — pode, por si só, contribuir para a convergência (RF-11)

**Given** um recálculo posterior de um `period_id` cujos sinais deixaram de confirmar (aluno recuperou)
**When** processado
**Then** a `TrajectoryChange` já gravada não é apagada nem revertida — é um evento histórico imutável, não um gauge ao vivo (AD-1)

### Story 3.3: Página inicial com mudanças recentes

As a coordenação pedagógica,
I want ver na página inicial a lista de mudanças recentes detectadas entre meus estudantes,
So that eu perceba rapidamente, ao abrir o sistema, quais trajetórias merecem revisão hoje.

**Acceptance Criteria:**

**Given** mudanças de trajetória detectadas recentemente
**When** a coordenação abre a Home
**Then** vê uma linha por mudança (nome do estudante, descrição curta, marcador de ícone), ordenadas por data de detecção — nunca por gravidade ou score (RF-18, RF-21, UX-DR10)

**Given** a interface da Home
**When** qualquer elemento é renderizado
**Then** não exibe ranking de estudantes, score de evasão ou KPI do tipo "alunos de alto risco" em nenhuma forma (RF-21)

**Given** uma linha de mudança recente
**When** clicada
**Then** abre a Trajetória do Estudante direto na seção de evidência daquela mudança (UX-DR10)

**Given** nenhuma mudança recente detectada
**When** a Home é carregada
**Then** exibe mensagem explícita de que não há mudanças a revisar hoje — nunca uma lista vazia genérica (UX-DR18)

**Given** a busca de aluno
**When** a coordenação digita um nome ou turma
**Then** os resultados aparecem como lista de itens focáveis por Tab, com `aria-live="polite"` anunciando a contagem — necessário porque a Home só lista quem tem mudança recente, não todos os ~200 estudantes (UX-DR12)

**Given** uma busca sem resultado
**When** executada
**Then** exibe "Nenhum estudante encontrado com esse nome/turma." sem sugestões automáticas (UX-DR18)

**Given** a tela em carregamento
**When** os dados ainda não chegaram
**Then** exibe skeleton simples nos blocos de conteúdo, nunca um spinner de tela cheia (UX-DR18)

**Given** um erro ao carregar a Home
**When** ocorre
**Then** exibe mensagem factual ("Não foi possível carregar os dados agora.") com ação de tentar novamente (UX-DR18)

**Given** a paleta de cores e tipografia de `DESIGN.md`
**When** a Home é implementada
**Then** aplica os tokens definidos (bg/surface/text/primary/attention/success, tipografia display/heading/eyebrow/body) de forma consistente, em coluna única centralizada de até 900px (UX-DR15, UX-DR16, UX-DR17)

**Given** a Home
**When** navegada por teclado
**Then** toda a navegação (link de mudança, campo de busca) é alcançável e opera sem mouse, com foco visível (RNF-08, UX-DR20)

**Given** a descrição de uma mudança recente exibida na Home
**When** redigida
**Then** segue o tom de `EXPERIENCE.md.Voice and Tone` — frases curtas e factuais referenciando o registro-fonte (ex. "Mudança recente: queda de frequência e aumento de atividades pendentes — 3º bimestre"), nunca linguagem de diagnóstico, previsão ou julgamento (ex. nunca "82% de chance de evasão" ou "aluno de risco") (UX-DR21)

### Story 3.4: Trajetória do estudante — gráfico, evidências e fator preocupante

As a coordenação pedagógica,
I want visualizar a trajetória de um estudante com gráfico, linha do tempo, evidências e fatores preocupantes,
So that eu entenda, com evidência rastreável, o que mudou na trajetória dele e por quê.

**Acceptance Criteria:**

**Given** a trajetória de um estudante
**When** a tela é aberta
**Then** exibe o gráfico de trajetória com a faixa habitual calculada sobre o próprio histórico do aluno (nunca da turma), linha real da trajetória, e ponto(s) de mudança marcados com ícone + texto (nunca só cor) (RF-19, UX-DR1)

**Given** o gráfico de trajetória
**When** renderizado
**Then** tem alternativa textual/tabular equivalente (toggle "ver como tabela" ou `sr-only`) com a série bimestre × valor × faixa habitual, e `role="img"` com nome acessível resumindo a tendência (UX-DR2)

**Given** um ponto de mudança no gráfico
**When** focado via Tab e ativado por clique ou Enter/Espaço
**Then** rola até o card de evidência correspondente, com foco visível (UX-DR3)

**Given** uma mudança com evidência
**When** exibida
**Then** aparece um card de evidência sempre expandido, com selo restrito a ícone/círculo e rótulo textual sobre a superfície — apontando para pelo menos um registro válido (RF-19, RF-09, RNF-11, UX-DR4)

**Given** um sinal isolado que não convergiu
**When** exibido
**Then** aparece como "fator preocupante" — visualmente discreto, com cabeçalho focável e expansível (`role="button"`, `aria-expanded`), fechado por padrão, foco permanece no cabeçalho após alternar (RF-11, UX-DR5)

**Given** um estudante sem mudança recente
**When** sua trajetória é exibida
**Then** aparece um card de estado calmo ("dentro da faixa habitual") com o mesmo cuidado visual do estado com mudança — nunca uma tela vazia (UX-DR6)

**Given** a linha do tempo de registros do estudante
**When** exibida
**Then** é uma lista vertical estática, somente leitura, sem cor por tipo de registro, sem hover/seleção (UX-DR9)

**Given** o eixo Y do gráfico
**When** rotulado
**Then** usa o indicador real (frequência, notas, atividades) — nunca "score" ou "risco" (RF-21)

**Given** um estudante ou trajetória inexistente
**When** acessado
**Then** exibe mensagem factual com ação de voltar à Home, nunca uma tela em branco (UX-DR18)

## Epic 4: Acompanhamento Pedagógico

A partir da evidência revisada, a coordenação abre, conduz e encerra um acompanhamento, com histórico completo de ações e evidências, e o registro pedagógico do estudante fica com visibilidade restrita ao responsável e à coordenação. Realiza UJ-3.

**FRs covered:** RF-12, RF-13, RF-14, RF-20, RF-22, e completa RF-18 (seção de acompanhamentos em andamento na Home)

### Story 4.1: Abertura de acompanhamento vinculado a evidências

As a coordenação pedagógica,
I want abrir um acompanhamento para um estudante a partir da evidência revisada na trajetória,
So that eu inicie um processo humano de acompanhamento com evidência rastreável, nunca com uma afirmação solta.

**Acceptance Criteria:**

**Given** a Trajetória de um estudante com uma mudança e evidência revisada
**When** a coordenação clica em "Abrir acompanhamento"
**Then** um `FollowUp` é criado com status inicial "Em observação", `responsible_user_id` = usuário autenticado, e vinculado à(s) `TrajectoryChange` correspondente(s) via `FollowUpEvidence` (RF-12, RF-22)

**Given** a criação de um `FollowUpEvidence`
**When** persistido
**Then** `trajectory_change_id` é uma FK real `NOT NULL` — nunca criado sem referência válida (RNF-11, AD-7)

**Given** a vinculação de evidência a um acompanhamento
**When** ocorre
**Then** é sempre uma ação explícita da coordenação — nunca um auto-attach automático quando uma nova `TrajectoryChange` aparecer para um `FollowUp` já aberto (AD-1)

**Given** um `FollowUp` recém-aberto
**When** a tela de acompanhamento é aberta a partir do botão "Abrir acompanhamento"
**Then** exibe o status "Em observação" com o selo de pílula (RF-20, UX-DR7)

**Given** o card de evidência reaproveitado na tela de acompanhamento
**When** exibido
**Then** inclui um link "Ver na trajetória de [aluno]" de volta à Trajetória do Estudante (UX-DR4)

### Story 4.2: Registro de ações e mudança de status de um acompanhamento

As a coordenação pedagógica,
I want registrar ações e alterar o status de um acompanhamento entre os 4 estados fechados,
So that eu conduza o processo de acompanhamento de forma transparente e rastreável até sua conclusão.

**Acceptance Criteria:**

**Given** um acompanhamento ativo
**When** a coordenação registra uma ação (texto livre) no formulário de ação
**Then** um `FollowUpAction` é persistido com `author_user_id` e `created_at`, e passa a integrar o histórico — nunca substitui uma ação anterior (RF-13, RF-14)

**Given** o campo de ação vazio
**When** a coordenação tenta salvar
**Then** o botão de salvar permanece desabilitado (UX-DR13)

**Given** o seletor de status de um acompanhamento
**When** acionado
**Then** abre um `<select>` nativo (ou padrão WAI-ARIA listbox) com apenas os 4 estados fechados (Em observação, Ativo, Aguardando retorno, Encerrado) — nunca um campo de texto livre (RF-13, UX-DR8)

**Given** uma mudança de status
**When** efetivada
**Then** ocorre exclusivamente através de um método de application service — nunca atribuição direta de campo a partir do router (AD-6)

**Given** a tabela `follow_up_action`
**When** inspecionada
**Then** o papel de aplicação do Postgres tem `GRANT INSERT, SELECT` mas não `UPDATE`/`DELETE` — histórico é append-only mesmo contra um bug futuro de código (AD-6)

**Given** uma tentativa de encerrar um acompanhamento
**When** confirmada
**Then** pede confirmação simples antes de efetivar a mudança de status (UX-DR19)

### Story 4.3: Histórico completo de ações e evidências de um acompanhamento

As a coordenação pedagógica,
I want ver o histórico completo de ações e evidências de um acompanhamento, mesmo depois de encerrado,
So that eu tenha transparência total do processo conduzido, sem perder informação ao longo do tempo.

**Acceptance Criteria:**

**Given** um acompanhamento com múltiplas ações e evidências ao longo do tempo
**When** a Tela de Acompanhamento é aberta
**Then** exibe todas as `FollowUpAction` em ordem cronológica e todas as `TrajectoryChange` vinculadas via `FollowUpEvidence` (RF-14, RF-20)

**Given** um acompanhamento encerrado sem nenhuma ação registrada
**When** a coordenação tenta encerrar
**Then** o sistema permite (sem bloqueio de regra de negócio), mas a Tela de Acompanhamento deixa isso visível no histórico — transparência em vez de validação forçada

**Given** a Tela de Acompanhamento
**When** navegada por teclado
**Then** abrir/fechar seções e mudar status funcionam sem mouse, com foco visível (RNF-08, UX-DR20)

**Given** um acompanhamento inexistente (link inválido ou removido)
**When** acessado
**Then** exibe mensagem factual com ação de voltar à Home (UX-DR18)

### Story 4.4: Escopo de acesso ao registro pedagógico vinculado a um acompanhamento

As a coordenação pedagógica,
I want que o registro pedagógico do estudante vinculado a um acompanhamento tenha visibilidade restrita ao responsável e à coordenação,
So that a privacidade do registro seja preparada estruturalmente para crescimento futuro do sistema, mesmo com perfil único hoje.

**Acceptance Criteria:**

**Given** uma `PedagogicalObservation` que vira fonte de evidência de um `FollowUp` (via `TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`)
**When** isso ocorre
**Then** a exibição do texto dessa observação fica escopada à união dos `responsible_user_id` de todos os `FollowUp`s que a citam como evidência (RF-22, AD-8)

**Given** mais de um acompanhamento citando o mesmo registro histórico como evidência
**When** qualquer um dos responsáveis acessa
**Then** consegue visualizar o texto — nunca exclusivo a um só responsável (AD-8)

**Given** o filtro de visibilidade
**When** aplicado
**Then** vive no mesmo método de leitura de `PedagogicalObservation` do repositório-base — nunca inline em cada endpoint (AD-11)

**Given** o `SignalEvaluator` de registro pedagógico (Epic 3)
**When** avalia sinais para detecção de convergência
**Then** continua rodando sobre o conjunto completo e não filtrado de registros — o filtro de visibilidade só afeta a exibição do texto, nunca a detecção (AD-8)

### Story 4.5: Acompanhamentos em andamento na página inicial

As a coordenação pedagógica,
I want ver na página inicial os acompanhamentos em andamento,
So that eu tenha, num único lugar, tanto as mudanças novas quanto os casos que já estou conduzindo.

**Acceptance Criteria:**

**Given** acompanhamentos com status diferente de "Encerrado"
**When** a Home é carregada
**Then** exibe um card por acompanhamento em andamento, com o selo de status e nome do estudante — completando RF-18 (mudanças recentes + acompanhamentos em andamento)

**Given** um card de acompanhamento em andamento
**When** clicado em qualquer ponto da área do card
**Then** abre a Tela de Acompanhamento correspondente (UX-DR11)

**Given** nenhum acompanhamento ativo
**When** a Home é carregada
**Then** exibe mensagem neutra ("Nenhum acompanhamento em andamento no momento"), nunca tratada como falha do sistema (UX-DR18)

**Given** um card de acompanhamento
**When** exibido
**Then** nunca mostra contagem regressiva de urgência (UX-DR11)

## Epic 5: Machine Learning Experimental

O sistema treina, versiona e avalia — offline, nunca no caminho de requisição — um modelo experimental que explora padrões associados à evasão no dataset sintético, sempre tratado como resultado de pesquisa, nunca como fato sobre o estudante real.

**FRs covered:** RF-15, RF-16, RF-17, RF-23

### Story 5.1: Pipeline de pré-processamento e treino do modelo offline

As a autor/avaliador do sistema,
I want treinar, via comando CLI offline, um modelo de ML sobre o recorte de treino do dataset sintético, usando um único Pipeline de pré-processamento + modelo,
So that eu explore se é possível reconhecer padrões associados à evasão, sem nunca treinar dentro do caminho de requisição do produto.

**Acceptance Criteria:**

**Given** o recorte `TRAIN` do dataset sintético
**When** o comando `python -m app.ml.train` é executado
**Then** treina um `Pipeline` único do scikit-learn (pré-processamento + modelo) e o serializa em um artefato versionado (RF-15, RF-17, AD-3)

**Given** o processo de treino
**When** executado
**Then** só roda via CLI offline, disparado manualmente pelo autor — nunca pelo processo web, nunca por scheduler (AD-3)

**Given** o `Pipeline` serializado
**When** reutilizado para inferência
**Then** é exatamente o mesmo objeto de pré-processamento + modelo usado no treino — nunca uma reimplementação separada do pré-processamento (RNF-03)

**Given** uma nova versão de modelo treinada
**When** persistida
**Then** recebe uma versão identificável, associada a cada predição gerada por ela (RF-17)

**Given** o recorte `TRAIN`
**When** consultado pelo treino
**Then** usa um `TrainingRepository` explicitamente diferente do repositório-base da aplicação web — nunca a mesma classe usada pelo caminho web (AD-11)

### Story 5.2: Geração de score experimental como dado de pesquisa

As a autor/avaliador do sistema,
I want gerar um score experimental a partir do modelo treinado, sempre tratado como dado experimental,
So that o resultado nunca seja confundido com um fato ou probabilidade real sobre o estudante.

**Acceptance Criteria:**

**Given** o modelo treinado e um estudante do recorte de avaliação
**When** uma predição é gerada
**Then** o score é persistido como `MLPrediction` associado à versão do modelo que o gerou (RF-15, RF-17)

**Given** o score gerado
**When** documentado ou exibido em qualquer relatório
**Then** é sempre rotulado como "dado experimental" — nunca como fato ou probabilidade real sobre o estudante (RF-16)

**Given** o score/predição
**When** qualquer endpoint ou schema de resposta do produto é inspecionado (`/students/*`, `/follow-ups/*`)
**Then** nunca aparece nele — vive atrás de um boundary interno separado (`/research/*` ou notebook) (AD-3, RF-21)

**Given** uma inferência ao vivo (se existir)
**When** solicitada
**Then** carrega o artefato uma única vez por processo (singleton em memória, `--workers 1`) — nunca recarrega ou retreina por requisição (AD-3)

### Story 5.3: Avaliação do modelo com split de dataset sem vazamento

As a autor/avaliador do sistema,
I want avaliar o modelo com precision, recall, F1 e matriz de confusão sobre o recorte de avaliação, nunca o recorte de treino,
So that a avaliação seja honesta e documentada como reconhecimento de padrões simulados, nunca validade preditiva real.

**Acceptance Criteria:**

**Given** o comando `python -m app.ml.evaluate`
**When** executado
**Then** lê o recorte `EVAL_DEMO` por inteiro, com desfecho completo, sem qualquer registro do recorte `TRAIN` (RF-23, AD-5, AD-11)

**Given** a avaliação executada
**When** o relatório é gerado
**Then** inclui obrigatoriamente precision, recall, F1 e matriz de confusão — ROC-AUC e PR-AUC como métricas adicionais (RNF-14)

**Given** o relatório de avaliação
**When** documentado
**Then** declara explicitamente o dataset sintético utilizado e o recorte (treino vs. avaliação/operação/demo), e afirma estritamente "capacidade de reconhecer os padrões simulados no dataset sintético" — nunca "validade preditiva sobre uma população escolar real" (RNF-14)

**Given** o script de avaliação
**When** lê o recorte `EVAL_DEMO`
**Then** NÃO aplica a truncagem de `as_of()` usada pelo caminho de serviço ao vivo — precisa do desfecho completo, não truncado em "hoje" (AD-5)

**Given** o recorte de treino
**When** a avaliação é executada
**Then** nenhum registro dele aparece nas métricas — ausência de vazamento de treino é verificável (RF-23)

### Story 5.4: Demonstração ao vivo truncada em "hoje" sem vazamento de futuro

As a autor/avaliador do sistema,
I want que a demonstração ao vivo do sistema use o recorte de avaliação/demo truncado na data de referência,
So that nenhuma informação posterior a "hoje" fique visível durante uma demonstração, preservando a integridade da simulação.

**Acceptance Criteria:**

**Given** o recorte `EVAL_DEMO` servido pela aplicação web (Home, Trajetória)
**When** consultado
**Then** é truncado por `as_of()` — nenhum fato datado após a referência de "hoje" (real ou `SINALIZA_DEMO_AS_OF`) é visível (RF-23, AD-5)

**Given** a variável `SINALIZA_DEMO_AS_OF`
**When** configurada para ensaio de demonstração
**Then** sobrescreve a data de referência apenas para o caminho de leitura ao vivo — documentada como mecanismo de ensaio, não uma funcionalidade de produto (AD-5)

**Given** a mesma base `EVAL_DEMO`
**When** usada simultaneamente pela avaliação de métricas (Story 5.3, sem truncagem) e pela demonstração ao vivo (com truncagem)
**Then** os dois usos coexistem sem exigir bases sintéticas separadas — só a camada de aplicação diferencia a truncagem (RF-23, AD-4)

## Epic 6: Hospedagem e Publicação do Sistema

O sistema fica hospedado numa VM sempre ativa (sem scale-to-zero, sem cron), acessível para demonstração e avaliação pela banca até 23/11/2026.

**FRs covered:** nenhum RF numerado diretamente (RNF-04, RNF-06, SM-1)

### Story 6.1: Empacotamento containerizado dos três serviços

As a autor do sistema,
I want empacotar Postgres, backend FastAPI e frontend estático/Nginx em um docker-compose único,
So that eu possa subir o sistema completo de forma reprodutível em qualquer VM.

**Acceptance Criteria:**

**Given** o `docker-compose.yml`
**When** executado (`docker compose up --build`)
**Then** sobe três serviços — Postgres, FastAPI/Uvicorn, Nginx (servindo o build estático do React + reverse proxy `/api`) (RNF-06)

**Given** os três serviços
**When** configurados
**Then** usam `restart: unless-stopped` — recuperação automática após reboot da VM ou crash do processo (AD-9)

**Given** o volume de dados do Postgres
**When** o container é recriado ou a VM reiniciada
**Then** os dados persistem em um volume Docker nomeado — só um `docker volume rm` explícito apaga, nunca um redeploy de rotina (AD-9)

**Given** o backend
**When** executado
**Then** roda com um único worker Uvicorn (`--workers 1`), consistente com o singleton de artefato de ML (AD-3, AD-9)

**Given** nenhum dos três serviços
**When** inspecionado
**Then** nenhum contém um cron/scheduler/worker assíncrono agendado — reforça RNF-06 e AD-1

### Story 6.2: Provisionamento da VM sempre ativa (Plano A/B)

As a autor do sistema,
I want provisionar uma VM Oracle Cloud Always Free sempre ativa (Ampere A1 ou, se indisponível, VM.Standard.E2.1.Micro),
So that o sistema fique disponível para desenvolvimento e demonstração sem depender de hospedagem que hiberna.

**Acceptance Criteria:**

**Given** a tentativa de provisionamento do Plano A (Ampere A1, 2 OCPU/12GB)
**When** a região OCI não tem capacidade disponível
**Then** o Plano B (`VM.Standard.E2.1.Micro`, 1 OCPU/1GB) é usado como caminho igualmente esperado, não uma contingência de último caso (AD-9)

**Given** o Plano B
**When** configurado
**Then** usa `shared_buffers` reduzido no Postgres, um único worker Uvicorn e swap habilitado (AD-9)

**Given** a VM provisionada (Plano A ou B)
**When** em operação
**Then** permanece sempre ativa, sem scale-to-zero — nenhuma dependência de um ping de keep-warm agendado (RNF-04, AD-9)

**Given** o acesso ao sistema hospedado
**When** solicitado pela banca ou pelo autor
**Then** responde às interações em até 5 segundos nas condições normais de operação (RNF-01, RNF-04)

### Story 6.3: Plano de contingência de hospedagem (Plano C) documentado

As a autor do sistema,
I want ter documentado um plano de contingência (Render + Neon + Vercel free) caso nenhuma VM Oracle provisione a tempo,
So that o prazo de entrega (23/11/2026) não dependa de um único caminho de provisão sem alternativa.

**Acceptance Criteria:**

**Given** nenhuma VM Oracle disponível até o prazo
**When** o Plano C é ativado
**Then** o backend roda em Render free, o Postgres em Neon free e o frontend estático em Vercel free — mesma topologia lógica dos Planos A/B (AD-9)

**Given** o Plano C
**When** usado para uma demonstração ao vivo
**Then** um pré-aquecimento manual (visitar a URL / health check alguns minutos antes) é realizado como ação humana pontual — nunca um job agendado, para não violar RNF-06 (AD-9)

**Given** o Plano C
**When** documentado
**Then** registra explicitamente que RNF-01 (5s) fica exposto a cold-start fora do pré-aquecimento — por isso é o Plano C, não A (AD-9)

### Story 6.4: Sistema hospedado e acessível para avaliação

As a banca avaliadora / autor do sistema,
I want acessar o sistema completo, hospedado e funcional, através de uma URL pública,
So that a avaliação e demonstração do TCC possam ocorrer até 23/11/2026 às 23:59.

**Acceptance Criteria:**

**Given** o sistema hospedado (Plano A, B ou C)
**When** acessado por uma URL pública (IP ou DNS dinâmico)
**Then** todas as telas principais (Login, Home, Trajetória, Acompanhamento, Lançamento) carregam e funcionam de ponta a ponta (SM-1)

**Given** o ambiente de deploy
**When** atualizado
**Then** o processo é SSH manual + `git pull` + `docker compose up --build` — suficiente para autor único, sem exigência de pipeline de CI/CD

**Given** o banco de dados em produção
**When** operado
**Then** há disciplina de `pg_dump` manual periódico para fora da VM antes de sessões de trabalho relevantes — não é um cron da aplicação (AD-9)

**Given** o sistema hospedado
**When** avaliado no dia da demonstração
**Then** nenhuma tela exibe score, ranking ou KPI de risco em nenhum momento (SM-3, RF-21 — verificação final cross-epic)
