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

// spec-ui-4: the three Home lists page with "Ver mais". Pages are offset
// based, so a row can come back twice if the list changed in between (a
// follow-up opened, a change recomputed); appending through this keeps each
// row once.
function appendUnique<T>(prev: T[] | null, next: T[], key: (item: T) => string): T[] {
  const seen = new Set((prev ?? []).map(key))
  return [...(prev ?? []), ...next.filter((item) => !seen.has(key(item)))]
}

const changeKey = (change: RecentChange) => `${change.student_id}|${change.type}|${change.description}`
const followUpKey = (followUp: InProgressFollowUp) => followUp.id
const resultKey = (result: StudentSearchResult) => `${result.id}|${result.classroom_name}`

const LOAD_MORE_ERROR = 'Não foi possível carregar mais agora. Tente de novo.'

function LoadMore({
  shown,
  total,
  loading,
  error,
  onClick,
}: {
  shown: number
  total: number
  loading: boolean
  error: boolean
  onClick: () => void
}) {
  if (shown >= total && !error) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8, marginTop: 4 }}>
      {error && <Notice tone="attention">{LOAD_MORE_ERROR}</Notice>}
      {shown < total && (
        <Button variant="quiet" onClick={onClick} disabled={loading}>
          {loading ? 'Carregando…' : `Ver mais (${plural(total - shown, 'restante', 'restantes')})`}
        </Button>
      )}
    </div>
  )
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
  const [changesPage, setChangesPage] = useState(1)
  const [changesTotal, setChangesTotal] = useState(0)
  const [loadingMoreChanges, setLoadingMoreChanges] = useState(false)
  const [moreChangesError, setMoreChangesError] = useState(false)
  const [inProgressFollowUps, setInProgressFollowUps] = useState<InProgressFollowUp[] | null>(null)
  const [followUpsPage, setFollowUpsPage] = useState(1)
  const [followUpsTotal, setFollowUpsTotal] = useState(0)
  const [loadingMoreFollowUps, setLoadingMoreFollowUps] = useState(false)
  const [moreFollowUpsError, setMoreFollowUpsError] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StudentSearchResult[] | null>(null)
  const [searchPage, setSearchPage] = useState(1)
  const [searchTotal, setSearchTotal] = useState(0)
  const [loadingMoreResults, setLoadingMoreResults] = useState(false)
  const [moreResultsError, setMoreResultsError] = useState(false)
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
        setChangesPage(home.recent_changes_page)
        setChangesTotal(home.recent_changes_total)
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

  // Each "Ver mais" asks only for the next page of its own list; the other
  // list keeps its page untouched.
  function handleLoadMoreChanges() {
    if (!token || loadingMoreChanges) return
    setLoadingMoreChanges(true)
    setMoreChangesError(false)
    getHome(token, { changesPage: changesPage + 1 })
      .then((home) => {
        setRecentChanges((prev) => appendUnique(prev, home.recent_changes, changeKey))
        setChangesPage(home.recent_changes_page)
        setChangesTotal(home.recent_changes_total)
      })
      .catch(() => setMoreChangesError(true))
      .finally(() => setLoadingMoreChanges(false))
  }

  function handleLoadMoreFollowUps() {
    if (!token || loadingMoreFollowUps) return
    setLoadingMoreFollowUps(true)
    setMoreFollowUpsError(false)
    getHome(token, { followUpsPage: followUpsPage + 1 })
      .then((home) => {
        setInProgressFollowUps((prev) => appendUnique(prev, home.in_progress_follow_ups, followUpKey))
        setFollowUpsPage(home.in_progress_follow_ups_page)
        setFollowUpsTotal(home.in_progress_follow_ups_total)
      })
      .catch(() => setMoreFollowUpsError(true))
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
      setMoreResultsError(false)
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
          setMoreResultsError(false)
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
    setMoreResultsError(false)
    const nextPage = searchPage + 1
    searchStudents(token, trimmed, nextPage)
      .then((response) => {
        if (queryRef.current !== trimmed) return
        setResults((prev) => appendUnique(prev, response.results, resultKey))
        setSearchPage(response.page)
        setSearchTotal(response.total)
      })
      .catch(() => {
        if (queryRef.current !== trimmed) return
        setMoreResultsError(true)
      })
      .finally(() => setLoadingMoreResults(false))
  }

  const showingSearch = query.trim().length > 0

  return (
    <Page>
      <ScreenHead kicker="Coordenação pedagógica" title="Home">
        {recentChanges !== null && inProgressFollowUps !== null && !loadError && (
          <p className="sz-summary">
            {changesTotal > 0 ? (
              <>
                <b>{plural(changesTotal, 'mudança', 'mudanças')}</b> para revisar
              </>
            ) : (
              'Nada novo para revisar'
            )}
            {' · '}
            <b>{plural(followUpsTotal, 'acompanhamento', 'acompanhamentos')}</b> em andamento
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
                ? `${searchTotal} ${searchTotal === 1 ? 'estudante encontrado' : 'estudantes encontrados'}`
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
                  <li key={resultKey(result)}>
                    <Link to={`/estudantes/${result.id}`}>
                      <Icon name="pessoa" size={20} style={{ color: 'var(--ink-muted)' }} />
                      <span className="sz-results-name">{result.name}</span>
                      <Tag>{result.classroom_name}</Tag>
                      <Icon name="chevron-dir" size={20} className="sz-results-chev" />
                    </Link>
                  </li>
                ))}
              </ul>
              <LoadMore
                shown={results.length}
                total={searchTotal}
                loading={loadingMoreResults}
                error={moreResultsError}
                onClick={handleLoadMoreResults}
              />
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
              {recentChanges.map((change) => (
                <li key={changeKey(change)}>
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
          {recentChanges !== null && !loadError && recentChanges.length > 0 && (
            <LoadMore
              shown={recentChanges.length}
              total={changesTotal}
              loading={loadingMoreChanges}
              error={moreChangesError}
              onClick={handleLoadMoreChanges}
            />
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
            <LoadMore
              shown={inProgressFollowUps.length}
              total={followUpsTotal}
              loading={loadingMoreFollowUps}
              error={moreFollowUpsError}
              onClick={handleLoadMoreFollowUps}
            />
          </>
        )}
      </Section>
    </Page>
  )
}
