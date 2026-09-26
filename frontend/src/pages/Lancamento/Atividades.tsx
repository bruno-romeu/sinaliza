import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  ApiError,
  listAcademicPeriods,
  listAssignmentsByClassroom,
  listClassrooms,
  listEnrolledStudents,
  registerAssignment,
  registerAssignmentSubmission,
  type AcademicPeriod,
  type Assignment,
  type AssignmentSubmissionCreateRequest,
  type Classroom,
  type Student,
} from '../../api/client'
import { Header } from '../../components/Header'

type SubmissionStatusValue = AssignmentSubmissionCreateRequest['status']

const STATUS_OPTIONS: { value: SubmissionStatusValue; label: string }[] = [
  { value: 'DELIVERED', label: 'Entregue' },
  { value: 'NOT_DELIVERED', label: 'Não entregue' },
  { value: 'PARTIAL', label: 'Parcial' },
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
  status: SubmissionStatusValue
  saving: boolean
  message: string | null
  isError: boolean
}

/**
 * "Lançamento de atividades" surface (Story 1.4). One turma context shared
 * across two linked steps (spec Design Notes): (1) a "Cadastrar atividade"
 * sub-form that creates an `Assignment` for the selected turma; (2) once at
 * least one atividade exists, selecting it (plus a data) exposes one row per
 * matriculated student to register that student's delivery `status` — saved
 * independently per row, mirroring `Presenca.tsx`'s "lançar o próximo
 * estudante sem interrupção".
 */
export function Atividades() {
  const { token } = useAuth()
  const classroomSelectId = useId()
  const subjectInputId = useId()
  const periodSelectId = useId()
  const dueDateInputId = useId()
  const assignmentSelectId = useId()
  const submissionDateInputId = useId()

  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [classroomsError, setClassroomsError] = useState<string | null>(null)
  const [selectedClassroomId, setSelectedClassroomId] = useState('')

  const [periods, setPeriods] = useState<AcademicPeriod[]>([])
  const [periodsError, setPeriodsError] = useState<string | null>(null)

  // --- Step 1: cadastro da atividade -----------------------------------
  const [subject, setSubject] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [dueDate, setDueDate] = useState(todayIsoDate())
  const [creatingAssignment, setCreatingAssignment] = useState(false)
  const [assignmentMessage, setAssignmentMessage] = useState<string | null>(null)
  const [assignmentMessageIsError, setAssignmentMessageIsError] = useState(false)

  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [assignmentsError, setAssignmentsError] = useState<string | null>(null)

  // --- Step 2: status de entrega ----------------------------------------
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('')
  const [submissionDate, setSubmissionDate] = useState(todayIsoDate())

  const [students, setStudents] = useState<Student[]>([])
  const [studentsError, setStudentsError] = useState<string | null>(null)
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})

  const selectedClassroomIdRef = useRef(selectedClassroomId)
  selectedClassroomIdRef.current = selectedClassroomId
  const selectedAssignmentIdRef = useRef(selectedAssignmentId)
  selectedAssignmentIdRef.current = selectedAssignmentId
  const submissionDateRef = useRef(submissionDate)
  submissionDateRef.current = submissionDate

  useEffect(() => {
    if (!token) return
    listClassrooms(token)
      .then(setClassrooms)
      .catch(() => setClassroomsError('Não foi possível carregar as turmas agora.'))
    listAcademicPeriods(token)
      .then(setPeriods)
      .catch(() => setPeriodsError('Não foi possível carregar os períodos letivos agora.'))
  }, [token])

  function refreshAssignments(classroomId: string) {
    if (!token) return
    setAssignmentsError(null)
    listAssignmentsByClassroom(token, classroomId)
      .then((fetched) => {
        // Stale-response guard: discard if the turma changed while this
        // request was in flight (mirrors the ref-guard pattern used
        // elsewhere in this file).
        if (classroomId !== selectedClassroomIdRef.current) return
        setAssignments(fetched)
      })
      .catch(() => {
        if (classroomId !== selectedClassroomIdRef.current) return
        setAssignmentsError('Não foi possível carregar as atividades agora.')
      })
  }

  useEffect(() => {
    setSelectedAssignmentId('')
    setAssignments([])
    setAssignmentMessage(null)
    setAssignmentMessageIsError(false)
    if (!token || !selectedClassroomId) return
    refreshAssignments(selectedClassroomId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedClassroomId])

  useEffect(() => {
    if (!token || !selectedAssignmentId || !submissionDate) {
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
              { status: 'DELIVERED', saving: false, message: null, isError: false } as RowState,
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
  }, [token, selectedClassroomId, selectedAssignmentId, submissionDate])

  function updateRow(studentId: string, patch: Partial<RowState>) {
    setRowStates((prev) => ({ ...prev, [studentId]: { ...prev[studentId], ...patch } }))
  }

  const canCreateAssignment = Boolean(selectedClassroomId && subject.trim() && periodId && dueDate)

  async function handleCreateAssignment() {
    if (!token || !canCreateAssignment) return
    const classroomIdAtStart = selectedClassroomId
    setCreatingAssignment(true)
    setAssignmentMessage(null)
    setAssignmentMessageIsError(false)
    try {
      await registerAssignment(token, {
        classroom_id: classroomIdAtStart,
        subject: subject.trim(),
        period_id: periodId,
        due_date: dueDate,
      })
      setCreatingAssignment(false)
      if (selectedClassroomIdRef.current !== classroomIdAtStart) return
      setAssignmentMessage('Atividade cadastrada.')
      setAssignmentMessageIsError(false)
      setSubject('')
      setPeriodId('')
      setDueDate(todayIsoDate())
      refreshAssignments(classroomIdAtStart)
    } catch (caught) {
      setCreatingAssignment(false)
      if (selectedClassroomIdRef.current !== classroomIdAtStart) return
      const message =
        caught instanceof ApiError ? caught.message : 'Não foi possível cadastrar a atividade agora.'
      setAssignmentMessage(message)
      setAssignmentMessageIsError(true)
    }
  }

  const canSaveSubmission = Boolean(selectedAssignmentId && submissionDate)

  async function handleSaveSubmission(studentId: string) {
    if (!token || !selectedAssignmentId || !submissionDate) return
    const row = rowStates[studentId]
    if (!row) return

    const assignmentIdAtStart = selectedAssignmentId
    const submissionDateAtStart = submissionDate
    const sharedContextChanged = () =>
      selectedAssignmentIdRef.current !== assignmentIdAtStart ||
      submissionDateRef.current !== submissionDateAtStart

    updateRow(studentId, { saving: true, message: null, isError: false })
    try {
      await registerAssignmentSubmission(token, {
        assignment_id: assignmentIdAtStart,
        student_id: studentId,
        status: row.status,
        date: submissionDateAtStart,
      })
      if (sharedContextChanged()) return
      updateRow(studentId, { saving: false, message: 'Registro salvo.', isError: false })
    } catch (caught) {
      if (sharedContextChanged()) return
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
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>
            Lançamento de atividades
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Selecione a turma para cadastrar uma atividade e registrar o status de entrega de cada
            estudante.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220, maxWidth: 320 }}>
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

        {selectedClassroomId && (
          <section
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
              padding: '16px 20px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Cadastrar atividade</h2>

            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
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
                  value={periodId}
                  onChange={(event) => setPeriodId(event.target.value)}
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
                <label htmlFor={dueDateInputId} style={{ fontWeight: 600 }}>
                  Data de entrega
                </label>
                <input
                  id={dueDateInputId}
                  type="date"
                  value={dueDate}
                  onChange={(event) => setDueDate(event.target.value)}
                  style={fieldStyle}
                />
              </div>
            </div>

            <div>
              <button
                type="button"
                onClick={handleCreateAssignment}
                disabled={creatingAssignment || !canCreateAssignment}
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
                  cursor: creatingAssignment || !canCreateAssignment ? 'not-allowed' : 'pointer',
                }}
              >
                {creatingAssignment ? 'Cadastrando…' : 'Cadastrar atividade'}
              </button>
            </div>

            {assignmentMessage && (
              <p
                role={assignmentMessageIsError ? 'alert' : 'status'}
                aria-live="polite"
                style={{
                  margin: 0,
                  fontSize: 14,
                  color: assignmentMessageIsError
                    ? 'var(--color-attention)'
                    : 'var(--color-success)',
                }}
              >
                {assignmentMessage}
              </p>
            )}

            {assignmentsError && (
              <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
                {assignmentsError}
              </p>
            )}
          </section>
        )}

        {selectedClassroomId && !assignmentsError && assignments.length === 0 && (
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Nenhuma atividade cadastrada nesta turma ainda. Cadastre uma atividade acima para
            registrar o status de entrega.
          </p>
        )}

        {selectedClassroomId && assignments.length > 0 && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Status de entrega</h2>

            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220 }}>
                <label htmlFor={assignmentSelectId} style={{ fontWeight: 600 }}>
                  Atividade
                </label>
                <select
                  id={assignmentSelectId}
                  value={selectedAssignmentId}
                  onChange={(event) => setSelectedAssignmentId(event.target.value)}
                  style={fieldStyle}
                >
                  <option value="">Selecione…</option>
                  {assignments.map((assignment) => (
                    <option key={assignment.id} value={assignment.id}>
                      {assignment.subject} — {assignment.due_date}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 180 }}>
                <label htmlFor={submissionDateInputId} style={{ fontWeight: 600 }}>
                  Data
                </label>
                <input
                  id={submissionDateInputId}
                  type="date"
                  value={submissionDate}
                  onChange={(event) => setSubmissionDate(event.target.value)}
                  style={fieldStyle}
                />
              </div>
            </div>

            {selectedAssignmentId && studentsLoading && (
              <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
                Carregando estudantes…
              </p>
            )}

            {selectedAssignmentId && studentsError && (
              <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
                {studentsError}
              </p>
            )}

            {selectedAssignmentId &&
              !studentsLoading &&
              !studentsError &&
              students.length === 0 && (
                <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
                  Nenhum estudante matriculado nesta turma.
                </p>
              )}

            {students.length > 0 && !canSaveSubmission && (
              <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
                Selecione a atividade e a data para registrar o status de entrega.
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
                  <SubmissionRow
                    key={student.id}
                    student={student}
                    rowState={rowStates[student.id]}
                    canSave={canSaveSubmission}
                    onStatusChange={(status) =>
                      updateRow(student.id, { status, message: null, isError: false })
                    }
                    onSave={() => handleSaveSubmission(student.id)}
                  />
                ))}
              </ul>
            )}
          </section>
        )}
      </main>
    </div>
  )
}

function SubmissionRow({
  student,
  rowState,
  canSave,
  onStatusChange,
  onSave,
}: {
  student: Student
  rowState: RowState | undefined
  canSave: boolean
  onStatusChange: (status: SubmissionStatusValue) => void
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
          onChange={(event) => onStatusChange(event.target.value as SubmissionStatusValue)}
          aria-describedby={rowState.message ? messageId : undefined}
          style={{ ...fieldStyle, minWidth: 160 }}
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
