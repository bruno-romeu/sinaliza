import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  ApiError,
  listClassrooms,
  listEnrolledStudents,
  registerPedagogicalObservation,
  type Classroom,
  type Student,
} from '../../api/client'
import { Header } from '../../components/Header'

const fieldStyle: CSSProperties = {
  padding: '0 12px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  fontSize: 15,
}

const selectStyle: CSSProperties = {
  ...fieldStyle,
  minHeight: 'var(--min-hit-target)',
}

interface RowState {
  text: string
  saving: boolean
  message: string | null
  isError: boolean
}

/**
 * "Lançamento de observações" surface (Story 1.5). Turma is the shared
 * "lançamento session" context (mirrors `Presenca.tsx`/`Notas.tsx`); each
 * student's free-text observation is its own row, saved independently so
 * the coordenação can move to the next student without interruption. No
 * date/status field — `PedagogicalObservation`'s only per-row input is the
 * text itself (spec Code Map). No read-back of past observations here
 * (append-only "histórico", never displayed in this story — spec
 * Boundaries & Constraints).
 */
export function Observacoes() {
  const { token } = useAuth()
  const classroomSelectId = useId()

  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [classroomsError, setClassroomsError] = useState<string | null>(null)
  const [selectedClassroomId, setSelectedClassroomId] = useState('')

  const [students, setStudents] = useState<Student[]>([])
  const [studentsError, setStudentsError] = useState<string | null>(null)
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})

  // Captured at the start of each row's save and re-checked once the
  // response resolves — if the selected turma changed mid-flight, the stale
  // response is discarded (mirrors `Presenca.tsx`'s guard).
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
              { text: '', saving: false, message: null, isError: false } as RowState,
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

  function updateRow(studentId: string, patch: Partial<RowState>) {
    setRowStates((prev) => ({ ...prev, [studentId]: { ...prev[studentId], ...patch } }))
  }

  async function handleSave(studentId: string) {
    if (!token || !selectedClassroomId) return
    const row = rowStates[studentId]
    if (!row || row.text.trim() === '') return

    const classroomIdAtSaveStart = selectedClassroomId
    const textAtSaveStart = row.text

    updateRow(studentId, { saving: true, message: null, isError: false })
    try {
      await registerPedagogicalObservation(token, {
        student_id: studentId,
        classroom_id: classroomIdAtSaveStart,
        text: textAtSaveStart,
      })
      if (selectedClassroomIdRef.current !== classroomIdAtSaveStart) return
      updateRow(studentId, { text: '', saving: false, message: 'Registro salvo.', isError: false })
    } catch (caught) {
      if (selectedClassroomIdRef.current !== classroomIdAtSaveStart) return
      const message =
        caught instanceof ApiError ? caught.message : 'Não foi possível salvar a observação agora.'
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
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>
            Lançamento de observações
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Selecione a turma e registre uma observação pedagógica em texto livre para cada
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
              style={selectStyle}
            >
              <option value="">Selecione…</option>
              {classrooms.map((classroom) => (
                <option key={classroom.id} value={classroom.id}>
                  {classroom.name}
                </option>
              ))}
            </select>
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
              <ObservacaoRow
                key={student.id}
                student={student}
                rowState={rowStates[student.id]}
                onTextChange={(text) =>
                  updateRow(student.id, { text, message: null, isError: false })
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

function ObservacaoRow({
  student,
  rowState,
  onTextChange,
  onSave,
}: {
  student: Student
  rowState: RowState | undefined
  onTextChange: (text: string) => void
  onSave: () => void
}) {
  const textId = useId()
  const messageId = useId()

  if (!rowState) return null

  const canSave = rowState.text.trim() !== ''

  return (
    <li
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '16px 20px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <span style={{ fontWeight: 600 }}>{student.name}</span>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label htmlFor={textId} style={{ fontSize: 13, fontWeight: 600 }}>
          Observação
        </label>
        <textarea
          id={textId}
          value={rowState.text}
          onChange={(event) => onTextChange(event.target.value)}
          aria-describedby={rowState.message ? messageId : undefined}
          rows={3}
          style={{ ...fieldStyle, padding: '8px 12px', resize: 'vertical', fontFamily: 'inherit' }}
        />
      </div>

      <div>
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
      </div>

      <div
        id={messageId}
        role={rowState.isError ? 'alert' : 'status'}
        aria-live="polite"
        style={{
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
