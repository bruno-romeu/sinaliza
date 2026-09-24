# Spine Pair Review — Sinaliza

## Overall verdict

O par cobre mecanicamente as três jornadas e as três telas principais do PRD, os tokens de cor/tipografia/forma resolvem sem exceção, e a ordem canônica de seções está correta em ambos os arquivos — a espinha é utilizável como contrato hoje. O problema mais sério é um erro de terminologia herdado: EXPERIENCE.md nomeia o gráfico central como "faixas de percentil" (estatística populacional), enquanto DESIGN.md e o mockup confirmado (`.working/direction-espacoso.html`) implementam uma única faixa do próprio histórico do aluno — se um consumidor downstream ler só a IA table, corre o risco de implementar exatamente a comparação entre alunos que o PRD proíbe explicitamente. Fora isso, a cobertura de componentes é o ponto mais fraco: metade dos componentes usados em algum flow (linha de mudança recente, card de acompanhamento, busca, formulário de ação, botão, linha do tempo) não tem par visual+comportamental nos dois arquivos.

## 1. Flow coverage — adequate

Checado: as três Key Flows mapeiam 1:1 para UJ-1/UJ-2/UJ-3 com rótulo explícito, protagonista consistente ("a coordenação pedagógica"), passos numerados e um beat de **Climax** cada. RF-18/19/20 aparecem todos na Information Architecture com citação de RF. RF-11/RNF-11 (evidência rastreável) e RF-21 (nunca ranking) reaparecem corretamente nos climaxes e no Component Patterns.

### Findings
- **medium** Fluxo 1 (UJ-1) e Fluxo 2 (UJ-2) não têm caminho de falha/variação, enquanto o Fluxo 3 tem um parágrafo dedicado ("Falha/variação: se a coordenação tentar encerrar..."). Os exemplos de referência (Drift, Quill) dão a toda Key Flow uma linha de falha, mesmo quando trivial (EXPERIENCE.md, `Fluxo 1 — ...` linhas 94–102 e `Fluxo 2 — ...` linhas 104–108). *Fix:* acrescentar uma linha de falha/variação a cada um — ex. Fluxo 1: "a coordenação revisa a evidência e decide não abrir acompanhamento agora"; Fluxo 2: "observação salva com texto vazio/mínimo é bloqueada ou aceita como está?".
- **low** RF-22 (escopo de acesso ao registro pedagógico por `responsible_user_id`) não é mencionado em nenhum dos dois arquivos, embora seja um RF nomeado do PRD com efeito potencial na Tela de Acompanhamento. O PRD já justifica a omissão ("hoje há um único perfil, então na prática todo usuário autenticado é coordenação pedagógica"), mas essa justificativa não foi herdada para a spine (EXPERIENCE.md, ausente de `Foundation` e `Tela de Acompanhamento`). *Fix:* uma linha em `Foundation` explicando por que RF-22 não gera nenhum estado de UI visível hoje, para que o próximo consumidor não precise voltar ao PRD para descobrir isso.

## 2. Token completeness — adequate

Checado: todo token de `colors`, `typography`, `rounded`, `spacing` e `components` do frontmatter de DESIGN.md contra toda referência `{path.to.token}` no corpo — todas resolvem, sem token órfão. Todo par light/dark de cor tem hex explícito nos dois modos (`bg`/`bg-dark`, `primary`/`primary-dark`, etc.).

### Findings
- **medium** Nenhuma meta de contraste (razão numérica) é declarada para as combinações de cor que carregam a exigência de acessibilidade explícita do produto (RNF-08/Accessibility Floor cita WCAG 2.1 AA como referência) — ex. `text-secondary` sobre `bg`, texto/ícone sobre `attention`/`success` nos badges, `primary` como cor de botão. DESIGN.md só usa linguagem qualitativa ("baixíssimo contraste") (DESIGN.md, Colors, linhas 105–113). *Fix:* declarar a razão de contraste alvo (ou o valor calculado) para cada par carregado — pelo menos texto-secundário/fundo e texto-sobre-badge nos dois modos.
- **low** A escala de espaçamento numérica (`spacing['1']` a `spacing['6']`, 4px–32px) está definida no frontmatter mas nunca é referenciada em nenhuma seção do corpo — só os tokens nomeados (`content-max-width`, `section-gap`, `card-padding`) são usados (DESIGN.md, frontmatter linhas 64–69). *Fix:* referenciar a escala num uso real (ex. gap interno de badge/ícone) ou removê-la do frontmatter.

## 3. Component coverage — thin

Checado: todo nome de componente citado em qualquer lugar de DESIGN.md ou EXPERIENCE.md, verificando par visual (`DESIGN.md.Components`) + comportamental (`EXPERIENCE.md.Component Patterns`). De ~9 componentes distintos usados nos flows, só 4 têm as duas metades (Gráfico de trajetória, Card de evidência, Fator preocupante, Selo de status de acompanhamento).

### Findings
- **high** "Linha de mudança recente" e "Card de acompanhamento em andamento" — os dois componentes que compõem toda a Home — têm linha comportamental em EXPERIENCE.md.Component Patterns mas nenhuma entrada visual em DESIGN.md.Components (EXPERIENCE.md linhas 53–54; ausente de DESIGN.md linhas 144–151). *Fix:* adicionar entrada mínima de anatomia visual para os dois (mesmo que componha tokens já existentes, ex. `followup-status-pill` + `typography.body`).
- **medium** "Busca de aluno" e "Formulário de ação/registro" têm linha comportamental em EXPERIENCE.md mas nenhuma entrada em DESIGN.md.Components — só a nota genérica de `rounded.sm` para inputs em Shapes cobre parcialmente (EXPERIENCE.md linhas 59–60). *Fix:* mesma recomendação — anatomia mínima de input/textarea/botão de envio.
- **medium** "Linha do tempo de registros" tem spec visual completa em DESIGN.md.Components (linha 151) mas nenhuma linha em EXPERIENCE.md.Component Patterns — não há regra comportamental declarada (é clicável? expande? é só leitura?). *Fix:* adicionar linha, mesmo que seja "estático, sem interação".
- **low** O botão de ação primária/secundária ("Abrir acompanhamento", "Registrar ação"), usado nos três flows e citado em DESIGN.md.Colors, nunca recebe uma entrada dedicada em nenhum dos dois `Components`/`Component Patterns` — só existe em prosa solta. *Fix:* uma linha de Button cobriria os dois arquivos de uma vez.

## 4. State coverage — adequate

Checado: as 4 superfícies principais (Home, Trajetória, Acompanhamento, Lançamento) percorridas contra vazio/carregamento frio/erro/offline/permissão negada. Offline está corretamente declarado fora de escopo em `Foundation` (não precisa de estado). `Score/ML` está corretamente listado como ausência deliberada de componente, não estado escondido.

### Findings
- **medium** A superfície de Lançamento (RF-03 a RF-09, incluindo RF-04 "impedir duplicidade de registro" e RNF-11 "duplicidade impedida em nível de banco") não tem nenhuma linha em `State Patterns` — não há estado de erro de validação, tentativa de duplicidade ou confirmação de salvamento definido para os formulários que implementam 7 requisitos funcionais (EXPERIENCE.md, State Patterns, linhas 64–72; Lançamento só aparece na IA table e no `[ASSUMPTION]`). *Fix:* adicionar ao menos um estado de "tentativa de registro duplicado" (liga direto a RF-04/RNF-11) e um de confirmação de salvamento.
- **low** Não há estado de "aluno/acompanhamento não encontrado" (deep link inválido) para Trajetória do Estudante ou Tela de Acompanhamento — provavelmente aceitável para MVP acadêmico, mas não está declarado como decisão. *Fix:* uma linha rápida decidindo tratamento (404 simples vs. redirecionar à Home) evitaria a pergunta na implementação.

## 5. Visual reference coverage — pending (not a failure)

Checado: `mockups/`, `wireframes/`, `imports/` no diretório da spine. `imports/` existe e está vazio. Não há `mockups/` nem `wireframes/`. Quatro artefatos de exploração vivem em `.working/` (`color-themes-1.html`, `direction-compacto.html`, `direction-espacoso.html`, `direction-editorial-clinico.html`) — confirmados pelo `.memlog.md` como a paleta "clínico calmo" e a direção "espaçoso" escolhidas pelo usuário, mas nenhum dos dois arquivos de spine cita esses artefatos.

### Findings
- **low** Nenhuma linha "→ Composition reference" (padrão usado nos exemplos Drift/Quill) aponta para `.working/direction-espacoso.html`, mesmo ele já existindo e resolvendo ambiguidades visuais (ex. a única faixa do gráfico, ver achado crítico da seção 7) antes do Finalize. Não é falha nesta etapa — os artefatos ainda não foram promovidos — mas fica pendente. *Fix:* no Finalize, promover `direction-espacoso.html` para `mockups/` e adicionar a linha de referência na Information Architecture de EXPERIENCE.md.

## 6. Bloat & overspecification — strong

DESIGN.md carrega voz editorial de forma proporcional (Brand & Style em prosa, mas sem exceder o necessário para fixar a postura visual); EXPERIENCE.md permanece seco e tabular, sem narrativa decorativa — mesmo os beats de "Climax" nos Key Flows carregam uma decisão real (ex. "a decisão de acompanhar nasce da evidência, não de um número"), não são só cor local. Nenhuma seção parece supérflua para um consumidor downstream.

### Findings
- **low** Redundância pontual entre `Colors` e `Do's and Don'ts` (ex. "não existe uma segunda cor de marca" aparece nos dois lugares) — mas essa é a função esperada da tabela Do's/Don'ts (compressão de regras já ditas), não bloat real.

## 7. Inheritance discipline — thin

Checado: frontmatter `sources` resolvendo para arquivos reais; nomes de UJ/RF idênticos ao PRD; glossário ("Coordenação Pedagógica", nunca "professor" como perfil) consistente; nomes de componente e referências de token cruzando entre os dois arquivos.

### Findings
- **critical** A linha da Information Architecture para "Trajetória do Estudante" nomeia o gráfico central como **"gráfico de faixas de percentil"** (EXPERIENCE.md, linha 26). "Percentil" é estatística populacional — mas o componente `trajectory-chart` de DESIGN.md (linhas 108, 146), o mockup confirmado como escolhido (`.working/direction-espacoso.html`, `.chart-band`/`--band`, linhas 6–15 e 121) e o princípio central do PRD (§1: "o aluno é sempre comparado contra o próprio histórico, nunca contra os colegas") definem consistentemente **uma única faixa da própria "faixa habitual" do aluno**, não múltiplas bandas de percentil calculadas contra a turma/população. Se um arquiteto ou desenvolvedor implementar a IA table literalmente, o resultado violaria o princípio ético-técnico mais importante do produto. *Fix:* trocar "gráfico de faixas de percentil" por "gráfico de faixa habitual" (ou o termo exato de DESIGN.md) na linha 26 de EXPERIENCE.md.
- Verificado e correto: `sources` de ambos os arquivos apontam para `docs/prds/prd-sinaliza-2026-09-16/prd.md`, `docs/briefs/brief-sinaliza-2026-09-16/brief.md` + `addendum.md`, `docs/data-model.md` e `AGENTS.md` — todos existem no disco. UJ-1/UJ-2/UJ-3 e RF-18/19/20/RNF-08/RNF-11 usados com numeração literal do PRD. "Coordenação Pedagógica" é o único nome de perfil usado; "professor" só aparece descritivamente ("no papel acumulado de professor"), exatamente como o próprio PRD (§2.4) permite.

## 8. Shape fit — strong

DESIGN.md segue a ordem canônica exata: Brand & Style → Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and Don'ts. EXPERIENCE.md tem todos os defaults obrigatórios na ordem esperada: Foundation, Information Architecture, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows. `Inspiration & Anti-patterns` e `Responsive & Platform` estão ausentes, e ambas as ausências são defensáveis nas condições já dadas: não há produto de referência externa (usuário partiu do zero, confirmado pelo `.memlog.md`) nem variação real de plataforma (web responsivo simples desktop+tablet, já coberto em prosa por `DESIGN.md.Layout & Spacing`).

### Findings
- Nenhum achado — seção estruturalmente correta nos dois arquivos.

## Mechanical notes

- Frontmatter `sources` idêntico nos dois arquivos; todos os 5 caminhos existem no disco (`prd.md`, `brief.md`, `addendum.md`, `data-model.md`, `AGENTS.md`).
- Todas as referências `{path.to.token}` em DESIGN.md resolvem para chaves reais do frontmatter; nenhuma referência quebrada encontrada. Único achado de token é o de tokens *não usados* (`spacing['1']`–`spacing['6']`), não de referência quebrada — ver seção 2.
- Referências cruzadas de EXPERIENCE.md para DESIGN.md (`DESIGN.md.calm-state-card`, `DESIGN.md.Components`, `DESIGN.md.Brand & Style`, `DESIGN.md.Layout & Spacing`) resolvem todas para seções/componentes reais.
- Único mismatch de terminologia encontrado: "gráfico de faixas de percentil" (EXPERIENCE.md) vs. "faixa habitual" (DESIGN.md + mockup escolhido) — ver achado crítico da seção 7.
- Rótulos do enum de `FollowUp` ("Em observação · Ativo · Aguardando retorno · Encerrado") usados de forma idêntica em DESIGN.md e EXPERIENCE.md, e semanticamente alinhados ao enum de `docs/data-model.md` (`EM_OBSERVACAO`, `ACOMPANHAMENTO_ATIVO`, `AGUARDANDO_RETORNO`, `ENCERRADO`) e ao texto do Glossário do PRD.
- Nenhum diretório `mockups/` ou `wireframes/` existe ainda; `imports/` existe vazio; os 4 artefatos de `.working/` não foram promovidos nem citados — estado esperado antes do Finalize, não um defeito desta etapa.
