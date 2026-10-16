---
title: 'Pipeline de pré-processamento e treino do modelo offline'
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
baseline_commit: 'e2b8459035904120027bbfbe68516de8c1fa3815'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no way to train an ML model on the synthetic dataset's `TRAIN` cut today — nothing produces a versioned, reusable preprocessing+model artifact, and no code reads `TRAIN` rows through a repository structurally separate from the web application's `EVAL_DEMO`-only read path.

**Approach:** Add an `app/ml/` package with a `TrainingRepository` that reads only `Student` rows with `dataset_split == TRAIN` and a non-null `synthetic_profile` label, joined with pedagogical facts as features; a `build_pipeline()` factory for a single scikit-learn `Pipeline` (preprocessing + classifier); and a `python -m app.ml.train` CLI (mirroring `app/synthetic/generate.py`'s shape) that fits the pipeline, serializes it to a versioned artifact file, and persists one `MLModelVersion` row Story 5.2 will later reference.

## Boundaries & Constraints

**Always:** Training reads students exclusively via the new `TrainingRepository`, filtering `dataset_split == TRAIN`; this repository never calls `filter_eval_demo_students`/`filter_as_of` and is not a subclass of, or shared code with, any `SqlAlchemy*Repository` used by the web path (AD-11). The command runs only as an offline CLI (`python -m app.ml.train`), opening its own `SessionLocal()` directly like `app/synthetic/generate.py` — never wired into `composition.py`/FastAPI `Depends`, never invoked by the web process or a scheduler (AD-3). The serialized artifact is the single sklearn `Pipeline` object (preprocessing fused with the model) that inference must reuse verbatim later — never a separately reimplemented preprocessing step (RNF-03). Every successful run inserts one new `MLModelVersion` row with an identifiable, unique version string and the artifact's file path (RF-17). `app/ml/` only imports domain models/ports, never `presentation/`.

**Never:** Never reads or writes `EVAL_DEMO` rows (out of scope here — Story 5.2/5.3/5.4). Never exposes anything via a product HTTP endpoint or router — this story adds no `presentation/` code at all (RF-21/AD-3). Never overwrites a prior `MLModelVersion` row or artifact file on re-run. Out of scope: prediction generation (Story 5.2), evaluation metrics (Story 5.3), live inference loading (Story 5.4).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | `TRAIN` students with `synthetic_profile` set and pedagogical facts present | Fits the `Pipeline`, writes artifact file, inserts `MLModelVersion` row (version + path), prints summary, exit 0 | No error expected |
| No usable training rows | Zero `TRAIN` rows with non-null `synthetic_profile` | No artifact file or `MLModelVersion` row written | Raises a domain error; CLI prints to stderr, exits non-zero |
| `TRAIN` row missing label | Some `TRAIN` rows have `synthetic_profile IS NULL` | Row excluded from the training set; only fatal if this empties the set (same as the no-usable-rows case) | Noted in the printed summary, not fatal on its own |
| Re-run the command twice | `python -m app.ml.train` executed twice in a row | Two distinct `MLModelVersion` rows and two distinct artifact files exist; neither run touches the other's | No error, non-destructive |

</frozen-after-approval>

## Code Map

- `backend/app/synthetic/generate.py` -- CLI pattern to mirror exactly: `_build_arg_parser()`, `main(argv=None)`, opens `with SessionLocal() as session:`, catches domain errors and does `print(..., file=sys.stderr); sys.exit(1)`, prints a summary and exits 0 on success.
- `backend/app/infrastructure/repositories/base.py` -- `filter_eval_demo_students`/`filter_as_of` helpers used by every web-path repository; `TrainingRepository` must not call either.
- `backend/app/infrastructure/repositories/sqlalchemy_student_repository.py` -- `SqlAlchemyStudentRepository`, the web-path repo `TrainingRepository` must stay structurally separate from (different module, no shared base/mixin).
- `backend/app/domain/student.py` -- `DatasetSplit` (`TRAIN`/`EVAL_DEMO`) and `SyntheticProfile` enums; the product-facing `Student` dataclass deliberately omits `synthetic_profile`, so `TrainingRepository` needs its own read shape that includes it.
- `backend/app/infrastructure/db/models.py:70-85` -- `StudentModel.dataset_split`/`synthetic_profile` columns; also `AttendanceRecordModel`, `GradeModel`, `AssignmentModel`, `AssignmentSubmissionModel`, `PedagogicalObservationModel` as feature sources.
- `backend/alembic/versions/0010_synthetic_profile_self_heal_falling_grades.py` -- most recent migration; the new migration is `0011`, `down_revision = "0010"`.
- `backend/app/config.py` -- `Settings(BaseSettings)` pattern (`Field(...)` validation style) to add `ml_artifact_dir` to.
- `backend/pyproject.toml` -- no scikit-learn/joblib/numpy yet; add via `uv add scikit-learn joblib`.
- `backend/tests/test_synthetic_facts_generation.py`, `test_synthetic_dataset_split.py` -- test pattern to mirror: call the generation function directly against the `db_session` fixture (never subprocess).
- `backend/tests/test_migrations.py` -- precedent for asserting a new table exists after `upgrade()` / is gone after `downgrade()`.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/pyproject.toml` -- add `scikit-learn` and `joblib` as dependencies (`uv add scikit-learn joblib`) -- needed to build and serialize the `Pipeline`
- [ ] `backend/alembic/versions/0011_create_ml_model_version_table.py` -- new migration creating `ml_model_version` (`id`, `version` unique, `artifact_path`, `trained_at`, `created_at`) -- persists the versioned record Story 5.2 will reference
- [ ] `backend/app/domain/ml_model_version.py` -- new pure dataclass `MLModelVersion` -- no framework imports, matching domain/ conventions
- [ ] `backend/app/infrastructure/db/models.py` -- add `MLModelVersionModel` ORM class -- backs the new migration
- [ ] `backend/app/ml/__init__.py` -- new package
- [ ] `backend/app/ml/training_repository.py` -- new `TrainingRepository(session)` reading only `StudentModel` rows with `dataset_split == DatasetSplit.TRAIN` and non-null `synthetic_profile`, joined with attendance/grade/assignment/pedagogical-observation facts into per-student feature rows + label -- structurally distinct from `SqlAlchemyStudentRepository` (AD-11)
- [ ] `backend/app/ml/pipeline.py` -- new `build_pipeline() -> Pipeline` returning an unfitted sklearn `Pipeline` (preprocessing `ColumnTransformer` + a deterministic classifier, fixed `random_state`) -- the single object reused at inference (RNF-03)
- [ ] `backend/app/ml/train.py` -- new CLI module: `_build_arg_parser()`, `run_training(session, artifact_dir) -> MLModelVersion`, `main(argv=None)` mirroring `app/synthetic/generate.py` -- fetches data via `TrainingRepository`, fits `build_pipeline()`, serializes with `joblib.dump` to a uniquely-versioned filename under `artifact_dir`, inserts an `MLModelVersionModel` row, raises on an empty training set
- [ ] `backend/app/config.py` -- add `ml_artifact_dir: str` (default `"./ml_artifacts"`) -- configurable artifact storage location
- [ ] `backend/tests/test_ml_train.py` -- new file calling `run_training(db_session, tmp_path)` directly -- asserts happy path creates exactly one `MLModelVersionModel` row and one `joblib`-loadable fitted `Pipeline` file; empty-training-set raises the documented error; two consecutive runs produce two distinct versions/files
- [ ] `backend/tests/test_migrations.py` -- extend with a `to_regclass('ml_model_version')` assertion after `upgrade()` and `IS NULL` after `downgrade()`, following the existing pattern

**Acceptance Criteria:**
- Given the `TRAIN` cut with populated `synthetic_profile` labels, when `python -m app.ml.train` runs, then it fits one sklearn `Pipeline`, serializes it under the configured artifact directory, and inserts one `MLModelVersion` row with a unique version and that path.
- Given the training code, when inspected, then all its data access goes through `TrainingRepository`, which never calls `filter_eval_demo_students` and shares no base class with any `SqlAlchemy*Repository` reachable from `composition.py`.
- Given zero `TRAIN` rows with a non-null `synthetic_profile`, when `python -m app.ml.train` runs, then it exits non-zero with a clear stderr message, writing neither an artifact file nor an `MLModelVersion` row.
- Given two consecutive successful runs, when both complete, then two distinct `MLModelVersion` rows and two distinct artifact files exist, and neither overwrote the other.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Pass 1 (thorough: blind-hunter, edge-case-hunter, verification-gap, intent-alignment). Verdict counts: medium=3, low=3, false=8.

- [blind-hunter] `SimpleImputer`'s default `missing_values=np.nan` vs `TrainingRepository` producing Python `None` for missing aggregates. → **false**: the happy-path test seeds a `with_facts=False` row (all-`None` features) and passed in actual execution (`uv run pytest tests/test_ml_train.py -q`, 5 passed) — numpy's `np.asarray(X, dtype=float)` coerces `None` to `nan` on construction, which `check_array`/`SimpleImputer` then handle normally. Refuted by passing test evidence.
- [blind-hunter] `scikit-learn>=1.9.1`/`joblib>=1.6.0` added as open-ended lower bounds while every other dependency in `pyproject.toml` is pinned exactly. → **low**. Fix is a direct correction (pin the resolved versions) → kept, routed to patch.
- [blind-hunter] `MLModelVersion` stores no feature-schema/hyperparameter/training-snapshot metadata. → **false**: the frozen Boundaries explicitly scope the row to "an identifiable, unique version string and the artifact's file path" only — matches intent, not a gap.
- [blind-hunter] No test exercises `main()`/the CLI entry point itself. → **medium** (see intent-alignment's matching finding below; merged into one patch entry).
- [blind-hunter] `joblib.dump` before `session.commit()` risks an orphaned artifact file if commit fails for any reason. → **low**, fix requires adding a try/except guard (more than a direct correction) and commit failure is unlikely in an offline single-operator CLI → auto-rejected per the low-finding rule.
- [blind-hunter] Version string (microsecond timestamp only) has no collision handling if two runs land in the same microsecond tick. → **medium**: real risk, confirmed independently by edge-case-hunter. Kept, routed to patch.
- [blind-hunter] `sprint-status.yaml` bump to `in-progress` has no accompanying narrative doc. → **false**: this is the standard `sync-sprint-status.md` workflow step, by design, not a code defect.
- [blind-hunter] Feature aggregates are unbounded lifetime history, no time-windowing. → **false**: matches the approved spec's own Design Notes verbatim ("per-student aggregates over their full TRAIN history").
- [blind-hunter] No DB index / documented "latest version" lookup pattern for `MLModelVersion`. → **false**/out-of-scope: that lookup belongs to Story 5.2 (prediction generation), explicitly listed as out of scope for this story.
- [blind-hunter] `ml_artifact_dir`'s relative-path default could resolve differently across processes/CWDs. → **false**/out-of-scope: only matters once a second (inference) process exists, which is Story 5.2/5.4's concern, not reachable today.
- [edge-case-hunter] `main()` only catches `NoTrainingDataError`; any other exception propagates as a raw traceback. → **false**: this mirrors `app/synthetic/generate.py`'s existing, already-deferred pattern (`docs/deferred-work.md`) verbatim, per the spec's own Code Map instruction to mirror that file's shape — not a regression introduced by this story.
- [edge-case-hunter] Version collision (same as blind-hunter's finding above) → merged, see **medium** patch entry.
- [edge-case-hunter] `ml_artifact_dir` pointing at an existing non-directory file would make `mkdir(parents=True, exist_ok=True)` raise. → **low**, unlikely misconfiguration + fix requires an added guard → auto-rejected.
- [edge-case-hunter] (claim) `ml_artifact_dir` should follow the `Field(...)` validation style per the spec's Code Map. → **false**: refuted directly against `config.py` — plain string settings (`dev_seed_name`, `dev_seed_email`) use no `Field()` either; `Field(...)` is only used for numeric bounds (`jwt_expire_minutes`, `trajectory_window_days`), which don't apply to a path string.
- [verification-gap, pre-verified] No test asserts `TrainingRepository.fetch_training_rows()`'s computed feature values against the known seeded facts — only end-to-end fit success is checked, so an inverted aggregation (e.g. counting absences instead of presences) would ship with a green suite. → **medium**. Kept, routed to patch.
- [verification-gap, other] `pipeline.py`'s `_NUMERIC_FEATURE_COUNT = 4` duplicates `len(training_repository.FEATURE_COLUMNS)` with only a comment enforcing sync. → **low**, fix is a direct substitution (derive from `len(FEATURE_COLUMNS)` instead of hardcoding) → kept, routed to patch.
- [intent-alignment] CLI entry point (`main()`) and the `ml_artifact_dir` default wiring it exercises are never invoked by any test — the I/O Matrix's documented CLI-level behavior (stderr + exit code) is unverified by execution. → **medium**. Merged with blind-hunter's matching finding into one patch entry.
- [intent-alignment] `app/config.py`'s comment says "Story 5.4's inference loader will read this same setting," while `ml_model_version.py`/`MLModelVersionModel` both say Story 5.2. → **low**: verified against `docs/epics.md` — Story 5.2 is the live-inference/`joblib.load` story, Story 5.4 is display-only truncation, so `config.py`'s comment is the one that's wrong. Fix is a direct one-line correction → kept, routed to patch.

**Patch entries dispatched** (6, after grouping by root cause):
1. `backend/app/ml/train.py` — no test exercises `main()` — add tests for the stderr/exit(1) and print/exit(0) CLI paths.
2. `backend/app/ml/train.py` — version string has no collision handling — append a short random suffix so uniqueness never depends on clock resolution alone.
3. `backend/pyproject.toml` — `scikit-learn`/`joblib` unpinned — pin exact resolved versions.
4. `backend/app/config.py` — wrong story number in `ml_artifact_dir` comment — correct "Story 5.4" to "Story 5.2".
5. `backend/tests/test_ml_train.py` — no assertion on `TrainingRepository`'s computed feature values — add direct value assertions against seeded facts.
6. `backend/app/ml/pipeline.py` — `_NUMERIC_FEATURE_COUNT` duplicates `FEATURE_COLUMNS`'s length — derive it instead of hardcoding.

## Design Notes

Feature engineering only needs to be reasonable, not exhaustive — this story's ACs test structure (single `Pipeline`, `TrainingRepository` separation, versioning), not model quality. A sensible default: per-student aggregates over their full `TRAIN` history — attendance rate, grade average, assignment on-time/completion rate, pedagogical-observation count — as numeric features, with `synthetic_profile` as the categorical label. Use a fixed `random_state` on the classifier so training is deterministic across runs. Version string: `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")` is sufficient uniqueness for a single-operator offline CLI; no need for a counter or external ID scheme.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_ml_train.py -q` -- expected: all new tests pass
- `cd backend && uv run pytest -q` -- expected: full suite green (aside from the 4 pre-existing unrelated failures already logged in `docs/deferred-work.md`)
- `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1` -- expected: `ml_model_version` table created then cleanly dropped
- `cd backend && uv run python -m app.ml.train` (against the dev DB) -- expected: prints a summary, writes an artifact file under the configured directory, and a new `MLModelVersion` row is visible in the DB

**Manual checks (if no CLI):**
- Inspect the artifact file written under `ml_artifact_dir` and confirm `joblib.load(path)` returns a fitted `sklearn.pipeline.Pipeline` whose `.predict`/`.predict_proba` runs without error on a held-out feature row.
