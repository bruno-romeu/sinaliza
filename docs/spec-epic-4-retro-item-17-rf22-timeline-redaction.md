---
title: 'RF-22: redact restricted observation text in the trajectory-detail timeline'
type: 'bugfix'
created: '2026-10-15'
status: 'done'
baseline_commit: '2b480282dce0b300fa6b41c9ee4deedbbe80dded'
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

**Problem:** `GetStudentTrajectoryDetailService._recent_observations` (`backend/app/application/trajectory/get_student_trajectory_detail.py:255-265`) returns `PedagogicalObservation.text` unredacted for the page's timeline section, even when the same observation — cited as evidence of a real `FollowUp` — is correctly redacted for a non-responsible user in that follow-up's evidence card (`resolve_evidence` → `get_by_ids(ids, requesting_user_id)`). RF-22/AD-8 (Story 4.4) only threaded `requesting_user_id` through the evidence path, not the timeline path, so a non-responsible user can read the exact text the evidence card hides for them. Confirmed live with two real users.

**Approach:** Make `_recent_observations` apply the same redaction `get_by_ids` already does, instead of reading raw text via `list_by_student_in_range`: fetch the candidate observations, pick the most recent `_MAX_OBSERVATIONS` by date, then re-resolve exactly those ids through `pedagogical_observation_repository.get_by_ids(ids, requesting_user_id)` (the one place AD-11's restricted/visible logic lives) before building `ObservationItem`s. No repository or port changes — `get_by_ids` already takes `requesting_user_id` and already implements the correct rule.

</frozen-after-approval>

## Implementation Notes

Oneshot: single call-site fix reusing existing, already-tested redaction logic (`SqlAlchemyPedagogicalObservationRepository.get_by_ids`) — no new DB query shape, no port changes. `_recent_observations` must preserve its current ordering (desc by `created_at`) and the `_MAX_OBSERVATIONS` cap; `get_by_ids` doesn't guarantee return order, so re-sort after redaction.

## Review Triage Log

- Quick-lens pass (1 lens run): no findings. Reviewer confirmed the call-site fix correctly reuses `get_by_ids`'s existing AD-8/AD-11 redaction logic, preserves desc-by-date ordering and the `_MAX_OBSERVATIONS` cap by re-sorting from `most_recent` rather than trusting `get_by_ids`'s return order, and that both HTTP call sites already supply `requesting_user_id`. Full suite run: 353 passed, 4 pre-existing failures in `tests/test_synthetic_dataset_split.py` unrelated to this diff (confirmed via `git stash` isolation before this spec's changes) — logged in `docs/deferred-work.md`.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_trajectory.py -q` -- expected: a new test asserting a non-responsible `requesting_user_id` sees `_RESTRICTED_TEXT` in the timeline `observations` for an observation cited as evidence of someone else's `FollowUp`, and the responsible user still sees real text, passes alongside existing tests.
- `cd backend && uv run pytest -q` -- expected: full suite green, no regression to Story 3.4/4.4 evidence-card behavior.

**Manual checks (if no CLI):**
- Re-run the two-user live repro from the Epic 4 retro against `GET /students/{id}/trajectory/detail`: a non-responsible user's timeline must now show `_RESTRICTED_TEXT` for the previously-leaked observation, matching what the evidence card already shows.
