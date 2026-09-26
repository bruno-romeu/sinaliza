---
title: 'Registro de presença/falta por turma e data (Story 1.2)'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'full'
route_source: 'auto'
baseline_commit: '591dd275851a4f81fc41296572002f24c175ede2'
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

**Problem:** There is no way yet for the coordenação pedagógica to record daily attendance per student/turma/date, and nothing prevents a duplicate attendance row for the same combination.

**Approach:** Add a "Lançamento" attendance surface: backend endpoints to list dev-fixture classrooms/enrolled students and register one attendance record at a time (fixed status enum + DB-level UNIQUE constraint), plus a per-student-row frontend form with inline, non-blocking save confirmation.

## Boundaries & Constraints

**Always:** attendance writes go through one application-service method (`RegisterAttendanceService`), never a router assigning fields directly; `AttendanceRecord.status` is the fixed enum `PRESENT`/`ABSENT_JUSTIFIED`/`ABSENT_UNJUSTIFIED` (AD-10); `UNIQUE(student_id, classroom_id, date)` is enforced at the DB level via Alembic migration, not only application-side checking (AD-7, RNF-11); the enrolled-student read defaults to `Student.dataset_split = EVAL_DEMO` via a shared repository-base filter (AD-11) — the first repository to establish that pattern; all 3 new endpoints require the existing `get_current_user` bearer dependency (first routes to actually apply it); every form field has a visible label, and selects/buttons meet a ≥44×44px touch target; classrooms/students/enrollments come only from a dev seed script, never a registration UI.

**Never:** a classroom/student/enrollment CRUD screen; bulk/batch attendance submission across multiple students in one request — saving is per student, per the "lançar o próximo estudante sem interrupção" flow; editing or deleting an already-saved attendance record (no AC requires it); synthetic dataset generation logic (Epic 2); `as_of()`/date-truncation on attendance reads (AD-5 governs trajectory calculation only, not the date a coordinator logs attendance for).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Turma+data selected with matriculados; a status chosen and saved for one student | `POST /attendance` → 201, record persisted; that row shows "Registro salvo." inline, no modal | No error |
| Duplicate | Same student/classroom/date already saved; save attempted again | 409 `{error:{code:"duplicate_attendance", message:"Já existe registro de presença para este aluno, turma e data."}}` | Message rendered next to that student's status field via `aria-describedby`; no duplicate row created |
| DB-level bypass | A duplicate INSERT issued directly against the table, bypassing the service | `IntegrityError` on the UNIQUE constraint, caught and translated to the same `DuplicateAttendanceError` | Proves the constraint is real at the DB level, tested directly against Postgres |
| Unauthenticated | No/invalid bearer token on any of the 3 endpoints | 401, same envelope as `get_current_user` (Story 1.1) | No error body leakage |
| Unknown classroom | `GET /classrooms/{id}/students` with a nonexistent id | 404 `{error:{code:"classroom_not_found", message:"Turma não encontrada."}}` | — |
| Student not enrolled | `POST /attendance` with a `student_id` not enrolled in the given `classroom_id` | 422 `{error:{code:"student_not_enrolled", message:"Estudante não está matriculado nesta turma."}}` | Prevents attendance rows disconnected from a real matrícula |

</frozen-after-approval>

## Code Map

- `backend/app/domain/user.py` -- pattern to mirror for new domain dataclasses (frozen, enum for closed sets)
- `backend/app/infrastructure/db/models.py` -- add new ORM models beside `UserModel`; reuse the `SAEnum(..., native_enum=True, validate_strings=True)` pattern already used for `user_role_enum`
- `backend/app/infrastructure/db/base.py` -- reuse `Base`/`SessionLocal`/`get_db` unchanged
- `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py` -- pattern to mirror for the new repositories (Protocol implementation, session injected in `__init__`)
- `backend/alembic/versions/0001_create_users_table.py` -- pattern for the new migration, incl. the native-enum create/drop lifecycle comment (`checkfirst=True` / `create_type=False`)
- `backend/app/composition.py` -- extend with factories for the new services/repos, same `Depends`-chained factory-function style
- `backend/app/presentation/auth/router.py` + `dependencies.py` -- pattern for the new router (`AppError` envelope, `get_current_user` applied for the first time to real routes)
- `backend/app/presentation/errors.py` -- reuse `AppError`/`register_error_handlers` unchanged
- `backend/app/infrastructure/db/seed_dev_user.py` -- idempotent CLI pattern to mirror for the new fixture seed (existence check, `IntegrityError` race guard)
- `backend/app/main.py` -- register the new router beside `auth_router`
- `backend/tests/conftest.py` -- reuse `client`/`db_session` fixtures unchanged; add a seeded-classroom fixture shaped like `seeded_user`
- `frontend/src/api/client.ts` + `schema.d.ts` -- extend with 3 new typed calls; regenerate `schema.d.ts` from `backend/openapi.json`, never hand-edit
- `frontend/src/pages/Login.tsx` -- pattern to mirror for form fields (`useId`, visible label, `fieldStyle`, `aria-describedby` error region)
- `frontend/src/components/Header.tsx` -- add the "Lançamento" nav link here (the IA's "ação global de navegação")
- `frontend/src/App.tsx` -- add the new route behind `ProtectedRoute`

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/domain/classroom.py` -- `Classroom` frozen dataclass (id, name, academic_year) -- AD-2 pure domain
- [ ] `backend/app/domain/student.py` -- `Student` dataclass + `DatasetSplit` enum (TRAIN/EVAL_DEMO) -- AD-4
- [ ] `backend/app/domain/attendance.py` -- `AttendanceRecord` dataclass + `AttendanceStatus` enum (PRESENT/ABSENT_JUSTIFIED/ABSENT_UNJUSTIFIED) -- AD-10
- [ ] `backend/app/infrastructure/db/models.py` -- add `ClassroomModel`, `StudentModel` (dataset_split enum column), `EnrollmentModel`, `AttendanceRecordModel` with `UniqueConstraint("student_id","classroom_id","date")`
- [ ] `backend/alembic/versions/0002_create_attendance_tables.py` -- creates classrooms/students/enrollments/attendance_records + both new native enums + the UNIQUE constraint, migration-only
- [ ] `backend/app/application/attendance/ports.py` -- `ClassroomRepositoryPort`, `StudentRepositoryPort` (list_enrolled, exists_enrollment), `AttendanceRepositoryPort` (save)
- [ ] `backend/app/application/attendance/errors.py` -- `ClassroomNotFoundError`, `StudentNotEnrolledError`, `DuplicateAttendanceError`
- [ ] `backend/app/application/attendance/list_classrooms.py` -- `ListClassroomsService.execute()`
- [ ] `backend/app/application/attendance/list_enrolled_students.py` -- `ListEnrolledStudentsService.execute(classroom_id)`, raises `ClassroomNotFoundError`
- [ ] `backend/app/application/attendance/register_attendance.py` -- `RegisterAttendanceService.execute(...)`: checks enrollment, saves, translates `IntegrityError` -> `DuplicateAttendanceError`
- [ ] `backend/app/infrastructure/repositories/base.py` -- small `dataset_split == EVAL_DEMO` filter helper reused by student-reading repositories (AD-11's repository-base pattern)
- [ ] `backend/app/infrastructure/repositories/sqlalchemy_classroom_repository.py`, `sqlalchemy_student_repository.py`, `sqlalchemy_attendance_repository.py` -- implement the ports above
- [ ] `backend/app/presentation/schemas/attendance.py` -- `ClassroomOut`, `StudentOut`, `AttendanceCreateRequest`, `AttendanceRecordOut`
- [ ] `backend/app/presentation/attendance/router.py` -- `GET /classrooms`, `GET /classrooms/{classroom_id}/students`, `POST /attendance`, all behind `get_current_user`
- [ ] `backend/app/composition.py` -- factories for the 3 new services
- [ ] `backend/app/main.py` -- register the attendance router
- [ ] `backend/app/infrastructure/db/seed_dev_fixtures.py` -- idempotent CLI seeding 2 classrooms + ~8 students each (EVAL_DEMO) + enrollments
- [ ] `backend/tests/test_attendance.py` -- covers every I/O Matrix row against real Postgres, incl. the DB-level UNIQUE bypass test
- [ ] `frontend/src/api/client.ts` -- `listClassrooms`, `listEnrolledStudents`, `registerAttendance`; regenerate `schema.d.ts`
- [ ] `frontend/src/pages/Lancamento/Presenca.tsx` -- turma+data selectors, per-student status `<select>` + save `<button>`, inline confirmation/error per row
- [ ] `frontend/src/components/Header.tsx` -- add "Lançamento" nav link
- [ ] `frontend/src/App.tsx` -- route `/lancamento/presenca` behind `ProtectedRoute`

**Acceptance Criteria:**
- Given a turma with matriculated students (seed fixture), when the coordenação selects turma+data on Lançamento, then it sees every matriculated student with a status selector (Presente/Falta justificada/Falta não justificada).
- Given a status saved for one student, when the coordenação then acts on a different student in the same turma+data, then that student's status saves independently with no modal interrupting the flow.
- Given the `attendance_records` table, when inspected, then it carries `UNIQUE(student_id, classroom_id, date)` at the schema level.
- Given the Lançamento form, when rendered, then every field has a visible label and the save control meets the 44×44px target.

## Implementation Notes

Implemented in full per the Tasks checklist: domain (`Classroom`/`Student`+`DatasetSplit`/`AttendanceRecord`+`AttendanceStatus`), Alembic migration `0002` (classrooms/students/enrollments/attendance_records, both native enums, `UNIQUE(student_id,classroom_id,date)` plus the two constraints added during review), the `attendance` application/infrastructure/presentation stack mirroring the `auth` slice's layering, an idempotent `seed_dev_fixtures.py` (2 classrooms × 8 `EVAL_DEMO` students), and the `Presenca.tsx` per-row Lançamento form wired into `Header`/`App.tsx`.

Verified against a real Postgres 17 container: `alembic upgrade head` → `downgrade` → `upgrade`, `seed_dev_fixtures` run twice (second run no-op), `\d attendance_records` confirming the UNIQUE constraint at the schema level, `pytest` (28/28), `npm run generate:api-types && npm run build`, and `npm run test`.

**Review-driven fixes (Pass 1, all patch-routed):** `exists_enrollment` now applies the same `EVAL_DEMO` filter as `list_enrolled`; `POST /attendance` now returns 404 `classroom_not_found` for a nonexistent classroom instead of a misleading 422; added `UniqueConstraint`s on `enrollments(student_id,classroom_id)` and `classrooms(name)` (the latter making `seed_dev_fixtures.py`'s existing race guard actually effective); `Presenca.tsx`'s student-loading effect now depends on `date` too and ignores stale responses; `handleSave` no-ops if the classroom selection changed mid-flight. See Review Triage Log for the full disposition of all 14 findings across 4 lenses.

**Deferred (not this story's blocker):** no automated frontend test renders `Presenca.tsx` itself (the I/O Matrix's frontend-observable rows are covered at the HTTP/DB layer only) — logged in `docs/deferred-work.md`, same precedent as Story 1.1's analogous Login-form gap.

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verdict counts: 2 medium, 6 low, 5 false. Routing: 7 patch, 1 defer, 5 false (rejected/no action). Zero intent_gap, zero bad_spec — no loopback, `review_loop_iteration` stays 0.

| # | Finding (source) | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `SqlAlchemyStudentRepository.exists_enrollment` never applies the `dataset_split = EVAL_DEMO` filter that its sibling `list_enrolled` does (verification-gap, blind-hunter, edge-case-hunter, intent-alignment — same root cause, grouped) | medium | patch | Confirmed by direct read: `exists_enrollment` queries only `EnrollmentModel`, no join to `StudentModel`. Unreachable today (`seed_dev_fixtures.py` only ever creates `EVAL_DEMO` students) but erodes the AD-4/AD-11 invariant this story's own `repositories/base.py` was introduced to centralize, once Epic 2 introduces `TRAIN` students. Trivial fix (join + filter, mirrors the existing pattern), no public surface added — routes patch, not bad_spec. |
| 2 | `POST /attendance` with a nonexistent `classroom_id` returns 422 `student_not_enrolled` instead of 404 `classroom_not_found` (blind-hunter, edge-case-hunter, grouped) | low | patch | Confirmed: `RegisterAttendanceService` only checks `exists_enrollment`, never classroom existence directly. Unreachable through the UI (classroom_id always comes from `GET /classrooms`) but a real API-contract inconsistency vs. the sibling endpoint for the same underlying condition. Fix is a direct addition (existence check + `ClassroomNotFoundError`), not rejected despite low real-world exposure. |
| 3 | Any `IntegrityError` on `save()`, not only the UNIQUE violation, gets translated to `duplicate_attendance` (edge-case-hunter) | false | — | `exists_enrollment` already guarantees both `student_id`/`classroom_id` reference existing rows (an `EnrollmentModel` row implies valid FKs to both) before `save()` is ever called, and `attendance_records` has no other constraint besides the UNIQUE being translated — no other `IntegrityError` path is reachable in this code today. |
| 4 | `EnrollmentModel` has no `UniqueConstraint(student_id, classroom_id)` (blind-hunter, edge-case-hunter, grouped) | low | patch | Confirmed absent. Only current write path is the idempotent `seed_dev_fixtures.py` (guarded by an existing-classroom-count check), so unreachable today — but the fix is a direct, trivial addition to the still-unreleased `0002` migration, so it doesn't meet the reject bar (fix must be *more than* a direct correction to reject a low finding). |
| 5 | `seed_dev_fixtures.py`'s idempotency claim relies on an `IntegrityError` catch with no backing constraint — a true concurrent race double-inserts classrooms/students instead of no-op'ing (edge-case-hunter, confidence: high) | low | patch | Confirmed: no `UniqueConstraint` on `classrooms.name`, so two concurrent runs both pass the `count() == 0` check and both insert. Directly mirrors `seed_dev_user.py`'s already-reviewed-and-patched TOCTOU fix (Story 1.1 triage #16), which works only because `email` has a real unique index — this script copies the same catch without the constraint that makes it effective. Trivial fix: add `UniqueConstraint("name")` to `classrooms` in migration `0002` (still unreleased). |
| 6 | `Presenca.tsx`'s student-loading `useEffect` depends on `[token, selectedClassroomId]`, not `date` — changing the date for an already-selected turma leaves the previous date's "Registro salvo."/status messages visible (blind-hunter) | medium | patch | Confirmed via direct read of the effect's dependency array. Directly touches this story's own confirmation-accuracy AC and is reachable through completely normal use (logging several dates for the same turma in a row). Trivial fix: add `date` to the dependency array so `rowStates` resets on either change. |
| 7 | Same effect has no cancellation guard — a stale, slower `listEnrolledStudents` response can resolve after a newer one and overwrite the current classroom's roster (edge-case-hunter) | low | patch | Confirmed no `AbortController`/ignore-flag. Requires rapid classroom switching to trigger; fix is a standard, trivial ignore-flag guard. |
| 8 | `handleSave`'s async continuation can run after a classroom switch cleared `rowStates`, writing a stale/malformed entry keyed to a no-longer-relevant student (edge-case-hunter) | low | patch | Confirmed. Narrow window (save in-flight + switch away + switch back before resolution) but a real stale-closure bug; trivial guard (no-op the continuation if the classroom selection changed). |
| 9 | `AttendanceRecord` captures no `created_by`/`created_at` audit trail (blind-hunter) | false | — | `data-model.md`'s canonical `AttendanceRecord` schema is `{id, student_id, classroom_id, date, status}` — no author/timestamp field, unlike `PedagogicalObservation` which explicitly has `author_user_id`. A deliberate difference in the documented model, not an oversight of this story. |
| 10 | No test for `GET /classrooms` with zero fixtures seeded, or `GET /classrooms/{id}/students` for a classroom with zero enrollments (blind-hunter) | low | rejected | Both paths are already correct by construction (`list_all()`/`list_enrolled()` naturally return `[]`; the frontend already renders "Nenhum estudante matriculado nesta turma."). No bad outcome demonstrated — a coverage suggestion for already-correct behavior, not a defect. |
| 11 | `AttendanceStatus` is independently re-declared 4 times (domain enum, 2 Pydantic `Literal`s, native Postgres enum) instead of schemas deriving from the domain enum (blind-hunter) | false | — | Mirrors Story 1.1's own reviewed pattern (`UserOut.role` manually declares `Literal["COORDENACAO_PEDAGOGICA"]` rather than deriving from `UserRole`, per 1.1 triage #9) — consistent with established convention, not a new drift risk. |
| 12 | Migration `downgrade()` and `test_migrations.py`'s teardown both hand-code table/enum drop order with no shared helper (blind-hunter) | false | — | Mirrors the pre-existing `0001_create_users_table.py`/`test_migrations.py` pattern, already present before this story — extends an established convention rather than introducing a new one. |
| 13 | No automated test exercises the frontend-observable half of the I/O Matrix — the "Registro salvo." inline confirmation and the field-adjacent duplicate message in `Presenca.tsx` (intent-alignment, primary divergence) | medium | defer | Confirmed: `test_attendance.py` covers every row at the HTTP/DB layer; no Vitest/RTL test renders `Presenca.tsx`. Directly analogous to Story 1.1 triage #20 (no automated Login-form→redirect test), which was deferred rather than force-patched since the underlying behavior is proven correct at the unit/HTTP level. Same precedent applied here. |
| 14 | The "no error body leakage" (`"detail" not in body`) assertion is only checked for `GET /classrooms`'s 401 test, not the other two new endpoints' 401 tests (intent-alignment, secondary divergence) | false | — | All 3 endpoints share one identical `APIRouter(dependencies=[Depends(get_current_user)])` — a single router-level dependency, not per-route — so there is no code path through which the three endpoints' 401 bodies could diverge. |

## Design Notes

Per-student save (not one bulk submit) is the literal reading of "permitindo lançar o próximo estudante sem interrupção" — each row's `<select>` + `<button>` posts independently; confirmation/duplicate messaging is scoped to that row, not global.

`repositories/base.py`'s EVAL_DEMO filter is intentionally minimal here (one helper, one caller) — AD-11's "classe-base de repositório" is established as a reusable pattern for Stories 1.3+ and Epic 3 to extend, not built out as a generic framework prematurely.

`academic_year` on `Classroom` and `dataset_split` on `Student` are populated now because `data-model.md` already fixes their shape — omitting them would just mean a backfill migration once Epic 2 needs them.

## Verification

**Commands:**
- `cd backend && alembic upgrade head` -- expected: classrooms/students/enrollments/attendance_records created with the UNIQUE constraint and both native enums
- `cd backend && python -m app.infrastructure.db.seed_dev_fixtures` -- expected: 2 classrooms + students + enrollments exist; re-running is a no-op
- `cd backend && pytest` -- expected: all I/O Matrix rows pass, including the DB-level UNIQUE bypass test
- `cd frontend && npm run generate:api-types && npm run build` -- expected: clean build, no manual `schema.d.ts` drift

**Manual checks:**
- Log in, open Lançamento, pick a seeded turma+data, save one student's status, confirm inline "Registro salvo." with no modal, then try saving the same student/turma/date again and confirm the field-adjacent duplicate message with no second row created.
