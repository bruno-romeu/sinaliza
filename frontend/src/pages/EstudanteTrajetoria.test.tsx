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
          type: 'ATTENDANCE_DROP',
          period_id: 'p2',
          detected_at: '2026-09-24T00:00:00Z',
          description: 'Mudança recente: queda de frequência — 3º Bimestre',
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
          description: 'Mudança recente: queda de frequência — 3º Bimestre',
        },
        observations: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const toggle = await screen.findByRole('button', { name: 'Fator preocupante' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Mudança recente: queda de frequência — 3º Bimestre')).not.toBeInTheDocument()

    fireEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Mudança recente: queda de frequência — 3º Bimestre')).toBeInTheDocument()
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
})
