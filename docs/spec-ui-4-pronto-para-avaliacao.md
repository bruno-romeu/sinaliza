---
title: 'Pronto para avaliação: base sintética na data real, paginação da Home e população do ambiente hospedado'
type: 'fix'
created: '2026-10-28'
status: 'review'
baseline_commit: 'ca04c6b'
route: 'oneshot'
route_source: 'human'
context: ['docs/spec-ui-3-deteccao-contra-o-proprio-historico.md', 'docs/epics.md (Story 6.4)']
---

## Intent

**Problem:** Na data real (avaliação até 23/11/2026, com `SINALIZA_DEMO_AS_OF` vazio), a Home não tinha nenhuma mudança: o gerador datava todas as notas, entregas e observações de um bimestre no último dia dele, então nada convergia antes de 18/12. A Home também mostrava só 5 mudanças, sem como chegar às outras, e o resumo dizia "5 mudanças". O ambiente hospedado não tinha como criar o usuário de login, porque o compose não repassava `DEV_SEED_*`.

**Decisões (humano, 2026-10-28):** redistribuir os dados no gerador (em vez de fixar a data da demo) e fazer a paginação da Home funcionar de ponta a ponta.

## O que mudou

- **Gerador 2.7.0:** notas em 20/40/60/80% do bimestre, entregas em 12,5/37,5/62,5/87,5% e a observação no meio (`facts.spread_day`). A nota de cada estudante parte de um nível habitual por disciplina com variação pequena entre bimestres (antes era sorteada do zero a cada bimestre e um estudante estável oscilava vários pontos).
- **Home, mudanças recentes:** `GET /home` aceita `changes_page`/`changes_page_size` e devolve `recent_changes_total`/`_page`/`_page_size`, como os acompanhamentos. Ordem `detected_at desc, id desc` (páginas sem repetir nem pular linhas com a mesma data). Busca ganhou desempate por turma.
- **Home, frontend:** resumo com os totais; "Ver mais" nas três listas, cada um pedindo só a página da própria lista; linhas que voltam repetidas numa página seguinte não duplicam; erro ao carregar mais mostra aviso e mantém o botão; contagem da busca usa o total; "1 restante" no singular.
- **Ambiente hospedado:** `DEV_SEED_*` no `docker-compose.yml`; passo 9b no runbook da VM (e nota no Plano C) com a sequência de população; README e `.env.example` dizem que a demo usa a data real.
- **Ajustes:** 4 testes de `test_synthetic_dataset_split.py` semeiam o usuário; teste instável de observações usa 8 estudantes; `useTheme` não quebra sem `localStorage`; docstring do `--reset`; `.gitattributes` com LF; rótulo do ponto de mudança não passa da borda do gráfico no último bimestre.

## Resultado na base sintética (seed 42)

| Data | Mudanças | Perfis em queda (17) | Estáveis (43) |
|---|---|---|---|
| 25/09/2026 | 16 | 16 | 0 |
| 23/11/2026 | 16 | 15 | 1 |
| 18/12/2026 | 16 | 16 | 0 |

Antes desta mudança, 23/11 tinha 0.

## Observação para a demonstração

A base sintética já tem presença para todos os dias letivos do ano, então lançar presença ao vivo para um aluno gerado devolve "Já existe registro de presença para este aluno, turma e data." (comportamento correto). Notas, atividades e observações lançadas ao vivo aparecem na hora.

## Verification

- `cd backend && uv run pytest -q` -- expected: 421 passam, sem falhas.
- `cd frontend && npm run generate:api-types && npx tsc --noEmit -p . && npm test && npm run build` -- expected: 56 passam.
- Manual: `generate --seed 42 --reset` + `prepare_demo` sem `SINALIZA_DEMO_AS_OF`; a Home mostra o total no resumo e o "Ver mais" percorre todas as mudanças.
