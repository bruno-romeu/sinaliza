import { useId, useState, type CSSProperties, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const fieldStyle: CSSProperties = {
  minHeight: 'var(--min-hit-target)',
  padding: '0 12px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  fontSize: 15,
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const emailId = useId()
  const passwordId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate('/home', { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message)
      } else {
        setError('Não foi possível fazer login agora.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <form
        onSubmit={handleSubmit}
        noValidate
        style={{
          width: '100%',
          maxWidth: 400,
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--spacing-card-padding)',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Entrar no Sinaliza</h1>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label htmlFor={emailId} style={{ fontWeight: 600 }}>
            E-mail
          </label>
          <input
            id={emailId}
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-describedby={error ? 'login-error' : undefined}
            style={fieldStyle}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label htmlFor={passwordId} style={{ fontWeight: 600 }}>
            Senha
          </label>
          <input
            id={passwordId}
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby={error ? 'login-error' : undefined}
            style={fieldStyle}
          />
        </div>

        <div
          id="login-error"
          role="alert"
          aria-live="assertive"
          style={{ minHeight: 20, color: 'var(--color-attention)', fontSize: 14 }}
        >
          {error}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            minHeight: 'var(--min-hit-target)',
            minWidth: 'var(--min-hit-target)',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: 'var(--color-primary)',
            color: 'var(--color-surface)',
            fontSize: 15,
            fontWeight: 600,
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
          }}
        >
          {isSubmitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </main>
  )
}
