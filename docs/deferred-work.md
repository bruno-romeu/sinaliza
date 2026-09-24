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
