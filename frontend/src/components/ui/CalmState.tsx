import type { ReactNode } from 'react'
import { Icon } from './Icon'

/** Estado "dentro da faixa habitual": tão cuidadoso quanto o estado com mudança, porque é a maioria dos casos. */
export function CalmState({
  title,
  kicker = 'Dentro da faixa habitual',
  children,
}: {
  title: ReactNode
  kicker?: ReactNode
  children?: ReactNode
}) {
  return (
    <section className="sz-card sz-calm">
      <span className="sz-badge sz-badge-success" aria-hidden="true">
        <Icon name="check" size={20} strokeWidth={2.4} />
      </span>
      <div>
        <p className="sz-calm-kicker">{kicker}</p>
        <h3 className="sz-card-title">{title}</h3>
        {children && <p>{children}</p>}
      </div>
    </section>
  )
}
