import { useState } from 'react'
import { Button } from './Button'
import { IndicatorTag } from './Tag'
import type { Indicator } from './indicators'

export interface ChartPoint {
  key: string
  label: string
  value: number | null
}

const W = 640
const H = 240
const PAD = { left: 52, right: 24, top: 28, bottom: 36 }

/**
 * Trajetória real do aluno contra a faixa habitual do próprio histórico
 * dele, nunca contra a turma. Faixa em `band-fill` com contorno tracejado,
 * linha em `trajectory-line`, ponto de mudança em `attention` com halo e
 * rótulo. O ponto de mudança é focável e ativa com Enter/Espaço. A tabela
 * equivalente está sempre no DOM (visível com "Ver como tabela", oculta para
 * leitor de tela caso contrário).
 */
export function TrajectoryChart({
  summary,
  indicator,
  indicatorLabel,
  points,
  band,
  changeIndex,
  changeLabel,
  changeDescription,
  bandLabel,
  format,
  onChangePoint,
}: {
  summary: string
  indicator?: Indicator
  indicatorLabel?: string
  points: ChartPoint[]
  band: { low: number; high: number } | null
  changeIndex?: number
  changeLabel?: string
  changeDescription?: string
  bandLabel: string
  format: (value: number | null) => string
  onChangePoint?: () => void
}) {
  const [showTable, setShowTable] = useState(false)
  const known = points.map((point) => point.value).filter((value): value is number => value !== null)
  const all = [...known, ...(band ? [band.low, band.high] : [])]
  let lo = all.length ? Math.min(...all) : 0
  let hi = all.length ? Math.max(...all) : 1
  const span = hi - lo || Math.abs(hi) || 1
  lo -= span * 0.15
  hi += span * 0.15
  const n = Math.max(points.length, 2)
  const x = (index: number) =>
    points.length <= 1 ? (PAD.left + W - PAD.right) / 2 : PAD.left + (index * (W - PAD.left - PAD.right)) / (n - 1)
  const y = (value: number) => PAD.top + ((hi - value) * (H - PAD.top - PAD.bottom)) / (hi - lo)
  const ticks = [0, 0.5, 1].map((f) => lo + span * 0.15 + f * (hi - lo - span * 0.3))
  const line = points
    .map((point, index) => (point.value === null ? null : `${x(index)},${y(point.value)}`))
    .filter(Boolean)
    .join(' ')
  const change = changeIndex !== undefined && changeIndex >= 0 ? points[changeIndex] : undefined
  // "Saiu da faixa" only when the point is really outside the band; the
  // change can also come from other indicators than the one charted.
  const outsideBand =
    change !== undefined && change.value !== null && band !== null && (change.value < band.low || change.value > band.high)
  const pointLabel = changeLabel ?? (outsideBand ? 'Saiu da faixa' : 'Mudança detectada')

  return (
    <figure className="sz-card sz-chart" style={{ margin: 0 }}>
      <div className="sz-chart-head">
        <div>{indicator && <IndicatorTag indicator={indicator}>{indicatorLabel}</IndicatorTag>}</div>
        <Button
          variant="quiet"
          icon={showTable ? 'grafico' : 'tabela'}
          aria-pressed={showTable}
          onClick={() => setShowTable((current) => !current)}
        >
          {showTable ? 'Ver como gráfico' : 'Ver como tabela'}
        </Button>
      </div>
      {!showTable && (
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
          {ticks.map((tick, index) => (
            <g key={`t${index}`}>
              <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} />
              <text className="axis" x={PAD.left - 10} y={y(tick) + 4} textAnchor="end">
                {format(tick)}
              </text>
            </g>
          ))}
          {band && points.length > 1 && (
            <rect
              className="band"
              x={x(0)}
              y={y(band.high)}
              width={x(points.length - 1) - x(0)}
              height={Math.max(y(band.low) - y(band.high), 1)}
            />
          )}
          {line && <polyline className="line" points={line} />}
          {points.map((point, index) =>
            point.value === null || index === changeIndex ? null : (
              <circle key={point.key} className="dot" cx={x(index)} cy={y(point.value)} r={4.5} />
            ),
          )}
          {points.map((point, index) => (
            <text
              key={`x${point.key}`}
              className={['axis', index === changeIndex ? 'axis-hot' : null].filter(Boolean).join(' ')}
              x={x(index)}
              y={H - 10}
              textAnchor={points.length > 1 && index === 0 ? 'start' : points.length > 1 && index === points.length - 1 ? 'end' : 'middle'}
            >
              {point.label}
            </text>
          ))}
          {change && change.value !== null && changeIndex !== undefined && (
            <g
              className="cp"
              tabIndex={0}
              role="button"
              aria-label={`Mudança detectada em ${change.label}: ${format(change.value)}${changeDescription ? `. ${changeDescription}` : ''}. Ver evidência.`}
              onClick={onChangePoint}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onChangePoint?.()
                }
              }}
            >
              <circle className="cp-hit" cx={x(changeIndex)} cy={y(change.value)} r={22} />
              <circle className="cp-halo" cx={x(changeIndex)} cy={y(change.value)} r={12} />
              <circle className="cp-ring" cx={x(changeIndex)} cy={y(change.value)} r={11} />
              <circle className="cp-dot" cx={x(changeIndex)} cy={y(change.value)} r={5} />
              <text className="cp-label" x={x(changeIndex)} y={y(change.value) - 20} textAnchor="middle">
                {pointLabel}
              </text>
            </g>
          )}
        </svg>
      )}
      <table className={showTable ? 'sz-table' : 'sz-sr'}>
        <caption className="sz-sr">{summary}</caption>
        <thead>
          <tr>
            <th scope="col">Bimestre</th>
            <th scope="col">{indicatorLabel ?? 'Valor'}</th>
            <th scope="col">Faixa habitual</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.key}>
              <td>{point.label}</td>
              <td>{format(point.value)}</td>
              <td>{band ? `${format(band.low)} a ${format(band.high)}` : 'Sem registro'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!showTable && (
        <ul className="sz-legend">
          {band && (
            <li>
              <span className="sw-band" />
              {bandLabel}
            </li>
          )}
          <li>
            <span className="sw-line" />
            Trajetória real
          </li>
          {change && (
            <li>
              <span className="sw-cp" />
              Mudança detectada
            </li>
          )}
        </ul>
      )}
    </figure>
  )
}
