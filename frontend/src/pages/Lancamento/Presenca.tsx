import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  ApiError,
  listClassrooms,
  listEnrolledStudents,
  registerAttendance,
  type AttendanceCreateRequest,
  type Classroom,
  type Student,
} from '../../api/client'
import { Header } from '../../components/Header'

type AttendanceStatusValue = AttendanceCreateRequest['status']

const STATUS_OPTIONS: { value: AttendanceStatusValue; label: string }[] = [
  { value: 'PRESENT', label: 'Presente' },
  { value: 'ABSENT_JUSTIFIED', label: 'Falta justificada' },
  { value: 'ABSENT_UNJUSTIFIED', label: 'Falta não justificada' },
]

function todayIsoDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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
  status: AttendanceStatusValue
  saving: boolean
  message: string | null
  isError: boolean
}

/**
 * "Lançamento" attendance surface (Story 1.2). Per-student save — not one
 * bulk submit — so the coordenação can "lançar o próximo estudante sem
 * interrupção" (spec Design Notes): each row's `<select>` + `<button>`
 * posts independently, and confirmation/duplicate messaging is scoped to
 * that row, never a global modal.
 */
export function Presenca() {
  const { token } = useAuth()
  const classroomSelectId = useId()
  const dateInputId = useId()

  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [classroomsError, setClassroomsError] = useState<string | null>(null)
  const [selectedClassroomId, setSelectedClassroomId] = useState('')
  const [date, setDate] = useState(todayIsoDate())

  const [students, setStudents] = useState<Student[]>([])
  const [studentsError, setStudentsError] = useState<string | null>(null)
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})

  const selectedClassroomIdRef = useRef(selectedClassroomId)
  selectedClassroomIdRef.current = selectedClassroomId

  useEffect(() => {
    if (!token) return
    listClassrooms(token)
      .then(setClassrooms)
      .catch(() => setClassroomsError('Não foi possível carregar as turmas agora.'))
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
              { status: 'PRESENT', saving: false, message: null, isError: false } as RowState,
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
  }, [token, selectedClassroomId, date])

  function updateRow(studentId: string, patch: Partial<RowState>) {
    setRowStates((prev) => ({ ...prev, [studentId]: { ...prev[studentId], ...patch } }))
  }

  async function handleSave(studentId: string) {
    if (!token || !selectedClassroomId) return
    const row = rowStates[studentId]
    if (!row) return

    const classroomIdAtSaveStart = selectedClassroomId
    updateRow(studentId, { saving: true, message: null, isError: false })
    try {
      await registerAttendance(token, {
        student_id: studentId,
        classroom_id: selectedClassroomId,
        date,
        status: row.status,
      })
      if (selectedClassroomIdRef.current !== classroomIdAtSaveStart) return
      updateRow(studentId, { saving: false, message: 'Registro salvo.', isError: false })
    } catch (caught) {
      if (selectedClassroomIdRef.current !== classroomIdAtSaveStart) return
      const message =
        caught instanceof ApiError ? caught.message : 'Não foi possível salvar o registro agora.'
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
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Lançamento de presença</h1>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Selecione a turma e a data para registrar a presença de cada estudante.
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
              <AttendanceRow
                key={student.id}
                student={student}
                rowState={rowStates[student.id]}
                onStatusChange={(status) =>
                  updateRow(student.id, { status, message: null, isError: false })
                }
                onSave={() => handleSave(student.id)}
              />
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}

function AttendanceRow({
  student,
  rowState,
  onStatusChange,
  onSave,
}: {
  student: Student
  rowState: RowState | undefined
  onStatusChange: (status: AttendanceStatusValue) => void
  onSave: () => void
}) {
  const statusId = useId()
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
        <label htmlFor={statusId} style={{ fontSize: 13, fontWeight: 600 }}>
          Status
        </label>
        <select
          id={statusId}
          value={rowState.status}
          onChange={(event) => onStatusChange(event.target.value as AttendanceStatusValue)}
          aria-describedby={rowState.message ? messageId : undefined}
          style={{ ...fieldStyle, minWidth: 200 }}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={onSave}
        disabled={rowState.saving}
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
          cursor: rowState.saving ? 'not-allowed' : 'pointer',
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
