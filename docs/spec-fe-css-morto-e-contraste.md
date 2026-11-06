---
id: SPEC-fe-css-morto-e-contraste
companions: []
sources:
  - docs/deferred-work.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Varredura de cascata perdida e medição de contraste dos rótulos do gráfico

## Why

Duas entradas abertas de `docs/deferred-work.md` (seção de 2026-11-05) descrevem o mesmo tipo de problema: alguém acreditar que uma coisa está verificada quando ela não está.

**A primeira** é CSS morto por cascata perdida. Descobriu-se no PR #50 que
`@media (max-width: 640px) { .sz-header-nav { gap: var(--space-2) } }`, escrita em `base.css`, nunca teve efeito: `components.css` define o mesmo seletor com a mesma especificidade e `main.tsx` o importa depois. A regra pontual foi corrigida ali; o que ficou aberto é a varredura. Uma regra morta por cascata não quebra nada — e é exatamente por isso que é perigosa: o ajuste responsivo não produz efeito e a conclusão natural de quem escreveu é que o **valor** estava errado, não que a regra nunca rodou. Ninguém tinha conferido se havia outras.

**A segunda** é o contraste dos rótulos dentro do `<svg>` do gráfico de trajetória. O axe-core 4.10.2 devolve os 8 nós de texto do gráfico como `incomplete`, não como aprovados, porque a regra `color-contrast` não sabe avaliar texto dentro de SVG. Com 0 violações de AA no resto da interface nos dois temas, esses 8 nós são o **único** lugar da interface onde o contraste é desconhecido em vez de verificado. O `AGENTS.md` §Gráficos exige considerar acessibilidade; um ponto cego declarado não satisfaz isso.

As duas entradas pedem a mesma coisa: trocar uma suposição por uma medição, e deixar a medição registrada.

## Capabilities

- **CAP-1**
  - **intent:** Determinar, por ferramenta e não a olho, se alguma declaração de `base.css` perde a cascata para `components.css` em toda a aplicação.
  - **success:** Existe um procedimento reproduzível, descrito na própria spec, que (a) compara os seletores dos dois arquivos com especificidade calculada e (b) resolve o vencedor real da cascata por elemento no navegador, via CSSOM, para cada declaração de `base.css`. O resultado nomeia cada declaração que perde e quem a vence, ou afirma que não há nenhuma.

- **CAP-2**
  - **intent:** Remover ou mover o CSS que a varredura provar morto, caso a caso, com o critério explicado.
  - **success:** Nenhuma declaração é removida sem que a varredura tenha mostrado que ela perde em todas as larguras e em todas as rotas onde seu seletor aparece. Uma declaração que vence em alguma rota permanece.

- **CAP-3**
  - **intent:** Eliminar o arranjo que produziu o bug original — `base.css` declarando sobre um seletor cuja definição vive em `components.css`.
  - **success:** Nenhum seletor é declarado nos dois arquivos; o comportamento renderizado é idêntico antes e depois, verificado por comparação de `getComputedStyle` nos elementos afetados.

- **CAP-4**
  - **intent:** Medir a razão de contraste real dos 8 nós de texto dentro do SVG do gráfico, nos dois temas, contra o fundo efetivo atrás deles.
  - **success:** Para cada classe de texto (`axis`, `axis-hot`, `cp-label`) existe um número medido no navegador a partir da cor computada, nos temas claro e escuro, contra cada fundo que pode estar atrás dela (superfície do cartão e preenchimento da faixa).

- **CAP-5**
  - **intent:** Decidir o limiar WCAG aplicável a partir do tamanho **renderizado** desses rótulos, não do `font-size` declarado.
  - **success:** O tamanho renderizado em px é medido (`font-size` em unidades de usuário × escala do `viewBox`) nas larguras extremas, e a qualificação como "texto grande" é decidida com o critério do WCAG (≥ 24px, ou ≥ 18.66px em negrito) aplicado a esse número.

- **CAP-6**
  - **intent:** Deixar a medição registrada onde quem mexer no gráfico a encontre, para que ninguém precise refazê-la.
  - **success:** Os números, os dois temas, o limiar aplicado e a razão de o axe não conseguir medir isso estão em comentário no CSS que define esses rótulos.

## Constraints

- `frontend/src/styles/tokens.css` é **gerado** a partir do design system; qualquer correção de cor só pode usar um token que já exista. Se nenhum servir, a correção vira reporte, não edição.
- Nenhum `.tsx`/`.ts` pode ser tocado. O `viewBox` do gráfico vive no componente: ajustes de tipografia só podem passar por `font-size`, que dentro de um SVG com `viewBox` é expresso em unidades de usuário e escala junto.
- Especificidade igual não é condição suficiente para declarar uma regra morta, e seletor duplicado também não: a prova tem de ser por propriedade e por elemento, porque uma regra aparentemente duplicada pode estar vencendo legitimamente em outra propriedade.
- A ausência de elemento correspondente numa rota **não** é prova de morte. Isso é seletor não exercido naquela rota, problema diferente, fora do escopo.
- O `AGENTS.md` proíbe cor vermelha como mecanismo único de classificação e manda considerar acessibilidade; a correção de contraste, se houver, não pode introduzir nova codificação por cor.

## Non-goals

- Não remover seletores apenas por não terem elemento correspondente nas rotas visitadas (`.sz-results`, `.sz-check`, `.sz-confirm` e os estados `:hover`/`:focus-visible` aparecem sob condição de runtime).
- Não reorganizar `base.css`/`components.css` além do necessário para fechar CAP-3.
- Não mexer em `tokens.css`, nem propor valores novos de token dentro desta entrega.
- Não tratar as outras entradas abertas de `docs/deferred-work.md` (rótulo "Em observação", CSP, índices redundantes).
- Não editar `docs/deferred-work.md` nem `docs/sprint-status.yaml`.

## Success signal

Dado `docs/deferred-work.md`, as duas entradas de 2026-11-05 sob este escopo podem ser fechadas com evidência citável: para a primeira, o resultado da varredura e o método que o produziu; para a segunda, seis razões de contraste medidas e o limiar WCAG justificado pelo tamanho renderizado. Um leitor futuro que abra `components.css` encontra os números sem precisar rodar nada.

## Resultado da investigação

Registrado aqui porque é a evidência que fecha CAP-1, CAP-4 e CAP-5.

### Varredura (CAP-1, CAP-2, CAP-3)

Camada estática (postcss, seletores normalizados + especificidade calculada): os **únicos** seletores declarados nos dois arquivos são `.sz-header-nav` e `.sz-header-nav .sz-btn`. Nenhuma colisão de propriedade — `components.css` declara `display/align-items/gap/font-size/color` em `.sz-header-nav` e `padding` em `.sz-header-nav .sz-btn`; `base.css` declara `flex-wrap`/`justify-content` e `white-space`. Conjuntos disjuntos.

Camada dinâmica (CSSOM no navegador, vencedor resolvido por elemento): 224 declarações em `base.css`, 153 exercidas em 8 rotas, com a condição de mídia avaliada analiticamente para 9 larguras (1920, 1280, 761, 760, 721, 720, 641, 640, 360). **Nenhuma declaração de `base.css` perde permanentemente para `components.css`.** A única que nunca vence em 7 das 8 rotas — `a { color: var(--action) }` — vence em `/login`, portanto não está morta.

Conclusão: não há CSS a remover. As duas regras de `.sz-header-nav` migram para `components.css` não por estarem mortas, mas porque são o único ponto em que `base.css` ainda disputa cascata com `components.css` — um `flex-wrap` ou `white-space` adicionado lá amanhã as mataria em silêncio, que é literalmente o bug do PR #50 repetido.

### Contraste (CAP-4, CAP-5)

Cor computada via `getComputedStyle`, fundo efetivo obtido subindo a árvore até o primeiro `background-color` opaco, razão pela fórmula WCAG 2.x.

| texto | tema claro | tema escuro |
| --- | --- | --- |
| `.axis` sobre `--surface` | 8.15:1 | 11.00:1 |
| `.axis-hot` / `.cp-label` sobre `--surface` | 6.65:1 | 9.36:1 |
| `.axis` sobre `--band-fill` | 6.96:1 | 8.90:1 |
| `.axis-hot` / `.cp-label` sobre `--band-fill` | 5.68:1 | 7.58:1 |

`--band-fill` entra na tabela porque `.cp-label` de fato cai sobre a faixa (verificado por interseção de `getBoundingClientRect`); os rótulos de eixo não caem.

**Não se qualificam como texto grande.** O `font-size` do CSS está em unidades de usuário do `viewBox` (640×240) e é escalado pela razão entre a largura renderizada e a do `viewBox`. Medido: 9.65px renderizados em viewport de 360px (21px × 0.4594) e 16.86px em 1280px (13px × 1.2969). O WCAG exige ≥ 24px, ou ≥ 18.66px em negrito; nenhum dos dois é alcançado em nenhuma largura. Aplica-se **4.5:1**, e todas as seis medições passam — a pior é 5.68:1.

Nenhuma cor muda. A entrega é o registro.
