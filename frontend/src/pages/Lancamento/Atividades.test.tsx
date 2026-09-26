import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../../auth/AuthContext'
import { Atividades } from './Atividades'

const STORAGE_KEY = 'sinaliza.session'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderAtividades() {
  return render(
    <MemoryRouter initialEntries={['/lancamento/atividades']}>
      <AuthProvider>
        <Atividades />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Atividades — cadastro de atividade e registro de status de entrega (Story 1.4)', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let assignmentsListCallCount: number

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token: 'fake-token',
        user: { id: 'u1', name: 'Test User', email: 'test@example.com', role: 'COORDENACAO_PEDAGOGICA' },
      }),
    )

    assignmentsListCallCount = 0

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
      if (url === '/api/classrooms/classroom-1/assignments' && init?.method !== 'POST') {
        assignmentsListCallCount += 1
        if (assignmentsListCallCount === 1) {
          return jsonResponse([])
        }
        return jsonResponse([
          {
            id: 'assignment-1',
            classroom_id: 'classroom-1',
            subject: 'Matemática',
            period_id: 'period-1',
            due_date: '2026-09-30',
          },
        ])
      }
      if (url === '/api/assignments' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(
          {
            id: 'assignment-1',
            classroom_id: body.classroom_id,
            subject: body.subject,
            period_id: body.period_id,
            due_date: body.due_date,
          },
          201,
        )
      }
      if (url === '/api/assignment-submissions' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(
          {
            id: 'submission-1',
            assignment_id: body.assignment_id,
            student_id: body.student_id,
            status: body.status,
            date: body.date,
          },
          201,
        )
      }
      throw new Error(`Unexpected fetch call in test: ${url} ${init?.method ?? 'GET'}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('cadastra uma atividade: POSTs /assignments with the form fields and shows "Atividade cadastrada."', async () => {
    renderAtividades()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await waitFor(() => {
      expect(screen.getByLabelText('Disciplina')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Disciplina'), { target: { value: 'Matemática' } })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: '3º Bimestre' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Período letivo'), { target: { value: 'period-1' } })
    fireEvent.change(screen.getByLabelText('Data de entrega'), { target: { value: '2026-09-30' } })

    const submitButton = screen.getByRole('button', { name: 'Cadastrar atividade' })
    expect(submitButton).not.toBeDisabled()
    fireEvent.click(submitButton)

    await screen.findByText('Atividade cadastrada.')

    const assignmentsCall = fetchMock.mock.calls.find(([input, init]) => {
      const url = typeof input === 'string' ? input : String(input)
      return url === '/api/assignments' && (init as RequestInit | undefined)?.method === 'POST'
    })
    expect(assignmentsCall).toBeDefined()
    const [, init] = assignmentsCall as [RequestInfo | URL, RequestInit]
    expect(JSON.parse(String(init?.body))).toEqual({
      classroom_id: 'classroom-1',
      subject: 'Matemática',
      period_id: 'period-1',
      due_date: '2026-09-30',
    })

    // The newly cadastrada atividade appears in the atividade selector.
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Matemática — 2026-09-30' })).toBeInTheDocument()
    })
  })

  it('registra o status de entrega de um estudante: POSTs /assignment-submissions and shows "Registro salvo." on that row', async () => {
    // Start with an atividade already cadastrada for the turma so the second
    // step is reachable directly.
    assignmentsListCallCount = 1

    renderAtividades()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Turma Teste' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Turma'), { target: { value: 'classroom-1' } })

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Matemática — 2026-09-30' })).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Atividade'), { target: { value: 'assignment-1' } })
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-09-30' } })

    await screen.findByText('Estudante Teste')

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'PARTIAL' } })

    const saveButton = screen.getByRole('button', { name: 'Salvar' })
    expect(saveButton).not.toBeDisabled()
    fireEvent.click(saveButton)

    await screen.findByText('Registro salvo.')

    const submissionCall = fetchMock.mock.calls.find(([input, init]) => {
      const url = typeof input === 'string' ? input : String(input)
      return (
        url === '/api/assignment-submissions' && (init as RequestInit | undefined)?.method === 'POST'
      )
    })
    expect(submissionCall).toBeDefined()
    const [, init] = submissionCall as [RequestInfo | URL, RequestInit]
    expect(JSON.parse(String(init?.body))).toEqual({
      assignment_id: 'assignment-1',
      student_id: 'student-1',
      status: 'PARTIAL',
      date: '2026-09-30',
    })
  })
})
