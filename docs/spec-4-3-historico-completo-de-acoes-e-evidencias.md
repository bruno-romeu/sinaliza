---
title: 'Histórico completo de ações e evidências de um acompanhamento'
type: 'feature'
created: '2026-10-14'
status: 'done'
baseline_commit: 'af493daa8ce45df153d9e6d612fe8f158f75f367'
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

**Problem:** Story 4.2's Tela de Acompanhamento shows only the status pill, one merged evidence list, and a write-only action form — it never reads back the `FollowUpAction` rows already persisted, never shows which `TrajectoryChange` each evidence item came from, and never gives keyboard users a way to expand/collapse that history (RF-14/RF-20 undelivered).

**Approach:** Extend `GET /follow-ups/{id}` to return every `FollowUpAction` in chronological order and every linked `TrajectoryChange` (with its own evidence) grouped and ordered by `detected_at`. Render both as keyboard-operable collapsible sections on the Tela de Acompanhamento, reusing the `aria-expanded`/`aria-controls` button pattern already proven in `EstudanteTrajetoria.tsx`'s "Fator preocupante" section.

## Boundaries & Constraints

**Always:**
- `FollowUpActionOut` entries in the response are ordered by `created_at` ascending (then `id` ascending as a deterministic tiebreak) — oldest first, matching "histórico" (RF-14).
- Evidence is grouped per linked `TrajectoryChange`, each group carrying that change's `type`/`description`/`detected_at` plus its own resolved evidence list; groups are ordered by `detected_at` ascending (RF-14, RF-20).
- A `FollowUp` with zero registered actions renders an explicit "Nenhuma ação registrada até o momento." message — never a blank list — satisfying "transparência em vez de validação forçada."
- The actions-history section and each evidence group are collapsible via a `<button aria-expanded aria-controls>` (mirrors `EstudanteTrajetoria.tsx`'s concerning-factor section) — native keyboard operable (Enter/Space), visible focus from the existing global focus-visible styling, no mouse required (RNF-08, UX-DR20). Default open (this screen's whole purpose is reviewing history, unlike the calm-state-adjacent concerning-factor section it mirrors).
- The existing 404 branch (factual message + "Voltar para a Home" link) and loading/error states are unchanged — already satisfy this story's not-found AC (UX-DR18).

**Never:**
- Never change `POST /follow-ups/{id}/actions`, `PATCH /follow-ups/{id}/status`, or their request/response shapes — this story only extends the `GET` read model.
- Never add pagination — history volume per follow-up is small (manually entered actions, at most a handful of linked changes); out of scope.
- Never filter `PedagogicalObservation` text visibility — Story 4.4 scope.
- Never restyle or alter `FollowUpStatusPill`/`StatusSelector`/`ActionForm` beyond what's needed to fit the new sections above/below them.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Multiple actions over time | Follow-up with 3 `FollowUpAction` rows inserted out of `created_at` order | `GET` returns all 3, sorted oldest→newest | No error expected |
| Zero actions | Freshly opened follow-up, no actions registered | `GET` returns `actions: []`; UI shows "Nenhuma ação registrada até o momento." | No error expected |
| Multiple evidence groups | Follow-up with 2 `FollowUpEvidence` rows citing 2 different `TrajectoryChange`s | `GET` returns 2 groups ordered by `detected_at`, each with its own evidence items | No error expected |
| Keyboard-only toggle | Tab to a section's header button, press Enter/Space | Section content expands/collapses, focus stays on the button | No error expected |

</frozen-after-approval>

## Code Map

- `backend/app/application/followups/ports.py` -- EXTEND `FollowUpRepositoryPort`: add `list_actions_by_follow_up(follow_up_id) -> list[FollowUpAction]` (read-only, mirrors `list_evidence_by_follow_up`'s existing shape).
- `backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- EXTEND: implement `list_actions_by_follow_up` (`SELECT ... WHERE follow_up_id = ... ORDER BY created_at ASC, id ASC`); extend `list_evidence_by_follow_up`'s query to `JOIN trajectory_changes` and `ORDER BY trajectory_changes.detected_at ASC, follow_up_evidence.id ASC` (currently unordered).
- `backend/app/application/followups/get_follow_up.py` -- EXTEND: add `TrajectoryChangeEvidenceGroup{trajectory_change: TrajectoryChange, evidence: list[EvidenceItem]}` dataclass; `FollowUpDetailResult` gains `actions: list[FollowUpAction]` and replaces `evidence: list[EvidenceItem]` with `trajectory_changes: list[TrajectoryChangeEvidenceGroup]`. `execute()` calls the new port method for actions; for each `FollowUpEvidence` row, loads the `TrajectoryChange` via `TrajectoryChangeRepositoryPort.get_by_id` (already in `followups/ports.py`, added Story 4.1) and builds one group with its `resolve_evidence(...)` result.
- `backend/app/presentation/schemas/follow_ups.py` -- EXTEND: new `TrajectoryChangeEvidenceGroupOut{trajectory_change: TrajectoryChangeOut, evidence: list[EvidenceItemOut]}` (reuse `TrajectoryChangeOut` from `schemas/trajectory.py`, already has `id`/`type`/`description`/`detected_at`); `FollowUpDetailOut` replaces its `evidence` field with `trajectory_changes: list[TrajectoryChangeEvidenceGroupOut]` and adds `actions: list[FollowUpActionOut]`.
- `backend/app/presentation/follow_ups/router.py` -- EXTEND: `get_follow_up` builds `trajectory_changes` (one `TrajectoryChangeEvidenceGroupOut` per `TrajectoryChangeEvidenceGroup`, mapping the nested `TrajectoryChangeOut`/`EvidenceItemOut`) and `actions` (`FollowUpActionOut` per `FollowUpAction`) instead of the old flat `evidence` list.
- `backend/tests/test_follow_ups.py` -- EXTEND: update the two existing assertions reading `detail["evidence"]` to flatten `detail["trajectory_changes"][*]["evidence"]` instead (same semantics, new shape); add tests for the 4 I/O Matrix rows — multi-action chronological order, zero-actions returns `actions: []`, multi-evidence-group ordering (insert a second `FollowUpEvidence` row directly via `db_session` citing a second seeded `TrajectoryChange`, assert 2 groups ordered by `detected_at`).
- `frontend/src/pages/Acompanhamento.tsx` -- EXTEND: `AcompanhamentoContent` renders an `ActionHistory` section (collapsible, default open, `<ol>` of actions oldest→newest mirroring `EstudanteTrajetoria.tsx`'s observations-timeline `<li>` style, each row showing `description` + formatted `created_at`; empty state text per Boundaries) above `ActionForm`, and one collapsible `EvidenceCard` per `detail.trajectory_changes[*]` group (replaces the single hardcoded `EvidenceCard` call) — each wrapped in the same `aria-expanded`/`aria-controls`/`+`/`−` button pattern as `EstudanteTrajetoria.tsx`'s concerning-factor section, default open, labeled with a local 4-entry `CHANGE_TYPE_LABEL` map (same labels as `EstudanteTrajetoria.tsx`, duplicated locally — no shared module exists for it). `FollowUpDetail['trajectory_changes'][number]` becomes the new type alias used in place of the old flat evidence array.
- `frontend/src/pages/Acompanhamento.test.tsx` -- EXTEND: mock `GET` responses with `actions`/`trajectory_changes` in the new shape across existing tests; add cases for multi-action chronological rendering, zero-actions empty-state text, multi-group evidence rendering, and keyboard toggle (`fireEvent.keyDown`/`.click` on a section header toggles `aria-expanded` and visibility of its content).

## Tasks & Acceptance

**Execution:**
- [x] `application/followups/ports.py` -- add `list_actions_by_follow_up` -- RF-14
- [x] `infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- implement it + order `list_evidence_by_follow_up` -- RF-14
- [x] `application/followups/get_follow_up.py` -- group evidence by `TrajectoryChange`, add actions -- RF-14, RF-20
- [x] `presentation/schemas/follow_ups.py`, `presentation/follow_ups/router.py` -- new response shape -- RF-14, RF-20
- [x] `backend/tests/test_follow_ups.py` -- I/O Matrix coverage + fix pre-existing `evidence`-shape assertions
- [x] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- updated `FollowUpDetail` type (generated, no manual edits beyond regeneration)
- [x] `pages/Acompanhamento.tsx` -- action history list + grouped collapsible evidence cards -- RF-14, RF-20, RNF-08, UX-DR20
- [x] `pages/Acompanhamento.test.tsx` -- state + keyboard coverage

**Acceptance Criteria:**
- Given a follow-up with multiple actions and evidence over time, when the Tela de Acompanhamento loads, then it shows every `FollowUpAction` in chronological order and every linked `TrajectoryChange`'s evidence, grouped and ordered by `detected_at` (RF-14, RF-20).
- Given a follow-up closed with zero actions registered, when the screen loads, then it shows the history section with an explicit "no actions" message rather than blocking or hiding the section.
- Given the Tela de Acompanhamento, when navigated by keyboard, then the action-history and evidence-group sections expand/collapse via Enter/Space on their header buttons, and the status `<select>` remains operable, with visible focus throughout (RNF-08, UX-DR20).
- Given a nonexistent follow-up id, when accessed, then the existing factual message + "Voltar para a Home" link still renders unchanged (UX-DR18).

## Implementation Notes

Implemented by a subagent following this spec directly, then verified and corrected by the orchestrating session.

One correction made after the subagent's initial pass (review finding, see Review Triage Log): wrapping each `EvidenceCard` in a `CollapsibleSection` duplicated the change-type label as a heading twice (once in the collapsible header button, once in `EvidenceCard`'s own `<h2>`). Fixed by passing `title="Evidências"` to the nested `EvidenceCard` instead of repeating `CHANGE_TYPE_LABEL[...]`, and updated the corresponding test assertion (`Acompanhamento.test.tsx`, "renders one evidence section per trajectory-change group") to expect one `CHANGE_TYPE_LABEL` occurrence (collapsible header) plus two "Evidências" occurrences (one per group's card).

A second correction: the keyboard-toggle test was titled "...via keyboard (Enter/Space)..." but only ever called `fireEvent.click`, never a keyboard event — verified empirically (a throwaway test proved `fireEvent.keyDown(button, {key:'Enter'})` does not dispatch a click in this project's jsdom setup, and `@testing-library/user-event` — which does simulate real native button activation — is not a dependency anywhere in this codebase). Since a real `<button type="button">` is genuinely Enter/Space-operable in every actual browser via native UA behavior (not application code), faking that in jsdom via a raw `keyDown` assertion would either do nothing (if left unconverted) or misrepresent what was tested (if the handler were called directly). Fixed by renaming the test to state what it verifies (click + focus retention) and adding a structural assertion that the header is a non-disabled native `<button type="button">` — the actual mechanism RNF-08/UX-DR20's keyboard-operability claim relies on.

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 10 blind-hunter findings + 5 edge-case-hunter findings (JSON) + 1 verification-gap finding + intent-alignment divergences, grouped to 8 entries after dedup.

1. [blind-hunter] + [edge-case-hunter] `GetFollowUpService.execute`'s `if change is None: continue` silently drops a `FollowUpEvidence` row (and its resolved evidence) with no logging/test if the linked `TrajectoryChange` fails to resolve. Verified false: `FollowUpEvidence.trajectory_change_id` is a real `NOT NULL` FK to `trajectory_changes.id`, no `ondelete` cascade exists, and no endpoint anywhere in this codebase deletes a `TrajectoryChange` row — the same codebase-wide no-deletion invariant already accepted in Story 4.1's own triage log (findings 5 and 11, same class: "unreachable given existing invariant"). The verification-gap lens independently reached the same conclusion and declined to file it. → **reject** (false; unreachable given the established no-deletion invariant).
2. [blind-hunter] + [edge-case-hunter] No defense against two `FollowUpEvidence` rows citing the same `trajectory_change_id` (would render as two duplicate collapsible sections). Verified false: `OpenFollowUpService` is the only writer of `FollowUpEvidence` rows anywhere in the codebase, and it always inserts exactly one row per `FollowUp` at creation time — no endpoint exists to attach a second evidence row to an existing `FollowUp`, so duplicate rows citing the same change cannot occur via any product code path today (only the new test's own direct `db_session` insert creates a *second distinct* `TrajectoryChange`, never a duplicate of the same one). → **reject** (false; no code path can produce this state).
3. [blind-hunter] + [edge-case-hunter] A `trajectory_changes` group with an empty `evidence` list (exercised directly by the new backend test `test_get_follow_up_groups_evidence_by_trajectory_change_ordered_by_detected_at`'s `groups[0]["evidence"] == []`) renders as a bare `<ul>` with no message on the frontend, unlike the actions list's explicit empty-state text; same point raised for an entirely empty `trajectory_changes` array. Verified false for both: (a) every `FollowUp` is created with exactly one `FollowUpEvidence` row (`OpenFollowUpService`, Story 4.1, unchanged here), so `trajectory_changes` can never be empty for any follow-up reachable through the product's one creation path; (b) AD-7 guarantees every `TrajectoryChange` created through the real convergence-detection flow has ≥1 `TrajectoryChangeSource` written in the same transaction, so a group's `evidence` list is structurally non-empty for any `TrajectoryChange` created that way — the test's `groups[0]["evidence"] == []` case exists only because the test seeds a bare `TrajectoryChange` row directly via `db_session` with no sources, to isolate the ordering assertion from evidence-resolution complexity, not because production data can reach that state. Same reasoning already accepted in Story 4.1's own triage log (finding 8). → **reject** (false; unreachable in production given `OpenFollowUpService` and AD-7's invariants).
4. [blind-hunter] + [verification-gap] + [intent-alignment] The test titled "toggles a section open/closed via keyboard (Enter/Space) and with a click..." never fires a keyboard event, only `fireEvent.click` — verified by reading the full test body and confirming no `keyDown`/`keyUp`/`userEvent` call exists anywhere in the file. Verification-gap's proposed fix (add `fireEvent.keyDown` assertions) was tried and found not to work as stated: a throwaway test proved `fireEvent.keyDown` does not trigger a click on a bare `<button onClick>` in this project's jsdom setup, and `@testing-library/user-event` (which does simulate real native keyboard-to-click activation) is not a dependency anywhere in this codebase — introducing it would add a new testing dependency, more than a direct test correction. → **patch**: renamed the test to describe what it actually verifies (click + focus retention) and added an assertion that the header is a non-disabled native `<button type="button">` — the structural guarantee that makes Enter/Space work via the browser's own default action, same mechanism (and same absence of a dedicated keyboard-event test) already accepted for `EstudanteTrajetoria.tsx`'s "Fator preocupante" section this pattern was copied from.
5. [blind-hunter] N+1 query pattern: `list_evidence_by_follow_up` already joins `trajectory_changes` to order by `detected_at`, then `GetFollowUpService` issues one more `get_by_id` per group to fetch the same row again (a single batched fetch could avoid the extra round-trips). **low** (every `FollowUp` has exactly one evidence group today, per Story 4.1's `OpenFollowUpService`; even a hypothetical multi-group case stays in the single digits — no demonstrated performance harm at this scale, and batching would add a new repository method the spec never calls for). → **reject** (low; fix disproportionate to any demonstrated harm).
6. [blind-hunter] `CHANGE_TYPE_LABEL` in `Acompanhamento.tsx` has no fallback for an unrecognized `TrajectoryChangeType`, so an added enum value not mirrored into this (intentionally duplicated) map renders `undefined` as a section title. Verified false as a defect newly introduced by this diff: `EstudanteTrajetoria.tsx`'s own `CHANGE_TYPE_LABEL` (the map this one is explicitly duplicated from, per spec Code Map) has the identical no-fallback gap today, unrelated to this story. → **reject** (false; pre-existing, identical pattern in the component this duplicates, not introduced here).
7. [blind-hunter] `composition.py` now constructs two separate `SqlAlchemyTrajectoryChangeRepository(db)` instances for the same session (one per port it satisfies) instead of sharing one. **low**, harmless redundancy, no behavior difference since both wrap the same session. → **reject** (low; no demonstrated harm, fix is a factory-wiring change disproportionate to a cosmetic duplication).
8. [blind-hunter] No test exercises `list_actions_by_follow_up`/`list_evidence_by_follow_up`'s ordering at the repository layer directly (only indirectly via the API), and no test covers the tie-break ordering (`id ASC`) when two groups share the exact same `detected_at`. **low** (the ordering is exercised end-to-end via the API tests that matter to the AC; the exact-tie case is a self-imposed determinism guarantee for an edge unlikely to occur with real convergence-detection timestamps, and adding it tests an implementation detail beyond what the AC requires). → **reject** (low; unlikely in everyday use, API-level coverage already exists).

**Pass 1 totals:** 8 entries (after grouping 17 raw findings across 4 lenses — 10 blind-hunter, 5 edge-case-hunter, 1 verification-gap, plus intent-alignment's descriptive divergences folded into entry 4 and otherwise raising no actionable finding), 0 high, 0 medium, 1 low→patch (entry 4, upgraded from low because multiple lenses converged on the same verified gap and the fix was cheap once correctly scoped), 6 false (entries 1–3, 6–8, two bundling sub-findings), 1 low-rejected (entry 5). 1 patch applied directly (no step-03 subagent re-engagement needed — the fix was a two-line test change), checks re-run and green after the patch (frontend: 8 files / 42 tests pass; `tsc --noEmit` clean).

## Design Notes

`TrajectoryChangeEvidenceGroup` groups by `TrajectoryChange` rather than keeping the Story 4.1 flat `EvidenceItem` list because the AC explicitly asks for "todas as `TrajectoryChange` vinculadas via `FollowUpEvidence`" — a follow-up can in principle cite more than one change (the data model already supports multiple `FollowUpEvidence` rows; no UI creates a second one yet, so tests insert it directly via `db_session` to exercise the grouping/ordering path).

The collapsible pattern is copied inline into `Acompanhamento.tsx` rather than extracted into a shared component: `EstudanteTrajetoria.tsx` only has one such section today, and extracting a shared component for two call sites across two files is a larger, unscoped refactor the intent doesn't ask for.

Default-open (vs. the concerning-factor section's default-closed) reflects that this screen's entire purpose post-4.3 is reviewing history — hiding it by default would contradict "transparência total do processo."

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests incl. extended `test_follow_ups.py` pass (pre-existing `test_synthetic_dataset_split.py` failures unrelated, ignore)
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` -- expected: regenerates `backend/openapi.json` with the new `FollowUpDetailOut` shape
- `cd frontend && npm run generate:api-types && npm test -- --run` -- expected: types regenerate cleanly, all tests incl. updated `Acompanhamento.test.tsx` pass
- `cd frontend && npx tsc --noEmit` -- expected: clean
- `git status --short` -- expected: only Code Map files + this spec + sprint-status.yaml changed
