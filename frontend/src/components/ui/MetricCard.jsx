import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { formatSigned } from '../../utils/formatters';

/** Small % delta badge. `good`: true (green), false (red), null (neutral). */
export function DeltaBadge({ pct, good, title }) {
  if (pct === null || pct === undefined) return null;
  const Icon = pct === 0 ? Minus : pct > 0 ? ArrowUpRight : ArrowDownRight;
  const tone = good === true
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
    : good === false
      ? 'border-red-500/30 bg-red-500/10 text-red-300'
      : 'border-slate-500/30 bg-slate-500/10 text-slate-300';
  return (
    <span title={title} className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}>
      <Icon className="h-3 w-3" aria-hidden />
      {formatSigned(pct)}
    </span>
  );
}

/**
 * Metric card. `values`: [{label, text, color?, best?, na?, title?}].
 * `delta`: {pct, good, title} optional badge.
 */
export default function MetricCard({ label, hint, values, delta, icon: Icon }) {
  return (
    <div className="rounded-xl border border-line bg-ink-800/90 p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-white">{label}</div>
          {hint && <div className="text-xs text-slate-400">({hint})</div>}
        </div>
        {Icon && <Icon className="h-4 w-4 text-slate-500" aria-hidden />}
      </div>
      <div className="mt-3 space-y-1.5">
        {values.map((v) => (
          <div key={v.label || v.text} className="flex items-baseline justify-between gap-3">
            {v.label && (
              <span className="flex items-center gap-1.5 text-xs text-slate-400">
                {v.color && <span className="h-2 w-2 rounded-full" style={{ background: v.color }} aria-hidden />}
                {v.label}
              </span>
            )}
            <span
              title={v.title}
              className={`font-mono text-xl font-semibold ${v.na ? 'text-slate-500' : v.best ? 'text-emerald-400' : 'text-white'}`}
            >
              {v.text}
            </span>
          </div>
        ))}
      </div>
      {delta && delta.pct !== null && delta.pct !== undefined && (
        <div className="mt-3">
          <DeltaBadge {...delta} />
        </div>
      )}
    </div>
  );
}

/** Compact tile used under viewers. */
export function MetricTile({ label, arrow, text, best, na, title }) {
  return (
    <div className="rounded-lg border border-line bg-ink-900/80 px-3 py-2.5" title={title}>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">
        {label} {arrow && <span aria-hidden>{arrow}</span>}
      </div>
      <div className={`mt-0.5 font-mono text-base font-semibold ${na ? 'text-slate-500' : best ? 'text-emerald-400' : 'text-white'}`}>
        {text}
      </div>
    </div>
  );
}
