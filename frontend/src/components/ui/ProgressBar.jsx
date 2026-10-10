export default function ProgressBar({ value = 0, label }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2.5 flex-1 overflow-hidden rounded-full bg-ink-600"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(v)}
        aria-label={label || 'Progress'}
      >
        <div className="h-full rounded-full bg-brand-gradient transition-all duration-500" style={{ width: `${v}%` }} />
      </div>
      <span className="w-12 text-right font-mono text-sm text-slate-200">{Math.round(v)}%</span>
    </div>
  );
}
