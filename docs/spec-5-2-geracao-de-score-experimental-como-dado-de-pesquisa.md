---
title: 'Geração de score experimental como dado de pesquisa'
type: 'feature'
created: '2026-10-16'
status: 'done'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: []
baseline_commit: '29cac28743e95e0a4d00edb0884e66dd88e29fbd'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 5.1 trains and versions an offline model (`MLModelVersion` + a serialized `sklearn.Pipeline`), but nothing yet uses that artifact to produce a score — there is no `MLPrediction` record, and no code reads the `EVAL_DEMO` cut for scoring.

**Approach:** Add a `PredictionRepository` (reads `EVAL_DEMO` students' pedagogical facts, mirroring `TrainingRepository`'s feature shape but for the eval/demo split, with no `as_of()` truncation), a new `MLPrediction` domain entity + table (FK to the `MLModelVersion` that produced it), and a `python -m app.ml.predict` CLI (mirroring `app/ml/train.py`'s shape) that loads the most recently trained `MLModelVersion`'s artifact via `joblib.load`, scores every `EVAL_DEMO` student, and persists one `MLPrediction` row per student with the model's probability that the student does **not** belong to the `STABLE` profile.

## Boundaries & Constraints

**Always:** Scoring reads students exclusively via the new `PredictionRepository`, filtering `dataset_split == DatasetSplit.EVAL_DEMO`, reading the full cut with **no** `as_of()` truncation (same rationale as `ml/evaluate` in Story 5.3: this is offline research tooling, not the live-demo path). `PredictionRepository` reuses `app/ml/training_repository.py`'s `FEATURE_COLUMNS` ordering/semantics so feature vectors line up with what the pipeline was fit on. The CLI runs only offline (`python -m app.ml.predict`), opening its own `SessionLocal()` directly like `app/ml/train.py` — never wired into `composition.py`/FastAPI, never invoked by the web process or a scheduler. It selects the single most recently trained `MLModelVersion` (max `trained_at`), `joblib.load`s its `artifact_path` verbatim (never refits or reimplements preprocessing), and calls `.predict_proba` on the loaded `Pipeline`. Every successful run inserts one `MLPrediction` row per scored student, each with a `model_version_id` FK to the `MLModelVersion` used and a `score` (float) = `1 - predict_proba(STABLE)` from that version's fitted classifier (locate the `STABLE` index via the pipeline's `classes_` attribute at run time — never hardcode a class index). `app/ml/` continues to only import domain models/ports, never `presentation/`.

**Never:** No `MLPrediction` field, score, or anything derived from it is added to any `presentation/` router or Pydantic schema (`/students/*`, `/follow-ups/*`, or any other product endpoint) — this story adds zero `presentation/` code. Never re-fits or re-evaluates the model — that's Story 5.3. Never dedupes or skips already-scored students on re-run — each run is a fresh, independent batch of `MLPrediction` rows tied to whichever `MLModelVersion` was latest at that moment; this is documented, non-fatal, append-only behavior, not a bug to guard against. Out of scope: evaluation metrics (Story 5.3), live inference loading / in-memory singleton (Story 5.4), any `/research/*` HTTP router (not needed yet — this story is CLI-only, consistent with Story 5.1's precedent).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | `EVAL_DEMO` students exist; at least one `MLModelVersion` row with a loadable artifact exists | Loads latest `MLModelVersion`, scores every `EVAL_DEMO` student, inserts one `MLPrediction` row each (score in `[0,1]`), prints summary, exit 0 | No error expected |
| No `MLModelVersion` exists | `ml_model_version` table empty | No `MLPrediction` rows written | Raises a domain error; CLI prints to stderr, exits non-zero |
| No `EVAL_DEMO` rows | Zero students with `dataset_split == EVAL_DEMO` | No `MLPrediction` rows written | Raises a domain error; CLI prints to stderr, exits non-zero |
| `EVAL_DEMO` student missing some facts | Some feature values are `None` (no attendance/grade/assignment/observation rows) | Student still scored (same null-handling as training's `SimpleImputer`); row written | Noted in printed summary, not fatal |
| Re-run the command twice | `python -m app.ml.predict` executed twice with the same latest `MLModelVersion` | Two `MLPrediction` rows per student exist, both referencing the same `model_version_id` | No error, non-destructive, documented append-only behavior |

</frozen-after-approval>

## Code Map

- `backend/app/ml/training_repository.py` — `FEATURE_COLUMNS` tuple and `TrainingRow`/query shape to mirror for `PredictionRepository`; reuse `FEATURE_COLUMNS` directly (import it) so feature ordering never drifts between training and scoring.
- `backend/app/ml/pipeline.py` — `build_pipeline()`; not called here (no refit), but confirms the fitted object exposes `.classes_` and `.predict_proba`.
- `backend/app/ml/train.py` — CLI shape to mirror exactly: `NoTrainingDataError` style custom error, `_version_string`/CLI arg parsing not needed here, `run_training(session, artifact_dir) -> MLModelVersion` pattern → mirror as `run_prediction(session, artifact_dir) -> list[MLPrediction]`; `main(argv=None)` opens `SessionLocal()`, catches domain errors, stderr + `sys.exit(1)` on failure, prints summary + exit 0 on success.
- `backend/app/domain/ml_model_version.py` — `MLModelVersion` dataclass shape to mirror for the new `MLPrediction` dataclass (`id`, `version`→n/a, `artifact_path`→n/a, `trained_at`/`created_at` pattern).
- `backend/app/infrastructure/db/models.py:346-360` — `MLModelVersionModel` (table `ml_model_version`, `String(64)` unique `version`, `String(1024)` `artifact_path`) — add `MLPredictionModel` near it; also `StudentModel` (lines 70-85) for `dataset_split`/`synthetic_profile` columns and `id` FK target.
- `backend/app/infrastructure/repositories/base.py` — `filter_eval_demo_students`/`filter_as_of`; `PredictionRepository` must filter `EVAL_DEMO` itself (same value, different repository) but must **not** call `filter_as_of` (no truncation for research scoring).
- `backend/app/domain/student.py` — `DatasetSplit.EVAL_DEMO`, `SyntheticProfile.STABLE` (and the other three profile values) — exact enum members to reference.
- `backend/alembic/versions/0011_create_ml_model_version_table.py` — most recent migration; new migration is `0012`, `down_revision = "0011"`; mirror its `op.create_table`/`postgresql.UUID(as_uuid=True)` style exactly.
- `backend/tests/test_ml_train.py` — test scaffold to mirror: `_seed_train_student`-style helper (here, seed `EVAL_DEMO` students instead), `_SessionContext` + `monkeypatch.setattr(..., "SessionLocal", ...)` / `get_settings` pattern for CLI-level (`main()`) tests; also need a seeded `MLModelVersionModel` row pointing at a real `joblib`-dumped fitted `Pipeline` fixture (fit `build_pipeline()` on a tiny in-test dataset and dump it to `tmp_path`, or reuse `run_training` against seeded `TRAIN` rows to produce a real artifact).
- `backend/tests/test_migrations.py` — extend with a `to_regclass('ml_prediction')` assertion after `upgrade()` / `IS NULL` after `downgrade()`.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/alembic/versions/0012_create_ml_prediction_table.py` — new migration creating `ml_prediction` (`id` PK, `student_id` FK → `students.id` not null, `model_version_id` FK → `ml_model_version.id` not null, `score` float not null, `created_at` timestamptz not null) — persists one row per scored student per run
- [ ] `backend/app/domain/ml_prediction.py` — new pure dataclass `MLPrediction` (`id`, `student_id`, `model_version_id`, `score`, `created_at`) — no framework imports, matching `ml_model_version.py`'s conventions
- [ ] `backend/app/infrastructure/db/models.py` — add `MLPredictionModel` ORM class with FKs to `students` and `ml_model_version` — backs the new migration
- [ ] `backend/app/ml/prediction_repository.py` — new `PredictionRepository(session)` with `fetch_scoring_rows() -> list[...]` reading `StudentModel` rows with `dataset_split == DatasetSplit.EVAL_DEMO`, joined with the same pedagogical fact sources as `TrainingRepository`, reusing `FEATURE_COLUMNS` — structurally separate from `SqlAlchemyStudentRepository`, never calls `filter_as_of`
- [ ] `backend/app/ml/predict.py` — new CLI module: `run_prediction(session, artifact_dir) -> list[MLPrediction]` (loads latest `MLModelVersionModel` by `trained_at`, `joblib.load`s its artifact, fetches rows via `PredictionRepository`, computes `score = 1 - predict_proba(STABLE)` per student via the fitted pipeline's `classes_`, inserts one `MLPredictionModel` row per student, raises on no model version / no scoring rows), `main(argv=None)` mirroring `app/ml/train.py`
- [ ] `backend/tests/test_ml_predict.py` — new file: happy path (asserts one `MLPredictionModel` row per seeded `EVAL_DEMO` student, each `score` in `[0, 1]`, each `model_version_id` matching the seeded version), no-model-version error case, no-`EVAL_DEMO`-rows error case, missing-facts non-fatal case, two-runs-produce-two-rows-per-student case, plus CLI-level `main()` stderr/exit-code coverage mirroring `test_ml_train.py`'s `_SessionContext` pattern
- [ ] `backend/tests/test_migrations.py` — extend with `ml_prediction` table existence assertions after `upgrade()`/`downgrade()`

**Acceptance Criteria:**
- Given at least one `EVAL_DEMO` student and a trained `MLModelVersion` with a loadable artifact, when `python -m app.ml.predict` runs, then it inserts one `MLPrediction` row per `EVAL_DEMO` student, each referencing the latest `MLModelVersion` and a `score` in `[0, 1]`.
- Given the prediction code, when inspected, then all its data access goes through `PredictionRepository`, which filters `EVAL_DEMO`, never calls `filter_as_of`, and shares no base class with any `SqlAlchemy*Repository` reachable from `composition.py`.
- Given zero `MLModelVersion` rows or zero `EVAL_DEMO` students, when `python -m app.ml.predict` runs, then it exits non-zero with a clear stderr message and writes no `MLPrediction` rows.
- Given the full codebase, when inspected, then no `presentation/` router or Pydantic schema references `MLPrediction`, a prediction score, or anything derived from it.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Pass 1 (thorough: blind-hunter, edge-case-hunter, verification-gap, intent-alignment). Verdict counts: medium=4, low=1, false=6, out of 13 findings (after grouping/dedup across lenses).

- [verification-gap, other] `backend/ml_artifacts/model-20261017T013302119387-61d09ddb.joblib` — a trained-model binary artifact — was staged into the diff. → **medium**: confirmed via `git diff --cached --stat`, file is `A` (added). Caused by the reviewing session's own `git add -A` after running the CLI verification commands against the dev DB, which wrote into `backend/ml_artifacts/` (a real runtime-output directory inside the repo root, never gitignored). `ml_artifacts/` is documented everywhere (spec, `app/config.py`, `train.py`) as a per-run output location, never a tracked asset. Kept, routed to patch (remove from git, add `.gitignore` entry).
- [blind-hunter] Same artifact file, noting its timestamp is a day after the spec's `created` date. → merged into the entry above (same root cause).
- [intent-alignment] Same artifact file, "never mentioned by the spec, byproduct of local exercising." → merged into the entry above (same root cause).
- [edge-case-hunter] `predict.py`: `joblib.load` on a missing/corrupted artifact file raises uncaught, instead of a clean stderr+exit(1) like the two documented domain errors. → **false**: refuted by direct precedent — `docs/deferred-work.md`'s Story 2.1 entry logs the identical, already-accepted gap for `app/synthetic/generate.py`'s `main()` ("only catches `DatabasePopulatedError`...any other failure surfaces as a raw traceback"), which `app/ml/train.py` already mirrors verbatim (accepted in Story 5.1's own review as "mirrors an existing, already-deferred pattern — not a regression"). `predict.py`'s Code Map explicitly directs mirroring `train.py`'s shape; same established, logged, accepted pattern, not a new defect.
- [edge-case-hunter] `predict.py`: `run_prediction` raising any exception other than the two documented domain errors is also uncaught by `main()`. → **false**, same refutation as above — merged.
- [blind-hunter] No test/handling for a corrupted/missing artifact file. → **false**, same refutation as above — merged.
- [edge-case-hunter] `predict.py`: if the loaded pipeline's `classes_` never contains `STABLE` (e.g. a model trained on a `TRAIN` cut with no `STABLE`-labeled rows), `classes.index(...)` raises an unhandled `ValueError`. → **low**: real but the TRAIN cut is generated deterministically by Epic 2's synthetic generator, which seeds all 4 `SyntheticProfile` values across a reasonably sized population — unlikely a real training run ever produces a `STABLE`-free model. Fix requires a new guard/domain error class (`UnscoreableModelError`), which is more than a direct correction. Rejected per the low-finding rule (unlikely + fix more than direct correction).
- [edge-case-hunter] `predict.py`: two `MLModelVersion` rows sharing the exact same `trained_at` would make "latest" selection nondeterministic. → **low**, real but fix is a direct one-line addition (extra `order_by` tiebreaker column, e.g. `id.desc()`). Kept, routed to patch.
- [blind-hunter] `prediction_repository.py`: the `FEATURE_COLUMNS`/`ScoringRow` order-parity guard is a bare `assert`, stripped when Python runs with `-O`, silently defeating the guard. → **medium**: if triggered, consequence is silent feature-order drift between training and scoring (wrong predictions with no error) — a real, meaningfully bad outcome, and the fix (replace `assert` with an explicit `if ...: raise RuntimeError(...)`) is a direct, trivial correction. Kept, routed to patch.
- [blind-hunter] `run_prediction`'s `artifact_dir` parameter is unused ("dead parameter"). → **false**: refuted directly against the spec's own Code Map, which explicitly specifies this exact signature — "mirror as `run_prediction(session, artifact_dir) -> list[MLPrediction]`" — for call-shape parity with `run_training`. Deliberate, spec-directed, not an oversight.
- [blind-hunter] `PredictionRepository.fetch_scoring_rows()` duplicates `TrainingRepository`'s attendance/grade/submission/observation aggregation SQL almost verbatim (only `FEATURE_COLUMNS` itself is shared). → **medium**: real duplicated source of truth — a future fix to one repository's aggregation logic (e.g. how `attendance_rate` is computed) would not propagate to the other, silently causing feature-computation drift between training and scoring with no test to catch it. Fix (extract a shared aggregation helper used by both repositories) is a non-trivial refactor touching `training_repository.py` too, and the spec's own Boundaries direct `PredictionRepository` to be written as a structurally separate implementation (mirroring, not sharing with, `TrainingRepository`) beyond the explicit `FEATURE_COLUMNS` reuse — the spec doesn't clearly settle whether full aggregation-logic sharing was intended. Routed to **defer**.
- [blind-hunter] No test exercises "latest `MLModelVersion` selected by `trained_at`" when more than one `MLModelVersion` row exists — all current tests train exactly one model. → **medium**: this is acceptance-criteria-relevant logic (the spec's Boundaries require selecting "the single most recently trained `MLModelVersion` (max `trained_at`)") left unverified against competing rows; a latent ordering bug wouldn't be caught. Fix is test-only and trivial. Kept, routed to patch.
- [blind-hunter] `ml_prediction`'s FKs (`student_id`, `model_version_id`) have no `ondelete` policy. → **false**: refuted by precedent — `docs/deferred-work.md` already documents this exact pattern codebase-wide (Story 1.5 and Story 3.2 entries: every existing FK omits `ondelete`), and no deletion code path exists anywhere for `Student`/`MLModelVersion` rows today (nothing to actually trigger this). Consistent with established, already-accepted convention, not a new defect.
- [blind-hunter] `main()`'s `missing_facts_count` only checks `attendance_rate`/`grade_average`/`assignment_completion_rate` for `None`, excluding `observation_count`. → **false**: refuted directly — `observation_count` is typed `int` (never `None`) in both `ScoringRow` and `TrainingRow`, defaulting to `0` when a student has no observation rows; checking it for `None` would never fire by design, so excluding it is correct, not an oversight.
- [blind-hunter] Repeated manual verification runs (`uv run python -m app.ml.train && uv run python -m app.ml.predict`) accumulate rows/artifacts in the dev DB with no documented cleanup. → rejected: the only fix here is editing the spec's own Verification section, which is explicitly out of scope for triage ("reject any finding whose fix is to edit this build's spec").
- [verification-gap, pre-verified] `main()`'s printed summary includes a `missing_facts_count`, but the only test exercising `main()`'s success path (`test_main_exits_zero_and_prints_summary_on_success`) seeds a single student with all facts present, so `missing_facts_count` is trivially `0` and the assertion never inspects that part of the string; the direct-call test for the missing-facts matrix row never reaches `main()`/the summary at all. → **medium**: a regression in the missing-facts counting logic could ship silently wrong. Kept, routed to patch.
- [intent-alignment] The spec's acceptance criteria name two structural/architectural facts (`PredictionRepository` shares no base class reachable from `composition.py`; no `presentation/` code references `MLPrediction`) as inspectable outcomes, but no automated test asserts them — only manual/one-time inspection does. → **false**: mirrors the identical, already-accepted gap in Story 5.1 (its own `TrainingRepository` separation is likewise untested by a dedicated structural test) — established codebase convention, not a regression introduced by this story.

**Patch entries dispatched** (5, after grouping by root cause):
1. `backend/ml_artifacts/model-20261017T013302119387-61d09ddb.joblib` — stray trained-model artifact staged into the diff — remove it from git tracking and add a `.gitignore` entry so `ml_artifacts/` (or `*.joblib`) is never tracked again.
2. `backend/app/ml/predict.py` — "latest `MLModelVersion`" selection has no tiebreaker for equal `trained_at` values — add a deterministic secondary `order_by` (e.g. `id.desc()`) after `trained_at.desc()`.
3. `backend/app/ml/prediction_repository.py` — the `FEATURE_COLUMNS`/`ScoringRow` order-parity guard is a bare `assert`, stripped under `python -O` — replace it with an explicit `if ...: raise RuntimeError(...)`.
4. `backend/tests/test_ml_predict.py` — no test exercises "latest by `trained_at`" selection when multiple `MLModelVersion` rows exist — add a test seeding two model versions with different `trained_at` values and asserting the newer one is used.
5. `backend/tests/test_ml_predict.py` — `missing_facts_count`'s actual numeric value in `main()`'s printed summary is never asserted — extend or add a `main()`-level test with one `with_facts=True` and one `with_facts=False` `EVAL_DEMO` student, asserting the exact missing-facts count in `captured.out`.

## Design Notes

`score = 1 - predict_proba(STABLE)` gives a single scalar in `[0, 1]` summarizing "probability the model associates this student's synthetic trajectory with a non-stable (deterioration) profile" — simple, deterministic given a fitted pipeline, and avoids inventing a bespoke risk formula. Locate `STABLE`'s column index via `pipeline.named_steps["classifier"].classes_.tolist().index(SyntheticProfile.STABLE.value)` (classes are the string enum values used as labels in `app/ml/train.py`) rather than assuming a fixed index, since scikit-learn sorts `classes_` alphabetically and that order must never be hardcoded.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_ml_predict.py -q` -- expected: all new tests pass
- `cd backend && uv run pytest -q` -- expected: full suite green (aside from the 4 pre-existing unrelated failures already logged in `docs/deferred-work.md`)
- `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` -- expected: `ml_prediction` table created, cleanly dropped, then recreated
- `cd backend && uv run python -m app.ml.train && uv run python -m app.ml.predict` (against the dev DB) -- expected: train prints a summary and writes an `MLModelVersion`; predict prints a summary and a new `MLPrediction` row per `EVAL_DEMO` student is visible in the DB

**Manual checks (if no CLI):**
- Inspect a few `MLPrediction` rows and confirm `score` is a float in `[0, 1]` and `model_version_id` matches the `MLModelVersion` used.
