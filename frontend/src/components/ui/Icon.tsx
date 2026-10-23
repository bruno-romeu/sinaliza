import type { CSSProperties, ReactElement } from 'react'

/** Conjunto de ícones de traço do design system (24px, traço 1.9, `currentColor`). */
const PATHS = {
  sinal: (
    <>
      <circle cx={12} cy={12} r={3} fill="currentColor" stroke="none" />
      <path d="M6.3 6.3a8 8 0 0 0 0 11.4M17.7 6.3a8 8 0 0 1 0 11.4" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  frequencia: (
    <>
      <rect x={4} y={5} width={16} height={15} rx={2.5} />
      <path d="M4 10h16M8.5 3v4M15.5 3v4M9 15l2 2 4-4" />
    </>
  ),
  notas: <path d="M5 19V9M10 19V5M15 19v-7M20 19v-4" />,
  entregas: (
    <>
      <path d="M7 3.5h7l4.5 4.5v12a.5.5 0 0 1-.5.5H7a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 7 3.5z" />
      <path d="M14 3.5V8h4.5M9 13.5l2 2 4-4" />
    </>
  ),
  observacao: (
    <>
      <path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 1-1.5 1.5h-7l-4.5 3.5V17H5a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 5 5.5z" />
      <path d="M8 10h8M8 13h5" />
    </>
  ),
  busca: (
    <>
      <circle cx={11} cy={11} r={6.5} />
      <path d="M16 16l4.5 4.5" />
    </>
  ),
  seta: <path d="M5 12h14M13 6l6 6-6 6" />,
  voltar: <path d="M19 12H5M11 6l-6 6 6 6" />,
  chevron: <path d="M6 9l6 6 6-6" />,
  'chevron-dir': <path d="M9 6l6 6-6 6" />,
  olho: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx={12} cy={12} r={3} />
    </>
  ),
  ativo: (
    <>
      <circle cx={12} cy={12} r={8} />
      <path d="M10 8.5l5 3.5-5 3.5z" fill="currentColor" />
    </>
  ),
  relogio: (
    <>
      <circle cx={12} cy={12} r={8} />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  encerrado: (
    <>
      <circle cx={12} cy={12} r={8} />
      <path d="M8.5 12.2l2.4 2.4 4.6-4.8" />
    </>
  ),
  info: (
    <>
      <circle cx={12} cy={12} r={8.5} />
      <path d="M12 11v5" />
      <circle cx={12} cy={8} r={1} fill="currentColor" stroke="none" />
    </>
  ),
  mais: <path d="M12 5v14M5 12h14" />,
  pessoa: (
    <>
      <circle cx={12} cy={8.5} r={3.5} />
      <path d="M5 19.5c1.2-3.3 3.9-5 7-5s5.8 1.7 7 5" />
    </>
  ),
  tabela: (
    <>
      <rect x={3.5} y={5} width={17} height={14} rx={2} />
      <path d="M3.5 10h17M3.5 14.5h17M9.5 10v9" />
    </>
  ),
  grafico: (
    <>
      <path d="M4 4v16h16" />
      <path d="M7 15l4-4 3 3 5-6" />
    </>
  ),
  sair: <path d="M15 4.5h3A1.5 1.5 0 0 1 19.5 6v12a1.5 1.5 0 0 1-1.5 1.5h-3M10 16l-4-4 4-4M6 12h10" />,
} satisfies Record<string, ReactElement>

export type IconName = keyof typeof PATHS

export function Icon({
  name,
  size = 20,
  title,
  strokeWidth = 1.9,
  className,
  style,
}: {
  name: IconName
  size?: number
  title?: string
  strokeWidth?: number
  className?: string
  style?: CSSProperties
}) {
  return (
    <svg
      className={['sz-icon', className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      style={style}
    >
      {PATHS[name]}
    </svg>
  )
}
