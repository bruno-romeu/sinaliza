import { Header } from '../components/Header'

/**
 * Placeholder authenticated shell — full content (mudanças recentes,
 * acompanhamentos em andamento) is Epic 3 Story 3.3, out of scope here.
 */
export function Home() {
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
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px' }}>Home</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Mudanças recentes e acompanhamentos em andamento chegam aqui em uma próxima história.
        </p>
      </main>
    </div>
  )
}
