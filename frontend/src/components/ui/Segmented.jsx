/** Segmented control (radio group). options: [{value, label, disabled?, title?}] */
export default function Segmented({ options, value, onChange, label, className = '' }) {
  return (
    <div role="radiogroup" aria-label={label} className={`inline-flex rounded-lg border border-line bg-ink-900 p-0.5 ${className}`}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={o.disabled}
            title={o.title}
            onClick={() => onChange(o.value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40
              ${active ? 'bg-brand-blue text-white shadow' : 'text-slate-300 hover:bg-ink-700'}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
