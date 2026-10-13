import { useEffect, useId, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getStudentTrajectoryDetail,
  type EvidenceItem,
  type ObservationItem,
  type TrajectoryDetail,
} from '../api/client'
import { Header } from '../components/Header'

type ChartIndicator = TrajectoryDetail['chart_indicator']
type ChangeType = NonNullable<TrajectoryDetail['trajectory_change']>['type']

const CHART_INDICATOR_LABEL: Record<ChartIndicator, string> = {
  attendance_rate: 'Frequência',
  grade_average: 'Nota média',
  missing_assignments_count: 'Atividades pendentes',
}

const CHANGE_TYPE_LABEL: Record<ChangeType, string> = {
  ATTENDANCE_DROP: 'Queda de frequência',
  GRADE_DROP: 'Queda de notas',
  MISSING_ASSIGNMENTS_INCREASE: 'Aumento de atividades pendentes',
  COMBINED_DETERIORATION: 'Mudança combinada',
}

const SOURCE_TYPE_LABEL: Record<EvidenceItem['source_type'], string> = {
  ATTENDANCE_RECORD: 'Frequência',
  GRADE: 'Nota',
  ASSIGNMENT_SUBMISSION: 'Atividade',
  PEDAGOGICAL_OBSERVATION: 'Registro pedagógico',
}

function formatIndicatorValue(indicator: ChartIndicator, value: string | null): string {
  if (value === null) return 'Sem dado'
  const num = Number(value)
  if (indicator === 'attendance_rate') return `${Math.round(num * 100)}%`
  if (indicator === 'grade_average') return num.toFixed(1)
  return String(Math.round(num))
}

function formatDateBr(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

function formatDetectedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

const sectionStyle = { display: 'flex', flexDirection: 'column', gap: 16 } as const
const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--spacing-card-padding)',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
} as const
const srOnlyStyle = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
} as const

// --- Chart --------------------------------------------------------------------------

const CHART_WIDTH = 640
const CHART_HEIGHT = 240
const CHART_PADDING = { top: 20, right: 20, bottom: 32, left: 20 }

function TrajectoryChart({ detail }: { detail: TrajectoryDetail }) {
  const { chart_indicator: indicator, series, habitual_range: habitualRange, trajectory_change } =
    detail
  const indicatorLabel = CHART_INDICATOR_LABEL[indicator]
  const chartTitleId = useId()

  const numericSeries = series.map((point) => ({
    ...point,
    numericValue: point.value === null ? null : Number(point.value),
  }))
  const knownValues = numericSeries
    .map((point) => point.numericValue)
    .filter((value): value is number => value !== null)
  const habitualLow = habitualRange ? Number(habitualRange.low) : null
  const habitualHigh = habitualRange ? Number(habitualRange.high) : null

  const allValues = [
    ...knownValues,
    ...(habitualLow !== null ? [habitualLow] : []),
    ...(habitualHigh !== null ? [habitualHigh] : []),
  ]
  const minValue = allValues.length > 0 ? Math.min(...allValues) : 0
  const maxValue = allValues.length > 0 ? Math.max(...allValues) : 1
  const valueSpan = maxValue - minValue || 1

  const innerWidth = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right
  const innerHeight = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom

  const xForIndex = (index: number) =>
    series.length <= 1
      ? CHART_PADDING.left + innerWidth / 2
      : CHART_PADDING.left + (index / (series.length - 1)) * innerWidth

  const yForValue = (value: number) =>
    CHART_PADDING.top + innerHeight - ((value - minValue) / valueSpan) * innerHeight

  const linePoints = numericSeries
    .map((point, index) =>
      point.numericValue === null ? null : `${xForIndex(index)},${yForValue(point.numericValue)}`,
    )
    .filter((point): point is string => point !== null)
    .join(' ')

  const changePointIndex =
    trajectory_change !== null
      ? series.findIndex((point) => point.period_id === trajectory_change.period_id)
      : -1
  const changePoint =
    changePointIndex >= 0 ? numericSeries[changePointIndex] : undefined

  const accessibleName =
    `Gráfico de ${indicatorLabel.toLowerCase()} por bimestre` +
    (trajectory_change !== null ? `, com mudança destacada em ${changePoint?.period_label ?? ''}` : '')

  return (
    <div>
      <div style={{ position: 'relative' }}>
        <svg
          role="img"
          aria-labelledby={chartTitleId}
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          <title id={chartTitleId}>{accessibleName}</title>

          {habitualLow !== null && habitualHigh !== null && (
            <rect
              x={CHART_PADDING.left}
              y={yForValue(habitualHigh)}
              width={innerWidth}
              height={Math.max(yForValue(habitualLow) - yForValue(habitualHigh), 1)}
              fill="var(--color-primary)"
              opacity={0.12}
            />
          )}

          {linePoints && (
            <polyline
              points={linePoints}
              fill="none"
              stroke="var(--color-primary)"
              strokeWidth={2}
            />
          )}

          {numericSeries.map((point, index) =>
            point.numericValue === null ? null : (
              <circle
                key={point.period_id}
                cx={xForIndex(index)}
                cy={yForValue(point.numericValue)}
                r={4}
                fill="var(--color-primary)"
              />
            ),
          )}

          {changePoint && changePoint.numericValue !== null && (
            <circle
              cx={xForIndex(changePointIndex)}
              cy={yForValue(changePoint.numericValue)}
              r={8}
              fill="var(--color-attention)"
              aria-hidden="true"
            />
          )}

          {series.map((point, index) => (
            <text
              key={point.period_id}
              x={xForIndex(index)}
              y={CHART_HEIGHT - 8}
              fontSize={11}
              textAnchor="middle"
              fill="var(--color-text-secondary)"
            >
              {point.period_label}
            </text>
          ))}
        </svg>

        {changePoint && changePoint.numericValue !== null && (
          <button
            type="button"
            aria-label={`Mudança detectada em ${changePoint.period_label}: ${trajectory_change?.description ?? ''}`}
            style={{
              position: 'absolute',
              left: `${(xForIndex(changePointIndex) / CHART_WIDTH) * 100}%`,
              top: `${(yForValue(changePoint.numericValue) / CHART_HEIGHT) * 100}%`,
              transform: 'translate(-50%, -50%)',
              width: 'var(--min-hit-target)',
              height: 'var(--min-hit-target)',
              borderRadius: '50%',
              border: '2px solid var(--color-surface)',
              background: 'transparent',
              cursor: 'pointer',
              padding: 0,
            }}
          />
        )}
      </div>

      {/* WCAG 1.1.1 text-table alternative to the chart above. */}
      <table style={srOnlyStyle}>
        <caption>{accessibleName}</caption>
        <thead>
          <tr>
            <th scope="col">Bimestre</th>
            <th scope="col">{indicatorLabel}</th>
          </tr>
        </thead>
        <tbody>
          {series.map((point) => (
            <tr key={point.period_id}>
              <td>{point.period_label}</td>
              <td>{formatIndicatorValue(indicator, point.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- Page -----------------------------------------------------------------------------

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; detail: TrajectoryDetail }
  | { status: 'not_found' }
  | { status: 'error' }

export function EstudanteTrajetoria() {
  const { studentId } = useParams<{ studentId: string }>()
  const { token } = useAuth()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [concerningFactorOpen, setConcerningFactorOpen] = useState(false)
  const concerningFactorContentId = useId()

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
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Trajetória do estudante</h1>

        {loadState.status === 'loading' && (
          <div aria-hidden="true" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  height: i === 0 ? 220 : 64,
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--color-border)',
                  opacity: 0.4,
                }}
              />
            ))}
          </div>
        )}

        {loadState.status === 'not_found' && (
          <div style={sectionStyle}>
            <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
              Estudante não encontrado.
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
          <TrajectoryDetailContent
            detail={loadState.detail}
            concerningFactorOpen={concerningFactorOpen}
            setConcerningFactorOpen={setConcerningFactorOpen}
            concerningFactorContentId={concerningFactorContentId}
          />
        )}
      </main>
    </div>
  )
}

function TrajectoryDetailContent({
  detail,
  concerningFactorOpen,
  setConcerningFactorOpen,
  concerningFactorContentId,
}: {
  detail: TrajectoryDetail
  concerningFactorOpen: boolean
  setConcerningFactorOpen: (updater: (open: boolean) => boolean) => void
  concerningFactorContentId: string
}) {
  const hasChange = detail.trajectory_change !== null
  const hasConcerningFactor = detail.concerning_factor !== null
  const isCalm = !hasChange && !hasConcerningFactor

  return (
    <>
      {/* Chart section — reached first via keyboard. */}
      <section style={sectionStyle}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
          {CHART_INDICATOR_LABEL[detail.chart_indicator]} ao longo do tempo
        </h2>
        <TrajectoryChart detail={detail} />
      </section>

      {/* Evidence section — only when a change was detected. */}
      {hasChange && (
        <section style={cardStyle}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
            {CHANGE_TYPE_LABEL[detail.trajectory_change!.type]}
          </h2>
          <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
            {detail.trajectory_change!.description} —{' '}
            {formatDetectedAt(detail.trajectory_change!.detected_at)}
          </p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {detail.evidence.map((item, index) => (
              <li
                key={`${item.source_type}-${index}`}
                style={{
                  padding: '8px 12px',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                  {SOURCE_TYPE_LABEL[item.source_type]}
                </span>
                <span>
                  {item.description} — {formatDateBr(item.date)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Concerning-factor section — exactly one confirmed signal, closed by default. */}
      {hasConcerningFactor && !hasChange && (
        <section style={cardStyle}>
          <h2 style={{ margin: 0 }}>
            <button
              type="button"
              aria-expanded={concerningFactorOpen}
              aria-controls={concerningFactorContentId}
              onClick={() => setConcerningFactorOpen((open) => !open)}
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
              <span>Fator preocupante</span>
              <span aria-hidden="true">{concerningFactorOpen ? '−' : '+'}</span>
            </button>
          </h2>
          {concerningFactorOpen && (
            <div id={concerningFactorContentId}>
              <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
                {detail.concerning_factor!.description}
              </p>
            </div>
          )}
        </section>
      )}

      {/* Calm-state card — equal visual weight, replaces evidence/concerning sections. */}
      {isCalm && (
        <section style={cardStyle}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Trajetória estável</h2>
          <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
            Nenhuma mudança relevante detectada dentro do período vigente.
          </p>
        </section>
      )}

      {/* Observations timeline. */}
      <section style={sectionStyle}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Registros pedagógicos recentes</h2>
        {detail.observations.length === 0 ? (
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Nenhum registro pedagógico nos últimos 12 meses.
          </p>
        ) : (
          <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {detail.observations.map((observation: ObservationItem, index) => (
              <li
                key={`${observation.date}-${index}`}
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
                  {formatDateBr(observation.date)}
                </span>
                <span>{observation.text}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Follow-up action — Epic 4 scope, rendered disabled for now. */}
      <section>
        <button
          type="button"
          disabled
          title="Acompanhamento vinculado a evidências chega em uma próxima etapa."
          style={{
            minHeight: 'var(--min-hit-target)',
            padding: '0 20px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text-secondary)',
            fontSize: 15,
            cursor: 'not-allowed',
          }}
        >
          Abrir acompanhamento
        </button>
      </section>
    </>
  )
}
