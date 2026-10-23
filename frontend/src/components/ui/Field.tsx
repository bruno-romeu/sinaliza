import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { Icon, type IconName } from './Icon'

function describedBy(hintId: string, errorId: string, hint?: ReactNode, error?: ReactNode) {
  return [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined
}

function Messages({ hintId, errorId, hint, error }: { hintId: string; errorId: string; hint?: ReactNode; error?: ReactNode }) {
  return (
    <>
      {hint && (
        <p className="sz-field-hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="sz-field-error" id={errorId} role="alert">
          <Icon name="info" size={16} />
          {error}
        </p>
      )}
    </>
  )
}

/** Campo de texto com label sempre visível; `hint` e `error` ligados por `aria-describedby`. */
export function TextField({
  label,
  hint,
  error,
  icon,
  id,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; hint?: ReactNode; error?: ReactNode; icon?: IconName }) {
  const auto = useId()
  const fieldId = id ?? auto
  const hintId = `${fieldId}-hint`
  const errorId = `${fieldId}-error`
  return (
    <div className={['sz-field', error ? 'sz-field-invalid' : null, className].filter(Boolean).join(' ')}>
      <label className="sz-field-label" htmlFor={fieldId}>
        {label}
      </label>
      <div className="sz-field-box">
        {icon && <Icon name={icon} size={20} />}
        <input
          id={fieldId}
          type="text"
          aria-describedby={describedBy(hintId, errorId, hint, error)}
          aria-invalid={error ? true : undefined}
          {...rest}
        />
      </div>
      <Messages hintId={hintId} errorId={errorId} hint={hint} error={error} />
    </div>
  )
}

export function TextAreaField({
  label,
  hint,
  error,
  id,
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: ReactNode; hint?: ReactNode; error?: ReactNode }) {
  const auto = useId()
  const fieldId = id ?? auto
  const hintId = `${fieldId}-hint`
  const errorId = `${fieldId}-error`
  return (
    <div className={['sz-field', error ? 'sz-field-invalid' : null, className].filter(Boolean).join(' ')}>
      <label className="sz-field-label" htmlFor={fieldId}>
        {label}
      </label>
      <div className="sz-field-box">
        <textarea
          id={fieldId}
          aria-describedby={describedBy(hintId, errorId, hint, error)}
          aria-invalid={error ? true : undefined}
          {...rest}
        />
      </div>
      <Messages hintId={hintId} errorId={errorId} hint={hint} error={error} />
    </div>
  )
}

/** `<select>` nativo estilizado: herda a navegação por teclado do navegador. */
export function SelectField({
  label,
  hint,
  error,
  id,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label: ReactNode; hint?: ReactNode; error?: ReactNode }) {
  const auto = useId()
  const fieldId = id ?? auto
  const hintId = `${fieldId}-hint`
  const errorId = `${fieldId}-error`
  return (
    <div className={['sz-field', error ? 'sz-field-invalid' : null, className].filter(Boolean).join(' ')}>
      <label className="sz-field-label" htmlFor={fieldId}>
        {label}
      </label>
      <div className="sz-field-box">
        <select id={fieldId} aria-describedby={describedBy(hintId, errorId, hint, error)} {...rest}>
          {children}
        </select>
        <Icon name="chevron" size={18} className="sz-select-caret" />
      </div>
      <Messages hintId={hintId} errorId={errorId} hint={hint} error={error} />
    </div>
  )
}
