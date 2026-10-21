# deploy/

Operator tooling for provisioning and verifying the always-on VM that hosts
Sinaliza (Story 6.2, AD-9 Plan A/B). This directory contains documentation
and plain-bash scripts a human runs manually — nothing here is invoked by
CI, a cron job, or a scheduled task.

Plan A (Oracle Cloud Ampere A1) and Plan B (`VM.Standard.E2.1.Micro`
fallback) tooling is below. Plan C (Render/Neon/Vercel contingency,
activated only if no Oracle VM provisions in time) is documented
separately in `plan-c-contingency-runbook.md` — see that section below.

## Contents

- **`vm-provisioning-runbook.md`** — start here. Step-by-step Oracle Cloud
  console + SSH instructions: create the VM (Plan A, falling back to Plan B
  on capacity failure), open ports, install Docker, clone the repo,
  configure `.env`, apply Plan B tuning if applicable, and
  `docker compose up --build -d`.
- **`postgres-plan-b.conf`** — the three Postgres settings Plan B needs
  (reduced `shared_buffers`, `work_mem`, `max_connections`) with rationale.
  Not parsed by any script — a human copies these into the
  `docker-compose.override.yml` shown in the runbook. **Plan A does not
  need this file.**
- **`enable-swap.sh`** — idempotent script that creates and activates a 2GB
  swapfile, persisted via `/etc/fstab`. **Plan B only.**
- **`verify-always-on.sh`** — run against the deployed stack (locally or
  over SSH) to confirm all 3 services are `Up`/`running` with
  `restart: unless-stopped` honored (RNF-04, no scale-to-zero).
- **`smoke-test.sh`** — run against a live base URL to confirm responses
  complete within 5 seconds (RNF-01).

## Usage at a glance

```bash
# After provisioning + deploying per the runbook:
./deploy/verify-always-on.sh ubuntu@<vm-ip>
./deploy/smoke-test.sh http://<vm-ip>
```

See `vm-provisioning-runbook.md` for full context on each step.

## Plan C (contingency) — Story 6.3

Activated only if no Oracle VM (Plan A or B, above) provisions in time for
the deadline. No Render/Neon/Vercel account exists in this environment —
these files are documentation and operator scripts only, not a live
deployment.

- **`plan-c-contingency-runbook.md`** — start here if Plan C is activated.
  Neon (Postgres), Render (backend), Vercel (frontend) setup steps, the
  manual pre-warm procedure, and an explicit statement of RNF-01's
  cold-start waiver on this plan — read that section first.
- **`vercel.json`** — Vercel rewrite config (`/api/*` → the Render backend
  URL) so the frontend's existing same-origin `/api` calls keep working
  across two different hosts, with no CORS config and no frontend code
  change.
- **`prewarm.sh`** — run by hand a few minutes before a live demo on
  Plan C, to force the Render/Neon cold start to resolve before the
  audience sees it. Never scheduled — see the script's own header.

```bash
# Before a live demo on Plan C only:
./deploy/prewarm.sh https://<render-backend-url>
```
