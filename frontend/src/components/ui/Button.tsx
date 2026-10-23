import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon, type IconName } from './Icon'

type Variant = 'primary' | 'secondary' | 'quiet'

function classes(variant: Variant, className?: string) {
  return ['sz-btn', `sz-btn-${variant}`, className].filter(Boolean).join(' ')
}

function Content({ icon, iconRight, children }: { icon?: IconName; iconRight?: IconName; children: ReactNode }) {
  return (
    <>
      {icon && <Icon name={icon} size={18} />}
      <span>{children}</span>
      {iconRight && <Icon name={iconRight} size={18} />}
    </>
  )
}

/** Botão do design system: `primary` (uma ação principal por tela), `secondary` e `quiet`. */
export function Button({
  variant = 'primary',
  icon,
  iconRight,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  icon?: IconName
  iconRight?: IconName
}) {
  return (
    <button type={type} className={classes(variant, className)} {...rest}>
      <Content icon={icon} iconRight={iconRight}>
        {children}
      </Content>
    </button>
  )
}

/** Mesmo visual do `Button`, para navegação (react-router `Link`). */
export function ButtonLink({
  to,
  variant = 'primary',
  icon,
  iconRight,
  className,
  children,
}: {
  to: string
  variant?: Variant
  icon?: IconName
  iconRight?: IconName
  className?: string
  children: ReactNode
}) {
  return (
    <Link to={to} className={classes(variant, className)}>
      <Content icon={icon} iconRight={iconRight}>
        {children}
      </Content>
    </Link>
  )
}
