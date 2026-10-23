import { useEffect, useId, useRef, useState } from 'react'
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
import { Button, ChoiceGroup, RosterRow, Section, SelectField, TextField } from '../../components/ui'
import { LancamentoLayout, RosterStates, rowStatus } from './LancamentoLayout'

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
    <LancamentoLayout
      title="Presença"
      description="Selecione a turma e a data para registrar a presença de cada estudante. Cada linha salva sozinha."
      contextTitle="Turma e data"
      contextError={classroomsError}
      context={
        <>
          <SelectField
            label="Turma"
            value={selectedClassroomId}
            onChange={(event) => setSelectedClassroomId(event.target.value)}
          >
            <option value="">Selecione…</option>
            {classrooms.map((classroom) => (
              <option key={classroom.id} value={classroom.id}>
                {classroom.name}
              </option>
            ))}
          </SelectField>
          <TextField label="Data" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </>
      }
    >
      <Section id="lancamento-alunos" title="Estudantes">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <p className="sz-muted">Todos começam como "Presente". Ajuste quem faltou e salve linha por linha.</p>
          {students.length > 0 && (
            <Button
              variant="quiet"
              icon="check"
              onClick={() =>
                setRowStates((prev) =>
                  Object.fromEntries(
                    Object.entries(prev).map(([id, row]) => [
                      id,
                      row.saving ? row : { ...row, status: 'PRESENT' as AttendanceStatusValue },
                    ]),
                  ),
                )
              }
            >
              Marcar todos como presentes
            </Button>
          )}
        </div>
        <RosterStates
          selected={Boolean(selectedClassroomId)}
          loading={studentsLoading}
          error={studentsError}
          empty={!studentsLoading && !studentsError && students.length === 0}
        />
        {students.length > 0 && (
          <ul className="sz-roster">
            {students.map((student) => (
              <AttendanceRow
                key={student.id}
                student={student}
                rowState={rowStates[student.id]}
                onStatusChange={(status) => updateRow(student.id, { status, message: null, isError: false })}
                onSave={() => handleSave(student.id)}
              />
            ))}
          </ul>
        )}
      </Section>
    </LancamentoLayout>
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
      >
        <ChoiceGroup
          label={`Presença de ${student.name}`}
          hideLabel
          value={rowState.status}
          onChange={onStatusChange}
          options={STATUS_OPTIONS}
        />
      </RosterRow>
    </li>
  )
}
