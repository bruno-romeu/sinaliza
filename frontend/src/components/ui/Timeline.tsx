import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import { INDICATORS, type Indicator } from './indicators'

export interface TimelineItem {
  key: string
  date: ReactNode
  text: ReactNode
  /** Fonte do registro; define ícone e cor do nó. */
  indicator?: Indicator
  /** Ícone e rótulo próprios, para itens que não são um indicador (ex.: ação de acompanhamento). */
  icon?: IconName
  label?: ReactNode
  color?: string
  author?: ReactNode
  quote?: boolean
}

/** Linha do tempo somente leitura. Observações pedagógicas aparecem como citação em `voice-tint`. */
export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="sz-timeline">
      {items.map((item) => {
        const info = item.indicator ? INDICATORS[item.indicator] : undefined
        const color = item.color ?? info?.color ?? 'var(--action)'
        const icon = item.icon ?? info?.icon ?? 'check'
        const label = item.label ?? info?.label
        const quote = item.quote ?? item.indicator === 'observacao'
        return (
          <li key={item.key}>
            <span className="sz-tl-date">{item.date}</span>
            <span className="sz-tl-node" style={{ color }} aria-hidden="true">
              <Icon name={icon} size={15} />
            </span>
            <div>
              <p className={['sz-tl-text', quote ? 'sz-tl-quote' : null].filter(Boolean).join(' ')}>{item.text}</p>
              {(label || item.author) && (
                <p className="sz-tl-meta">
                  {label}
                  {item.author && (
                    <>
                      {label ? ' · ' : ''}registrado por <b>{item.author}</b>
                    </>
                  )}
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
