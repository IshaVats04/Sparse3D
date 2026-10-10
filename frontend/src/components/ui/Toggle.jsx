export default function Toggle({ checked, onChange, label, description, disabled = false, id }) {
  const inputId = id || `tg-${String(label).replace(/\W+/g, '-').toLowerCase()}`;
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <label htmlFor={inputId} className="min-w-0 cursor-pointer">
        <span className="block text-sm font-medium text-slate-100">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-slate-400">{description}</span>}
      </label>
      <button
        id={inputId}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50
          ${checked ? 'border-transparent bg-brand-gradient' : 'border-line bg-ink-600'}`}
      >
        <span
          className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : ''}`}
        />
      </button>
    </div>
  );
}
