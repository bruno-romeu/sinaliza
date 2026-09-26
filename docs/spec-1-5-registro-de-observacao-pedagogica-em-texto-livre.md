---
title: 'Registro de observação pedagógica em texto livre (Story 1.5)'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'full'
route_source: 'auto'
baseline_commit: '4df8ebd5b3c1885ee53b24be127958402ffb905e'
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

**Problem:** There is no way yet for the coordenação pedagógica to register a free-text pedagogical observation about a student — `PedagogicalObservation` does not exist in the schema yet (Stories 1.2–1.4 only cover attendance, grades, and assignments/submissions).

**Approach:** Add a "Lançamento de observações" surface following the same shared-turma-context/per-student-row pattern as `Presenca.tsx` (Story 1.2): select a turma, see its matriculated students, and register a free-text observation for any one of them independently, with no read-back UI (append-only "histórico", never an update) — mirroring `RegisterAttendanceService`/`RegisterGradeService`'s single-write-path precedent.

## Boundaries & Constraints

**Always:** the write goes through one application-service method (`RegisterObservationService`), never a router assigning fields directly; `author_user_id` is taken from `get_current_user` (the authenticated bearer's `sub` claim), never a request field; `created_at` is set server-side (`datetime.now(UTC)`), never client-supplied; `POST /pedagogical-observations` requires the existing `get_current_user` bearer dependency; the write checks the classroom exists (404 `classroom_not_found`) then the student is enrolled in it (422 `student_not_enrolled`) — same `exists_enrollment` port and ordering reused from `attendance`/`grades`/`assignments`, even though `classroom_id` is validation-only and is not persisted on `PedagogicalObservation` (mirrors data-model.md's fixed shape: `id, student_id, author_user_id, text, created_at`); `text` is required, non-blank after trimming (`StringConstraints(strip_whitespace=True, min_length=1)`); the save button stays disabled while the text field is empty (UX-DR13); every field has a visible associated label (RNF-08); a successful save shows a brief inline text confirmation, no modal (UX-DR18, consistent with the epic's other Lançamento screens even though this AC set doesn't restate UX-DR18 verbatim).

**Never:** a `follow_up_id` or any FK to `FollowUp`/`TrajectoryChange` on `PedagogicalObservation` (data-model.md: it belongs to the student, not to a follow-up); any visibility-scoping/restriction logic for RF-22 — the epic context and this story's own AC explicitly defer that to Epic 4 (Story 4.4), so no code here restricts who can see an observation; any read-back/listing endpoint for `PedagogicalObservation` in this story (no AC requires displaying past observations, mirrors `Grade`/`AttendanceRecord`'s write-only precedent — unlike `Assignment`, nothing here structurally needs a list to proceed); editing or deleting a saved observation (UX-DR13: "toda ação registrada entra no histórico, nunca substitui uma anterior"); a `follow_up`/`acompanhamento` screen of any kind (Epic 4, out of scope); any `ExtractedSignal`/`SignalReview`/NLP processing of the text (Epic 5, explicitly out of scope for Epic 1 per the epic context).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Turma and student selected; text filled; "Salvar" clicked | `POST /pedagogical-observations` → 201, persisted with `student_id`, `author_user_id` (from the bearer token), `created_at` (server time); inline "Registro salvo." on that row, no modal | No error |
| Blank text (UI gate) | Text field empty | Save button stays disabled | No request sent |
| Whitespace-only text (API bypass) | `POST /pedagogical-observations` with `text: "   "` | Pydantic rejects (stripped to empty, fails `min_length=1`), standard FastAPI 422 | Default validation body, not the `AppError` envelope |
| Unauthenticated | No/invalid bearer token | 401, same envelope as `get_current_user` (Story 1.1) | No error body leakage |
| Unknown classroom | `POST /pedagogical-observations` with a nonexistent `classroom_id` | 404 `{error:{code:"classroom_not_found", message:"Turma não encontrada."}}` | Mirrors attendance/grades/assignments' identical check |
| Student not enrolled | `POST /pedagogical-observations` with a `student_id` not enrolled in `classroom_id` (or a `TRAIN`-split student) | 422 `{error:{code:"student_not_enrolled", message:"Estudante não está matriculado nesta turma."}}` | Mirrors attendance/grades/assignments' identical check |

</frozen-after-approval>

## Code Map

- `backend/app/domain/grade.py` -- reference pattern for a simple frozen-dataclass domain model with no enum
- `backend/app/domain/pedagogical_observation.py` -- NEW: `PedagogicalObservation` frozen dataclass (id, student_id, author_user_id, text, created_at: `datetime`)
- `backend/app/infrastructure/db/models.py` -- add `PedagogicalObservationModel` (student_id FK, author_user_id FK to `users.id`, text `String` unbounded/`Text`, created_at `DateTime(timezone=True)`); no new enum needed
- `backend/alembic/versions/0005_create_pedagogical_observations_table.py` -- NEW migration: `pedagogical_observations` table, FKs to `students`/`users`, indexes (`ix_pedagogical_observations_student_id`, `ix_pedagogical_observations_author_user_id`)
- `backend/app/application/attendance/ports.py` -- `ClassroomRepositoryPort`/`StudentRepositoryPort` reused as-is (import only, no changes)
- `backend/app/application/observations/ports.py` -- NEW: `PedagogicalObservationRepositoryPort` (save)
- `backend/app/application/observations/errors.py` -- NEW: `ClassroomNotFoundError`, `StudentNotEnrolledError` (small, intentionally duplicated, same precedent as Stories 1.3/1.4's Code Map)
- `backend/app/application/observations/register_observation.py` -- NEW: `RegisterObservationService.execute(...)` — checks classroom exists, student enrolled in it, then saves with server-set `created_at`
- `backend/app/infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py` -- NEW: implements `PedagogicalObservationRepositoryPort`
- `backend/app/presentation/schemas/observations.py` -- NEW: `PedagogicalObservationCreateRequest` (classroom_id, student_id, text), `PedagogicalObservationOut`
- `backend/app/presentation/observations/router.py` -- NEW: `POST /pedagogical-observations`, behind `get_current_user`; reads `current_user.id` for `author_user_id`
- `backend/app/composition.py` -- extend with a factory for `RegisterObservationService`
- `backend/app/main.py` -- register the new observations router
- `backend/tests/test_observations.py` -- NEW: covers every I/O Matrix row against real Postgres
- `backend/tests/test_migrations.py` -- extend `migration_engine`'s drop list (new table, no new enum) and the upgrade/downgrade/upgrade assertion for the new table
- `backend/tests/conftest.py` -- no new fixture needed beyond existing `seeded_user`/`seeded_classroom`/`seeded_enrolled_student`
- `frontend/src/api/client.ts` -- extend with `registerPedagogicalObservation`; regenerate `schema.d.ts` from `backend/openapi.json`
- `frontend/src/pages/Lancamento/Observacoes.tsx` -- NEW: turma-shared context; one row per matriculated student with a labeled textarea + save `<button>` disabled while empty, independent per-row save, inline confirmation/error (mirrors `Presenca.tsx`'s `AttendanceRow`, minus the status `<select>`/date field)
- `frontend/src/pages/Lancamento/Observacoes.test.tsx` -- NEW: mirrors `Notas.test.tsx`'s structure — happy path asserting the exact request payload and the per-row confirmation, plus a test asserting the save button is disabled while the textarea is empty
- `frontend/src/components/Header.tsx` -- add a "Lançamento de observações" nav link beside the existing three Lançamento links
- `frontend/src/App.tsx` -- add route `/lancamento/observacoes` behind `ProtectedRoute`

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/domain/pedagogical_observation.py` -- `PedagogicalObservation` frozen dataclass -- AD-2 pure domain
- [x] `backend/app/infrastructure/db/models.py` -- add `PedagogicalObservationModel`
- [x] `backend/alembic/versions/0005_create_pedagogical_observations_table.py` -- creates `pedagogical_observations`, FKs, indexes
- [x] `backend/app/application/observations/ports.py`, `errors.py` -- port + error types
- [x] `backend/app/application/observations/register_observation.py` -- `RegisterObservationService`
- [x] `backend/app/infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py` -- implements the port above
- [x] `backend/app/presentation/schemas/observations.py` -- request/response schemas
- [x] `backend/app/presentation/observations/router.py` -- route behind `get_current_user`
- [x] `backend/app/composition.py` -- factory for the new service
- [x] `backend/app/main.py` -- register the observations router
- [x] `backend/tests/test_observations.py` -- covers every I/O Matrix row
- [x] `backend/tests/test_migrations.py` -- extend for the new table
- [x] `frontend/src/api/client.ts` -- new function; regenerate `schema.d.ts`
- [x] `frontend/src/pages/Lancamento/Observacoes.tsx` -- turma selector + per-student observation rows
- [x] `frontend/src/pages/Lancamento/Observacoes.test.tsx` -- happy-path + blank-text-disables-save coverage
- [x] `frontend/src/components/Header.tsx` -- add "Lançamento de observações" nav link
- [x] `frontend/src/App.tsx` -- route `/lancamento/observacoes` behind `ProtectedRoute`

**Acceptance Criteria:**
- Given a matriculated student, when the coordenação registers a free-text observation about them, then a `PedagogicalObservation` is persisted with a reference to the student, the author (`author_user_id`), and the creation timestamp (RF-08, RF-09).
- Given the observation text field empty, when the coordenação attempts to save, then the save button stays disabled — no blank pedagogical observation is ever recorded (UX-DR13).
- Given a newly created observation not yet cited as evidence of any acompanhamento, when any authenticated user accesses it, then it is visible normally — no visibility restriction is implemented in this story (that is Epic 4/Story 4.4's concern; nothing here builds or enforces it).
- Given the observation form, when rendered, then the text field has a visible associated label and the save button follows the button spec (RNF-08, UX-DR13, UX-DR14).

## Implementation Notes

Implemented in full per the Tasks checklist, dispatched to and completed by an implementation subagent working from this spec alone. Backend: `PedagogicalObservation` frozen dataclass, Alembic migration `0005` adding `pedagogical_observations` (FKs to `students`/`users`, no new native enum, `text` as `Text`, `created_at` as `DateTime(timezone=True)`), `application/observations` ports/errors/`RegisterObservationService` (classroom-exists → 404, then enrollment → 422, then save with server-computed `datetime.now(UTC)` — never a caller-supplied timestamp), the SQLAlchemy repository, `presentation/schemas/observations.py` + `presentation/observations/router.py` (`author_user_id` read from `get_current_user`'s `sub` claim, never a request field), `composition.py`/`main.py` wiring, and `backend/tests/test_observations.py` (8 tests covering every I/O Matrix row: happy path, no-dedup second-observation, whitespace-only and blank-text 422, unauthenticated 401, unknown-classroom 404, not-enrolled 422, `TRAIN`-split-student 422). `test_migrations.py` extended for the new table's upgrade/downgrade/upgrade cycle.

Frontend: `frontend/src/pages/Lancamento/Observacoes.tsx` (NEW) — turma selector → per-student roster, each row a labeled textarea + independent "Salvar" button disabled while the trimmed text is empty, inline "Registro salvo."/error text with no modal, stale-response guard mirroring `Presenca.tsx`'s ref-check pattern; `frontend/src/pages/Lancamento/Observacoes.test.tsx` (NEW) — one test asserting the save button stays disabled for empty/whitespace-only text and issues no request, one happy-path test asserting the exact `POST /pedagogical-observations` payload and the inline confirmation with no `dialog` role rendered; `api/client.ts` gained `registerPedagogicalObservation` (+ types), `schema.d.ts` regenerated from a freshly exported `openapi.json`; `Header.tsx` gained the "Lançamento de observações" nav link; `App.tsx` gained the `/lancamento/observacoes` route behind `ProtectedRoute`.

Verified: `cd backend && pytest` (61/61: 53 baseline + 8 new); `cd frontend && npm run generate:api-types && npm run build` clean (tsc + vite, no manual `schema.d.ts` drift); `cd frontend && npm run test -- --run` (8/8 across 4 test files). Matrix Test Audit (all 6 I/O Matrix rows): happy path, whitespace-only/blank text (both backend 422 and frontend disabled-button), unauthenticated, unknown classroom, student-not-enrolled (including the `TRAIN`-split variant) — all covered by a passing test.

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verdict counts: 1 low (patch), 1 low (defer, pre-existing), 3 low (rejected), 5 false, 1 rejected (fix-edits-spec). Routing: 1 patch, 1 defer, 4 rejected, 5 false (no action). Zero intent_gap, zero bad_spec — no loopback, `review_loop_iteration` stays 0. Verification-gap reported zero qualifying gaps (traced the full I/O Matrix against `test_observations.py`, the migration cycle, and both frontend tests; independently confirmed `schema.d.ts` already carries the new path).

| # | Finding (source) | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `Observacoes.tsx`'s `handleSave` success branch never clears `rowState.text` after a save, so "Salvar" re-enables immediately with the same text still in the field — an accidental re-click creates a genuine duplicate observation with no visual cue distinguishing "unsaved edit" from "already-saved text" (blind-hunter, corroborated independently by verification-gap's aside) | low | patch | Confirmed at `Observacoes.tsx:125` (pre-patch) — `updateRow(studentId, { saving: false, message: 'Registro salvo.', isError: false })` omitted any `text` reset, and `canSave = rowState.text.trim() !== ''` (line 245) stays true right after save. Fixed: success branch now also resets `text: ''`. `Observacoes.test.tsx` asserts only the confirmation message, not textarea contents, so the existing suite is unaffected. |
| 2 | `pedagogical_observations.student_id`/`author_user_id` FKs have no `ondelete` clause, and the repository's `save()` never translates an `IntegrityError` into a domain error, so deleting a referenced student/user later would surface as an unhandled 500 (edge-case-hunter's two findings + blind-hunter's matching one, grouped as one root cause) | low | defer | Confirmed every existing FK in `models.py` (attendance, grades, assignments, submissions) also omits `ondelete`, and `sqlalchemy_grade_repository.py`/`sqlalchemy_assignment_repository.py`/`sqlalchemy_assignment_submission_repository.py` carry the identical "`save` never needs to translate an `IntegrityError`" docstring — this story faithfully reproduces an established, codebase-wide pattern, not a new defect. Logged in `docs/deferred-work.md`. |
| 3 | `POST /pedagogical-observations` is gated only by `get_current_user` (authentication), with no role check — any authenticated user, not only "coordenação pedagógica," can register an observation (blind-hunter) | false | — | Confirmed via `backend/app/domain/user.py`: `UserRole` has exactly one member, `COORDENACAO_PEDAGOGICA` ("It must never gain a second member — there is exactly one profile... AD-8, RF-02"). Every authenticated user in this system is definitionally coordenação pedagógica; there is no other role to distinguish from, and no sibling router (attendance/grades/assignments) implements role checks either. |
| 4 | `text` has no `max_length` constraint, unlike `AssignmentCreateRequest.subject`'s `max_length=255` (blind-hunter, edge-case-hunter) | low | rejected | Confirmed `observations.py:22` has no upper bound while `assignments.py:19` does — a real deviation from a sibling schema, but for an internal, authenticated-staff-only free-text field with no size requirement stated anywhere in the spec, unbounded input is unlikely to be hit in everyday use, and picking a specific cap isn't a direct correction (a 255-char label limit doesn't transfer to a multi-sentence observation) — meets both reject-low conditions. |
| 5 | `StringConstraints(strip_whitespace=True, min_length=1)` doesn't strip zero-width/invisible Unicode whitespace (e.g. U+200B), so an all-invisible-character string could pass the "non-blank" check (edge-case-hunter) | false | — | The spec's own frozen Boundaries & Constraints line defines "non-blank after trimming" as precisely this construct verbatim ("`text` is required, non-blank after trimming (`StringConstraints(strip_whitespace=True, min_length=1)`)"). The code implements exactly the named mechanism; any edge case inherent to it is the frozen intent's own limitation, not an implementation gap. Also requires deliberately crafted API input bypassing the UI, not reachable through normal use. |
| 6 | `uuid.UUID(current_user.id)` in `router.py:38` isn't wrapped in a try/except, so a non-UUID `sub` claim would surface as an unhandled 500 (edge-case-hunter) | false | — | Confirmed `JwtTokenIssuer.issue()` (`jwt_issuer.py:35`) always sets `"sub": str(user.id)` from a UUID-typed domain field, and tokens are HS256-signed/verified before `decode()` returns claims — an authenticated caller cannot supply an arbitrary `sub`; the cited bad outcome has no reachable trigger. |
| 7 | The Implementation Notes' "freshly exported `openapi.json`"/regenerated `schema.d.ts` claims have no corresponding diff hunk (blind-hunter, two findings) | false | — | Confirmed both `backend/openapi.json` and `frontend/src/api/schema.d.ts` are listed in `.gitignore` (lines 16, 21) — generated, intentionally untracked files; their absence from the diff is expected project convention. Confirmed `schema.d.ts` does contain the new `/pedagogical-observations` path in the working tree. |
| 8 | `docs/sprint-status.yaml`'s `1-5-...` entry reads `in-progress` while the spec's own frontmatter says `status: in-review` (blind-hunter) | false | — | Expected transient pipeline state — step-05-present (the next step of this same workflow run) syncs this entry to `review`; not a code defect. |
| 9 | Frontend test coverage is limited to 2 tests (disabled-save-button, happy path); no test for per-row independence across 2+ students, the error/catch path, or the turma-switch stale-response guard (blind-hunter, intent-alignment) | low | rejected | Confirmed by direct read that per-row state is mechanically isolated (`updateRow` keys strictly by `studentId`) and the stale-response guard (`selectedClassroomIdRef`) mirrors `Presenca.tsx`'s already-accepted pattern — correct by inspection, so this is coverage-only. The verification-gap lens (this finding's own category) independently traced the same ground and reported no qualifying gap. Fix requires several new test scenarios, more than a direct correction — meets both reject-low conditions. |
| 10 | AC3 ("visibility... no restriction implemented... visible normally") is unfalsifiable as written since no read path exists yet to observe it against (blind-hunter) | — | rejected | Critique of the AC's own testability, not a code defect in the diff; rejected per the rule that any finding whose fix is to edit this build's spec is rejected outright. |
| 11 | No composite `(student_id, created_at)` index is added, even though Epic 4's eventual observation-history read path will need one (blind-hunter) | low | rejected | Confirmed the migration only adds single-column indexes on `student_id`/`author_user_id`; the intent explicitly places any read/listing path in Epic 4, out of this story's scope, and no current code path queries by `created_at` — a speculative index for a not-yet-designed future query is unlikely to matter now and is more than a direct correction. |

## Design Notes

**One screen, per-student rows, no linked second step (autonomous decision):** unlike Story 1.4 (cadastro + status-de-entrega as two linked steps), this story's single AC set is one flat action — pick a turma, pick a student, write, save — so `Observacoes.tsx` mirrors `Presenca.tsx`'s shape exactly (turma → roster → per-row form + independent save), not `Atividades.tsx`'s two-section shape. Multi-goal check: not split — this is one cohesive feature spanning DB+BE+UI, the SCOPE STANDARD's "don't split" case.

**`classroom_id` is validation-only, never persisted (autonomous decision):** `PedagogicalObservation`'s shape is fixed by `data-model.md` as `{id, student_id, author_user_id, text, created_at}` — no `classroom_id` field. But every prior write in this epic (attendance/grade/assignment-submission) validates "student enrolled" via `StudentRepositoryPort.exists_enrollment(student_id, classroom_id)`, which needs a classroom to check against, and the UI itself only ever knows a student through the turma-scoped roster (`GET /classrooms/{id}/students`). Rather than inventing a new "does this student exist at all" port (no precedent for one, and `Student` has no exposed `get_by_id`), the request accepts `classroom_id` purely to run the same enrollment gate used everywhere else in the epic, then discards it — the persisted row never stores it. This keeps the validation structurally identical to Grade/Assignment-submission's precedent instead of introducing a new checking mechanism for one story.

**AC3 (visibility) is satisfied by absence, not by a read endpoint (autonomous decision):** the epic context is explicit — "the visibility-scoping rule referenced by RF-22 is an Epic 4 concern layered on top later, not something to build here" — and Story 4.4's own AC says the scoping filter "vive no mesmo método de leitura de `PedagogicalObservation` do repositório-base," implying that read method is introduced whenever a read path is first needed, not necessarily in 1.5. Since no AC in this story requires displaying past observations (unlike `Assignment`, which structurally needed `GET /classrooms/{id}/assignments` before a submission could be registered), building a listing/read endpoint now would be scope creep beyond the frozen intent. AC3 is treated as a forward-looking scope note: because no restriction is implemented, an observation is trivially "visible normally" to any code path that might read it later — there is nothing in this story that could visibility-restrict access. No new test is needed to prove a negative; the absence of any scoping code is confirmed by code review (Boundaries & Constraints: "Never... any visibility-scoping/restriction logic for RF-22").

**No duplicate-observation rejection, no UNIQUE constraint (autonomous decision):** mirrors `Grade`/`AssignmentSubmission`'s already-accepted precedent and UX-DR13's own text ("toda ação registrada entra no histórico, nunca substitui uma anterior") — multiple observations for the same student are expected and valid, each a new row.

**Gate self-decisions (autonomous run, no human present):** VCS sanity check passed as-is (branch name matches story, tree clean at start, based on Story 1.4's `done` commit). Epic context (`docs/epic-1-context.md`) verified valid and current — already names Story 1.5's entities and constraints — not recompiled. Previous-story continuity loaded from `docs/spec-1-4-cadastro-de-atividades-e-registro-de-status-de-entrega.md` (status `done`, highest story number below 1.5) — its Code Map, Design Notes, and Tasks list are the direct template for this spec's shape. Token-count gate: kept the full spec (cohesive cross-layer DB+BE+UI feature, same reasoning Stories 1.3/1.4 used). Checkpoint 1: "Approve and continue" — Open Questions is empty, no ambiguity found that required a human decision; this is an unattended pipeline run per the orchestrator's instructions.

## Verification

**Commands:**
- `cd backend && alembic upgrade head` -- expected: `pedagogical_observations` created with FKs
- `cd backend && pytest` -- expected: all I/O Matrix rows pass, plus the migration upgrade/downgrade/upgrade cycle
- `cd frontend && npm run generate:api-types && npm run build` -- expected: clean build, no manual `schema.d.ts` drift
- `cd frontend && npm run test -- --run` -- expected: existing suite + new `Observacoes.test.tsx` all green

**Manual checks:**
- Log in, open Lançamento de observações, pick a seeded turma, pick a student, confirm the save button is disabled with empty text, type an observation, save — confirm inline "Registro salvo." with no modal, and that the textarea can be independently saved again for a different student without disturbing the first row's confirmation.
