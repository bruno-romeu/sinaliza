---
title: 'Acompanhamentos em andamento na página inicial'
type: 'feature'
created: '2026-10-14'
status: 'done'
baseline_commit: 'debe305e1d0b430a5fcc6a0fe88bf774bff9a988'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: ['docs/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Home (Story 3.3) only shows recent trajectory changes; the coordenação has no way to see, on the same screen, which `FollowUp`s she already opened and is actively conducting — RF-18 ("mudanças recentes e acompanhamentos em andamento") remains half-delivered.

**Approach:** Extend `GET /home` to also return every `FollowUp` whose status is not `ENCERRADO`, and add an "Acompanhamentos em andamento" section to the existing `Home.tsx` — one clickable card per active follow-up, reusing the existing `FollowUpStatusPill` and the stub route to the Tela de Acompanhamento — without touching Story 3.3's recent-changes/search behavior.

## Boundaries & Constraints

**Always:**
- `GET /home`'s response gains `in_progress_follow_ups: list[InProgressFollowUpOut]` — one entry per `FollowUp` with `status != ENCERRADO`, each carrying `id`, `student_id`, `student_name`, `status` — read via a new `FollowUpRepositoryPort.list_active()` implemented in `SqlAlchemyFollowUpRepository`, never recomputed/derived from trajectory data.
- `list_active()` orders by `created_at` desc, `id` desc as a deterministic tiebreak — same precedent as `list_recent`'s own tiebreak (spec-3-3).
- Each entry resolves `student_name` via the existing `StudentRepositoryPort.get_by_id` (`EVAL_DEMO`-filtered) — mirrors `GetHomeService`'s existing recent-changes resolution; a `FollowUp` whose student lookup returns `None` is skipped defensively (unreachable by construction, same precedent as the recent-changes loop).
- Each card is a single full-area `<Link to="/acompanhamentos/{id}">` (same whole-row-clickable precedent as the recent-changes row) showing `FollowUpStatusPill` + student name — never a new status representation.
- Zero active follow-ups renders the neutral message "Nenhum acompanhamento em andamento no momento" — never styled or treated as an error/failure state.
- The new section always renders, independent of the existing search/recent-changes toggle (`showingSearch`) — both sections coexist on the page per the epic context, and the active-follow-ups count stays visible even when there are no recent changes to show (UX-DR18).

**Never:**
- Never add a cap/pagination to `list_active()` — no AC calls for one, and open-case volume is operator-driven (manual "Abrir acompanhamento"), unlike the high-volume synthetic `TrajectoryChange` rows `list_recent` caps.
- Never show an urgency countdown, due date, or anything derived from `next_review_date` on the card (UX-DR11 explicit "never"; `next_review_date` stays unused, matching Story 4.1-4.4 scope).
- Never change `POST /follow-ups`, `/follow-ups/{id}/actions`, `/follow-ups/{id}/status`, or `GET /follow-ups/{id}` — this story only adds a read to `GET /home`.
- Never show student ranking/evasion score/"high-risk" KPI anywhere (shared product-wide Never, unchanged).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Active follow-ups exist | ≥1 `FollowUp` with status != `ENCERRADO` | `GET /home` includes one entry per such follow-up, ordered `created_at` desc; UI renders one card per entry (status pill + student name) | No error expected |
| Mixed statuses | Follow-ups across `EM_OBSERVACAO`/`ACOMPANHAMENTO_ATIVO`/`AGUARDANDO_RETORNO`, plus one `ENCERRADO` | The `ENCERRADO` one is excluded; all others are included | No error expected |
| No active follow-ups | 0 rows, or all `ENCERRADO` | `in_progress_follow_ups: []`; UI shows "Nenhum acompanhamento em andamento no momento" | No error expected |
| Card click | Coordenação clicks anywhere on a card | Navigates to `/acompanhamentos/{follow_up_id}` | No error expected |
| Existing `GET /home` load failure | 5xx/network error | Same existing "Não foi possível carregar os dados agora." retry action covers both sections (single fetch) | Unchanged from Story 3.3 |

</frozen-after-approval>

## Code Map

- `backend/app/application/home/ports.py` -- ADD `FollowUpRepositoryPort` Protocol: `list_active() -> list[FollowUp]`, following this file's existing one-narrow-port-per-method convention (mirrors `TrajectoryChangeRepositoryPort`/`StudentRepositoryPort` here, not the wider `application/followups/ports.py` one).
- `backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- EXTEND `SqlAlchemyFollowUpRepository`: add `list_active() -> list[FollowUp]` — `select(FollowUpModel).where(FollowUpModel.status != FollowUpStatus.ENCERRADO).order_by(FollowUpModel.created_at.desc(), FollowUpModel.id.desc())`, mapped the same way `get_by_id` already maps a `FollowUpModel` to the `FollowUp` dataclass.
- `backend/app/application/home/get_home.py` -- EXTEND: new frozen dataclass `ActiveFollowUp(follow_up: FollowUp, student_name: str)`; `GetHomeService.__init__` gains `follow_up_repository: FollowUpRepositoryPort`; `execute()` now returns a `HomeResult(recent_changes: list[RecentChange], active_follow_ups: list[ActiveFollowUp])` dataclass instead of a bare list — student-name resolution for each active follow-up reuses the same `self._student_repository.get_by_id(...)`/skip-if-`None` pattern already used for `recent_changes`.
- `backend/app/presentation/schemas/home.py` -- ADD `InProgressFollowUpOut(id: uuid.UUID, student_id: uuid.UUID, student_name: str, status: Literal["EM_OBSERVACAO", "ACOMPANHAMENTO_ATIVO", "AGUARDANDO_RETORNO", "ENCERRADO"])` (own local `Literal`, matching this file's existing `RecentChangeOut.type` convention, not an import from `presentation/schemas/follow_ups.py`); extend `HomeOut` with `in_progress_follow_ups: list[InProgressFollowUpOut]`.
- `backend/app/presentation/home/router.py` -- EXTEND `get_home`: read `result.active_follow_ups` from the now-`HomeResult`-returning `service.execute()` and populate `HomeOut.in_progress_follow_ups`.
- `backend/app/composition.py` -- EXTEND `get_get_home_service`: pass `follow_up_repository=SqlAlchemyFollowUpRepository(db)` into `GetHomeService(...)`.
- `backend/tests/test_home.py` -- EXTEND: update the two existing exact-equality assertions (`{"recent_changes": []}` and the empty-list case) to also include `"in_progress_follow_ups": []`; add tests for the I/O Matrix's active-follow-ups/mixed-statuses-excludes-encerrado/empty rows.
- `frontend/src/api/client.ts` -- EXTEND: add `export type InProgressFollowUp = Home['in_progress_follow_ups'][number]` (regenerated `schema.d.ts`, never hand-transcribed).
- `frontend/src/pages/Home.tsx` -- EXTEND: read `home.in_progress_follow_ups` from the existing `getHome` response into new state; render a new "Acompanhamentos em andamento" section (placed before "Mudanças recentes"/"Resultados da busca", always visible regardless of `showingSearch`) with one `<Link to={`/acompanhamentos/${item.id}`}>` card per entry — reusing `rowStyle` and `FollowUpStatusPill` — plus the neutral empty-state message when the list is empty.
- `frontend/src/pages/Home.test.tsx` -- EXTEND: add `in_progress_follow_ups: []` to the existing `/api/home` mock responses (keeps those tests focused on recent-changes/search behavior, unaffected by the new section); add tests for the new section's card rendering, its full-card link target, and its empty-state message.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/application/home/ports.py` -- add `FollowUpRepositoryPort.list_active` -- feeds the new active-follow-ups read
- [x] `backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py` -- implement `list_active()` -- RF-18
- [x] `backend/app/application/home/get_home.py` -- thread `follow_up_repository` through `GetHomeService`, return `HomeResult` -- RF-18
- [x] `backend/app/presentation/schemas/home.py` -- add `InProgressFollowUpOut`, extend `HomeOut` -- surfaces active follow-ups
- [x] `backend/app/presentation/home/router.py` -- populate `HomeOut.in_progress_follow_ups` -- RF-18
- [x] `backend/app/composition.py` -- wire `follow_up_repository` into `get_get_home_service` -- registers the dependency
- [x] `backend/tests/test_home.py` -- I/O Matrix coverage + update existing exact-equality assertions -- RNF-09
- [x] `frontend/src/api/client.ts` + regenerated `schema.d.ts` -- typed `InProgressFollowUp` -- never hand-transcribed
- [x] `frontend/src/pages/Home.tsx` -- new "Acompanhamentos em andamento" section: cards, empty state -- RF-18, UX-DR11, UX-DR18
- [x] `frontend/src/pages/Home.test.tsx` -- card/empty-state rendering + updated mocks -- UX-DR11

**Acceptance Criteria:**
- Given `FollowUp`s with status different from `ENCERRADO`, when Home loads, then it shows one card per in-progress follow-up, with the status pill and student name (completing RF-18: mudanças recentes + acompanhamentos em andamento).
- Given an in-progress follow-up card, when clicked anywhere in the card's area, then it opens the corresponding Tela de Acompanhamento (`/acompanhamentos/{id}`) (UX-DR11).
- Given zero active follow-ups, when Home loads, then it shows the neutral message "Nenhum acompanhamento em andamento no momento", never treated as a system failure (UX-DR18).
- Given an in-progress follow-up card, when rendered, then it never shows an urgency countdown (UX-DR11).

## Implementation Notes

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — 2 patch, 4 rejected (false/low), 0 defer, 0 intent-gap, 0 bad-spec.

1. [verification-gap] + [blind-hunter] `SqlAlchemyFollowUpRepository.list_active()` orders by `created_at.desc(), id.desc()` but no test seeds two active follow-ups sharing an identical `created_at` to pin the `id.desc()` tiebreaker — unlike the analogous, already-covered `test_home_breaks_detected_at_tie_by_id_desc` for `list_recent`. [backend/tests/test_home.py, backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py:80] → **patch**: add a tiebreak test mirroring `test_home_breaks_detected_at_tie_by_id_desc`'s structure for active follow-ups.
2. [verification-gap] `list_active()` is explicitly never capped (spec Boundaries & Constraints, code comment), but no test seeds more than 20 active follow-ups to verify none are truncated — unlike the analogous `test_home_caps_recent_changes_at_twenty` for `list_recent` (which asserts the opposite: a cap). [backend/tests/test_home.py, backend/app/infrastructure/repositories/sqlalchemy_follow_up_repository.py:73-77] → **patch**: add a test seeding >20 active follow-ups asserting all are returned, uncapped.
3. [blind-hunter] `GetHomeService.execute()`'s per-row `student_repository.get_by_id(...)` resolution for active follow-ups is an N+1 query, now against an uncapped list (unlike the bounded-at-20 `recent_changes` loop this mirrors). **Verified low**: open-case volume is operator-driven (manual "Abrir acompanhamento" actions only), realistically small in this demo's actual usage, well within the epic's 5s/request budget; a batched `get_by_ids` would add a new port method disproportionate to the benefit. This exact N+1 concern was already raised and rejected for the bounded `recent_changes` loop in spec-3-3's own Review Triage Log (Pass 1, finding #13). → **reject** (low; unlikely to matter at realistic scale, fix disproportionate).
4. [blind-hunter] A `FollowUp` whose `student_id` lookup returns `None` is silently skipped (`continue`), untested for the new active-follow-ups loop. **Verified false**: a `FollowUp` is only ever created (via `OpenFollowUpService`) for a student that already passed the same `EVAL_DEMO`-filtered `get_by_id` lookup as part of opening a trajectory-evidence-backed follow-up, and `StudentModel.dataset_split` is never mutated after generation — so this branch is unreachable by any current write path, mirroring spec-3-3's own already-accepted "unreachable by construction" rejection (Pass 1, finding #5) for the identical pattern on `recent_changes`. → **reject** (false; unreachable).
5. [blind-hunter] The new section's loading skeleton is `aria-hidden="true"` with no `aria-live` announcement, so a screen-reader user gets no "loading" feedback while `in_progress_follow_ups` is in flight. **Verified false as a regression**: this is byte-for-byte the same skeleton pattern the pre-existing, already-reviewed-and-accepted `recentChanges === null` skeleton uses (`Home.tsx`, Story 3.3) — this diff only replicates an established, accepted codebase convention, it does not introduce a new accessibility gap relative to what already ships. → **reject** (false; matches existing accepted precedent, not a regression this diff introduces).
6. [blind-hunter] + [edge-case-hunter] When `loadError` is true, the new "Acompanhamentos em andamento" section renders only its heading with no content (not skeleton, not the empty message, not an error message) — unlike the recent-changes section, which shows "Não foi possível carregar os dados agora." + retry. **Verified real but low**: in the default (most common) failure path, `showingSearch` is false, so the existing retry affordance is visible just below the new section's blank heading, and one click re-fetches `GET /home`, correctly repopulating both sections (spec's own I/O Matrix: "single fetch" covers both). The only strictly-broken scenario (no error affordance visible anywhere) requires the user to already be mid-search when the initial load fails — a narrow compound edge case, unlikely in everyday use. Smallest correct fix requires adding a new conditional branch (not a plain correction/deletion). → **reject** (low; unlikely in everyday use given the visible retry in the common path, and the fix adds branching complexity disproportionate to the benefit).
7. [blind-hunter] `InProgressFollowUpOut.status`'s `Literal` includes all 4 enum values though only `EM_OBSERVACAO`/`ACOMPANHAMENTO_ATIVO`/`AGUARDANDO_RETORNO` can ever reach this field (server-side filtered), with a claim that `AGUARDANDO_RETORNO` is untested end-to-end. **Verified false**: `test_home_excludes_encerrado_follow_ups` exercises `AGUARDANDO_RETORNO` directly through `GET /home`; `FollowUpStatusPill` (reused, not reimplemented) already renders all 4 statuses correctly per its own Story 4.1 tests; the all-4-value `Literal` matches this file's own established `RecentChangeOut.type` convention (schemas never import domain enums, per spec-3-3's own accepted precedent). → **reject** (false; already covered, matches established convention).
8. [intent-alignment] Descriptive-only: noted that "not `ENCERRADO`" (the diff's operative definition) is a narrower reading than the Problem statement's "actively conducting," and that the uncapped list is untested at realistic volume. **Not actionable**: the frozen Intent's own Approach section already settles the operative definition verbatim ("every `FollowUp` whose status is not `ENCERRADO`"), so there is no gap left for this diff to resolve; intent-alignment's instructions are explicitly descriptive-only, not a finding to route. → no row/action needed beyond this note.

**Pass 1 totals:** low 3 (rejected), false 3 (rejected), patch 2. Patches 1-2 dispatched to the implementation subagent; re-verified after patch (see Verification run below).

## Design Notes

The active-follow-ups section is placed above "Mudanças recentes"/"Resultados da busca" and always renders regardless of the search toggle — neither the frozen spec nor epics.md dictates an exact position, but conducted cases are the coordenação's actionable work-in-progress, while recent changes are "things to triage"; surfacing the former first is a UI-only call, not a requirement. Rendering it outside the `showingSearch` ternary (rather than hiding it during search, like recent-changes does) is what makes UX-DR18's "contagem de acompanhamentos ativos ainda visível" true even while search results are showing, not only in the no-recent-changes case literally named in that pattern.

`GetHomeService.execute()` changing its return type from a bare `list[RecentChange]` to a `HomeResult` dataclass bundling both lists is the only call-site-breaking change in this story; its one caller (`presentation/home/router.py`) is also in this story's Code Map, so nothing is left on the old signature.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests incl. extended `test_home.py` pass (pre-existing `test_synthetic_dataset_split.py` failures unrelated, ignore)
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` -- expected: `backend/openapi.json` regenerates with `HomeOut.in_progress_follow_ups`
- `cd frontend && npm run generate:api-types` -- expected: `schema.d.ts` picks up the new `/home` response shape
- `cd frontend && npx tsc --noEmit` -- expected: clean
- `cd frontend && npm test -- --run` -- expected: all tests incl. extended `Home.test.tsx` pass
- `git status --short` -- expected: only Code Map files + this spec + sprint-status.yaml changed
