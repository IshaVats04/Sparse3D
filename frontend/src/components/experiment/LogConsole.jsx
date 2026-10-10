import { useEffect, useRef } from 'react';

function lineClass(line) {
  if (/\[ERROR\]|\bERROR\b/.test(line)) return 'text-red-300';
  if (/\[WARN(ING)?\]/.test(line)) return 'text-amber-300';
  if (/\[SUCCESS\]|\[DONE\]/.test(line)) return 'text-emerald-300';
  return 'text-slate-300';
}

/** Monospace console that auto-scrolls to the newest line unless the user scrolled up. */
export default function LogConsole({ logs = [], height = 320 }) {
  const ref = useRef(null);
  const stick = useRef(true);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  };

  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [logs.length]);

  return (
    <div
      ref={ref}
      onScroll={onScroll}
      role="log"
      aria-live="off"
      tabIndex={0}
      aria-label="Live logs"
      className="overflow-y-auto rounded-lg border border-line bg-[#070a18] p-3 font-mono text-xs leading-relaxed"
      style={{ height }}
    >
      {logs.length === 0 ? (
        <span className="text-slate-500">Waiting for log output...</span>
      ) : (
        logs.map((l, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <div key={i} className={`whitespace-pre-wrap break-words ${lineClass(l)}`}>{l}</div>
        ))
      )}
    </div>
  );
}
