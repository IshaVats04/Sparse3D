import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react';

const ICONS = {
  ok: { Icon: CheckCircle2, cls: 'text-emerald-400' },
  warn: { Icon: AlertTriangle, cls: 'text-amber-400' },
  error: { Icon: XCircle, cls: 'text-red-400' },
};

/** Messages from POST /api/validate. */
export default function ValidationPanel({ validation, validating }) {
  if (validating && !validation) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Checking images...
      </div>
    );
  }
  if (!validation) return null;
  const messages = validation.messages || [];
  const pairs = (validation.pairs || []).filter((p) => p.warning);
  const hasWarn = messages.some((m) => m.level === 'warn') || pairs.length > 0;
  return (
    <div className="space-y-3" aria-live="polite">
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        Image checks
        {validating && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" aria-label="Re-checking" />}
      </div>
      <ul className="space-y-1.5">
        {messages.map((m, i) => {
          const { Icon, cls } = ICONS[m.level] || ICONS.ok;
          return (
            <li key={`${i}-${m.text}`} className="flex items-start gap-2 text-sm text-slate-200">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} aria-hidden />
              <span>{m.text}</span>
            </li>
          );
        })}
        {pairs.map((p) => (
          <li key={`${p.a}-${p.b}`} className="flex items-start gap-2 text-sm text-slate-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
            <span>
              Low overlap between {p.a} and {p.b}
              {p.overlap_pct !== null && p.overlap_pct !== undefined ? ` (${Number(p.overlap_pct).toFixed(1)}% overlap, ${p.matches} matches)` : ''}
            </span>
          </li>
        ))}
        {messages.length === 0 && pairs.length === 0 && (
          <li className="text-sm text-slate-400">No messages from the validator.</li>
        )}
      </ul>
      {hasWarn && validation.can_proceed && (
        <p className="text-sm font-medium text-amber-300">Proceed with reconstruction? Warnings do not block you; results may be weaker.</p>
      )}
      {!validation.can_proceed && (
        <p className="text-sm font-medium text-red-300">Fix the errors above (remove or replace the affected images) to continue.</p>
      )}
    </div>
  );
}
