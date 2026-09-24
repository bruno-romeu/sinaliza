# Deferred Work

- source_spec: `docs/spec-1-1-autenticacao-coordenacao-pedagogica.md`
  summary: `POST /auth/login` has no rate limiting or lockout, so the single seeded account is open to unlimited password-guessing attempts.
  evidence: Confirmed no rate-limiting/backoff middleware anywhere in `backend/app/presentation/auth/router.py` or `app/main.py`. Not required by any RF/RNF captured so far (RNF-05 only mandates hashed storage); real but not needed for this story's scope. Revisit if the product moves toward real deployment beyond the TCC demo.

- source_spec: `docs/spec-1-1-autenticacao-coordenacao-pedagogica.md`
  summary: No lint/formatting tooling is configured for either the backend (ruff/black) or the frontend (eslint/prettier).
  evidence: `backend/pyproject.toml` and `frontend/package.json` have no lint/format scripts or dependencies. General project hygiene, not specific to the auth vertical slice; nothing in the epics/architecture docs calls it out as a Story 1.1 requirement.

- source_spec: `docs/spec-1-1-autenticacao-coordenacao-pedagogica.md`
  summary: No automated test exercises the literal Login-form-submit-to-redirect path (`Login.tsx` → `AuthContext.login()` → `POST /auth/login` → navigate to `/home`) — only covered by the spec's own "Manual checks" note.
  evidence: `frontend/src/auth/ProtectedRoute.test.tsx` seeds `localStorage` directly rather than exercising the form/login call; no `Login.test.tsx` exists. The backend side of this same behavior is fully covered by `backend/tests/test_auth_login.py`. Worth adding a rendered-form test (mocking `fetch`, asserting `navigate('/home')`) in a follow-up once more of the app exists to test against end-to-end.

- source_spec: `docs/spec-1-2-registro-de-presenca-falta-por-turma-e-data.md`
  summary: No automated frontend test exercises `Presenca.tsx`'s per-row "Registro salvo." confirmation or the field-adjacent duplicate-attendance message — the frontend-observable half of the story's I/O Matrix.
  evidence: `backend/tests/test_attendance.py` covers every I/O Matrix row at the HTTP/DB layer with exact-body assertions; no Vitest/RTL test renders `Presenca.tsx` itself. Same precedent as the Login-form deferral above (Story 1.1) — the underlying behavior is proven correct at the HTTP contract level, and a rendered-component test is a reasonable follow-up once the app has more surface to test end-to-end against.

- source_spec: `docs/spec-1-3-registro-de-notas-por-disciplina-e-periodo-letivo.md`
  summary: There is no `GET /grades` (or any read-back) endpoint or UI — once a coordenação leaves "Lançamento de notas," there is no way to review which grades were already entered for a turma/disciplina/período.
  evidence: Confirmed no listing/read endpoint exists anywhere in `backend/app/presentation/grades/router.py`. Not required by any of Story 1.3's ACs; `docs/epic-1-context.md`'s Goal frames Epic 1 as capturing raw facts for Epic 3's later consumption/analysis, and Story 1.2 shipped the identical shape (no `GET /attendance` listing endpoint either). Consistent epic-wide write-now/read-later precedent — revisit once a story actually needs to display recorded grades (Epic 3, or a future "consultar lançamentos" story).

- source_spec: `docs/spec-1-3-registro-de-notas-por-disciplina-e-periodo-letivo.md`
  summary: `seed_dev_fixtures.py`'s new `_seed_academic_periods` idempotency path (re-running the script when periods already exist is a no-op) has no automated test.
  evidence: No test in `backend/tests/` imports or calls `seed_dev_fixtures()`/`_seed_academic_periods` — the `seeded_academic_period` fixture in `conftest.py` builds the row directly via SQLAlchemy, bypassing the script entirely. Dev-only tooling with no production request path; a regression here would only surface on a developer's manual re-run, not via the automated suite. A follow-up test would import the module and call it twice against the test DB, asserting row counts stay stable on the second call.
