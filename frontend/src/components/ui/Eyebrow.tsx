import type { ReactNode } from 'react'

/** Rótulo de seção em maiúsculas, na cor `voice`: o principal recurso de hierarquia entre seções. */
export function Eyebrow({ id, children, as: Tag = 'h2' }: { id?: string; children: ReactNode; as?: 'h2' | 'h3' | 'p' }) {
  return (
    <Tag className="sz-eyebrow" id={id}>
      {children}
    </Tag>
  )
}
