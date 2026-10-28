import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getHome,
  searchStudents,
  type InProgressFollowUp,
  type RecentChange,
  type StudentSearchResult,
} from '../api/client'
import {
  Button,
  CalmState,
  ChangeRow,
  FollowupCard,
  Icon,
  Notice,
  Page,
  ScreenHead,
  Section,
  Skeleton,
  Tag,
  TextField,
  type Indicator,
} from '../components/ui'
import { Link } from 'react-router-dom'

type ChangeType = RecentChange['type']

// Indicador de cada tipo de mudança (design system: a cor diz de onde vem o
// sinal). `COMBINED_DETERIORATION` envolve mais de um sinal e a API ainda não
// diz quais, então não ganha chip (Contrato de dados, proposta `signal_kinds`).
const CHANGE_TYPE_INDICATORS: Record<ChangeType, Indicator[]> = {
  ATTENDANCE_DROP: ['frequencia'],
  GRADE_DROP: ['notas'],
  MISSING_ASSIGNMENTS_INCREASE: ['entregas'],
  COMBINED_DETERIORATION: [],
}

function formatDetectedAt(detectedAt: string): string {
  const date = new Date(detectedAt)
  if (Number.isNaN(date.getTime())) return detectedAt
  // `detected_at` is a UTC-midnight timestamp (`datetime.combine(as_of_date,
  // time.min, tzinfo=timezone.utc)`, Story 3.2). Formatting it with
  // `toLocaleDateString` would convert to the browser's local timezone
  // first, which for a Brazil-based browser (UTC-3) rolls midnight UTC back
  // to the previous local day — "today" would display as yesterday. Read
  // the UTC calendar date directly instead, so the displayed date always
  // matches the date the backend intended.
  return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' })
}

function plural(count: number, singular: string, pluralForm: string) {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

/**
 * Home: recent trajectory changes (read-only, never recomputed here) plus a
 * student search box — both link to `/estudantes/:studentId`. No
 * ranking/score/"high-risk" KPI anywhere (spec Boundaries & Constraints).
 * Visual: design system `TelaHome`.
 */
export function Home() {
  const { token } = useAuth()

  const [recentChanges, setRecentChanges] = useState<RecentChange[] | null>(null)
  const [inProgressFollowUps, setInProgressFollowUps] = useState<InProgressFollowUp[] | null>(null)
  const [followUpsPage, setFollowUpsPage] = useState(1)
  const [followUpsTotal, setFollowUpsTotal] = useState(0)
  const [loadingMoreFollowUps, setLoadingMoreFollowUps] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StudentSearchResult[] | null>(null)
  const [searchPage, setSearchPage] = useState(1)
  const [searchTotal, setSearchTotal] = useState(0)
  const [loadingMoreResults, setLoadingMoreResults] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)

  // Stale-response guard (mirrors `Atividades.tsx`'s `ignore` flag idiom).
  useEffect(() => {
    if (!token) return
    let ignore = false
    setLoadError(false)
    getHome(token)
      .then((home) => {
        if (ignore) return
        setRecentChanges(home.recent_changes)
        setInProgressFollowUps(home.in_progress_follow_ups)
        setFollowUpsPage(home.in_progress_follow_ups_page)
        setFollowUpsTotal(home.in_progress_follow_ups_total)
      })
      .catch(() => {
        if (ignore) return
        setLoadError(true)
      })
    return () => {
      ignore = true
    }
  }, [token, loadAttempt])

  function handleLoadMoreFollowUps() {
    if (!token || loadingMoreFollowUps) return
    setLoadingMoreFollowUps(true)
    const nextPage = followUpsPage + 1
    getHome(token, nextPage)
      .then((home) => {
        setInProgressFollowUps((prev) => [...(prev ?? []), ...home.in_progress_follow_ups])
        setFollowUpsPage(home.in_progress_follow_ups_page)
        setFollowUpsTotal(home.in_progress_follow_ups_total)
      })
      .finally(() => setLoadingMoreFollowUps(false))
  }

  // Stores the trimmed query so the staleness check below compares
  // trimmed-to-trimmed (see `queryAtStart` below); a leading/trailing space
  // typed after the debounce fired must not be treated as "still stale".
  const queryRef = useRef(query.trim())
  queryRef.current = query.trim()

  useEffect(() => {
    if (!token || !query.trim()) {
      setResults(null)
      setSearchError(null)
      setSearching(false)
      setSearchPage(1)
      setSearchTotal(0)
      return
    }
    let ignore = false
    setSearching(true)
    setSearchError(null)
    // Trimmed before being sent (Review patch): a trailing/leading space
    // (e.g. "Ana ") must still match a student literally named "Ana".
    const queryAtStart = query.trim()
    const timeoutId = window.setTimeout(() => {
      searchStudents(token, queryAtStart)
        .then((response) => {
          if (ignore || queryRef.current !== queryAtStart) return
          setResults(response.results)
          setSearchPage(response.page)
          setSearchTotal(response.total)
        })
        .catch((caught) => {
          if (ignore || queryRef.current !== queryAtStart) return
          const message =
            caught instanceof ApiError ? caught.message : 'Não foi possível buscar estudantes agora.'
          setSearchError(message)
        })
        .finally(() => {
          if (ignore || queryRef.current !== queryAtStart) return
          setSearching(false)
        })
    }, 250)
    return () => {
      ignore = true
      window.clearTimeout(timeoutId)
    }
  }, [token, query])

  function handleLoadMoreResults() {
    const trimmed = query.trim()
    if (!token || !trimmed || loadingMoreResults) return
    setLoadingMoreResults(true)
    const nextPage = searchPage + 1
    searchStudents(token, trimmed, nextPage)
      .then((response) => {
        if (queryRef.current !== trimmed) return
        setResults((prev) => [...(prev ?? []), ...response.results])
        setSearchPage(response.page)
        setSearchTotal(response.total)
      })
      .finally(() => setLoadingMoreResults(false))
  }

  const showingSearch = query.trim().length > 0

  return (
    <Page>
      <ScreenHead kicker="Coordenação pedagógica" title="Home">
        {recentChanges !== null && inProgressFollowUps !== null && !loadError && (
          <p className="sz-summary">
            {recentChanges.length > 0 ? (
              <>
                <b>{plural(recentChanges.length, 'mudança', 'mudanças')}</b> para revisar
              </>
            ) : (
              'Nada novo para revisar'
            )}
            {' · '}
            <b>{plural(inProgressFollowUps.length, 'acompanhamento', 'acompanhamentos')}</b> em andamento
          </p>
        )}
      </ScreenHead>

      <div style={{ marginTop: 32, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <TextField
          label="Buscar estudante por nome ou turma"
          icon="busca"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ex.: Maria ou 7º Ano A"
          hint="A Home mostra só quem tem mudança recente ou acompanhamento. Use a busca para chegar aos demais."
        />
      </div>

      {showingSearch && (
        <Section id="home-busca" title="Resultados da busca">
          <p role="status" aria-live="polite" className="sz-muted">
            {searching
              ? 'Buscando…'
              : results !== null
                ? `${results.length} ${results.length === 1 ? 'estudante encontrado' : 'estudantes encontrados'}`
                : ''}
          </p>

          {searchError && <Notice tone="attention">{searchError}</Notice>}

          {!searching && !searchError && results !== null && results.length === 0 && (
            <p className="sz-muted">Nenhum estudante encontrado com esse nome/turma.</p>
          )}

          {results !== null && results.length > 0 && (
            <>
              <ul className="sz-results">
                {results.map((result) => (
                  <li key={result.id}>
                    <Link to={`/estudantes/${result.id}`}>
                      <Icon name="pessoa" size={20} style={{ color: 'var(--ink-muted)' }} />
                      <span className="sz-results-name">{result.name}</span>
                      <Tag>{result.classroom_name}</Tag>
                      <Icon name="chevron-dir" size={20} className="sz-results-chev" />
                    </Link>
                  </li>
                ))}
              </ul>
              {results.length < searchTotal && (
                <Button variant="quiet" onClick={handleLoadMoreResults} disabled={loadingMoreResults}>
                  {loadingMoreResults ? 'Carregando…' : `Ver mais (${searchTotal - results.length} restantes)`}
                </Button>
              )}
            </>
          )}
        </Section>
      )}

      {!showingSearch && (
        <Section id="home-mudancas" title="Mudanças recentes">
          {recentChanges === null && !loadError && <Skeleton heights={[72, 72, 72]} />}

          {loadError && (
            <Notice
              tone="attention"
              action={
                <Button variant="secondary" onClick={() => setLoadAttempt((n) => n + 1)}>
                  Tentar novamente
                </Button>
              }
            >
              Não foi possível carregar os dados agora.
            </Notice>
          )}

          {recentChanges !== null && !loadError && recentChanges.length === 0 && (
            <CalmState kicker="Tudo dentro da faixa habitual" title="Nenhuma mudança a revisar hoje.">
              Os estudantes com registros recentes seguem dentro da própria faixa habitual.
            </CalmState>
          )}

          {recentChanges !== null && !loadError && recentChanges.length > 0 && (
            <ul className="sz-list">
              {recentChanges.map((change, index) => (
                <li key={`${change.student_id}-${index}`}>
                  <ChangeRow
                    to={`/estudantes/${change.student_id}`}
                    name={change.student_name}
                    description={change.description}
                    date={formatDetectedAt(change.detected_at)}
                    indicators={CHANGE_TYPE_INDICATORS[change.type]}
                  />
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {/* Always renders, independent of `showingSearch` (spec-4-5 Boundaries
          & Constraints, UX-DR18) — the active-follow-ups count stays
          visible even while search results are showing. */}
      <Section id="home-acompanhamentos" title="Acompanhamentos em andamento">
        {inProgressFollowUps === null && !loadError && <Skeleton heights={[64, 64]} />}

        {inProgressFollowUps !== null && inProgressFollowUps.length === 0 && (
          <p className="sz-muted">Nenhum acompanhamento em andamento no momento</p>
        )}

        {inProgressFollowUps !== null && inProgressFollowUps.length > 0 && (
          <>
            <ul className="sz-list">
              {inProgressFollowUps.map((item) => (
                <li key={item.id}>
                  <FollowupCard to={`/acompanhamentos/${item.id}`} name={item.student_name} status={item.status} />
                </li>
              ))}
            </ul>
            {inProgressFollowUps.length < followUpsTotal && (
              <Button variant="quiet" onClick={handleLoadMoreFollowUps} disabled={loadingMoreFollowUps}>
                {loadingMoreFollowUps
                  ? 'Carregando…'
                  : `Ver mais (${followUpsTotal - inProgressFollowUps.length} restantes)`}
              </Button>
            )}
          </>
        )}
      </Section>
    </Page>
  )
}
