import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from './Icon'
import { StatusPill, type FollowUpStatus } from './StatusPill'
import { Tag } from './Tag'

function initials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
}

/** Linha da Home para um acompanhamento em andamento; abre a Tela de Acompanhamento. */
export function FollowupCard({
  to,
  name,
  classroom,
  status,
  lastAction,
}: {
  to: string
  name: string
  classroom?: ReactNode
  status: FollowUpStatus
  lastAction?: ReactNode
}) {
  return (
    <Link className="sz-row" to={to} style={{ alignItems: 'center' }}>
      <span className="sz-avatar" aria-hidden="true">
        {initials(name)}
      </span>
      <span className="sz-row-body">
        <span className="sz-row-top">
          <span className="sz-row-name">{name}</span>
          {classroom && <Tag>{classroom}</Tag>}
        </span>
        {lastAction && <span className="sz-row-desc">{lastAction}</span>}
      </span>
      <StatusPill status={status} />
      <Icon name="chevron-dir" size={20} className="sz-row-chev" />
    </Link>
  )
}

export { initials }
