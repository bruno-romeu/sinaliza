import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { Acompanhamento } from './Acompanhamento'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPage(followUpId = 'follow-up-1') {
  return render(
    <MemoryRouter initialEntries={[`/acompanhamentos/${followUpId}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/acompanhamentos/:followUpId" element={<Acompanhamento />} />
          <Route path="/home" element={<div>Home mock</div>} />
          <Route path="/estudantes/:studentId" element={<div>Trajetória mock</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Acompanhamento — tela de acompanhamento (Story 4.1)', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: 'fake-token',
        user: { id: 'u1', name: 'Test User', email: 'test@example.com', role: 'COORDENACAO_PEDAGOGICA' },
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the "Em observação" pill, student name, and evidence with a working link back to the trajectory', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        id: 'follow-up-1',
        student_id: 'student-1',
        student_name: 'Maria Silva',
        status: 'EM_OBSERVACAO',
        created_at: '2026-10-13T00:00:00Z',
        evidence: [
          {
            source_type: 'ATTENDANCE_RECORD',
            description: 'Falta não justificada em 20/09/2026',
            date: '2026-09-20',
          },
        ],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Em observação')
    expect(screen.getByText('Maria Silva')).toBeInTheDocument()
    expect(screen.getByText('Falta não justificada em 20/09/2026', { exact: false })).toBeInTheDocument()

    const link = screen.getByRole('link', { name: 'Ver na trajetória de Maria Silva' })
    expect(link).toHaveAttribute('href', '/estudantes/student-1')
  })

  it('shows a loading skeleton before the response resolves', () => {
    fetchMock = vi.fn(() => new Promise<Response>(() => {}))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    expect(screen.getByText('Acompanhamento')).toBeInTheDocument()
    expect(screen.queryByText('Em observação')).not.toBeInTheDocument()
  })

  it('shows a factual not-found message with a link back to Home for an unknown follow-up', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse(
        { error: { code: 'follow_up_not_found', message: 'Acompanhamento não encontrado.' } },
        404,
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage('unknown-follow-up')

    await screen.findByText('Acompanhamento não encontrado.')
    expect(screen.getByRole('link', { name: 'Voltar para a Home' })).toHaveAttribute('href', '/home')
  })

  it('shows a factual error message with retry on load failure', async () => {
    fetchMock = vi.fn(async () => jsonResponse({ error: { code: 'server_error', message: 'boom' } }, 500))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Não foi possível carregar os dados agora.')
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
  })
})
