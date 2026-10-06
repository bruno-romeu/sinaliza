import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  ApiError,
  listAcademicPeriods,
  listClassrooms,
  listEnrolledStudents,
  registerGrade,
  type AcademicPeriod,
  type Classroom,
  type Student,
} from '../../api/client'
import { Header } from '../../components/Header'

function todayIsoDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Client-side mirror of the backend's `Field(ge=0, le=10)` bound (spec
 * I/O Matrix, "Out-of-range value (client)") — blocks the request entirely
 * before any network call, distinct from the server-side 422 that still
 * applies if this is ever bypassed. */
function validateValue(raw: string): string | null {
  if (raw.trim() === '') {
    return 'Informe um valor entre 0 e 10.'
  }
  const parsed = Number(raw)
  if (Number.isNaN(parsed)) {
    return 'Valor inválido.'
  }
  const decimalPart = raw.trim().split('.')[1]
  if (decimalPart && decimalPart.length > 2) {
    return 'Informe no máximo 2 casas decimais.'
  }
  if (parsed < 0 || parsed > 10) {
    return 'O valor deve estar entre 0 e 10.'
  }
  return null
}

const fieldStyle: CSSProperties = {
  minHeight: 'var(--min-hit-target)',
  padding: '0 12px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  fontSize: 15,
}

interface RowState {
  value: string
  saving: boolean
  message: string | null
  isError: boolean
}

/**
 * "Lançamento de notas" surface (Story 1.3). Turma/disciplina/período/data
 * are shared "lançamento session" context (spec Design Notes) — `valor` is
 * the only per-row field, saved independently per student so the
 * coordenação can move to the next student without interruption (mirrors
 * `Presenca.tsx`).
 */
export function Notas() {
  const { token } = useAuth()
  const classroomSelectId = useId()
  const subjectInputId = useId()
  const periodSelectId = useId()
  const dateInputId = useId()

  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [classroomsError, setClassroomsError] = useState<string | null>(null)
  const [selectedClassroomId, setSelectedClassroomId] = useState('')

  const [periods, setPeriods] = useState<AcademicPeriod[]>([])
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [selectedPeriodId, setSelectedPeriodId] = useState('')

  const [subject, setSubject] = useState('')
  const [date, setDate] = useState(todayIsoDate())

  const [students, setStudents] = useState<Student[]>([])
  const [studentsError, setStudentsError] = useState<string | null>(null)
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})

  // Captured at the start of each row's save and re-checked once the
  // response resolves — if any of the shared "lançamento session" fields
  // changed mid-flight, the stale response is discarded (mirrors
  // `Presenca.tsx`'s single-field version of this guard).
  const selectedClassroomIdRef = useRef(selectedClassroomId)
  selectedClassroomIdRef.current = selectedClassroomId
  const selectedPeriodIdRef = useRef(selectedPeriodId)
  selectedPeriodIdRef.current = selectedPeriodId
  const subjectRef = useRef(subject)
  subjectRef.current = subject
  const dateRef = useRef(date)
  dateRef.current = date

  useEffect(() => {
    if (!token) return
    listClassrooms(token)
      .then(setClassrooms)
      .catch(() => setClassroomsError('Não foi possível carregar as turmas agora.'))
    listAcademicPeriods(token)
      .then(setPeriods)
      .catch(() => setPeriodsError('Não foi possível carregar os períodos letivos agora.'))
  }, [token])

  useEffect(() => {
    if (!token || !selectedClassroomId) {
      setStudents([])
      setRowStates({})
      return
    }
    let ignore = false
    setStudentsLoading(true)
    setStudentsError(null)
    listEnrolledStudents(token, selectedClassroomId)
      .then((fetched) => {
        if (ignore) return
        setStudents(fetched)
        setRowStates(
          Object.fromEntries(
            fetched.map((student) => [
              student.id,
              { value: '', saving: false, message: null, isError: false } as RowState,
            ]),
          ),
        )
      })
      .catch(() => {
        if (ignore) return
        setStudentsError('Não foi possível carregar os estudantes agora.')
      })
      .finally(() => {
        if (ignore) return
        setStudentsLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [token, selectedClassroomId])

  useEffect(() => {
    setRowStates((prev) => {
      const next: Record<string, RowState> = {}
      for (const studentId of Object.keys(prev)) {
        next[studentId] = { value: '', saving: false, message: null, isError: false }
      }
      return next
    })
  }, [selectedPeriodId, subject, date])

  function updateRow(studentId: string, patch: Partial<RowState>) {
    setRowStates((prev) => ({ ...prev, [studentId]: { ...prev[studentId], ...patch } }))
  }

  const canSave = Boolean(selectedClassroomId && selectedPeriodId && subject.trim() && date)

  async function handleSave(studentId: string) {
    if (!token || !selectedClassroomId || !selectedPeriodId || !subject.trim() || !date) return
    const row = rowStates[studentId]
    if (!row) return

    const validationError = validateValue(row.value)
    if (validationError) {
      updateRow(studentId, { message: validationError, isError: true })
      return
    }

    const classroomIdAtSaveStart = selectedClassroomId
    const periodIdAtSaveStart = selectedPeriodId
    const subjectAtSaveStart = subject
    const dateAtSaveStart = date
    const sharedContextChanged = () =>
      selectedClassroomIdRef.current !== classroomIdAtSaveStart ||
      selectedPeriodIdRef.current !== periodIdAtSaveStart ||
      subjectRef.current !== subjectAtSaveStart ||
      dateRef.current !== dateAtSaveStart

    updateRow(studentId, { saving: true, message: null, isError: false })
    try {
      await registerGrade(token, {
        student_id: studentId,
        classroom_id: classroomIdAtSaveStart,
        subject: subjectAtSaveStart.trim(),
        period_id: periodIdAtSaveStart,
        date: dateAtSaveStart,
        value: row.value.trim(),
      })
      if (sharedContextChanged()) return
      updateRow(studentId, { saving: false, message: 'Registro salvo.', isError: false })
    } catch (caught) {
      if (sharedContextChanged()) return
      const message =
        caught instanceof ApiError ? caught.message : 'Não foi possível salvar a nota agora.'
      updateRow(studentId, { saving: false, message, isError: true })
    }
  }

  return (
    <div>
      <Header />
      <main
        style={{
          maxWidth: 'var(--spacing-content-max-width)',
          margin: '0 auto',
          padding: 'var(--spacing-section-gap) 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 32,
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Lançamento de notas</h1>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Selecione a turma, disciplina, período letivo e data para registrar a nota de cada
            estudante.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220 }}>
            <label htmlFor={classroomSelectId} style={{ fontWeight: 600 }}>
              Turma
            </label>
            <select
              id={classroomSelectId}
              value={selectedClassroomId}
              onChange={(event) => setSelectedClassroomId(event.target.value)}
              style={fieldStyle}
            >
              <option value="">Selecione…</option>
              {classrooms.map((classroom) => (
                <option key={classroom.id} value={classroom.id}>
                  {classroom.name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 200 }}>
            <label htmlFor={subjectInputId} style={{ fontWeight: 600 }}>
              Disciplina
            </label>
            <input
              id={subjectInputId}
              type="text"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Ex.: Matemática"
              maxLength={255}
              style={fieldStyle}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220 }}>
            <label htmlFor={periodSelectId} style={{ fontWeight: 600 }}>
              Período letivo
            </label>
            <select
              id={periodSelectId}
              value={selectedPeriodId}
              onChange={(event) => setSelectedPeriodId(event.target.value)}
              style={fieldStyle}
            >
              <option value="">Selecione…</option>
              {periods.map((period) => (
                <option key={period.id} value={period.id}>
                  {period.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 180 }}>
            <label htmlFor={dateInputId} style={{ fontWeight: 600 }}>
              Data
            </label>
            <input
              id={dateInputId}
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              style={fieldStyle}
            />
          </div>
        </div>

        {classroomsError && (
          <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
            {classroomsError}
          </p>
        )}

        {periodsError && (
          <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
            {periodsError}
          </p>
        )}

        {selectedClassroomId && studentsLoading && (
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>Carregando estudantes…</p>
        )}

        {selectedClassroomId && studentsError && (
          <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
            {studentsError}
          </p>
        )}

        {selectedClassroomId && !studentsLoading && !studentsError && students.length === 0 && (
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Nenhum estudante matriculado nesta turma.
          </p>
        )}

        {students.length > 0 && !canSave && (
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Selecione disciplina, período letivo e data para lançar notas.
          </p>
        )}

        {students.length > 0 && (
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            {students.map((student) => (
              <NotaRow
                key={student.id}
                student={student}
                rowState={rowStates[student.id]}
                canSave={canSave}
                onValueChange={(value) => updateRow(student.id, { value, message: null, isError: false })}
                onSave={() => handleSave(student.id)}
              />
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}

function NotaRow({
  student,
  rowState,
  canSave,
  onValueChange,
  onSave,
}: {
  student: Student
  rowState: RowState | undefined
  canSave: boolean
  onValueChange: (value: string) => void
  onSave: () => void
}) {
  const valueId = useId()
  const messageId = useId()

  if (!rowState) return null

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 16,
        padding: '16px 20px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <span style={{ flex: '1 1 200px', fontWeight: 600 }}>{student.name}</span>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label htmlFor={valueId} style={{ fontSize: 13, fontWeight: 600 }}>
          Valor
        </label>
        <input
          id={valueId}
          type="number"
          min={0}
          max={10}
          step={0.01}
          value={rowState.value}
          onChange={(event) => onValueChange(event.target.value)}
          aria-invalid={rowState.isError || undefined}
          aria-describedby={rowState.message ? messageId : undefined}
          style={{ ...fieldStyle, minWidth: 100 }}
        />
      </div>

      <button
        type="button"
        onClick={onSave}
        disabled={rowState.saving || !canSave}
        style={{
          minHeight: 'var(--min-hit-target)',
          minWidth: 'var(--min-hit-target)',
          padding: '0 16px',
          borderRadius: 'var(--radius-md)',
          border: 'none',
          background: 'var(--color-primary)',
          color: 'var(--color-surface)',
          fontSize: 15,
          fontWeight: 600,
          cursor: rowState.saving || !canSave ? 'not-allowed' : 'pointer',
        }}
      >
        {rowState.saving ? 'Salvando…' : 'Salvar'}
      </button>

      <div
        id={messageId}
        role={rowState.isError ? 'alert' : 'status'}
        aria-live="polite"
        style={{
          flexBasis: '100%',
          minHeight: 20,
          fontSize: 14,
          color: rowState.isError ? 'var(--color-attention)' : 'var(--color-success)',
        }}
      >
        {rowState.message}
      </div>
    </li>
  )
}
