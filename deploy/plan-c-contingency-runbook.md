# Plan C — Hosting Contingency (Render + Neon + Vercel, all free tier)

Story 6.3 (AD-9). This is a **contingency runbook, not a preferred path**. No
Render, Neon, or Vercel account exists in this environment — this document
and the scripts beside it have not been exercised against a live deployment.
They describe exactly what a human operator does if Plan A/B (Story 6.2,
`deploy/vm-provisioning-runbook.md`) does not produce a running Oracle Cloud
VM in time for the 2026-11-23 deadline.

> **RNF-01 WAIVER — READ THIS FIRST**
>
> Plan C's free-tier services (Render, Neon, Vercel) scale to zero or sleep
> after inactivity. The first request after a period of inactivity pays a
> **cold-start penalty that can exceed 5 seconds**. Stories 6.1/6.2 guarantee
> a sub-5-second response (RNF-01) under normal conditions; **Plan C does
> not hold that guarantee except immediately after the manual pre-warm
> described in Section 5.** This is the one and only reason Plan C exists as
> a third tier instead of being folded into Plan A/B — a VM with
> `restart: unless-stopped` never sleeps, so RNF-01 holds unconditionally;
> a free-tier PaaS does sleep, so RNF-01 only holds inside a pre-warmed
> window. If you are reading this while Plan A or B is still viable, use
> those instead.

## 0. Activation criteria

Activate Plan C only when **all** of the following are true:

1. Plan A (Oracle Cloud Ampere A1) failed to provision — capacity error, or
   the tenancy/region never granted the shape.
2. Plan B (`VM.Standard.E2.1.Micro` fallback) also failed to provision, or
   there is not enough time left before the deadline to complete Plan B's
   provisioning + deploy + verification steps.
3. The 2026-11-23 evaluation deadline is close enough that waiting longer
   for Oracle capacity risks having nothing hosted at all.

Plan C is never a parallel or preferred deployment target — it exists only
so the deadline does not depend on a single provider.

## 1. Topology (same logical shape as Plan A/B)

| Role | Plan A/B | Plan C |
|------|----------|--------|
| Database | Postgres container on the VM | **Neon** free Postgres project |
| Backend | FastAPI/Uvicorn container on the VM | **Render** free Web Service (built from `backend/Dockerfile`) |
| Frontend | Nginx container on the VM | **Vercel** free static deployment (built from `frontend/`) |

All three roles are unchanged from `docker-compose.yml`'s service
definitions — Plan C only changes *who hosts each role*, not the
application code or build artifacts. No code under `backend/app` or
`frontend/src` is modified for Plan C.

## 2. Step 1 — Neon (Postgres)

1. Create a free Neon project (https://neon.tech) — region closest to your
   demo audience is not critical; latency between Render and Neon matters
   more than audience distance.
2. Create a database named `sinaliza` (or accept Neon's default and record
   the name — it only needs to match what you put in `DATABASE_URL` below).
3. Copy the connection string Neon shows you. Neon offers both a
   **pooled** connection string (hostname contains `-pooler`) and a
   **direct** one — use the **direct** string. This backend runs a single
   Uvicorn worker with SQLAlchemy's own small connection pool (AD-3), so it
   does not need Neon's external PgBouncer pooler, and the pooled endpoint
   can behave differently for session-level features the app may rely on
   (e.g. prepared statements). It looks like:
   ```
   postgresql://<user>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
   ```
4. Rewrite it for SQLAlchemy's `psycopg` (v3) driver, matching
   `backend/.env.example`'s `DATABASE_URL` format — add `+psycopg` after
   `postgresql` and keep `?sslmode=require` (Neon requires TLS; the vanilla
   `docker-compose.yml` Postgres container does not need this flag, Neon
   does):
   ```
   postgresql+psycopg://<user>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
   ```
5. Keep this value — it is the `DATABASE_URL` Render needs in Step 2.
   Neon's free tier auto-suspends the compute endpoint after inactivity;
   the next query wakes it, contributing to the same cold-start window the
   RNF-01 waiver above describes. No action needed here — it is accounted
   for by the pre-warm procedure (Section 5).

Nothing about Alembic migrations changes: `backend/docker-entrypoint.sh`'s
`alembic upgrade head` runs against whatever `DATABASE_URL` Render gives
the container, Neon included.

## 3. Step 2 — Render (backend)

1. Create a free Render account, then a new **Web Service**.
2. Connect it to this repository, select **Docker** as the runtime.
3. Set the build context to the repo root and the Dockerfile path to
   `backend/Dockerfile` — the same two settings `docker-compose.yml`
   already encodes (`build.context: .`, `build.dockerfile: backend/Dockerfile`).
   Do not use Render's auto-detected root-`Dockerfile` default; this repo's
   backend Dockerfile expects a repo-root build context (it `COPY`s
   `backend/...` paths), exactly as it does for `docker compose build`.
4. Set these environment variables, mirroring `backend/.env.example`:
   - `DATABASE_URL` = the Neon connection string from Section 2, step 4.
   - `JWT_SECRET` = a long random value (generate one; never reuse a dev
     value in anything demo-facing).
   - `JWT_EXPIRE_MINUTES` = `60` (or your preferred value).
5. Leave the service on Render's free plan. **This is exactly what causes
   the cold-start exposure documented in the RNF-01 waiver above** — free
   Render services spin down after a period of no traffic and take a
   noticeable cold-start on the next request.
6. Deploy. Render builds the image via `backend/Dockerfile` and runs its
   `ENTRYPOINT` unmodified (`alembic upgrade head` then
   `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`) — the
   single-worker constraint (AD-3, the in-memory ML artifact singleton) is
   preserved because the Dockerfile and entrypoint are reused byte-for-byte.
7. Record the public URL Render assigns the service (e.g.
   `https://sinaliza-backend.onrender.com`) — it is needed in Step 3 and
   for the pre-warm script in Section 5.
8. Verify once: `curl https://<render-url>/openapi.json` should return
   the OpenAPI schema (this route needs no auth, matching
   `deploy/smoke-test.sh`'s Plan A/B check) — but note the first call after
   a deploy may itself be slow (cold start), so a slow *first* response here
   is expected, not a failure.

## 4. Step 3 — Vercel (frontend)

The split-origin problem: in Plan A/B, Nginx (`frontend/nginx.conf`)
reverse-proxies `/api/*` to the backend container on the same host, so
`frontend/src/api/client.ts`'s `API_BASE = '/api'` is always a same-origin
relative path and the backend never needs CORS configuration
(`frontend/vite.config.ts`'s own comment states this explicitly). On Plan C,
frontend (Vercel) and backend (Render) are two different hosts — the same
problem, solved the same way, at the platform level instead of in Nginx:

1. Create a free Vercel account, then a new project pointed at this repo's
   `frontend/` directory as the project root.
2. Build command: Vercel's build environment only checks out `frontend/`,
   so it has no access to `backend/openapi.json` the way the monorepo
   Docker build context does (`frontend/Dockerfile` generates it from
   `backend/app` in an earlier stage). `frontend/package.json`'s
   `generate:api-types` script (`openapi-typescript ../backend/openapi.json
   -o src/api/schema.d.ts`) hardcodes that local path, so do not run it
   as-is on Vercel. Instead, override the build command in the Vercel
   project settings to call `openapi-typescript` directly against the
   **Render** backend's live schema URL — `openapi-typescript` accepts an
   HTTP(S) URL as its input in place of a local file path:
   ```
   npx openapi-typescript https://<render-backend-url>/openapi.json -o src/api/schema.d.ts && npm run build
   ```
   This is a Vercel build-command override only — no change to
   `frontend/package.json` or any file under `frontend/src`.
3. Output directory: `dist` (matches `frontend/Dockerfile`'s
   `COPY --from=build /frontend/dist`).
4. Copy `deploy/vercel.json` into `frontend/vercel.json` (or configure the
   equivalent rewrite in the Vercel dashboard) and replace
   `<render-backend-url>` with the real Render URL from Section 3, step 7.
   This rewrite is what lets the frontend's unmodified `API_BASE = '/api'`
   keep working — Vercel transparently forwards `/api/*` requests to the
   Render backend, so the browser never makes a cross-origin request and the
   backend never needs CORS headers added.
5. Deploy. Record the public URL Vercel assigns (e.g.
   `https://sinaliza.vercel.app`) — this is the URL you give to the
   evaluation committee and the one you pre-warm before a demo.

## 5. Manual pre-warm before a live demonstration

**This is a human action performed once, by hand, a few minutes before a
live demo. It is never a scheduled job, cron entry, systemd timer, or CI
schedule of any kind — doing so would violate RNF-06/AD-9's no-cron
constraint exactly the way a keep-warm ping would.**

Shortly (a few minutes) before starting a live demonstration on Plan C:

```bash
./deploy/prewarm.sh https://<render-backend-url>
# and, separately, visit the Vercel frontend URL in a browser once
```

`deploy/prewarm.sh` hits the backend's unauthenticated `/openapi.json`
route directly on the Render URL (no `/api` prefix — that prefix only
exists behind the Vercel rewrite from Section 4; calling Render directly
means no prefix) to force Render and Neon to wake up (the backend's first
request triggers the Neon connection too, via `alembic`'s already-run
migration path and the first real query). Confirm it reports a successful response
before starting the demo. If it reports a connection failure, the service
may still be deploying or down — do not proceed to the demo until it
reports success.

Visiting the Vercel frontend URL once in a browser similarly warms any
Vercel-side cold path, though static hosting rarely needs this — Render and
Neon are the services that actually sleep.

## 6. What Plan C deliberately does not include

- No CI/CD pipeline triggers the pre-warm or any deploy step — deploys on
  Render/Vercel are triggered manually (via the dashboard or a `git push`
  the operator makes), consistent with Plan A/B's "manual SSH + git pull"
  deploy philosophy (`docs/epic-6-context.md`).
- No cron job, systemd timer, GitHub Actions schedule, or third-party
  "keep my Render service awake" ping service is used or recommended, even
  though such services exist and are commonly suggested for this exact
  problem — using one would reintroduce a scheduled job and violate RNF-06.
- No CORS middleware is added to `backend/app` — the Vercel rewrite
  (Section 4) solves the split-origin problem without it.
