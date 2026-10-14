---
title: 'Registro de ações e mudança de status de um acompanhamento'
type: 'feature'
created: '2026-10-14'
status: 'done'
baseline_commit: '65037f0b4e354dcbdebb7124881c3d6beacae7f5'
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

**Problem:** Story 4.1's Tela de Acompanhamento only displays a freshly opened `FollowUp` (status pill + evidence) — there is no way yet to record a `FollowUpAction`, nor to move the case through its 4 closed statuses, so the coordenação cannot conduct the process past the moment of opening.

**Approach:** Add `FollowUpAction` domain+persistence, `POST /follow-ups/{id}/actions` (append a free-text action) and `PATCH /follow-ups/{id}/status` (closed-set transition), both behind new application-service methods — never a router-level field assignment. Extend the Tela de Acompanhamento with an action form (textarea + disabled-while-empty submit, mirrors `Observacoes.tsx`) and a status `<select>` (mirrors `Atividades.tsx`'s status select), with a simple confirm step when the new status is "Encerrado". Back `follow_up_action` with a DB-level `GRANT INSERT, SELECT` / no `UPDATE`/`DELETE` privilege so history append-only-ness doesn't rely only on application code.

## Boundaries & Constraints

**Always:**
- `FollowUpAction{id, follow_up_id, description, author_user_id, created_at}` is always a fresh INSERT — `author_user_id` from `get_current_user`, never a request field; every submitted action joins the history, never replaces a prior one (RF-13, RF-14).
- Status changes go exclusively through a new `ChangeFollowUpStatusService.execute(follow_up_id, status) -> FollowUp` — the router only ever calls this service, never assigns `FollowUpModel.status` directly (AD-6).
- The status selector is a native `<select>` with exactly the 4 closed `FollowUpStatus` values — never free text (RF-13, UX-DR8).
- `follow_up_action` carries `GRANT INSERT, SELECT` / revoked `UPDATE`/`DELETE` for the app's Postgres role, set in the Alembic migration; the same REVOKE is also applied in `tests/conftest.py`'s `engine` fixture right after `Base.metadata.create_all` (tests bypass Alembic entirely per that file's existing docstring, so the privilege must be asserted there too, identical SQL, to stay verifiable and avoid drift) (AD-6).
- Submitting the action form requires non-blank text; the save button stays disabled while the field is empty — same pattern as `Observacoes.tsx`'s `canSave` (UX-DR13). Backend additionally rejects blank/whitespace description with FastAPI's standard 422, same `StringConstraints(strip_whitespace=True, min_length=1)` idiom as `PedagogicalObservationCreateRequest.text`.
- Selecting "Encerrado" in the status select asks for a simple confirmation (`window.confirm`) before calling the API; any other status change calls the API immediately (UX-DR19 — only the destructive/irreversible transition is gated).
- Closing a follow-up with zero recorded actions is allowed — no business-rule block anywhere in this story.

**Never:**
- Never implement the full chronological history view (actions + evidence list) — Story 4.3 scope. This story only needs the action form and the status select to work; it does not need to render previously submitted actions.
- Never restrict which status an existing status can transition to — all 4 values are always selectable regardless of current status (no state-machine adjacency rules specified anywhere).
- Never gate action submission on the follow-up's current status — the AC's "acompanhamento ativo" means "an open case", not literally `status=ACOMPANHAMENTO_ATIVO`; any of the 4 statuses accepts a new action.
- Never filter `PedagogicalObservation` visibility — Story 4.4 scope, unrelated to this story's surface.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Register action | Existing `follow_up_id`; non-blank `description` | 201, `FollowUpAction` persisted, appended (never replaces prior rows) | No error expected |
| Blank action text | `description` empty/whitespace-only | FastAPI 422 (`StringConstraints` validation) | UI already keeps submit disabled; this is the API-level backstop |
| Action on nonexistent follow-up | Unknown `follow_up_id` | 404 `follow_up_not_found` | UI shows inline error |
| Change status | Existing `follow_up_id`; status in the 4 closed values | 200, `FollowUp.status` updated via `ChangeFollowUpStatusService` only | No error expected |
| Status change on nonexistent follow-up | Unknown `follow_up_id` | 404 `follow_up_not_found` | UI shows inline error |
| Close with confirmation declined | User selects "Encerrado", cancels `window.confirm` | No API call made; select reverts to the prior status | No error expected |
| DB-level backstop | Direct `UPDATE`/`DELETE` attempt on `follow_up_action` as the app role | Postgres denies (insufficient privilege) | Verified by test querying `has_table_privilege` |

</frozen-after-approval>

## Code Map

- `backend/app/domain/follow_up.py` -- EXTEND: add frozen dataclass `FollowUpAction{id, follow_up_id, description, author_user_id, created_at}`, mirrors `FollowUpEvidence`'s style.
- `backend/alembic/versions/0009_create_follow_up_action_table.py` -- NEW: `follow_up_action(id, follow_up_id FK follow_ups.id NOT NULL, description Text NOT NULL, author_user_id FK users.id NOT NULL, created_at)`, index on `follow_up_id`. After `op.create_table`, `op.execute("GRANT INSERT, SELECT ON follow_up_action TO CURRENT_USER")` then `op.execute("REVOKE UPDATE, DELETE ON follow_up_action FROM CURRENT_USER")` — `CURRENT_USER` resolves to whatever role runs the migration, which is the same role the app connects as (`settings.database_url`), so this needs no hardcoded role name. `downgrade()` drops the table (privileges go with it).
- `backend/app/infrastructure/db/models.py` -- EXTEND: `FollowUpActionModel(__tablename__="follow_up_action")` mirroring `FollowUpEvidenceModel`'s shape plus `description: Text NOT NULL`, `author_user_id` FK `users.id` NOT NULL indexed, `created_at: DateTime(timezone=True) NOT NULL`.
- `backend/app/application/followups/ports.py` -- EXTEND `FollowUpRepositoryPort`: add `add_action(action: FollowUpAction) -> FollowUpAction` (plain insert+commit) and `update_status(follow_up_id: uuid.UUID, status: FollowUpStatus) -> FollowUp | None` (UPDATE scoped to the `status` column only, returns `None` if the row doesn't exist so the service can raise `FollowUpNotFoundError` without a prior extra read).
- `backend/app/application/followups/register_follow_up_action.py` -- NEW: `RegisterFollowUpActionService.execute(follow_up_id, description, author_user_id) -> FollowUpAction`. Calls `follow_up_repository.get_by_id`; raises `FollowUpNotFoundError` if `None`; builds `FollowUpAction(id=uuid4(), follow_up_id, description, author_user_id, created_at=datetime.now(UTC))`; calls `add_action`.
- `backend/app/application/followups/change_follow_up_status.py` -- NEW: `ChangeFollowUpStatusService.execute(follow_up_id, status: FollowUpStatus) -> FollowUp`. Calls `follow_up_repository.update_status(follow_up_id, status)`; raises `FollowUpNotFoundError` if `None`; returns the updated `FollowUp`. This is the one and only place that ever changes `FollowUp.status` (AD-6) — the router/repository below never do it directly.
- `backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- EXTEND: `add_action` (plain `session.add(FollowUpActionModel(...))` + commit, mirrors `save_with_evidence`'s insert style); `update_status` (`session.get(FollowUpModel, follow_up_id)`, `None` check, set `.status = status`, commit, return mapped `FollowUp` domain object — this single line is the only `FollowUpModel.status =` assignment in the codebase, and it lives in infrastructure, reached only via `ChangeFollowUpStatusService`, never the router).
- `backend/app/presentation/schemas/follow_ups.py` -- EXTEND: `RegisterFollowUpActionRequest{description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]}`; `FollowUpActionOut{id, follow_up_id, description, author_user_id, created_at}`; `ChangeFollowUpStatusRequest{status: _FollowUpStatusLiteral}` (reuses the existing literal alias).
- `backend/app/presentation/follow_ups/router.py` -- EXTEND: `POST /follow-ups/{follow_up_id}/actions` (201) -> `RegisterFollowUpActionService`, `author_user_id=uuid.UUID(current_user.id)`; `PATCH /follow-ups/{follow_up_id}/status` (200) -> `ChangeFollowUpStatusService`; both map `FollowUpNotFoundError` -> 404 `follow_up_not_found` (same envelope as the existing GET).
- `backend/app/composition.py` -- EXTEND: `get_register_follow_up_action_service`, `get_change_follow_up_status_service` factories, same pattern as the two existing follow-up factories (~line 196).
- `backend/tests/conftest.py` -- EXTEND: in the `engine` fixture, right after `Base.metadata.create_all(engine)`, execute `GRANT INSERT, SELECT ON follow_up_action TO CURRENT_USER` then `REVOKE UPDATE, DELETE ON follow_up_action FROM CURRENT_USER` (identical SQL to the migration) so the privilege is verifiable under the test DB, which is built from ORM metadata, not Alembic.
- `backend/tests/test_follow_ups.py` -- EXTEND: register-action happy path (persists, appends, never replaces — insert two actions and assert both rows exist), blank-description 422, action-on-unknown-follow-up 404, change-status happy path (all 4 target values), status-change-on-unknown-follow-up 404, and a DB-privilege test using `SELECT has_table_privilege(current_user, 'follow_up_action', 'UPDATE'/'DELETE'/'INSERT'/'SELECT')`.
- `frontend/src/api/client.ts` -- EXTEND: broaden `RequestOptions.method` to `'GET' | 'POST' | 'PATCH'`; add types `RegisterFollowUpActionRequest`/`FollowUpAction`/`ChangeFollowUpStatusRequest` from regenerated `schema.d.ts`; `registerFollowUpAction(token, followUpId, payload)`, `changeFollowUpStatus(token, followUpId, payload)` wrappers mirroring existing POST/PATCH idioms.
- `frontend/src/pages/Acompanhamento.tsx` -- EXTEND: `AcompanhamentoContent` gains local state for the action textarea (text/saving/message, mirrors `ObservacaoRow` in `Observacoes.tsx`) and the status select (saving/error). Status select: labeled `<select>` with the 4 `FollowUpStatus` options below the existing `FollowUpStatusPill`; `onChange` calls `window.confirm(...)` only when the new value is `ENCERRADO` — cancel reverts the `<select>`'s value, confirm (or any non-`ENCERRADO` value) calls `changeFollowUpStatus` and updates the pill via a callback into the parent's `loadState.detail`. Action form: textarea + "Salvar" button disabled while blank, calls `registerFollowUpAction`, shows "Registro salvo." message on success (mirrors `Observacoes.tsx`'s `handleSave`) — no re-fetch/list rendering of past actions (Story 4.3 scope).
- `frontend/src/pages/Acompanhamento.test.tsx` -- EXTEND: status-select-shows-4-options, select-ENCERRADO-without-confirm-makes-no-request (mock `window.confirm` returning `false`), select-other-status-calls-api-and-updates-pill, action-form-disabled-when-empty, action-form-submit-success-shows-message, action-form-submit-failure-shows-error.

## Tasks & Acceptance

**Execution:**
- [x] `domain/follow_up.py` -- add `FollowUpAction` -- RF-13, RF-14
- [x] `alembic/versions/0009_create_follow_up_action_table.py`, `infrastructure/db/models.py` -- table + GRANT/REVOKE -- AD-6
- [x] `application/followups/ports.py` (`add_action`, `update_status`), `register_follow_up_action.py`, `change_follow_up_status.py` -- application services -- RF-13, AD-6
- [x] `infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- persistence for both new port methods
- [x] `presentation/schemas/follow_ups.py`, `presentation/follow_ups/router.py`, `composition.py` -- wire the two new endpoints -- RF-13
- [x] `tests/conftest.py` -- apply GRANT/REVOKE to the test engine
- [x] `tests/test_follow_ups.py` -- I/O Matrix coverage incl. DB-privilege assertion -- AD-6
- [x] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- typed wrappers, `PATCH` method support
- [x] `pages/Acompanhamento.tsx` -- status select + action form -- RF-13, UX-DR8, UX-DR13, UX-DR19
- [x] `pages/Acompanhamento.test.tsx` -- state coverage

**Acceptance Criteria:**
- Given an open follow-up, when the coordenação submits a non-blank action, then a `FollowUpAction` is persisted with `author_user_id`/`created_at` and a second submission does not replace the first.
- Given the action field empty, when the coordenação looks at the save button, then it is disabled.
- Given the status selector, when opened, then it shows a native `<select>` with exactly the 4 closed states and no free-text alternative.
- Given a status change, when effected, then it only ever happens via `ChangeFollowUpStatusService` — no router code path assigns `FollowUpModel.status` directly.
- Given `follow_up_action`, when its Postgres grants are inspected (test DB), then the app role has `INSERT`/`SELECT` but not `UPDATE`/`DELETE`.
- Given an attempt to close a follow-up (select "Encerrado"), when confirmed, then the status changes; when the confirmation is declined, then no request is made and the select shows the prior status.

## Implementation Notes

Implemented by a subagent following this spec directly, then verified and corrected by the orchestrating session.

One correction made after the subagent's initial pass: the DB-privilege test (`test_follow_up_action_table_privileges_allow_insert_select_deny_update_delete`) originally used `has_table_privilege(current_user, ...)` and `pytest.skip`-ed itself when `current_user` turned out to be a Postgres superuser — the local `sinaliza` role used by `TEST_DATABASE_URL`/`DATABASE_URL` is provisioned as a superuser in this environment (confirmed via `SELECT rolsuper FROM pg_roles`), and superusers bypass every ACL check unconditionally regardless of GRANT/REVOKE, so `has_table_privilege` always reported `True` for UPDATE/DELETE no matter what the migration/`conftest.py` actually granted. A skipped test is uncovered coverage, so the test was rewritten to inspect `pg_class.relacl` directly via `aclexplode()` joined to `pg_roles` — this reflects what was actually recorded in the catalog (exactly what the AC's "quando inspecionada" asks for) and is unaffected by superuser enforcement bypass. Verified manually against a throwaway table that the same GRANT/REVOKE SQL produces `relacl = {sinaliza=arDxt/sinaliza}` (no `w`/`d`) regardless of role superuser status. The test now runs unconditionally (16/16 tests pass in `test_follow_ups.py`, no skips).

A pre-existing, unrelated docstring in `Acompanhamento.tsx` claiming "Status transitions, the action form... are Stories 4.2/4.3/4.5 scope — not implemented here" was updated to reflect this story's additions (`StatusSelector`/`ActionForm`) rather than left stale.

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 10 blind-hunter findings + 3 edge-case-hunter findings + 1 verification-gap finding + intent-alignment divergences, grouped to 9 entries after dedup.

1. [blind-hunter] + [edge-case-hunter] `RegisterFollowUpActionService.execute`'s `get_by_id`-then-`add_action` has a TOCTOU gap: if the `FollowUp` row were deleted between the two calls, the insert's FK would raise an unhandled `IntegrityError` (raw 500) instead of a mapped 404. [edge-case-hunter] also raised the identical class for `update_status`'s `session.get`-then-commit, and for `author_user_id` (from a stateless JWT) no longer existing in `users`. Verified false: confirmed via `grep -rn "@router.delete\|session.delete\|DELETE FROM" app/` that no DELETE endpoint or cascade exists anywhere in this codebase for `FollowUp`, `User`, or any other row — the same no-deletion invariant already accepted as false in Story 4.1's own triage log (finding 11, same class). → **reject** (false; unreachable, no deletion capability exists for any of the referenced entities).
2. [blind-hunter] The privilege test addresses only the Postgres *superuser* ACL-bypass, not a *table-owner* bypass — since the app's role also owns `follow_up_action` (it ran `CREATE TABLE`), the claim was that `REVOKE UPDATE, DELETE` might have no runtime effect for an owner even when non-superuser. Verified false empirically: created a throwaway `NOSUPERUSER` role, had it own a test table, issued the identical `GRANT`/`REVOKE` SQL as a non-superuser owner, then attempted `UPDATE`/`DELETE` as that same role — both failed with `InsufficientPrivilege`. Postgres ACL checks apply to the owner exactly like any other role once an explicit ACL exists; only superuser status (not ownership) bypasses them. → **reject** (false; disproven by direct experiment against this exact Postgres instance).
3. [blind-hunter] `follow_up_action` is `vacuumed`/no `max_length` on `RegisterFollowUpActionRequest.description`. Verified false: `PedagogicalObservationCreateRequest.text` (the explicitly-cited idiom this field mirrors) carries the identical `strip_whitespace=True, min_length=1`-only constraint with no `max_length` either — this is the established codebase convention, not a defect newly introduced here. → **reject** (false; consistent with the existing, already-accepted codebase-wide idiom it explicitly mirrors).
4. [blind-hunter] The diff includes no update to the generated OpenAPI schema/types file backing `paths[...]` lookups in `client.ts`, risking a frontend build failure on the new path keys. Verified false: `backend/openapi.json`/`frontend/src/api/schema.d.ts` are both gitignored and never committed in this codebase (same as every prior story, see Story 4.1's own accepted triage log) — both were regenerated and verified during this story's own Verification run (`python -m app.export_openapi` + `npm run generate:api-types`, `tsc --noEmit` clean). → **reject** (false; gitignored-by-design generated artifacts, verified regenerated and green).
5. [blind-hunter] `sprint-status.yaml`'s mechanical `in-progress` bump "looks mechanical rather than reflecting the actual scope delivered." No named harm identified beyond the observation itself. → **reject** (not a defect — no concrete bad outcome named; this is the workflow's own standard sprint-sync step, explicitly directed by the build workflow).
6. [blind-hunter] No test exercises a same-status (idempotent) `PATCH` at the API/service level. Verified false: `test_change_follow_up_status_happy_path` is parametrized over all 4 `FollowUpStatus` values while the seeded follow-up always starts at `EM_OBSERVACAO` — the `target_status="EM_OBSERVACAO"` case *is* the same-status idempotent update, already asserted to return 200 with the unchanged status. → **reject** (false; already covered by the existing parametrized test).
7. [blind-hunter] No authorization/ownership check gates `PATCH /follow-ups/{id}/status` beyond "any authenticated user," and no actor/timestamp is recorded for a status change (unlike `FollowUpAction`, which always records `author_user_id`). The "any authenticated user" half is verified false: this is the identical, already-accepted single-profile authorization model (AD-8) applied consistently to every other route in this codebase, including the two existing `follow-ups` endpoints (Story 4.1's own triage log, finding 9, same class). The "no status-change actor recorded" half is a real design gap, but the verbatim frozen Intent only ever names `FollowUpAction`-level persistence plus a status-column mutation via a service — no audit-log entity is named anywhere in the intent, the epics.md ACs for Stories 4.2/4.3, or `data-model.md` (which lists exactly `FollowUp`/`FollowUpEvidence`/`FollowUpAction`, nothing else); no other mutable entity in this codebase (grades, attendance, assignments) carries a change-audit trail either, so adding one here would be inventing scope the intent never asked for, not fixing an omission within it. → **reject** (false for the authorization half, consistent with established convention; out-of-scope for the audit-trail half — the intent itself never names a status-change audit entity, consistent with the rest of the codebase).
8. [blind-hunter] The Alembic migration's `GRANT`/`REVOKE ... TO/FROM CURRENT_USER` assumes migrations and the app connect as the same role — a future deployment with a separate migration/admin role would silently grant the real app role nothing. [verification-gap, Other findings] separately noted the backstop's "superuser bypass" caveat would also apply in production if that role is ever a superuser there. Both are real, but speculative against this project's actual deployment model: `alembic/env.py` reads the same `settings.database_url` the app uses (single-role setup, confirmed by code), and no split migration/admin-role convention exists anywhere in this codebase or in Epic 6's hosting docs. → **defer** (real risk if the deployment model ever changes to a split-role setup or a superuser production role; not reachable in this project's current single-role, non-superuser-by-default deployment convention).
9. [verification-gap] + [intent-alignment] `StatusSelector`'s failed-`PATCH` path (`applyStatusChange`'s `catch`/`finally`) has no test — a regression removing the `finally { setSaving(false) }` or the error-message render would not be caught by any of the three existing status-selector tests (options-render, decline-confirm, non-Encerrado-success). [intent-alignment] separately found the "accept the confirm for Encerrado" path itself is untested — the one existing non-Encerrado-success test uses `ACOMPANHAMENTO_ATIVO`, and the decline test never accepts the confirm, so no test ever confirms `window.confirm` returning `true` for "Encerrado" actually fires the `PATCH` with `status: "ENCERRADO"`. Both verified real by reading `Acompanhamento.test.tsx`'s 3 status-selector tests directly. → **patch**: add a test asserting a failed `/status` PATCH shows the inline error and re-enables the `<select>`; add a test asserting accepting `window.confirm` for "Encerrado" fires the PATCH with `{status: "ENCERRADO"}` and updates the pill.
10. [blind-hunter] No test verifies `PATCH /follow-ups/{id}/status` rejects an invalid/unknown status string (e.g. `"FOO"`) with 422, despite `RegisterFollowUpActionRequest`'s blank-description 422 case having explicit coverage. Verified real: `ChangeFollowUpStatusRequest.status`'s `Literal[...]` already rejects invalid values via Pydantic's standard validation (confirmed by inspecting the schema), but no test exercises it. → **patch**: add a test posting an invalid status string and asserting 422.

**Pass 1 totals:** patch 2 (grouped into 1 entry: #9) + 1 (entry #10) = 2 patch entries, defer 1 (entry #8), false 6 (entries #1–#7, two of which bundle sub-findings) — 9 entries total (after grouping 15 raw findings across 4 lenses), 0 high, 0 medium, 0 low kept (all low/false findings resolved to false or out-of-scope on verification), 2 patch, 1 defer.

## Design Notes

`FollowUpStatusPill` stays a pure display component (no `onClick`/interactivity added) because Story 4.5 reuses it, unchanged, as a non-interactive pill on Home's active-follow-ups cards — making the pill itself double as the status trigger would couple a future read-only surface to this story's write affordance. The new `<select>` sits alongside it instead, following the same labeled-`<select>` convention already used for every other closed-set field in this codebase (`Atividades.tsx`'s submission-status select, `Presenca.tsx`, `Notas.tsx`).

`update_status`'s repository method returns `FollowUp | None` (not raising) so `ChangeFollowUpStatusService` owns the one place that decides a missing row means `FollowUpNotFoundError` — the repository stays a dumb persistence boundary, consistent with `get_by_id`'s existing `| None` contract.

The GRANT/REVOKE statement is deliberately duplicated verbatim between the Alembic migration (production path) and `tests/conftest.py` (test path, which builds schema from `Base.metadata.create_all` and never runs Alembic — see that file's own docstring). This is a necessary consequence of the existing test-infrastructure split, not a new pattern; keeping the SQL string identical in both places is the cheapest way to avoid drift.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests incl. extended `test_follow_ups.py` pass
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` -- expected: regenerates `backend/openapi.json` with the two new paths
- `cd frontend && npm run generate:api-types && npm test -- --run` -- expected: types regenerate cleanly, all tests incl. new/updated `Acompanhamento.test.tsx` pass
- `cd frontend && npx tsc --noEmit` -- expected: clean
- `git status --short` -- expected: only Code Map files + this spec changed

**Results (ran 2026-10-14):**
- Backend `pytest -q`: 340 passed, 4 failed, 4 warnings. The 4 failures are all in `tests/test_synthetic_dataset_split.py` (`MissingAuthorUserError: No users row found with email='coordenacao@sinaliza.dev'`) — confirmed pre-existing and unrelated: reproduced identically by stashing every Story 4.2 change and running the same file against `baseline_commit` (4 failed, 4 passed there too). `tests/test_follow_ups.py` alone: 16/16 passed, no skips.
- `python -m app.export_openapi`: wrote `backend/openapi.json` with `/follow-ups/{follow_up_id}/actions` and `/follow-ups/{follow_up_id}/status`.
- `npm run generate:api-types && npm test -- --run`: schema regenerated cleanly; 8 test files / 36 tests passed.
- `npx tsc --noEmit`: clean, no output.
- `git status --short`: only this story's Code Map files + `docs/spec-4-2-...md` + `docs/sprint-status.yaml` (flipped `4-2-...` to `in-progress` per the workflow's sprint sync) changed; `backend/openapi.json`/`frontend/src/api/schema.d.ts` stayed gitignored, same as Story 4.1.
