# Adversarial Review — ARCHITECTURE-SPINE.md (Sinaliza)

Reviewed: `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md`
Method: for each AD, construct two independent, spine-compliant builders and try to make them build something incompatible. Every pair below is a case where BOTH builders can honestly claim "I followed the rule to the letter" while producing code that clashes with the other's.

Verdict up front: the spine is unusually disciplined about *what must not happen* (AD-1..AD-10 read like a checklist of banned anti-patterns) but weaker about *the exact shape of the happy path* — upsert keys, transaction scope, retraction semantics, and enforcement mechanisms are repeatedly asserted as outcomes ("idempotente", "atômica", "nunca aparece", "em nível de schema") without specifying the mechanism that makes them true. That's where every pair below lives.

---

## 1. AD-2/AD-3 — On-demand computation + convergence: 4 distinct holes

### 1a. "Idempotent upsert" has no stated natural key
AD-2: "a mesma requisição faz upsert idempotente das linhas" for `TrajectorySnapshot`/`TrajectoryChange`. No unique key is given anywhere in the spine (not in AD-2, AD-3, AD-7, or the Structural Seed).

- **Builder A** keys the upsert on `(student_id, period_id)` and treats the row as a live, mutable projection of "current convergence state for this period" — re-evaluated and overwritten every time signals are recomputed (window is rolling, so the signal set legitimately differs day to day within the same `AcademicPeriod`).
- **Builder B** keys on `(student_id, period_id, detected_at)` (or just auto-increment, no natural key at all) and treats each request's detection as a new historical event — never updates a prior row, because AD-6 established the append-only pattern for `FollowUpAction` and Builder B generalizes that spirit to `TrajectoryChange` too.

Both satisfy "idempotent" under a narrow reading (A: re-running today's request is a no-op after the first upsert; B: re-running produces the same *new* row only if `detected_at` is pinned to the period, so also technically idempotent). But A produces at most one `TrajectoryChange` per student per period ever; B can produce many. `FollowUpEvidence.trajectory_change_id` (AD-7) and the home page's "recent changes" list will show completely different histories depending on which builder wrote the persistence code.

**Fix needed:** name the unique constraint explicitly (e.g., `UNIQUE(student_id, period_id)` on `trajectory_change`) and state whether the row is a live projection or a point-in-time event log.

### 1b. Retraction/downgrade is undefined
Because `window_days` is rolling and re-evaluated per request, a student's signal count can cross the ≥2 threshold upward on Monday and back down to 1 (or 0) on Tuesday within the same `AcademicPeriod`, purely from the window sliding — no new fact was even recorded.

- **Builder A** (live-projection reading from 1a) deletes or downgrades the existing `TrajectoryChange` row on Tuesday's request, since it's "recomputed on demand" and the row is supposed to reflect current truth. This cascades: `trajectory_change_sources` rows get deleted, and `FollowUpEvidence.trajectory_change_id` (NOT NULL FK per AD-7) now dangles — either the delete must be blocked, or a coordinator's saved evidence citation silently disappears.
- **Builder B** (event-log reading) never retracts; once ≥2 categories converge and a row is upserted, it stays forever, even after the underlying signals recover. The home page's "recent changes" could show a stale alarm for a student who is no longer at risk, with no code path that ever removes it.

Neither behavior is forbidden by the spine, and they are operationally opposite (one loses evidence, the other never clears alarms). Nothing in AD-2/AD-3/AD-7 says what happens when a previously-emitted convergence stops converging.

### 1c. What counts as "the same request" when the home page fans out over ~200 students, and what is the atomicity unit?
AD-2 mandates a set-based query for the *read/aggregation* ("nunca um loop Python por aluno"). AD-7 mandates that a `TrajectoryChange` and its `trajectory_change_sources` rows are inserted "na mesma transação atômica" — but that sentence is scoped to *one* change, not to the request as a whole.

- **Builder A** computes the aggregate set-based, then loops in Python over the (small) subset of students whose signals actually converged, calling the application service once per student; each call opens and commits its own transaction. A failure validating one student's `source_id` (e.g., a `PedagogicalObservation` that was hard-deleted between the read and the write) fails only that student's upsert; the other 199 succeed and the home page renders with one student silently missing its new change.
- **Builder B** wraps the entire `GET /home` request in one outer transaction for consistency and calls the same per-student upserts inside it, planning to commit once at the end. The same single bad `source_id` now raises inside the transaction and rolls back all 200 students' upserts, turning one stale FK into a full 500 on the home page — for a request whose whole point is to be resilient under RNF-01's 5s budget for ~200 students.

Both builders can point to AD-2's "a mesma requisição" language to justify their choice (A reads it as "the persistence unit is the change, happening during the request"; B reads it as "the request is the unit of work, and it upserts"). The spine never says whether partial failure within the home fan-out is acceptable or whether the whole request must be all-or-nothing.

---

## 2. AD-5 — "Hoje" and dataset truncation: what `as_of()` actually anchors to

AD-5 centralizes truncation in one utility (`as_of()`), applied only to `EVAL_DEMO` reads, "nunca `date.today()` disperso pelo código." Good — but it never says what `as_of()` returns internally, and that ambiguity is exactly where the ML-eval builder and the live-trajectory builder can diverge:

- **Builder A (ML eval script)** wants reproducible metrics independent of when the script is run. They anchor `as_of()` to `SyntheticGenerationRun.generated_at` (a frozen "logical today" baked in at generation time), so re-running the eval script in October gives identical numbers to running it in November.
- **Builder B (live trajectory-read path)** wants the demo to visibly "advance" as real days pass between now (2026-09-17) and the defesa (2026-11-23), so the coordinator sees new data appear over time. They anchor `as_of()` to the real wall-clock `datetime.date.today()`.

Both are legitimate, single-utility, non-dispersed implementations of `as_of()` — and they are incompatible: if the synthetic generator's calendar dates were authored relative to a fixed "logical today" (A's assumption) but the live app truncates against the real system clock (B's assumption), then on any given day the live demo and the eval script's frozen metrics describe two different truncation points, and the demo narrative (trajectories "unfolding" toward the defesa date) only works if the synthetic dates were generated to line up with real calendar dates in the first place — a generator requirement AD-5 never states. Nothing here is technically "date.today() disperso pelo código" (each side has exactly one call site), yet the two single-utility implementations produce different data.

**Fix needed:** state explicitly whether `as_of()` wraps the real system clock or a stored "reference date," and require the synthetic generator's calendar to be anchored to real dates if it's the former.

---

## 3. AD-7 — "Garantida em nível de schema" is not actually achievable with the given DDL

This is the sharpest hole in the document. AD-7's title promises schema-level (not just app-level) integrity, and the Rule gives a concrete DDL:

> `trajectory_change_sources(trajectory_change_id FK NOT NULL, source_type ENUM(...), source_id BIGINT)`

`source_id` is a **polymorphic** reference — it points at `attendance_record`, `grade`, `assignment_submission`, or `pedagogical_observation` depending on `source_type`. Standard relational FK constraints cannot reference "one of four tables conditionally" from a single column. So the DDL as literally specified in AD-7 **cannot** be schema-enforced; the "each `source_id` existe" check the Rule describes ("validando que cada source_id existe... antes do commit") is necessarily an application-level `SELECT EXISTS` — which is precisely the pattern the AD's own title claims to avoid.

- **Builder A** implements the DDL exactly as written (one `source_id BIGINT`, no FK) and treats "atomic transaction" as: open a SQLAlchemy session, run the four `EXISTS` checks, insert the change, insert the sources, commit — all app-level, no DB constraint backing it. Under Postgres's default READ COMMITTED isolation, a concurrent delete of the referenced row between the `EXISTS` check and the `INSERT` (still inside Builder A's transaction) is **not** blocked by anything — there's no FK for Postgres to take a row lock against. This is exactly the TOCTOU gap the task description anticipates, and it survives despite Builder A honoring "atomic transaction" to the letter.
- **Builder B**, trying to actually satisfy the AD's title ("nível de schema"), redesigns the join table with four nullable per-type FK columns (`attendance_id`, `grade_id`, `assignment_submission_id`, `pedagogical_observation_id`) plus a `CHECK` that exactly one is non-null and matches `source_type`. This gets real DB-enforced referential integrity (Postgres FK checks take locks on the referenced row, so a concurrent delete would block or fail) — but it is a **different physical schema** than the one AD-7 dictates, and no longer matches `data-model.md`, the ER diagram, or what Builder A built.

Both builders can defend their schema as compliant with AD-7's *Rule* text; they cannot both be right about the AD's *title*. This is the "boundary stated but not made enforceable" case explicitly called out in the task: the spine asserts a guarantee its own prescribed DDL cannot deliver, and offers no trigger, constraint-exclusion table, or other mechanism to close the gap.

---

## 4. AD-9 — Single VM: unstated restart/resource/persistence semantics

AD-9 correctly rules out scale-to-zero PaaS, but says nothing about *intra-VM* robustness, which two compliant builders will fill in differently:

- **Restart policy.** Nothing in `docker-compose.yml`'s description mandates `restart: always`/`unless-stopped`. Builder A sets it (containers self-heal after an OOM-kill or crash); Builder B leaves the Compose default (`no`), reasoning that RNF-04 "dispensa disponibilidade 24/7" so manual `docker-compose up` after a crash is acceptable. If the API container crashes mid-afternoon on 23/11 (defesa day), A's app self-recovers within seconds; B's stays down until someone notices and SSHs in. Both configurations "run docker-compose with 3 services" per AD-9's letter.
- **Postgres data durability.** AD-9 never specifies a named/bind-mounted volume for Postgres. Builder A adds a named volume so data survives `docker-compose down`/VM reboot; Builder B, focused only on satisfying "3 services in docker-compose," leaves Postgres on the container's ephemeral writable layer — functionally identical until the first `docker-compose down -v`, `docker system prune`, or VM reboot wipes the whole synthetic dataset days before the defesa.
- **Model-singleton vs. multi-worker Uvicorn.** AD-4 says the ML artifact is "carregado uma vez no startup (singleton em memória)." Builder A runs Uvicorn with multiple workers to meet RNF-01's 5s budget under the ~200-student fan-out, and reads "singleton" as per-process (each worker loads its own copy — 4x model memory, but each still "loads once at startup, never per-request"). Builder B reads "singleton" literally as one global instance and pins `--workers 1`, which may not meet the RNF-01 budget under concurrent load but is unambiguously "one artifact in memory."
- **Resource contention with the offline training CLI.** AD-4's manual training run and the live Postgres/Uvicorn containers all share the same 2 OCPU/12GB (or the E2.1.Micro fallback's much smaller footprint) with no `mem_limit`/`cpus:` constraints mentioned. A training run kicked off at the wrong moment can starve or OOM-kill the live API/DB containers — nothing in AD-9 assigns resource limits or forbids training while the demo/live app is up.

None of these is forbidden by AD-9's Rule, and each pair of builders produces a materially different failure/recovery story for the exact demo-day scenario the whole document is optimized for.

---

## 5. Auth/JWT `[ASSUMPTION]` — expiry, refresh, storage all open

The Consistency Conventions table asserts only: "JWT bearer stateless ... sem sessão server-side `[ASSUMPTION]`." No expiry, no refresh mechanism, no client storage location.

- **Frontend storage.** Builder A stores the JWT in `localStorage` (simplest, matches "stateless," survives reloads/tabs, but is readable by any injected script — no CSP is specified anywhere in the spine to mitigate XSS exfiltration). Builder B stores it only in memory (a JS variable/React context), requiring re-login on every page reload — worse UX, but not contradicted by anything in the spine. These are incompatible frontend architectures for the same backend.
- **Expiry + refresh.** Builder A issues a long-lived token (days) specifically to avoid building refresh logic, since "sem sessão server-side" reads to them as "no server-side token state at all, ever." Builder B issues a short-lived token (minutes) and builds a `/auth/refresh` endpoint backed by a persisted refresh-token record — but no such endpoint appears in the `presentation/api/` route list (`/auth`, `/students`, `/followups`, `/observations`, `/launch`) and no refresh-token entity appears anywhere in AD-1's five domain groups or the Structural Seed ER diagram. Builder B's implementation therefore requires a new table and a new route the rest of the spine doesn't acknowledge, while Builder A's requires neither — yet both are defensible readings of "JWT bearer stateless."

---

## 6. Bonus finds (outside the requested focus areas, but genuine pairs)

### 6a. Is `TrajectorySnapshot` even persisted?
AD-2's Rule hedges: "se persistidos, a mesma requisição faz upsert idempotente" (*if* persisted). The directory listing (`domain/trajectory/ # TrajectorySnapshot, TrajectoryChange, ...`) implies both are first-class entities, but the Structural Seed ER diagram lists only `TrajectoryChange` as a table with relationships — `TrajectorySnapshot` never appears as an ER node. Builder A treats `TrajectorySnapshot` as purely transient/computed-per-request (never a table, since AD-1 requires "cada um dos 5 grupos... sua própria tabela" and Snapshot isn't clearly one of the five persisted groups or referenced by any FK). Builder B persists it as its own table "for FK stability," per AD-2's own justification ("dá estabilidade de FK"), and now has a table with no documented schema, no place in the ER diagram, and no consumer that references it by FK (unlike `TrajectoryChange`, which `FollowUpEvidence` and `TrajectoryChangeSource` do reference). Two builders end up with, respectively, zero and one extra table for the same concept.

### 6b. AD-8's scoping rule references a link the data model doesn't have
AD-8: "a query/repositório de `PedagogicalObservation` vinculado a um `FollowUp` sempre filtra por `FollowUp.responsible_user_id = current_user.id`." But the Structural Seed ER diagram shows `PedagogicalObservation` linked directly to `Student` and to `User` (as author), with **no FK from `PedagogicalObservation` to `FollowUp`** at all. "Vinculado a um FollowUp" therefore has no literal join path in the given schema.
- **Builder A** adds an FK `PedagogicalObservation.follow_up_id` (a schema addition the spine never mentions) so the filter is a direct join.
- **Builder B** reads "vinculado" as "for the same student as an open FollowUp" and implements the filter as `EXISTS (SELECT 1 FROM follow_up WHERE follow_up.student_id = observation.student_id AND follow_up.responsible_user_id = current_user.id)` — which leaks *every* observation for a student to *any* coordinator who happens to have their own, unrelated `FollowUp` open on that same student, including observations tied to a different coordinator's follow-up. This is a real privacy hole (the exact class of bug RF-22/RNF-12/AD-8 exist to prevent) produced by two equally literal readings of "vinculado a um FollowUp" over a schema that doesn't actually encode that link.

### 6c. AD-4's product/research boundary has no enforcement mechanism named
AD-4: the ML score "nunca aparece em endpoint ou schema de resposta do produto ... vive atrás de um boundary interno separado (`/research/*`)." Nothing says *how* this is checked — no contract test, no lint rule, no separate app/port. Builder A adds an automated test asserting `/students/*`/`/followups/*` response models never carry ML fields (schema introspection or golden-response diff) and mounts `/research` on a separate internal-only port/app instance not reachable through Nginx. Builder B relies on manual code review and mounts `/research` on the *same* FastAPI app instance as everything else, trusting only that Nginx's `proxy_pass` config for `/api` doesn't happen to also forward `/research` — which holds only as long as (a) Nginx config is correct and (b) Oracle Cloud's security list doesn't expose Uvicorn's raw port directly. Nothing in AD-9's VM description mandates a firewall rule restricting inbound access to Uvicorn's port, so Builder B's "boundary" is one misconfiguration away from being publicly reachable, and the spine gives no test or check that would catch either regression.

---

## Recommendations (would close every pair above)

1. Name the unique constraint/upsert key for `TrajectoryChange` (and state if `TrajectorySnapshot` is persisted at all).
2. State explicitly whether convergence can be retracted/downgraded once emitted, and what happens to dependent `FollowUpEvidence` rows if so.
3. Define the atomicity unit for the home-page fan-out: per-student transaction vs. whole-request transaction, and the partial-failure behavior.
4. Specify what `as_of()` wraps (system clock vs. a stored reference date) and require the synthetic generator's calendar to be anchored consistently with it.
5. Either accept AD-7's integrity guarantee is application-level only (and drop/soften the "nível de schema" claim), or change the DDL to per-type nullable FK columns + CHECK so schema-level enforcement is actually possible — pick one, because the current text promises the former's title with the latter's DDL being impossible.
6. Add restart policy, volume persistence, and Uvicorn worker-count decisions to AD-9 (or a new AD) — these directly determine demo-day failure recovery.
7. Pin down JWT expiry, refresh strategy (and whether a refresh-token table/route is in scope), and frontend storage location.
8. Either add the `PedagogicalObservation.follow_up_id` FK to the data model or rewrite AD-8's rule to name the actual join path, since "vinculado a um FollowUp" is currently unimplementable as literally stated.
9. Name a concrete enforcement mechanism (contract test, separate process/port, or firewall rule) for AD-4's product/research boundary — "never appears" is not self-enforcing.
