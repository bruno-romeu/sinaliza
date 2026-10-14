import { useEffect, useId, useState, type ChangeEvent, type CSSProperties, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  changeFollowUpStatus,
  getFollowUp,
  registerFollowUpAction,
  type FollowUpDetail,
  type TrajectoryChangeEvidenceGroup,
} from '../api/client'
import { EvidenceCard } from '../components/EvidenceCard'
import { FollowUpStatusPill } from '../components/FollowUpStatusPill'
import { Header } from '../components/Header'

type FollowUpStatusValue = FollowUpDetail['status']
type FollowUpActionItem = FollowUpDetail['actions'][number]
type ChangeType = TrajectoryChangeEvidenceGroup['trajectory_change']['type']

const STATUS_OPTIONS: { value: FollowUpStatusValue; label: string }[] = [
  { value: 'EM_OBSERVACAO', label: 'Em observação' },
  { value: 'ACOMPANHAMENTO_ATIVO', label: 'Ativo' },
  { value: 'AGUARDANDO_RETORNO', label: 'Aguardando retorno' },
  { value: 'ENCERRADO', label: 'Encerrado' },
]

// Duplicated from `EstudanteTrajetoria.tsx` (same labels, spec Code Map — no
// shared module exists for it; extracting one for two call sites across two
// files is a larger, unscoped refactor the intent doesn't ask for).
const CHANGE_TYPE_LABEL: Record<ChangeType, string> = {
  ATTENDANCE_DROP: 'Queda de frequência',
  GRADE_DROP: 'Queda de notas',
  MISSING_ASSIGNMENTS_INCREASE: 'Aumento de atividades pendentes',
  COMBINED_DETERIORATION: 'Mudança combinada',
}

const fieldStyle: CSSProperties = {
  padding: '0 12px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  fontSize: 15,
}

const selectStyle: CSSProperties = {
  ...fieldStyle,
  minHeight: 'var(--min-hit-target)',
}

const cardStyle: CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--spacing-card-padding)',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
}

function formatDateTimeBr(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR')
}

/**
 * Collapsible section header — same `aria-expanded`/`aria-controls`/`+`/`−`
 * button pattern as `EstudanteTrajetoria.tsx`'s "Fator preocupante" section
 * (spec Boundaries & Constraints, RNF-08, UX-DR20), copied inline here rather
 * than extracted into a shared component (spec Design Notes). Default open —
 * unlike that section, this screen's whole purpose is reviewing history.
 */
function CollapsibleSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  const contentId = useId()

  return (
    <section style={cardStyle}>
      <h2 style={{ margin: 0 }}>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((current) => !current)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            minHeight: 'var(--min-hit-target)',
            background: 'none',
            border: 'none',
            padding: 0,
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--color-text)',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span>{title}</span>
          <span aria-hidden="true">{open ? '−' : '+'}</span>
        </button>
      </h2>
      {open && <div id={contentId}>{children}</div>}
    </section>
  )
}

/**
 * Chronological list of every registered `FollowUpAction`, oldest first
 * (RF-14). Zero actions renders an explicit message instead of a blank list
 * (spec Boundaries & Constraints — "transparência em vez de validação
 * forçada").
 */
function ActionHistory({ actions }: { actions: FollowUpActionItem[] }) {
  return (
    <CollapsibleSection title="Histórico de ações">
      {actions.length === 0 ? (
        <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
          Nenhuma ação registrada até o momento.
        </p>
      ) : (
        <ol
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {actions.map((action) => (
            <li
              key={action.id}
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: '12px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                {formatDateTimeBr(action.created_at)}
              </span>
              <span>{action.description}</span>
            </li>
          ))}
        </ol>
      )}
    </CollapsibleSection>
  )
}

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; detail: FollowUpDetail }
  | { status: 'not_found' }
  | { status: 'error' }

/**
 * Tela de Acompanhamento (`/acompanhamentos/:followUpId`). Story 4.1 built
 * the status pill and the reused evidence card with a link back to the
 * student's trajectory (UX-DR4). Story 4.2 adds the status `<select>`
 * (`StatusSelector`) and the free-text action form (`ActionForm`) below.
 * Full chronological history (past actions + evidence list) and Home's
 * active-follow-ups section remain Stories 4.3/4.5 scope — not implemented
 * here.
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

        {loadState.status === 'loaded' && followUpId && (
          <AcompanhamentoContent
            followUpId={followUpId}
            detail={loadState.detail}
            onStatusChange={(status) =>
              setLoadState({ status: 'loaded', detail: { ...loadState.detail, status } })
            }
          />
        )}
      </main>
    </div>
  )
}

function AcompanhamentoContent({
  followUpId,
  detail,
  onStatusChange,
}: {
  followUpId: string
  detail: FollowUpDetail
  onStatusChange: (status: FollowUpStatusValue) => void
}) {
  return (
    <>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span style={{ color: 'var(--color-text-secondary)' }}>{detail.student_name}</span>
        <FollowUpStatusPill status={detail.status} />
      </section>

      <StatusSelector
        followUpId={followUpId}
        status={detail.status}
        onStatusChange={onStatusChange}
      />

      {detail.trajectory_changes.map((group) => (
        <CollapsibleSection
          key={group.trajectory_change.id}
          title={CHANGE_TYPE_LABEL[group.trajectory_change.type]}
        >
          <EvidenceCard
            title="Evidências"
            description={group.trajectory_change.description}
            detectedAt={group.trajectory_change.detected_at}
            evidence={group.evidence}
            linkTo={`/estudantes/${detail.student_id}`}
            linkLabel={`Ver na trajetória de ${detail.student_name}`}
          />
        </CollapsibleSection>
      ))}

      <ActionHistory actions={detail.actions} />

      <ActionForm followUpId={followUpId} />
    </>
  )
}

/**
 * Native `<select>` with exactly the 4 closed `FollowUpStatus` values — never
 * free text (RF-13, UX-DR8). Selecting "Encerrado" asks for a simple
 * `window.confirm` before calling the API; any other target status calls the
 * API immediately (UX-DR19 — only the destructive/irreversible transition is
 * gated). Declining the confirmation makes no request and reverts the select
 * to the prior status.
 */
function StatusSelector({
  followUpId,
  status,
  onStatusChange,
}: {
  followUpId: string
  status: FollowUpStatusValue
  onStatusChange: (status: FollowUpStatusValue) => void
}) {
  const { token } = useAuth()
  const selectId = useId()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function applyStatusChange(nextStatus: FollowUpStatusValue) {
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      const updated = await changeFollowUpStatus(token, followUpId, { status: nextStatus })
      onStatusChange(updated.status)
    } catch (caught) {
      const message =
        caught instanceof ApiError ? caught.message : 'Não foi possível atualizar o status agora.'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextStatus = event.target.value as FollowUpStatusValue
    if (nextStatus === status) return

    if (nextStatus === 'ENCERRADO') {
      const confirmed = window.confirm(
        'Tem certeza que deseja encerrar este acompanhamento? Esta ação não pode ser desfeita.',
      )
      if (!confirmed) {
        // Revert — the <select>'s value is controlled by `status`, which
        // hasn't changed, so simply not calling the API is enough; React
        // will re-render the <select> back to the current status.
        return
      }
    }

    void applyStatusChange(nextStatus)
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 280 }}>
      <label htmlFor={selectId} style={{ fontWeight: 600 }}>
        Status do acompanhamento
      </label>
      <select
        id={selectId}
        value={status}
        onChange={handleChange}
        disabled={saving}
        style={selectStyle}
      >
        {STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p role="alert" style={{ color: 'var(--color-attention)', margin: 0, fontSize: 14 }}>
          {error}
        </p>
      )}
    </section>
  )
}

/**
 * Free-text action form (textarea + disabled-while-empty submit) — mirrors
 * `Observacoes.tsx`'s `ObservacaoRow`/`canSave` pattern. Submitting never
 * replaces a prior action: every submission is a fresh row (RF-13, RF-14).
 * No read-back/list of past actions here (Story 4.3 scope).
 */
function ActionForm({ followUpId }: { followUpId: string }) {
  const { token } = useAuth()
  const textId = useId()
  const messageId = useId()
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [isError, setIsError] = useState(false)

  const canSave = text.trim() !== ''

  async function handleSave() {
    if (!token || !canSave) return
    setSaving(true)
    setMessage(null)
    setIsError(false)
    try {
      await registerFollowUpAction(token, followUpId, { description: text })
      setText('')
      setMessage('Registro salvo.')
      setIsError(false)
    } catch (caught) {
      const errorMessage =
        caught instanceof ApiError ? caught.message : 'Não foi possível salvar o registro agora.'
      setMessage(errorMessage)
      setIsError(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '16px 20px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Registrar ação</h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label htmlFor={textId} style={{ fontSize: 13, fontWeight: 600 }}>
          Ação
        </label>
        <textarea
          id={textId}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setMessage(null)
            setIsError(false)
          }}
          aria-describedby={message ? messageId : undefined}
          rows={3}
          style={{ ...fieldStyle, padding: '8px 12px', resize: 'vertical', fontFamily: 'inherit' }}
        />
      </div>

      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !canSave}
          style={{
            minHeight: 'var(--min-hit-target)',
            minWidth: 'var(--min-hit-target)',
            padding: '0 16px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: 'var(--color-primary)',
            color: 'var(--color-surface)',
            fontSize: 15,
            fontWeight: 600,
            cursor: saving || !canSave ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Salvando…' : 'Salvar'}
        </button>
      </div>

      <div
        id={messageId}
        role={isError ? 'alert' : 'status'}
        aria-live="polite"
        style={{
          minHeight: 20,
          fontSize: 14,
          color: isError ? 'var(--color-attention)' : 'var(--color-success)',
        }}
      >
        {message}
      </div>
    </section>
  )
}
