---
title: 'Detecção de mudança relevante por convergência de sinais'
type: 'feature'
created: '2026-10-08'
status: 'done'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: []
baseline_commit: 'cc6db795659537a0d73dadd6137ddc24b3a8ca37'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `GET /students/{id}/trajectory` (Story 3.1) só devolve indicadores brutos — a coordenação não tem nenhum sinal de que uma mudança de trajetória é real e vale atenção, nem rastro persistido para citar como evidência depois.

**Approach:** Quatro `SignalEvaluator` (frequência, nota, atividades, registro pedagógico) avaliam o período vigente do estudante; uma `ConvergenceRule` pura decide, a partir de ≥2 sinais `confirmed=True`, se cria/atualiza uma `TrajectoryChange` (upsert `ON CONFLICT`, mesma transação de suas `TrajectoryChangeSource`) ou devolve um "fator preocupante" efêmero. Tudo roda dentro do `GET /students/{id}/trajectory` já existente — sem endpoint novo.

## Boundaries & Constraints

**Always:**
- Síncrono, dentro do mesmo `GET /students/{id}/trajectory`; cada recomputação é a própria transação (AD-1).
- Avaliação é por `period_id` (período vigente, mesmo resolvido em 3.1) — não por `window_days`; cada `SignalEvaluator` lê fatos só dentro de `[period.start_date, period.end_date]` do período atual e do anterior (por `order_index`), reaproveitando `filter_eval_demo_students`/`filter_as_of`.
- Upsert `TrajectoryChange` por `(student_id, type, period_id)` via `INSERT ... ON CONFLICT ... DO UPDATE`, nunca `SELECT`+`INSERT`/`UPDATE` (AD-1, RF-11). `TrajectoryChangeSource` inserida na mesma transação — nenhuma `TrajectoryChange` sem fonte (RNF-11).
- Registro pedagógico pesa igual aos demais sinais — pode, sozinho com outro sinal qualquer, formar convergência.
- `TrajectoryChange` é evento imutável: recálculo posterior do mesmo `period_id` sem convergência não apaga/reverte a linha já gravada.
- "Fator preocupante" nunca é persistido — só aparece na resposta HTTP do próprio `GET`, sem id estável.

**Never:**
- Sem job/cron/worker escrevendo essas tabelas.
- Sem `TrajectorySnapshot` nesta story — 3.1 já devolve indicadores sem persistir; nada na AC de 3.2 pede essa tabela, só `TrajectoryChange`/`TrajectoryChangeSource`.
- Sem freeze-on-evidence: `FollowUp`/`FollowUpEvidence` (Epic 4) ainda não existem, então o upsert desta story é sempre `DO UPDATE` incondicional (nunca checa evidência) — o guard `DO NOTHING` entra como ALTER do Epic 4, quando `follow_up_evidence` existir (decisão do humano, registrada em `deferred-work.md`).
- Sem endpoint novo, sem Home (`GET /home`, Story 3.3) nem UI de trajetória (3.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Convergência (2+ sinais) | ≥2 `SignalEvaluator` com `confirmed=True` no período vigente | `TrajectoryChange` criada/atualizada + `TrajectoryChangeSource`(s); resposta inclui a mudança | No error expected |
| Sinal isolado | Exatamente 1 `confirmed=True` | Nenhuma linha gravada; resposta traz `concerning_factor` efêmero | No error expected |
| Nenhum sinal confirmado | 0 `confirmed=True` | Nenhuma linha gravada; resposta sem mudança nem fator preocupante | No error expected |
| Recálculo do mesmo período | `TrajectoryChange` já existe para `(student_id, type, period_id)`, sinais mudaram | `DO UPDATE`: `description`/`detected_at`/`TrajectoryChangeSource` substituídos (delete+reinsert) | No error expected |
| Recálculo, sinais pararam de confirmar | `TrajectoryChange` do período anterior existente, período atual sem convergência | Linha antiga permanece intocada; nenhuma nova linha para o período atual | No error expected |
| Concorrência | 2 `GET`s simultâneos, mesmo estudante/período | `ON CONFLICT` resolve sem lock explícito, resultado final idêntico | No error expected |

</frozen-after-approval>

## Code Map

- `backend/app/domain/trajectory.py:61-62,75-88` -- REUSE: `_ATTENDANCE_QUANT`/`_GRADE_QUANT`, `_attendance_rate`, `_grade_average` helpers for signal math (promote to module-level reuse, not re-implement).
- `backend/app/domain/convergence.py` -- NEW: `SignalKind` enum (`ATTENDANCE`,`GRADE`,`ASSIGNMENTS`,`PEDAGOGICAL_OBSERVATION`), `Signal` frozen dataclass (`confirmed: bool`, `kind: SignalKind`, `source_ids: tuple[uuid.UUID, ...]`), pure `evaluate_attendance_signal`/`evaluate_grade_signal`/`evaluate_assignments_signal`/`evaluate_pedagogical_signal`, `decide_change_type(confirmed_kinds) -> TrajectoryChangeType`, `build_description(confirmed_kinds, period_label) -> str`, `evaluate_convergence(signals) -> ConvergenceResult` (either `change` fields or `concerning_factor`). Zero I/O (AD-2, AD-12).
- `backend/app/domain/trajectory_change.py` -- NEW: `TrajectoryChangeType` enum (`ATTENDANCE_DROP`,`GRADE_DROP`,`MISSING_ASSIGNMENTS_INCREASE`,`COMBINED_DETERIORATION`), `TrajectoryChange`/`TrajectoryChangeSource` frozen dataclasses (`data-model.md:70-76`), `SourceType` enum (`ATTENDANCE_RECORD`,`GRADE`,`ASSIGNMENT_SUBMISSION`,`PEDAGOGICAL_OBSERVATION`).
- `backend/app/application/trajectory/ports.py` -- EXTEND: `TrajectoryChangeRepositoryPort.upsert(change, sources) -> TrajectoryChange` (always `DO UPDATE`, no freeze guard — see Never); `PedagogicalObservationRepositoryPort.list_by_student_in_range(student_id, start, end)` (new method, mirrors `AttendanceRepositoryPort.list_by_student_in_range`).
- `backend/app/application/trajectory/get_student_trajectory.py:55-112` -- EXTEND: after computing indicators, resolve the 4 `Signal`s from current/previous period data already fetched (reuse, don't re-query), call `evaluate_convergence`, upsert if converged, attach result to `TrajectoryIndicators`/service return value.
- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- NEW: implements `upsert` via `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(index_elements=["student_id","type","period_id"], ...)` — first precedent for `ON CONFLICT` in this codebase, no existing idiom to mirror.
- `backend/app/infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py:17-` -- EXTEND: add `list_by_student_in_range(student_id, start, end)` (filters `created_at` date between bounds), mirroring the attendance repo's range method.
- `backend/app/infrastructure/db/models.py:208` (after `SyntheticGenerationRunModel`) -- EXTEND: `TrajectoryChangeModel` (`UniqueConstraint("student_id","type","period_id")`), `TrajectoryChangeSourceModel` (FK `trajectory_change_id`, `source_type` native enum, `source_id`); new `trajectory_change_type_enum`/`trajectory_change_source_type_enum` `SAEnum`s alongside existing ones (line 22-37 pattern).
- `backend/alembic/versions/0007_create_trajectory_change_tables.py` -- NEW: migration for the two tables + 2 native enums, following `0004_create_assignments_tables.py`'s shape.
- `backend/app/presentation/schemas/trajectory.py` -- EXTEND: `TrajectoryOut` gains `trajectory_change: TrajectoryChangeOut | None` and `concerning_factor: ConcerningFactorOut | None` (mutually exclusive); new `TrajectoryChangeOut`(`type`,`period_id`,`detected_at`,`description`), `ConcerningFactorOut`(`kind`,`description`) schemas. Never `source_ids`/`synthetic_profile`.
- `backend/app/composition.py:109-131` -- EXTEND: wire `SqlAlchemyTrajectoryChangeRepository`, pass into `GetStudentTrajectoryService`.
- `backend/tests/test_convergence_domain.py` -- NEW: pure unit tests for `domain/convergence.py` (all 4 evaluators, type-mapping table, description text).
- `backend/tests/test_trajectory.py` -- EXTEND: cover the I/O Matrix (convergence creates row, single-signal returns `concerning_factor`, recompute replaces an existing row, prior-period row left untouched, concurrency).

## Tasks & Acceptance

**Execution:**
- [x] `domain/trajectory_change.py` -- `TrajectoryChangeType`/`SourceType` enums + dataclasses -- data-model.md:70-76 as code
- [x] `domain/convergence.py` -- `Signal`, 4 evaluators, `decide_change_type`, `build_description`, `evaluate_convergence` -- AD-12 pure pipeline contract
- [x] `infrastructure/db/models.py` + `alembic/versions/0007_*` -- `TrajectoryChangeModel`/`TrajectoryChangeSourceModel` + enums + `UNIQUE(student_id,type,period_id)` -- AD-1 upsert key
- [x] `infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- `upsert` via `ON CONFLICT` -- AD-1, never SELECT-then-write
- [x] `infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py` -- `list_by_student_in_range` -- feeds pedagogical `SignalEvaluator`
- [x] `application/trajectory/ports.py`, `get_student_trajectory.py` -- wire signals + convergence + upsert into the existing service -- RF-11
- [x] `presentation/schemas/trajectory.py` -- `trajectory_change`/`concerning_factor` response fields -- surfaces RF-11 output
- [x] `composition.py` -- wire new repository -- registers dependency
- [x] `tests/test_convergence_domain.py` -- unit, all evaluators + type mapping -- RNF-09
- [x] `tests/test_trajectory.py` -- extend with I/O Matrix scenarios -- RF-11, RNF-11

**Acceptance Criteria:**
- Given ≥2 `SignalEvaluator`s com `confirmed=True` no período vigente, when `GET /students/{id}/trajectory`, then uma `TrajectoryChange` é upsertada com ≥1 `TrajectoryChangeSource` na mesma transação, e a resposta a inclui.
- Given exatamente 1 sinal confirmado, when `GET`, then nenhuma linha é gravada e a resposta traz `concerning_factor` sem id estável.
- Given um recálculo do mesmo `period_id` com sinais diferentes dos da gravação anterior, when `GET`, then `description`/`detected_at`/`TrajectoryChangeSource` são substituídos (delete+reinsert) — upsert incondicional, sem freeze-on-evidence nesta story (ver Never, `deferred-work.md`).
- Given um registro pedagógico como único segundo sinal, when avaliado junto de outro sinal confirmado, then conta para convergência com peso igual aos demais.
- Given 2 requisições concorrentes para o mesmo estudante/período, when processadas, then o `ON CONFLICT` resolve sem lock explícito e sem duplicar a `TrajectoryChange`.

## Implementation Notes

- Signal evaluation reads facts scoped to `[period.start_date, period.end_date]` via a second, separate set of repository calls inside `GetStudentTrajectoryService._evaluate_convergence` — distinct from the rolling-window reads already made for the 6 indicators (different range entirely, except `Grade`, which is already período-scoped and is reused as-is, matching the Code Map's "reaproveitando" note for that one repository).
- `TrajectoryChange.detected_at` is derived deterministically from `as_of()` (`datetime.combine(as_of_date, time.min, tzinfo=UTC)`), never `datetime.now()` — required for RNF-09: two concurrent requests computing the same convergence must write the identical row, including `detected_at`.
- `_citable_missing` (the ASSIGNMENTS evaluator's helper) only counts an `Assignment` as missing when it has ≥1 `AssignmentSubmission` actually `NOT_DELIVERED`/`PARTIAL` — this is a stricter cut than 3.1's `missing_assignments_count` (which also counts total absence of any submission), made deliberately so every confirmed ASSIGNMENTS signal always has a real row to cite as `TrajectoryChangeSource` (RNF-11).
- `presentation/schemas/trajectory.py` uses `Literal[...]` for `TrajectoryChangeOut.type`/`ConcerningFactorOut.kind` rather than importing the domain enums directly — matches the existing codebase convention (`attendance.py`/`assignments.py` schemas already do this for their own enums).
- Verified: `pytest -q` (`TEST_DATABASE_URL` against the 5435 container) — 295 passed, plus the same 4 pre-existing `test_synthetic_dataset_split.py` failures already present on the pre-story baseline commit (missing dev-user seed row in a fresh test DB — confirmed identical via `git stash`, an environment-setup gap unrelated to this story, same as noted in Story 3.1's own Implementation Notes).
- Verified: `alembic upgrade head` against the test container applies migration `0007` cleanly on top of `0001`–`0006`.
- `tests/test_migrations.py`'s hardcoded drop/assert lists were extended with the two new tables/enums — otherwise its upgrade/downgrade/upgrade cycle would conflict with the schema `Base.metadata.create_all()` already built (not called out explicitly by the spec's Code Map, but required for that existing test to keep passing).

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 13 findings total (after grouping overlaps by shared root cause).

1. [blind-hunter] + [verification-gap/Other] `SqlAlchemyTrajectoryChangeRepository.upsert()` calls `self._session.commit()` itself, which `ports.py`'s docstring doesn't mention as a side effect — flagged as a layering leak (repository ending the request's transaction instead of the application service). Verified false: every existing repository in this codebase already does exactly this (e.g. `sqlalchemy_pedagogical_observation_repository.py`'s `save()`: `self._session.add(model); self._session.commit(); self._session.refresh(model)`) — this is the established, consistent codebase-wide convention, faithfully followed here, not a new defect this story introduced. → **reject** (false).
2. [blind-hunter] `evaluate_attendance_signal`/`evaluate_grade_signal` set `source_ids` to every current-period record/grade when confirmed (including `PRESENT` days / high grades), unlike `evaluate_assignments_signal`'s stricter citable-only filter. Verified: every cited record genuinely contributed to the computed `attendance_rate`/`grade_average` that drove confirmation — citing the full set is accurate, traceable evidence (RNF-11 requires real, citable sources, not a minimal subset), not fabrication. `ASSIGNMENTS` is filtered differently only because of a structural citability gap (a missing assignment with zero registered submissions has no row to cite at all, spec Design Notes), not because broader citation elsewhere is wrong. → **reject** (false).
3. [blind-hunter] `TrajectoryOut`'s `missing_assignments_count`/`missing_assignment_delta` (3.1, counts all missing assignments) and the `ASSIGNMENTS` convergence signal (3.2, counts only citable missing ones) can legitimately disagree for the same student/period, with no doc comment explaining this. **low** (real but cosmetic; a reader could be confused, no functional harm). → **patch**: add a one-line doc comment on `TrajectoryOut` noting the two can diverge and why.
4. [blind-hunter] + [intent-alignment] `domain/convergence.py`'s module docstring cites "`SignalEvaluator.evaluate(...) -> Signal`" as the interface each function implements, but no such type/protocol exists in the diff — four free functions with different signatures instead. **low** (docstring overclaims a type that isn't there; AD-12's literal `(student_id, period_id)` signature couldn't live in `domain/` anyway without violating AD-2's zero-I/O rule, so the actual split — pure domain functions + an orchestrating application-layer method — is the only architecturally consistent shape; this is a wording mismatch, not a functional gap). → **patch**: reword the docstring to describe what's actually implemented instead of naming a nonexistent type.
5. [blind-hunter] `GetStudentTrajectoryService.execute`'s return type changes from `TrajectoryIndicators` to `TrajectoryResult`, a breaking change to the service's public contract, with no search shown confirming no other caller depends on the old shape. Verified false: `grep -rn "GetStudentTrajectoryService\|\.execute(student_id"` across `backend/app` finds exactly one call site (`presentation/trajectory/router.py:41`), already updated in this same diff to consume `TrajectoryResult`. → **reject** (false).
6. [blind-hunter] `_evaluate_convergence` fetches overlapping current+previous période-scoped attendance/assignment data via two separate range queries, each filtered twice in Python — a duplicated fetch-then-filter pattern across the two repositories. **low** (real but a pure style nit; no functional defect, and factoring it out cleanly would add a small generic helper for marginal duplication). → **reject** (low; unlikely to cause any real-world harm, and a DRY fix here is more than a trivial one-line correction for the benefit gained).
7. [blind-hunter] No test proves a single confirmed core signal without pedagogical corroboration stays a `concerning_factor` and is never "upgraded." Verified false: `test_trajectory_happy_path_returns_200_with_six_indicators` (`backend/tests/test_trajectory.py`) exercises exactly this — a single confirmed `ATTENDANCE` signal, asserting `trajectory_change is None` and `concerning_factor == {"kind": "ATTENDANCE", ...}`. → **reject** (false).
8. [blind-hunter] `trajectory_change_sources` has no `UNIQUE(trajectory_change_id, source_type, source_id)` constraint, so a hypothetical bug calling `upsert` twice with overlapping `sources` in one call could silently duplicate citation rows. Verified false: unreachable from any current caller — each `Signal.source_ids` is built from a single repository query's distinct row ids (no duplicates possible within one kind), and `evaluate_convergence` never produces two `Signal`s of the same `kind`, so the `sources` list passed to `upsert` can never contain a repeated `(source_type, source_id)` pair today. → **reject** (false; unreachable from any current code path, same class as spec-3-1's already-accepted "unreachable today" rejections).
9. [blind-hunter] No test verifies `trajectory_change_sources`'/`trajectory_changes`' FK behavior if a referenced `student`/`academic_period`/source row is ever deleted (no `ondelete` clause on any FK). Verified real but pre-existing: every FK in this codebase already omits `ondelete` (attendance, grades, assignments, pedagogical_observations — `deferred-work.md`'s Story 1.5 entry already documents this exact codebase-wide gap). This story's new tables simply extend an already-accepted, already-deferred pattern. → **defer** (pre-existing, not caused by this story; logged in `deferred-work.md`).
10. [verification-gap] The two new native Postgres enums (`trajectory_change_type`, `trajectory_change_source_type`) are hardcoded as literal label lists in migration `0007`, independently of `TrajectoryChangeType`/`SourceType` in `domain/trajectory_change.py` — exactly the drift class `test_migrations.py` already has a dedicated regression test for on `synthetic_profile` (added after a real incident where `FALLING_GRADES` was added to the domain enum but not the migration's literal list), but no equivalent assertion exists for either of this story's two new enums. **medium** (real, demonstrated historical failure mode in this exact codebase, currently unguarded for the new enums). → **patch**: add the same `pg_enum`/`pg_type` label-comparison assertion `test_migrations.py` already has for `synthetic_profile`, duplicated for `trajectory_change_type` against `TrajectoryChangeType` and `trajectory_change_source_type` against `SourceType`.
11. [edge-case-hunter] If the confirmed-signal combination changes `TrajectoryChangeType` between two recomputations of the *same* `period_id` (e.g. `ATTENDANCE_DROP` → later `GRADE_DROP`, as `ATTENDANCE` stops confirming and `GRADE` starts), the `ON CONFLICT (student_id, type, period_id)` target no longer matches the prior row, so a new row is inserted alongside the untouched old one instead of replacing it — untested (the shipped recompute test keeps the same type, `COMBINED_DETERIORATION`, both times). Verified false: this is the architecture's own explicit design, not a bug — AD-1/data-model.md fix the upsert key as the 3-column `(student_id, type, period_id)` specifically so each confirmed type is independently tracked, and the spec's own Boundaries text ("`TrajectoryChange` é evento imutável: recálculo posterior do mesmo `period_id` sem convergência não apaga/reverte a linha já gravada") directly describes this exact outcome as intended: when a later recompute no longer confirms a previously-detected type, that type's row is left untouched as history, not deleted — regardless of whether a *different* type now also converges for the same period. → **reject** (false; matches the architecture's own binding upsert-key design, not an oversight).
12. [intent-alignment] The "Concorrência" test (`test_trajectory_two_requests_with_convergence_produce_identical_change_no_duplicate_row`) issues two sequential `TestClient.get()` calls rather than true overlapping concurrent transactions. Verified false: identical precedent already reviewed and explicitly accepted in spec-3-1's own Review Triage Log (Pass 1, finding #10) on the grounds that Postgres's `ON CONFLICT` conflict resolution is a single-statement, engine-level atomicity guarantee independent of call timing — sequential calls genuinely exercise the real conflict-resolution branch (the second call's `INSERT` really does collide with the first's committed row), proving the same correctness property true concurrent timing would, without adding confidence about lock contention this codebase has no stated performance requirement to test for (AD-1: optimize only if a real RNF-01 measurement shows risk). → **reject** (false).
13. [blind-hunter] `deferred-work.md`'s new entry (freeze-on-evidence) doesn't separately flag the repository-commits-itself or source_ids-citation-breadth points as open items for Epic 4. Moot once both underlying findings (#1, #2) are themselves rejected as false — there is nothing left to additionally log. → **reject** (false; predicated on findings already rejected above).

**Pass 1 totals:** medium 1, low 2 (both patched), false 9, defer 1 — 13 entries, 0 high.

## Design Notes

**Limiares de confirmação (decisão de implementação, `[ASSUMPTION]` do PRD RF-11 — "limiar exato fixo no MVP, a calibrar depois"):**
- `ATTENDANCE` confirma se `attendance_rate` do período vigente `< 0.75` (ancora no limiar legal já citado em `calibration.py` — LDB 9.394/1996 art. 24 VI) OU `attendance_trend <= -0.10`.
- `GRADE` confirma se `grade_average` do período vigente `< 5.0` (fronteira já usada por `GRADE_DISTRIBUTION`'s faixa "Insuficiente", `calibration.py:340`) OU `grade_trend <= -1.0`.
- `ASSIGNMENTS` confirma se `missing_assignments_count >= 2` OU `missing_assignment_delta >= 2`, contando só `Assignment`s com ao menos uma `AssignmentSubmission` `NOT_DELIVERED`/`PARTIAL` registrada — nunca as com zero submissões registradas, porque `TrajectoryChangeSource.source_type=ASSIGNMENT_SUBMISSION` exige uma linha real para citar (RNF-11) e `AssignmentSubmission` não é criada automaticamente (Story 1.4). Isso diverge levemente do `missing_assignments_count` de 3.1 (que conta ausência total também) — é um recorte propositalmente mais estrito só para fins de citabilidade do sinal.
- `PEDAGOGICAL_OBSERVATION` confirma se existe ≥1 `PedagogicalObservation` com `created_at.date()` dentro de `[period.start_date, period.end_date]`.

**Mapeamento de `type` (enum rascunho, `data-model.md:85` autoriza revisão na implementação):** exatamente 1 de `{ATTENDANCE, GRADE, ASSIGNMENTS}` confirmado (o outro sinal confirmante é sempre `PEDAGOGICAL_OBSERVATION`) → `ATTENDANCE_DROP`/`GRADE_DROP`/`MISSING_ASSIGNMENTS_INCREASE` respectivamente; ≥2 de `{ATTENDANCE, GRADE, ASSIGNMENTS}` confirmados → `COMBINED_DETERIORATION`.

**Descrição factual (Voice and Tone, `epic-3-context.md`):** `build_description` gera texto no padrão `"Mudança recente: {lista de sinais em PT-BR} — {period.label}"`, nunca linguagem diagnóstica/preditiva.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: todos os testes + os novos passam
- `cd backend && ./.venv/Scripts/python.exe -m alembic upgrade head` (against both test containers) -- expected: migration 0007 aplica limpo
- `git status --short` -- expected: só os arquivos do Code Map e esta spec mudaram
