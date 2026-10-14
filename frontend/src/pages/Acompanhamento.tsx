import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError, getFollowUp, type FollowUpDetail } from '../api/client'
import { EvidenceCard } from '../components/EvidenceCard'
import { FollowUpStatusPill } from '../components/FollowUpStatusPill'
import { Header } from '../components/Header'

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; detail: FollowUpDetail }
  | { status: 'not_found' }
  | { status: 'error' }

/**
 * Tela de Acompanhamento (`/acompanhamentos/:followUpId`) — Story 4.1. Only
 * needs to show the status pill and the reused evidence card with a link
 * back to the student's trajectory (UX-DR4). Status transitions, the action
 * form, full history and Home's active-follow-ups section are Stories
 * 4.2/4.3/4.5 scope — not implemented here (spec Never).
 *
 * Same loading/error/not-found conventions as `EstudanteTrajetoria.tsx`
 * (Story 3.4): skeleton while loading, factual message + retry on error,
 * factual message + link to Home when the follow-up doesn't exist.
 */
export function Acompanhamento() {
  const { followUpId } = useParams<{ followUpId: string }>()
  const { token } = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)

  useEffect(() => {
    if (!token || !followUpId) return
    let ignore = false
    setLoadState({ status: 'loading' })
    getFollowUp(token, followUpId)
      .then((detail) => {
        if (ignore) return
        setLoadState({ status: 'loaded', detail })
      })
      .catch((caught) => {
        if (ignore) return
        if (caught instanceof ApiError && caught.code === 'follow_up_not_found') {
          setLoadState({ status: 'not_found' })
        } else {
          setLoadState({ status: 'error' })
        }
      })
    return () => {
      ignore = true
    }
  }, [token, followUpId, loadAttempt])

  return (
    <div>
      <Header />
      <main
        style={{
          maxWidth: 'var(--spacing-content-max-width)',
          margin: '0 auto',
          padding: 'var(--spacing-section-gap) 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 32,
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Acompanhamento</h1>

        {loadState.status === 'loading' && (
          <div aria-hidden="true" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[0, 1].map((i) => (
              <div
                key={i}
                style={{
                  height: 64,
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--color-border)',
                  opacity: 0.4,
                }}
              />
            ))}
          </div>
        )}

        {loadState.status === 'not_found' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
              Acompanhamento não encontrado.
            </p>
            <div>
              <Link
                to="/home"
                style={{
                  minHeight: 'var(--min-hit-target)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  color: 'var(--color-primary)',
                }}
              >
                Voltar para a Home
              </Link>
            </div>
          </div>
        )}

        {loadState.status === 'error' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
              Não foi possível carregar os dados agora.
            </p>
            <div>
              <button
                type="button"
                onClick={() => setLoadAttempt((n) => n + 1)}
                style={{
                  minHeight: 'var(--min-hit-target)',
                  minWidth: 'var(--min-hit-target)',
                  padding: '0 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: 15,
                  cursor: 'pointer',
                }}
              >
                Tentar novamente
              </button>
            </div>
          </div>
        )}

        {loadState.status === 'loaded' && (
          <AcompanhamentoContent detail={loadState.detail} />
        )}
      </main>
    </div>
  )
}

function AcompanhamentoContent({ detail }: { detail: FollowUpDetail }) {
  return (
    <>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span style={{ color: 'var(--color-text-secondary)' }}>{detail.student_name}</span>
        <FollowUpStatusPill status={detail.status} />
      </section>

      <EvidenceCard
        title="Evidências"
        evidence={detail.evidence}
        linkTo={`/estudantes/${detail.student_id}`}
        linkLabel={`Ver na trajetória de ${detail.student_name}`}
      />
    </>
  )
}
