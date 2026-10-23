import type { ReactNode } from 'react'
import { Icon } from './Icon'
import { INDICATORS, type Indicator } from './indicators'

/** Etiqueta neutra para metadados: turma, bimestre, disciplina. */
export function Tag({ children }: { children: ReactNode }) {
  return <span className="sz-tag">{children}</span>
}

/** Chip que identifica a fonte de um dado (Frequência, Notas, Entregas, Observação). */
export function IndicatorTag({ indicator, children }: { indicator: Indicator; children?: ReactNode }) {
  const info = INDICATORS[indicator]
  return (
    <span className="sz-tag sz-tag-ind">
      <Icon name={info.icon} size={16} style={{ color: info.color }} />
      {children ?? info.label}
    </span>
  )
}
