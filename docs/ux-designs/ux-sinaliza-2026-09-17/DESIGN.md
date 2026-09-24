---
title: "DESIGN.md: Sinaliza"
status: final
created: 2026-09-17
updated: 2026-09-17
sources:
  - docs/prds/prd-sinaliza-2026-09-16/prd.md
  - docs/briefs/brief-sinaliza-2026-09-16/brief.md
  - docs/briefs/brief-sinaliza-2026-09-16/addendum.md
  - docs/data-model.md
  - AGENTS.md
name: Sinaliza
description: Ferramenta pedagógica de acompanhamento de trajetória escolar. Curva de crescimento, não painel de risco — clínica, calma, individual.
colors:
  bg: '#F5F9F8'
  surface: '#FFFFFF'
  text: '#1E3A36'
  text-secondary: '#57746E'
  border: '#D3E4E0'
  primary: '#2C6E63'
  attention: '#C97A3D'
  success: '#4C9A7A'
  bg-dark: '#10201D'
  surface-dark: '#16302B'
  text-dark: '#E7F3F0'
  text-secondary-dark: '#9DBDB5'
  border-dark: '#244F47'
  primary-dark: '#5FBFA9'
  attention-dark: '#E0985A'
  success-dark: '#6FC79C'
typography:
  display:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: '30px'
    fontWeight: '700'
    lineHeight: '1.25'
  heading:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: '24px'
    fontWeight: '700'
    lineHeight: '1.3'
  eyebrow:
    fontSize: '12px'
    fontWeight: '700'
    letterSpacing: '0.08em'
  body:
    fontSize: '15px'
    lineHeight: '1.65'
  body-secondary:
    fontSize: '14px'
    lineHeight: '1.6'
  caption:
    fontSize: '12.5px'
    lineHeight: '1.4'
rounded:
  sm: '6px'
  md: '10px'
  lg: '16px'
  full: '9999px'
spacing:
  content-max-width: '900px'
  section-gap: '52px'
  card-padding: '32px'
  '1': '4px'
  '2': '8px'
  '3': '12px'
  '4': '16px'
  '5': '20px'
  '6': '32px'
components:
  trajectory-chart:
    band-fill: '{colors.border}'
    band-stroke: '{colors.text-secondary}'
    line-stroke: '{colors.primary}'
    change-point-fill: '{colors.attention}'
    radius: '{rounded.lg}'
    min-hit-target: '44px'
  evidence-card:
    background: '{colors.surface}'
    border: '{colors.border}'
    radius: '{rounded.lg}'
    badge-fill: '{colors.attention}'
    badge-text: '{colors.text}'
    badge-gap: '{spacing.2}'
  calm-state-card:
    background: '{colors.surface}'
    badge-fill: '{colors.success}'
    badge-text: '{colors.text}'
    radius: '{rounded.lg}'
  factor-preocupante:
    background: '{colors.bg}'
    text: '{colors.text-secondary}'
    radius: '{rounded.lg}'
    min-hit-target: '44px'
  followup-status-pill:
    radius: '{rounded.full}'
    border: '{colors.border}'
    em-observacao-fill: '#EEF3F1'
    em-observacao-text: '{colors.text-secondary}'
    ativo-fill: '#DCEEE7'
    ativo-text: '{colors.primary}'
    aguardando-retorno-fill: '#E8E1D2'
    aguardando-retorno-text: '{colors.text-secondary}'
    encerrado-fill: '#E1EEE6'
    encerrado-text: '{colors.success}'
  button:
    background: '{colors.primary}'
    text: '{colors.surface}'
    radius: '{rounded.md}'
    min-hit-target: '44px'
  home-change-row:
    background: '{colors.surface}'
    border: '{colors.border}'
    radius: '{rounded.md}'
    marker-fill: '{colors.attention}'
  followup-card:
    background: '{colors.surface}'
    border: '{colors.border}'
    radius: '{rounded.md}'
  search-input:
    background: '{colors.surface}'
    border: '{colors.border}'
    radius: '{rounded.sm}'
    min-hit-target: '44px'
  form-field:
    background: '{colors.surface}'
    border: '{colors.border}'
    radius: '{rounded.sm}'
---

## Brand & Style

Sinaliza não é um painel de risco — é um prontuário de trajetória. A referência declarada pelo produto é a curva de crescimento pediátrico: um gráfico que qualquer pessoa reconhece do consultório do pediatra, onde a criança é plotada contra a própria curva, nunca contra a curva de outra criança. Essa referência não é só a forma do gráfico central — é a postura de toda a interface. Uma tela de Sinaliza deve dar vontade de perguntar "o que aconteceu aqui?", nunca "quem está pior?".

O registro visual escolhido é **clínico calmo**: superfícies claras, verde-azulado como única cor de marca, muito espaço em branco, uma coisa de cada vez. É o oposto deliberado de um dashboard de CRM ou de um painel de KPI — não existe grade densa de números, não existe vermelho gritando urgência, não existe ranking. Quando a trajetória de um aluno está dentro do esperado, a tela deve comunicar isso com a mesma calma com que comunica uma mudança — nunca como ausência de conteúdo.

A cor de atenção (`attention`) marca "isto merece um olhar", nunca "isto é grave" — e nunca aparece sozinha: todo estado de atenção carrega ícone e texto além da cor, para não depender de percepção cromática (RNF-08, AGENTS.md).

## Colors

- **Fundo (`{colors.bg}` `#F5F9F8` / `{colors.bg-dark}` `#10201D`)** — tom verde-azulado quase neutro, levemente mais frio que branco puro. Canvas de toda a aplicação; nunca recebe conteúdo diretamente, só camadas de superfície por cima.
- **Superfície (`{colors.surface}` `#FFFFFF` / `{colors.surface-dark}` `#16302B`)** — cards, o gráfico de trajetória, cards de evidência. Único uso: conter conteúdo que precisa se destacar do fundo.
- **Texto primário (`{colors.text}` `#1E3A36` / `{colors.text-dark}` `#E7F3F0`)** e **texto secundário (`{colors.text-secondary}` `#57746E` / `{colors.text-secondary-dark}` `#9DBDB5`)** — o secundário é usado para metadados (datas, legendas de eixo, descrições de apoio), nunca para a informação principal de uma linha. Contraste verificado (WCAG 2.1 AA, texto normal ≥4.5:1): `text-secondary` sobre `bg` = 4.79:1, sobre `surface` = 5.09:1; `text-secondary-dark` sobre `bg-dark`/`surface-dark` ≥6.9:1 nos dois casos.
- **Borda (`{colors.border}` `#D3E4E0` / `{colors.border-dark}` `#244F47`)** — divisórias de baixíssimo contraste e o preenchimento da faixa sombreada do gráfico de trajetória (a "faixa habitual" do aluno é pintada com o tom de borda, para não competir com a linha da trajetória). O preenchimento sozinho não atinge 3:1 contra `surface` (WCAG 1.4.11, objeto gráfico necessário à compreensão) — por isso a faixa recebe um contorno em `{components.trajectory-chart.band-stroke}` (`{colors.text-secondary}`), que sozinho garante o mínimo de 3:1 sem escurecer o preenchimento e sem competir com a linha da trajetória.
- **Primária (`{colors.primary}` `#2C6E63` / `{colors.primary-dark}` `#5FBFA9`)** — verde-azulado de marca. Usada na linha do gráfico de trajetória, em botões de ação primária ("Abrir acompanhamento") e em links. É a única cor "de marca" do produto — não existe uma segunda cor decorativa. Botão primário usa texto `{colors.surface}` sobre fundo `{colors.primary}` (contraste 6.1:1 light / texto `{colors.bg-dark}` sobre `{colors.primary-dark}` em dark), nunca o inverso.
- **Atenção (`{colors.attention}` `#C97A3D` / `{colors.attention-dark}` `#E0985A`)** — laranja terroso, deliberadamente **não vermelho**. Marca o ponto de mudança no gráfico e o selo de "mudança recente" na Home. Sempre acompanhada de ícone e texto (ex.: um símbolo de atenção + a palavra "mudança"), nunca comunicada só pela cor (RNF-08). Nunca usada para classificar o aluno como pessoa — só para marcar um ponto ou um card de evidência. **Regra de contraste do selo:** nem branco nem `{colors.text}` atingem 4.5:1 sobre o preenchimento saturado de `attention` (3.32:1 e 3.70:1) — por isso o texto do rótulo nunca fica dentro da área preenchida; o preenchimento vira um ícone/círculo pequeno (`badge-fill`) ao lado do rótulo, e o rótulo em si usa `{components.evidence-card.badge-text}` (`{colors.text}`) sobre `{colors.surface}`.
- **Sucesso (`{colors.success}` `#4C9A7A` / `{colors.success-dark}` `#6FC79C`)** — usada com moderação: recuperação de um sinal, encerramento de um acompanhamento, e o selo do estado "sem novidades recentes". Nunca é um "score bom" — é sempre atrelada a um evento (recuperou, encerrou), nunca a uma nota permanente do aluno. Mesma regra de contraste do selo de atenção acima: rótulo de texto sempre em `{colors.text}` sobre `{colors.surface}`, `success` restrito ao ícone.

Evitar: vermelho em qualquer variação (mesmo para "erro" de formulário — usar `attention` com ícone e texto), gradientes, qualquer cor adicional de marca além da primária, texto de rótulo diretamente sobre um preenchimento saturado (`attention`/`success` não atingem 4.5:1 com nenhum texto), e qualquer paleta que crie uma escala visual de "pior para melhor" aluno a aluno — a paleta descreve estados de uma trajetória individual, nunca posições relativas entre alunos.

## Typography

Pilha de fontes de sistema (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`) em todos os papéis — sem serifa, sem fonte de marca customizada. A ferramenta pedagógica não precisa de uma voz tipográfica decorativa; precisa ser lida rápido e sem ambiguidade por quem está entre uma aula e outra.

- `{typography.display}` (30px/700) — título da tela de trajetória do estudante (nome do aluno). Aparece uma vez por tela, sempre centralizado.
- `{typography.heading}` (24px/700) — título da Home e da tela de acompanhamento.
- `{typography.eyebrow}` (12px/700, letter-spacing 0.08em, maiúsculas) — rótulo de seção acima de cada bloco ("TRAJETÓRIA", "EVIDÊNCIA DA MUDANÇA", "REGISTROS"). É o principal recurso de hierarquia entre seções, no lugar de bordas ou cor de fundo.
- `{typography.body}` (15px/1.65) — texto de evidência, descrições, corpo de registro pedagógico. Line-height generoso de propósito: são textos que a coordenação lê com atenção, não escaneia.
- `{typography.body-secondary}` (14px/1.6) — subtítulos e texto de apoio.
- `{typography.caption}` (12.5px) — datas, breadcrumbs, legendas de eixo do gráfico.

Nenhum peso de fonte abaixo de 400 (regular) é usado — não há necessidade de texto "light" numa interface que já é, por design, pouco densa.

## Layout & Spacing

Coluna única, centralizada, largura máxima de `{spacing.content-max-width}` (900px) — reforça a decisão de densidade "calma, uma coisa por vez" em vez de um layout multi-coluna tipo dashboard. Sem sidebar de navegação persistente: com 3 telas principais (Home, trajetória, acompanhamento), a navegação é simples o suficiente para não precisar de chrome permanente.

Ritmo vertical generoso entre seções (`{spacing.section-gap}`, 52px) — gráfico, depois evidência, depois fator preocupante (se houver), depois linha do tempo, depois ação, cada um claramente separado, nunca comprimido para caber "tudo" na primeira dobra. Dentro de um card, padding generoso (`{spacing.card-padding}`, 32px).

Responsivo para desktop e tablet (RNF-02, RNF-10): a coluna única de 900px já degrada bem para tablet sem breakpoint especial; abaixo disso, os cards perdem padding lateral mas mantêm a mesma ordem vertical de seções.

## Elevation & Depth

Sem sombra como recurso de hierarquia. Cards se distinguem do fundo só pelo contraste tonal `{colors.surface}` sobre `{colors.bg}` e por uma borda de baixíssimo contraste (`{colors.border}`). Hierarquia vem de espaçamento e do rótulo `eyebrow`, não de elevação — um dashboard de risco usa sombra e camadas para simular urgência (cards "flutuando" pedindo atenção); Sinaliza evita esse vocabulário deliberadamente.

## Shapes

`{rounded.sm}` (6px) para elementos pequenos (badges de ícone, inputs). `{rounded.md}` (10px) para blocos de apoio (o texto de racional/nota do "fator preocupante"). `{rounded.lg}` (16px) para todos os cards principais — gráfico de trajetória, card de evidência, card de estado calmo. `{rounded.full}` (pill) reservado exclusivamente para os selos de status de acompanhamento (Em observação · Ativo · Aguardando retorno · Encerrado) — o único lugar da interface onde uma forma de pílula aparece, para que o olho aprenda a associar pílula = estado de processo humano, nunca a associe a "nível de risco".

Toda área clicável tem alvo de toque mínimo de 44×44px CSS (`min-hit-target` em `{components.trajectory-chart}`, `{components.factor-preocupante}`, `{components.button}`, `{components.search-input}`), mesmo quando o glifo visível é menor — padding invisível preenche a diferença. Relevante porque o produto é responsivo para tablet (RNF-02, RNF-10), não só desktop com mouse de precisão.

## Components

- **Gráfico de trajetória** (`{components.trajectory-chart}`) — peça central da tela de trajetória do estudante. Faixa preenchida em `{colors.border}` com contorno em `{components.trajectory-chart.band-stroke}` representando a "faixa habitual" calculada sobre o próprio histórico do aluno (nunca sobre a turma); linha em `{colors.primary}` traçando a trajetória real; ponto de mudança marcado em `{colors.attention}` com rótulo de texto ao lado (nunca só a cor), alvo de toque `{components.trajectory-chart.min-hit-target}` mesmo sendo um glifo pequeno. Cantos `{rounded.lg}`. Eixo X sempre em bimestres; eixo Y nunca rotulado como "score" ou "risco" — rotulado com o indicador real (frequência, notas, atividades).
- **Card de evidência** (`{components.evidence-card}`) — aparece abaixo do ponto de mudança. Cabeçalho com selo (`{components.evidence-card.badge-fill}` restrito a um ícone/círculo pequeno; o rótulo de texto do selo em `{components.evidence-card.badge-text}` sobre `{colors.surface}`, nunca dentro da área preenchida) e descrição em `{typography.body}` (ver `EXPERIENCE.md.Component Patterns` para a regra de exibição da lista de registros-fonte, RNF-11).
- **Fator preocupante** (`{components.factor-preocupante}`) — visualmente mais discreto que o card de evidência: fundo igual ao canvas (`{colors.bg}`, não `{colors.surface}`), sem selo colorido, texto em `{colors.text-secondary}`. A discrição visual é intencional — é um sinal que ainda não convergiu, não deve competir visualmente com uma mudança confirmada. Cabeçalho expansível tem alvo de toque `{components.factor-preocupante.min-hit-target}`.
- **Card de estado calmo** (`{components.calm-state-card}`) — o que a coordenação vê quando não há mudança recente para um aluno. Selo em ícone `{colors.success}` + rótulo em `{components.calm-state-card.badge-text}` (ex. "dentro da faixa habitual"), nunca um espaço vazio ou mensagem de erro. Este estado precisa parecer tão intencional e cuidadoso quanto o estado com mudança — é a maioria dos casos, não uma exceção.
- **Selo de status de acompanhamento** (`{components.followup-status-pill}`) — pílula com os 4 estados fechados, cada um com fundo e texto próprios além de ícone: **Em observação** (`em-observacao-fill`/`em-observacao-text`, tom neutro — acabou de ser aberto), **Ativo** (`ativo-fill`/`ativo-text`, tinta de `{colors.primary}` — em condução), **Aguardando retorno** (`aguardando-retorno-fill`/`aguardando-retorno-text`, neutro quente — parado esperando algo externo), **Encerrado** (`encerrado-fill`/`encerrado-text`, tinta de `{colors.success}` — concluído). Nenhum dos 4 usa `{colors.attention}` nem qualquer tom que sugira "alto risco"; o conjunto fechado nunca ganha um quinto estado ad-hoc tipo "crítico". Cada pílula sempre traz o rótulo de texto do estado, nunca só cor.
- **Linha do tempo de registros** — lista vertical simples (data em `{typography.caption}`, descrição em `{typography.body}`, tag de tipo em `{typography.caption}` abaixo), sem ícones de sentimento, sem cor por tipo de registro. Nenhum estado de hover/seleção.
- **Linha de mudança recente** (`{components.home-change-row}`) — linha da Home: nome do aluno em `{typography.body}`, descrição curta da mudança em `{typography.body-secondary}`, marcador `{components.home-change-row.marker-fill}` (ícone, não bolinha de cor sozinha) à esquerda. Toda a linha é clicável, alvo de toque cobre a altura inteira, não só o texto.
- **Card de acompanhamento em andamento** (`{components.followup-card}`) — usa `{components.followup-status-pill}` para o status e nome do aluno em `{typography.body}`. Mesma regra de clique de área total da linha de mudança recente.
- **Busca de aluno** (`{components.search-input}`) — campo de texto padrão com label visível (não só placeholder), alvo de toque `{components.search-input.min-hit-target}` de altura.
- **Formulário de ação/registro** (`{components.form-field}`) — campos de texto/textarea com label associado sempre visível acima do campo (nunca só placeholder, RNF-08); botão de envio segue a spec de **Botão** abaixo.
- **Botão** (`{components.button}`) — ação primária (ex. "Abrir acompanhamento", "Registrar ação") em `{colors.primary}` com texto `{colors.surface}`, cantos `{rounded.md}`, alvo de toque `{components.button.min-hit-target}`. Ação secundária/cancelar usa contorno em `{colors.border}` com texto `{colors.text}`, mesmo fundo `{colors.surface}` — nunca uma segunda cor de marca.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Uma cor de marca (`primary`) + uma cor de atenção não-vermelha + uma de sucesso, e parar por aí | Adicionar uma segunda cor de marca ou uma escala de cor por "nível de risco" |
| Toda informação de atenção com ícone + texto, além da cor (RNF-08) | Comunicar mudança/risco só pela cor |
| Gráfico de trajetória sempre com faixa do próprio histórico do aluno | Gráfico com eixo comparando alunos entre si, percentil de turma, ou ranking |
| Estado "sem novidades" com o mesmo cuidado visual do estado com mudança | Tela vazia, cinza, ou com aparência de erro quando não há mudança |
| Pílula reservada só para status de acompanhamento | Pílula ou badge para "nível" de aluno, score, ou prioridade |
| Uma coisa por vez, ritmo vertical generoso | Grade densa tipo dashboard/planilha de 200 alunos na mesma tela |
| Rótulo `eyebrow` como principal recurso de hierarquia | Sombra ou elevação para simular urgência |
