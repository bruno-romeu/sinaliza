---
title: 'Story 6.1: Empacotamento containerizado dos três serviços'
type: 'feature'
created: '2026-10-20'
status: 'done'
baseline_commit: '9ca1569a710db342e44e954788a27fda6a7d3d56'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: ['{project-root}/docs/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The system has no Docker packaging at all — Postgres, the FastAPI backend, and the React frontend only run via manual local processes. Epic 6 needs a reproducible `docker compose up --build` that stands up all three services on any VM, and the frontend's production build is currently unreproducible from a clean clone because it depends on two gitignored, generated artifacts (`backend/openapi.json`, `frontend/src/api/schema.d.ts`) that nothing currently regenerates (open item `epic-1-retro-item-9`).

**Approach:** Add `backend/Dockerfile` (uv-based, runs Alembic migrations then a single-worker Uvicorn), `frontend/Dockerfile` (multi-stage: generate `openapi.json` from the backend source, run `generate:api-types`, build the Vite SPA, serve it from Nginx with a `/api` reverse proxy), and a root `docker-compose.yml` wiring the three services with `restart: unless-stopped` and a named Postgres volume.

## Boundaries & Constraints

**Always:**
- Exactly three services in `docker-compose.yml`: `postgres`, `backend` (FastAPI/Uvicorn), `frontend` (Nginx serving the static build + reverse-proxying `/api`). All three use `restart: unless-stopped`.
- Backend runs `alembic upgrade head` before serving, then Uvicorn with `--workers 1` (required by the in-memory ML artifact singleton, AD-3).
- Postgres data lives in a named Docker volume that survives container recreation/VM restart.
- `docker compose up --build` succeeds unaided from a fresh clone — no pre-generated `openapi.json` or `schema.d.ts` assumed present; the frontend image build generates both itself.

**Never:**
- No VM provisioning or Plan B/C hosting setup (Stories 6.2/6.3) — this story only packages, it does not deploy.
- No CI/CD pipeline, no cron/scheduler/background worker in any of the 3 services.
- No seeding of demo/fixture data as part of container startup — existing seed scripts stay manual, dev-only, out of scope.
- Do not commit `backend/openapi.json` or `frontend/src/api/schema.d.ts` to git — they stay generated, inside the image build only.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fresh clone, empty volume | `docker compose up --build` | All 3 services start; backend applies migrations before accepting requests; frontend serves the SPA | Migration failure stops the backend container (non-zero exit), compose reports it unhealthy |
| Browser loads a client-side route | `GET /trajetoria/123` (no matching static file) | Nginx `try_files` falls back to `index.html`; React Router renders the page | N/A |
| Frontend calls the API | `GET /api/home` | Nginx strips `/api` and proxies to `backend:8000/home`, response passed through unmodified | Backend 4xx/5xx pass through unmodified |
| Container crash or VM reboot | Any of the 3 containers exits | `restart: unless-stopped` recovers it automatically; Postgres volume data is intact | N/A |
| Routine redeploy (`docker compose up --build` again) | Named Postgres volume already exists | Data persists; only an explicit `docker volume rm` would erase it | N/A |

</frozen-after-approval>

## Code Map

- `backend/app/infrastructure/db/base.py:19` -- module-level `get_settings()` call; importing `app.main` (needed to call `app.openapi()` for schema generation) requires `DATABASE_URL`/`JWT_SECRET` env vars to be *set* (dummy values are fine — `create_engine` is lazy, no real connection happens).
- `backend/app/config.py` -- `Settings`: `database_url` and `jwt_secret` are required, no defaults; fail fast if unset.
- `backend/pyproject.toml`, `backend/uv.lock` -- backend deps, installed via `uv sync --frozen --no-dev` in the image.
- `backend/alembic.ini`, `backend/alembic/env.py` -- `env.py` reads `settings.database_url`; run via `alembic upgrade head` before serving.
- `frontend/package.json` -- scripts `generate:api-types` (reads `../backend/openapi.json`, writes `src/api/schema.d.ts`) and `build` (`tsc && vite build`); `build` fails without `schema.d.ts` present.
- `frontend/src/api/client.ts:1,86` -- imports the generated `./schema`; hardcodes `API_BASE = '/api'`.
- `frontend/vite.config.ts` -- dev-only proxy already rewrites `/api/*` -> backend by stripping the prefix; mirror this exact rewrite in `nginx.conf`.
- `.gitignore:16-17,23` -- `backend/openapi.json`, `backend/ml_artifacts/`, `frontend/src/api/schema.d.ts` are gitignored; never assume present in a clean clone.
- `docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md:165-188` (AD-9) -- confirms the 3-service topology and `backend/Dockerfile` + `frontend/Dockerfile` + root `docker-compose.yml` layout.
- `docs/sprint-status.yaml` action item `epic-1-retro-item-9` (open) -- this exact openapi/schema prebuild gap, explicitly deferred to Epic 6; closing it is in scope here.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/Dockerfile` -- multi-stage `python:3.12-slim` build: install deps with `uv sync --frozen --no-dev`, copy `app/` and `alembic/` -- produces the backend image
- [ ] `backend/docker-entrypoint.sh` -- `set -e; alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` -- migrate-then-serve, single-worker AC
- [ ] `backend/.dockerignore` -- exclude `.venv/`, `__pycache__/`, `tests/`, `ml_artifacts/`, `openapi.json` -- correct build context
- [ ] `frontend/Dockerfile` -- stage `openapi` (`python:3.12-slim`, `uv sync` on `backend/pyproject.toml`+`uv.lock`, dummy `DATABASE_URL`/`JWT_SECRET`, dump `app.openapi()` to `openapi.json`); stage `build` (`node:24-slim`, `npm ci`, copy the generated `openapi.json` to `../backend/openapi.json`, run `npm run generate:api-types && npm run build`); final stage `nginx:alpine` copying `dist/` + `nginx.conf` -- closes `epic-1-retro-item-9`
- [ ] `frontend/nginx.conf` -- serve `/usr/share/nginx/html` with SPA `try_files $uri /index.html`; `location /api/ { proxy_pass http://backend:8000/; }` (strips the prefix, mirroring `vite.config.ts`'s rewrite) -- RNF-06
- [ ] `frontend/.dockerignore` -- exclude `node_modules/`, `dist/`, `src/api/schema.d.ts` -- correct build context
- [ ] `docker-compose.yml` (repo root) -- services `postgres` (image `postgres:16-alpine`, named volume `postgres_data`, env `POSTGRES_USER/PASSWORD/DB`), `backend` (build context `.`, dockerfile `backend/Dockerfile`, `DATABASE_URL` pointing at the `postgres` service, `JWT_SECRET` from `.env`, `depends_on: postgres`), `frontend` (build context `.`, dockerfile `frontend/Dockerfile`, publishes port 80, `depends_on: backend`); all three `restart: unless-stopped` -- the reproducible entrypoint
- [ ] `backend/.env.example` -- document `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` alongside the existing vars, as the single source `docker-compose.yml` reads from -- avoids a second, divergent env file

**Acceptance Criteria:**
- Given `docker-compose.yml`, when run (`docker compose up --build`), then three services come up — Postgres, FastAPI/Uvicorn, Nginx (static React build + `/api` reverse proxy) (RNF-06)
- Given the three services, when configured, then all use `restart: unless-stopped` (AD-9)
- Given the Postgres data volume, when a container is recreated or the VM reboots, then data persists — only an explicit `docker volume rm` erases it (AD-9)
- Given the backend, when it runs, then it serves with a single Uvicorn worker (`--workers 1`) (AD-3, AD-9)
- Given none of the three services, when inspected, then none contains a cron/scheduler/scheduled async worker (RNF-06, AD-1)
- Given a fresh clone with no `backend/openapi.json` or `frontend/src/api/schema.d.ts` present, when `docker compose up --build` runs, then the frontend image build generates both and `npm run build` succeeds unaided

## Implementation Notes

## Spec Change Log

## Review Triage Log

Lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment. Verdicts: 3 medium, 4 low (patch), 2 low (reject), 1 low (defer), 2 false.

| Finding | Verdict | Evidence |
|---|---|---|
| `frontend/Dockerfile`'s `openapi` stage reimplements `app.openapi()` dumping inline instead of calling the existing, tested `app/export_openapi.py::export_openapi()` (which `backend/tests/test_synthetic_generation.py::test_openapi_export_never_contains_synthetic_profile` guards against leaking `synthetic_profile`) | medium | Verified: `export_openapi.OUTPUT_PATH` resolves to `backend/openapi.json`, identical to the inline command's output path, so swapping to `python -m app.export_openapi` is behavior-preserving and closes the gap — a future redaction rule added to `export_openapi()` would silently not apply to the Docker-built artifact otherwise. |
| `docker-compose.yml`'s `backend` depends only on `postgres` container-start (`depends_on: [postgres]`, no healthcheck on either service) — `alembic upgrade head` can race a cold Postgres boot | medium | Verified: Postgres's first-boot `initdb` takes several seconds after the container reports "Up"; a fresh-volume `docker compose up --build` (the spec's own first I/O-matrix row) can hit connection-refused before Alembic retries, relying only on `restart: unless-stopped` to eventually succeed. Demo-day startup reliability (RNF-01) is a named stake. |
| `docker-compose.yml:JWT_SECRET: ${JWT_SECRET}` has no `:-`/`:?` guard, unlike the adjacent `POSTGRES_*` vars | medium | Verified: an unset/missing root `.env` makes Compose substitute an empty string rather than failing `up`; `Settings.jwt_secret: str` has no non-empty validator, so the backend would start and sign JWTs with an empty secret instead of failing fast as the Code Map claims. Self-flagged as a residual risk by the implementer. |
| `backend/.dockerignore` and `frontend/.dockerignore` are not the filename BuildKit's per-Dockerfile lookup expects for a `context: .` build (it looks for `<dockerfile-path>.dockerignore` at the context root, e.g. `backend/Dockerfile.dockerignore`) — only the root `.dockerignore` is ever actually consulted, and it has silently drifted from the two dead files it claims to mirror | low | Verified: confirmed against Docker/BuildKit's documented `.dockerignore` resolution rule. Not a behavioral bug (root file's patterns are functionally equivalent today) but misleading — editing the per-service files has no effect. |
| `backend/.env.example`'s `POSTGRES_PASSWORD` has no warning that URL-reserved characters (`:`, `@`, `/`, `#`) would break `docker-compose.yml`'s string-interpolated `DATABASE_URL` | low | Verified: the interpolation is unescaped; a password with those characters breaks the connection string silently. No code fix needed — a doc comment is the direct, trivial mitigation. |
| No README/docs section explains the new `docker compose up --build` workflow or the `.env.example` → root `.env` copy step | low | Verified: nothing in the diff documents this for a future reader; `backend/.env.example`'s new comment only covers part of it. |
| `frontend/Dockerfile`'s final stage `FROM nginx:alpine` is unpinned, inconsistent with `postgres:16-alpine`/`node:24-slim`/`python:3.12-slim` which all pin a version | low | Verified: an unpinned tag can drift across rebuilds, undercutting the story's own reproducibility goal. Trivial one-line pin. |
| `docker-compose.yml`'s `backend` service has no `ports:` mapping, so there's no way to reach the API directly without going through Nginx | false | Not a defect: the reverse-proxy-only topology is the intended design (AD-9) — exposing the backend directly would widen the surface the Nginx proxy exists to narrow. |
| `backend/Dockerfile`'s `uv sync --frozen --no-dev` runs before `app/` is copied into the `deps` stage, theorized to fail because `[tool.hatch.build.targets.wheel] packages = ["app"]` can't find its source | false | Disproven empirically: the implementer's own `docker compose build backend` succeeded from this exact Dockerfile (confirmed again by the live `docker compose up` run completing migrations and serving requests). |
| All three images run as the default root user — no `USER` directive in `backend/Dockerfile` or `frontend/Dockerfile` | low, unverified severity if real | Deferred: a real hardening gap, but the correct fix for the custom `backend` image is straightforward while the `nginx:alpine` image's master process is root by Nginx's own standard design (binding port 80) — reconciling both correctly is more than a direct one-line correction, and out of this story's demonstrated scope (no multi-tenant/untrusted-input threat model stated for the single-author VM target). |
| No `HEALTHCHECK` anywhere, and `frontend`'s `depends_on: backend` only waits for container-start — so `/api/*` can briefly hit Nginx's own error during the backend's migration window, and the spec's own I/O-matrix wording ("compose reports it unhealthy") doesn't literally hold without a HEALTHCHECK | low | Rejected: fixing this properly needs a new `/health` backend endpoint (new application surface, not infra config), which exceeds a direct correction; the window is seconds long and self-heals via `restart: unless-stopped`; the demonstrated behavior (container exits non-zero, visible via `docker compose logs`/`ps`) already satisfies the practical intent for a single-author operator. |

## Design Notes

The frontend/backend dependency is a build-time-only coupling: the `openapi` stage in `frontend/Dockerfile` installs the backend's Python deps and imports `app.main` purely to call `.openapi()` and dump JSON — it never starts a server or touches a real database. Keep `docker-compose.yml`'s build `context: .` (repo root) for the `frontend` service specifically so its Dockerfile can `COPY backend/pyproject.toml backend/uv.lock backend/app ...` — a context scoped to `frontend/` alone cannot see `backend/`.

## Verification

**Commands:**
- `docker compose up --build -d` -- expected: all 3 containers report `Up`/`running` within a couple of minutes
- `docker compose logs backend` -- expected: shows `alembic upgrade head` completing before the Uvicorn startup banner, no traceback
- `curl -sf http://localhost/` -- expected: HTTP 200, HTML containing the Vite-built SPA shell
- `curl -sf http://localhost/api/home -H "Authorization: Bearer <token>"` (or any known route) -- expected: proxied backend response, not Nginx's own 404
- `docker compose down && docker compose up -d` (no `--build`, volume untouched) -- expected: previously-persisted Postgres data is still present
- `docker compose down -v` -- cleanup after verification, expected: stops containers and removes the test volume

**Manual checks (if no CLI):**
- Inspect `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml` for any `cron`, `celery`, `scheduler`, or background-worker invocation — none should exist.
