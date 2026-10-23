import { useId, useState, type ReactNode } from 'react'
import { Icon } from './Icon'

/**
 * Fator preocupante: um sinal isolado que ainda não convergiu em mudança.
 * Mais discreto que o card de evidência. Cabeçalho é um `<button>` com
 * `aria-expanded`; o foco permanece nele ao alternar.
 */
export function ConcernFactor({
  title,
  defaultOpen = false,
  children,
}: {
  title: ReactNode
  defaultOpen?: boolean
  children?: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  return (
    <section className="sz-concern" data-open={open}>
      <button
        type="button"
        className="sz-concern-btn"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="sz-concern-ring" aria-hidden="true" />
        <span>
          <span className="sz-concern-k">Fator preocupante · ainda não confirmado</span>
          <span className="sz-concern-t">{title}</span>
        </span>
        <Icon name="chevron" size={20} className="sz-concern-chev" />
      </button>
      <div id={contentId} className="sz-concern-body" hidden={!open}>
        {open && children}
      </div>
    </section>
  )
}
