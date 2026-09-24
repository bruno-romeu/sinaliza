---
title: 'Autenticação da coordenação pedagógica (Story 1.1)'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'full'
route_source: 'auto'
baseline_commit: 'd93c4c725d910bb65d9b40fa3e679f36ce43c1fc'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '{project-root}/docs/architecture/architecture-sinaliza-2026-09-17/ARCHITECTURE-SPINE.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/DESIGN.md'
  - '{project-root}/docs/ux-designs/ux-sinaliza-2026-09-17/EXPERIENCE.md'
  - '{project-root}/docs/data-model.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Sinaliza repo is greenfield — no backend, no frontend, no auth exists — yet every later story (1.2–1.5 and beyond) needs authenticated access before it can register any pedagogical fact.

**Approach:** Stand up the minimal layered backend + Vite/React frontend scaffold (per `ARCHITECTURE-SPINE.md` Structural Seed) needed for one vertical slice: `POST /auth/login` issuing a stateless JWT bearer token against a single `User` (`role = COORDENACAO_PEDAGOGICA`), a Login page, and a `ProtectedRoute` + simple header pattern reused by every screen after login.

## Boundaries & Constraints

**Always:** Domain has zero framework imports (AD-2); application depends only on domain + repository/hasher/token ports; passwords hashed with bcrypt/argon2, never plaintext (RNF-05); JWT bearer is stateless, no server-side session; login failure returns the same factual message ("Login ou senha inválidos.") whether the email or the password was wrong, and issues no token; error responses use envelope `{ "error": { "code", "message" } }`; schema changes only via Alembic; frontend HTTP types generated from the backend's OpenAPI schema (`openapi-typescript`), never hand-transcribed; every form field has a visible label (not placeholder-only), visible focus, and ≥44×44px hit target.

**Never:** a second role/"professor" profile or a role enum with more than one value; a self-service registration/signup screen — the one seeded user comes from a dev-only CLI seed script; real content for Home/Trajetória/Acompanhamento/Lançamento (placeholder shell only — those are later stories); Docker/docker-compose/CI wiring (Epic 6 scope); a refresh-token endpoint or server-side session store; protecting any backend route besides `/auth/login` — `get_current_user` is scaffolded here for Stories 1.2+ to reuse, not applied to a route yet.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Login success | `POST /auth/login {email, password}`, matches seeded user | 200 `{access_token, token_type: "bearer", user: {id, name, email, role}}`; frontend stores session, redirects to `/home` | No error |
| Wrong password | Valid email, wrong password | 401 `{error:{code:"invalid_credentials", message:"Login ou senha inválidos."}}` | Message never names the field |
| Unknown email | Email not in `users` | Identical 401 payload as wrong password | Prevents user enumeration |
| Malformed body | Missing/empty `email` or `password` | 422 FastAPI default validation error | Standard Pydantic validation, not the auth envelope |
| Unauthenticated frontend nav | Browser opens `/home` (or any protected route) with no stored token | `ProtectedRoute` redirects to `/login` before rendering | No backend call needed |
| Stale/invalid bearer token | Future protected call carries expired/invalid JWT | `get_current_user` raises 401 with the same envelope shape | Frontend clears session, redirects to `/login` |

</frozen-after-approval>

## Code Map

- No source exists yet — this is the first vertical slice of the Structural Seed in `ARCHITECTURE-SPINE.md` (`backend/app/{domain,application,infrastructure,presentation}/`, `frontend/src/{pages,components,api}/`).
- `docs/architecture/.../ARCHITECTURE-SPINE.md` — AD-2 (layering), AD-8 (single `User`, hashed password, JWT bearer), Stack table (Python 3.14, FastAPI 0.141.x, SQLAlchemy 2.x, Alembic, PostgreSQL 18.6, React 19.3, Vite 8).
- `docs/data-model.md` — `User { id, name, email, role: COORDENACAO_PEDAGOGICA }`.
- `docs/ux-designs/.../DESIGN.md` — `{components.button}` / `{components.form-field}` tokens, 44px `min-hit-target`.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/pyproject.toml` -- fastapi, uvicorn, sqlalchemy>=2, alembic, psycopg[binary], pydantic-settings, bcrypt, pyjwt, pytest, httpx -- pins the Stack table versions
- [ ] `backend/app/config.py` -- pydantic-settings `Settings` (DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES) -- no hardcoded secrets
- [ ] `backend/app/domain/user.py` -- pure `User` dataclass (id, name, email, password_hash, role literal) -- AD-2, no framework imports
- [ ] `backend/app/application/auth/ports.py` -- `UserRepositoryPort`, `PasswordHasherPort`, `TokenIssuerPort` Protocols
- [ ] `backend/app/application/auth/authenticate_user.py` -- `AuthenticateUserService`, raises `InvalidCredentialsError` on any mismatch
- [ ] `backend/app/infrastructure/db/base.py` + `models.py` -- SQLAlchemy engine/session + `UserModel` (`users` table, unique `email`)
- [ ] `backend/alembic/` (env + first migration) -- creates `users` table via migration only
- [ ] `backend/app/infrastructure/repositories/sqlalchemy_user_repository.py` -- implements `UserRepositoryPort`
- [ ] `backend/app/infrastructure/security/bcrypt_hasher.py` -- implements `PasswordHasherPort`
- [ ] `backend/app/infrastructure/security/jwt_issuer.py` -- implements `TokenIssuerPort`, HS256, embeds `sub`/`name`/`role`/`exp`
- [ ] `backend/app/presentation/schemas/auth.py` -- `LoginRequest`/`LoginResponse`/`UserOut`
- [ ] `backend/app/presentation/auth/router.py` -- `POST /auth/login`
- [ ] `backend/app/presentation/auth/dependencies.py` -- `get_current_user` (401 envelope on invalid/expired/missing bearer), for future stories
- [ ] `backend/app/presentation/errors.py` + `backend/app/main.py` -- error-envelope exception handler, app factory wiring the auth router
- [ ] `backend/app/infrastructure/db/seed_dev_user.py` -- idempotent CLI (`python -m app.infrastructure.db.seed_dev_user`) seeding one `COORDENACAO_PEDAGOGICA` user from env vars
- [ ] `backend/tests/test_auth_login.py` -- covers every I/O Matrix row against a real Postgres test DB
- [ ] `backend/app/export_openapi.py` -- writes `backend/openapi.json` for the frontend codegen step
- [ ] `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` -- Vite+React+TS scaffold, with `generate:api-types` script running `openapi-typescript`
- [ ] `frontend/src/api/schema.d.ts` -- generated output, never hand-edited
- [ ] `frontend/src/api/client.ts` -- typed fetch wrapper for `POST /auth/login`
- [ ] `frontend/src/auth/AuthContext.tsx` -- token+user state, persisted in `localStorage`, `login()`/`logout()`
- [ ] `frontend/src/auth/ProtectedRoute.tsx` -- redirects to `/login` when unauthenticated
- [ ] `frontend/src/pages/Login.tsx` -- email/senha form: visible labels, visible focus, 44×44px targets, single factual error region (`role="alert"`)
- [ ] `frontend/src/components/Header.tsx` -- authenticated user's name + link to Home, no side nav
- [ ] `frontend/src/pages/Home.tsx` -- placeholder authenticated shell rendering `Header` (full content is Epic 3 Story 3.3)
- [ ] `frontend/src/App.tsx` + `main.tsx` -- router: `/login` public, `/home` behind `ProtectedRoute`

**Acceptance Criteria:**
- Given a seeded user with valid email/password, when submitted on the Login form, then the backend returns a JWT bearer and the frontend redirects to Home.
- Given an incorrect password or unknown email, when login is attempted, then the same factual message displays without naming the field, and no token is issued.
- Given the `users` table, when inspected, then `password_hash` holds a bcrypt/argon2 hash, never plaintext.
- Given an unauthenticated visitor, when any route other than `/login` is opened, then they are redirected to `/login`.
- Given the `User` model, when inspected, then `role` has exactly one possible value, `COORDENACAO_PEDAGOGICA`.
- Given the login form fields, when rendered, then each has a visible label, visible focus state, and a ≥44×44px hit target.
- Given any screen after login, when rendered, then a simple header shows the user's name and a link back to Home, with no persistent side navigation.

## Implementation Notes

Implemented in full per the Tasks checklist: layered FastAPI backend (`domain`/`application`/`infrastructure`/`presentation`), Alembic-managed `users` table with native Postgres enum, bcrypt hashing, HS256 JWT issuing `sub`/`name`/`role` claims (so `get_current_user` needs no DB round-trip), idempotent dev seed CLI, and a Vite/React frontend (`AuthContext` + `localStorage` session, `ProtectedRoute`, `Login`/`Home`/`Header`), with `frontend/src/api/schema.d.ts` generated via `openapi-typescript` from `backend/openapi.json`.

Verified against a real Postgres 18 container (not sqlite): `alembic upgrade head` → `downgrade` → `upgrade` round trip (caught and fixed a native-enum create/drop lifecycle bug), `pytest` 14/14, seed idempotency, and a manual end-to-end login through the Vite dev proxy for all four backend I/O Matrix scenarios.

**Matrix Test Audit fix:** the "Unauthenticated frontend nav" row initially had no automated test — `frontend/package.json` had no test runner. Added Vitest + Testing Library (`frontend/src/auth/ProtectedRoute.test.tsx`, `frontend/src/test/setup.ts`) rendering `ProtectedRoute` with/without a stored session and asserting the actual redirect/render behavior. `npm test` → 2/2 pass; `npm run build` confirmed unaffected by the `vitest/config` swap in `vite.config.ts`.

Known deviations (see full implementer report): dev interpreter is Python 3.12, not the spine's 3.14 (no 3.14-only syntax used); TypeScript pinned to 5.9.3 for `openapi-typescript`'s peer range (not in the Stack table, so not a pinned-version deviation); `get_current_user`'s 401 uses `code: "invalid_token"` (matrix only specified same envelope *shape*, not identical code/message to `invalid_credentials`); router/dependency factories construct concrete infrastructure adapters via `Depends` (standard composition-root pattern, flagged for a second opinion against a literal reading of AD-2).

## Spec Change Log

## Review Triage Log

**Pass 1** (lenses: blind-hunter, edge-case-hunter, verification-gap, intent-alignment) — verdict counts: 1 medium, 15 low, 6 false. Routing: 12 patch, 3 defer, 6 false (rejected/no action, incl. 1 rejected-low-out-of-scope, 2 rejected-low-nontrivial-fix). Zero intent_gap, zero bad_spec — no loopback, `review_loop_iteration` stays 0.

| # | Finding (source) | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `docs/epic-1-context.md` contains corrupted mid-word text (blind-hunter) | false | — | Confirmed via direct grep of the committed file: no such text exists. The reviewed diff file itself was contaminated by the coordinator's own `git diff ... 2>&1` redirect, which piped a stderr CRLF warning into the diff text — an artifact of review-prep, not the deliverable. |
| 2 | Logout only clears `localStorage`, no server-side JWT revocation (blind-hunter) | low | rejected (out of scope) | The spec's own `## Intent` Approach text commits to "a stateless JWT bearer token," and Boundaries explicitly exclude "a refresh-token endpoint or server-side session store" — revocation is precluded by the chosen design, not an oversight. |
| 3 | Bearer token stored in `localStorage`, not an httpOnly cookie — XSS exposure (blind-hunter) | low | rejected | Real class of concern, but the fix (cookie + CSRF handling) is far more than a direct correction, and this story renders no untrusted user content that would create an XSS vector yet. |
| 4 | No rate limiting/lockout on `POST /auth/login` (blind-hunter) | low | defer | Real gap; not required by RF-01/RF-02/RNF-05. Logged in `docs/deferred-work.md`. |
| 5 | `get_by_email` is case/whitespace-sensitive (blind-hunter + edge-case-hunter, grouped) | low | patch | Confirmed exact-match query, no `.strip()/.lower()`. Trivial, no public-surface fix. |
| 6 | `pyproject.toml`'s comment claims to "pin the Stack table versions" while `sqlalchemy` floats (blind-hunter) | false | — | No such comment exists in `backend/pyproject.toml` (it has zero comments) — the phrase is the spec's own Tasks-list rationale, not a code claim. The `>=2,<3` range also faithfully mirrors architecture's own open "SQLAlchemy \| 2.x" stack row. |
| 7 | Alembic enum create/drop lifecycle fix has no automated regression test (verification-gap, pre-verified, grouped w/ blind-hunter's same observation) | medium | patch | verification-gap traced: only `Base.metadata.create_all()` is used in test setup; no test imports `alembic.command` or exercises `upgrade()`/`downgrade()`. A revert of the `create_type=False` fix would pass 100% of pytest while reintroducing the `DuplicateObject` bug the migration's own comment documents. |
| 8 | `export_openapi.py` transitively requires `Settings()` (env vars) at import time via `app.main` (blind-hunter) | low | rejected | `create_engine()` is lazy (no live connection needed), only construction of `Settings()` is required — consistent with the app's deliberate fail-fast config design (no defaults, documented in `config.py`); `.env.example` already documents the vars. Fix would require nontrivially decoupling schema export from the rest of app wiring. |
| 9 | `UserOut.role`/API contract typed as bare `str`, not reflecting the single-role invariant (blind-hunter + intent-alignment (d)) | low | patch | Confirmed. AD-8 explicitly "Prevents: introduzir um segundo papel." Trivial `Literal[...]` fix protects the invariant at the contract/generated-types layer too, not just DB/domain. |
| 10 | No lint/format tooling configured (blind-hunter) | low | defer | Real, general project hygiene, not specific to auth. Logged in `docs/deferred-work.md`. |
| 11 | Spec/`sprint-status.yaml` status "inconsistency" at review time (blind-hunter) | false | — | Snapshot-timing artifact: the diff was generated between two frontmatter edits made during this same review step, not a deliverable defect. `sprint-status.yaml` synced separately as routine workflow housekeeping. |
| 12 | `ProtectedRoute.test.tsx` mock uses `role: 'admin'`, a value the system can never produce (blind-hunter) | low | patch | Confirmed; test doesn't assert on role at all, but the fixture should still reflect the real contract. Trivial one-line fix. |
| 13 | `LoginRequest` has no `max_length` on `email`/`password` (edge-case-hunter) | low | patch | Confirmed unbounded `Field(min_length=1)`. Trivial. |
| 14 | `BcryptPasswordHasher.hash()` doesn't guard bcrypt's 72-byte limit (edge-case-hunter) | low | patch | Confirmed — only `verify()` has a try/except. Narrow blast radius (operator-controlled seed password only, never end-user input), but the fix is trivial. |
| 15 | `jwt_expire_minutes` accepts zero/negative unchecked (edge-case-hunter) | low | patch | Confirmed plain `int = 60`, no constraint. Trivial `Field(gt=0)` fix. |
| 16 | `seed_dev_user` existence-check + insert has a TOCTOU race (edge-case-hunter) | low | patch | Confirmed two separate DB round-trips with no transaction guard. Trivial `IntegrityError` catch. |
| 17 | `AuthContext.readStoredSession` doesn't validate parsed JSON shape (edge-case-hunter + verification-gap "Other findings", grouped) | medium | patch | Confirmed: only a JSON-parse-throw guard exists; a partial value (e.g. `{"token":"x"}`) passes through, making `isAuthenticated` true with `user` undefined instead of being treated as logged-out. Trivial guard fix, real visible consequence (blank header name instead of a correct login redirect). |
| 18 | `api/client.ts login()` has no request timeout (edge-case-hunter) | low | patch | Confirmed plain `fetch` with no `AbortSignal`. A hung backend leaves the submit button stuck indefinitely. Trivial fix. |
| 19 | `presentation/auth/{router,dependencies}.py` construct concrete `infrastructure/` classes directly — literal AD-2 layering violation (intent-alignment (b), self-flagged in Implementation Notes) | low | patch | Confirmed literal import of `SqlAlchemyUserRepository`/`BcryptPasswordHasher`/`JwtTokenIssuer` inside `presentation/`. No business logic actually leaked (AD-2's named "Prevents" harms don't occur), but the rule's letter is violated; trivial mechanical fix (relocate the two factory functions to a neutral `app/composition.py`) resolves it without behavior change. |
| 20 | No automated test exercises the literal Login-form → redirect path (intent-alignment (a)) | medium | defer | Confirmed: only `ProtectedRoute.test.tsx` exists (seeds `localStorage` directly), no `Login.test.tsx`. The backend side of the same AC is fully covered by pytest. Logged in `docs/deferred-work.md` rather than forced as a spec-blocking gap, since the underlying behavior is otherwise proven correct at the unit level. |
| 21 | Second Postgres test-instance (port 5433) has no provisioning path in the diff (intent-alignment (c)) | false | — | Boundaries explicitly exclude Docker/compose/CI wiring this story; `.env.example` already documents `TEST_DATABASE_URL`'s expected shape. Nothing promised was left missing. |
| 22 | Python 3.14→3.12, TypeScript 5.9.3 vs. an unpinned Stack-table entry (intent-alignment (e)) | false | — | Already self-disclosed transparently in Implementation Notes; no 3.14-only syntax used; TypeScript isn't in the Stack table at all. |

## Design Notes

JWT claims carry `sub`/`name`/`role` so `get_current_user` never needs a DB round-trip to answer "who is this and what's their name" — consistent with AD-8's "stateless" bearer design and avoids adding a `/auth/me` endpoint this story doesn't need. The frontend mirrors this: it persists the `user` object returned at login (not just the token) so the header can render the name without a second request.

## Verification

**Commands:**
- `cd backend && alembic upgrade head` -- expected: `users` table created with a unique index on `email`
- `cd backend && python -m app.infrastructure.db.seed_dev_user` -- expected: exactly one `COORDENACAO_PEDAGOGICA` user exists; re-running is a no-op
- `cd backend && pytest` -- expected: all rows of the I/O Matrix pass, including the hashed-password assertion
- `cd frontend && npm run generate:api-types && npm run build` -- expected: clean TypeScript build, no manually-edited `schema.d.ts` drift

**Manual checks (if no CLI):**
- Run the backend (`uvicorn app.main:app`) and frontend dev servers, log in with the seeded credentials, confirm redirect to Home with the header showing the user's name; clear the stored session and navigate directly to `/home`, confirm redirect to `/login`.
