---
title: 'Registros pedagógicos sintéticos coerentes com o perfil do estudante (Story 2.5)'
type: 'feature'
created: '2026-10-07'
status: 'in-progress'
route: 'full'
route_source: 'auto'
review: 'none'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
baseline_commit: '3330904cca8960b7ab399e0978e2e062c84409cf'
context:
  - '{project-root}/docs/epic-2-context.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The generator (Stories 2.1/2.2/2.4) produces attendance, grades and assignment facts per `SyntheticProfile`, but no `PedagogicalObservation` rows — the free-text signal RF-11's convergence rule and Epic 3's evidence cards also read from is entirely absent from the synthetic base.

**Approach:** One new pure module, `backend/app/synthetic/observations.py`, holding a fixed set of deterministic Portuguese sentence templates per profile/trend-stage (never open-ended generation), selected by `(seed, student_id, period)` the same way `profiles.py` selects grades/attendance. One observation per `(student, academic period)` is generated and persisted through `PedagogicalObservationModel` — the exact Epic 1 table, no parallel schema. `author_user_id` resolves to the single `COORDENACAO_PEDAGOGICA` user seeded by `seed_dev_user.py` (D6), looked up by its configured email in `generate.py`.

## Boundaries & Constraints

**Always:** every exported template set is a plain tuple of literal strings, never an f-string that embeds a fabricated statistic (no invented absence counts, no numeric judgments); template selection for a given `(seed, student_id, period)` is reproducible via `app.synthetic.rng.derived_key`, exactly like `profiles.py`; `STABLE` only ever selects from routine/no-trend templates; `FALLING_ATTENDANCE` only from attendance-decline templates; `FALLING_GRADES` only from performance-decline templates; `COMBINED_DETERIORATION` composes one attendance-decline sentence with one assignment-decline sentence (mirrors `EXPERIENCE.md`'s own Do example: "queda de frequência e aumento de atividades pendentes"); decline templates intensify by trend stage (`early`/`mid`/`late`, computed from `period_index/total_periods` exactly like `profiles.py::_progress`) but stay descriptive ("frequência reduzida neste período"), never a judgment label, diagnosis or prediction (`EXPERIENCE.md` Voice and Tone: no "aluno de risco", no "alerta", no percentage/probability language); `author_user_id` is resolved once per generation run from the `UserModel` row whose `email` equals `get_settings().dev_seed_email` (normalized `.strip().lower()`, matching `seed_dev_user.py`'s own normalization); `created_at` is `datetime.combine(period.end_date, time(12, 0), tzinfo=UTC)` — deterministic, never wall-clock; `population_fingerprint` is extended (not rewritten) to hash `pedagogical_observations` by `id|student_id|text|created_at`, explicitly excluding `author_user_id` (same precedent as excluding `period_id` for grades/assignments: a real DB-assigned id from a different seeding event, not derived from the generator's seed — including it would break cross-machine determinism of the hash even though the FK itself is correct in the DB).

**Never:** any judgment-label vocabulary ("risco", "evasão", "abandono", "alerta", percentages) inside a template string; a template that fabricates a specific number not cross-checked against the actual generated fact (no "faltou 7 vezes"); a second table or JSON blob for synthetic observation text — `PedagogicalObservationModel` only; changes to `backend/app/domain/pedagogical_observation.py`, `backend/app/application/observations/**`, `backend/app/presentation/observations/**` (Epic 1's write path for human-entered observations stays untouched — the generator writes `PedagogicalObservationModel` rows directly via the ORM, the same pattern `generate.py` already uses for attendance/grades/assignments, bypassing `RegisterObservationService` which enforces an HTTP-era enrollment check the generator's own population construction already guarantees); any file under `backend/app/synthetic/population.py`, `backend/app/synthetic/profiles.py`, `backend/app/synthetic/calibration.py`, `backend/app/synthetic/names.py`, dataset-split logic, or any `docs/spec-2-3-*` file (Story 2.3's disjoint concurrent branch); modifying `docs/sprint-status.yaml` (orchestrating session owns it exclusively); touching `backend/app/synthetic/__init__.py`'s byte-emptiness.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `run_generation`, `STABLE` student | clean DB, academic periods seeded, coordination user seeded | one `PedagogicalObservationModel` per `(student, period)`, text drawn only from routine templates | No error |
| `run_generation`, `FALLING_ATTENDANCE`/`COMBINED_DETERIORATION` student, late period | same | text drawn from the `late`-stage decline template set for that profile | No error |
| No `UserModel` row with `email == dev_seed_email` | clean DB, periods seeded, no coordination user | generation fails before any row is written | Raises a dedicated `MissingAuthorUserError` (same shape as `MissingAcademicPeriodsError`), CLI exits 1 with a message pointing at `seed_dev_user.py` |
| `--reset` re-run, same seed | DB already populated with a prior generation | `pedagogical_observations` rows for the old run are deleted (already covered by `generate.py::reset_generated_data`) and regenerated identically | No error; fingerprint unchanged |
| Two generations, same seed, different coordination-user DB id (hypothetical cross-machine case) | — | `population_fingerprint` output is identical (author_user_id excluded from the hash) | No error |

</frozen-after-approval>

## Code Map

- `backend/app/synthetic/observations.py` -- NEW. `GeneratedObservation` frozen dataclass (`id, student_id, author_user_id, text, created_at`); template tuples per profile/stage; `_stage(progress) -> Literal["early","mid","late"]` mirroring `profiles.py::_progress`; `build_observations(population, periods, author_user_id, seed) -> tuple[GeneratedObservation, ...]`, one per `(student, period)`, selecting templates via `derived_key(seed, "observation", str(student_id), period.id_label, <sub-label>)`. Zero SQLAlchemy/datetime-now imports (AD-2 spirit, `facts.py`/`profiles.py` precedent).
- `backend/app/synthetic/generate.py` -- `run_generation`: after `facts.build_facts`, resolve `author_user_id` (new `_resolve_author_user_id(session) -> uuid.UUID`, raises `MissingAuthorUserError` if no match — uses `get_settings()` + `UserModel` query, the only place in this story that imports settings/queries `UserModel`), call `observations.build_observations`, insert `PedagogicalObservationModel` rows (same `session.add`/`session.flush()` pattern as the other fact loops). Bump `GENERATOR_VERSION` to `"2.5.0"`. `reset_generated_data` already deletes `PedagogicalObservationModel` (Story 2.1 anticipated this) -- no change needed there.
- `backend/app/synthetic/fingerprint.py` -- `population_fingerprint`: append a `pedagogical_observations` block (import `PedagogicalObservationModel`, `ORDER BY id`, hash `id|student_id|text|created_at`, author_user_id deliberately excluded per Boundaries & Constraints).
- `backend/app/infrastructure/db/models.py` -- `PedagogicalObservationModel` (read-only reference, no changes): confirms `id, student_id, author_user_id, text, created_at` is the exact shape to populate.
- `backend/app/infrastructure/db/seed_dev_user.py` -- read-only reference: confirms the email-normalization convention (`.strip().lower()`) this story's author-lookup must match.
- `backend/app/domain/student.py` -- `SyntheticProfile` enum (read-only), reused for template dispatch.
- `backend/tests/test_synthetic_observations.py` -- NEW. Pure-template tests (determinism, profile-vocabulary isolation, no judgment-label regex) + DB-wiring tests (`run_generation` produces the right row count/text/author, `MissingAuthorUserError` path, fingerprint excludes `author_user_id`, fingerprint stability under same-seed re-run).
- `backend/tests/test_synthetic_generation.py`, `backend/tests/test_synthetic_facts_generation.py` -- **minimal addition only** (see Spec Change Log): add a local `_seed_coordination_user(db_session)` helper to each file (same shape as `_seed_academic_periods`/`_seed_periods`) and call it next to the existing periods-seeding call in every test that invokes `run_generation` — `run_generation` now has a new precondition (a resolvable `author_user_id`) that these pre-existing tests must satisfy. No other change to either file; no new fixture, no renamed test, no changed assertion.
- `backend/tests/conftest.py` -- **do not touch**; every file needing the coordination user defines its own local helper (this story's new file, plus the minimal addition above), mirroring the existing `_seed_academic_periods` convention instead of a shared autouse fixture.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/synthetic/observations.py` -- create templates + `build_observations` -- the entire template/selection deliverable (AC 1, AC 2)
- [ ] `backend/app/synthetic/generate.py` -- wire `_resolve_author_user_id`, `MissingAuthorUserError`, call `build_observations`, insert rows, bump `GENERATOR_VERSION` -- persists through the same `PedagogicalObservationModel` Epic 1 already defined (AC 3)
- [ ] `backend/app/synthetic/fingerprint.py` -- extend with the `pedagogical_observations` block -- keeps RNF-13's determinism proof covering every generated table
- [ ] `backend/tests/test_synthetic_observations.py` -- full coverage per I/O Matrix + tone checks -- proves AC 1, 2, 3, 4

**Acceptance Criteria:**
- Given a student with profile `FALLING_ATTENDANCE` or `COMBINED_DETERIORATION`, when synthetic observations are generated, then the text comes from that profile's deterministic decline template set, never from `STABLE`'s routine set.
- Given a student with profile `STABLE`, when synthetic observations are generated, then the text comes only from the routine template set — no decline vocabulary appears.
- Given the generated observations, when persisted, then each row is a `PedagogicalObservationModel` with `student_id, author_user_id, text, created_at` populated and `author_user_id` equal to the seeded coordination user's id — no parallel table.
- Given any generated observation text, when scanned for judgment-label vocabulary (`risco`, `evasão`, `abandono`, `alerta`, `%`, "chance de"), then none is found (`EXPERIENCE.md` Voice and Tone).

## Implementation Notes

## Spec Change Log

- **Finding:** the first implementation pass correctly made `run_generation` raise `MissingAuthorUserError` when no coordination user exists (frozen AC/I-O-matrix requirement), but this is a new precondition on `run_generation` that 18 pre-existing tests in `test_synthetic_generation.py`/`test_synthetic_facts_generation.py` (Stories 2.1/2.2's test surface) never satisfied, since they predate this story. **Amended:** the Code Map's blanket "do not touch" for those two files is narrowed to permit exactly one mechanical addition — a local `_seed_coordination_user` helper, called alongside each file's existing periods-seeding helper in every test that calls `run_generation`. **Avoids:** either silently weakening the frozen `MissingAuthorUserError` behavior (which would violate AC 3/the I/O matrix) or leaving 18 pre-existing tests broken. **Keep:** everything else about those two files — assertions, fixtures, test names, coverage — must survive unchanged; this is a setup-only addition, not a rewrite.

## Review Triage Log

## Design Notes

**Why one observation per `(student, period)`, not a fixed count per student.** Mirrors `facts.py`'s grade/assignment granularity exactly, so a deteriorating student's observation text visibly tracks the same period-indexed trend their numeric facts already show (`_stage` uses the identical `index/(total-1)` convergence as `profiles.py::_progress`), giving Epic 3 a genuinely independent but correlated signal rather than a one-shot label.

**Why `COMBINED_DETERIORATION` composes two sentences instead of three.** `profiles.py` degrades attendance, grades, and assignments together for this profile, but `EXPERIENCE.md`'s own worked example pairs exactly two signals ("queda de frequência e aumento de atividades pendentes"). Grades are already a first-class numeric fact column; restating a grade drop in prose risks drifting into evaluative language ("notas ruins"), so the template only narrates the two behavioral signals (attendance, assignments) that read naturally as observed conduct.

**Why `author_user_id` is excluded from the fingerprint but still a real FK.** Same precedent `fingerprint.py` already set for `period_id` (a real, DB-assigned `uuid.uuid4()` from a different seeding script, not derived from `config.seed`). The row must still carry the correct FK for the application to read; only the *hash* ignores it, so the determinism claim ("byte-identical base on any machine") isn't accidentally scoped to "any machine that happens to seed its coordination user in the same order."

## Assumptions

Recorded because this story ran non-interactively, with no human available at the workflow checkpoints (same convention as Story 2.4's spec):

1. **Checkpoint 1 (spec approval) auto-approved.** No human was available; the spec was self-reviewed against the READY FOR DEVELOPMENT standard instead. Open Questions was empty at that point.
2. **Token budget (~1850 estimated) exceeds the 1600 soft target.** The scope is one cohesive goal (templates + wiring + fingerprint extension for one new fact type) that does not decompose into independently shippable pieces; kept as a single spec rather than split.
3. **Review route pinned to `none`.** `epic-2-plan.md` §Ciclo por story runs `bmad-code-review` and an independent walkthrough as separate steps after the PR; an in-workflow review pass would duplicate them. The orchestrating task additionally requires this story to also run `bmad-code-review` as its own explicit gate after Build's own review.
4. **`docs/sprint-status.yaml` not updated**, even though the workflow would normally write status there — the orchestrating session owns that file exclusively.
5. **`docs/epic-2-context.md` reused as-is** rather than recompiled — it is still valid for Epic 2 (verified: starts with the correct header, content matches the current `docs/epics.md` Story 2.5 section).

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all pre-existing tests still pass plus the new observation tests, zero failures
- `cd backend && ./.venv/Scripts/python.exe -c "import app.synthetic.observations"` -- expected: exits 0, no DB/network needed (pure module)
- `git status --short` -- expected: only `backend/app/synthetic/{observations,generate,fingerprint}.py`, `backend/tests/test_synthetic_observations.py` and this spec changed
