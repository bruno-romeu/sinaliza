---
title: 'Self-healing migration for synthetic_profile enum (FALLING_GRADES)'
type: 'bugfix'
created: '2026-10-15'
status: 'done'
baseline_commit: 'd1527f97b7c4c6da926f576b934f1bf9d05de51e'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `alembic/versions/0006_create_synthetic_generation_runs_table.py` was amended in place during Story 2.2 to add `FALLING_GRADES` to the `synthetic_profile` enum literal, violating the project's "never amend an already-applied migration" convention (epic-2-retro-item-2). Alembic tracks applied migrations by revision id, not file content, so any database that ran `alembic upgrade head` while revision `0006` still had its original 3-member enum (`STABLE`, `FALLING_ATTENDANCE`, `COMBINED_DETERIORATION`) will never re-run it, leaving that database's `synthetic_profile` Postgres type permanently stuck without `FALLING_GRADES`. Escalated from Epic 2's retro (2026-10-08), unaddressed across Epic 3 and Epic 4; recommended before Epic 5 since its ML pipeline reads from `synthetic_profile`-bearing tables.

**Approach:** Add a new migration `0010` whose `upgrade()` runs `ALTER TYPE synthetic_profile ADD VALUE IF NOT EXISTS 'FALLING_GRADES'` — idempotent, so it's a no-op on a database where `0006` already created the type with all 4 labels, and self-heals one where it didn't. `downgrade()` is a no-op (with a comment explaining why): Postgres has no native "drop enum value," and this migration's own addition is a safety backstop, not a schema element to reverse.

</frozen-after-approval>

## Implementation Notes

Oneshot: a single new migration file, no application/domain code changes. `backend/alembic/env.py` wraps every pending migration in one transaction per `alembic upgrade` invocation (not Alembic's per-migration-transaction default), so `ALTER TYPE ... ADD VALUE IF NOT EXISTS` runs inside `op.get_context().autocommit_block()` to commit immediately — otherwise a later migration using `'FALLING_GRADES'` in the same upgrade run would hit Postgres's "unsafe use of new value of enum type" restriction (code review finding, patched).

## Review Triage Log

- Quick-lens pass (1 lens run): revision-chain/label-parity check and `downgrade()`-is-a-documented-no-op check both clean — `high`/confirmed finding: `backend/alembic/env.py` wraps every pending migration in one transaction per `alembic upgrade` invocation (not Alembic's per-migration-transaction default), so a future migration using `'FALLING_GRADES'` in the same `upgrade head` run as this one would hit Postgres's "unsafe use of new value of enum type" restriction. **Patched**: `upgrade()` now runs the `ALTER TYPE` inside `op.get_context().autocommit_block()` to commit it immediately, independent of surrounding migrations' transaction boundaries. Re-verified: `test_migrations.py`'s full upgrade/downgrade/upgrade cycle still passes.

## Verification

**Commands:**
- `cd backend && uv run alembic upgrade head` -- expected: succeeds with no error, including when starting from a state where `0006` already applied with all 4 labels (no-op) and — to actually exercise the self-heal path — from a hand-simulated "old 0006" state (see manual check below).
- `cd backend && uv run pytest tests/test_migrations.py -q` -- expected: full upgrade/downgrade/upgrade cycle still passes, `synthetic_profile_labels` still equals `{member.value for member in SyntheticProfile}` after the new migration runs.
- `cd backend && uv run pytest -q` -- expected: no regressions (pre-existing unrelated failures in `tests/test_synthetic_dataset_split.py` are tracked separately in `docs/deferred-work.md`, not caused by this change).

**Manual checks (if no CLI):**
- Simulate the stuck-old-DB scenario once against the test database: stamp `alembic_version` at `0006`, manually recreate `synthetic_profile` with only the original 3 labels, then run `alembic upgrade head` and confirm `FALLING_GRADES` is present afterward via `SELECT enumlabel FROM pg_enum ... WHERE typname = 'synthetic_profile'`.

