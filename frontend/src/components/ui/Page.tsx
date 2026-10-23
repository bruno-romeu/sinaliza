import type { CSSProperties, ReactNode } from 'react'
import { Header } from '../Header'
import { Eyebrow } from './Eyebrow'

/** Estrutura de uma tela autenticada: cabeçalho e coluna única de até `size-content`. */
export function Page({ children }: { children: ReactNode }) {
  return (
    <div>
      <Header />
      <main className="sz-page">{children}</main>
    </div>
  )
}

export function ScreenHead({
  kicker,
  title,
  display = false,
  center = false,
  children,
}: {
  kicker?: ReactNode
  title: ReactNode
  display?: boolean
  center?: boolean
  children?: ReactNode
}) {
  return (
    <div className={['sz-screen-head', center ? 'is-center' : null].filter(Boolean).join(' ')}>
      {kicker && <p className="sz-kick">{kicker}</p>}
      <h1 className={display ? 'sz-display' : 'sz-title'}>{title}</h1>
      {children}
    </div>
  )
}

/** Seção com rótulo `Eyebrow` e o ritmo vertical do design system (`space-7`). */
export function Section({
  id,
  title,
  children,
  style,
}: {
  id: string
  title: ReactNode
  children: ReactNode
  style?: CSSProperties
}) {
  return (
    <section className="sz-section" aria-labelledby={id} style={style}>
      <Eyebrow id={id}>{title}</Eyebrow>
      <div className="sz-section-body">{children}</div>
    </section>
  )
}

/** Blocos de carregamento: skeleton, nunca spinner de tela cheia. */
export function Skeleton({ heights }: { heights: number[] }) {
  return (
    <div aria-hidden="true" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {heights.map((height, index) => (
        <div key={index} className="sz-skeleton" style={{ height }} />
      ))}
    </div>
  )
}
