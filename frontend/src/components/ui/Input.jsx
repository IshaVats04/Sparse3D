import { useId } from 'react';

export default function Input({ label, helper, error, className = '', id, ...rest }) {
  const auto = useId();
  const inputId = id || auto;
  return (
    <div className={className}>
      {label && <label htmlFor={inputId} className="label">{label}</label>}
      <input id={inputId} className={`field ${error ? 'border-red-500/60' : ''}`} aria-invalid={!!error} {...rest} />
      {error ? <p className="mt-1.5 text-xs text-red-300">{error}</p> : helper ? <p className="mt-1.5 text-xs text-slate-400">{helper}</p> : null}
    </div>
  );
}
