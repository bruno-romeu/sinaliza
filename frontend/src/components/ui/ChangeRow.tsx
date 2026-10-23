import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from './Icon'
import { IndicatorTag, Tag } from './Tag'
import type { Indicator } from './indicators'

/** Linha da Home para uma mudança recente. A linha inteira é o link. Ordem por data, nunca por gravidade. */
export function ChangeRow({
  to,
  name,
  classroom,
  description,
  date,
  indicators,
}: {
  to: string
  name: ReactNode
  classroom?: ReactNode
  description: ReactNode
  date?: ReactNode
  indicators?: Indicator[]
}) {
  return (
    <Link className="sz-row" to={to}>
      <span className="sz-badge sz-badge-attention" aria-hidden="true">
        <Icon name="sinal" size={20} />
      </span>
      <span className="sz-row-body">
        <span className="sz-row-top">
          <span className="sz-row-name">{name}</span>
          {classroom && <Tag>{classroom}</Tag>}
        </span>
        <span className="sz-row-desc">
          <span className="sz-sr">Mudança recente: </span>
          {description}
        </span>
        {indicators && indicators.length > 0 && (
          <span className="sz-row-meta">
            {indicators.map((indicator) => (
              <IndicatorTag key={indicator} indicator={indicator} />
            ))}
          </span>
        )}
      </span>
      <span className="sz-row-side">
        <span className="sz-row-label" aria-hidden="true">
          MUDANÇA RECENTE
        </span>
        {date && <span>Detectado em {date}</span>}
      </span>
      <Icon name="chevron-dir" size={20} className="sz-row-chev" />
    </Link>
  )
}
