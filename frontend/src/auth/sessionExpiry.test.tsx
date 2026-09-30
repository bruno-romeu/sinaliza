import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { listClassrooms, login } from '../api/client'
import { AuthProvider, useAuth } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

const STORAGE_KEY = 'sinaliza.session'

const STORED_SESSION = {
  token: 'stale-token',
  user: {
    id: 'u1',
    name: 'Coordenação Pedagógica',
    email: 'coordenacao@sinaliza.dev',
    role: 'COORDENACAO_PEDAGOGICA',
  },
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * Renders a protected page whose only job is to fire one API call on mount —
 * standing in for any of the four Lançamento pages, which all load their
 * classroom list the same way through the shared `request()` helper.
 */
function ExpiringPage({ call }: { call: (token: string) => Promise<unknown> }) {
  const { token } = useAuth()
  // Fire-and-forget: the rejection is the point of the test, and every real
  // page catches it into its own error state rather than rethrowing.
  void call(token ?? '').catch(() => undefined)
  return <div>Secret Home Content</div>
}

function renderProtected(call: (token: string) => Promise<unknown>) {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/home"
            element={
              <ProtectedRoute>
                <ExpiringPage call={call} />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Session expiry on 401 invalid_token (spec-1-1 I/O Matrix)', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(STORED_SESSION))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('clears the stored session and redirects to /login when a protected call returns 401 invalid_token', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse(
        { error: { code: 'invalid_token', message: 'Credenciais inválidas ou expiradas.' } },
        401,
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderProtected((token) => listClassrooms(token))

    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })
    expect(screen.queryByText('Secret Home Content')).not.toBeInTheDocument()
    // The stale token must be gone from storage too — a reload must not
    // resurrect the session that the backend just rejected.
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('keeps the session when a protected call fails with a non-401 error', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse(
        { error: { code: 'student_not_enrolled', message: 'Estudante não matriculado.' } },
        422,
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderProtected((token) => listClassrooms(token))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    expect(screen.getByText('Secret Home Content')).toBeInTheDocument()
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull()
  })

  it('keeps the session when a login attempt fails with 401 invalid_credentials', async () => {
    // A failed login answers 401 too, but with a different code. Clearing the
    // session there would log out a user who is already signed in elsewhere
    // in the app, so the handler must not fire.
    fetchMock = vi.fn(async () =>
      jsonResponse(
        { error: { code: 'invalid_credentials', message: 'Login ou senha inválidos.' } },
        401,
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderProtected(() => login({ email: 'coordenacao@sinaliza.dev', password: 'errada' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    expect(screen.getByText('Secret Home Content')).toBeInTheDocument()
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull()
  })
})
