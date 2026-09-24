import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

/**
 * Simple header reused by every authenticated screen: the user's name plus a
 * link back to Home — no persistent side navigation (DESIGN.md Layout &
 * Spacing; spec Boundaries & Constraints).
 */
export function Header() {
  const { user, logout } = useAuth()

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
      }}
    >
      <Link
        to="/home"
        style={{
          color: 'var(--color-primary)',
          fontWeight: 700,
          fontSize: 18,
          textDecoration: 'none',
          minHeight: 'var(--min-hit-target)',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        Sinaliza
      </Link>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* "Lançamento" is reached from a global navigation action, not
            contextually per-screen (spec Code Map / EXPERIENCE.md IA). */}
        <Link
          to="/lancamento/presenca"
          style={{
            color: 'var(--color-text)',
            textDecoration: 'none',
            fontSize: 14,
            minHeight: 'var(--min-hit-target)',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          Lançamento
        </Link>
        <span>{user?.name}</span>
        <button
          type="button"
          onClick={logout}
          style={{
            minHeight: 'var(--min-hit-target)',
            minWidth: 'var(--min-hit-target)',
            padding: '0 16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          Sair
        </button>
      </div>
    </header>
  )
}
