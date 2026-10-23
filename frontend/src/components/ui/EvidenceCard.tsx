import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { EvidenceItem } from '../../api/client'
import { Icon } from './Icon'
import { INDICATORS, INDICATOR_BY_SOURCE_TYPE } from './indicators'

/**
 * Card de evidência: explica uma mudança detectada e lista os registros que
 * a sustentam. Sempre expandido. Só o cabeçalho recebe `attention-tint`.
 * A data de cada registro já vem dentro de `evidence[].description`.
 */
export function EvidenceCard({
  id,
  kicker,
  title,
  description,
  evidence,
  linkTo,
  linkLabel,
}: {
  id?: string
  kicker?: ReactNode
  title: ReactNode
  description?: ReactNode
  evidence: EvidenceItem[]
  linkTo?: string
  linkLabel?: ReactNode
}) {
  const titleId = id ? `${id}-title` : undefined
  return (
    <article className="sz-card sz-evidence" id={id} aria-labelledby={titleId} tabIndex={id ? -1 : undefined}>
      <div className="sz-evidence-head">
        <span className="sz-badge sz-badge-attention" aria-hidden="true">
          <Icon name="sinal" size={20} />
        </span>
        <div>
          <p className="sz-evidence-kicker">{kicker ?? 'Mudança detectada'}</p>
          <h3 className="sz-card-title" id={titleId}>
            {title}
          </h3>
        </div>
      </div>
      <div className="sz-evidence-body">
        {description && <p>{description}</p>}
        {evidence.length > 0 && (
          <>
            <p className="sz-sources-k">Registros que sustentam esta leitura</p>
            <ul className="sz-sources">
              {evidence.map((item, index) => {
                const info = INDICATORS[INDICATOR_BY_SOURCE_TYPE[item.source_type]]
                return (
                  <li key={`${item.source_type}-${index}`}>
                    <Icon name={info.icon} size={18} style={{ color: info.color }} title={info.label} />
                    <span>{item.description}</span>
                  </li>
                )
              })}
            </ul>
          </>
        )}
        {linkTo && (
          <Link className="sz-evidence-link" to={linkTo}>
            {linkLabel}
            <Icon name="seta" size={18} />
          </Link>
        )}
      </div>
    </article>
  )
}
