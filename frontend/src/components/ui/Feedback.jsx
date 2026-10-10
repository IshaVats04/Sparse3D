import { AlertCircle, AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, X } from 'lucide-react';
import Button from './Button';

const TONES = {
  error: { cls: 'border-red-500/40 bg-red-500/10 text-red-200', Icon: AlertCircle },
  warn: { cls: 'border-amber-500/40 bg-amber-500/10 text-amber-200', Icon: AlertTriangle },
  ok: { cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200', Icon: CheckCircle2 },
  info: { cls: 'border-blue-500/40 bg-blue-500/10 text-blue-200', Icon: Info },
};

/** Inline alert. */
export function Alert({ tone = 'info', title, children, onRetry, onDismiss, className = '' }) {
  const { cls, Icon } = TONES[tone] || TONES.info;
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${cls} ${className}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <div className="font-medium">{title}</div>}
        {children && <div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div>}
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" icon={RefreshCw} onClick={onRetry}>Retry</Button>
      )}
      {onDismiss && (
        <button type="button" aria-label="Dismiss" onClick={onDismiss} className="rounded p-1 opacity-70 hover:opacity-100">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

/** Error banner for an Error/ApiError (or string). */
export function ErrorBanner({ error, title = 'Something went wrong', onRetry, className }) {
  if (!error) return null;
  const msg = typeof error === 'string' ? error : error.message || String(error);
  return <Alert tone="error" title={title} onRetry={onRetry} className={className}>{msg}</Alert>;
}

export function EmptyState({ icon: Icon, title, children, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-12 text-center ${className}`}>
      {Icon && (
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ink-700 text-slate-400">
          <Icon className="h-6 w-6" aria-hidden />
        </div>
      )}
      <h3 className="text-base font-semibold text-white">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-slate-400">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function Spinner({ label = 'Loading', className = '' }) {
  return (
    <div role="status" className={`flex items-center gap-2 text-sm text-slate-400 ${className}`}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}
