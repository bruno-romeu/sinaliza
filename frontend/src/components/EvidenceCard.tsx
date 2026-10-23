import { Link } from 'react-router-dom'
import type { EvidenceItem } from '../api/client'

const SOURCE_TYPE_LABEL: Record<EvidenceItem['source_type'], string> = {
  ATTENDANCE_RECORD: 'Frequência',
  GRADE: 'Nota',
  ASSIGNMENT_SUBMISSION: 'Atividade',
  PEDAGOGICAL_OBSERVATION: 'Registro pedagógico',
}

const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--spacing-card-padding)',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
} as const

function formatDetectedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
}

/**
 * The evidence card — extracted out of `EstudanteTrajetoria.tsx` (Story 4.1
 * spec Code Map) so the Trajectory page and the new Tela de Acompanhamento
 * share identical markup/behavior.
 *
 * `linkTo`/`linkLabel` render the "Ver na trajetória de [aluno]" link
 * (UX-DR4) — omitted entirely on the Trajectory page itself, since that page
 * already *is* that destination.
 */
export function EvidenceCard({
  title,
  description,
  detectedAt,
  evidence,
  linkTo,
  linkLabel,
}: {
  title: string
  description?: string
  detectedAt?: string
  evidence: EvidenceItem[]
  linkTo?: string
  linkLabel?: string
}) {
  return (
    <section style={cardStyle}>
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>{title}</h2>
      {description !== undefined && (
        <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
          {description}
          {detectedAt !== undefined && ` · detectada em ${formatDetectedAt(detectedAt)}`}
        </p>
      )}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {evidence.map((item, index) => (
          <li
            key={`${item.source_type}-${index}`}
            style={{
              padding: '8px 12px',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
              {SOURCE_TYPE_LABEL[item.source_type]}
            </span>
            {/* The backend description already carries the date ("Falta não
                justificada em 20/09/2026"), so it is not repeated here. */}
            <span>{item.description}</span>
          </li>
        ))}
      </ul>
      {linkTo && (
        <div>
          <Link
            to={linkTo}
            style={{
              minHeight: 'var(--min-hit-target)',
              display: 'inline-flex',
              alignItems: 'center',
              color: 'var(--color-primary)',
            }}
          >
            {linkLabel}
          </Link>
        </div>
      )}
    </section>
  )
}
