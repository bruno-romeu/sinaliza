import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Icon, Notice, TextField } from '../components/ui'

/**
 * Login (RF-01). Visual: design system `TelaLogin`. Marca à esquerda (os
 * blocos de cor da capa, decorativos), formulário à direita.
 */
export function Login() {
  const { login, sessionExpired } = useAuth()
  const navigate = useNavigate()

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
    <main className="sz-login">
      <div className="sz-login-brand" aria-hidden="true">
        <svg width="520" height="420" viewBox="0 0 520 420">
          <rect className="b-mare" x={96} y={-24} width={192} height={288} rx={18} />
          <rect className="b-ipe" x={304} y={32} width={240} height={144} rx={18} />
          <rect className="b-jabu" x={304} y={192} width={96} height={96} rx={48} />
          <rect className="b-ceu" x={416} y={192} width={128} height={96} rx={18} />
          <rect className="b-ambar" x={32} y={216} width={48} height={48} rx={24} />
          <path className="b-wave" d="M160 200 a32 32 0 0 1 64 0" />
          <path className="b-wave" d="M128 200 a64 64 0 0 1 128 0" />
          <path className="b-wave" d="M96 200 a96 96 0 0 1 192 0" />
        </svg>
        <p className="sz-login-tag">Cada aluno contra a própria curva, nunca contra os colegas.</p>
        <p className="sz-login-sub">
          Mudanças na trajetória escolar, com as evidências que as sustentam, para a coordenação decidir o
          próximo passo.
        </p>
      </div>
      <div className="sz-login-side">
        <form className="sz-login-form" onSubmit={handleSubmit} noValidate>
          <span className="sz-wordmark">
            <span className="sz-wordmark-dot" aria-hidden="true" />
            Sinaliza
          </span>
          <h1 className="sz-title">Entrar no Sinaliza</h1>
          <p className="sz-muted" style={{ marginTop: -12 }}>
            Acesso da coordenação pedagógica.
          </p>
          {error ? (
            <div id="login-error">
              <Notice tone="attention" role="alert">
                {error}
              </Notice>
            </div>
          ) : (
            sessionExpired && <Notice tone="info">Sua sessão expirou. Entre de novo para continuar.</Notice>
          )}
          <TextField
            label="E-mail"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-describedby={error ? 'login-error' : undefined}
          />
          <TextField
            label="Senha"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby={error ? 'login-error' : undefined}
          />
          <button type="submit" className="sz-btn sz-btn-primary" disabled={isSubmitting} style={{ width: '100%' }}>
            {isSubmitting ? 'Entrando…' : 'Entrar'}
          </button>
          <p className="sz-login-foot">
            <Icon name="info" size={16} />
            Ambiente acadêmico com dados sintéticos. Nenhum dado real de estudante.
          </p>
        </form>
      </div>
    </main>
  )
}
