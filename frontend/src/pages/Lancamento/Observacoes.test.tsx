import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { Observacoes } from './Observacoes'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderObservacoes() {
  return render(
    <MemoryRouter initialEntries={['/lancamento/observacoes']}>
      <AuthProvider>
        <Observacoes />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Observacoes — Lançamento de observações (Story 1.5)', () => {
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

    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url === '/api/classrooms') {
        return jsonResponse([{ id: 'classroom-1', name: 'Turma Teste', academic_year: 2026 }])
      }
      if (url === '/api/classrooms/classroom-1/students') {
        return jsonResponse([{ id: 'student-1', name: 'Estudante Teste' }])
      }
      if (url === '/api/pedagogical-observations' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(
          {
            id: 'observation-1',
            student_id: body.student_id,
            author_user_id: 'u1',
            text: body.text,
            created_at: '2026-09-24T12:00:00Z',
          },
          201,
        )
      }
      throw new Error(`Unexpected fetch call in test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps the save button disabled while the observation textarea is empty (UX-DR13)', async () => {
    renderObservacoes()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await screen.findByText('Estudante Teste')

    fireEvent.click(screen.getByRole('button', { name: 'Escrever observação' }))
    const saveButton = screen.getByRole('button', { name: 'Salvar observação' })
    expect(saveButton).toBeDisabled()

    const observacaoTextarea = screen.getByLabelText(/Observação sobre/)
    fireEvent.change(observacaoTextarea, { target: { value: '   ' } })
    expect(saveButton).toBeDisabled()

    fireEvent.change(observacaoTextarea, { target: { value: 'Participou bem da aula.' } })
    expect(saveButton).not.toBeDisabled()

    // No request sent while blank/whitespace-only (spec I/O Matrix, "Blank
    // text (UI gate)").
    const observationCalls = fetchMock.mock.calls.filter(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url.includes('/pedagogical-observations')
    })
    expect(observationCalls).toHaveLength(0)
  })

  it('saves an observation: POSTs /pedagogical-observations with the exact payload and shows "Registro salvo." inline, no modal', async () => {
    renderObservacoes()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await screen.findByText('Estudante Teste')

    fireEvent.click(screen.getByRole('button', { name: 'Escrever observação' }))
    fireEvent.change(screen.getByLabelText(/Observação sobre/), {
      target: { value: 'Participou ativamente da aula e ajudou colegas.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Salvar observação' }))

    await screen.findByText('Registro salvo.')

    // No modal/dialog rendered for the confirmation (UX-DR18).
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const observationCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/pedagogical-observations'
    })
    expect(observationCall).toBeDefined()
    const [, init] = observationCall as [RequestInfo | URL, RequestInit]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      student_id: 'student-1',
      classroom_id: 'classroom-1',
      text: 'Participou ativamente da aula e ajudou colegas.',
      registers_concern: false,
    })
  })

  it('sends registers_concern when "Registra uma preocupação" is checked (spec-ui-3)', async () => {
    renderObservacoes()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })
    await screen.findByText('Estudante Teste')

    fireEvent.click(screen.getByRole('button', { name: 'Escrever observação' }))
    fireEvent.change(screen.getByLabelText(/Observação sobre/), {
      target: { value: 'Faltou às duas últimas avaliações.' },
    })
    const concern = screen.getByRole('checkbox', { name: /Registra uma preocupação/ })
    expect(concern).not.toBeChecked()
    fireEvent.click(concern)
    fireEvent.click(screen.getByRole('button', { name: 'Salvar observação' }))

    await screen.findByText('Registro salvo.')
    const observationCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/pedagogical-observations'
    })
    const [, init] = observationCall as [RequestInfo | URL, RequestInit]
    expect(JSON.parse(String(init?.body))).toMatchObject({ registers_concern: true })
  })
})
