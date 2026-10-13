---
title: 'Página inicial com mudanças recentes'
type: 'feature'
created: '2026-10-08'
status: 'done'
baseline_commit: 'f17da14627d1519962e149fa6cfff72b5daf69c8'
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

**Problem:** The Home page is a placeholder (`frontend/src/pages/Home.tsx`); the coordenação pedagógica has no way to see, at a glance, which students have a recently detected trajectory change, nor to search for a specific student.

**Approach:** Add a `GET /home` endpoint that reads existing `TrajectoryChange` rows (no recomputation) ordered by `detected_at` desc, plus a `GET /home/search` endpoint for name/turma search; replace the Home placeholder with a recent-changes list, a search box, and the required loading/empty/error states.

## Boundaries & Constraints

**Always:**
- `GET /home` only reads already-committed `TrajectoryChangeModel` rows (`list_recent`); it never iterates students or triggers `GetStudentTrajectoryService` recomputation — that stays request-scoped to the per-student trajectory endpoint (Epic 3 Technical Decisions).
- `list_recent` caps at the 20 most recent rows (decision: no pagination, "glance at today" framing) — never unbounded, never a second page.
- Recent-changes list is ordered strictly by `detected_at` descending — never by severity/score/type.
- Search queries `StudentModel.name` and the joined `ClassroomModel.name` with case-insensitive (`ILIKE`) matching, scoped to `filter_eval_demo_students` (AD-11), same as every other student-facing read.
- No student ranking, evasion score, or "high-risk" KPI anywhere on the page.
- Row/description text is factual, references the change `type`/`description` as-is — never diagnostic or predictive language.
- Full keyboard operability: list rows and search field reachable/operable without a mouse, with visible focus.
- A recent-change row and a search result both link to `/estudantes/:studentId`, a new stub route rendering a plain "Trajetória em construção" placeholder page (decision: Story 3.4 doesn't exist yet; this stub is the landing target until 3.4 replaces its content) — the stub is not the Trajetória do Estudante feature, just a routable placeholder.

**Never:**
- Never build the real Trajetória-do-estudante detail page (chart, evidence, concerning-factor UI) — that is Story 3.4; the stub route here is content-free beyond a placeholder message.
- Never hand-transcribe frontend API types — `schema.d.ts` is regenerated from the new OpenAPI paths.
- Never paginate/infinite-scroll the recent-changes list — single page, capped at 20 rows.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Recent changes exist | ≥1 `TrajectoryChange` row in DB | `GET /home` returns rows ordered by `detected_at` desc; UI renders one row per change (student name, description, type icon) | No error expected |
| No recent changes | 0 `TrajectoryChange` rows | `GET /home` returns empty list; UI shows explicit "nenhuma mudança a revisar hoje" message, never a blank list | No error expected |
| Search matches | Query matches a student name or classroom name | `GET /home/search?q=` returns matching students; UI shows focusable list + `aria-live="polite"` count | No error expected |
| Search no match | Query matches nothing | Empty results array | UI shows "Nenhum estudante encontrado com esse nome/turma.", no suggestions |
| Load failure | `GET /home` 5xx/network error | — | UI shows "Não foi possível carregar os dados agora." with a retry action |

</frozen-after-approval>

## Code Map

- `backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- EXTEND: add `list_recent(limit: int) -> list[TrajectoryChange]`, mirroring the existing `upsert` mapping (lines 74-81) — `select(TrajectoryChangeModel).order_by(detected_at.desc()).limit(limit)`.
- `backend/app/infrastructure/repositories/sqlalchemy_student_repository.py` -- EXTEND: add `search(query: str) -> list[Student]` — `StudentModel` joined to `EnrollmentModel`/`ClassroomModel`, `ILIKE` on name/classroom name, wrapped in `filter_eval_demo_students` (mirrors `list_enrolled`, lines 26-38).
- `backend/app/application/home/` -- NEW package (`__init__.py`, `ports.py`, `errors.py`, `get_home.py`, `search_students.py`), one narrow `Protocol` port per method actually used, following `application/trajectory`'s shape (ports.py:7-9 convention — no widening of existing ports).
- `backend/app/presentation/schemas/home.py` -- NEW: `RecentChangeOut(student_id, student_name, type: Literal[...], description, detected_at)`, `HomeOut(recent_changes: list[RecentChangeOut])`, `StudentSearchResultOut(id, name, classroom_name)`, `StudentSearchOut(results: list[...], count: int)` — `Literal` for `type`, matching `presentation/schemas/trajectory.py`'s convention.
- `backend/app/presentation/home/router.py` -- NEW: `router = APIRouter(dependencies=[Depends(get_current_user)])`, `GET /home`, `GET /home/search?q=`, same `AppError` envelope pattern as `presentation/trajectory/router.py`.
- `backend/app/composition.py:138-150` -- EXTEND: add `get_get_home_service`/`get_search_students_service` factories mirroring `get_get_student_trajectory_service`.
- `backend/app/main.py:11,22` -- EXTEND: `app.include_router(home_router)`.
- `frontend/src/api/client.ts` -- EXTEND: add `getHome`/`searchStudents` wrappers using the shared `request<T>()` helper (lines 95-132), types from regenerated `schema.d.ts`.
- `frontend/src/pages/Home.tsx` -- REPLACE placeholder with: `<Header/>` (unchanged), recent-changes list, search input, loading/empty/error states — reuse the stale-response guard (`ignore` flag in `useEffect` cleanup) and `role="status" aria-live="polite"` idiom from `frontend/src/pages/Lancamento/Atividades.tsx` (lines 147,171-173, 382-396).
- `frontend/src/App.tsx` -- EXTEND: add `/estudantes/:studentId` route (wrapped in `<ProtectedRoute>`, mirrors existing route entries lines 17-56) rendering a new stub `EstudanteTrajetoria.tsx` placeholder page.
- `frontend/src/pages/EstudanteTrajetoria.tsx` -- NEW: minimal page with `<Header/>` and a "Trajetória em construção" message — placeholder only, replaced by Story 3.4.
- `backend/tests/test_home.py` -- NEW: `TestClient` + `db_session`, seed multiple `TrajectoryChangeModel` rows directly (mirrors `test_trajectory.py` seeding, lines 77-116), cover the I/O Matrix.
- `frontend/src/pages/Home.test.tsx` -- NEW: Vitest + Testing Library, mock `/api/home` and `/api/home/search` by exact URL (mirrors `Atividades.test.tsx` lines 16-60).

## Tasks & Acceptance

**Execution:**
- [ ] `infrastructure/repositories/sqlalchemy_trajectory_change_repository.py` -- add `list_recent` -- feeds Home's recent-changes read
- [ ] `infrastructure/repositories/sqlalchemy_student_repository.py` -- add `search` -- feeds Home's student search
- [ ] `application/home/*` -- `GetHomeService`, `SearchStudentsService` + ports/errors -- layered orchestration per RF-18
- [ ] `presentation/schemas/home.py` -- response schemas -- surfaces recent changes + search results
- [ ] `presentation/home/router.py` -- `GET /home`, `GET /home/search` -- RF-18, RF-21
- [ ] `composition.py`, `main.py` -- wire new services/router -- registers dependencies
- [ ] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- typed calls -- never hand-transcribed
- [ ] `frontend/src/pages/Home.tsx` -- real content: list (linking to `/estudantes/:studentId`), search, loading/empty/error states -- RF-18, RF-21, UX-DR10/12/18/20/21
- [ ] `frontend/src/App.tsx` + `frontend/src/pages/EstudanteTrajetoria.tsx` -- stub route + placeholder page -- landing target until Story 3.4
- [ ] `backend/tests/test_home.py` -- I/O Matrix coverage -- RNF-09
- [ ] `frontend/src/pages/Home.test.tsx` -- list/search/empty/error rendering -- UX-DR12/18

**Acceptance Criteria:**
- Given ≥1 `TrajectoryChange` row, when the coordenação opens Home, then she sees one row per change (student name, short description, icon marker) ordered by `detected_at` desc.
- Given the Home UI, when any element renders, then no ranking/score/"high-risk" KPI appears anywhere.
- Given zero `TrajectoryChange` rows, when Home loads, then it shows an explicit "no changes to review today" message, never an empty generic list.
- Given a name/turma typed in search, when results return, then they render as a Tab-focusable list with `aria-live="polite"` announcing the count.
- Given a search with no matches, when executed, then it shows "Nenhum estudante encontrado com esse nome/turma." with no auto-suggestions.
- Given Home while data is loading, when rendered, then it shows a content skeleton, never a full-screen spinner.
- Given a `GET /home` failure, when it occurs, then the UI shows a factual error message with a retry action.
- Given keyboard-only navigation, when used on Home, then every interactive element (rows, search field) is reachable and operable with visible focus.
- Given a recent-change row or search result, when clicked, then it navigates to `/estudantes/:studentId`, which renders the "Trajetória em construção" stub placeholder (real evidence-scrolled detail view is Story 3.4).
- Given the `GET /home` recent-changes query, when more than 20 `TrajectoryChange` rows exist, then only the 20 most recent are returned.

### Review Findings

**Code review** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 1 decision-needed, 5 patch, 0 defer, 11 rejected.

- [x] [Review][Decision] `GET /home/search` has no cap on result count — the `ILIKE` match in `SqlAlchemyStudentRepository.search()` (`backend/app/infrastructure/repositories/sqlalchemy_student_repository.py:61-85`) has no `.limit()`, so a short query (e.g. one letter) can return the entire matching `EVAL_DEMO` roster unbounded into a single unstyled, unpaginated list in `Home.tsx`. The frozen spec caps `list_recent` at 20 but says nothing about a cap for search, and the right fix (a specific limit value, and whether to surface a "showing N of M" affordance) is a product call, not a mechanical one. **Resolved:** decision made — capped at 20, same as `list_recent`, no "showing N of M" affordance. `StudentSearchRepositoryPort.search()`/`SqlAlchemyStudentRepository.search()` now take a `limit` parameter; `SearchStudentsService` passes `SEARCH_RESULTS_LIMIT = 20`. Covered by `test_home_search_caps_results_at_twenty`.

- [x] [Review][Patch] Search query is not trimmed before matching — `SearchStudentsService.execute()` passes the raw `query` (not `query.strip()`) to the repository (`backend/app/application/home/search_students.py:26-29`), and the frontend also sends the untrimmed value (`frontend/src/pages/Home.tsx:94`, `queryAtStart = query`). A trailing/leading space (e.g. `"Ana "`) changes the `ILIKE` pattern and can fail to match a student literally named `"Ana"`. **Resolved:** `SearchStudentsService.execute()` now trims the query before the blank check and before passing it to the repository; `Home.tsx`'s `queryAtStart` (and the `queryRef` staleness guard) now also trim.
- [x] [Review][Patch] No test covers `list_recent`'s `TrajectoryModel.id.desc()` tiebreaker when two rows share an identical `detected_at` — the exact nondeterminism this line exists to fix (per this file's own Pass 1 log, finding #1) has no regression coverage. [backend/tests/test_home.py, backend/app/infrastructure/repositories/sqlalchemy_trajectory_change_repository.py:266-267] **Resolved:** added `test_home_breaks_detected_at_tie_by_id_desc`.
- [x] [Review][Patch] No test covers `GET /home/search`'s blank/whitespace-only `q` short-circuit at the HTTP boundary — only the frontend's own never-calls-blank guard is exercised indirectly; the backend guard itself (added per Pass 1 finding #3) is untested. [backend/tests/test_home.py, backend/app/application/home/search_students.py:27-28] **Resolved:** added `test_home_search_blank_q_returns_empty_results` and `test_home_search_whitespace_only_q_returns_empty_results`.
- [x] [Review][Patch] No test covers the `%`/`_` escaping added to the search `ILIKE` pattern (Pass 1 finding #2) — a query containing a literal `%` or `_` has no regression test guarding the fix. [backend/tests/test_home.py, backend/app/infrastructure/repositories/sqlalchemy_student_repository.py:66-67] **Resolved:** added `test_home_search_escapes_percent_wildcard` and `test_home_search_escapes_underscore_wildcard`.
- [x] [Review][Patch] `formatDetectedAt` renders the UTC-midnight `detected_at` (`datetime.combine(as_of_date, time.min, tzinfo=timezone.utc)`) via `toLocaleDateString('pt-BR')`, which converts to the browser's *local* timezone before formatting. For a Brazil-based browser (UTC-3), midnight UTC falls on the previous local day, so a change detected "today" can display as yesterday's date — undermining the spec's own "glance at today" framing. [frontend/src/pages/Home.tsx:24-28] **Resolved:** `formatDetectedAt` now calls `toLocaleDateString('pt-BR', { timeZone: 'UTC' })` so the UTC calendar date is read directly instead of being converted to the browser's local timezone first.

**Rejected:**
- [false] Inner join in `search()` could exclude an unenrolled student or duplicate a multi-classroom student — refuted: `backend/app/synthetic/population.py` (the only production write path that creates `StudentModel`/`EnrollmentModel` rows) appends exactly one `GeneratedEnrollment` per generated student by construction ("Every student belongs to exactly one classroom"); no other path creates students in production. Matches this file's own Pass 1 finding #10.
- [false] Typing into search hides the recent-changes list (`showingSearch` ternary) — refuted: a defensible, undictated UX choice; neither the frozen Intent/Boundaries nor the I/O Matrix requires concurrent visibility of both views. Matches Pass 1 finding #11.
- [low] `GetHomeService.execute()` makes up to 20 sequential `get_by_id` calls (N+1) rather than a batched lookup — not worth fixing: bounded at `RECENT_CHANGES_LIMIT = 20`, well within the epic's 5s/request budget; batching adds complexity disproportionate to the benefit. Matches Pass 1 finding #13.
- [low] No test for `search()` returning more than one match / verifying sort order — not worth fixing: behavior is already correct by construction (`order_by(StudentModel.name)`); a dedicated test is low-value coverage relative to its cost, mirroring this file's own precedent (Pass 1 findings #14/#15).
- [false] Empty `application/home/errors.py` module called out as dead weight — refuted: deliberately mirrors `application/trajectory`'s established port/errors package shape; a convention, not an oversight.
- [false] `EstudanteTrajetoria.tsx` ignores the `:studentId` route param — refuted: the frozen spec explicitly requires the stub be "content-free beyond a placeholder message"; echoing the id would overstep the intentionally minimal scope.
- [false] `docs/epic-3-context.md` rewritten inside a story-scoped diff — refuted: `_bmad`'s `bmad-build` workflow has a mandatory `compile-epic-context` step (confirmed present on disk) that regenerates this file; sanctioned tooling output, not ad hoc scope creep. Matches Pass 1 finding #7.
- [low] No dedicated keyboard/focus-order test — not worth fixing: every interactive element is a native, unmodified `<Link>`/`<input>`/`<button>` with no suppressed outline or custom `tabIndex`, functionally compliant by construction. Matches Pass 1 finding #14.
- [false] `CHANGE_TYPE_LABELS` adding a derived type→label mapping diverges from "description as-is" — refuted: this file's own Design Notes section explicitly sanctions "map `TrajectoryChangeType` to a small icon + text label."
- [false] `GetHomeService.execute()` silently skipping an unresolved `student_id` — refuted: a `TrajectoryChange` can only ever be written for a student that already passed the same `EVAL_DEMO`-filtered `get_by_id` lookup (`get_student_trajectory.py:107-108` raises `StudentNotFoundError` before any write), so the skip branch is unreachable by any current write path. Matches Pass 1 finding #5.
- [false/non-issue] `Home.tsx`'s extra `searchError` state beyond the frozen I/O Matrix's one load-failure case — additive, not a violation; a dedicated test for it already exists (`Home.test.tsx`, "shows a factual error message when the search request fails"), closing Pass 1 finding #4.

## Implementation Notes

## Spec Change Log

## Review Triage Log

**Pass 1** (iteration 0; lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 15 entries after grouping overlaps by shared root cause.

1. [blind-hunter] + [edge-case-hunter] `SqlAlchemyTrajectoryChangeRepository.list_recent` orders only by `detected_at desc` with no secondary key, and `detected_at` is derived deterministically from the shared `as_of()` date (`datetime.combine(as_of_date, time.min)`, Story 3.2) — so many/most `TrajectoryChange` rows computed under the same demo "today" share an identical timestamp. At the 20-row cap boundary, which tied rows land inside vs. outside is undefined by SQL without a tiebreaker, so the Home list can show a different subset of "the 20 most recent" across requests. **medium** (real nondeterminism visible to end users; plausible in this demo's actual data shape, not a rare edge case). → **patch**: add a deterministic secondary `ORDER BY` key (e.g. `TrajectoryChangeModel.id.desc()`).
2. [blind-hunter] + [edge-case-hunter] `SqlAlchemyStudentRepository.search()`'s `ILIKE` pattern (`f"%{query}%"`) doesn't escape literal `%`/`_` in the user's query, so those characters behave as SQL wildcards instead of literal matches. **low** (real, narrow — Portuguese student/turma names rarely contain these characters — trivial fix). → **patch**: escape `%` and `_` before building the pattern.
3. [edge-case-hunter] `GET /home/search` has no cap and a blank/missing `q` matches `%%`, returning every `EVAL_DEMO` student unbounded; the shipped UI never calls search with a blank query, but the endpoint itself has no equivalent guard. **low** (not reachable from the shipped UI; small blast radius at ~200 students; trivial fix). → **patch**: short-circuit a blank/whitespace-only `q` to an empty result, mirroring the frontend's own guard.
4. [intent-alignment] The spec's I/O Matrix only specifies a load-failure case for `GET /home`; `Home.tsx` also renders a `searchError` state for a failed `GET /home/search`, but no test exercises it. **low** (real coverage gap on real, shipped behavior; trivial to add, mirrors the existing load-error test). → **patch**: add a test asserting the search-failure message renders on a `GET /home/search` failure.
5. [blind-hunter] + [verification-gap] + [edge-case-hunter] `GetHomeService.execute()` silently skips (`continue`) any `TrajectoryChange` whose `student_id` doesn't resolve via the `EVAL_DEMO`-filtered `get_by_id`, untested, and could under-deliver the 20-row cap. Verified false: `GetStudentTrajectoryService.execute()` (`application/trajectory/get_student_trajectory.py:107-108`) raises `StudentNotFoundError` (404) from the same `EVAL_DEMO`-filtered `get_by_id` *before* any `TrajectoryChange` is ever computed or written for a given `student_id` — so a `TrajectoryChange` row pointing at a non-`EVAL_DEMO` (or otherwise unresolvable) student can never exist today. This mirrors Story 3.2's own already-accepted "unreachable from any current caller" rejection class (Pass 1, finding #8). → **reject** (false; unreachable from any current write path).
6. [blind-hunter] + [intent-alignment] Diff shows `frontend/src/api/client.ts` consuming `paths['/home']`/`paths['/home/search']` from `schema.d.ts`, but the diff contains no change to `schema.d.ts`/`openapi.json` — no evidence the required `npm run generate:api-types` regeneration happened. Verified false: both files are gitignored (`.gitignore:16,21`) by long-standing project convention, so a real regeneration correctly produces no diff lines. Confirmed directly: `frontend/src/api/schema.d.ts` on disk contains `"/home"`/`"/home/search"` path entries and `npx tsc --noEmit` runs clean against the new `client.ts` usage. → **reject** (false; regeneration verifiably happened, diff-invisibility is by design).
7. [blind-hunter] `docs/epic-3-context.md` is substantially rewritten inside this diff, bundling epic-level documentation changes into a story-level patch. Verified false: this file was regenerated by this same `bmad-build` run's mandatory Step 1 `compile-epic-context` procedure (the cached version was stale — postdated by spec-3-1/3-2 — so regeneration was required before planning could proceed), not introduced ad hoc by the implementer. Any session prepping Story 3.3 would produce the identical regeneration regardless of the feature code. → **reject** (false; sanctioned, required workflow step, not scope creep).
8. [blind-hunter] `frontend/src/pages/Home.tsx`'s recent-changes list key (`` `${change.student_id}-${index}` ``) mixes the array index into the React key, called out as an unnecessary anti-pattern since `student_id` is "already effectively unique." Verified false: a single student can have more than one independent `TrajectoryChange` row (distinct `type`/`period_id`) simultaneously present in the same capped top-20 list (`UNIQUE(student_id, type, period_id)`, not `UNIQUE(student_id)`) — so `student_id` alone is *not* guaranteed unique here; qualifying with the index is a correct, deliberate disambiguation, not an oversight. → **reject** (false).
9. [blind-hunter] `RecentChangeOut.type` hardcodes the four enum values as a `Literal[...]` instead of importing `TrajectoryChangeType` directly, risking drift if the domain enum changes. Verified false: this exactly matches `presentation/schemas/trajectory.py`'s existing, already-reviewed convention (Story 3.2 Review Triage Log, Pass 1 finding #4, explicitly accepted as "the only architecturally consistent shape" given `presentation/` schemas never import domain enums directly in this codebase). → **reject** (false; established, already-accepted codebase convention).
10. [edge-case-hunter] `SqlAlchemyStudentRepository.search()`'s inner join could (a) exclude a matching student with zero enrollments, and (b) produce duplicate rows for a student enrolled in more than one classroom. Verified false: `backend/app/synthetic/population.py:157-172` generates exactly one `GeneratedEnrollment` per generated student (single loop, one append per `student_id`, no student ever omitted or repeated) — both scenarios require a data shape this codebase's only write path never produces. → **reject** (false; unreachable given the generation invariant).
11. [intent-alignment] Typing into search hides the recent-changes list (`showingSearch` ternary) rather than showing both simultaneously, read against the epic context's framing of search as the way to reach a "calm" (no-recent-change) student alongside the list. Verified false: neither the frozen spec's Intent/Boundaries/I-O-Matrix nor the epics.md AC for this story requires concurrent visibility — only that each view (list, search) independently renders its own required states, which the diff does. Two defensible readings exist and nothing written and frozen picks one, so the implemented choice is not a violation of anything actually specified. → **reject** (false; not contradicted by any frozen requirement).
12. [blind-hunter] The two 401 tests assert only `"error" in response.json()`, not the full `{code, message}` envelope shape. Verified low: the envelope is produced entirely by the shared, pre-existing `get_current_user`/`AppError` dependency (`presentation/auth/dependencies.py:37-48`), identical to every other router, and already covered by that dependency's own existing tests elsewhere — a regression there would surface in those tests regardless of this file's assertion strength. **low** (real but redundant given existing coverage elsewhere). → **reject** (low; fix adds no protection beyond what's already covered, and is unlikely to ever matter in practice).
13. [blind-hunter] `GetHomeService.execute()` makes up to 20 sequential `get_by_id` calls (N+1) rather than a single batched lookup. **low** (bounded at 20 by `RECENT_CHANGES_LIMIT`, well within the epic's 5s/request budget; no stated perf requirement motivates batching). → **reject** (low; unlikely to matter at this bounded scale, and batching would add complexity disproportionate to the benefit).
14. [blind-hunter] No automated keyboard/focus-order assertions in `Home.test.tsx` for the "reachable and operable with visible focus" AC. Verified low: every interactive element in the diff is a native, unmodified `<Link>`/`<input>`/`<button>` with no suppressed outline or negative `tabIndex` anywhere in the diff — functionally compliant by construction. **low** (behavior is already correct; a real jsdom focus/tab-order test is more than a trivial addition for the marginal benefit). → **reject** (low; functionally satisfied, fix nontrivial).
15. [blind-hunter] No dedicated test for the 250ms search debounce / stale-response-guard behavior itself, only the end-to-end "type then see results" path. **low** (existing test already exercises the debounced path successfully end-to-end; a dedicated fake-timer unit test is more than a trivial addition for marginal benefit). → **reject** (low).

**Pass 1 totals:** medium 1 (patched), low 3 (patched), low 4 (rejected), false 7 — 15 entries, 0 high.

## Design Notes

**Icon marker mapping:** map `TrajectoryChangeType` to a small icon + text label (never color alone, per epic-3 accessibility floor) — reuse the same four-value enum already defined in `domain/trajectory_change.py`; exact icon choice is a UI-only decision, not worth a Design Notes table.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests + new `test_home.py` pass
- `cd frontend && npm run generate:api-types && npm test` -- expected: types regenerate cleanly, all tests + new `Home.test.tsx` pass
- `git status --short` -- expected: only Code Map files + this spec changed
