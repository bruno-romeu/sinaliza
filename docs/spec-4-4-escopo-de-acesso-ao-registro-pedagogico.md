---
title: 'Escopo de acesso ao registro pedagógico vinculado a um acompanhamento'
type: 'feature'
created: '2026-10-14'
status: 'done'
baseline_commit: '26bac16c86b59dee8f494761b5eb527bf650456d'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['independent-diff-review']
review_loop_iteration: 0
context: ['docs/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Once a `PedagogicalObservation` becomes a cited source of evidence for a real `FollowUp` (via `TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`), its full free-text content is readable by any authenticated user who can reach either `GET /students/{id}/trajectory/detail` or `GET /follow-ups/{id}` — there is no visibility scoping at all today (RF-22 undelivered; flagged as deferred work from Story 4.1's own review, finding 6: "any authenticated user who knows/guesses a `follow_up_id` can read observation text cited as its evidence").

**Approach:** Add a read-time visibility filter, living entirely inside `SqlAlchemyPedagogicalObservationRepository.get_by_ids` (the one method both evidence-resolution call sites already share via `application/trajectory/evidence.resolve_evidence`), so that any `PedagogicalObservation` cited as evidence of at least one real `FollowUp` has its `text` replaced with a factual placeholder unless the requesting user is the `responsible_user_id` of at least one `FollowUp` citing it (RF-22, AD-8, AD-11). Observations never cited by any `FollowUp` remain fully visible, unchanged from today — this filter only activates once the specific chain in the AC exists. `SignalEvaluator`/`ConvergenceRule` keep reading the unfiltered `list_by_student_in_range` exactly as before (AD-8's explicit carve-out) — this story touches `get_by_ids` only, never `list_by_student_in_range`.

## Boundaries & Constraints

**Always:**
- The visibility check runs entirely inside `SqlAlchemyPedagogicalObservationRepository.get_by_ids(ids, requesting_user_id)` — the one repository method `application/trajectory/evidence.resolve_evidence` already calls from both `GetStudentTrajectoryDetailService` (Trajetória's evidence card) and `GetFollowUpService` (Acompanhamento's evidence groups) — never duplicated inline in either application service, router, or `evidence.py` itself (AD-11: "vive no mesmo método de leitura... nunca inline em cada endpoint").
- An observation is "restricted" only once it is cited as a source (`TrajectoryChangeSource.source_type = PEDAGOGICAL_OBSERVATION`, `source_id = observation.id`) of a `TrajectoryChange` that itself has at least one real `FollowUpEvidence` row (i.e., some `FollowUp` actually cites it). An observation with zero such rows is never restricted — always returned with its real `text`, matching today's behavior and Story 1.5's documented-but-not-yet-implemented note.
- A restricted observation's `text` is visible, unredacted, to any requesting user who is `responsible_user_id` on *at least one* of the `FollowUp`s whose evidence chain cites it — never only the first/most-recent one (RF-22, AD-8: "nunca exclusivo a um só responsável").
- A restricted observation's `text` is replaced with the fixed factual placeholder `"Texto do registro pedagógico restrito ao responsável pelo acompanhamento que o cita como evidência."` for every other requesting user — the `PedagogicalObservation` row itself (id, student_id, author_user_id, created_at, the evidence item's date) is still returned/rendered; only the free-text content is withheld, consistent with `EXPERIENCE.md`'s Voice and Tone (factual, never a vague "access denied").
- `GetStudentTrajectoryDetailService.execute` and `GetFollowUpService.execute` both gain a required `requesting_user_id: uuid.UUID` parameter, threaded from each router's existing `get_current_user` dependency (`CurrentUser.id`) — the same idiom already used for `responsible_user_id`/`author_user_id` elsewhere in `followups/router.py`.
- `resolve_evidence(...)` in `application/trajectory/evidence.py` gains the same required `requesting_user_id: uuid.UUID` parameter, passed straight through to `observation_repo.get_by_ids`.
- `PedagogicalObservationRepositoryPort.get_by_ids`'s signature changes in `application/trajectory/ports.py` only (the single Protocol definition; `application/followups/ports.py` re-exports it unchanged).
- `SignalEvaluator`/`ConvergenceRule` (Epic 3) keep calling `list_by_student_in_range` exactly as today — completely unfiltered, unaware this story exists (AD-8: "sempre rodam sobre o conjunto completo não filtrado de registros pedagógicos").

**Never:**
- Never touch `list_by_student_in_range` — it feeds both the unfiltered `SignalEvaluator` (Epic 3, must never filter) and the Trajetória screen's raw observation timeline (`ObservationItemOut`, Story 3.4's `_recent_observations`); scoping that shared method would either break detection or require splitting it into two methods, neither of which this story's AC (phrased specifically around the `TrajectoryChangeSource → TrajectoryChange → FollowUpEvidence` evidence chain) asks for. The raw timeline staying unfiltered is the same already-documented, not-yet-implemented gap noted in Story 1.5's own AC ("aqui é apenas documentado, não implementado").
- Never add a `role`/visibility enum to `User` or `PedagogicalObservation` — AD-8 is explicit the perfil remains single (`COORDENACAO_PEDAGOGICA`); scoping is purely by `responsible_user_id` membership, never a new permission concept.
- Never change `POST /follow-ups`, `POST /follow-ups/{id}/actions`, `PATCH /follow-ups/{id}/status`, or `GET /students/{id}/trajectory` (the non-detail endpoint, which never resolves evidence) — this story only touches the two evidence-resolving reads.
- Never change `EvidenceItemOut`/`ObservationItemOut`'s shape — `description`/`text` stay plain strings; the placeholder is just a different string value for the same field, no new boolean/flag field on the wire.
- Never persist a restriction/visibility flag on `PedagogicalObservationModel` — the filter is computed at read time from existing tables (`trajectory_change_sources`, `follow_up_evidence`, `follow_ups`), per `domain/pedagogical_observation.py`'s own docstring ("no visibility-scoping field either... a future concern layered on... never persisted on this shape").

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Not yet evidence of any FollowUp | `PedagogicalObservation` cited only by a `TrajectoryChange` with zero `FollowUpEvidence` rows | `GET /students/{id}/trajectory/detail`'s evidence item shows the real text, for any authenticated user | No error expected |
| Evidence of a FollowUp, requester is responsible | `FollowUp.responsible_user_id = requesting_user_id`, citing a change sourced by the observation | `GET /follow-ups/{id}` and `GET /students/{id}/trajectory/detail` both show the real text | No error expected |
| Evidence of a FollowUp, requester is not responsible | A different user than `FollowUp.responsible_user_id` requests either endpoint | Both show the fixed placeholder text instead of the real content | No error expected |
| Cited by two FollowUps with different responsible users | Same observation sourced into two distinct `TrajectoryChange`s, each evidenced by a different `FollowUp` | Either responsible user sees the real text (union, not single-owner) | No error expected |
| SignalEvaluator read path | `PedagogicalObservationSignalEvaluator` reads via `list_by_student_in_range` for an observation that is otherwise restricted | Signal evaluation still sees the full observation (unfiltered) — convergence detection is unaffected | No error expected |

</frozen-after-approval>

## Code Map

- `backend/app/application/trajectory/ports.py` -- EXTEND `PedagogicalObservationRepositoryPort.get_by_ids`: add required `requesting_user_id: uuid.UUID` parameter to the signature (RF-22, AD-11).
- `backend/app/infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py` -- EXTEND `get_by_ids(ids, requesting_user_id)`: after loading the rows (existing `filter_as_of` call unchanged), run two additional queries joining `TrajectoryChangeSourceModel` (`source_type == PEDAGOGICAL_OBSERVATION`, `source_id IN ids`) → `FollowUpEvidenceModel` (`trajectory_change_id`) → `FollowUpModel` (`id`): one `SELECT DISTINCT source_id` with no further filter (the "restricted" set — cited by ≥1 real `FollowUp`), one `SELECT DISTINCT source_id` additionally filtered to `FollowUpModel.responsible_user_id == requesting_user_id` (the "visible to this requester" set). For any returned observation whose `id` is in the first set but not the second, construct the `PedagogicalObservation` with `text` replaced by the module-level `_RESTRICTED_TEXT` placeholder constant instead of `model.text`; everything else keeps `model.text` unchanged. Add the two extra queries behind an early `if not ids: return []` to avoid executing joins for the already-handled empty-list case.
- `backend/app/application/trajectory/evidence.py` -- EXTEND `resolve_evidence(...)`: add required `requesting_user_id: uuid.UUID` parameter; thread it into the single `observation_repo.get_by_ids(ids, requesting_user_id)` call inside `_resolve_items_for_type` (which itself also needs the new parameter threaded through from `resolve_evidence`).
- `backend/app/application/trajectory/get_student_trajectory_detail.py` -- EXTEND `GetStudentTrajectoryDetailService.execute`: add required `requesting_user_id: uuid.UUID` parameter; thread it to `self._resolve_evidence(result.trajectory_change, requesting_user_id)` → `resolve_evidence(...)`. `_recent_observations` (feeds `ObservationItemOut`, the raw timeline) is untouched — no `requesting_user_id` parameter added there (spec Boundaries & Constraints: raw timeline stays unfiltered).
- `backend/app/application/followups/get_follow_up.py` -- EXTEND `GetFollowUpService.execute`: add required `requesting_user_id: uuid.UUID` parameter; thread it into the existing per-group `resolve_evidence(...)` call.
- `backend/app/presentation/trajectory/router.py` -- EXTEND `get_student_trajectory_detail`: add `current_user: CurrentUser = Depends(get_current_user)` (mirrors `follow_ups/router.py`'s existing idiom; the router-level `dependencies=[Depends(get_current_user)]` already enforces auth but doesn't expose the identity to the handler), pass `requesting_user_id=uuid.UUID(current_user.id)` into `service.execute(...)`.
- `backend/app/presentation/follow_ups/router.py` -- EXTEND `get_follow_up`: add the same `current_user: CurrentUser = Depends(get_current_user)` parameter, pass `requesting_user_id=uuid.UUID(current_user.id)` into `service.execute(...)`.
- `backend/tests/test_follow_ups.py` -- EXTEND: add tests for the I/O Matrix's FollowUp-scoped rows — non-responsible requester sees the placeholder on `GET /follow-ups/{id}`, the responsible requester (and a second `FollowUp`'s different responsible user, when two distinct FollowUps cite the same observation) both see the real text.
- `backend/tests/test_trajectory_detail.py` -- EXTEND: add one test covering the same evidence card on `GET /students/{id}/trajectory/detail` through all three states in sequence — real text visible to anyone before any `FollowUp` cites the change (unrestricted default), still visible to the responsible user after one opens a `FollowUp` citing it, and redacted for a second, non-responsible authenticated user.

## Tasks & Acceptance

**Execution:**
- [x] `application/trajectory/ports.py` -- extend `PedagogicalObservationRepositoryPort.get_by_ids` signature -- RF-22
- [x] `infrastructure/repositories/sqlalchemy_pedagogical_observation_repository.py` -- implement the visibility filter in `get_by_ids` -- RF-22, AD-8, AD-11
- [x] `application/trajectory/evidence.py` -- thread `requesting_user_id` through `resolve_evidence`/`_resolve_items_for_type` -- RF-22
- [x] `application/trajectory/get_student_trajectory_detail.py` -- thread `requesting_user_id` through `execute`/`_resolve_evidence` -- RF-22
- [x] `application/followups/get_follow_up.py` -- thread `requesting_user_id` through `execute` -- RF-22
- [x] `presentation/trajectory/router.py`, `presentation/follow_ups/router.py` -- pass the authenticated user's id into both services -- RF-22
- [x] `backend/tests/test_follow_ups.py` -- I/O Matrix coverage for `GET /follow-ups/{id}`
- [x] `backend/tests/test_trajectory_detail.py` -- I/O Matrix coverage for `GET /students/{id}/trajectory/detail`

**Acceptance Criteria:**
- Given a `PedagogicalObservation` that becomes a source of evidence for a `FollowUp` (via `TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`), when a user who is not that `FollowUp`'s `responsible_user_id` reads either `GET /follow-ups/{id}` or `GET /students/{id}/trajectory/detail`, then the observation's text is replaced by a factual placeholder (RF-22, AD-8).
- Given the same scoped observation, when the `FollowUp`'s `responsible_user_id` reads either endpoint, then the real text is shown (RF-22).
- Given more than one `FollowUp` citing the same observation as evidence (via distinct `TrajectoryChange`s), when any of their respective responsible users reads either endpoint, then that user sees the real text — never exclusive to a single responsible user (AD-8).
- Given the visibility filter, when inspected in code, then it lives entirely inside `SqlAlchemyPedagogicalObservationRepository.get_by_ids` — never duplicated inline in a router or application service (AD-11).
- Given the `PedagogicalObservationSignalEvaluator` (Epic 3), when it evaluates signals for convergence detection via `list_by_student_in_range`, then it continues to see the complete, unfiltered set of observations — unaffected by this story (AD-8).

## Implementation Notes

Implemented directly by the orchestrating session (no separate implementation subagent), following this spec's Code Map.

`_restricted_ids`/`_visible_to_user_ids` are two separate SELECTs rather than one combined query with a `BOOL_OR`/`GROUP BY` — the two-query shape reads more directly as "is this id restricted at all" then "is it restricted *for this user specifically*", mirrors the plain, unoptimized style the rest of this repository class already uses (e.g. `filter_as_of` is a simple `WHERE`, not a windowed aggregate), and the second query only runs when the first returns a non-empty set (`if restricted_ids else set()`), so the common case (most observations never become `FollowUp` evidence) pays no extra query cost at all.

## Spec Change Log

## Review Triage Log

**Pass 1** (independent subagent review of the diff against this spec's frozen Intent/Boundaries/I-O Matrix, read-only, no DB access):

1. Verified `_restricted_ids`/`_visible_to_user_ids`'s joins and `SourceType.PEDAGOGICAL_OBSERVATION` filter are correct; `visible_ids` short-circuits to an empty set when `restricted_ids` is empty; the redaction condition (`in restricted_ids and not in visible_ids`) correctly implements union-of-responsible-users semantics (AD-8). → **no finding** (verified correct).
2. Grepped `get_by_ids(`/`resolve_evidence(` across `backend/app` and `backend/tests`: exactly the two expected call sites exist (`GetStudentTrajectoryDetailService`, `GetFollowUpService`), both updated; no stub/fake implementation of `PedagogicalObservationRepositoryPort` elsewhere retains the old 1-arg signature. → **no finding** (call-site completeness confirmed).
3. Flagged that `list_by_student_in_range` (the raw observation timeline, `_recent_observations`, and `PedagogicalObservationSignalEvaluator`) stays unfiltered even for a now-restricted observation — so the same text could appear redacted in the evidence card but unredacted in the Trajetória screen's raw timeline on the same page. → **accepted as intentional-per-spec, not a defect**: this is the frozen Boundaries & Constraints' explicit "Never" (touching the shared signal-detection/timeline method would either break AD-8's unfiltered-detection invariant or require an unscoped split of that method), and is the same already-documented, not-yet-implemented gap from Story 1.5's own AC. Not actioned; noted here for traceability rather than deferred-work.md, since it's a known, deliberate scope boundary rather than an open gap.
4. Confirmed all 5 I/O & Edge-Case Matrix rows have test coverage (unrestricted default, responsible-sees-real-text, non-responsible-redacted on both endpoints, two-`FollowUp`-union, and the `SignalEvaluator`-unaffected row is structurally guaranteed by leaving `list_by_student_in_range` untouched rather than needing a new direct test). → **no finding**.
5. Confirmed `requesting_user_id` threading end-to-end (`evidence.py` → `get_student_trajectory_detail.py`/`get_follow_up.py` → both routers' `uuid.UUID(current_user.id)` idiom) with no inline duplication of the filter logic anywhere (AD-11). → **no finding**.

**Pass 1 totals:** 0 bugs found, 1 explicitly-scoped-out observation reaffirmed as correct per the frozen spec (not actioned), 0 missing tests, 0 broken call sites. No patches required; checks already green from the implementation pass.

## Design Notes

The filter deliberately scopes only `get_by_ids` (the evidence-resolution read), never `list_by_student_in_range` (the raw student timeline + `SignalEvaluator`'s read). These two methods already served structurally different purposes before this story: `list_by_student_in_range` must stay unfiltered for `PedagogicalObservationSignalEvaluator` (AD-8's explicit carve-out — convergence detection would silently degrade if it started skipping restricted observations), and splitting it into a filtered/unfiltered pair just for the raw timeline would be a larger, unscoped refactor the AC's specific evidence-chain wording (`TrajectoryChangeSource` → `TrajectoryChange` → `FollowUpEvidence`) doesn't ask for. The raw timeline showing full text regardless of `FollowUp` status is the same already-documented, explicitly-deferred gap from Story 1.5's own AC ("aqui é apenas documentado, não implementado") — unchanged by this story, not a regression it introduces.

The redaction replaces `PedagogicalObservation.text` with a fixed placeholder string rather than adding a `visible: bool` field to the domain dataclass or the wire schema. This keeps `domain/pedagogical_observation.py`'s own documented intent ("no visibility-scoping field... never persisted on this shape") and needs zero changes to `EvidenceItemOut`/the OpenAPI contract/the frontend — the evidence card already renders `description` as an opaque string, so a different string value is transparently handled with no frontend code change at all.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5433/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: all tests incl. extended `test_follow_ups.py`/`test_trajectory_detail.py` pass (pre-existing `test_synthetic_dataset_split.py` failures unrelated, ignore)
- `cd backend && ./.venv/Scripts/python.exe -m app.export_openapi` -- expected: `backend/openapi.json` unchanged (no response-shape change, only a behavior change in an already-`str` field)
- `cd frontend && npx tsc --noEmit` -- expected: clean (no frontend contract change)
- `cd frontend && npm test -- --run` -- expected: all existing tests pass unchanged (no frontend code touched)
- `git status --short` -- expected: only Code Map files + this spec + sprint-status.yaml changed
