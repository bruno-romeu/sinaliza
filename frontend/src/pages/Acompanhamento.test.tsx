import { fireEvent, render, screen, within } from '@testing-library/react'
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

function baseDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
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
    ...overrides,
  }
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

    await screen.findByText('Maria Silva')
    expect(
      within(screen.getByText('Maria Silva').closest('section') as HTMLElement).getByText(
        'Em observação',
      ),
    ).toBeInTheDocument()
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

  it('shows a native <select> with exactly the 4 closed status values', async () => {
    fetchMock = vi.fn(async () => jsonResponse(baseDetail()))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    const select = screen.getByLabelText('Status do acompanhamento')
    const options = within(select).getAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual([
      'Em observação',
      'Ativo',
      'Aguardando retorno',
      'Encerrado',
    ])
  })

  it('selecting "Encerrado" without confirming makes no request and reverts the select', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1') {
        return jsonResponse(baseDetail())
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('confirm', vi.fn(() => false))

    renderPage()

    await screen.findByText('Maria Silva')
    const select = screen.getByLabelText('Status do acompanhamento') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'ENCERRADO' } })

    expect(window.confirm).toHaveBeenCalled()
    expect(select.value).toBe('EM_OBSERVACAO')
    const statusCalls = fetchMock.mock.calls.filter(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url.includes('/status')
    })
    expect(statusCalls).toHaveLength(0)
  })

  it('selecting a non-"Encerrado" status calls the API immediately and updates the pill', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1' && (init?.method ?? 'GET') === 'GET') {
        return jsonResponse(baseDetail())
      }
      if (url === '/api/follow-ups/follow-up-1/status' && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body))
        return jsonResponse({
          id: 'follow-up-1',
          student_id: 'student-1',
          status: body.status,
          created_at: '2026-10-13T00:00:00Z',
        })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    const select = screen.getByLabelText('Status do acompanhamento')
    fireEvent.change(select, { target: { value: 'ACOMPANHAMENTO_ATIVO' } })

    const pillSection = screen.getByText('Maria Silva').closest('section') as HTMLElement
    await within(pillSection).findByText('Ativo')
    expect(within(pillSection).queryByText('Em observação')).not.toBeInTheDocument()

    const statusCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/follow-ups/follow-up-1/status'
    })
    expect(statusCall).toBeDefined()
    const [, init] = statusCall as [RequestInfo | URL, RequestInit]
    expect(init?.method).toBe('PATCH')
    expect(JSON.parse(String(init?.body))).toEqual({ status: 'ACOMPANHAMENTO_ATIVO' })
  })

  it('shows an inline error and re-enables the select when the status PATCH fails', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1' && (init?.method ?? 'GET') === 'GET') {
        return jsonResponse(baseDetail())
      }
      if (url === '/api/follow-ups/follow-up-1/status' && init?.method === 'PATCH') {
        return jsonResponse(
          { error: { code: 'follow_up_not_found', message: 'Acompanhamento não encontrado.' } },
          404,
        )
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    const select = screen.getByLabelText('Status do acompanhamento') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'ACOMPANHAMENTO_ATIVO' } })

    await screen.findByText('Acompanhamento não encontrado.')
    expect(select).not.toBeDisabled()
  })

  it('selecting "Encerrado" and confirming calls the API and updates the pill', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1' && (init?.method ?? 'GET') === 'GET') {
        return jsonResponse(baseDetail())
      }
      if (url === '/api/follow-ups/follow-up-1/status' && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body))
        return jsonResponse({
          id: 'follow-up-1',
          student_id: 'student-1',
          status: body.status,
          created_at: '2026-10-13T00:00:00Z',
        })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('confirm', vi.fn(() => true))

    renderPage()

    await screen.findByText('Maria Silva')
    const select = screen.getByLabelText('Status do acompanhamento')
    fireEvent.change(select, { target: { value: 'ENCERRADO' } })

    expect(window.confirm).toHaveBeenCalled()
    const pillSection = screen.getByText('Maria Silva').closest('section') as HTMLElement
    await within(pillSection).findByText('Encerrado')

    const statusCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/follow-ups/follow-up-1/status'
    })
    expect(statusCall).toBeDefined()
    const [, init] = statusCall as [RequestInfo | URL, RequestInit]
    expect(init?.method).toBe('PATCH')
    expect(JSON.parse(String(init?.body))).toEqual({ status: 'ENCERRADO' })
  })

  it('keeps the action save button disabled while the textarea is empty', async () => {
    fetchMock = vi.fn(async () => jsonResponse(baseDetail()))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    const saveButton = screen.getByRole('button', { name: 'Salvar' })
    expect(saveButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Ação'), { target: { value: '   ' } })
    expect(saveButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Ação'), { target: { value: 'Conversei com a família.' } })
    expect(saveButton).not.toBeDisabled()
  })

  it('submits a new action and shows "Registro salvo." on success', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1' && (init?.method ?? 'GET') === 'GET') {
        return jsonResponse(baseDetail())
      }
      if (url === '/api/follow-ups/follow-up-1/actions' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(
          {
            id: 'action-1',
            follow_up_id: 'follow-up-1',
            description: body.description,
            author_user_id: 'u1',
            created_at: '2026-10-14T12:00:00Z',
          },
          201,
        )
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    fireEvent.change(screen.getByLabelText('Ação'), { target: { value: 'Conversei com a família.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await screen.findByText('Registro salvo.')

    const actionCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/follow-ups/follow-up-1/actions'
    })
    expect(actionCall).toBeDefined()
    const [, init] = actionCall as [RequestInfo | URL, RequestInit]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ description: 'Conversei com a família.' })
  })

  it('shows an inline error when submitting an action fails', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/follow-ups/follow-up-1' && (init?.method ?? 'GET') === 'GET') {
        return jsonResponse(baseDetail())
      }
      if (url === '/api/follow-ups/follow-up-1/actions' && init?.method === 'POST') {
        return jsonResponse(
          { error: { code: 'follow_up_not_found', message: 'Acompanhamento não encontrado.' } },
          404,
        )
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Maria Silva')
    fireEvent.change(screen.getByLabelText('Ação'), { target: { value: 'Conversei com a família.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await screen.findByText('Acompanhamento não encontrado.')
  })
})
