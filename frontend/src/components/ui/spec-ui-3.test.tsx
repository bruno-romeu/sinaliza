import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { EvidenceCard } from './EvidenceCard'
import { TrajectoryChart } from './TrajectoryChart'

const points = [
  { key: 'p1', label: '1º Bimestre', value: 0.9 },
  { key: 'p2', label: '2º Bimestre', value: 0.88 },
  { key: 'p3', label: '3º Bimestre', value: 0.6 },
]

function chart(band: { low: number; high: number } | null) {
  return (
    <TrajectoryChart
      summary="Gráfico"
      points={points}
      band={band}
      bandLabel="Faixa habitual"
      changeIndex={2}
      format={(value) => String(value)}
    />
  )
}

describe('TrajectoryChart (spec-ui-3)', () => {
  it('says "Saiu da faixa" only when the change point is outside the band', () => {
    const { container, rerender } = render(chart({ low: 0.85, high: 0.95 }))
    expect(container.querySelector('.cp-label')?.textContent).toBe('Saiu da faixa')

    rerender(chart({ low: 0.5, high: 0.95 }))
    expect(container.querySelector('.cp-label')?.textContent).toBe('Mudança detectada')

    rerender(chart(null))
    expect(container.querySelector('.cp-label')?.textContent).toBe('Mudança detectada')
  })
})

describe('EvidenceCard (spec-ui-3)', () => {
  const evidence = Array.from({ length: 8 }, (_, index) => ({
    source_type: 'ATTENDANCE_RECORD' as const,
    description: `Falta não justificada em ${String(index + 1).padStart(2, '0')}/09/2026`,
    date: `2026-09-${String(index + 1).padStart(2, '0')}`,
  }))

  it('shows the first 5 records and a button to see all of them', () => {
    render(
      <MemoryRouter>
        <EvidenceCard id="ev" title="Queda de frequência" evidence={evidence} />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('listitem')).toHaveLength(5)
    const toggle = screen.getByRole('button', { name: 'Ver todos os 8 registros' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(toggle)
    expect(screen.getAllByRole('listitem')).toHaveLength(8)
    expect(screen.getByRole('button', { name: 'Mostrar menos' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('has no toggle with 5 records or fewer', () => {
    render(
      <MemoryRouter>
        <EvidenceCard title="Queda de frequência" evidence={evidence.slice(0, 5)} />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('listitem')).toHaveLength(5)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
