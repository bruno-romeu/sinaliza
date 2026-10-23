import type { ReactNode } from 'react'
import { NavTabs, Notice, Page, ScreenHead, Section, type RosterStatus } from '../../components/ui'

const TIPOS = [
  { to: '/lancamento/presenca', label: 'Presença', indicator: 'frequencia' as const },
  { to: '/lancamento/notas', label: 'Notas', indicator: 'notas' as const },
  { to: '/lancamento/atividades', label: 'Atividades', indicator: 'entregas' as const },
  { to: '/lancamento/observacoes', label: 'Observações', indicator: 'observacao' as const },
]

/**
 * Estrutura comum das 4 telas de Lançamento (design system `TelaLancamento`):
 * título, abas por tipo (cada aba continua sendo uma rota), um card de
 * contexto (turma, data, disciplina…) e a lista da turma.
 */
export function LancamentoLayout({
  title,
  description,
  contextTitle,
  context,
  contextError,
  children,
}: {
  title: string
  description: ReactNode
  contextTitle: string
  context: ReactNode
  contextError?: ReactNode
  children: ReactNode
}) {
  return (
    <Page>
      <ScreenHead kicker="Lançar registro" title={title}>
        <p className="sz-summary">{description}</p>
      </ScreenHead>
      <div style={{ marginTop: 32 }}>
        <NavTabs label="Tipo de registro" items={TIPOS} />
      </div>
      <Section id="lancamento-contexto" title={contextTitle} style={{ marginTop: 24 }}>
        <div className="sz-ctx">{context}</div>
        {contextError && <Notice tone="attention">{contextError}</Notice>}
      </Section>
      {children}
    </Page>
  )
}

/** Estado de linha das telas de Lançamento traduzido para o `RosterRow`. */
export function rowStatus(row: { saving: boolean; message: string | null; isError: boolean }): RosterStatus {
  if (row.saving) return 'saving'
  if (row.isError) return 'error'
  if (row.message) return 'saved'
  return 'idle'
}

/** Mensagens de carregamento e lista vazia da turma. */
export function RosterStates({
  selected,
  loading,
  error,
  empty,
}: {
  selected: boolean
  loading: boolean
  error: string | null
  empty: boolean
}) {
  if (!selected) return <p className="sz-muted">Selecione a turma para ver os estudantes.</p>
  if (loading) return <p className="sz-muted">Carregando estudantes…</p>
  if (error) return <Notice tone="attention">{error}</Notice>
  if (empty) return <p className="sz-muted">Nenhum estudante matriculado nesta turma.</p>
  return null
}
