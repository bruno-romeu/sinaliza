---
title: 'Perfis de trajetória sintética conhecidos aplicados aos fatos (Story 2.2)'
type: 'feature'
created: '2026-10-06'
status: 'done'
route: 'full'
route_source: 'pinned'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_commit: '85e8eb921a6e8e5ab44cee5c9787f3c3e0621397'
context:
  - '{project-root}/docs/epic-2-context.md'
  - '{project-root}/docs/epic-2-plan.md'
  - '{project-root}/docs/data-model.md'
  - '{project-root}/docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 2.1's generator ships every student with `synthetic_profile` NULL, and generates no attendance/grade/assignment facts at all — so Epic 3's change-detection rule (RF-11) has no base with a known outcome to validate against, and Epic 5 has nothing to train or evaluate on.

**Approach:** Add a deterministic profile layer: assign each student one of four documented `SyntheticProfile` values (`STABLE`, `FALLING_ATTENDANCE`, `FALLING_GRADES`, `COMBINED_DETERIORATION`) at generation time per `calibration.SYNTHETIC_PROFILE_PROPORTIONS`, then generate `AttendanceRecord`/`Grade`/`Assignment`/`AssignmentSubmission` rows across the synthetic school year whose rates follow that profile's documented, seed-reproducible evolution rule, consuming `calibration.py`'s named constants (Story 2.4).

## Boundaries & Constraints

**Always:** `SyntheticProfile` gains a fourth member, `FALLING_GRADES`, making its member set exactly equal to `calibration.SYNTHETIC_PROFILE_PROPORTIONS`'s four string keys — asserted by a parity test this story owns; every student's profile and every fact's value/status is derived only from `(seed, student_id, ...)` via `app.synthetic.rng` (never ambient randomness), so the same seed reproduces a byte-identical base; the school calendar for attendance/grades/assignments is built strictly from existing `AcademicPeriod` rows for `config.academic_year` (queried, never created or modified by this generator) — one school day per weekday inside each period's `[start_date, end_date]`, excluding gaps between periods; `STABLE` holds every rate constant across the year; `FALLING_ATTENDANCE` linearly interpolates the daily presence probability from `DAILY_ATTENDANCE_RATE_BASELINE` to `DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR` over the school-day sequence, grades/assignments unaffected; `FALLING_GRADES` shifts the student's grade quantile (the same quantile `STABLE` uses against `GRADE_DISTRIBUTION`) linearly toward 0 over the period sequence, attendance/assignments unaffected; `COMBINED_DETERIORATION` applies the attendance decay, the grade-quantile shift, and a linear interpolation of assignment non-delivery from `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE` to `ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING`, all together, over the same year; every `Grade.value` stays inside `[GRADE_SCALE_MIN, GRADE_SCALE_MAX]`; every `AttendanceRecord` is unique per `(student_id, classroom_id, date)`; new pure modules (`profiles.py`, `facts.py`) have zero I/O and zero SQLAlchemy imports, unit-testable standalone (AD-2's spirit, Story 2.1's precedent); `fingerprint.py`'s declaration is extended, never rewritten, to cover the new fact tables and the now-non-NULL `synthetic_profile`, using each period's `order_index` (never its random `AcademicPeriod.id`) as the hashed proxy so the determinism claim never depends on a UUID a different script generated; `GENERATOR_VERSION` is bumped.

**Never:** any new database entity or migration (D1 — `SyntheticGenerationRun` from Story 2.1 remains the epic's only new entity); any write to `academic_periods` by the generator (owned by `seed_dev_fixtures.py`); any edit to `seed_dev_fixtures.py`, `calibration.py`, or any frontend file; any new calibration constant added to `calibration.py` — a magnitude this story needs that calibration.py does not already provide (the grade-decline mechanism) is expressed as a reusable, documented quantile shift instead, not a new "fact" dressed up as calibrated data; `synthetic_profile` in any Pydantic schema, router, or `backend/openapi.json` (D2/AD-3, already enforced by Story 2.1's test, re-verified here); silently tolerating a database with no `academic_periods` row for `config.academic_year` — the CLI must fail clearly, naming the fix, not generate an incomplete or inconsistent base.

## I/O & Edge-Case Matrix

CLI-invocation matrix (continuing Story 2.1's, no HTTP surface, no UI): each row is a command invocation plus database state → the resulting effect on the database.

| Scenario | Invocation / DB state | Effect on the database | Error handling |
|----------|----------------------|------------------------|----------------|
| Clean DB, periods seeded | `--seed 42` on a DB with `academic_periods` for 2026 already seeded (e.g. via `seed_dev_fixtures.py`), no classrooms/students | Every student gets a non-NULL `synthetic_profile` from the 4-member enum; `attendance_records` (one row per student per school day), `grades` (one per student × period × subject), `assignments` (one per classroom × period × subject), `assignment_submissions` (one per student × assignment in their classroom) are all populated; prints fingerprint; exit 0 | No error |
| No periods seeded | `--seed 42` on a DB with no `academic_periods` row for `config.academic_year` | Nothing written | Exit 1, stderr names `academic_periods`/`config.academic_year` and instructs running the period-seeding script first |
| Same seed twice | `--seed 42` then `--seed 42 --reset`, periods present throughout | Second run's fingerprint (covering facts + profile) is byte-identical to the first's | No error |
| Different seed | `--seed 43 --reset` after `--seed 42`, periods present throughout | Fingerprint differs from seed 42's; per-student profile assignment also differs in aggregate | No error |
| Attendance uniqueness | Any successful run | No two `attendance_records` share `(student_id, classroom_id, date)` | No error (DB `UNIQUE` never triggers) |
| Grade range | Any successful run | Every `grades.value` is within `[0.0, 10.0]` | No error (DB `CHECK` never triggers) |
| `FALLING_ATTENDANCE` student, inspected | A student assigned this profile | Their later-year attendance rate is measurably lower than their early-year rate | No error |
| `COMBINED_DETERIORATION` student, inspected | A student assigned this profile | Attendance, grade quantile, and assignment non-delivery all worsen from first to last period/day | No error |

</frozen-after-approval>

## Code Map

- `backend/app/domain/student.py` -- add `FALLING_GRADES = "FALLING_GRADES"` to `SyntheticProfile` (currently `STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`); do not touch `Student` or `DatasetSplit`.
- `backend/app/synthetic/calibration.py` -- read-only: `SYNTHETIC_PROFILE_PROPORTIONS` (4 string keys), `DAILY_ATTENDANCE_RATE_BASELINE`/`_AT_RISK_FLOOR`, `GRADE_DISTRIBUTION` (`GradeBand` tuple), `GRADE_SCALE_MIN`/`MAX`, `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE`/`_AT_RISK_CEILING`, `ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE`.
- `backend/app/synthetic/rng.py` -- reuse `stable_uuid`/`derived_key` verbatim for every new id and draw; do not modify.
- `backend/app/synthetic/population.py` -- `GeneratedStudent` gains a `synthetic_profile: SyntheticProfile` field, assigned in `build_population` via the new `profiles.assign_profile(seed, student_id)`; `GenerationConfig`/classroom-sizing/split logic untouched.
- `backend/app/synthetic/profiles.py` -- NEW, pure: `assign_profile(seed, student_id) -> SyntheticProfile` (weighted draw against `SYNTHETIC_PROFILE_PROPORTIONS`, keys iterated in sorted order for a stable cumulative boundary); `attendance_is_present(seed, student_id, profile, day_index, total_days) -> bool`; `grade_value(seed, student_id, period_id_label, subject, profile, period_index, total_periods) -> Decimal`; `assignment_submission_status(seed, student_id, assignment_id_label, profile, period_index, total_periods) -> AssignmentSubmissionStatus`.
- `backend/app/synthetic/facts.py` -- NEW, pure: `SUBJECTS` (4-item fixed tuple), `PeriodWindow` frozen dataclass (`id_label: str` built from `order_index`, `start_date`, `end_date`, `order_index`) so this module never imports `AcademicPeriodModel`; `school_days(periods: tuple[PeriodWindow, ...]) -> tuple[date, ...]`; `GeneratedAttendanceRecord`/`GeneratedGrade`/`GeneratedAssignment`/`GeneratedAssignmentSubmission` frozen dataclasses; `build_facts(population: GeneratedPopulation, periods: tuple[PeriodWindow, ...], config: GenerationConfig) -> GeneratedFacts`.
- `backend/app/synthetic/generate.py` -- `run_generation` queries `AcademicPeriodModel` filtered to `config.academic_year`, ordered by `order_index`; raises new `MissingAcademicPeriodsError` (same pattern as `DatabasePopulatedError`) when none exist; converts rows to `facts.PeriodWindow`; calls `facts.build_facts`; inserts the four new row kinds via the existing bulk-insert style; `main()` gains a `except MissingAcademicPeriodsError` branch mirroring the existing one; `GENERATOR_VERSION` -> `"2.2.0"`. `reset_generated_data`/`is_populated` need no change (Story 2.1 already deletes/checks every fact table).
- `backend/app/synthetic/fingerprint.py` -- extend `population_fingerprint` to hash `students.synthetic_profile`, and append `attendance_records`, `grades` (using `period.order_index`, not `period_id`), `assignments` (same), `assignment_submissions`, each `ORDER BY id`.
- `backend/app/infrastructure/db/models.py` -- no change (all four fact models and `synthetic_profile_enum` already exist from Epic 1 / Story 2.1).
- `backend/tests/conftest.py` -- no change; new tests seed their own `AcademicPeriodModel` rows directly, matching the "tests use `db_session` with no pre-seeded fixtures" precedent.
- `backend/tests/test_synthetic_generation.py` -- update `test_first_run_clean_database_creates_expected_rows`'s `assert all(s.synthetic_profile is None ...)` (no longer true) to assert every profile is a valid enum member instead; every other existing test must still pass by seeding `AcademicPeriodModel` rows for `academic_year=2026` before calling `run_generation` (a small local helper, not a `conftest.py` fixture, to keep Story 2.1's "no new fixture needed" scoped to that story).
- `backend/tests/test_synthetic_profiles.py` -- NEW: pure unit tests for `profiles.py`/`facts.py` (no DB) plus the enum/calibration parity test.
- `backend/tests/test_synthetic_facts_generation.py` -- NEW: DB-backed tests covering every matrix row above.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/domain/student.py` -- add `SyntheticProfile.FALLING_GRADES` -- closes the 3-vs-4 mismatch with `calibration.SYNTHETIC_PROFILE_PROPORTIONS`
- [x] `backend/app/synthetic/profiles.py` -- profile assignment + the three evolution-rule functions -- the story's documented, deterministic rules (AC)
- [x] `backend/app/synthetic/facts.py` -- pure fact construction (`PeriodWindow`, `school_days`, `build_facts`) -- AD-2 spirit, unit-testable without a database
- [x] `backend/app/synthetic/population.py` -- `GeneratedStudent.synthetic_profile` + assignment call in `build_population`
- [x] `backend/app/synthetic/generate.py` -- query periods, `MissingAcademicPeriodsError`, call `build_facts`, bulk-insert the four fact kinds, `GENERATOR_VERSION` bump
- [x] `backend/app/synthetic/fingerprint.py` -- extend the hashed declaration (profile + 4 fact tables)
- [x] `backend/tests/test_synthetic_generation.py` -- fix the now-false NULL-profile assertion; seed periods for the other tests
- [x] `backend/tests/test_synthetic_profiles.py` -- parity test + pure rule tests
- [x] `backend/tests/test_synthetic_facts_generation.py` -- every matrix row

**Acceptance Criteria:**
- Given a generated student, when `synthetic_profile` is read, then it is one of the 4 enum members, never NULL and never a 5th value — and `set(SyntheticProfile)` equals `set(calibration.SYNTHETIC_PROFILE_PROPORTIONS.value.keys())` exactly (RNF-13).
- Given a `FALLING_ATTENDANCE` student's generated `attendance_records` ordered by date, when the first quarter of school days is compared to the last quarter, then the presence rate in the last quarter is measurably lower, and regenerating with the same seed reproduces the identical sequence of statuses.
- Given the full profile enum, when inspected, then at least one member changes nothing (`STABLE`) and at least one changes attendance, grade and assignment delivery together (`COMBINED_DETERIORATION`).
- Given any generated base, when `attendance_records`/`grades` are inspected against Epic 1's constraints, then no `UNIQUE(student_id, classroom_id, date)` violation and no `grades.value` outside `[0, 10]` ever occurs — proven by querying the live Postgres after generation, not by code inspection alone.
- Given a database with no `academic_periods` row for `config.academic_year`, when the generator runs, then it writes nothing and exits 1 with a message naming the missing periods.
- Given two generations from the same seed (second with `--reset`, periods untouched between them), when `population_fingerprint` is compared, then the two values are byte-identical, now covering facts and profile, not just classrooms/students/enrollments.

## Implementation Notes

**Migration 0006 amended in place, not a new migration.** `synthetic_profile_enum`'s Postgres `ENUM` literal list in `alembic/versions/0006_create_synthetic_generation_runs_table.py` hardcoded the 3 pre-Story-2.2 member names (`STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`). Adding `SyntheticProfile.FALLING_GRADES` to the domain enum without touching the migration left the two definitions out of sync: `Base.metadata.create_all` (the test-suite schema path) derives the Postgres type from the current domain enum and picks up all 4 members for free, but a real `alembic upgrade head` (the only schema path for a dev/demo database) would still create a 3-member type, and inserting a `FALLING_GRADES` row against it fails with `InvalidTextRepresentation` — caught during this story's own full-suite run via `test_migrations.py`, which drives the actual migration file and left the test database's enum type pinned at 3 values for every test that ran after it in the same session. Fixed by adding `"FALLING_GRADES"` to both `ENUM(...)` declarations in 0006's `upgrade()` (the standalone `synthetic_profile_enum` used for `CREATE TYPE`, and the inline one used for the column's `ADD COLUMN`). This edits the existing migration rather than adding a new one — the spec's "Never: any new database entity or migration" forbids a *new* migration (e.g. an `ALTER TYPE ... ADD VALUE` in a 0007), not a correction to an unreleased one within the same epic; `D1` (`SyntheticGenerationRun` as the epic's only new entity) is unaffected since no entity was added. Round-trip (`upgrade` → `downgrade` → `upgrade`) still passes with the 4-member type.

## Spec Change Log

## Review Triage Log

Lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment. Verdict counts: 2 medium, 3 low, 4 false/rejected (plus 1 informational, non-actionable intent-alignment observation).

1. **medium — patch.** `run_generation` (`backend/app/synthetic/generate.py`) validates `academic_periods` for `config.academic_year` *after* `reset_generated_data(session)` has already run when `reset=True`, so "populated DB + `--reset` + periods missing for the configured year" leaves the session holding uncommitted deletes with no test exercising that combination (blind-hunter + edge-case-hunter, same root cause — the only missing-periods test starts from a clean, unpopulated DB, verified by reading `test_synthetic_facts_generation.py`). Routed: move the period query/`MissingAcademicPeriodsError` check to before the `is_populated`/`reset_generated_data` block, and add a regression test for the combination.
2. **medium — patch.** The real `alembic upgrade head` path has no test asserting the Postgres `synthetic_profile` enum's actual member labels, only its existence (`test_migrations.py`) — so a future migration/domain-enum drift, the exact class of bug this story's own Implementation Notes record finding, would ship silently except for incidental cross-test DB-state ordering (verification-gap, evidence verified by reading `test_migrations.py:74-139` and `conftest.py`'s `create_all`-based schema path). Routed: add an assertion in `test_migration_upgrade_downgrade_upgrade_does_not_raise` comparing the live `pg_enum` labels for `synthetic_profile` to `{m.value for m in SyntheticProfile}`.
3. **low — patch.** `school_days()` (`backend/app/synthetic/facts.py`) does not dedupe/sort its output, so two periods with overlapping date ranges (not produced by any current seeding script, but not guarded against) would emit duplicate attendance dates per student, colliding with the derived id and the DB `UNIQUE(student_id, classroom_id, date)` constraint (edge-case-hunter). Fix is a one-line direct correction (`return tuple(sorted(set(days)))`), so it survives the low-finding rejection filter. Routed: patch.
4. **low — patch.** Nothing guards against two `AcademicPeriod` rows for the same `config.academic_year` sharing an `order_index` — unreachable via any current seeding script, but would silently misattribute grades/assignments to the wrong period or collide derived ids if it ever happened (edge-case-hunter + blind-hunter). Fix is a direct assertion, so it survives the low-finding rejection filter. Routed: patch — assert `order_index` values are unique among `matching_periods` in `generate.py`, raising a clear error.
5. **low — patch.** `_justification_is_justified`'s 50/50 `ABSENT_JUSTIFIED`/`ABSENT_UNJUSTIFIED` split (Assumption 4) has zero test coverage — no test confirms both statuses actually occur (blind-hunter, verified via `grep` across `tests/`). Fix is a direct test addition. Routed: patch — add a pure unit test asserting both statuses appear across many days/students for a non-present outcome.
6. **false.** Blind-hunter: a database that ran `alembic upgrade head` before this story's migration-file fix would keep a stale 3-member `synthetic_profile` type. Verified: no such persisted environment exists in this deployment (`docker ps` shows no `sinaliza-dev-postgres` container at all, only the ephemeral test containers) — same class as spec-2.1's accepted-false finding #8 (speculative risk about an environment that does not currently exist).
7. **false.** Blind-hunter: "no test anywhere asserts `run.generator_version == '2.2.0'`, the bump itself is unverified." Disproven by `backend/tests/test_synthetic_generation.py:92`, `assert run.generator_version == GENERATOR_VERSION` — a dynamic reference to the bumped constant that fails if the assignment in `generate.py` regresses, even without a literal version string in the test.
8. **false.** Edge-case-hunter: a `SYNTHETIC_PROFILE_PROPORTIONS` key with no matching `SyntheticProfile` member would raise an uncaught `ValueError` in `assign_profile`. Verified: no such drift currently exists, and `test_syntheticprofile_enum_matches_calibration_proportion_keys_exactly` (`test_synthetic_profiles.py`) already asserts exact parity, so any future drift fails CI before reaching a runtime crash — same class as spec-2.1's accepted-false finding #9.
9. **rejected (fix is a spec edit only).** Blind-hunter: `_build_grades`/`_build_assignments` stamp every subject in a period with the same `date`/`due_date`, undocumented in Boundaries/Assumptions. No behavioral defect; the only fix is adding a sentence to this spec, which is out of scope for a code-triage patch.
10. **rejected (fix is a spec edit only).** Blind-hunter: the Code Map omits `GeneratedFacts` and the four per-row dataclasses. Documentation completeness only.
11. **rejected (describes expected pre-review state).** Blind-hunter: "Spec Change Log and Review Triage Log are both empty" — true at diff-capture time because this review pass (which fills them) had not run yet.
12. **rejected (low, fix exceeds a direct correction).** Blind-hunter: no DB-backed test checks the full-generation profile mix against calibration proportions at volume — only the pure 8,000-sample unit test does. The reduced-volume DB tests (48 students) are far too small for a reliable statistical check, and enlarging them contradicts the project's own "reduced volume, never full volume in CI" convention; the pure-function statistical test already covers the same code path.
13. **informational, non-actionable.** Intent-alignment auditor noted the Problem paragraph's RF-11/Epic-5 motivation could be read as requiring this story to also prove downstream detectability, not just generate labeled, trending facts. The Approach sentence of the same verbatim intent, and `epic-2-context.md`'s "Cross-Story Dependencies" (Epic 3 "validates its convergence rule against `synthetic_profile` as ground truth" in a later story), already resolve this: the ground truth this story owes is `synthetic_profile` itself, consumed by Epic 3/5 in their own stories. No code or spec change routed.

## Assumptions

Recorded per the orchestrating session's instruction that this is an unattended run with no human available at the workflow's checkpoints. Each entry is a decision that would otherwise have been a question.

1. **Subjects are a fixed 4-item tuple** (`Matemática`, `Português`, `Ciências`, `História`) defined in `facts.py`, not calibrated data — no AC specifies subject names or count; 4 keeps full-volume row counts (~3,200 grades, ~128 assignments, ~3,200 submissions) proportionate to the ~40k attendance rows the epic plan already budgets for.
2. **The grade-deterioration mechanism is a quantile shift, not a new calibration constant.** `calibration.py` has no "at-risk" grade parameter (unlike attendance and assignment-delivery, which both have a baseline+at-risk pair) and this story may not add one (D-equivalent to D1/D2: no new "fact" dressed as calibrated data). Reusing `GRADE_DISTRIBUTION`'s existing band mapping with the input quantile shifted linearly toward 0 (full shift, `shifted = quantile * (1 - progress)`) keeps every grade value traceable to the same already-documented, already-reviewed distribution, rather than inventing a second, unreviewed magnitude.
3. **Progress fraction for grades/assignments is indexed by period, not by calendar day:** `period_index / (total_periods - 1)`, or `1.0` when only one period exists (so a deteriorating profile still shows its worst state rather than silently behaving like `STABLE` under division-by-zero avoidance). Attendance instead uses the finer-grained school-day index, since daily presence is the signal RF-11 needs at day granularity.
4. **Absence justification split is a fresh, undocumented 50/50 coin** (`ABSENT_JUSTIFIED` vs. `ABSENT_UNJUSTIFIED`) on every non-present day, independent of profile — `calibration.py` and `research.md` have no public source for this split either, RF-11 counts both equally (Story 1.2 precedent), and no AC distinguishes them.
5. **Profile assignment is per-student, not per-classroom** (unlike `dataset_split`, which Story 2.1 deliberately balances per classroom) — no AC requires every classroom to contain every profile, and forcing that balance would need inventing a rule the epic never asked for.
6. **`docs/sprint-status.yaml` is not updated by this run** — the orchestrating session owns that file exclusively, per the same convention Stories 2.1 and 2.4 followed.
7. **The spec exceeds the 1600-token SCOPE STANDARD target and is kept whole**, following the Story 2.1/2.4 precedent — one cohesive goal (profile enum + 2 new pure modules + generator/fingerprint extension + tests), no independently shippable sub-deliverable.
8. **Spec-approval checkpoint (step-02 CHECKPOINT 1) is auto-approved** with no human available, status moved straight to `ready-for-dev`, per the orchestrating session's explicit instruction to record every such auto-approval as a numbered Assumption.

## Design Notes

**Why `facts.py` takes a `PeriodWindow`, not an `AcademicPeriodModel` (autonomous decision).** Mirrors Story 2.1's `population.py` boundary: the module that computes deterministic values must have zero SQLAlchemy imports to stay unit-testable without a database. `generate.py` is the only place that touches the ORM, converting queried rows into the plain dataclass before calling into pure code.

**Why `order_index`, not `AcademicPeriod.id`, is hashed into the fingerprint (autonomous decision).** `AcademicPeriodModel.id` defaults to a random `uuid.uuid4()` assigned by `seed_dev_fixtures.py`, not derived from the generator's seed — hashing it directly would make the "byte-identical fingerprint" claim depend on an ID a different, non-deterministic script happened to generate. `order_index` is stable, small, and already the field `data-model.md` treats as the period's identity for ordering purposes.

**Why the weighted profile draw sorts `SYNTHETIC_PROFILE_PROPORTIONS`' keys before building cumulative boundaries (autonomous decision).** `MappingProxyType` preserves insertion order, which is already stable in practice, but sorting makes the boundary assignment legible and independent of `calibration.py`'s internal declaration order, so a future reordering there (unlikely, but no test pins it) cannot silently reshuffle which seed-derived fraction lands in which profile.

## Verification

**Commands:**
- `cd backend && ./.venv/Scripts/python.exe -m pytest` -- expected: the full existing baseline plus the new `test_synthetic_profiles.py`/`test_synthetic_facts_generation.py` tests, all green
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` then search the file -- expected: no `synthetic_profile` anywhere (re-verifying Story 2.1's AC still holds)

**Verified (orchestrating session, after the 5 review patches above were applied):**
- `pytest -q` — 213/213 passing, reproduced on two separate clean runs (container restarted between them to rule out state carried over from an unrelated deadlock seen once during iteration — see below).
- `python -m app.export_openapi` — `openapi.json` contains zero occurrences of `synthetic_profile`.
- `test_populated_db_with_reset_but_periods_missing_writes_nothing` (patch item 1's regression test) initially failed on first write with `ForeignKeyViolation`: its original approach deleted the seeded `academic_periods` rows directly to simulate "periods missing for the configured year," but the prior `run_generation` call in the same test had already inserted `grades`/`assignments` rows referencing those periods, so the delete violated `grades_period_id_fkey` — a test-setup bug, not a `generate.py` defect. Fixed by swapping in a `GenerationConfig` with `academic_year=2099` for the second call instead of mutating the periods table; the test now exercises the same code path (no periods match the requested year) without touching committed rows.
- One `DROP TABLE`/`DeadlockDetected` failure and one subsequent batch of ~17 unrelated failures were observed once while running the full suite repeatedly in a short loop; both were not reproducible after restarting the `sinaliza-test-postgres` container, and every affected test passed in isolation beforehand — concurrent-access artifacts of `test_migrations.py`'s fixture running raw DDL (`DROP TABLE`/`CREATE TYPE`) against a shared container, not a defect introduced by this story. Not investigated further; same class as the epic's existing "check `docker ps` before suspecting code" guidance.

**Manual checks:**
- After a reduced-volume generation in a scratch DB, spot-check one student of each profile's attendance/grade/assignment rows to confirm the documented trend (flat for `STABLE`, declining for the other three along their respective axes).
