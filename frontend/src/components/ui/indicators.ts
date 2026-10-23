import type { EvidenceItem } from '../../api/client'
import type { IconName } from './Icon'

/** Fontes de dado do design system. A cor diz de onde vem o sinal, nunca quão grave ele é. */
export type Indicator = 'frequencia' | 'notas' | 'entregas' | 'observacao'

export const INDICATORS: Record<Indicator, { label: string; icon: IconName; color: string }> = {
  frequencia: { label: 'Frequência', icon: 'frequencia', color: 'var(--ind-frequencia)' },
  notas: { label: 'Notas', icon: 'notas', color: 'var(--ind-notas)' },
  entregas: { label: 'Entregas', icon: 'entregas', color: 'var(--ind-entregas)' },
  observacao: { label: 'Observação', icon: 'observacao', color: 'var(--ind-observacao)' },
}

export const INDICATOR_BY_SOURCE_TYPE: Record<EvidenceItem['source_type'], Indicator> = {
  ATTENDANCE_RECORD: 'frequencia',
  GRADE: 'notas',
  ASSIGNMENT_SUBMISSION: 'entregas',
  PEDAGOGICAL_OBSERVATION: 'observacao',
}
