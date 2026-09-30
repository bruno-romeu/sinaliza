# Epic 2 Context: Geração de Dataset Sintético Calibrado

<!-- Compiled from planning artifacts (epics.md, ARCHITECTURE-SPINE.md, data-model.md, research.md, AGENTS.md). Edit freely. -->

## Goal

This epic produces the only data the system will ever run on: a deterministic, seed-reproducible synthetic base of ~200 students with a full school year of attendance, grades, assignment submissions, and pedagogical observations, partitioned into a training slice and an evaluation/demo slice. It is what makes Epic 3's change detection testable against known outcomes, what makes Epic 5's model trainable without leaking into its own evaluation, and what lets the whole system be demonstrated without a single real student record. It covers no numbered FR directly — it exists to satisfy RNF-07 (exclusively synthetic data) and RNF-13 (provenance and governance), and to deliver the `Student.dataset_split` field (AD-4) that Epic 5 consumes.

## Stories

- Story 2.1: Geração determinística de estudantes, turmas e matrículas
- Story 2.2: Perfis de trajetória sintética conhecidos aplicados aos fatos observáveis
- Story 2.3: Split de dataset em recorte de treino e recorte de avaliação/demo
- Story 2.4: Calibração de parâmetros por referência a base pública de dados educacionais
- Story 2.5: Registros pedagógicos sintéticos coerentes com o perfil do estudante

## Requirements & Constraints

- **Determinism is the headline requirement.** The same seed must produce a byte-identical base on any run, on any machine. This has to be provable, not asserted — verified by comparing a content hash of the generated tables across two runs, never by comparing row counts.
- The generator is a **CLI only**, run manually by the author. It is never triggered by an HTTP request, by application boot, or by a scheduler — the same boundary AD-3 draws around ML training.
- Every student gets a `dataset_split` (`TRAIN` or `EVAL_DEMO`) **assigned at generation time, never derived at query time** (AD-4). Exactly two values exist; there is never a third category and never a second synthetic database to keep in sync.
- Every student follows a **named, documented profile rule** from an enum (`STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`, …) — never opaque random generation (AGENTS.md §Dados sintéticos). The set must include at least one stable profile and one combined-deterioration profile, since those bracket the spectrum RF-11's convergence rule has to distinguish.
- Generation metadata (seed, generator version, execution date) must be **persisted**, not just logged — otherwise the determinism claim is unverifiable after the fact (RNF-13).
- Generated facts obey the **same integrity constraints as Epic 1**: `UNIQUE(student_id, classroom_id, date)` on attendance, the 0.0–10.0 `CHECK` on `Grade.value`, the tri-state submission status. The generator never writes a row the application itself could not have written.
- Every generated record is **100% fictional** — no real name, enrollment number, phone, address, or any other real student datum (RNF-07, RNF-13).
- The public reference base is used **offline only**, while calibrating the generator's constants. It is never queried at runtime and never persisted into the system's database.
- Each calibration parameter records its **provenance**: the public source and a confidence level. A parameter with no Brazilian public equivalent is marked explicitly as a design assumption, never dressed up as calibrated data.
- Synthetic pedagogical observation text is **factual and descriptive**, built from deterministic templates — never a judgment label like "aluno de risco" (`EXPERIENCE.md` §Voice and Tone).

## Technical Decisions

- Everything lives in `backend/app/synthetic/` per the Structural Seed: the deterministic generator CLI, the profile rules, and the calibration constants. There is **no frontend work in this epic at all.**
- The layering rules from Epic 1 still hold: `domain/` stays pure Python, and generation writes through the infrastructure layer rather than issuing hand-rolled SQL.
- **One new entity: `SyntheticGenerationRun`** (`id, seed, generator_version, executed_at, student_count, train_ratio`), plus a nullable `Student.synthetic_profile` column. One Alembic migration (`0006`) carries both — migrations only, never manual schema edits.
- `Student.synthetic_profile` is a research label, not product data. It is **never exposed in any product endpoint or response schema** — the same boundary AD-3 draws around the ML score. Exposing it would leak the evaluation's answer key and turn the demo into a self-fulfilling prophecy.
- **`seed_dev_fixtures.py` stays exactly as it is.** It keeps serving the test suite (small, fast, stable); the synthetic generator becomes the dev/demo path. The two coexist with separate jobs — no Epic 1 test is rewritten as collateral of this epic.
- **Re-running against a populated database requires an explicit `--reset`.** Silently appending would violate attendance's `UNIQUE` constraint and destroy the determinism guarantee in the same stroke.
- Volume is real: ~200 students × ~200 school days is roughly 40k attendance rows alone, before grades, assignments, and observations. Generation uses bulk inserts and declares a time budget; the test suite exercises the generator at **reduced volume**, never the full base.
- AD-11's read-side enforcement (`repositories/base.py` applying `dataset_split = EVAL_DEMO` to every web read) **already shipped in Epic 1**, with regression tests in `test_attendance.py` and `test_assignments.py`. Story 2.3 verifies and extends that guarantee rather than building it.

## Calibration Reality (from `research.md`)

This is the epic's most easily-faked requirement, so the research conclusion is stated here flatly:

- **Calibratable, high confidence:** dropout/abandonment rates from Censo Escolar 2023 — ~3.0% abandonment (Ensino Fundamental), ~5.9% evasion / 3.9% failure (Ensino Médio), with 1º ano do EM as an elevated-risk subgroup (~16–21% combined). Confirmed by two independent sources. Treat abandonment and evasion as two distinct variables; never sum them.
- **Proxy only, medium confidence:** grade distribution. No public Brazilian source exists for 0–10 report-card grades. SAEB's 4 proficiency levels are the only proxy, and the resulting 0–10 distribution is a **documented design assumption**, not calibrated data.
- **Pure design assumption, no source:** daily attendance and assignment non-delivery. No Brazilian public base measures either. PNAD's adjusted net attendance rate (98.9–100% EF / 80.6% EM) measures *access to school*, not *daily presence in a classroom* — using it as an attendance proxy would artificially inflate the simulated rate. Do not.
- Per-student real data is not obtainable: since Censo Escolar 2021, INEP publishes school-aggregated microdata for LGPD compliance. Calibration is against aggregate rates; the per-student distribution is a modeling decision, drawn, not sampled.

## Cross-Story Dependencies

- **2.4 feeds 2.2, not the other way around.** The calibration constants are an input to the profile rules — building 2.2 first means inventing parameters that 2.4 then replaces. 2.4 is built in parallel with 2.1 (disjoint files), and 2.2 consumes both.
- 2.1 establishes the module, the CLI, the migration, and the run-metadata record that every later story writes into.
- 2.3 depends on 2.2 for the "complete trajectory over the full school year" guarantee on the `EVAL_DEMO` slice; most of its non-leakage requirement is already satisfied by Epic 1's AD-11 base repository.
- 2.5 depends on 2.2's profile enum — observation templates are selected by profile.
- Downstream: Epic 3 computes trajectory indicators over the facts generated here and validates its convergence rule against `synthetic_profile` as ground truth. Epic 5 trains on `TRAIN` and evaluates on `EVAL_DEMO`, and depends on `dataset_split` being assigned here, at generation time.
