import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { MAIN_ID, Page, Skeleton } from './Page'

const STORAGE_KEY = 'sinaliza.session'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AuthProvider>
        <Page>
          <p>Conteúdo da tela</p>
        </Page>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Page — bypass da navegação repetida (WCAG 2.4.1)', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: 'fake-token',
        user: {
          id: 'u1',
          name: 'Test User',
          email: 'test@example.com',
          role: 'COORDENACAO_PEDAGOGICA',
        },
      }),
    )
  })

  it('oferece o link de pulo antes de qualquer link do cabeçalho', () => {
    renderPage()

    // Testing Library devolve os elementos na ordem do documento, que é a
    // ordem de tabulação aqui (ninguém usa `tabindex` positivo). Antes desta
    // onda o primeiro `Tab` caía no wordmark e eram quatro paradas de
    // cabeçalho até o conteúdo, repetidas a cada rota.
    const skip = screen.getByRole('link', { name: 'Pular para o conteúdo' })
    expect(screen.getAllByRole('link')[0]).toBe(skip)
  })

  it('leva o foco para o <main>, que não é uma parada a mais na tabulação', () => {
    renderPage()

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', MAIN_ID)
    // `-1`: alvo programático, nunca percorrido por `Tab`.
    expect(main).toHaveAttribute('tabindex', '-1')

    fireEvent.click(screen.getByRole('link', { name: 'Pular para o conteúdo' }))
    expect(main).toHaveFocus()
  })
})

describe('Skeleton — carregamento anunciado', () => {
  it('acompanha os blocos decorativos de um texto em role="status"', () => {
    // Os blocos são `aria-hidden`; sozinhos, deixam quem usa leitor de tela
    // em silêncio até o conteúdo aparecer.
    render(<Skeleton heights={[72, 72]} />)

    expect(screen.getByRole('status')).toHaveTextContent('Carregando…')
  })
})
