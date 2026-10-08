# Epic 3 Context: Trajetória e Detecção de Mudança Convergente

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic turns the raw facts Epic 1 lets the coordination record (and Epic 2 generates synthetically) into trustworthy signal: on-demand trajectory indicators per student, and a convergence rule that only ever flags a change when at least two independent signals confirm it in the same bimester — never from a single metric or formula. It delivers the Home page's recent-changes list and the Student Trajectory screen (chart, timeline, evidence cards, "fator preocupante"), the two surfaces where the coordination actually sees what changed and why, always traceable back to source records. It fulfills UJ-1 and explicitly forbids any risk ranking, evasion score, or "high-risk student" KPI anywhere in the interface.

## Stories

- Story 3.1: Cálculo de indicadores de trajetória em janela rolante
- Story 3.2: Detecção de mudança relevante por convergência de sinais
- Story 3.3: Página inicial com mudanças recentes
- Story 3.4: Trajetória do estudante — gráfico, evidências e fator preocupante

## Requirements & Constraints

- Trajectory indicators (`attendance_rate`, `attendance_trend`, `grade_average`, `grade_trend`, `missing_assignments_count`, `missing_assignment_delta`) are computed over a **rolling window** (`window_days`), not tied to `AcademicPeriod` — attendance and assignments are continuous signals; only grades stay anchored to the official bimester via `Grade.period_id`.
- A trajectory change is only ever surfaced when **≥2 independent signals** (attendance, grades, assignments, pedagogical observation) confirm in the same `period_id`. A single confirmed signal with no convergence is returned as a "fator preocupante" — never persisted, no stable id, never citable as evidence.
- The pedagogical observation signal carries **equal weight** to the others — it can contribute to convergence on its own, alongside any other signal.
- Every `TrajectoryChange` must have at least one source record (`TrajectoryChangeSource`) — traceability is non-negotiable (RF-09, RNF-11).
- The Home page's recent-changes list is ordered strictly by **detection date**, never by severity or score. This epic delivers that list in full; the "acompanhamentos em andamento" section of the same Home page is added later by Epic 4.
- **Hard UI prohibition (RF-21):** no student ranking, no evasion score, no "high-risk students" KPI, anywhere, in any form — and no feature anywhere in the system may directly compare students to each other. The Y-axis of the trajectory chart is always labeled with the real indicator (attendance/grades/assignments), never "score" or "risco".
- Accessibility (RNF-08, WCAG 2.1 AA) applies to all three main screens touched here (Home, Trajectory): keyboard navigation in reading order (chart → evidence → fator preocupante → timeline), visible focus, 44×44px touch targets, no information conveyed by color alone.
- Microcopy follows the Voice and Tone rule: short, factual sentences referencing the source record (e.g. "Mudança recente: queda de frequência e aumento de atividades pendentes — 3º bimestre") — never diagnostic, predictive, or judgmental language (never "82% de chance de evasão" or "aluno de risco").
- Required UI states: empty "no recent changes" (explicit message, not a generic empty list), loading skeleton (never a full-screen spinner), load error (factual message + retry action), search with no results (no auto-suggestions), student/trajectory not found (factual message + link back to Home, no dedicated 404 page).

## Technical Decisions

- **Calculation is always synchronous, on-demand, inside the HTTP request** (`GET /home`, `GET /students/{id}/trajectory`) — never a scheduled job, worker, or cron. Each student recomputed is its own transaction; a failure for one student never rolls back the others. At ~200 students this is fine as plain set-based queries — no Python per-student loop; only optimize if a real RNF-01 (5s) measurement shows risk, and even then, optimization may only reduce per-request cost, never move the computation outside the request path.
- **Upsert key for `TrajectoryChange` is `(student_id, type, period_id)`**, enforced by a `UNIQUE` constraint and written as `INSERT ... ON CONFLICT ... DO UPDATE` — never a two-step `SELECT` then `INSERT`/`UPDATE`. This is what makes concurrent requests safe without explicit locks.
- **Freeze-on-evidence:** once a `TrajectoryChange` has at least one `FollowUpEvidence` pointing to it, recomputation becomes `DO NOTHING` — description, `detected_at`, and its `TrajectoryChangeSource` rows stop changing. Before that, each recomputation fully replaces them (delete+reinsert in the same transaction) to reflect the current window.
- **`TrajectoryChange` is an immutable event, never a live gauge.** If the signals that triggered it stop confirming in a later recomputation of the same `period_id` (student recovered), the row is never deleted or reverted — recovery shows up only as the absence of a new change in a later period.
- `FollowUpEvidence` is never written by the detection path — only by an explicit coordination action in Epic 4's `application/followup`. No auto-attach when a new `TrajectoryChange` appears for an already-open `FollowUp`.
- **Fixed pipeline contract (AD-12):** `SignalEvaluator.evaluate(student_id, period_id) -> Signal(confirmed, kind, source_ids)` for all four evaluators (attendance, grades, assignments, pedagogical observation); `ConvergenceRule.evaluate(signals) -> TrajectoryChange | None` combines ≥2 confirmed signals in the same period. Raw indicator math lives in `domain/trajectory.py` as a pure function, no I/O — unit-testable in isolation and reusable by any future ML feature engineering without reimplementing the formula.
- All reads go through the single base repository that already enforces `dataset_split = EVAL_DEMO` and `as_of()` truncation by default (shipped in Epic 1/Epic 2) — this epic's queries never bypass it, never read `TRAIN`, and never read beyond "today".
- Data model already exists (`docs/data-model.md`): `TrajectorySnapshot`, `TrajectoryChange` (`UNIQUE(student_id, type, period_id)`), `TrajectoryChangeSource` (real FK, `source_type` enum of `ATTENDANCE_RECORD | GRADE | ASSIGNMENT_SUBMISSION | PEDAGOGICAL_OBSERVATION`). `TrajectoryChange.type` is a closed enum: `ATTENDANCE_DROP`, `GRADE_DROP`, `MISSING_ASSIGNMENTS_INCREASE`, `COMBINED_DETERIORATION` (draft, may be revised when implementing the detection rule). "Fator preocupante" has no table at all.
- The exact convergence threshold's form is fixed by this epic (≥2 independent confirmed signals), but the PRD still marks the precise calibration an `[ASSUMPTION]` to validate once the synthetic base (Epic 2) exists — calibrate against `Student.synthetic_profile` as ground truth, never expose that field in any product response.
- Layering still applies: `domain/` (pure Python — indicators, `SignalEvaluator`, `ConvergenceRule`) has no I/O; `application/trajectory` is the only module permitted to write `TrajectoryChange`/`TrajectoryChangeSource`; `presentation/` only calls `application/`.

## UX & Interaction Patterns

- **Trajectory chart:** student's own historical "faixa habitual" band (never the class's), actual trajectory line, change points marked with icon+text (never color alone), 44×44px minimum touch target, rounded corners. Must have an equivalent text/table alternative (toggle or `sr-only` series), and `role="img"` with an accessible name summarizing the trend.
- **Change point** is a focusable control (`role="button"`, `tabindex="0"`), activates on click or Enter/Space, scrolls to the matching evidence card with visible focus.
- **Evidence card:** always expanded (never collapsed behind "see more"), badge restricted to a small icon/circle, label text always on `surface` — reused unmodified in the Epic 4 Follow-up screen.
- **Fator preocupante component:** visually discreet (background matches canvas, no colored badge, secondary text color), focusable/expandable header (`role="button"`, `aria-expanded`), closed by default, focus stays on the header after toggling.
- **Calm-state card:** shown when a student has no recent change ("dentro da faixa habitual") — same visual care as the change state, never a blank screen.
- **Read-only timeline:** static vertical list, no color coding by record type, no hover/selection states.
- **Recent-change line on Home:** student name + short description + icon marker, whole row clickable, opens Trajectory directly at the relevant evidence section.
- **Student search on Home:** visible label (not placeholder-only), filters by name or class across ~200 students, results as Tab-focusable list items, `aria-live="polite"` announcing result count — this is the only way to reach a "calm" student (no recent change, no active follow-up), since the recent-changes list itself only shows students with a detected change.

## Cross-Story Dependencies

- 3.1 (pure indicator calculation) is a prerequisite for 3.2 (convergence detection), which is a prerequisite for both 3.3 (Home) and 3.4 (Trajectory screen) — each of those consumes `TrajectoryChange`/"fator preocupante" output from 3.2.
- 3.3 and 3.4 both read from the same `GET /home` / `GET /students/{id}/trajectory` endpoints shaped by 3.1/3.2; they can be built in parallel once 3.2 exists.
- Depends on Epic 1's facts (attendance, grades, assignments, pedagogical observations) and Epic 1/Epic 2's base-repository invariants (`EVAL_DEMO` filter, `as_of()`), and benefits from Epic 2's `synthetic_profile` as ground truth for validating the convergence rule (without ever exposing that field).
- Epic 4 extends this epic's Home page with an "acompanhamentos em andamento" section and reuses the evidence card component; Epic 4's `FollowUpEvidence` is the only thing that ever freezes a `TrajectoryChange` produced here. Epic 5's ML feature engineering may reuse the pure indicator functions in `domain/trajectory.py` without reimplementing them.
