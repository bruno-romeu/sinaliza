import type { FollowUpDetail } from '../api/client'

type FollowUpStatus = FollowUpDetail['status']

// Tokens lifted from DESIGN.md's `followup-status-pill` component (Story
// 4.1): each of the 4 closed states gets its own fill/text pair, never
// `{colors.attention}` and never a 5th ad-hoc "crítico" state.
const STATUS_STYLE: Record<FollowUpStatus, { background: string; color: string; label: string }> = {
  EM_OBSERVACAO: { background: '#EEF3F1', color: 'var(--color-text-secondary)', label: 'Em observação' },
  ACOMPANHAMENTO_ATIVO: { background: '#DCEEE7', color: 'var(--color-primary)', label: 'Ativo' },
  AGUARDANDO_RETORNO: {
    background: '#E8E1D2',
    color: 'var(--color-text-secondary)',
    label: 'Aguardando retorno',
  },
  ENCERRADO: { background: '#E1EEE6', color: 'var(--color-success)', label: 'Encerrado' },
}

/**
 * The follow-up status pill — always renders the text label, never color
 * alone (DESIGN.md `followup-status-pill`).
 */
export function FollowUpStatusPill({ status }: { status: FollowUpStatus }) {
  const style = STATUS_STYLE[status]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 12px',
        borderRadius: 'var(--radius-full)',
        border: '1px solid var(--color-border)',
        background: style.background,
        color: style.color,
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      {style.label}
    </span>
  )
}
