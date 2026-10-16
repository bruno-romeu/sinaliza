---
title: 'Live-update ActionHistory on new FollowUpAction submission'
type: 'bugfix'
created: '2026-10-15'
status: 'done'
baseline_commit: '406ba55f0b72771417702128c5d9ef91e6c1d7f3'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `ActionForm` (`frontend/src/pages/Acompanhamento.tsx:441-540`) calls `registerFollowUpAction` and shows a "Registro salvo." confirmation, but the new `FollowUpAction` never appears in `ActionHistory` (same file, lines 123-164) above it — `AcompanhamentoContent` never learns a new action was registered, so the user only sees it after a manual page reload. `StatusSelector` already solves the identical problem for status changes via an `onStatusChange` callback threaded up to `AcompanhamentoContent` (lines 296-299, 322-326).

**Approach:** Mirror that exact pattern for actions: `AcompanhamentoContent` passes an `onActionRegistered` callback into `ActionForm`; `ActionForm` calls it with the `FollowUpAction` `registerFollowUpAction` returns, right after the save succeeds; `AcompanhamentoContent` appends it to `detail.actions` (oldest-first order, so append — never prepend, matching `ActionHistory`'s RF-14 chronological contract) via the same `setLoadState` spread pattern `onStatusChange` already uses one level up in the parent component.

</frozen-after-approval>

## Implementation Notes

Oneshot: a single-file frontend change, no new component, no API change — `registerFollowUpAction`'s existing return value (`FollowUpAction`) is the data `onActionRegistered` needs; no new request. `FollowUpAction` (from the actions POST response) and `FollowUpActionItem`/`FollowUpDetail['actions'][number]` (from the GET response) are both generated from the same backend `FollowUpAction` schema — confirm their shapes line up before appending one into the other's array (regenerate `frontend/src/api/schema.d.ts` via `npm run generate:api-types` first if it's stale, per the project's known deferred gap).

## Review Triage Log

- Quick-lens pass (1 lens run): no findings. Reviewer confirmed `FollowUpAction` and `FollowUpActionItem` resolve to the same generated `FollowUpActionOut` schema component (no cast needed), the callback is called before the success-message state update, the new test covers both the action text appearing and the empty-state message disappearing, and append (not prepend) order matches RF-14. `npm run build` (tsc + vite) and `npm test` (45/45) both green.

## Verification

**Commands:**
- `cd frontend && npm run build` -- expected: `tsc` passes with no new type errors from threading `onActionRegistered` through `AcompanhamentoContent`/`ActionForm`.
- `cd frontend && npm test` -- expected: existing suite green; if `Acompanhamento.test.tsx` (or similar) exists, extend it with a case asserting a submitted action appears in `ActionHistory` without a reload — otherwise add a minimal one.

**Manual checks (if no CLI):**
- Open a follow-up's page, submit a new action in "Registrar ação," and confirm it appears at the bottom of "Histórico de ações" immediately, with no page reload.
