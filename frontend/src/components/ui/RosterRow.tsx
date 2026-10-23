import type { ReactNode } from 'react'
import { Button } from './Button'
import { initials } from './FollowupCard'
import { Icon } from './Icon'

export type RosterStatus = 'idle' | 'saving' | 'saved' | 'error'

/**
 * Linha de um aluno numa lista de lançamento: nome, controle do registro e
 * salvamento só daquela linha (a API grava um aluno por vez). A mensagem da
 * linha fica numa região `aria-live`.
 */
export function RosterRow({
  nameId,
  name,
  meta,
  status = 'idle',
  message,
  messageId,
  onSave,
  saveDisabled,
  saveLabel = 'Salvar',
  extra,
  children,
}: {
  nameId: string
  name: string
  meta?: ReactNode
  status?: RosterStatus
  message?: string | null
  /** id da mensagem, para o controle da linha apontar `aria-describedby` para ela. */
  messageId?: string
  onSave?: () => void
  saveDisabled?: boolean
  saveLabel?: string
  extra?: ReactNode
  children?: ReactNode
}) {
  const shown = message ?? (status === 'saved' ? 'Registro salvo.' : null)
  return (
    <div className="sz-rrow" data-status={status}>
      <span className="sz-avatar" aria-hidden="true">
        {initials(name)}
      </span>
      <span className="sz-rrow-name" id={nameId}>
        {name}
        {meta && <span className="sz-rrow-meta">{meta}</span>}
      </span>
      <div className="sz-rrow-ctl">{children}</div>
      <div className="sz-rrow-act">
        {onSave && (
          <Button
            variant={status === 'saved' ? 'secondary' : 'primary'}
            disabled={saveDisabled || status === 'saving'}
            onClick={onSave}
            aria-describedby={nameId}
          >
            {status === 'saving' ? 'Salvando…' : saveLabel}
          </Button>
        )}
      </div>
      {extra && <div className="sz-rrow-extra">{extra}</div>}
      <p
        id={messageId}
        className={shown ? 'sz-rrow-msg' : 'sz-sr'}
        data-tone={status === 'error' ? 'error' : status === 'saved' ? 'saved' : undefined}
        role={status === 'error' ? 'alert' : 'status'}
        aria-live="polite"
      >
        {shown && <Icon name={status === 'error' ? 'info' : 'check'} size={15} strokeWidth={2.4} />}
        {shown}
      </p>
    </div>
  )
}
