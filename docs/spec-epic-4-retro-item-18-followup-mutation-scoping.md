---
title: 'Scope FollowUp mutation to responsible_user_id (RF-22 write-side)'
type: 'feature'
created: '2026-10-15'
status: 'done'
baseline_commit: '7305c6d7874766856fbc019a1b118fc0889e813b'
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

**Problem:** Story 4.4 scoped `PedagogicalObservation` *read* visibility to a `FollowUp`'s `responsible_user_id` (RF-22), but `PATCH /follow-ups/{id}/status` and `POST /follow-ups/{id}/actions` apply no such check — any authenticated user can change a `FollowUp`'s status or add an action even though they're blocked from reading its evidence text. Product decided (epic-4-retro-item-18) to close this: writes must respect the same trust boundary as reads.

**Approach:** Both `ChangeFollowUpStatusService.execute` and `RegisterFollowUpActionService.execute` take a `requesting_user_id`, load the `FollowUp` via the existing `follow_up_repository.get_by_id`, and raise a new `FollowUpAccessDeniedError` (→ 403, code `follow_up_access_denied`) when `requesting_user_id != follow_up.responsible_user_id` — checked after the not-found check, so a non-responsible user still gets 404 for a nonexistent follow-up (never leaking existence via a different status code). Both routers pass `current_user.id` as `requesting_user_id`, mirroring `OpenFollowUpService`'s `responsible_user_id` idiom already used for `POST /follow-ups`.

</frozen-after-approval>

## Implementation Notes

Oneshot: mirrors an existing, already-tested pattern (`get_by_id` + ownership compare) across 2 services + 1 new error + 2 router call sites. No port/schema/migration changes — `FollowUpRepositoryPort.get_by_id` already returns `responsible_user_id`.

## Review Triage Log

- Quick-lens pass (1 lens run): no findings. Reviewer confirmed the not-found-before-access-denied ordering in both services, correct 403/`follow_up_access_denied` mapping in both router endpoints, no other call sites left on the old signature, and the new tests assert both the 403 body shape and that no side effect occurred (zero rows / unchanged status). `pytest tests/test_follow_ups.py`: 24/24 passed. Full suite: 355 passed, 4 pre-existing unrelated failures (tracked in `docs/deferred-work.md`).

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_follow_ups.py -q` -- expected: new cases for both endpoints asserting a non-responsible authenticated user gets 403 `follow_up_access_denied` on `PATCH .../status` and `POST .../actions`, while the responsible user's requests still succeed exactly as before; existing tests unaffected.
- `cd backend && uv run pytest -q` -- expected: no regressions (pre-existing unrelated failures in `tests/test_synthetic_dataset_split.py` tracked separately in `docs/deferred-work.md`).

**Manual checks (if no CLI):**
- Re-run the two-user live repro from the Epic 4 retro: a non-responsible user's `PATCH /follow-ups/{id}/status` must now return 403, matching the already-redacted evidence read.
