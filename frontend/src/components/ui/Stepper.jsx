import { Check, X } from 'lucide-react';

/**
 * Horizontal stepper. steps: [{key, label, status: 'complete'|'running'|'pending'|'failed'|'skipped'}]
 */
export default function Stepper({ steps }) {
  return (
    <ol className="flex w-full items-start overflow-x-auto pb-2" aria-label="Pipeline stages">
      {steps.map((s, i) => {
        const done = s.status === 'complete';
        const running = s.status === 'running';
        const failed = s.status === 'failed';
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className="flex min-w-[120px] flex-1 flex-col items-center text-center" aria-current={running ? 'step' : undefined}>
            <div className="flex w-full items-center">
              <div className={`h-0.5 flex-1 ${i === 0 ? 'opacity-0' : steps[i - 1].status === 'complete' ? 'bg-emerald-500/70' : 'bg-line'}`} />
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition
                  ${done ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300' : ''}
                  ${running ? 'border-blue-500 bg-blue-500/15 text-blue-300 shadow-[0_0_18px_rgba(59,130,246,0.45)]' : ''}
                  ${failed ? 'border-red-500 bg-red-500/15 text-red-300' : ''}
                  ${!done && !running && !failed ? 'border-line-strong bg-ink-900 text-slate-400' : ''}`}
              >
                {done ? <Check className="h-5 w-5" strokeWidth={3} aria-label="complete" /> : failed ? <X className="h-5 w-5" aria-label="failed" /> : i + 1}
              </div>
              <div className={`h-0.5 flex-1 ${last ? 'opacity-0' : done ? 'bg-emerald-500/70' : 'bg-line'}`} />
            </div>
            <div className={`mt-2 px-1 text-xs font-medium ${running ? 'text-blue-300' : done ? 'text-emerald-300' : failed ? 'text-red-300' : 'text-slate-400'}`}>
              {s.label}
            </div>
            {running && (
              <span className="mt-1.5 rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-300">
                Processing...
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
