import { useEffect, useId, useRef, useState } from 'react'
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
import { Notice, RosterRow, Section, SelectField, TextField } from '../../components/ui'
import { LancamentoLayout, RosterStates, rowStatus } from './LancamentoLayout'

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
    <LancamentoLayout
      title="Notas"
      description="Defina turma, disciplina, bimestre e data, e lance a nota de cada estudante. Cada linha salva sozinha."
      contextTitle="Turma e avaliação"
      contextError={classroomsError ?? periodsError}
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
          <TextField
            label="Disciplina"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="Ex.: Matemática"
          />
          <SelectField
            label="Período letivo"
            value={selectedPeriodId}
            onChange={(event) => setSelectedPeriodId(event.target.value)}
          >
            <option value="">Selecione…</option>
            {periods.map((period) => (
              <option key={period.id} value={period.id}>
                {period.label}
              </option>
            ))}
          </SelectField>
          <TextField label="Data" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </>
      }
    >
      <Section id="lancamento-alunos" title="Estudantes">
        <p className="sz-muted">Valores de 0 a 10, com até duas casas decimais.</p>
        <RosterStates
          selected={Boolean(selectedClassroomId)}
          loading={studentsLoading}
          error={studentsError}
          empty={!studentsLoading && !studentsError && students.length === 0}
        />
        {students.length > 0 && !canSave && <Notice tone="info">Selecione disciplina, período letivo e data para lançar notas.</Notice>}
        {students.length > 0 && (
          <ul className="sz-roster">
            {students.map((student) => (
              <GradeRow
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
      </Section>
    </LancamentoLayout>
  )
}

function GradeRow({
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
  const nameId = useId()
  const valueId = useId()
  const messageId = useId()
  if (!rowState) return null
  return (
    <li>
      <RosterRow
        nameId={nameId}
        name={student.name}
        status={rowStatus(rowState)}
        message={rowState.message}
        messageId={messageId}
        onSave={onSave}
        saveDisabled={!canSave}
      >
        <label className="sz-sr" htmlFor={valueId}>
          Nota de {student.name}
        </label>
        <input
          id={valueId}
          type="number"
          inputMode="decimal"
          min={0}
          max={10}
          step={0.01}
          placeholder="0 a 10"
          value={rowState.value}
          onChange={(event) => onValueChange(event.target.value)}
          aria-invalid={rowState.isError || undefined}
          aria-describedby={messageId}
        />
      </RosterRow>
    </li>
  )
}
