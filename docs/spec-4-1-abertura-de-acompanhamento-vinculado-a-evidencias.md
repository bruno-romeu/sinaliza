---
title: 'Abertura de acompanhamento vinculado a evidências'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_commit: '3c6d83fd84945ca7cf08640f8b8500ff891d6222'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 3's trajectory page shows reviewed evidence but has only a disabled "Abrir acompanhamento" button (Story 3.4 explicitly deferred it); there is no `FollowUp`/`FollowUpEvidence` persistence yet, so a coordenação cannot start a tracked case from evidence.

**Approach:** Add `FollowUp`/`FollowUpEvidence` domain+persistence, a `POST /follow-ups` endpoint that opens a follow-up linked to exactly the displayed `TrajectoryChange`, a `GET /follow-ups/{id}` endpoint, and a new minimal Tela de Acompanhamento. Enable the trajectory page's button when a change exists; clicking it creates the follow-up and navigates to the new screen. Also implement the freeze-on-evidence guard on the trajectory-change upsert that Story 3.2 explicitly deferred to this epic.

## Boundaries & Constraints

**Always:**
- `FollowUp` is created with `status=EM_OBSERVACAO`, `responsible_user_id` = authenticated user (never a request field), linked via one `FollowUpEvidence` row to the `trajectory_change_id` the button was clicked from (RF-12, RF-22). `reason`/`next_review_date` are left `NULL` — no UI captures them in this story.
- `FollowUpEvidence.trajectory_change_id` is a real `NOT NULL` FK (RNF-11, AD-7); `FollowUp` + `FollowUpEvidence` are written in one transaction, same atomicity pattern as `TrajectoryChange`+`TrajectoryChangeSource` (AD-7).
- Opening a follow-up is always an explicit click — never auto-attached when a new `TrajectoryChange` later appears for an already-open `FollowUp` (AD-1).
- `FollowUp.status` is a native Postgres enum, 4 closed values, same `SAEnum`/migration idiom as `trajectory_change_type` (AD-6).
- Implement the freeze-on-evidence guard deferred from Story 3.2: once a `TrajectoryChange` has ≥1 `FollowUpEvidence` row, `sqlalchemy_trajectory_change_repository.py`'s upsert must leave it unchanged (`detected_at`/`description`/sources) instead of `DO UPDATE`.
- Tela de Acompanhamento (`/acompanhamentos/:followUpId`) shows the status pill ("Em observação") and the evidence card reused from the Trajectory page, with a "Ver na trajetória de [aluno]" link back (UX-DR4). Loading = skeleton, error = factual message + retry, nonexistent follow-up = factual message + link to Home — same conventions as `EstudanteTrajetoria.tsx` (Story 3.4).
- `TrajectoryChangeOut` gains an additive `id` field (needed so the frontend can submit `trajectory_change_id`) — existing `/trajectory` and `/trajectory/detail` response shapes are otherwise untouched.

**Never:**
- Never let the router mutate `FollowUp` state directly — only an application-service method (AD-6, generalized beyond this story).
- Never implement status transitions, the action form, full history, or Home's active-follow-ups section — Stories 4.2/4.3/4.5 scope. The new screen only needs to satisfy this story's ACs.
- Never filter `PedagogicalObservation` visibility here — Story 4.4 scope; evidence resolution reuses Story 3.4's existing, unfiltered reads as-is.
- Never add a GRANT/privilege migration for `follow_up_action` — that table doesn't exist until Story 4.2.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Open follow-up | Student has a current `trajectory_change`; button clicked | `POST /follow-ups` creates `FollowUp`(EM_OBSERVACAO)+`FollowUpEvidence`; frontend navigates to `/acompanhamentos/:id` | No error expected |
| Unknown trajectory_change_id | Payload references a nonexistent/foreign id | 404 `trajectory_change_not_found` | UI shows inline error, stays on trajectory page |
| student_id/trajectory_change mismatch | `trajectory_change.student_id != payload.student_id` | 422 `trajectory_change_mismatch` | Same as above |
| Recompute after evidence exists | Trajectory re-detected for a period whose change already has `FollowUpEvidence` | Upsert leaves `description`/`detected_at`/sources unchanged (frozen) | No error expected |
| View follow-up | `GET /follow-ups/{id}` for an existing id | Returns status, student name, evidence list | — |
| Nonexistent follow-up | Invalid/removed id | 404 `follow_up_not_found` | UI: factual message + link to Home |

</frozen-after-approval>

## Code Map

- `backend/app/domain/follow_up.py` -- NEW: `FollowUpStatus` enum (`EM_OBSERVACAO`, `ACOMPANHAMENTO_ATIVO`, `AGUARDANDO_RETORNO`, `ENCERRADO`), frozen dataclasses `FollowUp{id,student_id,status,reason:str|None,responsible_user_id,next_review_date:date|None,created_at}`, `FollowUpEvidence{id,follow_up_id,trajectory_change_id}`. Mirrors `domain/trajectory_change.py` style (pure, zero framework imports).
- `backend/alembic/versions/0008_create_follow_up_tables.py` -- NEW: mirrors `0007_create_trajectory_change_tables.py`'s explicit `checkfirst=True`/`create_type=False` enum lifecycle. `follow_up_status` enum; `follow_ups(id, student_id FK students.id, status, reason nullable Text, responsible_user_id FK users.id, next_review_date nullable Date, created_at)`; `follow_up_evidence(id, follow_up_id FK follow_ups.id NOT NULL, trajectory_change_id FK trajectory_changes.id NOT NULL)`, index on both FKs.
- `backend/app/infrastructure/db/models.py` -- EXTEND: `follow_up_status_enum = SAEnum(FollowUpStatus, name="follow_up_status", native_enum=True, validate_strings=True)`; `FollowUpModel`, `FollowUpEvidenceModel` (same shape as `TrajectoryChangeModel`/`TrajectoryChangeSourceModel`, no `ondelete`, codebase-wide accepted gap).
- `backend/app/application/trajectory/ports.py` -- EXTEND: add `get_by_id(change_id) -> TrajectoryChange | None` to `TrajectoryChangeRepositoryPort`.
- `backend/app/application/trajectory/evidence.py` -- NEW: extract `EvidenceItem` dataclass + `resolve_evidence(trajectory_change_id, source_repo, attendance_repo, grade_repo, submission_repo, observation_repo) -> list[EvidenceItem]` out of `get_student_trajectory_detail.py`'s `_resolve_evidence`/`_resolve_items_for_type`/description-helper methods verbatim (same `_SOURCE_TYPE_ORDER`, same per-type description strings) — shared by `GetStudentTrajectoryDetailService` and the new `GetFollowUpService` so the evidence card is genuinely one resolution path, not two. Update `get_student_trajectory_detail.py` to import and call it, dropping its now-duplicate private methods.
- `backend/app/application/followups/__init__.py`, `errors.py` -- NEW: `TrajectoryChangeNotFoundError`, `TrajectoryChangeMismatchError`, `FollowUpNotFoundError` (plain `Exception` subclasses, per-slice pattern like `application/observations/errors.py`).
- `backend/app/application/followups/ports.py` -- NEW: `FollowUpRepositoryPort` protocol: `save_with_evidence(follow_up: FollowUp, evidence: list[FollowUpEvidence]) -> FollowUp` (one transaction); `get_by_id(id) -> FollowUp | None`; `list_evidence_by_follow_up(follow_up_id) -> list[FollowUpEvidence]`. Re-imports `TrajectoryChangeRepositoryPort`, `TrajectoryChangeSourceRepositoryPort`, `AttendanceRepositoryPort`, `GradeRepositoryPort`, `AssignmentSubmissionRepositoryPort`, `PedagogicalObservationRepositoryPort`, `StudentRepositoryPort` from `application/trajectory/ports.py` (no duplicate protocol defs).
- `backend/app/application/followups/open_follow_up.py` -- NEW: `OpenFollowUpService.execute(student_id, trajectory_change_id, responsible_user_id) -> FollowUp`. Loads the change via `TrajectoryChangeRepositoryPort.get_by_id`; raises `TrajectoryChangeNotFoundError` if `None`; raises `TrajectoryChangeMismatchError` if `change.student_id != student_id`. Builds `FollowUp(id=uuid4(), student_id, status=EM_OBSERVACAO, reason=None, responsible_user_id, next_review_date=None, created_at=datetime.now(UTC))` + one `FollowUpEvidence(id=uuid4(), follow_up_id, trajectory_change_id)`; calls `save_with_evidence`.
- `backend/app/application/followups/get_follow_up.py` -- NEW: `GetFollowUpService.execute(follow_up_id) -> FollowUpDetailResult{follow_up, student_name, evidence: list[EvidenceItem]}`. Raises `FollowUpNotFoundError`. Resolves student name via `StudentRepositoryPort.get_by_id`; evidence via one `list_evidence_by_follow_up` call then `resolve_evidence` per linked `trajectory_change_id` (concatenated, story 4.1 always has exactly one).
- `backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- NEW: implements `FollowUpRepositoryPort` on `FollowUpModel`/`FollowUpEvidenceModel`, plain inserts (no upsert needed — always a fresh row), single `session.commit()` after both inserts.
- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- EXTEND: add `get_by_id`. Add freeze-on-evidence guard to `upsert`: build `where=~exists(select(FollowUpEvidenceModel.id).where(FollowUpEvidenceModel.trajectory_change_id == TrajectoryChangeModel.id))`, pass as `on_conflict_do_update(..., where=...)`, use `.scalar_one_or_none()` instead of `.scalar_one()`. When `None` (frozen — the WHERE blocked the update), `SELECT` the full existing row by `(student_id, type, period_id)` instead, `commit()`, and return it **without** touching `TrajectoryChangeSource` rows (skip delete+reinsert in that branch — the whole point of freezing). When not `None`, proceed exactly as today (delete+reinsert sources, return the upserted values).
- `backend/app/presentation/schemas/trajectory.py` -- EXTEND: add `id: uuid.UUID` to `TrajectoryChangeOut`.
- `backend/app/presentation/trajectory/router.py` -- EXTEND: populate `id=result.trajectory_change.id` in both `TrajectoryChangeOut(...)` call sites.
- `backend/app/presentation/schemas/follow_ups.py` -- NEW: `OpenFollowUpRequest{student_id: uuid.UUID, trajectory_change_id: uuid.UUID}`; `FollowUpOut{id, student_id, status: Literal[4 values], created_at}`; `FollowUpDetailOut{id, student_id, student_name, status, created_at, evidence: list[EvidenceItemOut]}` (reuse `EvidenceItemOut` from `schemas/trajectory.py`).
- `backend/app/presentation/follow_ups/router.py` -- NEW: `router = APIRouter(dependencies=[Depends(get_current_user)])`. `POST /follow-ups` (201) -> `OpenFollowUpService`, `responsible_user_id=uuid.UUID(current_user.id)`; maps `TrajectoryChangeNotFoundError`->404 `trajectory_change_not_found`, `TrajectoryChangeMismatchError`->422 `trajectory_change_mismatch`. `GET /follow-ups/{follow_up_id}` -> `GetFollowUpService`; maps `FollowUpNotFoundError`->404 `follow_up_not_found`.
- `backend/app/composition.py` -- EXTEND: `get_open_follow_up_service`, `get_get_follow_up_service` factories, same `Depends(get_db)` + inline-repository pattern as existing factories (lines ~135-165).
- `backend/app/main.py` -- EXTEND: import + `app.include_router(follow_ups_router)`.
- `backend/tests/test_follow_ups.py` -- NEW: open+fetch happy path, trajectory-change-not-found, student mismatch, freeze-on-evidence guard (recompute after evidence exists keeps old description/detected_at and old sources), follow-up-not-found.
- `frontend/src/api/client.ts` -- EXTEND: `OpenFollowUpRequest`/`FollowUp`/`FollowUpDetail` types from regenerated `schema.d.ts`; `openFollowUp(token, payload)`, `getFollowUp(token, id)` wrappers (mirror existing POST/GET wrapper idioms).
- `frontend/src/components/EvidenceCard.tsx` -- NEW: extract the inline evidence `<section>` (title, description+date, source list) out of `EstudanteTrajetoria.tsx` into a shared component taking `{title, description, detectedAt, evidence, linkTo?, linkLabel?}` — `linkTo` renders the "Ver na trajetória de [aluno]" link, omitted on the Trajectory page itself. `EstudanteTrajetoria.tsx` updated to use it (no `linkTo`), preserving identical markup/behavior.
- `frontend/src/components/FollowUpStatusPill.tsx` -- NEW: renders the 4-state pill per `DESIGN.md`'s `followup-status-pill` tokens (`em-observacao-fill:#EEF3F1`/text secondary, `ativo-fill:#DCEEE7`/`--color-primary`, `aguardando-retorno-fill:#E8E1D2`/text secondary, `encerrado-fill:#E1EEE6`/`--color-success`), `border-radius: var(--radius-full)`, always renders the text label (never color-only).
- `frontend/src/pages/Acompanhamento.tsx` -- NEW: route `/acompanhamentos/:followUpId`. `useParams`, `ignore`-flag fetch (`Home.tsx`/`EstudanteTrajetoria.tsx` pattern), skeleton/error/404 states, `<Header/>`, `<FollowUpStatusPill status=.../>`, `<EvidenceCard .../>` with `linkTo={/estudantes/${student_id}}` and `linkLabel="Ver na trajetória de {student_name}"`.
- `frontend/src/pages/Acompanhamento.test.tsx` -- NEW: Vitest/RTL, mock `GET /api/follow-ups/:id`, cover loaded/loading/error/404 states.
- `frontend/src/App.tsx` -- EXTEND: add `/acompanhamentos/:followUpId` route (same `ProtectedRoute` wrapper pattern).
- `frontend/src/pages/EstudanteTrajetoria.tsx` -- EXTEND: enable "Abrir acompanhamento" when `hasChange`; `onClick` calls `openFollowUp(token, {student_id: studentId, trajectory_change_id: detail.trajectory_change.id})`, disables button + shows inline submitting state while pending, `navigate(/acompanhamentos/${result.id})` on success, inline error message on failure (stays on page). Needs `useNavigate` import and `detail.trajectory_change.id` (now present per schema change above).
- `frontend/src/pages/EstudanteTrajetoria.test.tsx` -- EXTEND: button-enabled-with-change, click->POST->navigate, click-failure-shows-error, button-disabled-in-calm-state (replaces the old "disabled/title" assertions from Story 3.4).

## Tasks & Acceptance

**Execution:**
- [ ] `domain/follow_up.py`, migration `0008`, `infrastructure/db/models.py` -- data model -- RF-12
- [ ] `application/trajectory/ports.py` (`get_by_id`), `application/trajectory/evidence.py` (extraction), `get_student_trajectory_detail.py` (update) -- shared evidence resolution -- UX-DR4 reuse requirement
- [ ] `application/followups/{errors,ports,open_follow_up,get_follow_up}.py` -- application services -- RF-12, RF-20
- [ ] `infrastructure/repositories/sqlalchemy_follow_up_repository.py`, `sqlalchemy_trajectory_change_repository.py` (freeze guard + `get_by_id`) -- persistence + AD-1 deferred guard
- [ ] `presentation/schemas/{trajectory,follow_ups}.py`, `presentation/follow_ups/router.py`, `presentation/trajectory/router.py`, `composition.py`, `main.py` -- wire endpoints -- RF-12, RF-20
- [ ] `backend/tests/test_follow_ups.py` -- I/O Matrix coverage -- RNF-11
- [ ] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- typed wrappers
- [ ] `components/EvidenceCard.tsx`, `components/FollowUpStatusPill.tsx` -- shared UI -- UX-DR4
- [ ] `pages/Acompanhamento.tsx`, `App.tsx` route -- new screen -- RF-20
- [ ] `pages/EstudanteTrajetoria.tsx` -- enable button, wire open+navigate -- RF-12
- [ ] `pages/Acompanhamento.test.tsx`, `pages/EstudanteTrajetoria.test.tsx` -- state coverage

**Acceptance Criteria:**
- Given a trajectory with a detected change, when "Abrir acompanhamento" is clicked, then a `FollowUp`(EM_OBSERVACAO) + `FollowUpEvidence` row are created and the coordenação lands on the Tela de Acompanhamento.
- Given no detected change (calm state), when the trajectory page renders, then "Abrir acompanhamento" stays disabled.
- Given a `FollowUpEvidence` already cites a `TrajectoryChange`, when that period is recomputed, then description/detected_at/sources stay frozen.
- Given the Tela de Acompanhamento for a freshly opened follow-up, when it loads, then it shows the "Em observação" pill and the evidence card with a working "Ver na trajetória de [aluno]" link.
- Given a nonexistent follow-up id, when the screen loads, then it shows a factual message with a link back to Home.

## Implementation Notes

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verification-gap found nothing; intent-alignment found no divergence requiring action (schema.d.ts is gitignored/never committed, same as every prior story; the `save_with_evidence` flush-based atomicity is a documented, deliberate divergence from the single-INSERT pattern, not a bug). 11 blind-hunter findings + 2 edge-case-hunter findings, grouped to 9 entries after dedup.

1. [blind-hunter] `OpenFollowUpService.execute` has no idempotency/uniqueness guard — a double-click, two open tabs, or a client retry after a timeout can insert duplicate `FollowUp`+`FollowUpEvidence` rows for the same `trajectory_change_id`; no unique constraint on `follow_up_evidence(trajectory_change_id)` either. **low** (the one shipped UI entry point already disables the button during submission, so the common single-tab double-click case is already guarded; multi-tab/retry duplication is a real but unlikely-in-everyday-use gap, and a correct fix means choosing upsert-vs-409 semantics not specified anywhere in the spec — more than a direct correction). → **reject** (low; unlikely in everyday use, fix disproportionate).
2. [blind-hunter] `sqlalchemy_trajectory_change_repository.py`'s new `get_by_id(self, change_id)` is missing a type annotation on `change_id`, unlike every other method in the file and the port signatures it implements. **low**, trivial. → **patch**: add `change_id: uuid.UUID`.
3. [blind-hunter] The freeze-on-evidence branch of `upsert` calls `self._session.commit()` after only a `SELECT` (no write occurred in that branch) — harmless (closes the read transaction cleanly) but the lack of a comment could read as "this branch persists something." **low**, trivial. → **patch**: add a one-line comment clarifying the commit only closes the read-only transaction, nothing was written.
4. [blind-hunter] `test_recompute_after_follow_up_evidence_exists_keeps_change_frozen` only asserts the new observation's text doesn't appear in the evidence descriptions — a weaker symptom than the claim "sources are never deleted+reinserted." It would still pass if sources were deleted and reinserted with different content that happened not to mention the new observation. **low** (real test-strength gap, direct fix). → **patch**: query `TrajectoryChangeSourceModel` rows for the change directly and assert the row ids are unchanged before/after recompute.
5. [blind-hunter] + [edge-case-hunter] `GetFollowUpService.execute` silently falls back to `student_name=""` when the `Student` row is missing, with no test and no factual error — inconsistent with the story's "always factual, never silent" convention. Verified false: `FollowUp.student_id` is a real FK to `students.id` with no `ondelete`, Postgres defaults to `NO ACTION`/`RESTRICT`, and no endpoint anywhere in this codebase deletes a `Student` row (confirmed: no delete/cascade code exists for `students` or any fact table) — `student is None` is unreachable given the current, codebase-wide no-deletion invariant, same class already accepted in Story 3.4's own triage log. → **reject** (false; unreachable given existing invariant).
6. [blind-hunter] `GET /follow-ups/{id}` is a new code path that lets any authenticated user read a cited `PedagogicalObservation`'s full text via the evidence list, since Story 4.4's `responsible_user_id` visibility scoping doesn't exist yet. **medium if true** — this is a genuine exposure window, but the frozen Boundaries & Constraints explicitly state "Never filter `PedagogicalObservation` visibility here — Story 4.4 scope; evidence resolution reuses Story 3.4's existing, unfiltered reads as-is" — the intent itself excludes fixing this in this story. → **defer** (out of scope per the frozen intent; real and worth tracking until Story 4.4 lands).
7. [blind-hunter] `POST /follow-ups`'s `FollowUpOut` response omits the evidence list, so `EstudanteTrajetoria.tsx`'s success handler immediately triggers a second `GET /follow-ups/{id}` round trip to render the same case. **low** (real but minor; the fix means adding evidence to the open-response schema, a public-surface change the spec never calls for). → **reject** (low; fix disproportionate, no demonstrated user-facing harm within the 5s budget for one extra trivial GET).
8. [blind-hunter] Neither `Acompanhamento.tsx` nor its test covers an empty `detail.evidence` array (bare `<ul>`, no "sem evidências" fallback). Verified false: `OpenFollowUpService` always creates exactly one `FollowUpEvidence` row per `FollowUp`, and AD-7 guarantees every `TrajectoryChange` has ≥1 `TrajectoryChangeSource` — the evidence list is structurally non-empty for any `FollowUp` this story's own code can create. → **reject** (false; unreachable given this story's own and AD-7's invariants).
9. [blind-hunter] No role/authorization check beyond "any authenticated user" gates `POST /follow-ups`, even though `responsible_user_id` becomes load-bearing for Story 4.4's future visibility scoping. Verified false: this is the identical, already-accepted single-profile authorization model (AD-8: "perfil único mantido... nenhum enum de role novo") applied consistently to every other route in the codebase (observations, attendance, grades, trajectory) — not a gap newly introduced by this diff. → **reject** (false; consistent with established, already-accepted codebase-wide convention).
10. [blind-hunter] The two 401 tests (`test_open_follow_up_without_bearer_token_returns_401`, `test_get_follow_up_without_bearer_token_returns_401`) only assert `"error" in response.json()`, while every other test in the file asserts the full error-envelope body. **low**, trivial. → **patch**: assert the full `{"error": {"code": "...", "message": "..."}}` body (matching whatever `get_current_user`'s existing 401 envelope already returns, unchanged by this story).
11. [edge-case-hunter] `OpenFollowUpService.execute` has a TOCTOU gap between `get_by_id` validation and `save_with_evidence`'s insert — if the referenced `TrajectoryChange`/`Student` row were deleted in between, the insert's FK would raise an unhandled `IntegrityError` (raw 500) instead of a mapped 404. Verified false: no delete endpoint or cascade exists anywhere in this codebase for `Student` or `TrajectoryChange` rows — the same no-deletion invariant as finding 5 — so this race is unreachable today. → **reject** (false; unreachable, no deletion capability exists for either referenced entity).

**Pass 1 totals:** low 4 (patched), low 2 (rejected), false 4 (rejected), defer 1 — 11 entries (after grouping 13 raw findings), 0 high, 0 medium (finding 6 graded medium-if-true but routed to defer per the frozen intent's explicit exclusion).

## Design Notes

`OpenFollowUpRequest` carries a single `trajectory_change_id`, not a list, even though the schema's `FollowUpEvidence` is one-row-per-change: the trajectory page only ever displays one `trajectory_change` at a time, so one click can only ever cite one. The data model already supports multiple `FollowUpEvidence` rows per `FollowUp` for a future story to add more.

`reason`/`next_review_date` are columns with no UI in this story — left `NULL`. No AC or UX doc mentions capturing them at open time; inventing a form field for them would be unscoped UI.

The freeze-guard's `scalar_one_or_none()`-then-reselect branch exists because `RETURNING` only returns rows actually touched by the statement — a `WHERE`-blocked `DO UPDATE` touches nothing, so the existing row's current (frozen) values must be fetched separately rather than assumed to equal the proposed-but-rejected `change` argument.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests + new `test_follow_ups.py` pass
- `cd frontend && npm run generate:api-types && npm test -- --run` -- expected: types regenerate cleanly, all tests + new/updated test files pass
- `cd frontend && npx tsc --noEmit` -- expected: clean
- `git status --short` -- expected: only Code Map files + this spec changed
