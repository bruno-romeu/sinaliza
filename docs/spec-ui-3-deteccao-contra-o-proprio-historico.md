---
title: 'Detecção contra o próprio histórico, observação com preocupação e preparo da demonstração'
type: 'fix'
created: '2026-10-24'
status: 'review'
baseline_commit: 'c2b9de0'
route: 'oneshot'
route_source: 'human'
context: ['docs/spec-ui-1-pacote-backend-design-system.md', 'docs/spec-ui-2-migracao-visual-frontend.md']
---

## Intent

**Problem:** Rodando o frontend novo contra a base sintética (seed 42, `SINALIZA_DEMO_AS_OF=2026-09-25`), 50 dos 60 estudantes da demo apareciam com mudança, 33 deles do perfil estável. Duas regras causavam isso: nota abaixo de 5 contava como "queda de notas" (o gerador põe 59% das notas abaixo de 5) e qualquer observação pedagógica contava como sinal, inclusive "Frequência dentro da faixa habitual". Na Trajetória, a faixa habitual incluía o próprio ponto da mudança, o bimestre futuro repetia o valor de hoje e a evidência de frequência citava cada dia de presença.

**Decisões (humano, 2026-10-24):**

1. Nota: confirma quando a média do bimestre fica 1 ponto ou mais abaixo da menor média dos bimestres anteriores do próprio estudante. Sem bimestre anterior, não confirma.
2. Atividades pendentes: confirma quando o número do bimestre passa o maior número dos bimestres anteriores em 2 ou mais.
3. Observação: conta como sinal só quando quem registra marca "Registra uma preocupação" (`registers_concern`). Observações neutras continuam como evidência e na linha do tempo.
4. Frequência mantém o piso de 75% (mínimo legal) e a queda de 10 pontos em relação ao bimestre anterior.
5. Comando manual `python -m app.synthetic.prepare_demo` para calcular as trajetórias da demo uma vez. Data padrão da demonstração: 2026-09-25.

## O que mudou

- **Migração 0013:** `pedagogical_observations.registers_concern` (boolean, padrão `false`). `POST /pedagogical-observations` aceita o campo (opcional) e devolve; `observations[]` da Trajetória também.
- **`domain/convergence.py`:** regras acima. Evidência de frequência cita só as faltas. Frase da observação: "preocupação registrada pela equipe".
- **`get_student_trajectory.py`:** lê notas e atividades de todos os bimestres anteriores; quando há mudança, cita também as observações neutras do bimestre como evidência.
- **`get_student_trajectory_detail.py`:** faixa habitual = mínimo e máximo dos bimestres anteriores ao de referência (o da mudança, ou o atual); bimestre que ainda não começou vem com `value: null`.
- **Gerador (2.6.0):** observações dos perfis em queda vêm com `registers_concern=true`; nomes espalhados pela capacidade (antes todos tinham o sobrenome "Tavanor"); `--reset` apaga também mudanças, fontes, acompanhamentos e predições do ML, que antes travavam o reset com erro de chave estrangeira.
- **`app/synthetic/prepare_demo.py`**, nota no README e no `.env.example`.
- **Frontend:** caixa "Registra uma preocupação" na observação do Lançamento; "Saiu da faixa" só quando o ponto está fora da faixa (senão "Mudança detectada"); card de evidência mostra 5 registros e "Ver todos os N registros"; linha do tempo marca "Observação · preocupação registrada".

## Resultado na base sintética (seed 42, 2026-09-25)

| Perfil | Antes | Depois |
|---|---|---|
| Estável (43) | 33 com mudança | 1 |
| Queda de frequência (8) | 8 | 7 |
| Queda de notas (4) | 4 | 3 |
| Deterioração combinada (5) | 5 | 4 |

## Fora de escopo

- O gerador sorteia a nota de cada bimestre de forma independente, então a média de um estudante estável oscila bastante entre bimestres. Isso explica o estável que ainda aparece. Corrigir mexe nos experimentos de ML (Epic 5) e fica para depois.
- Mudanças já gravadas mantêm o texto e as fontes antigos até a base ser regerada.

## Verification

- `cd backend && uv run alembic upgrade head && uv run pytest -q` -- expected: tudo passa, exceto as 4 falhas conhecidas de `tests/test_synthetic_dataset_split.py` (dependem do usuário seed, ver `docs/deferred-work.md`). Casos novos em `tests/test_ui_package_3.py`.
- `cd frontend && npm run generate:api-types && npx tsc --noEmit -p . && npm test && npm run build` -- expected: 51 testes passam.
- Manual: regerar a base, rodar `prepare_demo` com `SINALIZA_DEMO_AS_OF=2026-09-25` e conferir a Home (15 mudanças) e a Trajetória de um estudante estável (sem mudança).
