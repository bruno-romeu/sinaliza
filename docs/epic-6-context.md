# Epic 6 Context: Hospedagem e Publicação do Sistema

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The system is packaged and hosted on an always-on VM — no scale-to-zero, no cron — so that it is publicly reachable for demonstration and evaluation by the thesis committee by 2026-11-23. This matters because the project is a single-author TCC with a hard deadline: hosting must be reproducible on any VM, resilient to Oracle Cloud's free-tier capacity being unavailable, and never rely on scheduled jobs that would contradict the system's "no cron" architectural constraint.

## Stories

- Story 6.1: Containerized packaging of the three services (Postgres, FastAPI, Nginx/React)
- Story 6.2: Provisioning the always-on VM (Plan A/B)
- Story 6.3: Documented hosting contingency plan (Plan C)
- Story 6.4: Hosted system accessible for evaluation

## Requirements & Constraints

- The system must respond to user interactions within 5 seconds under normal conditions. For any hosting path exposed to cold-start (Plan C), this guarantee is explicitly waived unless a manual warm-up is performed first.
- Availability only needs to cover the development/demo window — no 24/7 SLA is required — but whatever is up must never scale to zero and must never depend on a scheduled keep-warm ping, since that would itself be a cron job.
- Stack is fixed: PostgreSQL, Python/FastAPI backend, React frontend, Scikit-Learn for ML — hosted on a free-tier service, with no scheduled/cron jobs anywhere in the system.
- Success is measured by: the full system being hosted and functional by the deadline, with all primary screens (Login, Home, Trajetória, Acompanhamento, Lançamento) working end-to-end; and no screen ever displaying an ML score, ranking, or risk KPI during the demo (this is a cross-epic final check, not newly introduced by this epic).

## Technical Decisions

- Single `docker-compose.yml` runs three services: Postgres, FastAPI/Uvicorn, and Nginx (serving the static React build + reverse-proxying `/api`). All three use `restart: unless-stopped` for automatic recovery after VM reboot or crash. Postgres data lives in a named Docker volume that survives container recreation/VM restarts — only an explicit `docker volume rm` deletes it, never a routine redeploy.
- Backend runs with a single Uvicorn worker (`--workers 1`), required because the ML inference artifact is an in-memory singleton not safe to share across multiple workers.
- No service may contain a cron/scheduler/background worker — trajectory/change calculation stays query-time-only, consistent with the rest of the system's architecture.
- Hosting plan is tiered, not sequential-fallback-as-afterthought: Plan A (Oracle Cloud Always Free, Ampere A1, 2 OCPU/12GB) is preferred but Plan B (`VM.Standard.E2.1.Micro`, 1 OCPU/1GB, if Ampere A1 capacity is unavailable in-region) is treated as an equally expected path, not a last resort — most 2026 reports show Ampere A1 provisioning failing for new tenancies in most regions. Plan B requires reduced Postgres `shared_buffers`, the single Uvicorn worker, and swap enabled to fit the tighter memory budget (~200 synthetic students/1 school year, no headroom for the ML artifact beyond its cached-inference use).
- Plan C (contingency, only if no Oracle VM provisions in time): Render free (backend) + Neon free (Postgres) + Vercel free (static frontend), same logical topology as A/B. Plan C requires a manual pre-warm (visiting the URL / health check a few minutes before a live demo) as a one-off human action — never a scheduled job. Plan C must be explicitly documented as exposing the 5-second response guarantee to cold-start outside of that pre-warm window; this is precisely why it is Plan C and not Plan A.
- Deploy process is manual SSH + `git pull` + `docker compose up --build` — sufficient for a single author, no CI/CD pipeline required or expected.
- Production Postgres backup is manual `pg_dump` done periodically (e.g., before relevant work sessions) to a location outside the VM — author discipline, not an application cron job, so it does not violate the no-scheduled-jobs constraint.
- No DNS/domain is required — public IP or a free dynamic DNS (e.g., DuckDNS) is acceptable; this is a deploy detail, not an architecture decision.
- No staging environment exists — the same `docker-compose.yml` runs locally (dev) and on the VM (prod/demo).
- VM monitoring is SSH + `docker compose logs` only; no observability dashboard is in scope.

## Cross-Story Dependencies

- Story 6.4's final acceptance criterion (no score/ranking/KPI ever shown) is a cross-epic verification, not something newly built in Epic 6 — it depends on the ML score boundary already enforced in Epic 5 (score never in `/students/*` or `/follow-ups/*`, no UI state for it).
- Story 6.2 (VM provisioning) and Story 6.3 (Plan C) are alternatives aimed at the same outcome (Story 6.4: a publicly reachable system) — Plan C is only activated if Story 6.2's Plan A/B provisioning fails to complete in time.
- Story 6.1's containerization (single Uvicorn worker, no cron, persistent volume) is a prerequisite baseline that both Plan A/B (6.2) and, logically, Plan C (6.3) must preserve.
