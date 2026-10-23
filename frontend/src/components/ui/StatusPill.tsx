import type { FollowUpDetail } from '../../api/client'
import { Icon, type IconName } from './Icon'

export type FollowUpStatus = FollowUpDetail['status']

export const FOLLOW_UP_STATUS: Record<FollowUpStatus, { label: string; icon: IconName; className: string }> = {
  EM_OBSERVACAO: { label: 'Em observação', icon: 'olho', className: 'sz-pill-observacao' },
  ACOMPANHAMENTO_ATIVO: { label: 'Ativo', icon: 'ativo', className: 'sz-pill-ativo' },
  AGUARDANDO_RETORNO: { label: 'Aguardando retorno', icon: 'relogio', className: 'sz-pill-aguardando' },
  ENCERRADO: { label: 'Encerrado', icon: 'encerrado', className: 'sz-pill-encerrado' },
}

/**
 * Pílula de status de acompanhamento: os 4 estados fechados, cada um com
 * fundo, tinta e ícone próprios, sempre com o rótulo em texto. Nunca usa
 * `attention` e nunca ganha um quinto estado.
 */
export function StatusPill({ status }: { status: FollowUpStatus }) {
  const info = FOLLOW_UP_STATUS[status]
  return (
    <span className={`sz-pill ${info.className}`}>
      <Icon name={info.icon} size={16} />
      {info.label}
    </span>
  )
}
