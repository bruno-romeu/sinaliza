import { useEffect, useState, type ChangeEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  changeFollowUpStatus,
  getFollowUp,
  registerFollowUpAction,
  type FollowUpDetail,
  type TrajectoryChangeEvidenceGroup,
} from '../api/client'
import {
  Button,
  ButtonLink,
  Disclosure,
  EvidenceCard,
  FOLLOW_UP_STATUS,
  Notice,
  Page,
  ScreenHead,
  Section,
  SelectField,
  Skeleton,
  StatusPill,
  TextAreaField,
  Timeline,
} from '../components/ui'

type FollowUpStatusValue = FollowUpDetail['status']
type FollowUpActionItem = FollowUpDetail['actions'][number]
type ChangeType = TrajectoryChangeEvidenceGroup['trajectory_change']['type']

const STATUS_ORDER: FollowUpStatusValue[] = ['EM_OBSERVACAO', 'ACOMPANHAMENTO_ATIVO', 'AGUARDANDO_RETORNO', 'ENCERRADO']

const CHANGE_TYPE_LABEL: Record<ChangeType, string> = {
  ATTENDANCE_DROP: 'Queda de frequência',
  GRADE_DROP: 'Queda de notas',
  MISSING_ASSIGNMENTS_INCREASE: 'Aumento de atividades pendentes',
  COMBINED_DETERIORATION: 'Mudança combinada',
}

function formatDateBr(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

// `detected_at` is the detection *date* stored at UTC midnight (same rule as
// the Home): format it in UTC so it does not slip to the previous day.
function formatDetectedBr(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' })
}

function formatDateTimeBr(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; detail: FollowUpDetail }
  | { status: 'not_found' }
  | { status: 'error' }

/**
 * Tela de Acompanhamento (`/acompanhamentos/:followUpId`, RF-20). Visual:
 * design system `TelaAcompanhamento`, escopo "API atual": status, registro
 * de ação, histórico de ações e as evidências que originaram o caso.
 * Encerrar pede confirmação dentro da tela e não apaga nem esconde nada.
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
    <Page>
      {loadState.status !== 'loaded' && <ScreenHead kicker="Coordenação pedagógica" title="Acompanhamento" />}

      {loadState.status === 'loading' && (
        <div className="sz-section">
          <Skeleton heights={[64, 120, 120]} />
        </div>
      )}

      {loadState.status === 'not_found' && (
        <div className="sz-section" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p className="sz-muted">Acompanhamento não encontrado.</p>
          <div>
            <ButtonLink to="/home" variant="secondary" icon="voltar">
              Voltar para a Home
            </ButtonLink>
          </div>
        </div>
      )}

      {loadState.status === 'error' && (
        <div className="sz-section">
          <Notice
            tone="attention"
            action={
              <Button variant="secondary" onClick={() => setLoadAttempt((n) => n + 1)}>
                Tentar novamente
              </Button>
            }
          >
            Não foi possível carregar os dados agora.
          </Notice>
        </div>
      )}

      {loadState.status === 'loaded' && followUpId && (
        <AcompanhamentoContent
          followUpId={followUpId}
          detail={loadState.detail}
          onStatusChange={(status) => setLoadState({ status: 'loaded', detail: { ...loadState.detail, status } })}
          onActionRegistered={(action) =>
            setLoadState({
              status: 'loaded',
              detail: { ...loadState.detail, actions: [...loadState.detail.actions, action] },
            })
          }
        />
      )}
    </Page>
  )
}

function AcompanhamentoContent({
  followUpId,
  detail,
  onStatusChange,
  onActionRegistered,
}: {
  followUpId: string
  detail: FollowUpDetail
  onStatusChange: (status: FollowUpStatusValue) => void
  onActionRegistered: (action: FollowUpActionItem) => void
}) {
  const [notice, setNotice] = useState<{ tone: 'success' | 'info'; text: string } | null>(null)
  const actionCount = detail.actions.length

  return (
    <>
      <section aria-label="Resumo do acompanhamento">
        <ScreenHead kicker="Coordenação pedagógica › Acompanhamento" title={detail.student_name}>
          <div className="sz-head-row">
            <StatusPill status={detail.status} />
          </div>
          <p className="sz-summary">
            Aberto em {formatDateBr(detail.created_at)} ·{' '}
            <b>
              {actionCount} {actionCount === 1 ? 'ação registrada' : 'ações registradas'}
            </b>
          </p>
        </ScreenHead>
      </section>

      {notice && (
        <div style={{ marginTop: 24 }}>
          <Notice tone={notice.tone}>{notice.text}</Notice>
        </div>
      )}

      <StatusSelector
        followUpId={followUpId}
        studentName={detail.student_name}
        status={detail.status}
        onStatusChange={(status) => {
          onStatusChange(status)
          setNotice(
            status === 'ENCERRADO'
              ? { tone: 'success', text: 'Acompanhamento encerrado. O histórico e as evidências continuam disponíveis.' }
              : { tone: 'info', text: `Status alterado para ${FOLLOW_UP_STATUS[status].label}.` },
          )
        }}
      />

      <ActionForm followUpId={followUpId} onActionRegistered={onActionRegistered} />

      <ActionHistory actions={detail.actions} />

      {detail.trajectory_changes.map((group) => (
        <Disclosure key={group.trajectory_change.id} title={CHANGE_TYPE_LABEL[group.trajectory_change.type]}>
          <EvidenceCard
            kicker={`Mudança detectada em ${formatDetectedBr(group.trajectory_change.detected_at)}`}
            title={group.trajectory_change.description}
            description="Mudança de trajetória vinculada a este acompanhamento."
            evidence={group.evidence}
            linkTo={`/estudantes/${detail.student_id}`}
            linkLabel={`Ver na trajetória de ${detail.student_name}`}
          />
        </Disclosure>
      ))}
    </>
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
    <Disclosure title="Histórico de ações">
      {actions.length === 0 ? (
        <p className="sz-muted">Nenhuma ação registrada até o momento.</p>
      ) : (
        <Timeline
          items={actions.map((action) => ({
            key: action.id,
            date: formatDateTimeBr(action.created_at),
            text: action.description,
            icon: 'check' as const,
            label: 'Ação',
            color: 'var(--action)',
          }))}
        />
      )}
    </Disclosure>
  )
}

/**
 * Native `<select>` with exactly the 4 closed `FollowUpStatus` values — never
 * free text (RF-13, UX-DR8). Choosing "Encerrado" opens an inline
 * confirmation (no modal, no `window.confirm`); any other status calls the
 * API immediately. Cancelling makes no request and the select keeps the
 * current status.
 */
function StatusSelector({
  followUpId,
  studentName,
  status,
  onStatusChange,
}: {
  followUpId: string
  studentName: string
  status: FollowUpStatusValue
  onStatusChange: (status: FollowUpStatusValue) => void
}) {
  const { token } = useAuth()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmingClose, setConfirmingClose] = useState(false)

  async function applyStatusChange(nextStatus: FollowUpStatusValue) {
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      const updated = await changeFollowUpStatus(token, followUpId, { status: nextStatus })
      onStatusChange(updated.status)
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : 'Não foi possível atualizar o status agora.'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextStatus = event.target.value as FollowUpStatusValue
    if (nextStatus === status) return
    if (nextStatus === 'ENCERRADO') {
      setConfirmingClose(true)
      return
    }
    setConfirmingClose(false)
    void applyStatusChange(nextStatus)
  }

  return (
    <Section id="acompanhamento-status" title="Status do acompanhamento">
      <div style={{ maxWidth: 360 }}>
        <SelectField
          label="Status atual"
          value={status}
          onChange={handleChange}
          disabled={saving}
          error={error}
          hint="Sempre um dos 4 estados. Encerrar não apaga nem esconde nada."
        >
          {STATUS_ORDER.map((value) => (
            <option key={value} value={value}>
              {FOLLOW_UP_STATUS[value].label}
            </option>
          ))}
        </SelectField>
      </div>
      {confirmingClose && (
        <div className="sz-confirm" role="group" aria-labelledby="confirmar-encerramento">
          <p id="confirmar-encerramento">
            <b>Encerrar o acompanhamento de {studentName}?</b> O histórico de ações e as evidências continuam
            acessíveis, e o status pode ser alterado de novo depois.
          </p>
          <div className="sz-confirm-actions">
            <Button
              onClick={() => {
                setConfirmingClose(false)
                void applyStatusChange('ENCERRADO')
              }}
            >
              Encerrar acompanhamento
            </Button>
            <Button variant="secondary" onClick={() => setConfirmingClose(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </Section>
  )
}

/**
 * Free-text action form (textarea + disabled-while-empty submit).
 * Submitting never replaces a prior action: every submission is a fresh row
 * (RF-13, RF-14).
 */
function ActionForm({
  followUpId,
  onActionRegistered,
}: {
  followUpId: string
  onActionRegistered: (action: FollowUpActionItem) => void
}) {
  const { token } = useAuth()
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
      const action = await registerFollowUpAction(token, followUpId, { description: text })
      onActionRegistered(action)
      setText('')
      setMessage('Registro salvo.')
      setIsError(false)
    } catch (caught) {
      const errorMessage = caught instanceof ApiError ? caught.message : 'Não foi possível salvar o registro agora.'
      setMessage(errorMessage)
      setIsError(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Section id="acompanhamento-acao" title="Registrar ação">
      <TextAreaField
        label="Descreva a ação tomada"
        value={text}
        rows={4}
        placeholder="Ex.: Conversamos com a família sobre…"
        hint="Fatos observáveis, sem julgamentos sobre o estudante."
        onChange={(event) => {
          setText(event.target.value)
          setMessage(null)
          setIsError(false)
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button onClick={handleSave} disabled={saving || !canSave}>
          {saving ? 'Salvando…' : 'Registrar ação'}
        </Button>
      </div>
      <div aria-live="polite">
        {message && <Notice tone={isError ? 'attention' : 'success'} role={isError ? 'alert' : 'status'}>{message}</Notice>}
      </div>
    </Section>
  )
}
