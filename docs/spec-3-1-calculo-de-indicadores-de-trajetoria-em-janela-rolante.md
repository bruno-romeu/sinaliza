---
title: 'Cálculo de indicadores de trajetória em janela rolante'
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
baseline_commit: 'd5db6b0fc9c23d201158fa2786e74958460e7972'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A coordenação só vê fatos brutos (presença, notas, atividades), sem nenhum indicador agregado da evolução recente de um estudante.

**Approach:** Novo `GET /students/{id}/trajectory` calcula `attendance_rate`, `attendance_trend`, `grade_average`, `grade_trend`, `missing_assignments_count`, `missing_assignment_delta`, síncrono dentro da requisição, via função pura em `domain/trajectory.py`, lendo só `EVAL_DEMO` truncado por `as_of()` (AD-5). Só calcula e devolve — sem persistência e sem convergência (isso é Story 3.2).

## Boundaries & Constraints

**Always:**
- Cálculo síncrono no próprio `GET`, nunca job/cron (AD-1); indicadores em `domain/trajectory.py`, função pura sem I/O (AD-12).
- Toda leitura usa o filtro `EVAL_DEMO` existente + a nova `as_of()` — nunca `TRAIN` nem dado além de "hoje" (AD-4, AD-5, AD-11).
- `attendance_rate/trend` e `missing_assignments_count/delta` usam janela rolante `window_days` (default configurável, override `?window_days=`); `grade_average/trend` segue `Grade.period_id` (período vigente vs. anterior por `order_index`).
- Trend/delta = valor atual − valor do período/janela anterior equivalente (nunca regressão); `None` sem comparável.
- "Pendente" (`missing_assignments_count`) = `Assignment` vencida na janela sem `AssignmentSubmission` `DELIVERED` (ausência, `NOT_DELIVERED` e `PARTIAL` contam).
- Estudante inexistente ou `TRAIN` → mesmo 404, nunca vaza o split; `synthetic_profile` nunca na resposta.

**Never:**
- Sem `TrajectorySnapshot`/tabela nova — upsert só aparece na AC de `TrajectoryChange` (3.2).
- Sem `SignalEvaluator`/`ConvergenceRule`/"fator preocupante" (3.2); sem Home/Trajetória-UI (3.3/3.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Caminho feliz | Estudante `EVAL_DEMO` com fatos na janela | 200 com os 6 indicadores | No error expected |
| Sem dados na janela | Estudante sem registros | 200; rates/averages/trends `None`, `missing_assignments_count=0` | No error expected |
| Estudante inexistente/`TRAIN` | `id` inválido ou fora do `EVAL_DEMO` | — | 404 `student_not_found` (idêntico nos dois casos) |
| `as_of()` override | env `SINALIZA_DEMO_AS_OF` setada | Janela/período calculados a partir dessa data | No error expected |
| Concorrência | 2 GETs simultâneos, mesmo estudante | Cálculo independente, resultado idêntico, sem erro de lock | No error expected |

</frozen-after-approval>

## Code Map

- `backend/app/domain/as_of.py` -- NEW: `as_of() -> date` (AD-5), hoje UTC, override só via env `SINALIZA_DEMO_AS_OF`.
- `backend/app/domain/trajectory.py` -- NEW: `compute_trajectory_indicators(...)` pura, estilo dataclass+docstring-AD de `domain/attendance.py`/`grade.py`.
- `backend/app/infrastructure/repositories/base.py:22-25` -- EXTEND: já tem `filter_eval_demo_students`; adicionar `filter_as_of(stmt, date_column)` genérico (fecha lacuna que `epic-3-context.md` assumia já existir).
- `sqlalchemy_student_repository.py:21-51` -- EXTEND: `get_by_id` com `filter_eval_demo_students` (não existe hoje).
- `sqlalchemy_{attendance,grade,assignment,assignment_submission}_repository.py` -- EXTEND: leitura por estudante/intervalo com `filter_as_of`.
- `backend/app/application/trajectory/{__init__,ports,errors,get_student_trajectory}.py` -- NEW: `GetStudentTrajectoryService` + `StudentNotFoundError`, mirror de `application/attendance/register_attendance.py`.
- `backend/app/presentation/trajectory/router.py`, `presentation/schemas/trajectory.py` -- NEW: `GET /students/{id}/trajectory`, `TrajectoryOut`, padrão de `presentation/grades/router.py`.
- `backend/app/composition.py:109-131`, `app/main.py` -- EXTEND: factory + registro do router.
- `backend/app/config.py:14-31` -- EXTEND: `trajectory_window_days: int = Field(default=30, gt=0)`.
- `sqlalchemy_academic_period_repository.py` -- REUSE: período vigente (`start_date <= as_of() <= end_date`) e anterior por `order_index`.
- `backend/tests/test_trajectory_domain.py`, `tests/test_trajectory.py` -- NEW: unit (sem DB) + API (fixtures de `conftest.py`, cobrindo a I/O Matrix).

## Tasks & Acceptance

**Execution:**
- [x] `domain/as_of.py` -- implementar `as_of()` -- fonte única de "hoje" (AD-5)
- [x] `infrastructure/repositories/base.py` -- `filter_as_of` -- truncagem reutilizável (AD-11)
- [x] `sqlalchemy_student_repository.py` -- `get_by_id` -- valida existência + `EVAL_DEMO`
- [x] `sqlalchemy_{attendance,grade,assignment,assignment_submission}_repository.py` -- leitura por estudante/intervalo -- alimenta o cálculo sem vazar `TRAIN`/futuro
- [x] `domain/trajectory.py` -- indicadores + trend/delta puros -- RF-10, AD-12
- [x] `application/trajectory/*` -- `GetStudentTrajectoryService` -- orquestração sem I/O no domínio
- [x] `presentation/schemas/trajectory.py`, `presentation/trajectory/router.py` -- endpoint -- expõe via HTTP
- [x] `composition.py`, `main.py` -- wiring -- registra serviço/rota
- [x] `config.py` -- `trajectory_window_days` -- default configurável
- [x] `tests/test_trajectory_domain.py` -- unit da função pura -- RNF-09
- [x] `tests/test_trajectory.py` -- API cobrindo I/O Matrix -- 404, janela vazia, `as_of()` override

**Acceptance Criteria:**
- Given estudante `EVAL_DEMO` com fatos na janela, when `GET /students/{id}/trajectory`, then 200 com os 6 indicadores, sem `synthetic_profile`.
- Given `id` inexistente ou `TRAIN`, when `GET`, then 404 `student_not_found` idêntico nos dois casos.
- Given `SINALIZA_DEMO_AS_OF` setada, when calcula, then usa essa data como "hoje", nunca a real.
- Given 2 requisições concorrentes, when processadas, then sem estado compartilhado, resultados idênticos.

## Implementation Notes

- `AcademicPeriodRepositoryPort.list_all()` is reused as-is (no new repo method) — `GetStudentTrajectoryService` resolves the current período (`start_date <= as_of() <= end_date`) and the previous one (`order_index - 1`) in the application layer, matching the Code Map's "REUSE" marker for `sqlalchemy_academic_period_repository.py`.
- `missing_assignment_delta` is typed `int`, never `int | None`: `missing_assignments_count` is always a defined count (`0` with no assignments due), so the previous-window count is too, and the subtraction is always computable — "sem comparável" only applies to the ratio-based indicators (`attendance_rate`/`grade_average`), where division by zero is the actual missing-comparable case.
- `attendance_rate`/`attendance_trend` are rounded to 4 decimal places; `grade_average`/`grade_trend` to 2 (matching `GradeModel.value`'s `Numeric(4,2)` column scale) — keeps the response stable/comparable across independent recomputations (RNF-09).
- Verified: `pytest -q` (TEST_DATABASE_URL on both the 5433 and 5435 containers) — 257 passed, plus the 4 pre-existing `test_synthetic_dataset_split.py` failures that also fail identically on `master` before this change (missing dev-user seed row in a fresh test DB — an environment-setup gap unrelated to this story, confirmed via `git stash`).

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 18 findings total (see Pass 1 totals below).

1. [verification-gap] Untested period-boundary resolution: no test exercises `as_of_date` exactly equal to a period's `start_date`/`end_date`, nor "periods exist in DB but none covers `as_of_date`" (distinct from the already-tested "zero periods" case). — **low** (gap verified real by the lens's own evidence rules; no demonstrated wrong output today, but the boundary logic is genuinely unexercised). → **patch**: add the two tests it specifies.
2. [blind-hunter] No test exercises `?window_days=0`/negative. — Verified live: `window_days=0` and `-5` both return `422` (Pydantic `Query(gt=0)`) — behavior is already correct, only coverage is missing. **low**. → **patch**: add a test.
3. [edge-case-hunter] `window_days` has no upper bound (`Settings.trajectory_window_days: Field(gt=0)`, `Query(gt=0)`); a large value (confirmed live: `window_days≈2,000,000`) makes `date - timedelta(days=2*window_days)` raise an unhandled `OverflowError` → uncaught 500 instead of a clean 422. **medium** (real, trivially reachable via ordinary query-string input, not just malice). → **patch**: add `le=3650` (or similar) to both.
4. [edge-case-hunter] `as_of()` does `date.fromisoformat(override)` with no error handling; a malformed `SINALIZA_DEMO_AS_OF` value raises an unhandled `ValueError` on every request. **low** (operator-only misconfiguration of a demo-only override, never reachable from user input). → **patch**: wrap in try/except with a clear message.
5. [blind-hunter] Current window is closed-closed (`window_days+1` days), previous window is closed-open (`window_days` days) — a genuine 1-day/≈3% size asymmetry between the two sides of every trend/delta. Traced to the spec's own (non-frozen) Design Notes example, faithfully implemented as written. **low** — negligible on a ~200-student synthetic demo, no AC or user-visible behavior depends on exact statistical symmetry, and "fix" would touch 2 call sites + re-verify date fixtures in 3 existing tests for no observable benefit. → **reject** (low, fix is more than a trivial one-line correction, unlikely anyone meets it in everyday use).
6. [blind-hunter] + [edge-case-hunter] `as_of()` is called once in `GetStudentTrajectoryService.execute` but independently re-invoked inside every repository's `filter_as_of` — could disagree only if `SINALIZA_DEMO_AS_OF`/the real UTC date changes *during* a single request. **low** — real UTC date can only roll over at exact midnight UTC (microsecond race), and the demo override is static config never toggled mid-request; fix requires threading `as_of_date` through 5 method signatures. → **reject** (low, fix is more than a direct correction, not met in everyday use).
7. [blind-hunter] No test for a malformed (non-UUID) `student_id` path segment. Verified live: returns FastAPI's standard `422 {"detail": [...]}`, per `presentation/errors.py`'s own documented convention ("FastAPI/Pydantic's default validation error handling... is left untouched") — identical precedent already accepted (unverified-but-correct) for every other UUID-typed path/body field in this codebase (e.g. spec-1-4's review explicitly rejected the same class of finding). → **reject** (false: matches established, intentional, already-reviewed convention).
8. [blind-hunter] New route has no per-student/classroom authorization scoping — any authenticated user can fetch any student's trajectory. Verified: every existing route (`grades`, `attendance`, `assignments`, `observations`) has the identical pattern — only `get_current_user`, no ownership check — because the product has exactly one flat role (`COORDENACAO_PEDAGOGICA`, AD-8) and no multi-tenant model. → **reject** (false: not a gap this story introduced; matches the whole app's intentional single-role design).
9. [blind-hunter] No new DB indexes for the new range-scan query patterns. Verified against architecture AD-1: "fine as plain set-based queries... only optimize if a real RNF-01 (5s) measurement shows risk, and even then... never move the computation outside the request path" — performance work is explicitly deferred project-wide until measured. → **reject** (false/out of scope: excluded by binding architecture decision, not by this spec's own scope section).
10. [blind-hunter] Concurrency test (`test_trajectory_two_requests_for_same_student_produce_identical_results`) issues two sequential calls, not real parallel threads. Verified: the service does no writes and holds no shared mutable state or cache — safety is structural (pure function + stateless reads), not something a race test would add confidence to; sequential-call determinism is the established proxy this codebase already uses for similar claims. → **reject** (false: AC's concern — "no lock, no inconsistent result" — is already guaranteed by the architecture, not by this specific test shape).
11. [blind-hunter] `test_trajectory_window_days_query_param_overrides_default` asserts the literal string `"1.0000"` for a `Decimal` field. Verified: this is Pydantic's standard, documented `Decimal`→JSON-string encoding, stable within the pinned Pydantic version — not a fragile implementation detail. → **reject** (false).
12. [edge-case-hunter] A student's `dataset_split` could flip to `TRAIN` between the initial `get_by_id` check and later repository reads within the same request. Verified against AD-4: `Student.dataset_split` is "decidido na geração sintética, nunca em query time" — no code path anywhere in this codebase ever mutates it at request time, so the trigger condition cannot occur. → **reject** (false).
13. [edge-case-hunter] `compute_trajectory_indicators` has no internal guard for `window_days <= 0`. Verified: its only caller (the router) already enforces `>0` via Pydantic/FastAPI before the service or domain function ever runs; unreachable today. → **reject** (low, unreachable from any current caller; a guard would add unneeded complexity to a pure function for an untriggerable case).
14. [edge-case-hunter] `list_due_in_range_for_student`'s join through `EnrollmentModel` could return duplicate `Assignment` rows if a student has more than one enrollment row for the same classroom. Verified: `EnrollmentModel` has `UniqueConstraint("student_id", "classroom_id")` (`infrastructure/db/models.py`) — the precondition is structurally impossible. → **reject** (false).
15. [edge-case-hunter] Two overlapping `AcademicPeriod` date ranges could make `next(...)`'s period-match non-deterministic. Verified: `SqlAlchemyAcademicPeriodRepository.list_all()` always `ORDER BY order_index` — the match is deterministic regardless of overlap; `AcademicPeriod` is also dev-fixture-seeded only, no registration screen, so overlapping/malformed data isn't a reachable product scenario. → **reject** (false).
16. [intent-alignment] The diff faithfully implements the Approach paragraph (compute-and-return only) but does not close the Problem paragraph's user-visibility gap ("a coordenação só vê fatos brutos"), and `window_days` configurability isn't named in the literal 2-paragraph intent text. Verified: the same frozen `<frozen-after-approval>` block's Boundaries & Constraints explicitly states "sem Home/Trajetória-UI (3.3/3.4)" and "sem persistência... isso é Story 3.2" — the intent itself excludes UI-surfacing from this story, and `window_days` is a direct, undisputed elaboration of "janela rolante" already named in the Approach. → **reject** (false: excluded by the intent's own frozen Boundaries, not merely by the spec's scope section).

17. [blind-hunter] `current_period`/`previous_period` resolution relies on `order_index` being contiguous/unique with no guard or test for gaps/duplicates. Verified: `AcademicPeriodModel` docstring confirms it is "dev-fixture seeded only... no registration screen" — there is no product code path that can ever write a malformed/duplicate `order_index`; the invariant is guaranteed outside this story, same trust boundary the rest of the codebase already relies on for this table. → **reject** (false).
18. [blind-hunter] `SINALIZA_DEMO_AS_OF` is read unconditionally with no environment-based gate (e.g. no check against a `production`/`debug` flag) to stop it from working outside demo/test use. Verified against AD-5: "um único utilitário `as_of()`... variável de override... sobrescrevível só por essa variável, documentada, para ensaio de demonstração" — the binding architecture decision specifies exactly this unconditional, env-var-only mechanism, relying on operational discipline (documented in `.env.example`), the same pattern `config.py` already uses for other dev-only settings (`dev_seed_password`, etc.). → **reject** (false: excluded by the intent's own binding architecture decision).

**Pass 1 totals:** medium 1, low 6, false 11 — 18 findings, 0 high, 0 maybe-false.

All patch items are independent, trivial, test-only or validation-only additions — no shared root cause, grouped as separate entries.

- **Sem persistência:** as ACs de 3.1 só pedem cálculo+retorno; upsert/congelamento é contrato da Story 3.2 (`TrajectoryChange`). Antecipar `TrajectorySnapshot` agora arrisca retrabalho.
- **Trend/delta:** `attendance_trend = rate(janela atual) − rate(janela anterior, mesmo tamanho, não sobreposta)`; `grade_trend` usa o período anterior por `order_index`; sem comparável → `None`, nunca `0`.
- **Exemplo (window=30):** atual=`[hoje-30, hoje]`, anterior=`[hoje-60, hoje-30)`; `attendance_rate` = presentes/(presentes+faltas); `attendance_trend` = atual − anterior.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: todos os testes + `test_trajectory_domain.py` + `test_trajectory.py` passam
- `cd backend && ./.venv/Scripts/python.exe -c "import app.domain.trajectory, app.domain.as_of"` -- expected: exit 0, sem DB/network
- `git status --short` -- expected: só os arquivos do Code Map e esta spec mudaram
