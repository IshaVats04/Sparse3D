import { STATUS_META } from '../../utils/constants';

const TONES = {
  green: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  amber: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  red: 'border-red-500/30 bg-red-500/10 text-red-300',
  blue: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  violet: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
  slate: 'border-slate-500/30 bg-slate-500/10 text-slate-300',
};

export default function Badge({ tone = 'slate', children, dot = false, className = '', ...rest }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone] || TONES.slate} ${className}`}
      {...rest}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

/** Badge for a job status string (queued/processing/completed/...). */
export function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status || 'Unknown', tone: 'slate' };
  return (
    <Badge tone={meta.tone} dot>
      {meta.label}
    </Badge>
  );
}

/** "Colab GPU" badge for jobs that ran on the remote worker (job.execution.target === 'remote'). */
export function RemoteBadge({ job }) {
  if (!job || !job.execution || job.execution.target !== 'remote') return null;
  return (
    <Badge tone="violet" title="This experiment ran on the Colab GPU worker">
      Colab GPU
    </Badge>
  );
}
