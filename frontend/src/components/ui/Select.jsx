import { ChevronDown } from 'lucide-react';
import { useId } from 'react';

/**
 * Native select with label + helper text. `options`: [{value, label, disabled?}] or strings.
 */
export default function Select({ label, value, onChange, options, helper, disabled = false, className = '', id, ...rest }) {
  const auto = useId();
  const selectId = id || auto;
  return (
    <div className={className}>
      {label && <label htmlFor={selectId} className="label">{label}</label>}
      <div className="relative">
        <select
          id={selectId}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="field appearance-none pr-9 disabled:cursor-not-allowed disabled:opacity-60"
          {...rest}
        >
          {options.map((o) => {
            const opt = typeof o === 'object' ? o : { value: o, label: o };
            return (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            );
          })}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
      </div>
      {helper && <p className="mt-1.5 text-xs text-slate-400">{helper}</p>}
    </div>
  );
}
