import { Header } from '../components/Header'

/**
 * Stub landing target for a recent-change row / search result
 * (`/estudantes/:studentId`) — Story 3.4 replaces this with the real
 * Trajetória do Estudante screen (chart, evidence, concerning-factor UI).
 * Content-free beyond a placeholder message (spec-3-3 Boundaries &
 * Constraints).
 */
export function EstudanteTrajetoria() {
  return (
    <div>
      <Header />
      <main
        style={{
          maxWidth: 'var(--spacing-content-max-width)',
          margin: '0 auto',
          padding: 'var(--spacing-section-gap) 24px',
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Trajetória do estudante</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>Trajetória em construção.</p>
      </main>
    </div>
  )
}
