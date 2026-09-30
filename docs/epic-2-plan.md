# Epic 2 — Plano de execução

Aprovado em 2026-09-30. Complementa `docs/epic-2-context.md` (o *quê*) com o *como*: ordem, paralelismo e critérios de pronto.

## Por que esta epic não roda como a Epic 1

| | Epic 1 | Epic 2 |
|---|---|---|
| Superfície | backend + frontend + migration por story | backend-only, zero UI |
| Módulos tocados | disjuntos (attendance/grades/assignments/observations) | todos no mesmo `backend/app/synthetic/` |
| Verificação | clicar na tela + curl no I/O Matrix | rodar CLI + inspecionar o banco |
| Paralelismo | 5 branches empilhadas funcionaram bem | empilhar tudo geraria conflito constante no mesmo módulo |

Consequência prática: o "I/O Matrix" do spec-template vira **matriz de invocação de CLI → efeito no banco**, e o paralelismo é limitado a pares de stories que tocam arquivos comprovadamente disjuntos.

## Decisões fixadas antes de codar

| # | Decisão | Onde está registrada |
|---|---|---|
| D1 | `SyntheticGenerationRun` (seed, versão, data, contagem, proporção) é a única entidade nova | `data-model.md` §Geração sintética |
| D2 | `Student.synthetic_profile` nullable, **nunca** exposto em schema de resposta do produto | `data-model.md` §Geração sintética + §Decisões |
| D3 | `seed_dev_fixtures.py` permanece intacto servindo a suíte de testes; o gerador é o caminho de dev/demo | `epic-2-context.md` §Technical Decisions |
| D4 | Re-execução contra banco populado exige `--reset` explícito, nunca append silencioso | `epic-2-context.md` §Technical Decisions |
| D5 | 2.4 é insumo de 2.2 — construída em paralelo com 2.1, não depois | §Ondas, abaixo |
| D6 | Autor das observações sintéticas: o usuário de coordenação semeado por `seed_dev_user.py` | a fixar na spec de 2.5 |

## Ondas

**Onda 1 — paralela, 2 worktrees (arquivos disjuntos)**

- **2.1 — núcleo determinístico.** Módulo `app/synthetic/`, CLI `python -m app.synthetic.generate --seed N`, estudantes/turmas/matrículas, `dataset_split` atribuído na geração, migration `0006` (`SyntheticGenerationRun` + `Student.synthetic_profile`), `--reset` explícito, volume coerente com ~200 estudantes.
- **2.4 — constantes de calibração.** `app/synthetic/calibration.py`: constantes nomeadas com fonte + confiança por parâmetro, derivadas de `research.md`. Evasão/abandono calibrado pelo Censo 2023 (confiança alta); notas 0–10 por proxy do SAEB (confiança média); frequência diária e entrega de atividades marcadas como **suposição de design pura, sem fonte**.

**Onda 2 — sequencial**

- **2.2 — perfis aplicados aos fatos.** Enum `SyntheticProfile` + regras determinísticas de evolução de frequência/notas/atividades ao longo do ano letivo, consumindo as constantes de 2.4. Story mais pesada da epic.

**Onda 3 — paralela, 2 worktrees**

- **2.3 — split.** Constante nomeada de proporção, garantia de trajetória completa no recorte `EVAL_DEMO`, e teste de regressão de que nenhuma query da aplicação web enxerga `TRAIN`. Majoritariamente verificação: AD-11 já foi entregue na Epic 1 (`repositories/base.py`, com testes em `test_attendance.py` e `test_assignments.py`).
- **2.5 — observações sintéticas.** Templates determinísticos selecionados por perfil, tom factual conforme `EXPERIENCE.md`, persistidos na mesma tabela `PedagogicalObservation` da Epic 1.

**Onda 4** — `bmad-retrospective` da Epic 2 e fechamento do `sprint-status.yaml`.

## Ciclo por story

`bmad-build` (spec → plano → implementação em worktree dedicada) → `bmad-code-review` multi-lente com triagem patch-now/defer → **walkthrough independente em worktree limpa** → PR empilhado → merge pelo autor.

O walkthrough independente é o passo que pegou os problemas reais na Epic 1: ele reverifica as alegações do agente de build em vez de confiar no auto-relato.

## Definition of Done da Epic 2

Além da DoD normal do projeto:

- [ ] **Determinismo por hash do conteúdo das tabelas**, não por contagem de linhas — duas execuções com a mesma seed produzem o mesmo hash.
- [ ] **Teste inverso:** seeds diferentes produzem bases diferentes. Sem ele, um gerador constante passa no teste de determinismo.
- [ ] Toda constante de calibração carrega fonte + confiança, ou marcação explícita de suposição de design.
- [ ] Round-trip da migration (`upgrade` → `downgrade` → `upgrade`), como nas stories da Epic 1.
- [ ] Teste de ausência de dado real varrendo os campos textuais gerados.
- [ ] Geração respeita as constraints de banco da Epic 1 (`UNIQUE` de presença, `CHECK` de 0–10 em nota).
- [ ] A suíte de testes roda o gerador em **volume reduzido**; o tempo da geração completa é medido e declarado, nunca exercido no CI.
- [ ] `synthetic_profile` não aparece em `backend/openapi.json`.

## Infra

O backend depende de dois containers Postgres que não estão em nenhum `docker-compose` do repo:

```
sinaliza-test-postgres   porta 5433   -> TEST_DATABASE_URL
sinaliza-dev-postgres    porta 5434   -> DATABASE_URL
```

Se o pytest falhar com `OperationalError`, verifique `docker ps` antes de suspeitar do código.
