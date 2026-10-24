import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getStudentTrajectoryDetail,
  openFollowUp,
  type TrajectoryDetail,
} from '../api/client'
import {
  Button,
  ButtonLink,
  CalmState,
  ConcernFactor,
  EvidenceCard,
  Notice,
  Page,
  ScreenHead,
  Section,
  Skeleton,
  Tag,
  Timeline,
  TrajectoryChart,
  type Indicator,
} from '../components/ui'

type ChartIndicator = TrajectoryDetail['chart_indicator']
type ChangeType = NonNullable<TrajectoryDetail['trajectory_change']>['type']

const CHART_INDICATOR: Record<ChartIndicator, { label: string; indicator: Indicator }> = {
  attendance_rate: { label: 'Frequência', indicator: 'frequencia' },
  grade_average: { label: 'Nota média', indicator: 'notas' },
  missing_assignments_count: { label: 'Atividades pendentes', indicator: 'entregas' },
}

const CHANGE_TYPE_LABEL: Record<ChangeType, string> = {
  ATTENDANCE_DROP: 'Queda de frequência',
  GRADE_DROP: 'Queda de notas',
  MISSING_ASSIGNMENTS_INCREASE: 'Aumento de atividades pendentes',
  COMBINED_DETERIORATION: 'Mudança combinada',
}

const CONCERNING_KIND_LABEL: Record<NonNullable<TrajectoryDetail['concerning_factor']>['kind'], string> = {
  ATTENDANCE: 'Sinal isolado em frequência',
  GRADE: 'Sinal isolado em notas',
  ASSIGNMENTS: 'Sinal isolado em atividades',
  PEDAGOGICAL_OBSERVATION: 'Sinal isolado em registro pedagógico',
}

function toNumber(value: string | null): number | null {
  return value === null ? null : Number(value)
}

function formatIndicatorValue(indicator: ChartIndicator, value: number | null): string {
  if (value === null) return 'Sem dado'
  if (indicator === 'attendance_rate') return `${Math.round(value * 100)}%`
  if (indicator === 'grade_average') return value.toFixed(1).replace('.', ',')
  return String(Math.round(value))
}

function formatDateBr(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; detail: TrajectoryDetail }
  | { status: 'not_found' }
  | { status: 'error' }

/**
 * Trajetória do Estudante (RF-19). Visual: design system `TelaTrajetoria`,
 * escopo "API atual": um indicador escolhido pelo backend, faixa habitual
 * fixa, fator preocupante só quando não há mudança, registros só com
 * observações.
 */
export function EstudanteTrajetoria() {
  const { studentId } = useParams<{ studentId: string }>()
  const { token } = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)

  useEffect(() => {
    if (!token || !studentId) return
    let ignore = false
    setLoadState({ status: 'loading' })
    getStudentTrajectoryDetail(token, studentId)
      .then((detail) => {
        if (ignore) return
        setLoadState({ status: 'loaded', detail })
      })
      .catch((caught) => {
        if (ignore) return
        if (caught instanceof ApiError && caught.code === 'student_not_found') {
          setLoadState({ status: 'not_found' })
        } else {
          setLoadState({ status: 'error' })
        }
      })
    return () => {
      ignore = true
    }
  }, [token, studentId, loadAttempt])

  const student = loadState.status === 'loaded' ? loadState.detail.student : null

  return (
    <Page>
      {/* spec-ui-1: the detail endpoint carries the student's name and
          classroom; the generic title stays as the fallback while loading. */}
      <ScreenHead
        kicker={student?.classroom_name ? `Coordenação pedagógica › ${student.classroom_name}` : 'Coordenação pedagógica'}
        title={student ? student.name : 'Trajetória do estudante'}
        display
        center
      >
        {loadState.status === 'loaded' && (
          <div className="sz-head-row">
            {student?.classroom_name && <Tag>{student.classroom_name}</Tag>}
            {loadState.detail.open_follow_up_id ? (
              <Tag>Com acompanhamento aberto</Tag>
            ) : (
              <Tag>Sem acompanhamento</Tag>
            )}
          </div>
        )}
      </ScreenHead>

      {loadState.status === 'loading' && (
        <div className="sz-section">
          <Skeleton heights={[280, 120, 72]} />
        </div>
      )}

      {loadState.status === 'not_found' && (
        <div className="sz-section" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p className="sz-muted">Estudante não encontrado.</p>
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

      {loadState.status === 'loaded' && studentId && (
        <TrajectoryDetailContent detail={loadState.detail} studentId={studentId} token={token} />
      )}
    </Page>
  )
}

type OpenFollowUpState = { status: 'idle' } | { status: 'submitting' } | { status: 'error' }

function TrajectoryDetailContent({
  detail,
  studentId,
  token,
}: {
  detail: TrajectoryDetail
  studentId: string
  token: string | null
}) {
  const navigate = useNavigate()
  const change = detail.trajectory_change
  const hasChange = change !== null
  const hasConcerningFactor = detail.concerning_factor !== null
  const isCalm = !hasChange && !hasConcerningFactor
  const [openFollowUpState, setOpenFollowUpState] = useState<OpenFollowUpState>({ status: 'idle' })

  const chart = CHART_INDICATOR[detail.chart_indicator]
  const points = detail.series.map((point) => ({
    key: point.period_id,
    label: point.period_label,
    value: toNumber(point.value),
  }))
  const changeIndex = change ? detail.series.findIndex((point) => point.period_id === change.period_id) : -1
  const changePeriodLabel = changeIndex >= 0 ? detail.series[changeIndex].period_label : undefined
  const band = detail.habitual_range
    ? { low: Number(detail.habitual_range.low), high: Number(detail.habitual_range.high) }
    : null
  const summary =
    `Gráfico de ${chart.label.toLowerCase()} por bimestre` +
    (hasChange ? `, com mudança destacada em ${changePeriodLabel ?? ''}` : '') +
    ', comparado à faixa habitual do próprio estudante.'

  function handleOpenFollowUp() {
    if (!token || change === null) return
    setOpenFollowUpState({ status: 'submitting' })
    openFollowUp(token, { student_id: studentId, trajectory_change_id: change.id })
      .then((followUp) => {
        navigate(`/acompanhamentos/${followUp.id}`)
      })
      .catch(() => {
        setOpenFollowUpState({ status: 'error' })
      })
  }

  function goToEvidence() {
    const card = document.getElementById('evidencia-mudanca')
    if (!card) return
    card.scrollIntoView({ behavior: 'smooth', block: 'start' })
    card.focus({ preventScroll: true })
  }

  return (
    <>
      {/* Chart section — reached first via keyboard. */}
      <Section id="trajetoria-grafico" title="Trajetória · últimos bimestres">
        <TrajectoryChart
          summary={summary}
          indicator={chart.indicator}
          indicatorLabel={chart.label}
          points={points}
          band={band}
          bandLabel={detail.student ? `Faixa habitual de ${detail.student.name.split(' ')[0]}` : 'Faixa habitual do estudante'}
          changeIndex={changeIndex >= 0 ? changeIndex : undefined}
          changeDescription={change?.description}
          format={(value) => formatIndicatorValue(detail.chart_indicator, value)}
          onChangePoint={goToEvidence}
        />
      </Section>

      {/* Evidence section — only when a change was detected. No link here:
          this page already *is* the trajectory destination. */}
      {change && (
        <Section id="trajetoria-mudanca" title="O que mudou">
          <EvidenceCard
            id="evidencia-mudanca"
            kicker={changePeriodLabel ? `Mudança detectada · ${changePeriodLabel}` : 'Mudança detectada'}
            title={CHANGE_TYPE_LABEL[change.type]}
            description={change.description}
            evidence={detail.evidence}
          />
        </Section>
      )}

      {/* Concerning factor — one isolated signal, closed by default. */}
      {detail.concerning_factor && !hasChange && (
        <Section id="trajetoria-observacao" title="Em observação">
          <ConcernFactor title={CONCERNING_KIND_LABEL[detail.concerning_factor.kind]}>
            <p>{detail.concerning_factor.description}</p>
            <p>Um único sinal fora da faixa habitual ainda não caracteriza mudança de padrão.</p>
          </ConcernFactor>
        </Section>
      )}

      {/* Calm state — same visual care as a change, since it is most cases. */}
      {isCalm && (
        <Section id="trajetoria-situacao" title="Situação atual">
          <CalmState title="Trajetória estável">
            Nenhuma mudança relevante detectada dentro do período vigente.
          </CalmState>
        </Section>
      )}

      <Section id="trajetoria-registros" title="Registros pedagógicos recentes">
        {detail.observations.length === 0 ? (
          <p className="sz-muted">Nenhum registro pedagógico nos últimos 12 meses.</p>
        ) : (
          <Timeline
            items={detail.observations.map((observation, index) => ({
              key: `${observation.date}-${index}`,
              date: formatDateBr(observation.date).slice(0, 5),
              text: observation.text,
              indicator: 'observacao' as const,
              // spec-ui-3: say when the team registered a concern; only those
              // observations count as a signal.
              label: observation.registers_concern ? 'Observação · preocupação registrada' : undefined,
            }))}
          />
        )}
      </Section>

      {/* Follow-up action — enabled once a change was detected (Story 4.1).
          spec-ui-1: when the user already has an open follow-up for this
          student, link to it instead of offering to open another one. */}
      <div className="sz-actions" style={{ flexDirection: 'column', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <ButtonLink to="/lancamento/observacoes" variant="secondary" icon="observacao">
            Registrar observação
          </ButtonLink>
          {detail.open_follow_up_id ? (
            <ButtonLink to={`/acompanhamentos/${detail.open_follow_up_id}`} icon="seta">
              Ver acompanhamento
            </ButtonLink>
          ) : (
            <Button
              icon="mais"
              disabled={!hasChange || openFollowUpState.status === 'submitting'}
              onClick={handleOpenFollowUp}
              title={hasChange ? undefined : 'Acompanhamento vinculado a evidências requer uma mudança detectada.'}
            >
              {openFollowUpState.status === 'submitting' ? 'Abrindo…' : 'Abrir acompanhamento'}
            </Button>
          )}
        </div>
        {openFollowUpState.status === 'error' && (
          <Notice tone="attention">Não foi possível abrir o acompanhamento agora.</Notice>
        )}
      </div>
    </>
  )
}
