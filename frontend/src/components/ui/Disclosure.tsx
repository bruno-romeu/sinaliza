import { useId, useState, type ReactNode } from 'react'
import { Icon } from './Icon'

/**
 * Seção recolhível: o cabeçalho é um `<button>` nativo com `aria-expanded`
 * (Enter/Espaço de graça) no estilo do rótulo `Eyebrow`. Aberta por padrão,
 * para telas cujo propósito é revisar histórico.
 */
export function Disclosure({
  title,
  defaultOpen = true,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  return (
    <section className="sz-section sz-disclosure" data-open={open}>
      <h2 className="sz-eyebrow" style={{ margin: 0 }}>
        <button
          type="button"
          className="sz-disclosure-btn"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((current) => !current)}
        >
          <span>{title}</span>
          <Icon name="chevron" size={18} className="sz-disclosure-chev" />
        </button>
      </h2>
      <div id={contentId} className="sz-section-body" style={{ marginTop: 12 }}>
        {open && children}
      </div>
    </section>
  )
}
