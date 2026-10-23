---
title: 'Migração visual do frontend para o design system Sinaliza'
type: 'refactor'
created: '2026-10-22'
status: 'review'
baseline_commit: '990e951'
route: 'oneshot'
route_source: 'human'
context: ['Design system Sinaliza (telas de referência e Contrato de dados)', 'docs/spec-ui-1-pacote-backend-design-system.md']
---

## Intent

Trocar a camada visual do frontend pelo design system Sinaliza, sem mudar regras nem contratos com a API: mesmas rotas, mesmas chamadas, mesmos estados de carregamento, erro e duplicidade.

## O que mudou

- **Tokens:** `src/styles/tokens.css` gerado do `tokens.json` do design system (primitivas, tokens semânticos claro e escuro, espaçamento, raios, tamanhos, fontes). As variáveis `--color-*` antigas saíram.
- **Estilos:** `base.css` (layout de página, cabeçalho de tela, seções, skeleton, login, guia de escrita) e `components.css` (porte do `bundle.css`). Fontes Bricolage Grotesque e Atkinson Hyperlegible Next via Google Fonts no `index.html`.
- **Componentes** em `src/components/ui/`: Icon, Button/ButtonLink, TextField/TextAreaField/SelectField, Tag/IndicatorTag, StatusPill, Eyebrow, Notice, CalmState, ConcernFactor, EvidenceCard, ChangeRow, FollowupCard, Timeline, NavTabs, ChoiceGroup, RosterRow, TrajectoryChart, Disclosure, Page/ScreenHead/Section/Skeleton. `FollowUpStatusPill` e o `EvidenceCard` antigo foram removidos.
- **Cabeçalho:** wordmark, "Voltar à Home", um único "Lançar registro" no lugar dos 4 links, pessoa autenticada e "Sair".
- **Telas:** Login (marca, aviso de sessão expirada), Home, Trajetória, Acompanhamento (confirmação de encerramento dentro da tela, sem `window.confirm`), Lançamento com abas e linhas por estudante (`RosterRow`; presença e entrega com `ChoiceGroup`; observação aberta dentro da linha com guia "Escreva / Evite").
- **Sessão expirada:** `AuthContext` guarda `sessionExpired` quando o 401 desloga e a tela de login mostra o aviso.
- `detected_at` na Tela de Acompanhamento passa a ser formatado em UTC (mesma regra da Home), para a data não voltar um dia.

## Testes

Mesma intenção dos testes existentes, com ajustes só de rótulo: "Status atual", "Nota de {nome}", "Observação sobre {nome}" (depois de "Escrever observação"), "Salvar observação", opção de atividade "Matemática · prazo 30/09/2026" e entrega por rádio ("Parcial").

## Verification

- `cd frontend && npm run generate:api-types && npx tsc --noEmit -p . && npm test && npm run build` -- expected: 47 testes passam e o build gera o bundle.
- Manual: conferir Home, Trajetória, Acompanhamento, as 4 abas de Lançamento e Login nos temas claro e escuro e em 390px de largura (sem rolagem horizontal).
