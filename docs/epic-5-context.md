# Epic 5 Context: Machine Learning Experimental

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The system trains, versions, and evaluates — entirely offline, never in the request path — an experimental ML model that explores patterns associated with student dropout in the synthetic dataset. Every output of this pipeline (the score, the evaluation) must always be framed as research data describing the synthetic dataset's simulated patterns, never as a fact or real-world probability about an actual student. This matters because the product's core promise is that follow-up is a human process grounded in traceable evidence, not an automated risk classification — the ML pipeline must stay structurally incapable of contaminating that promise.

## Stories

- Story 5.1: Offline preprocessing + training pipeline for the experimental model
- Story 5.2: Generating the experimental score as research data
- Story 5.3: Model evaluation on a leakage-free dataset split
- Story 5.4: Live demo truncated to "today" with no future leakage

## Requirements & Constraints

- The system generates an experimental score from the synthetic dataset associated with dropout patterns; this score must always be labeled and treated as experimental data, never as fact or real probability about the student.
- Every trained model version must be identifiable and associated with each prediction it produces (versioning).
- The dataset must be split into two cuts, decided at synthetic-generation time (never at query time): a Train cut used only to fit the model, and an Eval/Operation/Demo cut with complete trajectory and known outcome, used for both metric evaluation and the live demo (truncated to "today" when served live). Training records must never appear in evaluation or demo.
- Evaluation must report precision, recall, F1, and a confusion matrix as mandatory metrics; ROC-AUC and PR-AUC are additional/optional metrics. Results must be documented strictly as "ability to recognize simulated patterns in the synthetic dataset used" — never as real predictive validity over an actual school population.
- The score/prediction must never appear in any product endpoint or response schema (`/students/*`, `/follow-ups/*`); it lives behind a separate internal boundary (`/research/*` or a notebook).
- No UI state exists for the score anywhere in the product — this is a deliberate absence, not a hidden/unimplemented state.

## Technical Decisions

- Training and evaluation run only via offline CLI commands (`python -m app.ml.train`, `python -m app.ml.evaluate`), manually triggered by the author — never by the web process, never by a scheduler.
- A single scikit-learn `Pipeline` (preprocessing + model) is trained once and serialized as a versioned artifact; the exact same object is reused for inference — never a separate reimplementation of preprocessing for serving.
- If/when live inference exists, the artifact loads once per process (in-memory singleton) and is never reloaded or retrained per request. This assumes a single Uvicorn worker (`--workers 1`); multiple workers would require a shared cache instead (deferred/out of scope).
- Training reads via a `TrainingRepository` explicitly distinct from the web application's base repository class — never the same repository used by the live web path.
- `Student.dataset_split` (enum `TRAIN` | `EVAL_DEMO`) partitions the single synthetic Postgres base; it is assigned during synthetic generation, never computed at query time. There are never three separate synthetic bases. Train queries filter `= TRAIN`; the live web app and the demo filter `= EVAL_DEMO`.
- `as_of()` is the single source of truth for "today" truncation, overridable only via `SINALIZA_DEMO_AS_OF` (a rehearsal mechanism, not a product feature). It applies **only** to the live-serving read path (home, trajectory). `ml/evaluate` must **never** apply this truncation — it reads the full `EVAL_DEMO` cut with complete outcome, exactly as required to produce honest metrics. Applying `as_of()` truncation inside the evaluation script would corrupt the metrics by hiding the very outcome it needs to see.
- Both uses of `EVAL_DEMO` (untruncated metric evaluation vs. truncated live demo) read the same underlying rows — only the application layer differs in whether it truncates; no separate datasets are maintained.
- All of the above read-time invariants (`as_of`, `dataset_split`, pedagogical-record visibility) are enforced structurally by a single base repository, never by convention scattered across individual queries/endpoints — a new endpoint must not be able to "forget" to filter.
- `ml/` may only read domain models/ports; it is never imported by `presentation/` outside the cached-inference path.
- Data model: `Student.dataset_split` and `Student.synthetic_profile` (nullable enum of deterministic synthetic evolution profiles, e.g. `STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`) live directly on `Student`, not in a separate labels table — the evaluation needs per-student ground truth without an extra join. `synthetic_profile`, like the ML score, must never appear in any product endpoint/schema — it is a research label, not product data, and exposing it would both turn the demo into a self-fulfilling prophecy and leak the evaluation answer key. `MLModelVersion` and `MLPrediction` are the model-version and prediction records (outside the MVP data-model draft's core entities, introduced by this epic); each `MLPrediction` is associated with the `MLModelVersion` that produced it.

## Cross-Story Dependencies

- Story 5.2 (score generation) depends on the trained artifact and versioning scheme from Story 5.1.
- Story 5.3 (evaluation) and Story 5.4 (live demo) both read the same `EVAL_DEMO` cut but apply opposite truncation behavior (5.3 never truncates; 5.4 always truncates via `as_of()`) — this distinction is a deliberate, explicit application-layer difference, not something to "fix" toward consistency.
- The `dataset_split` field and synthetic profile labels are produced by Epic 2's synthetic data generator; Epic 5 consumes them but does not define them.
- The repository-level enforcement of `as_of`/`dataset_split` filtering (shared with the live trajectory/home read paths from other epics) means changes to that base repository affect both product reads and ML evaluation correctness.
