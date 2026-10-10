import { useRef } from 'react';

/** Accessible tab strip. `tabs`: [{id, label}] — content is rendered by the caller. */
export default function Tabs({ tabs, value, onChange, className = '', idPrefix = 'tab' }) {
  const refs = useRef([]);
  const onKeyDown = (e, i) => {
    let next = null;
    if (e.key === 'ArrowRight') next = (i + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
    if (next !== null) {
      e.preventDefault();
      onChange(tabs[next].id);
      refs.current[next]?.focus();
    }
  };
  return (
    <div role="tablist" className={`flex gap-1 overflow-x-auto border-b border-line ${className}`}>
      {tabs.map((t, i) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => { refs.current[i] = el; }}
            role="tab"
            id={`${idPrefix}-${t.id}`}
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onKeyDown={(e) => onKeyDown(e, i)}
            onClick={() => onChange(t.id)}
            className={`relative -mb-px whitespace-nowrap px-4 py-2.5 text-sm font-medium transition
              ${active ? 'text-white' : 'text-slate-400 hover:text-slate-200'}`}
          >
            {t.label}
            {active && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-brand-gradient" />}
          </button>
        );
      })}
    </div>
  );
}
