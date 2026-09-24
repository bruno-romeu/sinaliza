---
title: 'Registro de notas por disciplina e período letivo (Story 1.3)'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'full'
route_source: 'auto'
baseline_commit: '429cec6432b62d70916f42806d79a569f9ca10a3'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '{project-root}/docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/DESIGN.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/EXPERIENCE.md'
  - '{project-root}/docs/data-model.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no way yet for the coordenação pedagógica to record a student's grade per disciplina and período letivo, and the `AcademicPeriod` entity itself does not exist in the schema yet (only `Classroom`/`Student`/`Enrollment`/`AttendanceRecord` exist, from Story 1.2).

**Approach:** Introduce `AcademicPeriod` (dev-fixture seeded, no registration screen) and add a "Lançamento de notas" surface: backend endpoints to list academic periods and register one grade at a time (`value` numeric(4,2), 0.0–10.0, structurally bounded by a DB CHECK constraint), reusing Story 1.2's existing classroom/student-listing endpoints, plus a per-student-row frontend form with shared turma/disciplina/período/data context and inline non-blocking save confirmation.

## Boundaries & Constraints

**Always:** grade writes go through one application-service method (`RegisterGradeService`), never a router assigning fields directly; `Grade.value` is `numeric(4,2)` on 0.0–10.0 with no approval/failure field (AD-10), enforced by Pydantic `Field(ge=0, le=10)` at the API boundary AND a DB-level `CHECK` constraint (mirrors AD-7's "structural, not just app-checked" philosophy from Story 1.2's UNIQUE constraint); `AcademicPeriod` is dev-fixture seeded only (extends `seed_dev_fixtures.py`) with at least one period whose `[start_date, end_date]` window contains the implementation date, so "período letivo vigente" is always satisfiable; `GET /academic-periods` and `POST /grades` require the existing `get_current_user` bearer dependency; a grade write checks classroom exists (404 `classroom_not_found`), student is enrolled (422 `student_not_enrolled`) and period exists (404 `academic_period_not_found`) — same order and status codes as `RegisterAttendanceService`'s precedent; every field (disciplina, valor, período, data) has a visible label, and the valor input's out-of-range state is wired via `aria-describedby` (UX-DR23).

**Never:** a classroom/student/enrollment/academic-period CRUD screen; pass/fail semantics on `Grade` (no derived boolean/enum); bulk/batch grade submission across students in one request — saving is per student, per row, mirroring `Presenca.tsx`'s "lançar o próximo estudante sem interrupção"; editing or deleting an already-saved grade (no AC requires it); rejecting a second grade for the same student/subject/período/date as a duplicate — unlike `AttendanceRecord`, `data-model.md`'s `Grade` has no UNIQUE constraint and no AC here requires one (a student may legitimately receive multiple assessments in the same período).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Turma selected with matriculados; disciplina+período+data filled; valor filled for one student, save clicked | `POST /grades` → 201, persisted; that row shows "Registro salvo." inline, no modal | No error |
| Out-of-range value (client) | valor = 10.5 (or -1) entered, save clicked | Save blocked client-side before any request; field-adjacent message via `aria-describedby` | No API call made |
| Out-of-range value (API bypass) | `POST /grades` with `value: 15.00` issued directly | Pydantic rejects, standard FastAPI 422 (untouched, mirrors `AttendanceCreateRequest`'s UUID-typing precedent) | Default validation body, not the `AppError` envelope |
| DB-level bypass | A `GradeModel` with `value=15` inserted directly against the table, bypassing the service/schema | `IntegrityError` on the `ck_grade_value_range` CHECK constraint | Proves the constraint is real at the DB level, tested directly against Postgres |
| Unauthenticated | No/invalid bearer token on `GET /academic-periods` or `POST /grades` | 401, same envelope as `get_current_user` (Story 1.1) | No error body leakage |
| Unknown classroom | `POST /grades` with a nonexistent `classroom_id` | 404 `{error:{code:"classroom_not_found", message:"Turma não encontrada."}}` | Mirrors attendance's identical check |
| Unknown period | `POST /grades` with a nonexistent `period_id` | 404 `{error:{code:"academic_period_not_found", message:"Período letivo não encontrado."}}` | — |
| Student not enrolled | `POST /grades` with a `student_id` not enrolled in `classroom_id` | 422 `{error:{code:"student_not_enrolled", message:"Estudante não está matriculado nesta turma."}}` | Mirrors attendance's identical check |

</frozen-after-approval>

## Code Map

- `backend/app/domain/attendance.py` -- reference pattern for the new frozen dataclasses below
- `backend/app/domain/grade.py` -- NEW: `Grade` frozen dataclass (id, student_id, classroom_id, subject, period_id, date, value: Decimal)
- `backend/app/domain/academic_period.py` -- NEW: `AcademicPeriod` frozen dataclass (id, label, start_date, end_date, order_index)
- `backend/app/infrastructure/db/models.py` -- add `AcademicPeriodModel`, `GradeModel`; `GradeModel.value` is `Numeric(4,2)` with `CheckConstraint("value >= 0 AND value <= 10", name="ck_grade_value_range")`
- `backend/alembic/versions/0003_create_grades_tables.py` -- NEW migration: `academic_periods` + `grades` tables, FKs, CHECK constraint, indexes (no new native enum needed)
- `backend/app/application/attendance/ports.py` -- `ClassroomRepositoryPort`/`StudentRepositoryPort` reused as-is (import only, no changes)
- `backend/app/application/academic_periods/ports.py` -- NEW: `AcademicPeriodRepositoryPort` (list_all, get_by_id)
- `backend/app/application/academic_periods/list_academic_periods.py` -- NEW: `ListAcademicPeriodsService.execute()`
- `backend/app/application/grades/ports.py` -- NEW: `GradeRepositoryPort` (save)
- `backend/app/application/grades/errors.py` -- NEW: `ClassroomNotFoundError`, `StudentNotEnrolledError`, `AcademicPeriodNotFoundError` (small, intentionally duplicated from `attendance/errors.py` to keep the two vertical slices independently importable)
- `backend/app/application/grades/register_grade.py` -- NEW: `RegisterGradeService.execute(...)` — checks classroom exists, student enrolled, period exists, then saves
- `backend/app/infrastructure/repositories/sqlalchemy_academic_period_repository.py` -- NEW: implements `AcademicPeriodRepositoryPort`
- `backend/app/infrastructure/repositories/sqlalchemy_grade_repository.py` -- NEW: implements `GradeRepositoryPort`
- `backend/app/presentation/schemas/grades.py` -- NEW: `AcademicPeriodOut`, `GradeCreateRequest` (value: `Annotated[Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)]`), `GradeOut`
- `backend/app/presentation/grades/router.py` -- NEW: `GET /academic-periods`, `POST /grades`, both behind `get_current_user`
- `backend/app/composition.py` -- extend with factories for the 2 new services
- `backend/app/main.py` -- register the new grades router
- `backend/app/infrastructure/db/seed_dev_fixtures.py` -- extend idempotently: seed 4 `AcademicPeriod` bimesters for academic_year 2026, one spanning 2026-09-24
- `backend/tests/test_grades.py` -- NEW: covers every I/O Matrix row against real Postgres
- `backend/tests/test_migrations.py` -- extend `migration_engine`'s drop list + assertion for the new tables
- `backend/tests/conftest.py` -- add a `seeded_academic_period` fixture shaped like `seeded_classroom`
- `frontend/src/api/client.ts` + `schema.d.ts` -- extend with `listAcademicPeriods`, `registerGrade`; regenerate `schema.d.ts` from `backend/openapi.json`
- `frontend/src/pages/Lancamento/Notas.tsx` -- NEW: turma+disciplina+período+data shared context, per-student `value` `<input type="number">` + save `<button>`, inline confirmation/error per row (mirrors `Presenca.tsx`)
- `frontend/src/components/Header.tsx` -- add a "Lançamento de notas" nav link beside the existing "Lançamento" (presença) link
- `frontend/src/App.tsx` -- add route `/lancamento/notas` behind `ProtectedRoute`

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/domain/academic_period.py` -- `AcademicPeriod` frozen dataclass -- AD-2 pure domain
- [x] `backend/app/domain/grade.py` -- `Grade` frozen dataclass -- AD-10
- [x] `backend/app/infrastructure/db/models.py` -- add `AcademicPeriodModel`, `GradeModel` with `Numeric(4,2)` + CHECK constraint
- [x] `backend/alembic/versions/0003_create_grades_tables.py` -- creates `academic_periods`/`grades`, FKs, CHECK constraint, indexes
- [x] `backend/app/application/academic_periods/ports.py`, `list_academic_periods.py` -- `AcademicPeriodRepositoryPort`, `ListAcademicPeriodsService`
- [x] `backend/app/application/grades/ports.py`, `errors.py`, `register_grade.py` -- `GradeRepositoryPort`, error types, `RegisterGradeService`
- [x] `backend/app/infrastructure/repositories/sqlalchemy_academic_period_repository.py`, `sqlalchemy_grade_repository.py` -- implement the ports above
- [x] `backend/app/presentation/schemas/grades.py` -- `AcademicPeriodOut`, `GradeCreateRequest`, `GradeOut`
- [x] `backend/app/presentation/grades/router.py` -- `GET /academic-periods`, `POST /grades`, both behind `get_current_user`
- [x] `backend/app/composition.py` -- factories for the 2 new services
- [x] `backend/app/main.py` -- register the grades router
- [x] `backend/app/infrastructure/db/seed_dev_fixtures.py` -- idempotent seeding of 4 academic periods (2026)
- [x] `backend/tests/conftest.py` -- `seeded_academic_period` fixture
- [x] `backend/tests/test_grades.py` -- covers every I/O Matrix row, incl. the DB-level CHECK bypass test
- [x] `backend/tests/test_migrations.py` -- extend for the new tables
- [x] `frontend/src/api/client.ts` -- `listAcademicPeriods`, `registerGrade`; regenerate `schema.d.ts`
- [x] `frontend/src/pages/Lancamento/Notas.tsx` -- shared turma/disciplina/período/data context, per-student valor input + save
- [x] `frontend/src/components/Header.tsx` -- add "Lançamento de notas" nav link
- [x] `frontend/src/App.tsx` -- route `/lancamento/notas` behind `ProtectedRoute`

**Acceptance Criteria:**
- Given a turma with matriculated students and at least one academic period seeded, when the coordenação opens Lançamento de notas, then it sees turma/disciplina/período/data selectors plus one row per matriculated student with a valor input.
- Given a valor saved for one student, when the coordenação then acts on a different student in the same turma, then that student's grade saves independently with no modal interrupting the flow.
- Given the `grades` table, when inspected, then it carries a CHECK constraint restricting `value` to `[0,10]` at the schema level.
- Given the Lançamento de notas form, when rendered, then every field (disciplina, valor, período, data) has a visible label.

## Implementation Notes

Implemented in full per the Tasks checklist: domain (`AcademicPeriod`, `Grade`), Alembic migration `0003` (`academic_periods`/`grades`, both FKs, `ck_grade_value_range` CHECK, indexes — no new native enum), the `academic_periods`/`grades` application/infrastructure/presentation stack mirroring the `attendance` slice's layering (`ClassroomRepositoryPort`/`StudentRepositoryPort` reused as-is, per Code Map), `seed_dev_fixtures.py` extended with 4 independently-idempotent `AcademicPeriod` bimesters for 2026 (classroom/student/enrollment seeding and academic-period seeding each check their own row count, so either half can already exist without skipping the other), and the `Notas.tsx` per-row Lançamento form (turma/disciplina/período/data shared context, per-student valor input) wired into `Header`/`App.tsx`.

Verified against the real Postgres containers already running for this worktree: `alembic upgrade head` against the dev DB (0002 → 0003, confirmed the `ck_grade_value_range` CHECK exists via `pg_constraint`), `seed_dev_fixtures` run twice (second run no-op for both halves), `pytest` against `TEST_DATABASE_URL` (39/39, including the DB-level CHECK-bypass test and the migration upgrade/downgrade/upgrade cycle), `npm run generate:api-types && npm run build` (clean, no manual `schema.d.ts` drift), and `npm run test -- --run` (3/3).

`frontend/src/pages/Lancamento/Notas.test.tsx` (added after an audit flagged the gap) covers the I/O Matrix's "Out-of-range value (client)" row directly: renders `Notas` with mocked `fetch` for the classrooms/academic-periods/students GETs, fills the shared turma/disciplina/período context, enters `15` in a row's valor input, clicks Save, and asserts both the field-adjacent message is wired via `aria-describedby` and no `POST /grades` call was ever made.

**Review-driven fixes (Pass 1, all patch-routed):** `GradeCreateRequest.subject` and the Disciplina input now bound to 1–255 chars (matching `GradeModel.subject`'s `String(255)`); `canSave`/`handleSave` now also require `date`; `handleSave`'s stale-response guard now compares all four shared-context fields (turma/período/disciplina/data), not only turma, before applying a save's result — mirrors `Presenca.tsx`'s single-field version of the same guard; `validateValue()` now rejects more than 2 decimal places client-side; `test_migrations.py` now asserts `ck_grade_value_range` exists (exact `pg_get_constraintdef`) on the Alembic-migration-built schema itself, not only the `Base.metadata.create_all()` schema `test_grades.py`'s DB-bypass test uses; a new `Notas.test.tsx` happy-path test asserts the `POST /grades` body matches the selected ids/subject/date/value and that the row then shows "Registro salvo." — closing both the verification-gap lens's payload-wiring-untested finding and intent-alignment's independently-raised point that the one UI behavior the frozen Approach text names explicitly had no automated coverage. See Review Triage Log for the full disposition of all 17 findings across 4 lenses.

**Deferred (not this story's blocker, logged in `docs/deferred-work.md`):** no `GET /grades`/read-back endpoint exists — a coordinator cannot review already-entered grades after leaving the page; excluded by the intent itself (Epic 1 captures facts, Epic 3 consumes/analyzes them; Story 1.2 shipped the identical write-only shape). `seed_dev_fixtures.py`'s new `_seed_academic_periods` idempotency path has no automated test — dev-only tooling, no production request path.

Re-verified after the patch round: `pytest` (39/39, including the new migration-schema CHECK-constraint assertion), `npm run build` (clean), `npm run test -- --run` (4/4, including the new happy-path test).

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verdict counts: 4 medium, 2 low, 8 false, plus 2 verification-gap-filed patches and 1 verification-gap-filed defer. Routing: 6 patch, 2 defer, 9 false (rejected/no action). Zero intent_gap, zero bad_spec — no loopback, `review_loop_iteration` stays 0.

| # | Finding (source) | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `GradeCreateRequest.subject` is a bare `str` with no `min_length`/`max_length`, unlike `GradeModel.subject`'s `String(255)`; matching `Notas.tsx` Disciplina input has no `maxLength` either (blind-hunter, edge-case-hunter, grouped) | medium | patch | Confirmed by direct read of `backend/app/presentation/schemas/grades.py` and `frontend/src/pages/Lancamento/Notas.tsx`. An overlong subject (>255 chars) submitted directly to the API would hit an uncaught Postgres length error instead of a clean 422; an empty subject also bypasses the UI's own `subject.trim()` guard when called directly. Trivial fix (add `Field(min_length=1, max_length=255)` + `maxLength={255}`), no public surface added. |
| 2 | `Notas.tsx`'s `canSave` and `handleSave`'s early-return guard never check that `date` is non-empty, unlike `classroomId`/`periodId`/`subject` (edge-case-hunter, verification-gap "Other findings", grouped) | low | patch | Confirmed: both conditions omit `date`. Clearing the date input and saving sends `date: ''`, hitting FastAPI's standard 422 and surfacing only the generic fallback message instead of field-specific feedback. Reachable in normal use (native `<input type="date">` is clearable) though narrow; fix is a direct one-line addition to two existing boolean expressions, so it does not meet the low-rejection bar. |
| 3 | `handleSave` only captures/compares `selectedClassroomIdRef` before applying its response, not `selectedPeriodId`/`subject`/`date` — the three new shared-context fields this story introduces (blind-hunter, edge-case-hunter, grouped) | medium | patch | Confirmed via direct read: only one ref exists. Same bug class Story 1.2 already patched for its one shared field (`Presenca.tsx` triage #6/#8) — Story 1.3 quadruples the shared-context surface (turma+disciplina+período+data) without extending the guard, so changing período/disciplina/data mid-save can paint "Registro salvo." onto a row the user is now viewing under a different context. Fix mirrors the existing `classroomIdAtSaveStart` pattern, extended to the other three fields — direct, bounded, no new public surface. |
| 4 | `validateValue()` checks range/NaN but not decimal precision — a value like `"8.567"` passes the client-side gate that the spec's I/O Matrix says should block out-of-range/malformed input before any network call (blind-hunter) | low | patch | Confirmed: the function has no decimal-places check, and the native `number` input's `step` attribute does not prevent typing extra decimals. Reachable (manual typing) but low-impact (falls back to a generic error message, no data corruption); fix is a direct addition to the existing validation function. |
| 5 | No automated test exercises `Notas.tsx`'s happy-path save (`handleSave`'s success branch: the `POST /grades` payload it builds from live UI state, and the resulting "Registro salvo." message) (verification-gap, filed pre-verified; intent-alignment, independently named the same gap as its primary divergence point) | medium | patch | Verification-gap's filed evidence: `student_id`/`classroom_id`/`period_id` are all typed as plain `string` in the generated client types, so a field-transposition bug in the request-object literal would not be caught by TypeScript and is untested by any existing test (`Notas.test.tsx` only covers the out-of-range-block row; backend tests never exercise frontend-constructed payloads). Also closes intent-alignment's independently-raised point that "inline non-blocking save confirmation" — the one UI behavior the frozen Approach text names explicitly — has no automated coverage. One test change closes both. |
| 6 | The `ck_grade_value_range` CHECK constraint is only verified against the ORM-model-built schema (`test_grades.py`'s DB-bypass test uses `Base.metadata.create_all()`), never against the actual Alembic-migration-built schema that real deployments run (verification-gap, filed pre-verified) | medium | patch | Verification-gap's filed evidence: `test_migration_upgrade_downgrade_upgrade_does_not_raise` only asserts table existence post-upgrade, never that the CHECK constraint itself exists/fires on the migration-built schema — mirroring the exact class of gap that file's own docstring says a prior enum bug fell through (`create_all()` never exercises Alembic's `upgrade()`). A dropped/mistyped constraint in the migration file would ship undetected while the full suite stays green. |
| 7 | `client.ts`'s `isErrorEnvelope()` doesn't recognize FastAPI's standard `{"detail": [...]}` shape, so any backend-only-caught malformed input falls back to a generic message (blind-hunter) | false | — | This is the same, already-accepted precedent as `AttendanceCreateRequest`'s malformed-UUID 422 (Story 1.2, never flagged there) and is explicitly this spec's own documented Design Notes tradeoff ("never a bespoke `AppError` for this case, since it's malformed input, not a business-rule conflict") — not a new gap introduced by this story. |
| 8 | No `GET /grades` (or any read-back) endpoint — a coordinator cannot review already-entered grades for a turma/período after leaving the page (blind-hunter; intent-alignment, its "Reading B" divergence point) | medium | defer | Real gap, but excluded by the intent itself, not just this spec's scope section: `epic-1-context.md`'s Goal frames Epic 1 as capturing raw facts for Epic 3's later consumption/analysis, and Story 1.2 shipped with the identical shape (no `GET /attendance` listing endpoint either, never flagged in its own review). Consistent, epic-wide write-now/read-later precedent, not a hole specific to this story's spec. |
| 9 | `RegisterGradeService` never validates that `date` falls within the selected `period_id`'s `[start_date, end_date]` window (blind-hunter) | false | — | No AC, `data-model.md` field, or `epic-1-context.md` requirement asks for this cross-field validation. Mirrors the MVP's established pattern of trusting coordinator-entered temporal fields beyond referential-integrity/value-range checks — Story 1.2's `AttendanceRecord.date` is likewise never validated against `Classroom.academic_year`. Inventing this rule risks incorrectly blocking legitimate late/corrective entries no AC contemplates. |
| 10 | The seed's "3º Bimestre" deliberately spans today so a "período letivo vigente" exists, but the frontend never pre-selects/surfaces it — the período `<select>` always starts blank (blind-hunter) | false | — | The AC's precondition only requires that a vigente período be selectable (it is — present in the dropdown), not that the UI auto-select it. Conflates "exists and is selectable" with "is defaulted," which no AC requires. |
| 11 | `test_list_academic_periods_returns_seeded_period` doesn't exercise the repository's `order_by(order_index)` ordering (blind-hunter) | false | — | Coverage-only suggestion for already-correct behavior (`sqlalchemy_academic_period_repository.py` does `order_by(AcademicPeriodModel.order_index)`), no bad outcome demonstrated — identical grounds to Story 1.2 triage #10's rejection of the same class of finding. |
| 12 | No test submits a value with more than 2 decimal places to exercise the backend's `decimal_places=2` Pydantic constraint (blind-hunter) | false | — | Coverage-only suggestion for already-correct, standard-library-enforced behavior — same grounds as #11. |
| 13 | Neither `GradeModel` nor `Grade` records `created_by`/`created_at` (blind-hunter) | false | — | `data-model.md`'s canonical `Grade` schema is `{id, student_id, classroom_id, subject, period_id, date, value}` — no author/timestamp field, exactly mirroring Story 1.2 triage #9's identical, already-accepted ruling for `AttendanceRecord`. A deliberate difference in the documented model, not an oversight. |
| 14 | No composite index on `grades(classroom_id, period_id)` (blind-hunter) | false | — | No query path in this codebase would use it — the only listing endpoint that would need it (`GET /grades`) is itself out of scope per #8. Premature optimization for a feature that doesn't exist yet. |
| 15 | `RegisterGradeService`/`SqlAlchemyGradeRepository.save()` doesn't catch an `IntegrityError` from a classroom/student/period deleted between the existence-checks and the insert (edge-case-hunter) | false | — | No delete/mutation endpoint exists anywhere in this codebase for classrooms/students/academic_periods (dev-fixture-seeded only) — this TOCTOU race is unreachable through any path in the application today, identical reachability argument to Story 1.2 triage #3's rejection of the equivalent claim. |
| 16 | The `listClassrooms`/`listAcademicPeriods` effect has no unmount ignore-flag guard (edge-case-hunter) | false | — | Identical pre-existing pattern already shipped in `Presenca.tsx`'s equivalent first effect (Story 1.2), never flagged there — `Notas.tsx` faithfully mirrors the established convention rather than introducing a new gap. |
| 17 | `seed_dev_fixtures.py`'s new `_seed_academic_periods` idempotency path has no automated test (verification-gap, filed pre-verified) | medium (unverified) | defer | Verification-gap's filed evidence: no test in `backend/tests/` calls the seed script at all (the `seeded_academic_period` fixture builds the row directly via SQLAlchemy, bypassing the script). Dev-only tooling with no production request path; a regression would only surface on a developer's manual re-run, not via the automated suite. |

## Design Notes

**Shared context vs. per-row field split (autonomous decision):** turma+disciplina+período+data are top-level shared fields (one "lançamento session" = one assessment context); `valor` is the only per-row field. This generalizes Story 1.2's turma+date-shared / status-per-row split, avoids redundant re-entry of subject/period/date for every student, and keeps `NotaRow` as small as `AttendanceRow`. The AC's field list (disciplina, valor, período, data) is read as "the form's fields with visible labels," not as "all must be per-row" — turma is the one extra selection-context field, same as in Story 1.2 where turma/date also weren't individually named in that story's own label AC.

**AcademicPeriod seed dates (autonomous decision):** 4 bimesters for `academic_year=2026` (`1º Bimestre` 2026-02-02–2026-04-17, `2º Bimestre` 2026-04-20–2026-06-26, `3º Bimestre` 2026-07-27–2026-09-25, `4º Bimestre` 2026-09-28–2026-12-18), `order_index` 1–4. `3º Bimestre` deliberately contains 2026-09-24 (today) so "período letivo vigente" holds for manual verification without a period-registration screen.

**No duplicate-grade rejection (autonomous decision):** confirmed against `data-model.md` — `Grade` carries no UNIQUE constraint and Story 1.3's ACs never mention rejecting a repeat grade. The CHECK constraint on `value` is this story's DB-level structural invariant, standing in for the UNIQUE constraint's role in Story 1.2's design (both are "AD-level rule enforced at the database, not just application logic").

**Value validated twice, deliberately:** client-side before any network call (immediate `aria-describedby` feedback per UX-DR23, no round trip) AND server-side via Pydantic `Field(ge=0, le=10)`, producing FastAPI's untouched standard 422 (same precedent as `AttendanceCreateRequest`'s UUID-typed fields) — never a bespoke `AppError` for this case, since it's malformed input, not a business-rule conflict.

**Gate self-decisions (autonomous run, no human present):** VCS sanity check passed as-is (branch name matches story, tree clean at start). Multi-goal check: single cohesive goal (grade registration end-to-end across all layers, same shape as Story 1.2) — not split. Token-count gate: kept the full spec (cohesive cross-layer DB+BE+UI feature; Story 1.2's spec also exceeded the 1600-token target and was kept whole under the same reasoning). Checkpoint 1: "Approve and continue" — Open Questions is empty, no ambiguity found that required a human decision.

## Verification

**Commands:**
- `cd backend && alembic upgrade head` -- expected: `academic_periods`/`grades` created with the CHECK constraint
- `cd backend && python -m app.infrastructure.db.seed_dev_fixtures` -- expected: 2 classrooms + students + enrollments + 4 academic periods exist; re-running is a no-op
- `cd backend && pytest` -- expected: all I/O Matrix rows pass, including the DB-level CHECK bypass test
- `cd frontend && npm run generate:api-types && npm run build` -- expected: clean build, no manual `schema.d.ts` drift
- `cd frontend && npm run test -- --run` -- expected: existing suite still green

**Manual checks:**
- Log in, open Lançamento de notas, pick a seeded turma + período + disciplina + data, save one student's valor, confirm inline "Registro salvo." with no modal; try valor = 15 and confirm the client-side `aria-describedby` message with no request sent.
