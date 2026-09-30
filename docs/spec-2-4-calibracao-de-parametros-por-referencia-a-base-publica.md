---
title: 'Calibração de parâmetros por referência a base pública de dados educacionais (Story 2.4)'
type: 'feature'
created: '2026-09-30'
status: 'done'
route: 'full'
route_source: 'pinned'
review: 'none'
review_source: 'pinned'
lenses_ran: []
review_loop_iteration: 0
baseline_commit: 'c3afd41dc985c33b71f1373869ef493a3937fcaa'
context:
  - '{project-root}/docs/epic-2-context.md'
  - '{project-root}/docs/research/technical-bases-publicas-dados-educacionais-calibr-2026-09-17/research.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The synthetic generator (Stories 2.1/2.2/2.5) needs named constants for attendance, grades, assignment delivery, profile mix and dropout — and `research.md` establishes that only *one* of those families has a real Brazilian public source. Inventing the rest silently, or citing a source that measures something else, would turn RNF-13's provenance requirement into decoration.

**Approach:** One pure module, `backend/app/synthetic/calibration.py`, where every constant is an instance of a frozen `CalibrationParameter` carrying `value`, `definition`, `source`, `source_refs`, `confidence`, `kind` and `used_by_generator`. Provenance becomes data the test suite asserts over, not a comment that rots. Three research verdicts map to three distinct `kind`s, so "calibrated" and "invented" can never be confused by a reader or by a downstream story.

## Boundaries & Constraints

**Always:** every exported constant is a `CalibrationParameter` with a non-empty `source` and a `Confidence` member — including the ones with no source, whose `source` states the absence and whose `confidence` is `Confidence.NONE`; abandonment (EF, Censo 2023) and evasion (EM, Censo 2023) are two separate parameters with two separate `definition` texts and are never added together; `ParameterKind.PUBLIC_REFERENCE` entries (PNAD adjusted net attendance, SAEB proficiency) carry `used_by_generator=False` — they are order-of-magnitude context, never generation inputs; `ALL_PARAMETERS` is derived by introspecting the module namespace so a new constant cannot escape the provenance tests; profile keys are plain strings, so this module never imports Story 2.2's enum.

**Never:** any network call, database access, file read, or import of `sqlalchemy`/`psycopg`/`httpx`/`fastapi`/`app.infrastructure`/`app.synthetic.generate` — the public base is consulted offline, by a human, at calibration time only (AC 2); PNAD's adjusted net attendance used as the daily-attendance parameter (it measures access to school, not presence in a classroom — it would inflate the simulated rate); the 0–10 grade distribution presented as calibrated data (no Brazilian public source publishes report-card grades); any recorte by gender or race as a generation parameter (`AGENTS.md` §Features — no sensitive attribute without necessity), even though `research.md` publishes them; any file under `backend/app/` other than `synthetic/calibration.py` and a byte-empty `synthetic/__init__.py`.

## Parameter Provenance Matrix

*(Replaces the template's I/O Matrix — this story has no HTTP surface, no UI and no database writes.)*

| Parameter | Value | Source | Confidence | Kind |
|---|---|---|---|---|
| `ABANDONMENT_RATE_EF` | 0.030 | Censo Escolar 2023 — abandono, Ensino Fundamental [20][21] | HIGH | CALIBRATED |
| `EVASION_RATE_EM` | 0.059 | Censo Escolar 2023 — evasão (taxa de transição), Ensino Médio [20][21] | HIGH | CALIBRATED |
| `FAILURE_RATE_EM` | 0.039 | Censo Escolar 2023 — reprovação, Ensino Médio [20][21] | HIGH | CALIBRATED |
| `COMBINED_FAILURE_RATE_EM_FIRST_YEAR` | (0.164, 0.213) | FCC/Censo Escolar — insucesso (reprovação+abandono), 1º ano EM, 2023 e 2019 [20] | HIGH | CALIBRATED |
| `SAEB_INSUFFICIENT_SHARE_MATH_FINAL_YEAR` | 0.59 | SAEB 2023, nível "Insuficiente" em Matemática, último ano da ed. básica [23] | MEDIUM | PUBLIC_REFERENCE |
| `PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EF` | (0.989, 1.000) | PNAD Contínua — frequência líquida ajustada, EF [9] | MEDIUM | PUBLIC_REFERENCE |
| `PNAD_ADJUSTED_NET_ATTENDANCE_RATE_EM` | 0.806 | PNAD Contínua — frequência líquida ajustada, EM [9] | MEDIUM | PUBLIC_REFERENCE |
| `GRADE_DISTRIBUTION` | 4 bands over 0–10, shares 0.59/0.24/0.13/0.04 | Only the 0.59 is anchored (SAEB proxy [23]); bands and remaining shares are drawn | MEDIUM | DESIGN_ASSUMPTION |
| `DAILY_ATTENDANCE_RATE_BASELINE` | 0.95 | No Brazilian public base measures daily presence (research §3) | NONE | DESIGN_ASSUMPTION |
| `DAILY_ATTENDANCE_RATE_AT_RISK_FLOOR` | 0.60 | idem | NONE | DESIGN_ASSUMPTION |
| `ASSIGNMENT_NON_DELIVERY_RATE_BASELINE` | 0.08 | No Brazilian public base measures assignment delivery (research §3) | NONE | DESIGN_ASSUMPTION |
| `ASSIGNMENT_PARTIAL_DELIVERY_RATE_BASELINE` | 0.07 | idem | NONE | DESIGN_ASSUMPTION |
| `ASSIGNMENT_NON_DELIVERY_RATE_AT_RISK_CEILING` | 0.50 | idem | NONE | DESIGN_ASSUMPTION |
| `SYNTHETIC_PROFILE_PROPORTIONS` | STABLE .70 / FALLING_ATTENDANCE .12 / FALLING_GRADES .08 / COMBINED_DETERIORATION .10 | No source measures "share of students with a deteriorating trajectory"; deliberately enriched vs. Censo rates | NONE | DESIGN_ASSUMPTION |
| `GRADE_SCALE_MIN` / `GRADE_SCALE_MAX` | 0.0 / 10.0 | Epic 1 `grades.value` CHECK (migration 0003, `data-model.md`) — a schema invariant, not calibration | HIGH | SYSTEM_INVARIANT |

</frozen-after-approval>

## Code Map

- `backend/app/domain/grade.py` -- `Grade.value` is `Decimal` on 0.0–10.0; grade-band bounds mirror that type
- `backend/app/domain/assignment_submission.py` -- tri-state `DELIVERED`/`NOT_DELIVERED`/`PARTIAL`; the three assignment parameters cover exactly those states (delivered is derived: `1 - non_delivery - partial`)
- `backend/app/domain/attendance.py` -- `AttendanceStatus` is tri-state; this story calibrates only present-vs-absent, never the justified/unjustified split (RF-11 counts them equally)
- `backend/app/synthetic/__init__.py` -- NEW, **must stay byte-empty** (0 bytes, no docstring): Story 2.1 creates the same file on a sibling branch; byte-identical empty is what makes the branches merge cleanly
- `backend/app/synthetic/calibration.py` -- NEW, the entire production deliverable
- `backend/tests/test_synthetic_calibration.py` -- NEW, the entire test deliverable
- `backend/tests/conftest.py` -- **do not touch**; it opens a Postgres session fixture, but this module needs none. Note it forces `TEST_DATABASE_URL` and defaults to port 5433 — run pytest with `TEST_DATABASE_URL` pointed at 5435 in this worktree
- `backend/app/synthetic/generate.py`, `backend/app/infrastructure/db/models.py`, `backend/alembic/**`, `backend/tests/test_migrations.py`, `frontend/**`, `docs/sprint-status.yaml` -- **owned by other work; do not create or modify**

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/synthetic/__init__.py` -- create as a 0-byte file -- merge-safety with Story 2.1
- [ ] `backend/app/synthetic/calibration.py` -- `Confidence` + `ParameterKind` enums, frozen `CalibrationParameter` and `GradeBand` dataclasses, the 16 constants of the provenance matrix, `ALL_PARAMETERS`/`PARAMETERS_BY_NAME` derived by namespace introspection -- provenance as testable data (RNF-13)
- [ ] `backend/tests/test_synthetic_calibration.py` -- registry completeness; every parameter has source+confidence+definition and `name` equal to its module attribute; the unsourced three flagged `DESIGN_ASSUMPTION`; abandonment vs. evasion distinct and never summed; `PUBLIC_REFERENCE` entries not generator inputs; bounds (rates in [0,1], grades in [0,10], shares summing to 1.0); frozen/immutable; subprocess import with sockets blocked and no DB env vars

**Acceptance Criteria:**
- Given any exported generation parameter, when inspected, then it reports a non-empty public source (or an explicit statement that none exists) and a confidence level (RNF-13, AC 1).
- Given the module, when imported in a process with no database, no environment configuration and sockets disabled, then it imports successfully and loads no driver, HTTP client or ORM module — the public base is consulted offline only (AC 2).
- Given a parameter with no Brazilian public equivalent (daily attendance, assignment non-delivery, 0–10 grade distribution), when inspected, then its `kind` is `DESIGN_ASSUMPTION` and it is never reported as calibrated data (AC 3).
- Given the module, when inspected, then it contains no student name, enrollment number, phone, address or any real student datum — only aggregate rates (AC 4, RNF-07).

## Design Notes

**Why `kind` has four members, not a boolean.** `research.md` reaches three different verdicts, and a two-valued flag collapses two of them. `PUBLIC_REFERENCE` exists specifically so PNAD's 98.9–100% can be *recorded* — it is the number a reviewer will reach for — while `used_by_generator=False` states in data that it is not the attendance parameter. `SYSTEM_INVARIANT` keeps the 0–10 scale bounds out of the "calibrated" bucket: they come from Epic 1's CHECK constraint, not from INEP.

**Why the design assumptions carry `Confidence.NONE`.** "Low" would imply a weak measurement. There is no measurement. `NONE` is a level (the tests still require one), and it reads as the refusal it is.

**Why profile proportions are enriched.** Censo's ~3% abandono would give ~6 deteriorating students in a 200-student base — too few for Epic 3 to validate a convergence rule against or for Epic 5 to train on. The 30% non-stable share is a deliberate modelling choice, recorded as such; the real rate stays visible in `ABANDONMENT_RATE_EF` so the inflation is auditable rather than hidden.

```python
GRADE_DISTRIBUTION = CalibrationParameter(
    name="GRADE_DISTRIBUTION",
    value=(GradeBand("Insuficiente", Decimal("0.0"), Decimal("4.9"), 0.59), ...),
    kind=ParameterKind.DESIGN_ASSUMPTION,   # NOT calibrated — only the 0.59 is anchored
    confidence=Confidence.MEDIUM,
    source="SAEB 2023 ... usado como proxy categórico; a escala 0–10 é desenhada, não observada",
    source_refs=("[23]",),
)
```

## Assumptions

Recorded because this story ran non-interactively, with no human available at the workflow checkpoints:

1. **Checkpoint 1 (spec approval) auto-approved.** No human was available; the spec was self-reviewed against the READY FOR DEVELOPMENT standard instead.
2. **Review route pinned to `none`.** `epic-2-plan.md` §Ciclo por story runs `bmad-code-review` and an independent walkthrough as separate steps after the PR, so an in-workflow review pass would duplicate them.
3. **`docs/sprint-status.yaml` not updated** (key `2-4-calibração-...`), even though the workflow would normally write status there — the orchestrating session owns that file exclusively.
4. **`docs/epic-2-context.md` reused as-is** rather than recompiled. It is valid for Epic 2 and its "Calibration Reality" section was hand-authored for this story; recompiling would overwrite it.
5. **Numeric values for the unsourced parameters were chosen by this agent** (0.95 / 0.60 attendance; 0.08 / 0.07 / 0.50 assignment; the three non-anchored grade-band shares; the four profile shares). They are plausible, not measured. The 75% legal attendance threshold for approval (LDB 9.394/1996, art. 24, VI) is cited in the module's rationale only as a *normative* anchor for the order of magnitude — it is a legal rule, not a statistic, and is not a calibration source.
6. **Gender and race recortes from `research.md` are deliberately excluded.** Encoding a sensitive attribute into a generator whose output trains an ML model needs a justification this story does not have (`AGENTS.md` §Features).
7. **Profile keys are strings, not Story 2.2's enum.** The parity check between these keys and `SyntheticProfile` belongs to Story 2.2 and is deferred to it.
8. **`DATASET_SPLIT` proportions are out of scope** — `epic-2-plan.md` assigns that named constant to Story 2.3.

## Implementation Notes

Implemented exactly as planned, three new files and nothing else:
`backend/app/synthetic/__init__.py` (0 bytes), `backend/app/synthetic/calibration.py`,
`backend/tests/test_synthetic_calibration.py`. All 16 parameters of the provenance matrix
exist; 13 carry `used_by_generator=True` and 3 (`SAEB_*`, both `PNAD_*`) carry `False`.

**Two deviations from the plan, both small:**

1. `CalibrationParameter` is `@dataclass(frozen=True, eq=False)`, not plain `frozen=True`.
   With structural equality the generated `__hash__` blows up on
   `SYNTHETIC_PROFILE_PROPORTIONS`, whose `value` is a `MappingProxyType` — the parameter
   could not go into a `set`. Identity semantics are correct for module-level singletons.
2. A `test_sourced_values_match_the_published_statistics` was added beyond the planned list,
   pinning the seven values that claim a citation. Without it a silent numeric edit would
   leave the `source` text pointing at a statistic the value no longer reports.

**The offline/no-network test was negative-controlled**, not just run green: injecting a
forbidden module into the probe's `sys.modules` fails it with
`AssertionError: forbidden modules imported: ['app.synthetic.generate']`, and calling
`socket.create_connection` inside the probe fails it too. Replacing `socket.socket` also
makes `ssl`/`http.client` unimportable inside the probe, so a network stack cannot load at all.

**Verified:** `pytest` 155/155 (63 pre-existing + 92 new), against Postgres on port 5435;
bare `python -c "import app.synthetic.calibration"` exits 0 with `DATABASE_URL`,
`TEST_DATABASE_URL` and `JWT_SECRET` all unset and no database reachable;
`backend/app/synthetic/__init__.py` is exactly 0 bytes; `git status` shows only the three
new files plus this spec.

**Deferred:**

- Key↔enum parity between `SYNTHETIC_PROFILE_PROPORTIONS` and Story 2.2's `SyntheticProfile`
  cannot be tested from here (the enum does not exist yet). Story 2.2 must add that assertion.
- The class-prevalence caveat (the profile mix is deliberately enriched ~10x above the Censo
  abandonment rate) is recorded in the parameter's `rationale`; Epic 5 still has to surface it
  when it reports metrics.
- `research.md`'s own open questions (SAEB primary PDF unreadable, Censo micro-data
  granularity disputed) are unchanged — they bound the confidence levels recorded here and
  were not re-investigated by this story.

## Verification

**Commands:**
- `cd backend && TEST_DATABASE_URL=postgresql+psycopg://sinaliza:sinaliza@localhost:5435/sinaliza_test ./.venv/Scripts/python.exe -m pytest -q` -- expected: the 63 pre-existing tests still pass plus the new calibration tests, zero failures
- `cd backend && ./.venv/Scripts/python.exe -c "import app.synthetic.calibration"` -- expected: exits 0 with no `DATABASE_URL`/`JWT_SECRET` set and no Postgres reachable
- `wc -c backend/app/synthetic/__init__.py` -- expected: exactly `0`
- `git status --short` -- expected: only `backend/app/synthetic/{__init__,calibration}.py`, `backend/tests/test_synthetic_calibration.py` and this spec
