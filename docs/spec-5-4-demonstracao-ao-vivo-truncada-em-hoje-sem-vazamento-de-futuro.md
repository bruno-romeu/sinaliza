---
title: 'Demonstração ao vivo truncada em "hoje" sem vazamento de futuro'
type: 'feature'
created: '2026-10-19'
status: 'done'
route: 'full'
route_source: 'auto'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
baseline_commit: '514427c77a70fb775037f3ca02e93d27ab2a8a71'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 5's remaining acceptance criteria for the live demo — `EVAL_DEMO` reads truncated by `as_of()`, `SINALIZA_DEMO_AS_OF` as a documented rehearsal override, and the same `EVAL_DEMO` base serving both Story 5.3's untruncated evaluation and the truncated live demo without separate datasets — already appear to be fully implemented by `as_of()`/`filter_as_of`/`filter_eval_demo_students` (built incrementally across Epics 3–4, specifically anticipating this story per `backend/app/infrastructure/repositories/base.py`'s own docstring). Nothing in the repository, however, proves this end-to-end across the live demo's actual surfaces (Home, Trajectory, Trajectory Detail) in one place, and nothing documents `SINALIZA_DEMO_AS_OF` as the mechanism for rehearsing or running the live demonstration itself.

**Approach:** Add one consolidated end-to-end regression test that seeds an `EVAL_DEMO` student with facts both on/before and strictly after a chosen `as_of()` date, then asserts the live demo's read surfaces (`GET /home`, `GET /students/{id}/trajectory`, `GET /students/{id}/trajectory/changes/{change_id}`) never expose or derive from the after-`as_of()` fact, and that a `TRAIN`-split student is invisible/404 across the same surfaces — proving the cross-epic invariant holds as one named, demo-specific guarantee rather than only as a side effect of per-repository tests. Document `SINALIZA_DEMO_AS_OF` as the rehearsal mechanism for the live demonstration in a short runbook note.

**Decision (human, 2026-10-19):** Scope confirmed as verification + documentation only (Open Questions Option A) — this story closes the loop on already-built Epic 3–4 infrastructure; it does not add a demo-facilitation CLI, a presentation walkthrough, or new UI affordances.

## Boundaries & Constraints

**Always:** The new test drives the real FastAPI app (`TestClient`) through `SINALIZA_DEMO_AS_OF`, exactly like the existing per-repository `as_of()` tests (`backend/tests/test_trajectory.py`, `test_trajectory_detail.py`, `test_follow_ups.py`) — never a new truncation mechanism. Any gap the test uncovers is fixed at the existing single source of truth (`as_of()`/`filter_as_of`/`filter_eval_demo_students` in `backend/app/infrastructure/repositories/base.py` and `backend/app/domain/as_of.py`) — never a new, parallel truncation check bolted onto one endpoint. The runbook note lives alongside existing operational docs (README or `.env.example`), is short, and states plainly that `SINALIZA_DEMO_AS_OF` is a rehearsal/demo mechanism, never a product feature (mirrors `as_of.py`'s own docstring).

**Never:** No new application-layer behavior, endpoint, or schema field. No changes to `app/ml/*` (Story 5.3's evaluation path is explicitly out of scope — it must keep reading the untruncated `EVAL_DEMO` cut). No retroactive truncation of already-persisted `TrajectoryChange` rows. Out of scope: any new "rewind the demo" or data-reset tooling beyond what `SINALIZA_DEMO_AS_OF` already provides.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path, no leak | `EVAL_DEMO` student with a grade/attendance/assignment/observation dated after `SINALIZA_DEMO_AS_OF` | `GET /home` and `GET /students/{id}/trajectory` never reflect the after-`as_of()` fact in indicators, confusion, or evidence | No error expected |
| `TRAIN`-split student | A `TRAIN` student with facts dated before `as_of()` | `GET /students/{id}/trajectory` returns 404; student never appears in `GET /home`'s recent changes or search | 404, same as an unknown id |
| `SINALIZA_DEMO_AS_OF` rewound between two requests | First request with a later `as_of()`, second with an earlier one (rehearsal rewind) | Second request's reads reflect only facts on/before the earlier `as_of()` — no residual leakage from the first request's later window | No error expected |

</frozen-after-approval>

## Code Map

- `backend/app/domain/as_of.py` — `as_of()`, already the single source of truth for "today"; no changes expected, only exercised by the new test.
- `backend/app/infrastructure/repositories/base.py` — `filter_as_of`/`filter_eval_demo_students`, already applied by every live-path repository; the test's job is to prove this holds end-to-end, not to add a new filter.
- `backend/app/infrastructure/repositories/sqlalchemy_{attendance,grade,assignment,assignment_submission,pedagogical_observation}_repository.py` — already call `filter_as_of` on every read; reference only, not expected to change.
- `backend/app/infrastructure/repositories/sqlalchemy_student_repository.py` — already calls `filter_eval_demo_students` on every read; reference only.
- `backend/app/application/trajectory/get_student_trajectory.py:255-275` — `detected_at` is already derived from `as_of_date` (never real wall-clock time), so persisted `TrajectoryChange` rows are themselves always grounded at or before `as_of()`; reference only.
- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` — `list_recent` (Home's only read of `TrajectoryChange`); reference only.
- `backend/app/application/home/get_home.py` — `GetHomeService`, the only entry point for `GET /home`; reference only.
- `backend/tests/test_trajectory.py`, `test_trajectory_detail.py`, `test_trajectory_domain.py`, `test_follow_ups.py` — existing `SINALIZA_DEMO_AS_OF`/`TestClient` test precedent to mirror for the new consolidated test.
- `backend/.env.example:23` — existing `# SINALIZA_DEMO_AS_OF=2026-09-24` comment; candidate location, or README, for the rehearsal-mechanism runbook note.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/tests/test_live_demo_no_future_leakage.py` -- new file: seeds an `EVAL_DEMO` student with facts straddling a chosen `as_of()` date and a `TRAIN` student with facts before it, drives `GET /home` and `GET /students/{id}/trajectory` (+ trajectory-detail/change endpoints already exercised by existing fixtures) via `TestClient` under `SINALIZA_DEMO_AS_OF`, and asserts no after-`as_of()` fact is ever reflected and the `TRAIN` student is invisible/404 throughout -- closes the gap that this invariant is currently proven only per-repository, never as one named, demo-specific end-to-end guarantee
- [ ] `backend/tests/test_live_demo_no_future_leakage.py` -- add the rewind scenario (two sequential requests with a later then earlier `SINALIZA_DEMO_AS_OF`) -- proves a rehearsal rewind never leaks a previously-visible later fact
- [ ] `README.md` or `backend/.env.example` -- add a short note documenting `SINALIZA_DEMO_AS_OF` as the live-demonstration rehearsal mechanism (set it to pin "today" for a rehearsal run; never set in the real deployment) -- closes the doc gap identified in investigation

**Acceptance Criteria:**
- Given an `EVAL_DEMO` student with a fact dated after `SINALIZA_DEMO_AS_OF`, when `GET /home` or `GET /students/{id}/trajectory` is called, then that fact never appears in any indicator, change, or evidence returned.
- Given a `TRAIN`-split student, when any live demo-facing endpoint is called, then the student is never visible (404 or absent from listings), matching the `EVAL_DEMO`-only read contract.
- Given the project's operational docs, when inspected, then `SINALIZA_DEMO_AS_OF` is documented as a rehearsal-only mechanism for the live demonstration, never a product feature.

## Implementation Notes

Investigation confirmed every read-path invariant the acceptance criteria describe was already enforced (`as_of()`, `filter_as_of`, `filter_eval_demo_students`, `TrajectoryChange.detected_at` derived from `as_of_date` not wall-clock time) — with one real gap found and fixed along the way: `SqlAlchemyTrajectoryChangeRepository.list_recent` (Home's only read of `TrajectoryChange`) applied no `as_of()` filter at all. Verified the gap was real before fixing it: `git stash`-ing the fix reproduces a failure in the new rewind test (a change persisted under a later `as_of()` stays visible in `GET /home` after `SINALIZA_DEMO_AS_OF` is rewound to an earlier date) — this is exactly the "vazamento de futuro" this story exists to prevent, not a hypothetical. Fixed by reusing the existing `filter_as_of` helper on `detected_at` (`backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py`), per Boundaries: fix at the single source of truth, no new parallel check.

Files touched:
- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` — `list_recent` now applies `filter_as_of` on `detected_at`.
- `backend/tests/test_live_demo_no_future_leakage.py` — new file, 3 tests: cross-surface no-leak (trajectory + home), the as_of()-rewind regression, and TRAIN-split invisibility across trajectory/home/search.
- `backend/.env.example` — expanded the `SINALIZA_DEMO_AS_OF` comment into the rehearsal-mechanism runbook note (confirmed safe to rewind, since every live read re-applies the current value).

Verified: `cd backend && uv run pytest -q` — 385 passed, 4 failed (pre-existing, unrelated — `docs/deferred-work.md`'s already-logged `test_synthetic_dataset_split.py` `MissingAuthorUserError` gap, reproduced identically on `master` before this change).

Note: this build ran without subagent access, so `bmad-build`'s own step-04 lens review (blind-hunter/edge-case-hunter/verification-gap/intent-alignment) was not run here. A separate `bmad-code-review` pass is still expected before this story is marked `done` in `sprint-status.yaml`, matching Story 5.3's precedent (spec marked `done`, sprint-status held at `review` until that pass ran).

## Spec Change Log

## Review Triage Log

Pass 1 (thorough: blind-hunter, edge-case-hunter, verification-gap, intent-alignment, run against PR #26's diff `514427c..ec82e3e`). Verdict counts: medium=1, low=1, defer=1 (pre-existing, flagged), false=10, out of ~18 findings (after grouping/dedup across lenses).

- [edge-case-hunter, verification-gap, independently corroborated] `filter_as_of` is applied directly to `TrajectoryChangeModel.detected_at` — a `DateTime(timezone=True)` column — without first casting to `Date`, unlike every other timestamp column this pattern touches (`sqlalchemy_pedagogical_observation_repository.py` explicitly does `cast(PedagogicalObservationModel.created_at, SA_Date)` before calling `filter_as_of`; plain-`Date` columns like `AttendanceRecordModel.date`/`GradeModel.date` need no cast). → **medium**: confirmed — Postgres resolves `timestamptz <= date` by casting the date literal to a timestamp at session-timezone midnight, not UTC midnight; the test DB happens to report `TimeZone=UTC` (making this correct today) but the engine (`backend/app/infrastructure/db/base.py`) never pins session timezone explicitly, so a non-UTC server/session default would silently shift the `as_of()` boundary by hours and reintroduce exactly the leak class this story exists to close. Fix is a direct, one-line cast mirroring the existing precedent. Kept, routed to patch.
- [blind-hunter] The new consolidated test only seeds an `AttendanceRecordModel` for the "fact dated after `as_of()`" scenario — grades, assignments, and pedagogical observations (all named in the spec's own I/O matrix and Problem statement) are never exercised by this file, relying entirely on separate per-repository tests to cover those fact types.
- [edge-case-hunter] The test file's own module docstring/the PR's commit message claim the no-future-leakage invariant is proven "across trajectory + home + search," but only `TRAIN`-split invisibility (not future-date leakage) is tested against `/home/search` — overstates what was verified. → merged into the entry above (same root cause: the "consolidated" test's actual coverage is narrower than its own stated claims). **low**: real completeness/claim-accuracy gap, but the underlying per-fact-type truncation is independently verified elsewhere (`test_trajectory.py` et al. already exercise grade/assignment/observation `as_of()` filtering with passing tests) — no demonstrated live bug, just an overclaim in this file's framing. Fix (seed 1-2 more fact types, soften the docstring claim) is direct. Kept, routed to patch.
- [verification-gap] `SqlAlchemyTrajectoryChangeRepository.get_by_id` (the only read behind `GET /follow-ups/{id}` and `POST /follow-ups`) still applies no `as_of()`/`filter_as_of` truncation — the identical "demo rewind leaks a later-dated row" bug class this story just fixed for `list_recent`, one method away in the same file. → **medium** (same class, same file, real risk if a rehearsal rewind opens/reads a follow-up tied to a since-future change), but explicitly pre-existing and out of this story's live-demo-surface scope (follow-ups aren't Home/Trajectory/Trajectory Detail) per spec Boundaries. Not caused by this diff. Deferred — flagged for a dedicated follow-up fix, not silently dropped.
- [blind-hunter, intent-alignment] The spec's own Approach names `GET /students/{id}/trajectory/changes/{change_id}` ("Trajectory Detail") as a surface the new consolidated test must drive; the actual test file never calls it. → **false**: `backend/tests/test_trajectory_detail.py` already has direct, independent `as_of()`/future-window-exclusion coverage for this exact endpoint (lines 498-535) — the underlying guarantee is verified in the codebase, just not inside this one new file. A scope/claim-labeling mismatch in the spec's own Approach wording, not a coverage gap.
- [blind-hunter] `test_train_split_student_invisible_across_trajectory_home_and_search` only asserts the negative case for search (`TRAIN` student absent) — no accompanying test in this file proves an `EVAL_DEMO` student *is* findable via search. → **false**: `backend/tests/test_home.py::test_home_search_matches_student_name` and `test_home_search_excludes_train_split_students` already cover both directions independently.
- [blind-hunter, intent-alignment] The rewind regression (`test_rewinding_as_of_hides_a_previously_detected_change`) only covers `GET /home`, not `GET /students/{id}/trajectory`. → **low**, rejected: `/trajectory` recomputes its response from live fact tables on every request (no persisted intermediate value analogous to a stored `TrajectoryChange` row), so there is no structural mechanism by which a rewind could leave it exposing stale data the way it did for `list_recent` — a trajectory-side rewind test is unlikely to catch a real bug, and writing one is more than a direct correction.
- [blind-hunter] `evaluate.py`-style guard for an off-midnight `detected_at` write path doesn't exist — a future write path setting a real wall-clock timestamp could reintroduce the leak undetected. → **false**: speculative: the only writer (`get_student_trajectory.py`) always combines `as_of_date` with `time.min` at UTC; no current code path can produce an off-midnight value.
- [blind-hunter] Spec's own Tasks &amp; Acceptance checklist left unchecked despite `status: done`. → **false**, out of triage scope (same precedent as Story 5.3's Pass 1: the only fix is editing this build's spec).
- [blind-hunter] `README.md` was never touched despite the Tasks line "`README.md` or `backend/.env.example`". → **false**: the task explicitly offered either location as acceptable; `.env.example` was chosen, satisfying it as written.
- [edge-case-hunter] A malformed `SINALIZA_DEMO_AS_OF` would make `list_recent` raise an uncaught `ValueError`. → **false**: `as_of()` already raises identically at every other call site across the codebase (every repository that calls `filter_as_of`) — not a new risk introduced by this diff.
- [intent-alignment] `GET /home/search` is exercised in the new test even though the verbatim Approach text never names it. → **false**: a reasonable, in-scope choice under the TRAIN-invisibility acceptance criterion's "absent from listings" wording — no harm, not a defect.
- [intent-alignment] A production code change (`list_recent`'s new `filter_as_of` call) occurred under a "verification + documentation only" scope decision. → **false**: explicitly sanctioned by the spec's own Boundaries carve-out ("any gap the test uncovers is fixed at the existing single source of truth") and Design Notes — deliberate, not scope creep.
- [intent-alignment] The `as_of()`-rewind test scenario isn't described in the verbatim Approach paragraph. → **false**: a benign, reasonable elaboration of the stated invariant, already covered by the frozen spec's own human-approved Decision/Boundaries text.
- [blind-hunter] `TrajectoryChangeRepositoryPort.list_recent`'s Protocol signature isn't annotated with the new `as_of()`-truncation contract, unlike the implementation's updated docstring. → **false**: `backend/app/application/home/ports.py` is bare `Protocol` signatures throughout with zero per-method docstrings on any port — matches the file's established convention, not an inconsistency this diff introduced.

**Patch entries dispatched** (2, applied):
1. [x] `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` — cast `TrajectoryChangeModel.detected_at` to `Date` before `filter_as_of`, mirroring `sqlalchemy_pedagogical_observation_repository.py`'s precedent for timestamp columns.
2. [x] `backend/tests/test_live_demo_no_future_leakage.py` — extended `test_trajectory_and_home_never_reflect_facts_after_as_of` with a post-`as_of()` grade (not just attendance), and softened the module docstring's "across trajectory + home + search" claim to reflect that search is only verified for `TRAIN`-invisibility here.

Verified: `cd backend && uv run pytest tests/test_live_demo_no_future_leakage.py tests/test_trajectory.py tests/test_trajectory_detail.py tests/test_home.py tests/test_follow_ups.py -q` — 81 passed. Full suite: 385 passed, 4 failed (pre-existing, unrelated, same baseline as before this review pass).

## Design Notes

This story's investigation found that Epics 3–4 already built every enforcement mechanism this story's acceptance criteria describe (`as_of()`, `filter_as_of`, `filter_eval_demo_students`, and `TrajectoryChange.detected_at` derived from `as_of()` rather than wall-clock time) — `backend/app/infrastructure/repositories/base.py`'s own docstring explicitly anticipated this epic's requirement. The spec therefore scopes this story as closing the verification/documentation gap (one consolidated end-to-end proof + a rehearsal-mechanism note) rather than building new truncation logic from scratch — confirmed by the human decision recorded in the Intent section above.
