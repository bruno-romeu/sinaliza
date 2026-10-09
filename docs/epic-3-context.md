# Epic 3 Context: Trajetória e Detecção de Mudança Convergente

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic turns the raw facts captured in Epic 1 (and generated in Epic 2) into the system's central value proposition: an on-demand trajectory view that surfaces real, evidence-backed change instead of noisy single-metric alarms. It computes rolling-window indicators (attendance, grades, missing assignments) for a student, then detects a "relevant change" only when at least two independent signals — attendance, grades, assignments, or free-text pedagogical observation — converge in the same bimestre; an isolated signal never becomes a change, it surfaces only as an ephemeral "fator preocupante." The Home page then lists these detected changes so the coordenação knows, at a glance, which trajectories deserve review today. This epic fully realizes UJ-1 and is the direct prerequisite for Epic 4's follow-ups, which cite `TrajectoryChange` rows as their evidence.

## Stories

- Story 3.1: Cálculo de indicadores de trajetória em janela rolante
- Story 3.2: Detecção de mudança relevante por convergência de sinais
- Story 3.3: Página inicial com mudanças recentes
- Story 3.4: Trajetória do estudante — gráfico, evidências e fator preocupante

## Requirements & Constraints

- Trajectory indicators (`attendance_rate`, `attendance_trend`, `grade_average`, `grade_trend`, `missing_assignments_count`, `missing_assignment_delta`) are computed over a rolling window (`window_days`), not tied to `AcademicPeriod` — attendance and assignments are continuous signals; only grades stay period-scoped via `Grade.period_id`.
- A relevant change is never declared from a single indicator or formula. It requires convergence of at least two independent confirmed signals within the same bimestre (`period_id`). A lone confirmed signal is returned as a "fator preocupante" and never promoted on its own.
- A pedagogical observation counts as a full signal, weighted equally with attendance/grade/assignments — it can be one of the two converging signals, not a second-class corroborator.
- Every displayed change must reference the actual source record(s) that produced it (attendance records, grades, assignment submissions, or observations) — never an unexplained "AI flagged this."
- The interface must never show a student ranking, an evasion score, or any "high-risk students" KPI — and no feature anywhere (not just this screen) may implement direct student-to-student comparison. Y-axis labels use the real indicator name, never "score" or "risk."
- The trajectory chart's "habitual range" is computed against the student's own history only, never the classroom's.
- Changes on the Home page are ordered strictly by detection date, never by severity or score.
- Accessibility floor applies to all three new UI surfaces: chart has an equivalent text/table alternative (WCAG 1.1.1) and `role="img"` with an accessible name; change points are focusable controls (`role="button"`, `tabindex="0"`) activated by click or Enter/Space; concerning-factor headers are focusable/expandable, closed by default; full keyboard navigation in reading order (chart → evidence → concerning factor → timeline → action); student search has a visible label and `aria-live="polite"` result count.
- Microcopy must stay factual and reference the source record (e.g., "Mudança recente: queda de frequência e aumento de atividades pendentes — 3º bimestre"), never diagnostic/predictive language ("82% de chance de evasão").
- Required empty/loading/error states: no recent changes (explicit message, not a blank list), no search results (no auto-suggestions), loading skeleton (never a full-screen spinner), load error (factual message + retry), nonexistent student/trajectory (factual message + link back to Home, no dedicated 404 page).
- Response time budget is 5 seconds max per interaction; responsive across desktop and tablet.

## Technical Decisions

- `TrajectorySnapshot`/`TrajectoryChange` are always computed synchronously inside the HTTP request that reads them (`GET /students/{id}/trajectory`, `GET /home`) — never by a scheduled job. Each student's recomputation runs in its own transaction.
- `TrajectoryChange` upsert key is `(student_id, type, period_id)`, written via `INSERT ... ON CONFLICT ... DO UPDATE` — never a `SELECT` followed by a separate `INSERT`/`UPDATE`. `TrajectoryChangeSource` rows are written in the same transaction; no `TrajectoryChange` may exist without at least one source.
- `TrajectoryChange` is an immutable historical event: if a later recomputation of the same `period_id` no longer converges, the already-written row is left untouched, never deleted or reverted. As shipped in Story 3.2, the upsert is unconditionally `DO UPDATE` (no freeze-on-evidence check yet) because `FollowUp`/`FollowUpEvidence` don't exist until Epic 4 — the `DO NOTHING`-once-evidenced guard is a deferred Epic 4 change (tracked in `docs/deferred-work.md`), not something to build here.
- "Fator preocupante" has no table: it's a single unconverged signal, computed and returned only inside the HTTP response, with no stable id, never citable as evidence.
- `type` is a closed enum: `ATTENDANCE_DROP`, `GRADE_DROP`, `MISSING_ASSIGNMENTS_INCREASE`, `COMBINED_DETERIORATION`.
- Indicator calculation lives in `domain/trajectory.py` as a pure function, no I/O — testable with known synthetic cases (RNF-09). The signal/convergence pipeline is likewise pure domain logic (`domain/convergence.py`), with the four evaluators (attendance, grade, assignments, pedagogical observation) each returning `Signal(confirmed, kind, source_ids)`, combined by a `ConvergenceRule`.
- All reads for trajectory computation use exclusively the `EVAL_DEMO` dataset split and the `as_of()` reference date — never `TRAIN`, never data beyond "today."
- General repo conventions still apply: layered architecture (`domain/` pure, `application/` orchestrates via ports, `presentation/` calls only `application/`); PKs are UUID v4; migrations via Alembic only; error envelope `{ "error": { "code", "message" } }`; frontend types generated from OpenAPI, never hand-transcribed.
- RF-18 (Home: recent changes + active follow-ups) is split across epics — this epic delivers the recent-changes section in full; Epic 4 adds the active-follow-ups section to the same screen.

## UX & Interaction Patterns

- Trajectory chart: habitual band filled with `border`/`text-secondary` outline, trend line in `primary`, change point in `attention` always paired with an icon + text label (never color alone), `rounded.lg` corners, 44×44px minimum touch target.
- Evidence card: small icon/circle badge only, label text always on `surface` (never inside a saturated color block), always expanded (never collapsed behind "see more"); reused in Epic 4's follow-up screen with a "Ver na trajetória de [aluno]" link back.
- Concerning-factor component: background matches the page canvas (`bg`, not `surface`), no colored badge, `text-secondary` text; header is focusable and expandable (`role="button"`, `aria-expanded`), closed by default, focus stays on the header after toggling.
- Calm-state card: shown when a student is within their habitual range — a `success` icon + text label (e.g., "dentro da faixa habitual"), with the same visual investment as the change state, never a blank screen or error message.
- Recent-change row (Home): student name + short description + icon marker, whole row clickable, opens the Trajectory screen scrolled directly to that change's evidence.
- Timeline of records: static, read-only vertical list (date in `caption`, description in `body`, type tag in `caption`) — no sentiment icons, no color-by-type, no hover/selection.
- Single-column layout, max width 900px, no persistent side navigation, generous vertical rhythm between sections; same rule applies across Home and Trajectory as the rest of the product.

## Cross-Story Dependencies

- Story 3.1 is the foundation for 3.2 (signal evaluators reuse its indicator math/helpers) and indirectly for 3.3/3.4 (both read the trajectory/changes it and 3.2 produce).
- Story 3.2 depends on 3.1's period-scoped data access and produces the `TrajectoryChange`/`TrajectoryChangeSource` rows that 3.3 (Home list) and 3.4 (trajectory screen evidence/concerning-factor UI) render.
- Story 3.3 only delivers the "recent changes" half of RF-18; Epic 4 (Story 4.5) completes the same Home screen with the "active follow-ups" section — building 3.3's layout should leave room for that addition rather than treating the recent-changes list as the whole page.
- Story 3.4's evidence cards and "abrir acompanhamento" entry point are consumed directly by Epic 4 (Story 4.1 opens a follow-up from reviewed evidence here); the freeze-on-evidence upsert guard deferred out of Story 3.2 is implemented as an Epic 4 change once `FollowUpEvidence` exists.
- Epic 2's synthetic `synthetic_profile` labels (ground truth) are used only to validate this epic's convergence rule during development/testing — `synthetic_profile` itself must never appear in any endpoint or UI this epic builds.
