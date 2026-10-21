---
title: 'Story 6.3: Plano de contingência de hospedagem (Plano C) documentado'
type: 'feature'
created: '2026-10-20'
status: 'done'
baseline_commit: 'bbdb155bba5817d6237c7db7a8a24f90c8b805f5'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: ['{project-root}/docs/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Stories 6.1/6.2 give a `docker compose up --build` package and an Oracle Cloud VM runbook, but both depend on a single provider (Oracle Cloud Always Free) whose capacity is reported unreliable for new tenancies. If no Oracle VM provisions by the 2026-11-23 deadline, nothing documents an alternative path to a publicly reachable system, and nothing warns that such a path would expose RNF-01's 5-second guarantee to cold-start.

**Approach:** Produce a human-executable Plan C contingency runbook (Render free for the backend, Neon free for Postgres, Vercel free for the static frontend, same logical topology as Plan A/B) plus the one small piece of config the split-origin topology actually requires (a Vercel rewrite so the frontend's existing same-origin `/api` calls still work without touching application code) and a manual pre-warm/health-check script a human runs once, by hand, a few minutes before a live demo. No Render/Neon/Vercel account exists in this environment — this story delivers documentation and operator scripts, not a live deployment.

## Boundaries & Constraints

**Always:**
- Document Plan C as activated only when no Oracle VM (Plan A/B, Story 6.2) provisions by the deadline — a contingency, not a parallel or preferred path.
- Preserve the same logical topology as Plan A/B: one service for the Postgres database, one for the FastAPI backend, one for the static React frontend.
- State explicitly and prominently that RNF-01's 5-second guarantee is waived outside a manual pre-warm window on Plan C — this is the documented reason it is Plan C, not Plan A (epic-6-context.md).
- Document the pre-warm/health-check step as a one-off human action performed shortly before a live demo — never a scheduled job, cron, or keep-warm ping (RNF-06, AD-9).
- Reuse Story 6.1's `backend/Dockerfile`, `frontend/Dockerfile`, and `backend/docker-entrypoint.sh` (migrate-then-serve, single Uvicorn worker) unmodified — Render/Vercel build from the same images/artifacts, no new build logic.

**Never:**
- No Render, Neon, or Vercel account is created, and no deployment is attempted in this session — do not fabricate having deployed anything.
- No changes to `backend/app`, `backend/Dockerfile`, `backend/docker-entrypoint.sh`, or `frontend/src` — Plan C must work against the stack as Story 6.1 shipped it.
- No CORS middleware added to the backend — the split-origin problem (frontend and backend now on different hosts) is solved via a platform-level rewrite/proxy config, mirroring `frontend/nginx.conf`'s approach, not via application code.
- No scheduled/cron keep-warm mechanism anywhere, including inside the pre-warm script itself (it must be a script a human invokes, not one that invokes itself).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Oracle VM provisioned in time | Story 6.2's runbook succeeds (Plan A or B) | Plan C is not activated; runbook documents this as the normal outcome | N/A |
| Oracle VM fails to provision by deadline | Plan A and Plan B both fail (capacity, access, or time) | Operator follows `deploy/plan-c-contingency-runbook.md`: Neon DB, Render backend, Vercel frontend, in that order | Runbook names the dependency order and what breaks if skipped (backend needs `DATABASE_URL` before it can start; frontend's rewrite needs the Render URL before it can route) |
| Live demo on Plan C | Operator about to start a demonstration | Operator runs `deploy/prewarm.sh <render-backend-url>` a few minutes beforehand, confirms a warm response, then proceeds | If the pre-warm request itself times out or errors, script reports it clearly so the operator knows the service is still cold/unavailable |
| Live demo on Plan C, no pre-warm performed | Operator skips the manual pre-warm | Runbook states explicitly: RNF-01's 5s guarantee does not hold; first request(s) may exceed it due to free-tier cold start | Documented as an accepted, explicit risk of Plan C — not silently assumed away |
| Frontend calling backend across origins | Vercel-hosted static frontend, Render-hosted backend, different domains | `deploy/vercel.json` rewrites `/api/*` to the Render backend URL, so `frontend/src/api/client.ts`'s existing `API_BASE = '/api'` keeps working with zero frontend code changes | If the rewrite destination is misconfigured, the runbook's verification step (`prewarm.sh` against the Vercel URL's `/api/openapi.json`) surfaces it as a failed/non-2xx check |

</frozen-after-approval>

## Code Map

- `docs/epic-6-context.md` -- source of the Plan A/B/C tiering, RNF-01 (5s)/RNF-06 (no cron) constraints, and the exact Plan C framing ("manual pre-warm... never a scheduled job"; "explicitly documented as exposing the 5-second response guarantee to cold-start outside of that pre-warm window") to preserve verbatim.
- `deploy/vm-provisioning-runbook.md`, `deploy/README.md` -- Story 6.2's runbook style/format and the `deploy/` directory convention this story's files join; `deploy/README.md` currently states "Plan C ... is Story 6.3 and is not covered here" — this story updates that line once Plan C exists.
- `docker-compose.yml` -- the three-service logical topology (postgres / backend / frontend) Plan C must mirror one-for-one onto Neon / Render / Vercel; env var names (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`) are reused as Render's environment variables.
- `backend/Dockerfile`, `backend/docker-entrypoint.sh` -- reused unmodified; Render builds from `backend/Dockerfile` (repo-root build context, same as Compose) and the entrypoint's `alembic upgrade head` then `uvicorn --workers 1` requires no change to run on Render.
- `backend/.env.example` -- source of env var names/comments Plan C's Render environment variables mirror; `DATABASE_URL` format (`postgresql+psycopg://...`) must gain `?sslmode=require` for Neon.
- `frontend/Dockerfile`, `frontend/nginx.conf` -- shows the existing reverse-proxy pattern (`/api/` -> backend, strips nothing extra) that Vercel's rewrite must replicate; Vercel does not build via this Dockerfile (no Nginx step on a static host) — Vercel builds the Vite SPA directly (`npm ci && npm run generate:api-types && npm run build`), reusing only the build stage's commands, not the Dockerfile itself.
- `frontend/src/api/client.ts:86` -- `const API_BASE = '/api'`, a same-origin relative path with no env-based override; this is why a Vercel rewrite (not a code change) is the only way to keep it working once frontend and backend are on different hosts.
- `frontend/vite.config.ts:4-17` -- confirms no CORS middleware exists anywhere in the stack by design ("the frontend never needs CORS configuration in either environment"); Plan C's rewrite preserves that invariant instead of adding CORS.
- `deploy/smoke-test.sh` -- Story 6.2's RNF-01 pass/fail checker; Plan C's `prewarm.sh` is a distinct, simpler script (no pass/fail threshold logic to reuse) because its purpose is triggering a cold-start wake-up before a demo, not gating a verification step.

## Tasks & Acceptance

**Execution:**
- [x] `deploy/plan-c-contingency-runbook.md` -- write the Plan C runbook: activation criteria (Plan A/B failed by deadline), Neon setup (create free project, copy the direct — not pooled — `DATABASE_URL`, append `?sslmode=require`), Render setup (new Web Service from `backend/Dockerfile`, repo-root build context, env vars mirroring `.env.example`), Vercel setup (new static project from `frontend/`, build command overridden to generate API types from the live Render `/openapi.json` instead of `npm run generate:api-types`'s hardcoded local path, then `npm run build`, output dir `dist`, apply `deploy/vercel.json`), the manual pre-warm procedure before a live demo, and a prominent, unmissable statement that RNF-01's 5s guarantee is waived outside the pre-warm window -- gives a human operator everything needed to stand up Plan C without an Oracle VM
- [x] `deploy/vercel.json` -- Vercel rewrite config: `{"rewrites": [{"source": "/api/:path*", "destination": "https://<render-backend-url>/:path*"}]}`, with the `<render-backend-url>` placeholder explained in the runbook (JSON has no comment syntax) -- lets `frontend/src/api/client.ts`'s unmodified `/api` base path resolve to the Render backend with no CORS config and no frontend code change
- [x] `deploy/prewarm.sh` -- bash script taking a base URL: `curl`s `<base-url>/openapi.json` directly (no `/api` prefix — that only exists behind the Vercel rewrite, not on Render itself) to force a cold-start wake-up, reports whether the response succeeded and how long it took, with explicit script-header comments stating it is meant to be run manually by a human shortly before a demonstration and must never be wired into a cron job, systemd timer, or CI schedule -- satisfies the "manual pre-warm, never scheduled" AC
- [x] `deploy/README.md` -- update the existing "Plan C ... is Story 6.3 and is not covered here" line to instead point at `plan-c-contingency-runbook.md`, `vercel.json`, and `prewarm.sh`, keeping the Plan A/B section unchanged -- orientation for a future reader of `deploy/`

**Acceptance Criteria:**
- Given no Oracle VM available by the deadline, when Plan C is activated, then the runbook describes the backend running on Render free, Postgres on Neon free, and the frontend static build on Vercel free -- the same logical topology as Plans A/B
- Given Plan C, when used for a live demonstration, then the runbook documents a manual pre-warm (visiting the URL / health check a few minutes before) as a one-off human action, and `deploy/prewarm.sh` is a plain script invoked by hand, never a scheduled job
- Given Plan C, when documented, then the runbook explicitly states that RNF-01's 5-second guarantee is exposed to cold-start outside the pre-warm window, and names this as precisely why it is Plan C and not Plan A
- Given none of the new files, when inspected, then none installs, invokes, or recommends a cron job, systemd timer, GitHub Actions schedule, or any other recurring keep-warm mechanism (RNF-06, AD-9)
- Given `deploy/vercel.json`, when compared against `frontend/src/api/client.ts` and `frontend/nginx.conf`, then its rewrite destination/source pattern preserves the existing `/api` relative-path contract with no frontend code change required

## Implementation Notes

Implemented all four files under `deploy/` as scoped. No Render/Neon/Vercel account exists in this environment and none was created — this story is documentation + operator scripts only, verified with local stand-ins (below), not a real deployment.

While drafting the runbook's Vercel step, found that this backend exposes no `/api` prefix anywhere in its own routing (`backend/app/presentation/*/router.py` only prefixes individual routers like `/auth`; confirmed via `grep -n "prefix"`) — the `/api` prefix the frontend calls (`frontend/src/api/client.ts:86`, `API_BASE = '/api'`) only exists because `frontend/nginx.conf`'s `location /api/ { proxy_pass http://backend:8000/; }` adds and strips it. This meant an initial draft of the runbook and `prewarm.sh` that called `<render-url>/api/openapi.json` directly against Render was wrong — Render serves the backend with no proxy in front of it, so the correct direct-to-Render path is `/openapi.json` (no prefix); the `/api/*` → Render rewrite only applies once Vercel's `vercel.json` is in place in front of the *frontend's* browser-facing calls. Corrected throughout the runbook and in `prewarm.sh` before finalizing.

Also found `frontend/package.json`'s `generate:api-types` script hardcodes a local file path (`openapi-typescript ../backend/openapi.json -o src/api/schema.d.ts`), which Vercel's build environment cannot satisfy (it only checks out `frontend/`, unlike the Docker build's multi-stage context). The runbook documents overriding the Vercel build command to call `openapi-typescript` directly against the Render backend's live `/openapi.json` URL instead — `openapi-typescript` accepts an HTTP(S) URL as input — with no change to `frontend/package.json` or any file under `frontend/src`.

Added a Neon-specific note (pooled vs. direct connection string) after confirming via Design Notes that AD-3's single-Uvicorn-worker/SQLAlchemy-pool setup makes the pooled (PgBouncer) endpoint unnecessary and a plausible source of confusion if an operator picks the wrong one from the Neon dashboard.

## Spec Change Log

## Review Triage Log

Self-reviewed (no subagent review lenses spawned for this documentation-only story; applied the edge-case-hunter, verification-gap, and intent-alignment lenses directly). Verdicts: 3 patch (all fixed before finalizing), 0 defer, 0 reject.

| Finding | Verdict | Evidence |
|---|---|---|
| Initial runbook draft and `prewarm.sh` called `<render-url>/api/openapi.json` directly against the Render backend, but the backend has no `/api` prefix of its own — that prefix is added only by `frontend/nginx.conf`'s reverse proxy (Plan A/B) or `deploy/vercel.json`'s rewrite (Plan C), neither of which sits in front of calls made directly to Render | patch | Verified via `grep -n "prefix" backend/app/presentation/*/router.py backend/app/main.py` — only per-domain prefixes like `/auth` exist, no `/api`. Fixed all direct-to-Render references (runbook Sections 3, 4, 5; `prewarm.sh`) to use `/openapi.json`; kept `/api/*` only for the Vercel-rewrite-fronted frontend path. |
| Runbook's Vercel build step originally said to run `npm run generate:api-types && npm run build` as-is, but that script hardcodes a local `../backend/openapi.json` path Vercel's single-directory build checkout cannot provide | patch | Verified via `grep -n "generate:api-types" frontend/package.json` — script body is `openapi-typescript ../backend/openapi.json -o src/api/schema.d.ts`, a local path. Fixed: runbook now documents overriding the Vercel build command to call `openapi-typescript` against the live Render `/openapi.json` URL instead. |
| Cross-reference numbers inside the runbook (e.g. "pre-warm procedure, Section 4") pointed at the wrong section after the document was drafted with the pre-warm step as Section 5 | patch | Verified by reading the final section numbering (0 Activation, 1 Topology, 2 Neon, 3 Render, 4 Vercel, 5 Pre-warm, 6 Exclusions) against every "Section N" reference in the file; three were stale (lines referring to the pre-warm procedure as "Section 4"). Corrected to "Section 5". |

## Design Notes

**Why a Vercel rewrite instead of CORS:** the codebase has zero CORS configuration by design (`frontend/vite.config.ts`'s own comment: "the frontend never needs CORS configuration in either environment"). Splitting frontend and backend across two hosts (Vercel + Render) would normally force a choice between adding CORS headers to the backend or routing through a same-origin proxy. Vercel's native `rewrites` config in `vercel.json` plays the same role `frontend/nginx.conf` plays in Plan A/B and `vite.config.ts`'s dev proxy plays locally: it makes `/api/*` resolve to the backend host transparently, so `API_BASE = '/api'` in `frontend/src/api/client.ts` needs no change and the backend needs no CORS middleware added. This is the one piece of config Plan C needs that Plan A/B does not, and it is a platform-level rewrite, not application code.

**Why `prewarm.sh` is a separate script from `smoke-test.sh`:** `smoke-test.sh` (Story 6.2) is a pass/fail gate with a 5-second threshold — on Plan C, a cold-start first request can legitimately exceed 5s, so running `smoke-test.sh` as the pre-warm step would report a false "fail" for an expected, documented cold start. `prewarm.sh` has no threshold; it reports latency for operator awareness and exits non-zero only on outright connection failure (the service never woke up), not on slowness.

**Render build reuse:** Render's "Docker" runtime builds directly from a Dockerfile with a configurable build context and dockerfile path, so `backend/Dockerfile` is used unmodified by pointing Render's build context at the repo root and the dockerfile path at `backend/Dockerfile` — the same two settings `docker-compose.yml` already encodes (`build.context: .`, `build.dockerfile: backend/Dockerfile`).

## Verification

**Commands run (all passed):**
- `bash -n deploy/prewarm.sh` -- no syntax errors
- `python3 -c "import json; json.load(open('deploy/vercel.json'))"` -- valid JSON
- `bash deploy/prewarm.sh http://127.0.0.1:8899` (a local Python `http.server` stub serving `/openapi.json`, standing in for a Render URL since no Neon/Render/Vercel account exists in this environment) -- reported `[OK] ... responded 200 in 0.0117s`, exit 0
- `bash deploy/prewarm.sh http://127.0.0.1:1` (an address nothing listens on) -- reported `[FAIL] Could not reach ... (curl exit 7)`, exit 1
- `bash deploy/prewarm.sh http://127.0.0.1:8899/wrong-path` (stub returns 404 for any unknown path) -- exercised the non-2xx/3xx branch
- `chmod +x deploy/prewarm.sh` -- executable bit set before commit, avoiding Story 6.2's review finding (its three scripts were committed non-executable despite being invoked as `./deploy/....sh`)

**Manual checks performed:**
- Read `deploy/plan-c-contingency-runbook.md` end-to-end: activation criteria are unambiguous (Section 0), the Neon/Render/Vercel steps cover the full topology (Sections 1-4), the pre-warm procedure (Section 5) is described as a one-off human action with an explicit "never scheduled" callout, and the RNF-01 cold-start waiver is stated in a blockquote at the top of the document under the heading "RNF-01 WAIVER — READ THIS FIRST", not merely implied.
- Confirmed no file under `deploy/` added by this story mentions cron, a scheduler, a systemd timer, or a CI schedule except as explicit negative documentation (`prewarm.sh`'s header comment and runbook Section 6, "What Plan C deliberately does not include").
- Confirmed via `grep -n "prefix"` across `backend/app/presentation/*/router.py` and `backend/app/main.py` that the backend has no built-in `/api` prefix, validating the runbook's direct-to-Render URLs (`/openapi.json`, no prefix) versus the Vercel-rewrite-fronted frontend path (`/api/*`, prefix stripped by `deploy/vercel.json`).
