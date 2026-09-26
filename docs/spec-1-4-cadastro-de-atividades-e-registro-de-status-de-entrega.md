---
title: 'Cadastro de atividades e registro de status de entrega (Story 1.4)'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'full'
route_source: 'auto'
baseline_commit: 'd7b61f125bf54d170212ba8c08be8b453a917832'
review: 'thorough'
review_source: 'auto'
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
review_loop_iteration: 0
context:
  - '{project-root}/docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/DESIGN.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/EXPERIENCE.md'
  - '{project-root}/docs/data-model.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no way yet for the coordenação pedagógica to register that an activity was assigned to a turma, nor to record whether each enrolled student delivered it — `Assignment` and `AssignmentSubmission` do not exist in the schema yet (only `Classroom`/`Student`/`Enrollment`/`AttendanceRecord`/`AcademicPeriod`/`Grade` exist, from Stories 1.2–1.3).

**Approach:** Add a "Lançamento de atividades" surface with two linked steps sharing one turma context (same shape as Stories 1.2/1.3's shared-context pattern): (1) register an `Assignment` (disciplina, período letivo, data de entrega) against the selected turma; (2) once at least one assignment exists for that turma, select it and register each matriculated student's delivery `status` (entregue/não entregue/parcial) as an `AssignmentSubmission`, one row per student, saved independently — mirroring `Presenca.tsx`/`Notas.tsx`'s "lançar o próximo estudante sem interrupção".

## Boundaries & Constraints

**Always:** both assignment and submission writes go through one application-service method each (`RegisterAssignmentService`, `RegisterSubmissionService`), never a router assigning fields directly; `Assignment` has no CHECK/UNIQUE beyond FK integrity (mirrors `Grade`'s precedent — no AC requires dedup); `AssignmentSubmission.status` is a fixed closed enum (`DELIVERED`, `NOT_DELIVERED`, `PARTIAL`), same native-Postgres-enum + `Literal[...]` pattern as `AttendanceRecord.status`; `POST /assignments`, `GET /classrooms/{classroom_id}/assignments`, `POST /assignment-submissions` all require the existing `get_current_user` bearer dependency; an assignment write checks classroom exists (404 `classroom_not_found`) then period exists (404 `academic_period_not_found`); a submission write checks the assignment exists (404 `assignment_not_found`) then the student is enrolled in the assignment's classroom (422 `student_not_enrolled`, same `exists_enrollment` port reused from `attendance`/`grades`); every field (disciplina, período, data de entrega, atividade, status, data) has a visible label; both the assignment-created and submission-saved confirmations are brief inline text, no modal (UX-DR18).

**Never:** a classroom/student/enrollment/academic-period CRUD screen (unchanged from prior stories); editing/deleting an already-saved assignment or submission (no AC requires it); rejecting a second submission for the same assignment/student as a duplicate — `data-model.md`'s `AssignmentSubmission` carries no UNIQUE constraint, mirroring `Grade`'s already-accepted "no dedup" precedent (a corrected/updated status is simply a new row — there is no read-back/listing endpoint in this MVP, same write-only shape as attendance/grades); validating `due_date` or submission `date` against the selected `period_id`'s window (no AC/RF requires it, same reasoning as Story 1.3 triage #9).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path — cadastro | Turma selected; disciplina+período+data de entrega filled; "Cadastrar atividade" clicked | `POST /assignments` → 201, persisted; inline "Atividade cadastrada." near the form, no modal; new atividade appears in the atividade selector | No error |
| Happy path — status de entrega | Atividade selected; data filled; one student's status chosen, save clicked | `POST /assignment-submissions` → 201, persisted; that row shows "Registro salvo.", no modal | No error |
| Unauthenticated | No/invalid bearer token on any of the 3 endpoints | 401, same envelope as `get_current_user` (Story 1.1) | No error body leakage |
| Unknown classroom (assignment) | `POST /assignments` with a nonexistent `classroom_id` | 404 `{error:{code:"classroom_not_found", message:"Turma não encontrada."}}` | Mirrors attendance/grades' identical check |
| Unknown period (assignment) | `POST /assignments` with a nonexistent `period_id` | 404 `{error:{code:"academic_period_not_found", message:"Período letivo não encontrado."}}` | Mirrors grades' identical check |
| Unknown classroom (list) | `GET /classrooms/{classroom_id}/assignments` with a nonexistent id | 404 `{error:{code:"classroom_not_found", ...}}` | Mirrors `GET /classrooms/{id}/students`'s identical check |
| Unknown assignment (submission) | `POST /assignment-submissions` with a nonexistent `assignment_id` | 404 `{error:{code:"assignment_not_found", message:"Atividade não encontrada."}}` | — |
| Student not enrolled | `POST /assignment-submissions` with a `student_id` not enrolled in the assignment's classroom | 422 `{error:{code:"student_not_enrolled", message:"Estudante não está matriculado nesta turma."}}` | Mirrors attendance/grades' identical check |
| Malformed status (API bypass) | `POST /assignment-submissions` with `status: "FOO"` issued directly | Pydantic rejects, standard FastAPI 422 (untouched, mirrors `AttendanceCreateRequest.status`'s `Literal` precedent) | Default validation body, not the `AppError` envelope |

</frozen-after-approval>

## Code Map

- `backend/app/domain/attendance.py` -- reference pattern for the enum + frozen dataclass shape below
- `backend/app/domain/assignment.py` -- NEW: `Assignment` frozen dataclass (id, classroom_id, subject, period_id, due_date)
- `backend/app/domain/assignment_submission.py` -- NEW: `AssignmentSubmissionStatus` enum (`DELIVERED`, `NOT_DELIVERED`, `PARTIAL`); `AssignmentSubmission` frozen dataclass (id, assignment_id, student_id, status, date)
- `backend/app/infrastructure/db/models.py` -- add `AssignmentModel` (classroom_id FK, subject `String(255)`, period_id FK, due_date `Date`), `AssignmentSubmissionModel` (assignment_id FK, student_id FK, status native enum `assignment_submission_status`, date `Date`); add `assignment_submission_status_enum = SAEnum(...)` alongside the existing enum declarations
- `backend/alembic/versions/0004_create_assignments_tables.py` -- NEW migration: `assignments` + `assignment_submissions` tables, FKs, the new native enum, indexes (`ix_assignments_classroom_id`, `ix_assignments_period_id`, `ix_assignment_submissions_assignment_id`, `ix_assignment_submissions_student_id`)
- `backend/app/application/attendance/ports.py` -- `ClassroomRepositoryPort`/`StudentRepositoryPort` reused as-is (import only, no changes)
- `backend/app/application/academic_periods/ports.py` -- `AcademicPeriodRepositoryPort` reused as-is (import only, no changes)
- `backend/app/application/assignments/ports.py` -- NEW: `AssignmentRepositoryPort` (save, get_by_id, list_by_classroom), `AssignmentSubmissionRepositoryPort` (save)
- `backend/app/application/assignments/errors.py` -- NEW: `ClassroomNotFoundError`, `AcademicPeriodNotFoundError`, `AssignmentNotFoundError`, `StudentNotEnrolledError` (small, intentionally duplicated from `attendance/errors.py`/`grades/errors.py`, same precedent as Story 1.3's Code Map)
- `backend/app/application/assignments/register_assignment.py` -- NEW: `RegisterAssignmentService.execute(...)` — checks classroom exists, period exists, then saves
- `backend/app/application/assignments/list_assignments.py` -- NEW: `ListAssignmentsByClassroomService.execute(classroom_id)` — checks classroom exists, then lists
- `backend/app/application/assignments/register_submission.py` -- NEW: `RegisterSubmissionService.execute(...)` — checks assignment exists, student enrolled in the assignment's classroom, then saves
- `backend/app/infrastructure/repositories/sqlalchemy_assignment_repository.py` -- NEW: implements `AssignmentRepositoryPort`
- `backend/app/infrastructure/repositories/sqlalchemy_assignment_submission_repository.py` -- NEW: implements `AssignmentSubmissionRepositoryPort`
- `backend/app/presentation/schemas/assignments.py` -- NEW: `AssignmentCreateRequest`, `AssignmentOut`, `AssignmentSubmissionCreateRequest` (status: `Literal["DELIVERED","NOT_DELIVERED","PARTIAL"]`), `AssignmentSubmissionOut`
- `backend/app/presentation/assignments/router.py` -- NEW: `POST /assignments`, `GET /classrooms/{classroom_id}/assignments`, `POST /assignment-submissions`, all behind `get_current_user`
- `backend/app/composition.py` -- extend with factories for the 3 new services
- `backend/app/main.py` -- register the new assignments router
- `backend/tests/test_assignments.py` -- NEW: covers every I/O Matrix row against real Postgres, plus the "allows a second submission" case (mirrors `test_grades.py`'s dedup-precedent test) and the `TRAIN`-split-student rejection case (mirrors `test_grades.py`)
- `backend/tests/test_migrations.py` -- extend `migration_engine`'s drop list (tables + new enum type) and the upgrade/downgrade/upgrade assertions for the 2 new tables
- `backend/tests/conftest.py` -- add a `seeded_assignment` fixture (built on `seeded_classroom` + `seeded_academic_period`, shaped like `seeded_academic_period`)
- `frontend/src/api/client.ts` -- extend with `registerAssignment`, `listAssignmentsByClassroom`, `registerAssignmentSubmission`; regenerate `schema.d.ts` from `backend/openapi.json`
- `frontend/src/pages/Lancamento/Atividades.tsx` -- NEW: turma-shared context; a "Cadastrar atividade" sub-form (disciplina/período/data de entrega + inline confirmation); an atividade `<select>` populated from `GET /classrooms/{id}/assignments`; once an atividade + data are set, one row per matriculated student with a status `<select>` + save `<button>`, inline confirmation/error per row (mirrors `Presenca.tsx`'s `AttendanceRow`)
- `frontend/src/pages/Lancamento/Atividades.test.tsx` -- NEW: mirrors `Notas.test.tsx`'s structure — happy path for both the assignment-creation POST and the submission POST, asserting each inline confirmation and the exact request payloads
- `frontend/src/components/Header.tsx` -- add a "Lançamento de atividades" nav link beside the existing "Lançamento"/"Lançamento de notas" links
- `frontend/src/App.tsx` -- add route `/lancamento/atividades` behind `ProtectedRoute`

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/domain/assignment.py` -- `Assignment` frozen dataclass -- AD-2 pure domain
- [x] `backend/app/domain/assignment_submission.py` -- `AssignmentSubmissionStatus` enum + `AssignmentSubmission` frozen dataclass -- AD-10
- [x] `backend/app/infrastructure/db/models.py` -- add `AssignmentModel`, `AssignmentSubmissionModel` + new native enum
- [x] `backend/alembic/versions/0004_create_assignments_tables.py` -- creates `assignments`/`assignment_submissions`, FKs, enum, indexes
- [x] `backend/app/application/assignments/ports.py`, `errors.py` -- ports + error types
- [x] `backend/app/application/assignments/register_assignment.py` -- `RegisterAssignmentService`
- [x] `backend/app/application/assignments/list_assignments.py` -- `ListAssignmentsByClassroomService`
- [x] `backend/app/application/assignments/register_submission.py` -- `RegisterSubmissionService`
- [x] `backend/app/infrastructure/repositories/sqlalchemy_assignment_repository.py`, `sqlalchemy_assignment_submission_repository.py` -- implement the ports above
- [x] `backend/app/presentation/schemas/assignments.py` -- request/response schemas
- [x] `backend/app/presentation/assignments/router.py` -- 3 routes behind `get_current_user`
- [x] `backend/app/composition.py` -- factories for the 3 new services
- [x] `backend/app/main.py` -- register the assignments router
- [x] `backend/tests/conftest.py` -- `seeded_assignment` fixture
- [x] `backend/tests/test_assignments.py` -- covers every I/O Matrix row
- [x] `backend/tests/test_migrations.py` -- extend for the new tables/enum
- [x] `frontend/src/api/client.ts` -- new functions; regenerate `schema.d.ts`
- [x] `frontend/src/pages/Lancamento/Atividades.tsx` -- cadastro sub-form + atividade selector + per-student status rows
- [x] `frontend/src/pages/Lancamento/Atividades.test.tsx` -- happy-path coverage for both POSTs
- [x] `frontend/src/components/Header.tsx` -- add "Lançamento de atividades" nav link
- [x] `frontend/src/App.tsx` -- route `/lancamento/atividades` behind `ProtectedRoute`

**Acceptance Criteria:**
- Given a turma, disciplina, and período letivo, when the coordenação cadastra uma atividade informando data de entrega, then the atividade is persisted and appears in the atividade selector for that turma, available for status-de-entrega registration against its matriculated students (RF-06).
- Given an atividade cadastrada, when the coordenação registra o status de entrega de um estudante (entregue, não entregue, or parcial), then an `AssignmentSubmission` is persisted linked to that atividade and that estudante (RF-07).
- Given the atividade-registration form and the status-de-entrega form, when rendered, then every field has a visible associated label (RNF-08).
- Given a successful cadastro or registro, when the operation completes, then a brief inline text confirmation appears with no blocking modal (UX-DR18).

## Implementation Notes

Implemented in full per the Tasks checklist. The backend vertical slice (domain `Assignment`/`AssignmentSubmission` + `AssignmentSubmissionStatus` enum, Alembic migration `0004` adding `assignments`/`assignment_submissions` + the new native `assignment_submission_status` enum + 4 indexes, the `application/assignments` ports/errors/services, the two SQLAlchemy repositories, the `presentation/schemas/assignments.py` + `presentation/assignments/router.py` 3-route router, `composition.py` factories, `main.py` registration) already existed on disk (built in an earlier session of this same pipeline run) and was verified rather than rewritten — it matches the spec's Code Map and I/O Matrix exactly, including the `TRAIN`-split-student rejection test mirroring `test_grades.py`'s precedent and the "second submission allowed" no-dedup test.

Completed in this pass: `frontend/src/api/client.ts` extended with `registerAssignment`, `listAssignmentsByClassroom`, `registerAssignmentSubmission` (+ `Assignment`/`AssignmentSubmission`/`*CreateRequest` types), `frontend/src/api/schema.d.ts` regenerated from a freshly exported `backend/openapi.json`; `frontend/src/pages/Lancamento/Atividades.tsx` (NEW) — shared turma context, a "Cadastrar atividade" sub-form (disciplina/período/data de entrega) with inline "Atividade cadastrada." confirmation that refreshes the atividade `<select>` via `GET /classrooms/{id}/assignments`, then once an atividade + data are set, one row per matriculated student (mirrors `Presenca.tsx`'s `AttendanceRow`) with a status `<select>` (Entregue/Não entregue/Parcial) + independent per-row save and inline "Registro salvo."/error text; `frontend/src/pages/Lancamento/Atividades.test.tsx` (NEW) — happy-path coverage for both the assignment-creation POST (asserts the exact request body and that the new atividade appears in the selector) and the submission POST (asserts the exact request body and the per-row confirmation); `Header.tsx` gained the "Lançamento de atividades" nav link; `App.tsx` gained the `/lancamento/atividades` route behind `ProtectedRoute`.

Verified: `cd backend && pytest` (53/53, incl. the migration upgrade/downgrade/upgrade cycle for the 2 new tables + enum); `alembic upgrade head` against the test DB applies 0001→0004 cleanly; `cd frontend && npx tsc --noEmit` clean; `npm run generate:api-types && npm run build` clean (no manual `schema.d.ts` drift); `npm run test -- --run` (6/6, all pre-existing + the 2 new `Atividades.test.tsx` tests).

**Review-driven fixes (Pass 1, all patch-routed):** `refreshAssignments`'s `.then()`/`.catch()` now discard a stale response if the turma changed while the request was in flight (mirrors the ref-guard pattern already used elsewhere in the file); `handleCreateAssignment` now resets `creatingAssignment` unconditionally in both branches instead of only when the turma is unchanged, so a mid-request turma switch can no longer strand the "Cadastrar atividade" button disabled; the turma-change effect now clears `assignmentMessage`/`assignmentMessageIsError` so a stale confirmation/error from the previous turma no longer lingers; `AssignmentCreateRequest.subject` now uses `StringConstraints(strip_whitespace=True, min_length=1, max_length=255)` so a whitespace-only disciplina is rejected instead of persisted; `handleCreateAssignment` now clears `subject`/`periodId`/`dueDate` back to blank/today's date after a successful cadastro; an inline message now appears when a turma has zero atividades, directing the user to cadastro first. See Review Triage Log for the full disposition of all 19 findings across 4 lenses.

**Deferred (not this story's blocker, logged in `docs/deferred-work.md`):** there is no `AssignmentSubmission` read-back — excluded by the frozen intent itself (mirrors `Grade`'s already-accepted Story 1.3 precedent). `test_migrations.py`'s downgrade assertions never verify the native enum types are actually dropped — an unaddressed pattern present since migration `0001`, not caused by this story.

Re-verified after the patch round: `pytest` (53/53), `npm run build` (clean, no `schema.d.ts` drift after regenerating from a freshly exported `openapi.json`), `npm run test -- --run` (6/6).

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verdict counts: 3 medium, 6 low, 9 false, 1 low (unverified, treated as pre-existing). Routing: 6 patch, 2 defer, 2 low-rejected, 9 false (rejected/no action). Zero intent_gap, zero bad_spec — no loopback, `review_loop_iteration` stays 0. Verification-gap reported zero findings (explicitly traced 404/422 ordering, auth gating, `exists_enrollment` argument order, and the migration/enum lifecycle; a suspected `handleSaveSubmission` race was investigated and dropped as ungrounded).

| # | Finding (source) | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `refreshAssignments`'s `.then(setAssignments)` has no guard against a stale response landing after the user switches turma — a fast classroom switch can display the wrong turma's atividade list (blind-hunter's missing-ignore-flag finding, grouped with edge-case-hunter's identical race) | medium | patch | Confirmed by direct read of `Atividades.tsx:114-128` — no ref-check inside the `.then()`, unlike the enrolled-students effect's own `ignore` guard in the same file. A late response can paint a different turma's atividade list into the selector, risking a submission tied to the wrong turma's assignment (caught downstream only by the backend's `student_not_enrolled` 422). |
| 2 | `handleCreateAssignment`'s success/error branches only call `setCreatingAssignment(false)` after the `selectedClassroomIdRef.current !== classroomIdAtStart` early-return, so switching turma mid-request leaves the "Cadastrar atividade" button permanently disabled (edge-case-hunter) | medium | patch | Confirmed by direct read of `Atividades.tsx:184-196` — the early `return` skips `setCreatingAssignment(false)` entirely, and `creatingAssignment` is component-level state, not scoped per turma, so the button stays stuck on "Cadastrando…" for the rest of the session once this race fires. |
| 3 | The effect that resets `selectedAssignmentId`/`assignments` on turma change never clears `assignmentMessage`/`assignmentMessageIsError`, so a stale confirmation/error from the previous turma stays visible under the newly selected turma's form (edge-case-hunter) | low | patch | Confirmed by direct read of `Atividades.tsx:122-128` — no reset of either state variable. Reachable in normal use (switch turma right after a cadastro); fix is a direct two-line addition to the existing effect. |
| 4 | `AssignmentCreateRequest.subject`'s `Field(min_length=1, max_length=255)` accepts a whitespace-only string, letting a blank disciplina persist (edge-case-hunter) | low | patch | Confirmed by direct read of `backend/app/presentation/schemas/assignments.py:16` — `min_length=1` counts a lone space as valid; no strip/re-check. Fix is a direct swap to a strip-then-validate constraint, no new public surface. |
| 5 | `handleCreateAssignment` never clears `subject`/`periodId`/`dueDate` after a successful cadastro, requiring the coordenação to manually overwrite stale values to register a second, different atividade for the same turma (blind-hunter) | low | patch | Confirmed by direct read — none of the three fields are reset in the success branch. Direct, trivial fix (reset to blank/today's date), no new surface. |
| 6 | When a turma has zero assignments, the entire "Status de entrega" section is hidden with no guidance directing the user back to "Cadastrar atividade" first (blind-hunter) | low | patch | Confirmed: the section is gated on `assignments.length > 0` with no fallback message, unlike the "Nenhum estudante matriculado nesta turma." message that exists for the analogous empty-roster case. Direct, trivial addition. |
| 7 | There is no `AssignmentSubmission` read-back — the per-student status `<select>` always defaults to "Entregue" with no way to see which students already have a status recorded (blind-hunter) | medium | defer | Real gap, but excluded by the intent itself, not just this spec's scope section: the frozen "Never" bullet explicitly states "there is no read-back/listing endpoint in this MVP, same write-only shape as attendance/grades," mirroring `Grade`'s already-accepted Story 1.3 precedent (that spec's identical `GET /grades` deferral, never flagged there either). Logged in `docs/deferred-work.md`. |
| 8 | `test_migrations.py`'s upgrade/downgrade/upgrade cycle never asserts the `assignment_submission_status` (or any of the 3 prior) native enum type is actually dropped by `downgrade()`; `checkfirst=True` on both `create()`/`drop()` could mask a failed drop (blind-hunter) | low (unverified) | defer | Confirmed via direct read that only `to_regclass` table-existence checks exist, no `pg_type`/`to_regtype` check for any of the 4 native enums. Identical, unaddressed pattern present since migration `0001` (Story 1.1), never flagged in Stories 1.1–1.3's own reviews — pre-existing, not caused by this story. Logged in `docs/deferred-work.md`. |
| 9 | Changing the "Data" field in the status-de-entrega step re-triggers the enrolled-students effect, resetting `rowStates` and discarding any unsaved per-row status selections/messages (blind-hunter) | low | rejected | Confirmed the effect's dependency array includes `submissionDate`, clearing `rowStates` on every change. No AC requires preserving unsaved selections across a date correction; already-saved rows' data is unaffected server-side (only the local "Registro salvo." confirmation resets). Fix would require nontrivial state-merging logic (more than a direct correction), and the scenario (editing date mid-entry) is uncommon — meets both reject-low conditions. |
| 10 | Frontend test coverage is limited to one happy-path test per POST flow; no test drives multiple students' rows in the same session, no in-flight-save interference test, no empty-atividade-list or no-enrolled-students state coverage, no 401/404/422 surfacing test on the page (intent-alignment, describing where the diff's rigor diverges from its own test symmetry with the backend) | low | rejected | Verified `Atividades.test.tsx` has exactly 2 tests. Matches the Code Map's own explicit scope ("mirrors `Notas.test.tsx`'s structure — happy path for both POSTs") and the resulting precedent Story 1.3's own review left in place (one happy-path test per flow, no multi-row/error coverage added there either). Fix (several new test scenarios) is more than a direct correction; rejected under the same reasoning as the low-rejection rule. |
| 11 | No test proves `GET /classrooms/{classroom_id}/assignments` is scoped to the requested classroom (no cross-classroom-leakage test) (blind-hunter) | false | — | Confirmed via direct read of `sqlalchemy_assignment_repository.py:58-65` — `list_by_classroom` already filters `.where(AssignmentModel.classroom_id == classroom_id)`. Coverage-only suggestion for already-correct behavior, same grounds as Story 1.3 triage #11/#12's rejections of the identical finding class. |
| 12 | No backend test exercises `subject` length validation (empty or >255 chars) (blind-hunter) | false | — | `AssignmentCreateRequest.subject` already declares `Field(min_length=1, max_length=255)`, standard Pydantic-enforced behavior. Coverage-only suggestion, same grounds as Story 1.3 triage #11/#12. |
| 13 | No backend test exercises a malformed/missing `due_date` on `POST /assignments` (blind-hunter) | false | — | `due_date: date` is a standard Pydantic-typed field; malformed input is rejected by the framework itself, same precedent as `AttendanceCreateRequest`'s UUID-typed fields (never separately tested there either). Coverage-only suggestion. |
| 14 | No test verifies `ListAssignmentsByClassroomService`/`list_by_classroom` results are ordered by `due_date` (blind-hunter) | false | — | Confirmed the repository's `select(...).order_by(AssignmentModel.due_date)` is already correct. Coverage-only suggestion for already-correct behavior, same grounds as Story 1.3 triage #11. |
| 15 | The `classrooms`/`periods`-loading effect in `Atividades.tsx` lacks the `ignore`-flag cleanup pattern used by the enrolled-students effect (blind-hunter; the assignments-loading effect's identical gap is finding #1 above, not this one) | false | — | The `classrooms`/`periods` effect is an identical, pre-existing pattern already shipped in `Presenca.tsx`/`Notas.tsx`'s equivalent first effect (Stories 1.2/1.3), never flagged there — `Atividades.tsx` faithfully mirrors the established convention rather than introducing a new gap. |
| 16 | The spec's frozen "Never" bullet says "there is no read-back/listing endpoint in this MVP" while this same story ships `GET /classrooms/{classroom_id}/assignments` (blind-hunter) | false | — | Misreads scope: that clause is specifically about rejecting duplicate *submissions* / `AssignmentSubmission` read-back ("a corrected/updated status is simply a new row — there is no read-back/listing endpoint..."), not about the `Assignment` listing endpoint, which the same frozen text and the Design Notes explicitly call in-scope. Not a contradiction. |
| 17 | No composite index on `assignment_submissions(assignment_id, student_id)` (blind-hunter) | false | — | No query path in this codebase would use it — the only feature that would need it (submission read-back/dedup lookup) is itself deferred per finding #7. Premature optimization for a feature that doesn't exist yet, same grounds as Story 1.3 triage #14. |
| 18 | "Unverifiable precedent" — claimed that `Presenca.tsx`, `Notas.tsx`, the `grades` application module, and `backend/tests` Python files do not exist, so the diff's mirroring claims can't be checked (intent-alignment) | false | — | The reviewer inspected `C:\Users\Bruno\dev\sinaliza` (the main checkout), not this story's worktree (`C:\Users\Bruno\dev\sinaliza-wt-1-4`). Direct inspection of the actual worktree confirms `Presenca.tsx`, `Notas.tsx`, `Header.tsx`, `App.tsx`, `backend/app/application/grades/`, and `backend/tests/test_grades.py` all exist and are the real precedent this diff mirrors. |
| 19 | Scope additions beyond the literal intent text — the listing endpoint, no-duplicate-submission rule, TRAIN-split filter, and malformed-status handling are elaborations from other stories' precedent, not stated in the verbatim intent (intent-alignment) | false | — | Descriptive only, no bad outcome asserted by the reviewer. Each addition is independently justified in the frozen Boundaries & Constraints and this spec's own Design Notes (dataset-split filter mirrors `attendance`/`grades`'s `exists_enrollment` precedent; the listing endpoint is required by the ACs themselves since submission registration is impossible without it). |

## Design Notes

**One screen, two linked steps (autonomous decision):** the AC's two Given/When/Then pairs (cadastro da atividade; registro de status por estudante) are one cohesive "lançamento de atividades" session, not two separate stories — same precedent as Stories 1.2/1.3 treating shared selection context (turma+date, turma+disciplina+período+data) as one Lançamento flow rather than splitting per field group. Multi-goal check: not split — cadastro and status-registro are sequentially dependent (status registration requires a previously-cadastrada atividade) and share the turma context end-to-end across all layers, exactly the "single cohesive feature spanning multiple layers/files" case the SCOPE STANDARD's "don't split" examples describe.

**Assignment selection surfaces via a live list, not a second navigation (autonomous decision):** `GET /classrooms/{classroom_id}/assignments` is the read-back endpoint this story needs internally (to populate the atividade `<select>` right after creating one) — unlike `Grade`/`AttendanceRecord`, which are genuinely write-only with no in-story read-back requirement, `AssignmentSubmission` registration is *impossible* without first knowing which atividades exist for the turma, so this one listing endpoint is in-scope by the ACs themselves, not a deferred "review" feature.

**No duplicate-submission rejection (autonomous decision):** confirmed against `data-model.md` — `AssignmentSubmission` carries no UNIQUE constraint and neither AC here mentions rejecting a repeat status. Mirrors `Grade`'s already-accepted Story 1.3 precedent exactly (a student's status may legitimately be re-entered/corrected as a new row; there is no update/read-back UI in this MVP).

**Gate self-decisions (autonomous run, no human present):** VCS sanity check passed as-is (branch name matches story, tree clean at start). Epic context (`docs/epic-1-context.md`) verified valid and current — already names Story 1.4's entities and constraints — not recompiled. Token-count gate: kept the full spec (cohesive cross-layer DB+BE+UI feature, same reasoning Story 1.3 used when its own spec exceeded 1600 tokens). Checkpoint 1: "Approve and continue" — Open Questions is empty, no ambiguity found that required a human decision.

## Verification

**Commands:**
- `cd backend && alembic upgrade head` -- expected: `assignments`/`assignment_submissions` created with FKs and the new enum
- `cd backend && python -m app.infrastructure.db.seed_dev_fixtures` -- expected: no-op (this story adds no new dev-fixture seeding — assignments are created through the UI itself, not seeded)
- `cd backend && pytest` -- expected: all I/O Matrix rows pass, plus the migration upgrade/downgrade/upgrade cycle
- `cd frontend && npm run generate:api-types && npm run build` -- expected: clean build, no manual `schema.d.ts` drift
- `cd frontend && npm run test -- --run` -- expected: existing suite + new `Atividades.test.tsx` all green

**Manual checks:**
- Log in, open Lançamento de atividades, pick a seeded turma, fill disciplina/período/data de entrega, cadastrar — confirm inline "Atividade cadastrada." with no modal and the new atividade appears in the selector; pick it, set data, register one student's status, confirm inline "Registro salvo." with no modal.
