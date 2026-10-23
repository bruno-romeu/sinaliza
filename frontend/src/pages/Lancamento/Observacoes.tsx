import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import {
  ApiError,
  listClassrooms,
  listEnrolledStudents,
  registerPedagogicalObservation,
  type Classroom,
  type Student,
} from '../../api/client'
import { Button, RosterRow, Section, SelectField, TextAreaField } from '../../components/ui'
import { LancamentoLayout, RosterStates, rowStatus } from './LancamentoLayout'

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
    <LancamentoLayout
      title="Observações"
      description="Selecione a turma e registre uma observação pedagógica em texto livre para cada estudante."
      contextTitle="Contexto"
      contextError={classroomsError}
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
      <Section id="lancamento-alunos" title="Estudantes">
        <p className="sz-muted">Abra a linha do estudante e descreva o que foi observado.</p>
        <RosterStates
          selected={Boolean(selectedClassroomId)}
          loading={studentsLoading}
          error={studentsError}
          empty={!studentsLoading && !studentsError && students.length === 0}
        />
        {students.length > 0 && (
          <ul className="sz-roster">
            {students.map((student) => (
              <ObservacaoRow
                key={student.id}
                student={student}
                rowState={rowStates[student.id]}
                onTextChange={(text) => updateRow(student.id, { text, message: null, isError: false })}
                onSave={() => handleSave(student.id)}
              />
            ))}
          </ul>
        )}
      </Section>

      <Section id="lancamento-guia" title="Como escrever">
        <div className="sz-guide">
          <div className="sz-guide-ok">
            <b>Escreva</b>
            “Participou menos das discussões nas últimas duas aulas e não entregou a atividade desta semana.”
          </div>
          <div className="sz-guide-no">
            <b>Evite</b>
            “Está desmotivado.” · “É aluno de risco.” · “Provavelmente vai evadir.”
          </div>
        </div>
      </Section>
    </LancamentoLayout>
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
  const nameId = useId()
  const [open, setOpen] = useState(false)
  if (!rowState) return null
  const canSave = rowState.text.trim() !== ''
  const status = rowStatus(rowState)
  return (
    <li>
      <RosterRow
        nameId={nameId}
        name={student.name}
        status={status}
        message={rowState.message}
        extra={
          open ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 0 8px' }}>
              <TextAreaField
                label={`Observação sobre ${student.name}`}
                value={rowState.text}
                rows={3}
                placeholder="Ex.: Participou menos das discussões nas últimas duas aulas."
                hint="Fatos observáveis, sem julgamentos sobre o estudante."
                onChange={(event) => onTextChange(event.target.value)}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={onSave} disabled={rowState.saving || !canSave}>
                  {rowState.saving ? 'Salvando…' : 'Salvar observação'}
                </Button>
              </div>
            </div>
          ) : undefined
        }
      >
        {!open && (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button variant="secondary" icon="observacao" onClick={() => setOpen(true)} aria-describedby={nameId}>
              {status === 'saved' ? 'Escrever outra' : 'Escrever observação'}
            </Button>
          </div>
        )}
      </RosterRow>
    </li>
  )
}
