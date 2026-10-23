import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { EstudanteTrajetoria } from './EstudanteTrajetoria'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPage(studentId = 'student-1') {
  return render(
    <MemoryRouter initialEntries={[`/estudantes/${studentId}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/estudantes/:studentId" element={<EstudanteTrajetoria />} />
          <Route path="/home" element={<div>Home mock</div>} />
          <Route path="/acompanhamentos/:followUpId" element={<div>Acompanhamento mock</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

const SERIES = [
  { period_id: 'p1', period_label: '2º Bimestre', value: '0.9000' },
  { period_id: 'p2', period_label: '3º Bimestre', value: '0.5000' },
]

describe('EstudanteTrajetoria — trajetória do estudante (Story 3.4)', () => {
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

  it('shows the chart, evidence card and no concerning factor when a change was detected', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        chart_indicator: 'attendance_rate',
        series: SERIES,
        habitual_range: { low: '0.5000', high: '0.9000' },
        trajectory_change: {
          id: 'change-1',
          type: 'ATTENDANCE_DROP',
          period_id: 'p2',
          detected_at: '2026-09-24T00:00:00Z',
          description: 'Queda de frequência no 3º Bimestre',
        },
        evidence: [
          { source_type: 'ATTENDANCE_RECORD', description: 'Falta não justificada em 20/09/2026', date: '2026-09-20' },
          { source_type: 'PEDAGOGICAL_OBSERVATION', description: 'Registro pedagógico em 01/09/2026: Observação.', date: '2026-09-01' },
        ],
        concerning_factor: null,
        observations: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Queda de frequência')
    expect(screen.getByRole('img', { name: /Gráfico de frequência por bimestre/ })).toBeInTheDocument()
    expect(screen.getByText('Falta não justificada em 20/09/2026', { exact: false })).toBeInTheDocument()
    expect(screen.queryByText('Fator preocupante')).not.toBeInTheDocument()
    expect(screen.queryByText('Trajetória estável')).not.toBeInTheDocument()

    const changePointButton = screen.getByRole('button', { name: /Mudança detectada em 3º Bimestre/ })
    expect(changePointButton).toBeInTheDocument()

    // WCAG 1.1.1 text-table alternative to the SVG chart.
    const table = screen.getByRole('table')
    expect(table).toHaveAccessibleName(/Gráfico de frequência por bimestre/)
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(SERIES.length + 1) // header + one per series point
    expect(screen.getByRole('cell', { name: '3º Bimestre' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '50%' })).toBeInTheDocument()
  })

  it('shows the calm-state card with equal weight when there is no change or concerning factor', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        chart_indicator: 'attendance_rate',
        series: SERIES,
        habitual_range: { low: '0.5000', high: '0.9000' },
        trajectory_change: null,
        evidence: [],
        concerning_factor: null,
        observations: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Trajetória estável')
    expect(screen.queryByText('Fator preocupante')).not.toBeInTheDocument()
  })

  it('renders the chart without a habitual-range band when fewer than 2 history points exist', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        chart_indicator: 'attendance_rate',
        series: [{ period_id: 'p1', period_label: '3º Bimestre', value: '0.9000' }],
        habitual_range: null,
        trajectory_change: null,
        evidence: [],
        concerning_factor: null,
        observations: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { container } = renderPage()

    await screen.findByText('Trajetória estável')
    // No fabricated range -> the chart renders the trend line with no band,
    // never a crash (code review finding, Story 3.4).
    expect(container.querySelector('rect')).not.toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Gráfico de frequência por bimestre/ })).toBeInTheDocument()
  })

  it('shows the concerning-factor header closed by default, expandable via keyboard, with no evidence list', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        chart_indicator: 'attendance_rate',
        series: SERIES,
        habitual_range: { low: '0.5000', high: '0.9000' },
        trajectory_change: null,
        evidence: [],
        concerning_factor: {
          kind: 'ATTENDANCE',
          description: 'Sinal isolado: queda de frequência no 3º Bimestre',
        },
        observations: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const toggle = await screen.findByRole('button', { name: 'Fator preocupante' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Sinal isolado: queda de frequência no 3º Bimestre')).not.toBeInTheDocument()

    fireEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Sinal isolado: queda de frequência no 3º Bimestre')).toBeInTheDocument()
  })

  it('shows a factual not-found message with a link back to Home for an unknown student', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({ error: { code: 'student_not_found', message: 'Estudante não encontrado.' } }, 404),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage('unknown-student')

    await screen.findByText('Estudante não encontrado.')
    expect(screen.getByRole('link', { name: 'Voltar para a Home' })).toHaveAttribute('href', '/home')
  })

  it('shows a factual error message with retry on load failure', async () => {
    fetchMock = vi.fn(async () => jsonResponse({ error: { code: 'server_error', message: 'boom' } }, 500))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    await screen.findByText('Não foi possível carregar os dados agora.')
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
  })

  // --- "Abrir acompanhamento" button (Story 4.1, replaces Story 3.4's stub) ---------

  const DETAIL_WITH_CHANGE = {
    chart_indicator: 'attendance_rate',
    series: SERIES,
    habitual_range: { low: '0.5000', high: '0.9000' },
    trajectory_change: {
      id: 'change-1',
      type: 'ATTENDANCE_DROP',
      period_id: 'p2',
      detected_at: '2026-09-24T00:00:00Z',
      description: 'Queda de frequência no 3º Bimestre',
    },
    evidence: [
      { source_type: 'ATTENDANCE_RECORD', description: 'Falta não justificada em 20/09/2026', date: '2026-09-20' },
    ],
    concerning_factor: null,
    observations: [],
  }

  const DETAIL_CALM = {
    chart_indicator: 'attendance_rate',
    series: SERIES,
    habitual_range: { low: '0.5000', high: '0.9000' },
    trajectory_change: null,
    evidence: [],
    concerning_factor: null,
    observations: [],
  }

  it('enables "Abrir acompanhamento" when a change exists, and clicking it opens the follow-up then navigates', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('/trajectory/detail')) {
        return jsonResponse(DETAIL_WITH_CHANGE)
      }
      if (url.includes('/follow-ups') && init?.method === 'POST') {
        return jsonResponse(
          {
            id: 'follow-up-1',
            student_id: 'student-1',
            status: 'EM_OBSERVACAO',
            created_at: '2026-10-13T00:00:00Z',
          },
          201,
        )
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const button = await screen.findByRole('button', { name: 'Abrir acompanhamento' })
    expect(button).toBeEnabled()

    fireEvent.click(button)

    await screen.findByText('Acompanhamento mock')
    const postCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        (typeof input === 'string' ? input : input.toString()).includes('/follow-ups') &&
        init?.method === 'POST',
    )
    expect(postCall).toBeDefined()
    const body = JSON.parse((postCall![1] as RequestInit).body as string)
    expect(body).toEqual({ student_id: 'student-1', trajectory_change_id: 'change-1' })
  })

  it('shows an inline error and stays on the page when opening the follow-up fails', async () => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('/trajectory/detail')) {
        return jsonResponse(DETAIL_WITH_CHANGE)
      }
      if (url.includes('/follow-ups') && init?.method === 'POST') {
        return jsonResponse(
          { error: { code: 'trajectory_change_not_found', message: 'Mudança de trajetória não encontrada.' } },
          404,
        )
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const button = await screen.findByRole('button', { name: 'Abrir acompanhamento' })
    fireEvent.click(button)

    await screen.findByText('Não foi possível abrir o acompanhamento agora.')
    expect(screen.getByText('Trajetória do estudante')).toBeInTheDocument()
  })

  it('keeps "Abrir acompanhamento" disabled in the calm state (no detected change)', async () => {
    fetchMock = vi.fn(async () => jsonResponse(DETAIL_CALM))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const button = await screen.findByRole('button', { name: 'Abrir acompanhamento' })
    expect(button).toBeDisabled()
  })

  // --- spec-ui-1: student name + open follow-up -------------------------------------

  it('titles the page with the student name and classroom when the API sends them', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        ...DETAIL_CALM,
        student: { id: 'student-1', name: 'Ana Beatriz Souza', classroom_name: 'Turma Aurora' },
        open_follow_up_id: null,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    expect(await screen.findByRole('heading', { level: 1, name: 'Ana Beatriz Souza' })).toBeInTheDocument()
    expect(screen.getByText('Turma Aurora')).toBeInTheDocument()
  })

  it('links to the open follow-up instead of offering to open a duplicate', async () => {
    fetchMock = vi.fn(async () =>
      jsonResponse({
        ...DETAIL_WITH_CHANGE,
        student: { id: 'student-1', name: 'Ana Beatriz Souza', classroom_name: 'Turma Aurora' },
        open_follow_up_id: 'follow-up-1',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const link = await screen.findByRole('link', { name: 'Ver acompanhamento' })
    expect(link).toHaveAttribute('href', '/acompanhamentos/follow-up-1')
    expect(screen.queryByRole('button', { name: 'Abrir acompanhamento' })).not.toBeInTheDocument()
  })
})
