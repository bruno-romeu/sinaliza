import { useState, type CSSProperties, type ReactNode } from 'react'
import { Header } from '../Header'
import { Eyebrow } from './Eyebrow'

export const MAIN_ID = 'conteudo'

// Fora de foco o link ocupa zero espaço visual (mesma receita de `.sz-sr`);
// em foco ele vira um botão no canto superior esquerdo. O estilo é inline de
// propósito: nenhum arquivo `.css` é editável nesta camada, e o link precisa
// existir mesmo assim — sem ele o primeiro `Tab` de qualquer tela autenticada
// cai no wordmark e são quatro paradas de cabeçalho até o conteúdo,
// repetidas a cada rota (WCAG 2.4.1, "Bypass Blocks").
const SKIP_HIDDEN: CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
}

const SKIP_VISIBLE: CSSProperties = {
  position: 'absolute',
  left: 16,
  top: 16,
  zIndex: 100,
  width: 'auto',
  height: 'auto',
  overflow: 'visible',
  clip: 'auto',
  whiteSpace: 'nowrap',
}

function SkipToContent() {
  const [focused, setFocused] = useState(false)
  return (
    <a
      href={`#${MAIN_ID}`}
      className="sz-btn sz-btn-secondary"
      style={focused ? SKIP_VISIBLE : SKIP_HIDDEN}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onClick={(event) => {
        // `preventDefault` mantém a URL limpa (sem `#conteudo` no histórico);
        // o foco é movido na mão, que é o que o leitor de tela acompanha.
        event.preventDefault()
        const main = document.getElementById(MAIN_ID)
        if (!main) return
        main.focus()
        // Chamada opcional: `scrollIntoView` não existe em todo ambiente
        // (jsdom, por exemplo), e mover o foco já é o essencial.
        main.scrollIntoView?.({ block: 'start' })
      }}
    >
      <span>Pular para o conteúdo</span>
    </a>
  )
}

/** Estrutura de uma tela autenticada: cabeçalho e coluna única de até `size-content`. */
export function Page({ children }: { children: ReactNode }) {
  return (
    <div>
      <SkipToContent />
      <Header />
      {/* `tabIndex={-1}`: alvo programático do link de pulo, nunca uma parada
          a mais na ordem de tabulação. */}
      <main className="sz-page" id={MAIN_ID} tabIndex={-1}>
        {children}
      </main>
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
    <div
      className={['sz-screen-head', center ? 'is-center' : null]
        .filter(Boolean)
        .join(' ')}
    >
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

/**
 * Blocos de carregamento: skeleton, nunca spinner de tela cheia.
 *
 * Os blocos são decoração (`aria-hidden`), então sozinhos eles deixam quem
 * usa leitor de tela em silêncio até o conteúdo aparecer — foi o que a
 * medição encontrou na Home e na Trajetória (zero regiões live). O texto em
 * `role="status"` diz o que está acontecendo sem ocupar espaço na tela.
 */
export function Skeleton({
  heights,
  label = 'Carregando…',
}: {
  heights: number[]
  label?: string
}) {
  return (
    <>
      <p className="sz-sr" role="status">
        {label}
      </p>
      <div
        aria-hidden="true"
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        {heights.map((height, index) => (
          <div key={index} className="sz-skeleton" style={{ height }} />
        ))}
      </div>
    </>
  )
}
