import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  getHome,
  searchStudents,
  type InProgressFollowUp,
  type RecentChange,
  type StudentSearchResult,
} from '../api/client'
import { Header } from '../components/Header'
import { FollowUpStatusPill } from '../components/FollowUpStatusPill'

type ChangeType = RecentChange['type']

// Icon marker mapping (Design Notes): a small icon + text label per
// `TrajectoryChangeType` — never color alone (epic-3 accessibility floor).
const CHANGE_TYPE_LABELS: Record<ChangeType, { icon: string; label: string }> = {
  ATTENDANCE_DROP: { icon: '📉', label: 'Queda de frequência' },
  GRADE_DROP: { icon: '📝', label: 'Queda de notas' },
  MISSING_ASSIGNMENTS_INCREASE: { icon: '📌', label: 'Aumento de atividades pendentes' },
  COMBINED_DETERIORATION: { icon: '⚠️', label: 'Mudança combinada' },
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

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 16,
  padding: '16px 20px',
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  textDecoration: 'none',
  color: 'var(--color-text)',
  minHeight: 'var(--min-hit-target)',
} as const

/**
 * Home: recent trajectory changes (read-only, never recomputed here) plus a
 * student search box — both link to `/estudantes/:studentId` (Story 3.4's
 * stub landing target). No ranking/score/"high-risk" KPI anywhere (spec
 * Boundaries & Constraints).
 */
export function Home() {
  const { token } = useAuth()
  const searchInputId = useId()

  const [recentChanges, setRecentChanges] = useState<RecentChange[] | null>(null)
  const [inProgressFollowUps, setInProgressFollowUps] = useState<InProgressFollowUp[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StudentSearchResult[] | null>(null)
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
      })
      .catch(() => {
        if (ignore) return
        setLoadError(true)
      })
    return () => {
      ignore = true
    }
  }, [token, loadAttempt])

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

  const showingSearch = query.trim().length > 0

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
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Home</h1>
          <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
            Mudanças recentes detectadas e busca de estudantes.
          </p>
        </div>

        <section style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 420 }}>
          <label htmlFor={searchInputId} style={{ fontWeight: 600 }}>
            Buscar estudante por nome ou turma
          </label>
          <input
            id={searchInputId}
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ex.: Maria ou 7º Ano A"
            style={{
              minHeight: 'var(--min-hit-target)',
              padding: '0 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 15,
            }}
          />
        </section>

        {/* Always renders, independent of `showingSearch` (spec-4-5 Boundaries
            & Constraints, UX-DR18) — the active-follow-ups count stays
            visible even while search results are showing. */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Acompanhamentos em andamento</h2>

          {inProgressFollowUps === null && !loadError && (
            <div aria-hidden="true" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[0, 1].map((i) => (
                <div
                  key={i}
                  style={{
                    height: 64,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-border)',
                    opacity: 0.4,
                  }}
                />
              ))}
            </div>
          )}

          {inProgressFollowUps !== null && inProgressFollowUps.length === 0 && (
            <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
              Nenhum acompanhamento em andamento no momento
            </p>
          )}

          {inProgressFollowUps !== null && inProgressFollowUps.length > 0 && (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {inProgressFollowUps.map((item) => (
                <li key={item.id}>
                  <Link to={`/acompanhamentos/${item.id}`} style={rowStyle}>
                    <FollowUpStatusPill status={item.status} />
                    <span style={{ fontWeight: 600 }}>{item.student_name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {showingSearch && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Resultados da busca</h2>

            <p role="status" aria-live="polite" style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
              {searching
                ? 'Buscando…'
                : results !== null
                  ? `${results.length} ${results.length === 1 ? 'estudante encontrado' : 'estudantes encontrados'}`
                  : ''}
            </p>

            {searchError && (
              <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
                {searchError}
              </p>
            )}

            {!searching && !searchError && results !== null && results.length === 0 && (
              <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
                Nenhum estudante encontrado com esse nome/turma.
              </p>
            )}

            {results !== null && results.length > 0 && (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {results.map((result) => (
                  <li key={result.id}>
                    <Link to={`/estudantes/${result.id}`} style={rowStyle}>
                      <span style={{ fontWeight: 600 }}>{result.name}</span>
                      <span style={{ color: 'var(--color-text-secondary)', fontSize: 14 }}>
                        {result.classroom_name}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {!showingSearch && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Mudanças recentes</h2>

            {recentChanges === null && !loadError && (
              <div aria-hidden="true" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    style={{
                      height: 64,
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--color-border)',
                      opacity: 0.4,
                    }}
                  />
                ))}
              </div>
            )}

            {loadError && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <p role="alert" style={{ color: 'var(--color-attention)', margin: 0 }}>
                  Não foi possível carregar os dados agora.
                </p>
                <div>
                  <button
                    type="button"
                    onClick={() => setLoadAttempt((n) => n + 1)}
                    style={{
                      minHeight: 'var(--min-hit-target)',
                      minWidth: 'var(--min-hit-target)',
                      padding: '0 16px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-surface)',
                      color: 'var(--color-text)',
                      fontSize: 15,
                      cursor: 'pointer',
                    }}
                  >
                    Tentar novamente
                  </button>
                </div>
              </div>
            )}

            {recentChanges !== null && !loadError && recentChanges.length === 0 && (
              <p style={{ color: 'var(--color-text-secondary)', margin: 0 }}>
                Nenhuma mudança a revisar hoje.
              </p>
            )}

            {recentChanges !== null && !loadError && recentChanges.length > 0 && (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {recentChanges.map((change, index) => {
                  const typeInfo = CHANGE_TYPE_LABELS[change.type]
                  return (
                    <li key={`${change.student_id}-${index}`}>
                      <Link to={`/estudantes/${change.student_id}`} style={rowStyle}>
                        <span aria-hidden="true" style={{ fontSize: 20 }}>
                          {typeInfo.icon}
                        </span>
                        <span style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
                          <span style={{ fontWeight: 600 }}>{change.student_name}</span>
                          <span style={{ color: 'var(--color-text-secondary)', fontSize: 14 }}>
                            {/* spec-ui-1: the description already names the
                                signals and the period ("Queda de frequência no
                                3º Bimestre"), so the type label is not repeated
                                and no dash is used. */}
                            {change.description}
                          </span>
                        </span>
                        <span style={{ color: 'var(--color-text-secondary)', fontSize: 13, whiteSpace: 'nowrap' }}>
                          {formatDetectedAt(change.detected_at)}
                        </span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
