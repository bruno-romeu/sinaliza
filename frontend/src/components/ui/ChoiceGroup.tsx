import { useId, type ReactNode } from 'react'

/** Opções exclusivas em botões segmentados (`<input type="radio">` em `<fieldset>`). Nenhuma opção ganha cor de estado. */
export function ChoiceGroup<T extends string>({
  label,
  hideLabel = false,
  value,
  onChange,
  options,
  disabled,
  name,
}: {
  label: ReactNode
  hideLabel?: boolean
  value: T
  onChange: (value: T) => void
  options: { value: T; label: string }[]
  disabled?: boolean
  name?: string
}) {
  const auto = useId()
  const groupName = name ?? auto
  return (
    <fieldset className="sz-choice" disabled={disabled}>
      <legend className={hideLabel ? 'sz-sr' : undefined}>{label}</legend>
      <div className="sz-choice-opts">
        {options.map((option) => (
          <label key={option.value} className="sz-choice-opt">
            <input
              type="radio"
              name={groupName}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
