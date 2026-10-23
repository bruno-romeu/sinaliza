import { useEffect, useId, useRef, useState } from 'react'
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
import { Button, ChoiceGroup, Notice, RosterRow, Section, SelectField, TextField } from '../../components/ui'
import { LancamentoLayout, RosterStates, rowStatus } from './LancamentoLayout'

type SubmissionStatusValue = AssignmentSubmissionCreateRequest['status']

const STATUS_OPTIONS: { value: SubmissionStatusValue; label: string }[] = [
  { value: 'DELIVERED', label: 'Entregue' },
  { value: 'PARTIAL', label: 'Parcial' },
  { value: 'NOT_DELIVERED', label: 'Não entregue' },
]

function todayIsoDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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
    <LancamentoLayout
      title="Atividades"
      description="Cadastre uma atividade da turma e registre o status de entrega de cada estudante. Cada linha salva sozinha."
      contextTitle="Turma e atividade"
      contextError={classroomsError ?? periodsError}
      context={
        <SelectField label="Turma" value={selectedClassroomId} onChange={(event) => setSelectedClassroomId(event.target.value)}>
          <option value="">Selecione…</option>
          {classrooms.map((classroom) => (
            <option key={classroom.id} value={classroom.id}>
              {classroom.name}
            </option>
          ))}
        </SelectField>
      }
    >
      {selectedClassroomId && (
        <Section id="lancamento-nova-atividade" title="Cadastrar atividade">
          <div className="sz-ctx" style={{ alignItems: 'end' }}>
            <TextField
              label="Disciplina"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Ex.: Matemática"
            />
            <SelectField label="Período letivo" value={periodId} onChange={(event) => setPeriodId(event.target.value)}>
              <option value="">Selecione…</option>
              {periods.map((period) => (
                <option key={period.id} value={period.id}>
                  {period.label}
                </option>
              ))}
            </SelectField>
            <TextField label="Data de entrega" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            <div>
              <Button icon="mais" onClick={handleCreateAssignment} disabled={creatingAssignment || !canCreateAssignment}>
                {creatingAssignment ? 'Cadastrando…' : 'Cadastrar atividade'}
              </Button>
            </div>
          </div>
          {assignmentMessage && (
            <Notice tone={assignmentMessageIsError ? 'attention' : 'success'} role={assignmentMessageIsError ? 'alert' : 'status'}>
              {assignmentMessage}
            </Notice>
          )}
          {assignmentsError && <Notice tone="attention">{assignmentsError}</Notice>}
        </Section>
      )}

      {selectedClassroomId && !assignmentsError && assignments.length === 0 && (
        <p className="sz-muted sz-section">
          Nenhuma atividade cadastrada nesta turma ainda. Cadastre uma atividade acima para registrar o status de
          entrega.
        </p>
      )}

      {selectedClassroomId && assignments.length > 0 && (
        <Section id="lancamento-entregas" title="Status de entrega">
          <div className="sz-ctx">
            <SelectField
              label="Atividade"
              value={selectedAssignmentId}
              onChange={(event) => setSelectedAssignmentId(event.target.value)}
            >
              <option value="">Selecione…</option>
              {assignments.map((assignment) => (
                <option key={assignment.id} value={assignment.id}>
                  {assignment.subject} · prazo {formatDateBr(assignment.due_date)}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Data"
              type="date"
              value={submissionDate}
              onChange={(event) => setSubmissionDate(event.target.value)}
            />
          </div>
          {selectedAssignmentId && (
            <RosterStates
              selected
              loading={studentsLoading}
              error={studentsError}
              empty={!studentsLoading && !studentsError && students.length === 0}
            />
          )}
          {students.length > 0 && !canSaveSubmission && (
            <Notice tone="info">Selecione a atividade e a data para registrar o status de entrega.</Notice>
          )}
          {students.length > 0 && (
            <ul className="sz-roster">
              {students.map((student) => (
                <SubmissionRow
                  key={student.id}
                  student={student}
                  rowState={rowStates[student.id]}
                  canSave={canSaveSubmission}
                  onStatusChange={(status) => updateRow(student.id, { status, message: null, isError: false })}
                  onSave={() => handleSaveSubmission(student.id)}
                />
              ))}
            </ul>
          )}
        </Section>
      )}
    </LancamentoLayout>
  )
}

function formatDateBr(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('pt-BR')
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
  const nameId = useId()
  if (!rowState) return null
  return (
    <li>
      <RosterRow
        nameId={nameId}
        name={student.name}
        status={rowStatus(rowState)}
        message={rowState.message}
        onSave={onSave}
        saveDisabled={!canSave}
      >
        <ChoiceGroup
          label={`Entrega de ${student.name}`}
          hideLabel
          value={rowState.status}
          onChange={onStatusChange}
          options={STATUS_OPTIONS}
        />
      </RosterRow>
    </li>
  )
}
