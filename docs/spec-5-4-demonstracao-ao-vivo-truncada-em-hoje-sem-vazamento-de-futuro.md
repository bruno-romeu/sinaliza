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

## Design Notes

This story's investigation found that Epics 3–4 already built every enforcement mechanism this story's acceptance criteria describe (`as_of()`, `filter_as_of`, `filter_eval_demo_students`, and `TrajectoryChange.detected_at` derived from `as_of()` rather than wall-clock time) — `backend/app/infrastructure/repositories/base.py`'s own docstring explicitly anticipated this epic's requirement. The spec therefore scopes this story as closing the verification/documentation gap (one consolidated end-to-end proof + a rehearsal-mechanism note) rather than building new truncation logic from scratch — confirmed by the human decision recorded in the Intent section above.
