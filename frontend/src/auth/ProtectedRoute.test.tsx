import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

const STORAGE_KEY = 'sinaliza.session'

function renderProtectedRoute() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/home"
            element={
              <ProtectedRoute>
                <div>Secret Home Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // Spec I/O & Edge-Case Matrix: "Unauthenticated frontend nav" — redirects
  // to /login before rendering, no backend call needed.
  it('redirects to /login and does not render children when there is no stored session', () => {
    renderProtectedRoute()

    expect(screen.queryByText('Secret Home Content')).not.toBeInTheDocument()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('renders the protected children when a session is already stored', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: 'fake-token',
        user: { id: 'u1', name: 'Test User', email: 'test@example.com', role: 'COORDENACAO_PEDAGOGICA' },
      }),
    )

    renderProtectedRoute()

    expect(screen.getByText('Secret Home Content')).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
  })
})
