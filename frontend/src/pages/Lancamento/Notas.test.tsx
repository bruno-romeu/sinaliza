import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { Notas } from './Notas'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderNotas() {
  return render(
    <MemoryRouter initialEntries={['/lancamento/notas']}>
      <AuthProvider>
        <Notas />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Notas — client-side out-of-range validation (spec I/O Matrix "Out-of-range value (client)")', () => {
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
      if (url === '/api/academic-periods') {
        return jsonResponse([
          {
            id: 'period-1',
            label: '3º Bimestre',
            start_date: '2026-07-27',
            end_date: '2026-09-25',
            order_index: 3,
          },
        ])
      }
      if (url === '/api/classrooms/classroom-1/students') {
        return jsonResponse([{ id: 'student-1', name: 'Estudante Teste' }])
      }
      if (url === '/api/grades' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(
          {
            id: 'grade-1',
            student_id: body.student_id,
            classroom_id: body.classroom_id,
            subject: body.subject,
            period_id: body.period_id,
            date: body.date,
            value: body.value,
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

  it('blocks save client-side for a valor outside 0–10, shows the aria-describedby message, and never calls POST /grades', async () => {
    renderNotas()

    // Wait for the shared-context selects to be populated from the mocked
    // GETs, then fill turma/disciplina/período so the row's Save button is
    // enabled (`canSave`).
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await screen.findByText('Estudante Teste')

    fireEvent.change(screen.getByLabelText('Disciplina'), { target: { value: 'Matemática' } })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: '3º Bimestre' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Período letivo'), { target: { value: 'period-1' } })

    const valorInput = screen.getByLabelText('Valor')
    fireEvent.change(valorInput, { target: { value: '15' } })

    const saveButton = screen.getByRole('button', { name: 'Salvar' })
    expect(saveButton).not.toBeDisabled()
    fireEvent.click(saveButton)

    const expectedMessage = 'O valor deve estar entre 0 e 10.'
    const messageElement = await screen.findByText(expectedMessage)

    // Field-adjacent message wired via `aria-describedby`, not only visual
    // proximity (spec Boundaries & Constraints, UX-DR23).
    const describedById = valorInput.getAttribute('aria-describedby')
    expect(describedById).toBeTruthy()
    expect(messageElement.id).toBe(describedById)

    // No `POST /grades` request was ever made — save was blocked entirely
    // client-side before any network call (spec I/O Matrix).
    const gradesCalls = fetchMock.mock.calls.filter(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url.includes('/grades')
    })
    expect(gradesCalls).toHaveLength(0)
  })

  it('saves a valid valor: POSTs /grades with the selected context and shows "Registro salvo."', async () => {
    renderNotas()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await screen.findByText('Estudante Teste')

    fireEvent.change(screen.getByLabelText('Disciplina'), { target: { value: 'Matemática' } })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: '3º Bimestre' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Período letivo'), { target: { value: 'period-1' } })
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-09-24' } })

    const valorInput = screen.getByLabelText('Valor')
    fireEvent.change(valorInput, { target: { value: '8.5' } })

    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await screen.findByText('Registro salvo.')

    const gradesCall = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/grades'
    })
    expect(gradesCall).toBeDefined()
    const [, init] = gradesCall as [RequestInfo | URL, RequestInit]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      student_id: 'student-1',
      classroom_id: 'classroom-1',
      subject: 'Matemática',
      period_id: 'period-1',
      date: '2026-09-24',
      value: '8.5',
    })
  })
})
