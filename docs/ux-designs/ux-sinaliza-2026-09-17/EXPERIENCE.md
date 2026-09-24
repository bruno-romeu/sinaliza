---
title: "EXPERIENCE.md: Sinaliza"
status: final
created: 2026-09-17
updated: 2026-09-17
sources:
  - docs/prds/prd-sinaliza-2026-09-16/prd.md
  - docs/briefs/brief-sinaliza-2026-09-16/brief.md
  - docs/briefs/brief-sinaliza-2026-09-16/addendum.md
  - docs/data-model.md
  - AGENTS.md
---

# Sinaliza — Experience Spine

## Foundation

Web responsivo, desktop + tablet (RNF-02, RNF-10) — sem app nativo, sem versão mobile dedicada. Nenhum design system citado no PRD (stack é React/Next.js "do zero", AGENTS.md); `DESIGN.md` é a referência de identidade visual desta spine. Perfil único de usuário (Coordenação Pedagógica) — não há variação de experiência por papel. Sem modo offline: RNF-04 dispensa disponibilidade 24/7, mas não define comportamento offline explícito; tratar como fora de escopo do MVP.

RF-22 (escopo de acesso ao registro pedagógico por `responsible_user_id`) não gera nenhum estado de UI visível hoje: com um único perfil ativo, todo usuário autenticado é a mesma Coordenação Pedagógica, então a restrição estrutural existe no backend (preparação para crescimento futuro do sistema) sem aparecer como controle de acesso na interface — nenhuma tela precisa de estado "sem permissão" no MVP.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Login | Abertura do app | Autenticação login/senha (RF-01) |
| Home | Login bem-sucedido | Mudanças recentes + acompanhamentos em andamento (RF-18) |
| Trajetória do Estudante | Home (linha de mudança) · busca de aluno | Linha do tempo, gráfico de trajetória, evidências, registros pedagógicos (RF-19) |
| Tela de Acompanhamento | Home (lista em andamento) · Trajetória (botão "Abrir acompanhamento") | Status, ações registradas, evidências vinculadas (RF-20) |
| Lançamento (chamada / nota / entrega / observação) | Ação global de navegação · atalho contextual na Trajetória do Estudante | Registro dos fatos observáveis do dia a dia (RF-03 a RF-09) |

→ Composition reference: `mockups/home.html`, `mockups/trajetoria-do-estudante.html`, `mockups/acompanhamento.html`. Ilustram layout e estados das 3 telas principais; esta spine (e `DESIGN.md`) vence em qualquer conflito com os mocks.

`[ASSUMPTION]` O PRD define RF-18/19/20 como as 3 "telas principais" (único escopo explícito do RNF-08 de acessibilidade) mas não desenha a superfície de Lançamento. Tratada aqui como formulários leves e utilitários — cada um com labels associados aos campos (consequência já exigida pelo próprio RNF-08), mas sem o mesmo investimento de design das 3 telas principais. Revisitar se a banca ou o autor quiserem elevá-la a tela principal.

Sem navegação lateral persistente (ver `DESIGN.md.Layout & Spacing`) — com 5 superfícies apenas, um cabeçalho simples com o nome do usuário autenticado e um link de volta à Home basta.

## Voice and Tone

Microcopy. Voz de marca e postura estética vivem em `DESIGN.md.Brand & Style`.

| Do | Don't |
|---|---|
| "Participou menos das discussões nas últimas duas aulas e não entregou a atividade desta semana." | "Está desmotivado." / "É aluno de risco." |
| "Mudança recente: queda de frequência e aumento de atividades pendentes — 3º bimestre." | "82% de chance de evasão." / "Aluno de alto risco." |
| "Dentro da faixa habitual." | "Sem risco." / "Tudo OK, pode ignorar." |
| "Fator preocupante — ainda não confirmado." | "Alerta." / "Atenção urgente." |
| "Acompanhamento encerrado." | Qualquer rótulo equivalente a "caso resolvido" com tom de conclusão definitiva sobre a pessoa |
| Frases curtas, factuais, sempre referenciando o registro-fonte | Qualquer frase que soe como diagnóstico, previsão ou julgamento sobre o estudante |

## Component Patterns

Comportamental. Especificação visual vive em `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Linha de "mudança recente" | Home | Clique abre a Trajetória do Estudante direto na seção de evidência daquela mudança. Nunca ordenada por "gravidade" ou score — ordenada por data de detecção. |
| Card de acompanhamento em andamento | Home | Clique abre a Tela de Acompanhamento. Mostra status atual (pílula) e nome do aluno; nunca mostra contagem regressiva de urgência. |
| Gráfico de trajetória | Trajetória do Estudante | Estático por padrão (sem zoom/pan no MVP); ponto de mudança é um controle focável (`role="button"`, `tabindex="0"`), ativável por clique ou Enter/Espaço, com foco visível — rola até o card de evidência correspondente. O SVG tem `role="img"` com nome acessível resumindo a tendência, e a série bruta (bimestre × valor × faixa habitual min/max) fica disponível como tabela equivalente via toggle "ver como tabela" ou elemento `sr-only`, para o leitor de tela inspecionar a curva além dos pontos já destacados. |
| Card de evidência | Trajetória do Estudante · Tela de Acompanhamento | Sempre expandido (nunca colapsado atrás de "ver mais") — a lista de registros-fonte é a própria evidência, não um detalhe opcional. Reaproveitado na Tela de Acompanhamento para mostrar a(s) `TrajectoryChange` que originaram o caso, com um link "Ver na trajetória de [aluno]" de volta à Trajetória do Estudante. |
| Fator preocupante | Trajetória do Estudante | Cabeçalho é um controle focável (`role="button"`, `tabindex="0"`, `aria-expanded`) ativável por clique ou Enter/Espaço para expandir o(s) registro(s) que o originaram; fechado por padrão, mas nunca escondido atrás de outra tela; foco permanece no cabeçalho do card após alternar. |
| Selo de status de acompanhamento | Tela de Acompanhamento | Clique abre um seletor com só os 4 estados fechados (Em observação · Ativo · Aguardando retorno · Encerrado) — implementado como `<select>` nativo (herda semântica de teclado de graça) ou, se customizado, seguindo o padrão WAI-ARIA APG de listbox (Esc fecha, setas navegam entre as 4 opções, foco retorna ao gatilho após a escolha). Nunca um campo de texto livre para status. |
| Formulário de ação/registro | Tela de Acompanhamento · Lançamento (observação) | Campo de texto livre + botão de envio ("Registrar ação" / "Salvar observação"); botão desabilitado enquanto o campo estiver vazio — não existe registro em branco. Toda ação registrada entra no histórico (RF-14), nunca substitui uma anterior. |
| Busca de aluno | Home (campo de busca) | Filtra por nome ou turma entre os ~200 estudantes; resultados renderizam como lista de itens focáveis por Tab abaixo do campo, com `aria-live="polite"` anunciando a contagem de resultados para leitor de tela; ver `State Patterns` para busca sem resultado. Necessário porque a Home não lista todos os alunos, só os que têm mudança recente ou acompanhamento ativo — a busca é a única forma de chegar a um aluno "tranquilo". |
| Linha do tempo de registros | Trajetória do Estudante | Estático, somente leitura — sem clique, sem expansão, sem interação além do scroll da página. |
| Botão (`DESIGN.md.button`) | Todas as telas | Semântica nativa de `<button>`; foco sempre visível; alvo de toque mínimo de 44×44px mesmo quando o rótulo visual é curto. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Sem mudanças recentes | Home | Nunca uma lista vazia genérica — mensagem explícita de que não há mudanças a revisar hoje, com contagem de acompanhamentos ativos ainda visível. |
| Aluno dentro da faixa habitual | Trajetória do Estudante | Card de estado calmo (`DESIGN.md.calm-state-card`) no lugar do card de evidência — nunca uma tela "vazia". |
| Sem acompanhamentos ativos | Home | Mensagem neutra ("Nenhum acompanhamento em andamento no momento"), nunca tratada como falha do sistema. |
| Busca sem resultado | Home (busca de aluno) | "Nenhum estudante encontrado com esse nome/turma." Sem sugestões automáticas. |
| Carregando | Todas | Skeleton simples nos blocos de conteúdo; nunca spinner de tela cheia (RNF-01: resposta em até 5s torna esse estado raro por design). |
| Erro de carregamento | Todas | Mensagem factual ("Não foi possível carregar os dados agora.") com ação de tentar novamente; nunca oculta o motivo atrás de um ícone genérico. |
| Tentativa de registro duplicado | Lançamento (chamada) | Mensagem factual junto ao campo ("Já existe registro de presença para este aluno, turma e data.") — reforça RF-04/RNF-11 (duplicidade impedida em nível de banco); nunca falha silenciosa. |
| Confirmação de salvamento | Lançamento | Confirmação textual breve após salvar (ex. "Registro salvo."), sem modal bloqueante — a coordenação continua lançando o próximo registro sem interrupção. |
| Aluno/acompanhamento não encontrado | Trajetória do Estudante · Tela de Acompanhamento | Link inválido ou registro removido: mensagem factual com ação de voltar à Home, nunca uma tela em branco. Tratamento simples (sem página 404 dedicada) é suficiente para o MVP acadêmico. |
| Score/ML | Nenhuma | Não existe estado de UI para o score experimental — ele nunca é renderizado em nenhuma tela do produto (RF-16, RF-21, RNF-14). Isso não é um estado "escondido" a implementar, é a ausência deliberada de um componente. |

## Interaction Primitives

- Clique/tap para navegar e para expandir conteúdo colapsado (fator preocupante). Sem gestos customizados — é uma ferramenta administrativa de desktop/tablet, não um app touch-first.
- Mudança de status de acompanhamento é sempre uma escolha explícita dentro do conjunto fechado de 4 estados — nunca inferida automaticamente a partir de sinais da trajetória (reforça RNF-11: nenhum estado equivalente a "alto risco").
- Toda ação destrutiva ou irreversível (ex.: encerrar acompanhamento) pede confirmação simples antes de efetivar.
- Navegação completa por teclado nas 3 telas principais (RNF-08): tab order segue a ordem de leitura (gráfico → evidência → fator preocupante → linha do tempo → ação), sem armadilhas de foco.
- **Banned:** contagem regressiva/urgência, notificação push ou e-mail automático, qualquer interação que ordene ou compare alunos entre si (ranking, drag-to-prioritize, etc.), auto-refresh que reordene a lista da Home enquanto a coordenação está lendo.

## Accessibility Floor

Comportamental. Contraste visual vive em `DESIGN.md`.

- WCAG 2.1 AA como referência (não certificação formal) nas 3 telas principais — Home, Trajetória do Estudante, Tela de Acompanhamento (RNF-08).
- Navegação completa por teclado nessas 3 telas, incluindo abrir/fechar o card de fator preocupante e mudar o status de acompanhamento sem mouse.
- Todo formulário de lançamento (chamada, nota, entrega, observação) com label associado a cada campo — nenhum campo identificado só por placeholder.
- Nenhuma informação de mudança de trajetória comunicada exclusivamente por cor — o ponto de mudança no gráfico, o selo de "mudança recente" e a cor de atenção sempre carregam ícone e/ou texto junto (AGENTS.md, RNF-08).
- Elementos interativos com foco visível (não suprimir o outline padrão sem substituto equivalente).
- Gráfico de trajetória (conteúdo não-textual, WCAG 1.1.1) tem alternativa textual/tabular equivalente — ver `Component Patterns.Gráfico de trajetória`. Sem essa alternativa, a curva em si (não só os pontos de mudança já destacados em texto) fica inacessível ao leitor de tela.
- Toda área clicável com alvo de toque mínimo de 44×44px CSS (`DESIGN.md.min-hit-target`).
- Mensagens de erro de validação em formulários usam `aria-describedby` apontando para o campo — nunca só cor/ícone isolado, mesma lógica do resto do produto.

## Key Flows

### Fluxo 1 — A coordenação percebe uma mudança convergente na Home (UJ-1)

1. A coordenação abre o sistema no início do dia, autenticada.
2. A Home exibe a lista de mudanças recentes e os acompanhamentos em andamento.
3. Uma linha mostra um estudante cuja frequência caiu e cujas atividades entregues diminuíram no mesmo bimestre.
4. Ela clica na linha, abrindo a Trajetória do Estudante direto na evidência daquela mudança.
5. Revisa a linha do tempo e os registros de origem apontados pelo card de evidência.
6. Clica em "Abrir acompanhamento".
7. **Climax:** o acompanhamento passa a existir com status "Em observação", já vinculado às evidências que o justificaram — a decisão de acompanhar nasce da evidência, não de um número.

Variação: a coordenação revisa a mesma evidência e decide não abrir acompanhamento agora — ela simplesmente sai da tela; nada é registrado como "recusado" ou "ignorado"; a mudança continua disponível para revisão futura.

### Fluxo 2 — A coordenação registra uma observação pedagógica no dia a dia (UJ-2)

1. Durante a rotina de aula, a coordenação (no papel acumulado de professor) acessa o Lançamento a partir do atalho contextual na Trajetória do Estudante (ou da ação global de navegação).
2. Registra uma observação em texto livre sobre um estudante — um fato observável, não uma classificação subjetiva (ver `Voice and Tone`).
3. **Climax:** o registro é salvo e passa a estar disponível como evidência potencial para futuras mudanças de trajetória detectadas para aquele estudante — sem que a coordenação precise fazer nada além de descrever o que observou.

Variação: se o texto da observação fica vazio, o botão de salvar permanece desabilitado (ver `Component Patterns.Formulário de ação/registro`) — não existe registro pedagógico em branco.

### Fluxo 3 — A coordenação conduz um acompanhamento até o encerramento (UJ-3)

1. A coordenação abre a Tela de Acompanhamento de um caso ativo (a partir da Home ou da Trajetória do Estudante).
2. Registra uma ação tomada no formulário de ação.
3. Observa, ao longo do tempo, recuperação nos sinais do estudante (visível se ela voltar à Trajetória do Estudante).
4. Volta à Tela de Acompanhamento e altera o status para "Encerrado" (confirmação simples).
5. **Climax:** o histórico completo de ações e evidências permanece acessível — encerrar não apaga nem esconde o processo, só marca que ele terminou.

Falha/variação: se a coordenação tentar encerrar sem nenhuma ação registrada, o sistema permite (não há bloqueio de regra de negócio no MVP), mas a Tela de Acompanhamento deixa isso visível no histórico — transparência em vez de validação forçada.
