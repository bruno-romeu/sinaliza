---
title: 'Trajetória do estudante — gráfico, evidências e fator preocupante'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_commit: '8f38e5c0b8ddf4224e085d5dcc64e282f3cde56b'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `frontend/src/pages/EstudanteTrajetoria.tsx` is a content-free stub ("Trajetória em construção") created in Story 3.3; the coordenação has no way to see a student's indicator trajectory over time, the evidence behind a detected change, or an unconverged "fator preocupante."

**Approach:** Add `GET /students/{id}/trajectory/detail`, which reuses `GetStudentTrajectoryService`'s current-period computation and adds: a per-bimestre indicator series (last up to 4 `AcademicPeriod`s) for the chart, the student's own habitual range for the charted indicator, resolved evidence records for any `trajectory_change`, and a recent pedagogical-observations timeline. Replace the stub with a real page: SVG chart + text-table alternative, evidence card, expandable concerning-factor, calm-state card, and observations timeline.

## Boundaries & Constraints

**Always:**
- The charted indicator is chosen deterministically from the trajectory_change's `type` (`ATTENDANCE_DROP`→`attendance_rate`, `GRADE_DROP`→`grade_average`, `MISSING_ASSIGNMENTS_INCREASE`→`missing_assignments_count`, `COMBINED_DETERIORATION`→`attendance_rate`); absent a change, default `attendance_rate` (decision — documented here, not an open question).
- Habitual range = min/max of the student's own historical values for the charted indicator across the computed series (own history only, per epic constraint); `null` when fewer than 2 non-null points exist — UI then renders the line without a band, never a fabricated range.
- Evidence items are resolved from real `TrajectoryChangeSource` rows (batch `get_by_ids` per `source_type`) — never a free-text-only "AI flagged this."
- Reuses `GetStudentTrajectoryService.execute()` internally for the current snapshot/change/concerning_factor; does not duplicate or fork its convergence logic.
- Chart: `role="img"` + accessible name, text-table alternative (WCAG 1.1.1), change point is a focusable `role="button"` control; concerning-factor header is `role="button" aria-expanded`, closed by default; calm-state card shown with equal visual weight when no change exists.
- Loading = skeleton (never full-screen spinner); load error = factual message + retry; nonexistent student = factual message + link back to Home (no dedicated 404 page).
- Existing `GET /students/{id}/trajectory` (`TrajectoryOut`) response contract is untouched — this is a new, additive endpoint.

**Never:**
- Never add a ranking/evasion-score/"high-risk" KPI, never color-only signal, never a second-class pedagogical-observation evidence source.
- Never change `TrajectoryChange`/`TrajectoryChangeSource` persistence semantics (still request-scoped synchronous upsert from Story 3.2).
- Never implement the "Abrir acompanhamento" button's actual follow-up action — Epic 4 scope; render the button disabled/absent for now (out of boundaries here).
- Never add a charting dependency — hand-rolled inline SVG, matching the UX mockup and the project's zero-chart-lib convention.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Change detected | Student has a current-period `trajectory_change` with sources | Chart shows band+line+focusable change point; evidence card lists resolved source descriptions; concerning_factor omitted | No error expected |
| Calm state | No current change, no concerning signal | Chart shows line only (band if ≥2 history points); calm-state card replaces evidence/concerning sections | No error expected |
| Concerning factor only | Exactly one confirmed signal | Concerning-factor section rendered, closed by default, expandable, no evidence list (no stable id) | No error expected |
| &lt;2 history points | Student enrolled this bimestre only | `habitual_range: null` | UI renders trend line without band, no crash |
| Unknown/TRAIN student | Invalid or non-`EVAL_DEMO` `student_id` | 404 `student_not_found` | UI shows factual message + link back to Home |
| Load failure | 5xx/network error | — | UI shows "Não foi possível carregar os dados agora." + retry |

</frozen-after-approval>

## Code Map

- `backend/app/application/trajectory/get_student_trajectory_detail.py` -- NEW: `GetStudentTrajectoryDetailService.execute(student_id, window_days)`; calls `GetStudentTrajectoryService.execute()` for current snapshot, loops `AcademicPeriodRepositoryPort.list_all()` (last ≤4 periods by `start_date`) calling `compute_trajectory_indicators` per period end date (mirrors `get_student_trajectory.py` period/window logic), resolves evidence, lists recent observations (`PedagogicalObservationRepositoryPort.list_by_student_in_range`, 365-day window, cap 10, desc by date).
- `backend/app/application/trajectory/ports.py` -- EXTEND: add `get_by_ids` to `AttendanceRepositoryPort`, `GradeRepositoryPort`, `AssignmentSubmissionRepositoryPort`, `PedagogicalObservationRepositoryPort`; add `TrajectoryChangeSourceRepositoryPort.list_by_change(change_id) -> list[TrajectoryChangeSource]`.
- `backend/app/infrastructure/repositories/sqlalchemy_{attendance,grade,assignment_submission,pedagogical_observation}_repository.py` -- EXTEND: add `get_by_ids(ids: list[UUID])`.
- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- EXTEND: add `list_sources_by_change(change_id) -> list[TrajectoryChangeSource]` (`select(TrajectoryChangeSourceModel).where(trajectory_change_id == ...)`).
- `backend/app/presentation/schemas/trajectory.py` -- EXTEND: add `TrajectorySeriesPointOut(period_id, period_label, value: Decimal|None)`, `HabitualRangeOut(low, high)`, `EvidenceItemOut(source_type: Literal[...], description, date)`, `ObservationItemOut(date, text)`, `TrajectoryDetailOut(chart_indicator: Literal["attendance_rate","grade_average","missing_assignments_count"], series: list[...], habitual_range: HabitualRangeOut|None, trajectory_change: TrajectoryChangeOut|None, evidence: list[EvidenceItemOut], concerning_factor: ConcerningFactorOut|None, observations: list[ObservationItemOut])`.
- `backend/app/presentation/trajectory/router.py` -- EXTEND: `GET /students/{student_id}/trajectory/detail`, same auth/404 pattern as existing route.
- `backend/app/composition.py` -- EXTEND: `get_get_student_trajectory_detail_service` factory.
- `backend/tests/test_trajectory_detail.py` -- NEW: seed periods/attendance/grades/assignments/observations/trajectory_change+sources; cover I/O Matrix.
- `frontend/src/api/client.ts` -- EXTEND: `getStudentTrajectoryDetail(token, studentId)` wrapper, types from regenerated `schema.d.ts`.
- `frontend/src/pages/EstudanteTrajetoria.tsx` -- REPLACE stub: `useParams<{studentId}>`, `ignore`-flag fetch (Home.tsx pattern), skeleton/error/404 states, SVG chart (habitual band, trend line, focusable change-point button) + visually-hidden text-table alternative, evidence card, expandable concerning-factor (`useState` open, closed by default), calm-state card, observations timeline, disabled "Abrir acompanhamento" button.
- `frontend/src/pages/EstudanteTrajetoria.test.tsx` -- NEW: Vitest/RTL, mock `/api/students/:id/trajectory/detail`, cover change/calm/concerning/404/error states + concerning-factor expand toggle.

## Tasks & Acceptance

**Execution:**
- [ ] `application/trajectory/ports.py` -- add `get_by_ids`/`list_by_change` port methods -- feeds evidence resolution
- [ ] repositories (attendance/grade/assignment_submission/pedagogical_observation/trajectory_change) -- implement new methods -- backs the ports
- [ ] `application/trajectory/get_student_trajectory_detail.py` -- new service -- orchestrates series+evidence+observations
- [ ] `presentation/schemas/trajectory.py`, `presentation/trajectory/router.py`, `composition.py` -- wire new endpoint -- RF-19/RF-20
- [ ] `backend/tests/test_trajectory_detail.py` -- I/O Matrix coverage -- RNF-09
- [ ] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- typed wrapper -- never hand-transcribed
- [ ] `frontend/src/pages/EstudanteTrajetoria.tsx` -- real page per Code Map -- RF-19/RF-20, UX-DR accessibility floor
- [ ] `frontend/src/pages/EstudanteTrajetoria.test.tsx` -- state/accessibility coverage -- UX-DR

**Acceptance Criteria:**
- Given a student with a detected change, when the page loads, then the chart shows the habitual band, trend line, and a focusable change-point control, and an equivalent text table is present.
- Given a detected change, when the evidence card renders, then every listed item traces to a real source record (attendance/grade/assignment/observation), never free text alone.
- Given exactly one confirmed signal, when the page loads, then the concerning-factor header renders closed, is keyboard-expandable, and shows no evidence list.
- Given a student within their habitual range, when the page loads, then a calm-state card (equal visual weight) replaces evidence/concerning sections.
- Given fewer than 2 historical data points, when the chart renders, then no band is drawn and nothing errors.
- Given an unknown or TRAIN-split student id, when the page loads, then it shows a factual message with a link back to Home.
- Given a `GET .../trajectory/detail` failure, when it occurs, then the UI shows a factual error message with retry.
- Given keyboard-only navigation, when used on this page, then chart → evidence → concerning factor → timeline → action are reachable in that order with visible focus.

## Implementation Notes

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 18 entries after grouping overlaps by shared root cause.

1. [verification-gap] `_CHART_INDICATOR_BY_CHANGE_TYPE` has no test for the `COMBINED_DETERIORATION` → `attendance_rate` mapping (`get_student_trajectory_detail.py:70-75`); grep confirms `COMBINED_DETERIORATION` never appears in `test_trajectory_detail.py`. **low** (real, narrow gap on a real branch). → **patch**: add `test_detail_chart_indicator_follows_combined_deterioration_change_type`.
2. [verification-gap] + [intent-alignment] The WCAG 1.1.1 text-table alternative (`EstudanteTrajetoria.tsx:227-243`) is never queried/asserted by any frontend test — could be deleted or broken (e.g. `srOnlyStyle` → `display:none`) with all 5 existing tests still green. **low** (real, the AC explicitly promises this). → **patch**: assert `getByRole('table')` + a representative row in the "change detected" test.
3. [blind-hunter] Change-point hit-target button is hardcoded `width:24,height:24` instead of `var(--min-hit-target)` used by every other interactive control in the same file, deviating from the epic's own "44×44px minimum touch target" UX constraint for the change point. **medium** (explicit, stated accessibility constraint; trivial fix). → **patch**: use `var(--min-hit-target)` for both dimensions.
4. [blind-hunter] `docs/sprint-status.yaml`'s `last_updated` dropped the `HH:MM` component present in the file's own established format. **low** (cosmetic, trivial). → **patch**: restore the `MM-DD-YYYY HH:MM` format.
5. [blind-hunter] Disabled "Abrir acompanhamento" button has no affordance explaining why it's inert, which could read as broken to a coordenação user. **low** (real UX nit, trivial fix). → **patch**: add a `title` attribute noting the feature lands in a future story.
6. [blind-hunter] `window_days` query override on the new `/trajectory/detail` route is accepted but has no dedicated test, unlike its sibling `/trajectory` route. **low** (real but the route is a copy of an already-reviewed, already-tested pattern; narrow). → **patch**: add one override test mirroring `test_trajectory.py`'s existing coverage.
7. [edge-case-hunter] + [blind-hunter] `_chart_indicator_for` indexes `_CHART_INDICATOR_BY_CHANGE_TYPE[trajectory_change.type]` without a default, risking `KeyError` if a change type isn't in the map. Verified false: `TrajectoryChangeType` is a closed 4-value enum and the dict defines exactly those 4 keys (`get_student_trajectory_detail.py:70-75`) — no code path can construct a 5th value. → **reject** (false; closed enum, dict is exhaustive).
8. [edge-case-hunter] + [intent-alignment] `recent_periods` (last ≤4 `AcademicPeriod`s by `start_date`) could exclude the period a `trajectory_change` belongs to, leaving the change point un-plottable and the accessible name text dangling. Verified false: the system seeds exactly 4 `AcademicPeriod`s for the single academic year this MVP covers (`seed_dev_fixtures.py:38-43`, "um ano letivo" per AGENTS.md) — "last ≤4" is always literally all periods that exist, so the change's period can never be excluded today. Same unreachable-given-invariant class already accepted in Story 3.2/3.3's own triage logs. → **reject** (false; unreachable given the current single-year data invariant).
9. [edge-case-hunter] `get_by_ids` (attendance/grade/submission/observation) applies `filter_as_of`, so a cited source dated after a rolled-back demo `as_of()` would silently vanish from the evidence list. Verified low: this mirrors the exact same defense-in-depth convention already used, untested, by every other repository read in the codebase (documented in `sqlalchemy_attendance_repository.py`'s own docstring); only reachable by manually rolling the demo date backward after a change was already detected forward, not a path any shipped UI exercises. → **reject** (low; consistent with established, already-accepted codebase convention, no new risk introduced).
10. [edge-case-hunter] Frontend effect's `if (!token || !studentId) return` could leave the page stuck on the loading skeleton forever. Verified false: this is the identical idiom already shipped and accepted in `Home.tsx`'s own effect (`if (!token) return`); `studentId` is always populated by the matched `/estudantes/:studentId` route. → **reject** (false; same accepted pattern as Story 3.3, not a new regression).
11. [blind-hunter] `CHANGE_TYPE_LABEL`/`CHART_INDICATOR_LABEL` frontend `Record` maps could render `undefined` for an unmapped key. Verified false: both are typed as `Record<ChangeType, string>`/`Record<ChartIndicator, string>` over closed union types mirroring the backend's closed `Literal`s — `tsc --noEmit` enforces exhaustiveness at compile time; this is on the "compiler-enforced, do not report" exclusion list. → **reject** (false; compiler-enforced exhaustiveness).
12. [blind-hunter] + [intent-alignment] No test asserts the keyboard tab order / focus-visibility acceptance criterion (chart → evidence → concerning factor → timeline → action). Verified low: every interactive element is a native unmodified `<button>`/`<a>` rendered in that literal JSX/DOM order with no suppressed outline or negative `tabIndex` anywhere in the diff — functionally correct by construction. **low** (same reasoning already accepted in Story 3.3's triage, finding #14; a real jsdom tab-order test is nontrivial for the marginal benefit). → **reject** (low; functionally satisfied, fix nontrivial for marginal benefit).
13. [blind-hunter] No test for the loading-skeleton state. **low** (the skeleton is static, `aria-hidden` placeholder markup with no branching logic to regress silently). → **reject** (low; no meaningful defect surface, fix adds test weight disproportionate to the risk).
14. [blind-hunter] `formatIndicatorValue`'s `grade_average`/`missing_assignments_count` branches and 3 of 4 `CHANGE_TYPE_LABEL` entries are untested by the frontend suite. **low** (simple, pure one-line formatting/lookup code; the 4 type mappings are already fully covered on the backend). → **reject** (low; marginal benefit, backend already covers the real decision logic).
15. [blind-hunter] Evidence items are grouped by source type then sorted by date within each group, not pure chronological order, with no Design Notes callout. Verified false: nothing in the frozen Boundaries or the epic's "Evidence card" UX pattern mandates chronological-only ordering; the implemented order is deterministic (mirrors `domain/convergence.py`'s own established ordering convention) — two defensible readings exist and nothing frozen picks one, same class already accepted in Story 3.3's triage (finding #11). → **reject** (false; not contradicted by any frozen requirement).
16. [blind-hunter] `srOnlyStyle` uses the older `clip: rect(0,0,0,0)` technique instead of `clip-path: inset(50%)`. **low** (cosmetic; both work correctly in this app's target browsers). → **reject** (low; no demonstrated defect, cosmetic only).
17. [blind-hunter] + [verification-gap "Other findings"] `get_student_trajectory_detail.py`'s series-window math and `router.py`'s `TrajectoryChangeOut`/`ConcerningFactorOut` construction each duplicate logic already present in the sibling `/trajectory` service/handler, rather than sharing a helper. **low** (real duplication, developer-maintenance risk only — the two handlers could drift when a field is added — but no demonstrated user-facing harm, and extracting a shared helper would touch the already-shipped `/trajectory` route, which is out of this story's frozen boundaries). → **reject** (low; cosmetic/maintenance duplication, fix disproportionate and touches already-shipped code).
18. [intent-alignment] "Calm-state card shown with equal visual weight" — verified false: the calm-state section and the evidence section both render via the identical shared `cardStyle` constant (`EstudanteTrajetoria.tsx`), so visual weight is equal by construction. → **reject** (false; disproved by shared styling constant).

**Pass 1 totals:** medium 1 (patched), low 5 (patched), low 6 (rejected), false 6 (rejected) — 18 entries, 0 high.

## Design Notes

Chart-indicator selection and habitual-range math (see Boundaries) are the two non-obvious decisions; both made here per epic constraints rather than left open, since the epic context gives enough to decide deterministically (indicator tied to the actual detected signal; range from the student's own series, never the classroom's).

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests + new `test_trajectory_detail.py` pass
- `cd frontend && npm run generate:api-types && npm test` -- expected: types regenerate cleanly, all tests + new `EstudanteTrajetoria.test.tsx` pass
- `git status --short` -- expected: only Code Map files + this spec changed
