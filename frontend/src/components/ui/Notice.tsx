import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

type Tone = 'success' | 'info' | 'attention'
const ICON: Record<Tone, IconName> = { success: 'check', info: 'info', attention: 'sinal' }

/** Aviso em linha, sem modal: confirmação, informação ou falha. Nunca vermelho. */
export function Notice({
  tone = 'info',
  role,
  children,
  action,
}: {
  tone?: Tone
  role?: 'status' | 'alert'
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className={`sz-notice sz-notice-${tone}`} role={role ?? (tone === 'attention' ? 'alert' : 'status')}>
      <span className={`sz-badge sz-badge-${tone}`} aria-hidden="true">
        <Icon name={ICON[tone]} size={16} strokeWidth={2.4} />
      </span>
      <span style={{ flex: 1 }}>{children}</span>
      {action}
    </div>
  )
}
