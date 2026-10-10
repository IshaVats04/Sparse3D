import { Check } from 'lucide-react';

export default function Checkbox({ checked, onChange, label, description, disabled = false, id }) {
  const inputId = id || `cb-${String(label).replace(/\W+/g, '-').toLowerCase()}`;
  return (
    <label htmlFor={inputId} className={`flex items-start gap-3 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
      <span className="relative mt-0.5 inline-flex h-5 w-5 shrink-0">
        <input
          id={inputId}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          className="peer absolute inset-0 h-5 w-5 cursor-pointer opacity-0"
        />
        <span className="flex h-5 w-5 items-center justify-center rounded-md border border-line-strong bg-ink-900 text-white transition peer-checked:border-transparent peer-checked:bg-brand-gradient peer-focus-visible:ring-2 peer-focus-visible:ring-blue-400">
          {checked && <Check className="h-3.5 w-3.5" strokeWidth={3} aria-hidden />}
        </span>
      </span>
      <span className="min-w-0">
        <span className="block text-sm text-slate-100">{label}</span>
        {description && <span className="block text-xs text-slate-400">{description}</span>}
      </span>
    </label>
  );
}
