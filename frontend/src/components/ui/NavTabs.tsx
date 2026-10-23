import { NavLink } from 'react-router-dom'
import { Icon } from './Icon'
import { INDICATORS, type Indicator } from './indicators'

/**
 * Abas em pílula que navegam entre rotas irmãs (ex.: os 4 tipos de
 * Lançamento). Como cada aba é uma rota, usa `<nav>` com links e
 * `aria-current="page"`, não `role="tablist"`.
 */
export function NavTabs({
  label,
  items,
}: {
  label: string
  items: { to: string; label: string; indicator?: Indicator }[]
}) {
  return (
    <nav aria-label={label}>
      <ul className="sz-tabs" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {items.map((item) => {
          const info = item.indicator ? INDICATORS[item.indicator] : undefined
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className="sz-tab"
                aria-selected={undefined}
                style={({ isActive }) =>
                  isActive
                    ? { borderColor: 'var(--action)', background: 'var(--action-tint)', boxShadow: 'inset 0 0 0 1px var(--action)' }
                    : undefined
                }
              >
                {info && <Icon name={info.icon} size={18} style={{ color: info.color }} />}
                <span>{item.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
