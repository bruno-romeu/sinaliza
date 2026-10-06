---
title: 'Geração determinística de estudantes, turmas e matrículas (Story 2.1)'
type: 'feature'
created: '2026-09-30'
status: 'done'
route: 'full'
route_source: 'pinned'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_commit: 'c3afd41dc985c33b71f1373869ef493a3937fcaa'
context:
  - '{project-root}/docs/epic-2-context.md'
  - '{project-root}/docs/epic-2-plan.md'
  - '{project-root}/docs/data-model.md'
  - '{project-root}/docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 2's whole point — a reproducible synthetic base of ~200 students — has no foundation yet: `backend/app/synthetic/` does not exist, there is no way to assign `dataset_split` at generation time (AD-4), and no `SyntheticGenerationRun` provenance record, so the determinism claim of RNF-13 is unverifiable. The only data path today is `seed_dev_fixtures.py`'s 16 hand-written test students.

**Approach:** Add `backend/app/synthetic/` with a CLI (`python -m app.synthetic.generate --seed N`) that deterministically builds classrooms, students and enrollments at ~200-student volume, assigns `dataset_split` per student at generation time, persists a `SyntheticGenerationRun` row per execution, and refuses to run against a populated database without an explicit `--reset`. Migration `0006` carries the run table plus a nullable `students.synthetic_profile` native enum column left NULL here (Story 2.2 populates it).

## Boundaries & Constraints

**Always:** determinism comes from explicit derivation, never ambient state — every id is `uuid.uuid5(NAMESPACE, "{seed}|{kind}|{index}")` and every choice comes from a named sub-stream derived with `blake2b(seed|label)`, so adding a new generated concern in Story 2.2 cannot shift Story 2.1's output; `dataset_split` is assigned during generation and persisted (AD-4), never derived at query time; generation writes through SQLAlchemy models and a `Session` (the `seed_dev_fixtures.py` CLI precedent), never a hand-rolled SQL string; the pure population construction (`population.py`) has zero I/O and zero SQLAlchemy imports so it is unit-testable in isolation (AD-2's spirit); every generated name is composed exclusively from the declared fictional vocabularies in `names.py` (RNF-07); `run_generation(session, config, reset)` takes a `Session` parameter so the test suite drives it inside its own rolled-back transaction; the schema change is Alembic-only.

**Never:** any edit to `backend/app/infrastructure/db/seed_dev_fixtures.py` (D3 — it keeps serving the test suite unchanged); any population of `students.synthetic_profile` (Story 2.2 owns it; the column ships NULL); any `backend/app/synthetic/calibration.py` (Story 2.4, concurrent branch); any content in `backend/app/synthetic/__init__.py` — it must be a zero-byte file so the concurrent Story 2.4 branch merges cleanly; any attendance/grade/assignment/observation generation (Story 2.2/2.5); `synthetic_profile` in any Pydantic response schema, router, or `backend/openapi.json` (D2, the AD-3 boundary); any frontend change; any edit to `docs/sprint-status.yaml`; silent appending to a populated database; a `--reset` that deletes `users` or `academic_periods` (they are seeded by their own scripts, not by this generator).

## I/O & Edge-Case Matrix

CLI-invocation matrix (this story has no HTTP surface and no UI), per `docs/epic-2-plan.md`: each row is a command invocation plus database state → the resulting effect on the database.

| Scenario | Invocation / DB state | Effect on the database | Error handling |
|----------|----------------------|------------------------|----------------|
| First run, clean DB | `--seed 42`; no classrooms/students/enrollments/runs | 8 classrooms, 200 students (each with `dataset_split`, `synthetic_profile` NULL), 200 enrollments, 1 `synthetic_generation_runs` row (seed=42, generator_version, executed_at, student_count=200, train_ratio=0.7); prints the content fingerprint; exit 0 | No error |
| Same seed twice | `--seed 42`, then `--seed 42 --reset` | Second run's content fingerprint over classrooms/students/enrollments is byte-identical to the first's; a second `synthetic_generation_runs` row is written | No error |
| Different seed | `--seed 42 --reset` after `--seed 43` | Fingerprint differs from seed 43's | No error |
| Populated DB, no `--reset` | `--seed 42` with rows already present | Nothing written — the database is untouched | Exit 1, stderr: database already populated, name `--reset` explicitly |
| Populated DB, `--reset` | `--seed 42 --reset` | Generated tables + dependent fact tables wiped in FK order, then regenerated; `users` and `academic_periods` untouched | No error |
| Reduced volume | `--seed 7 --students 12 --students-per-classroom 4` on a clean DB | 3 classrooms, 12 students, 12 enrollments; run row records `student_count=12` | No error |
| Invalid argument | `--train-ratio 1.0` (or `--students 0`, `--seed -1`) | Nothing written | Exit 2, argparse error naming the offending flag |

</frozen-after-approval>

## Code Map

- `backend/app/infrastructure/db/models.py` -- add `synthetic_profile_enum` (`SAEnum(..., name="synthetic_profile", native_enum=True, validate_strings=True)`) beside the four existing enums; add nullable `StudentModel.synthetic_profile`; add `SyntheticGenerationRunModel`. Do not touch any other model.
- `backend/alembic/versions/0002_create_attendance_tables.py` -- the create/drop lifecycle to copy verbatim for `0006`'s native enum (`postgresql.ENUM(...)`, `.create(bind, checkfirst=True)`, `create_type=False` at column level, explicit `.drop(bind, checkfirst=True)` in `downgrade`)
- `backend/alembic/versions/0006_create_synthetic_generation_runs_table.py` -- NEW: create `synthetic_profile` enum type, `op.add_column("students", ...nullable=True)`, create `synthetic_generation_runs`; downgrade reverses all three
- `backend/app/domain/student.py` -- add `SyntheticProfile(str, Enum)` (`STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`). Do **not** add the field to the `Student` frozen dataclass (see Design Notes)
- `backend/app/domain/synthetic_generation_run.py` -- NEW: `SyntheticGenerationRun` frozen dataclass, shaped like `domain/grade.py`
- `backend/app/synthetic/__init__.py` -- NEW: **zero bytes**, no docstring, no imports
- `backend/app/synthetic/rng.py` -- NEW: `stable_uuid(seed, *labels)` (uuid5 on a fixed module namespace) and `derived_key(seed, *labels)` (blake2b digest → int), the only two sources of determinism
- `backend/app/synthetic/names.py` -- NEW: `GIVEN_NAMES`, `FIRST_SURNAMES`, `SECOND_SURNAMES` fictional vocabularies + `compose_name(index)` mixed-radix decode; `CLASSROOM_NAME_TEMPLATE`
- `backend/app/synthetic/population.py` -- NEW, pure: `GenerationConfig` (seed, student_count, students_per_classroom, train_ratio, academic_year), `GeneratedClassroom`/`GeneratedStudent`/`GeneratedEnrollment` dataclasses, `build_population(config)`
- `backend/app/synthetic/fingerprint.py` -- NEW: `population_fingerprint(session)` — SHA-256 over the generated tables' contents in a declared, stably-ordered column list; extended (not rewritten) by later stories
- `backend/app/synthetic/generate.py` -- NEW: `GENERATOR_VERSION`, `is_populated(session)`, `reset_generated_data(session)`, `run_generation(session, config, reset)`, argparse `main()`; `python -m app.synthetic.generate`
- `backend/app/infrastructure/db/seed_dev_fixtures.py` -- read-only reference for the CLI/`SessionLocal` precedent; **do not modify**
- `backend/app/export_openapi.py` -- `export_openapi()` / `OUTPUT_PATH`, called by the openapi-absence test
- `backend/tests/test_migrations.py` -- extend `migration_engine`'s drop list (`synthetic_generation_runs`, `DROP TYPE IF EXISTS synthetic_profile`) and add `to_regclass`/`to_regtype` assertions in the same style already used there
- `backend/tests/conftest.py` -- no new fixture needed; the new tests use `db_session` and deliberately request no seeded fixtures
- `backend/tests/test_synthetic_generation.py` -- NEW: covers every matrix row plus the AC list below

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/domain/student.py` -- add `SyntheticProfile` enum -- AD-2 pure domain, values fixed by Story 2.2's AC
- [x] `backend/app/domain/synthetic_generation_run.py` -- `SyntheticGenerationRun` frozen dataclass -- D1's single new entity
- [x] `backend/app/infrastructure/db/models.py` -- new enum object, nullable `students.synthetic_profile`, `SyntheticGenerationRunModel`
- [x] `backend/alembic/versions/0006_create_synthetic_generation_runs_table.py` -- migration carrying both schema changes, reversible
- [x] `backend/app/synthetic/__init__.py` -- create as a zero-byte file
- [x] `backend/app/synthetic/rng.py` -- `stable_uuid`, `derived_key`
- [x] `backend/app/synthetic/names.py` -- fictional vocabularies + deterministic composition
- [x] `backend/app/synthetic/population.py` -- pure `build_population`, split assignment, no I/O
- [x] `backend/app/synthetic/fingerprint.py` -- `population_fingerprint`
- [x] `backend/app/synthetic/generate.py` -- persistence + `--seed`/`--reset` CLI
- [x] `backend/tests/test_synthetic_generation.py` -- every matrix row + AC coverage
- [x] `backend/tests/test_migrations.py` -- extend for the new table, column and enum type

**Acceptance Criteria:**
- Given a clean database, when the generator runs twice with the same seed (the second with `--reset`), then `population_fingerprint` is identical across the two runs — proven by content hash, never by row count (RNF-13).
- Given two different seeds, when each generates into a clean database, then the two fingerprints differ — without this a constant generator would pass the determinism test.
- Given a completed run, when `synthetic_generation_runs` is inspected, then exactly one new row records the invocation's seed, the generator version, an execution timestamp, the student count and the train ratio (RNF-13).
- Given a generated base, when students are inspected, then every student carries a `dataset_split`, both `TRAIN` and `EVAL_DEMO` are present, every classroom contains both, and the global `TRAIN` share matches the run's `train_ratio`; every `synthetic_profile` is NULL (AD-4, Story 2.2 boundary).
- Given a generated base, when every generated text field is scanned, then no value contains a digit, `@`, or any CPF/phone-shaped pattern, and every student name decomposes into the declared fictional vocabularies (RNF-07).
- Given `backend/openapi.json` regenerated from the live app, when searched, then `synthetic_profile` does not appear anywhere in it (D2, AD-3 boundary).
- Given `alembic upgrade head` → `downgrade base` → `upgrade head`, when run against the real test Postgres, then no error is raised and `synthetic_generation_runs`, `students.synthetic_profile` and the `synthetic_profile` type all exist at the end.
- Given the test suite, when it exercises the generator, then it always does so at reduced volume (≤ ~24 students) — the full ~200-student base is never generated in CI; its wall-clock time is measured once and recorded in Implementation Notes.

## Implementation Notes

**Full-volume timing (epic DoD: measured once, never exercised in CI).** `python -m app.synthetic.generate --seed 42 --reset` against the dev Postgres (port 5434, `sinaliza-dev-postgres`) generated 8 classrooms / 200 students / 200 enrollments in **~7.9s** wall clock (`real 0m7.884s`). Re-running the same seed (`--reset`) produced the byte-identical fingerprint `fb67d288c89fda06719350facd6ffaead10986ecf9b01aecf945afdeb85bcd58`.

**`--reset` does not delete `synthetic_generation_runs` (deviation from the Design Notes bullet, resolved in favor of the frozen I/O Matrix).** The Design Notes "`--reset` scope" bullet lists `synthetic_generation_runs` among the tables wiped by `--reset`, but the frozen I/O Matrix's "Same seed twice" row requires "a second `synthetic_generation_runs` row is written" after a same-seed `--reset` re-run, and the Acceptance Criteria describe "exactly one **new** row" per invocation — both only hold if provenance history survives `--reset`. Since the I/O Matrix and AC list live inside `<frozen-after-approval>` (human-owned intent) and the Design Notes bullet is an "autonomous decision" outside it, `reset_generated_data()` in `backend/app/synthetic/generate.py` deletes classrooms/students/enrollments/dependent fact tables only, and leaves `synthetic_generation_runs` untouched — every execution (reset or not) appends its own provenance row, which also better serves RNF-13's audit intent (a reset should not erase the record that a prior generation happened). `is_populated()` still treats any existing `synthetic_generation_runs` row as "populated," so a database with facts already reset but old run rows still present still requires an explicit `--reset` to regenerate.

**Split assignment.** Students are grouped by classroom, ordered within each classroom by `derived_key(seed, "split", student_id)`, and the first `round(n * train_ratio)` in that order become `TRAIN`. Verified at reduced volume (12 students / 3 classrooms / `train_ratio=0.5`): every classroom has both splits, global `TRAIN` share is exactly 0.5.

**Classroom sizing.** `num_classrooms = ceil(student_count / students_per_classroom)`; every classroom but the last gets exactly `students_per_classroom` students, the last absorbs the remainder (Assumption 2) — verified both at 200/25 (8 classrooms of 25) and at the reduced 12/4 (3 classrooms of 4) volumes.

## Spec Change Log

## Review Triage Log

1. **high** — `backend/app/synthetic/population.py:120`: per-classroom `round(size * train_ratio)` uses Python's banker's rounding; at the actual default parameters (200 students, 25/classroom, `train_ratio=0.7`), `round(25*0.7)` evaluates to `round(17.5)` = 18 (confirmed: `25*0.7 == 17.5` exactly in float), giving every classroom 18 TRAIN / 7 EVAL_DEMO and a global ratio of 144/200 = 0.72, not the configured 0.7 — directly violates the frozen AC "the global `TRAIN` share matches the run's `train_ratio`." No test exercises the default parameters (only the 50/50 reduced config, which never lands on a rounding boundary that drifts the sum). Routed: **patch**.
2. **medium** — `backend/app/synthetic/population.py:_classroom_sizes`/`build_population`: a classroom of size 1 (reachable via e.g. `--students 201 --students-per-classroom 25`, whose remainder classroom gets exactly 1 student per Assumption 2) cannot contain both `TRAIN` and `EVAL_DEMO`, violating the frozen AC "every classroom contains both." Verified: `round` of any single-student classroom under either split value is necessarily all-or-nothing. Routed: **patch**.
3. **medium** — `backend/app/synthetic/generate.py:75` (`reset_generated_data`) commits before `build_population`/the subsequent inserts in `run_generation` run; a failure during population construction or insertion (concretely, `--students` > `NAME_CAPACITY`=6480 together with `--reset` on an already-populated DB) leaves the database with the generated tables wiped and neither a replacement base nor a new provenance row. Verified by reading the call order in `run_generation` (`backend/app/synthetic/generate.py:85-100`) and `compose_name`'s range check in `backend/app/synthetic/names.py`. Routed: **patch**.
4. **medium** — the frozen AC "`backend/openapi.json` regenerated ... `synthetic_profile` does not appear anywhere in it" has no automated test; the Code Map's claim that `app/export_openapi.py` is "called by the openapi-absence test" is false — a repo-wide search (`grep -ri openapi backend`) found no such test anywhere. Verified only manually, once, by the implementing subagent. Routed: **patch**.
5. **low** — `backend/app/synthetic/generate.py:173`: `--academic-year` uses plain `type=int` with no lower-bound validator, unlike every other numeric flag (`--seed`, `--students`, `--students-per-classroom`, `--train-ratio`), all of which validate via a dedicated typed function. A zero/negative value is silently accepted and persisted on every classroom. Fix is a trivial direct correction (swap in `_positive_int`), so it survives the low-finding rejection filter. Routed: **patch**.
6. **low, carried to defer** — `backend/app/synthetic/generate.py:178-206` (`main()`): no test drives `main()` end-to-end, so its args→`GenerationConfig` mapping, its `DatabasePopulatedError` → stderr/exit(1) handling, and its success-path summary/exit(0) are unverified by CI; relatedly, `main()` only catches `DatabasePopulatedError`, so any other exception (e.g. a DB connection failure) surfaces as a raw traceback instead of a clean exit code. Verified: no `main(` call or `from app.synthetic.generate import main` anywhere in `backend/tests/`. Not a regression of any documented matrix row (the matrix only specifies behavior for the populated/invalid-argument cases, both of which the existing tests do cover via `run_generation`/`_build_arg_parser` directly) — thin wiring over already-tested internals, and the success/populated-without-reset paths were exercised manually by the implementing subagent. Routed: **defer**.
7. **false** — seed has no upper bound before reaching the `BigInteger` column, so an extremely large `--seed` could raise an uncaught `DataError` at commit. Real in principle but requires an operator to deliberately pass an enormous seed; the fix (an upper-bound guard) is more than a direct correction, so rejected per the low-finding filter.
8. **false** — `GENERATOR_VERSION` bump discipline has no enforcement. No demonstrated current bad outcome (the constant is correct today); speculative risk about a future story's hygiene, not a defect in this diff.
9. **false** — the `synthetic_profile` enum's member list is declared independently in the migration, the ORM `SAEnum`, and the `SyntheticProfile` Python enum, with no test asserting they stay in sync. No demonstrated current drift; speculative risk only.
10. **false** — `population_fingerprint` excludes `students.synthetic_profile` on the assumption it is "always NULL," with no runtime guard asserting that. In this story, `run_generation` always passes `synthetic_profile=None` explicitly, so the assumption holds by code, not just convention — no current defect.
11. **false** — `is_populated()`'s specific "only `users`/`academic_periods` present" scenario (Assumption 5) has no dedicated test, but reading the implementation shows the check is correct (queries exactly `classrooms`/`students`/`enrollments`/`synthetic_generation_runs`, none of which `users`/`academic_periods` would populate) — a coverage gap, not a demonstrated incorrectness.
13. **medium** — (found re-verifying the patch for #2) `_classroom_sizes` only folds a *trailing* size-1 remainder; with `--students-per-classroom 1` every classroom is independently size 1 by construction (e.g. `_classroom_sizes(4, 1)` → `[1, 1, 2]`, still leaving two size-1 classrooms), each incapable of containing both splits. Verified by direct computation across a parameter sweep. Routed: **patch** — reject `students_per_classroom < 2` in `GenerationConfig.__post_init__`, consistent with the existing validation style for `seed`/`student_count`/`train_ratio`.
14. **medium** — (found in the same sweep) the post-patch cumulative-remainder split computation still lets a single small classroom collapse to all-one-split under an extreme `train_ratio` (e.g. `student_count=2, students_per_classroom=2, train_ratio=0.1` → `train_count=0`), violating the frozen "every classroom contains both" AC. Verified by direct computation across seeds/ratios/sizes. Routed: **patch** — clamp each classroom's computed `train_count` into `[1, size-1]` after the cumulative-remainder calculation, so the global-ratio-matching behavior (already verified exact at the default/documented parameters) is preserved for realistic inputs while small/extreme-ratio classrooms can no longer end up single-split.
15. **false** — `compose_classroom_name`'s wrap-around (>23 classrooms) and the `ValueError` guards in `compose_name`/`compose_classroom_name` are untested, but unreachable at any volume this story's defaults or tests use (8 classrooms max) — a guard for state the program is never shown to reach, not a defect.

## Assumptions

Recorded per the orchestrating session's instruction that this is an unattended run with no human available at the workflow's checkpoints. Each entry is a decision that would otherwise have been a question.

1. **`train_ratio` default = 0.7.** Story 2.3 owns the named split-proportion constant; 2.1 needs a value now. 0.7/0.3 over 200 students leaves 60 `EVAL_DEMO` students for the demo and 140 for training. Exposed as `--train-ratio` and persisted per run precisely so a base generated at a different proportion stays identifiable (`data-model.md` §Geração sintética). Story 2.3 may relocate the constant without a data migration.
2. **Volume = 200 students at 25 per classroom → 8 classrooms.** "~200 students distributed across classrooms" (AC) with a plausible Brazilian class size. `--students` / `--students-per-classroom` make it configurable; the last classroom absorbs the remainder when the division is uneven.
3. **`academic_year` = 2026,** matching `seed_dev_fixtures.py`'s `_ACADEMIC_YEAR` and the four seeded bimesters, so a generated base and the existing `academic_periods` rows describe the same school year. Overridable via `--academic-year`.
4. **`GENERATOR_VERSION = "2.1.0"`,** a hand-maintained string bumped by any story that changes what the generator emits. It is what makes an old `synthetic_generation_runs` row interpretable after the generator evolves (RNF-13).
5. **"Already populated" means any row in `classrooms`, `students`, `enrollments` or `synthetic_generation_runs`.** A database holding only `users` and `academic_periods` (the two other seed scripts' output) is treated as clean, so the generator composes with them instead of fighting them.
6. **`epic-2-context.md` is treated as a valid cached epic context and is not recompiled,** despite every file in `docs/` sharing one worktree-checkout mtime. It is the authoritative brief for this epic per the orchestrating session, and regenerating it would overwrite hand-approved content with a derived summary.
7. **`docs/sprint-status.yaml` is not updated by this run,** although the story key `2-1-geração-determinística-de-estudantes-turmas-e-matrículas` resolves cleanly. The orchestrating session owns that file exclusively while a sibling story builds concurrently.
8. **The spec exceeds the 1600-token SCOPE STANDARD target and is kept whole.** This is one cohesive goal (module + CLI + migration + tests) with no independently shippable sub-deliverable, and Epic 1's five specs set the same precedent.

## Design Notes

**Determinism by derivation, not by a single RNG stream (autonomous decision).** A single `random.Random(seed)` consumed top-to-bottom would make Story 2.2's first extra draw silently change every student generated before it, breaking reproducibility of an already-published base. Instead each id is `uuid.uuid5(NAMESPACE, f"{seed}|student|{i}")` and each choice derives from `blake2b(f"{seed}|{label}".encode())` — `hashlib` and `uuid5` are specified algorithms, stable across CPython versions and platforms, unlike `random.shuffle`/`random.choice`, whose implementations have changed between releases. This makes "byte-identical on any machine" a property of the construction rather than a hope about the standard library.

**Split assigned per classroom, not by independent coin flips (autonomous decision).** Students within a classroom are ordered by `derived_key(seed, "split", student_id)` and the first `round(n * train_ratio)` become `TRAIN`. This guarantees both splits appear in every classroom (so the `EVAL_DEMO`-filtered web application sees a populated roster for every turma, AD-11) and makes the realised ratio exactly predictable, which independent Bernoulli draws would not.

**`SyntheticProfile` lives in `domain/student.py` but not on the `Student` dataclass (autonomous decision).** D2 and AD-3 say the profile is a research label that must never reach a product response. Keeping the enum in the domain (the migration and the ORM model both need its values) while leaving the product-facing `Student` frozen dataclass untouched makes that boundary structural: no repository can accidentally carry the label into an application service, because the field it would populate does not exist. `StudentModel.synthetic_profile` is the only in-code carrier.

**`--reset` scope (autonomous decision).** It deletes, in FK-safe order, `assignment_submissions`, `assignments`, `grades`, `attendance_records`, `pedagogical_observations`, `enrollments`, `students`, `classrooms`, `synthetic_generation_runs` — every table whose rows a synthetic base owns or that would dangle without students/classrooms. It never deletes `users` (owned by `seed_dev_user.py`) or `academic_periods` (owned by `seed_dev_fixtures.py`), because neither references students and both are re-seeded by their own idempotent scripts.

**Fingerprint excludes `executed_at` (autonomous decision).** The run record's timestamp is wall-clock by definition and can never match across runs; the determinism claim is about the generated base, so `population_fingerprint` covers `classrooms`, `students` and `enrollments` only, each with a declared column list and a stable `ORDER BY`. Later stories append their fact tables to the same declaration.

## Verification

**Commands:**
- `cd backend && ./.venv/Scripts/python.exe -m alembic upgrade head` -- expected: `synthetic_generation_runs` created, `students.synthetic_profile` added, `synthetic_profile` type created
- `cd backend && ./.venv/Scripts/python.exe -m pytest` -- expected: the 63-test Epic 1 baseline plus the new synthetic and migration tests, all green
- `cd backend && ./.venv/Scripts/python.exe -m app.synthetic.generate --seed 42 --reset` (dev DB, port 5434) -- expected: 8 classrooms / 200 students / 200 enrollments, a fingerprint printed, exit 0; re-running without `--reset` exits 1 with a message naming the flag
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` then search the file -- expected: no `synthetic_profile` anywhere

**Manual checks:**
- Time one full-volume `--seed 42 --reset` run against the dev database and record the wall-clock figure in Implementation Notes (epic DoD: the full base is measured and declared, never exercised in CI).
- Confirm `backend/app/synthetic/__init__.py` is exactly 0 bytes (`wc -c`) — the concurrent Story 2.4 branch creates the same path.
