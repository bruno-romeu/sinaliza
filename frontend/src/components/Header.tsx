import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ButtonLink } from './ui/Button'
import { initials } from './ui/FollowupCard'
import { Icon } from './ui/Icon'

/**
 * Cabeçalho de todas as telas autenticadas (design system `AppHeader`):
 * wordmark, volta à Home fora dela, uma única ação "Lançar registro" e a
 * pessoa autenticada. Sem navegação lateral.
 */
export function Header() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const onHome = pathname === '/home'
  const onLancamento = pathname.startsWith('/lancamento')

  return (
    <div className="sz-page" style={{ paddingBottom: 0 }}>
      <header className="sz-header">
        <Link className="sz-wordmark" to="/home">
          <span className="sz-wordmark-dot" aria-hidden="true" />
          Sinaliza
        </Link>
        <nav className="sz-header-nav" aria-label="Navegação principal">
          {!onHome && (
            <ButtonLink to="/home" variant="quiet" icon="voltar">
              Voltar à Home
            </ButtonLink>
          )}
          {!onLancamento && (
            <ButtonLink to="/lancamento/presenca" variant="secondary" icon="mais">
              Lançar registro
            </ButtonLink>
          )}
          {user && (
            <span className="sz-header-user">
              <span className="sz-avatar" aria-hidden="true">
                {initials(user.name)}
              </span>
              <span className="sz-header-name">{user.name}</span>
            </span>
          )}
          <Button variant="quiet" onClick={logout} aria-label="Sair">
            <Icon name="sair" size={18} />
          </Button>
        </nav>
      </header>
    </div>
  )
}
