import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  login as loginRequest,
  setUnauthorizedHandler,
  type LoginResponse,
} from '../api/client'

type SessionUser = LoginResponse['user']

interface StoredSession {
  token: string
  user: SessionUser
}

interface AuthContextValue {
  user: SessionUser | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const STORAGE_KEY = 'sinaliza.session'

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function isStoredSession(value: unknown): value is StoredSession {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<StoredSession>
  return (
    typeof candidate.token === 'string' &&
    candidate.token.length > 0 &&
    typeof candidate.user === 'object' &&
    candidate.user !== null &&
    typeof candidate.user.id === 'string' &&
    typeof candidate.user.name === 'string' &&
    typeof candidate.user.email === 'string' &&
    typeof candidate.user.role === 'string'
  )
}

function readStoredSession(): StoredSession | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    // A corrupted/partial value (e.g. missing `user`) must be treated as
    // logged-out, never as authenticated-with-a-blank-user.
    return isStoredSession(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => readStoredSession())

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest({ email, password })
    const next: StoredSession = { token: response.access_token, user: response.user }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setSession(next)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setSession(null)
  }, [])

  // Spec-1-1 I/O Matrix, "Stale/invalid bearer token": when any protected
  // call is rejected with `invalid_token`, the session is cleared here and
  // `ProtectedRoute` takes the user to /login on the resulting re-render.
  // Registered once for the provider's lifetime and torn down on unmount, so
  // a stale provider (e.g. between tests) can never keep handling responses.
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      token: session?.token ?? null,
      isAuthenticated: session !== null,
      login,
      logout,
    }),
    [session, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
