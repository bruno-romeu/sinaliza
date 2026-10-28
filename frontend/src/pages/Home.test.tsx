import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { Home } from './Home'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <AuthProvider>
        <Home />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Home — mudanças recentes e busca de estudantes (Story 3.3)', () => {
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

  it('shows one row per recent change, ordered as returned by the API', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({
          recent_changes: [
            {
              student_id: 'student-1',
              student_name: 'Maria Silva',
              type: 'ATTENDANCE_DROP',
              description: 'Queda de frequência no 3º Bimestre',
              detected_at: '2026-09-24T00:00:00Z',
            },
            {
              student_id: 'student-2',
              student_name: 'João Souza',
              type: 'COMBINED_DETERIORATION',
              description: 'Queda de frequência e queda de notas no 3º Bimestre',
              detected_at: '2026-09-20T00:00:00Z',
            },
          ],
          in_progress_follow_ups: [],
        })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()

    await screen.findByText('Maria Silva')
    expect(screen.getByText('João Souza')).toBeInTheDocument()

    const links = screen.getAllByRole('link').filter((link) => link.getAttribute('href')?.startsWith('/estudantes/'))
    expect(links[0]).toHaveAttribute('href', '/estudantes/student-1')
    expect(links[1]).toHaveAttribute('href', '/estudantes/student-2')
  })

  it('shows the explicit empty-state message when there are no recent changes', async () => {
    fetchMock = vi.fn(async () => jsonResponse({ recent_changes: [], in_progress_follow_ups: [] }))
    vi.stubGlobal('fetch', fetchMock)

    renderHome()

    await screen.findByText('Nenhuma mudança a revisar hoje.')
  })

  it('shows a factual error message with a retry action on load failure', async () => {
    fetchMock = vi.fn(async () => jsonResponse({ error: { code: 'server_error', message: 'boom' } }, 500))
    vi.stubGlobal('fetch', fetchMock)

    renderHome()

    await screen.findByText('Não foi possível carregar os dados agora.')
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
  })

  it('searches by name/turma and announces the result count via aria-live', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({ recent_changes: [], in_progress_follow_ups: [] })
      }
      if (url.startsWith('/api/home/search')) {
        return jsonResponse({
          results: [{ id: 'student-3', name: 'Ana Pereira', classroom_name: '7º Ano A' }],
          count: 1,
        })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Nenhuma mudança a revisar hoje.')

    fireEvent.change(screen.getByLabelText('Buscar estudante por nome ou turma'), {
      target: { value: 'Ana' },
    })

    await screen.findByText('Ana Pereira')
    expect(screen.getByText('1 estudante encontrado')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ana Pereira/ })).toHaveAttribute(
      'href',
      '/estudantes/student-3',
    )
  })

  it('shows a factual error message when the search request fails', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({ recent_changes: [], in_progress_follow_ups: [] })
      }
      if (url.startsWith('/api/home/search')) {
        return jsonResponse({ error: { code: 'server_error', message: 'boom' } }, 500)
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Nenhuma mudança a revisar hoje.')

    fireEvent.change(screen.getByLabelText('Buscar estudante por nome ou turma'), {
      target: { value: 'Ana' },
    })

    await screen.findByText('boom')
  })

  it('loads and appends the next page of search results on "Ver mais"', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({ recent_changes: [], in_progress_follow_ups: [] })
      }
      if (url.startsWith('/api/home/search')) {
        if (url.includes('page=2')) {
          return jsonResponse({
            results: [{ id: 'student-4', name: 'Bruna Lima', classroom_name: '7º Ano B' }],
            count: 1,
            total: 2,
            page: 2,
            page_size: 1,
          })
        }
        return jsonResponse({
          results: [{ id: 'student-3', name: 'Ana Pereira', classroom_name: '7º Ano A' }],
          count: 1,
          total: 2,
          page: 1,
          page_size: 1,
        })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Nenhuma mudança a revisar hoje.')

    fireEvent.change(screen.getByLabelText('Buscar estudante por nome ou turma'), {
      target: { value: 'a' },
    })

    await screen.findByText('Ana Pereira')
    const loadMore = screen.getByRole('button', { name: 'Ver mais (1 restantes)' })

    fireEvent.click(loadMore)

    await screen.findByText('Bruna Lima')
    expect(screen.getByText('Ana Pereira')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ver mais/ })).not.toBeInTheDocument()
  })

  it('shows the no-match message, with no suggestions, when search returns nothing', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({ recent_changes: [], in_progress_follow_ups: [] })
      }
      if (url.startsWith('/api/home/search')) {
        return jsonResponse({ results: [], count: 0 })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Nenhuma mudança a revisar hoje.')

    fireEvent.change(screen.getByLabelText('Buscar estudante por nome ou turma'), {
      target: { value: 'Inexistente' },
    })

    await screen.findByText('Nenhum estudante encontrado com esse nome/turma.')
  })
})

describe('Home — acompanhamentos em andamento (Story 4.5)', () => {
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

  it('shows one card per in-progress follow-up, with status pill, student name and a full-card link', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        recent_changes: [],
        in_progress_follow_ups: [
          { id: 'fu-1', student_id: 'student-1', student_name: 'Maria Silva', status: 'EM_OBSERVACAO' },
          { id: 'fu-2', student_id: 'student-2', student_name: 'João Souza', status: 'ACOMPANHAMENTO_ATIVO' },
        ],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderHome()

    await screen.findByText('Maria Silva')
    expect(screen.getByText('João Souza')).toBeInTheDocument()
    expect(screen.getByText('Em observação')).toBeInTheDocument()
    expect(screen.getByText('Ativo')).toBeInTheDocument()

    const link = screen.getByText('Maria Silva').closest('a')
    expect(link).toHaveAttribute('href', '/acompanhamentos/fu-1')
  })

  it('shows the neutral empty-state message when there are no active follow-ups', async () => {
    fetchMock = vi.fn(async () => jsonResponse({ recent_changes: [], in_progress_follow_ups: [] }))
    vi.stubGlobal('fetch', fetchMock)

    renderHome()

    await screen.findByText('Nenhum acompanhamento em andamento no momento')
  })

  it('loads and appends the next page of in-progress follow-ups on "Ver mais"', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('follow_ups_page=2')) {
        return jsonResponse({
          recent_changes: [],
          in_progress_follow_ups: [
            { id: 'fu-2', student_id: 'student-2', student_name: 'João Souza', status: 'ACOMPANHAMENTO_ATIVO' },
          ],
          in_progress_follow_ups_total: 2,
          in_progress_follow_ups_page: 2,
          in_progress_follow_ups_page_size: 1,
        })
      }
      return jsonResponse({
        recent_changes: [],
        in_progress_follow_ups: [
          { id: 'fu-1', student_id: 'student-1', student_name: 'Maria Silva', status: 'EM_OBSERVACAO' },
        ],
        in_progress_follow_ups_total: 2,
        in_progress_follow_ups_page: 1,
        in_progress_follow_ups_page_size: 1,
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Maria Silva')
    const loadMore = screen.getByRole('button', { name: 'Ver mais (1 restantes)' })

    fireEvent.click(loadMore)

    await screen.findByText('João Souza')
    expect(screen.getByText('Maria Silva')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ver mais/ })).not.toBeInTheDocument()
  })

  it('keeps the active-follow-ups section visible while search results are showing', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.startsWith('/api/home') && !url.startsWith('/api/home/search')) {
        return jsonResponse({
          recent_changes: [],
          in_progress_follow_ups: [
            { id: 'fu-1', student_id: 'student-1', student_name: 'Maria Silva', status: 'EM_OBSERVACAO' },
          ],
        })
      }
      if (url.startsWith('/api/home/search')) {
        return jsonResponse({ results: [], count: 0 })
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderHome()
    await screen.findByText('Maria Silva')

    fireEvent.change(screen.getByLabelText('Buscar estudante por nome ou turma'), {
      target: { value: 'Inexistente' },
    })

    await screen.findByText('Nenhum estudante encontrado com esse nome/turma.')
    expect(screen.getByText('Maria Silva')).toBeInTheDocument()
  })
})
