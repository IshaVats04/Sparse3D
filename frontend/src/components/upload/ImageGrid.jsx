import { useRef } from 'react';
import { AlertTriangle, CheckCircle2, FileImage, Plus, XCircle, X } from 'lucide-react';
import { IMAGE_ACCEPT } from '../../utils/constants';
import { apiUrl } from '../../services/api';
import { truncateMiddle } from '../../utils/formatters';

const STATUS = {
  ok: { Icon: CheckCircle2, cls: 'bg-emerald-500/90 text-white', label: 'OK' },
  warn: { Icon: AlertTriangle, cls: 'bg-amber-500/90 text-ink-950', label: 'Warning' },
  error: { Icon: XCircle, cls: 'bg-red-500/90 text-white', label: 'Error' },
};

/**
 * items: [{key, name, url, isRaw, status?: 'ok'|'warn'|'error', issues?: string[]}]
 * onRemove(key) shows an x button; onAdd(FileList) shows the dashed "+ Add Image" tile.
 */
export default function ImageGrid({ items, onRemove, onAdd, max = 6 }) {
  const inputRef = useRef(null);
  const remaining = max - items.length;
  return (
    <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {items.map((it) => {
        const st = it.status ? STATUS[it.status] : null;
        return (
          <li key={it.key} className="group">
            <div className="relative aspect-square overflow-hidden rounded-lg border border-line bg-ink-900">
              {it.url ? (
                <img src={apiUrl(it.url)} alt={it.name} className="h-full w-full object-cover" loading="lazy" />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-slate-500">
                  <FileImage className="h-8 w-8" aria-hidden />
                  <span className="text-[10px] uppercase">No preview</span>
                </div>
              )}
              {st && (
                <span
                  title={it.issues && it.issues.length ? it.issues.join('; ') : st.label}
                  className={`absolute bottom-1.5 left-1.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${st.cls}`}
                >
                  <st.Icon className="h-3 w-3" aria-hidden />
                  {st.label}
                </span>
              )}
              {onRemove && (
                <button
                  type="button"
                  onClick={() => onRemove(it.key)}
                  aria-label={`Remove ${it.name}`}
                  className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 text-white opacity-90 transition hover:bg-red-500"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <div className="mt-1.5 truncate text-xs text-slate-300" title={it.name}>{truncateMiddle(it.name, 24)}</div>
            {it.issues && it.issues.length > 0 && (
              <div className="mt-0.5 text-[11px] leading-snug text-amber-300">{it.issues.join('; ')}</div>
            )}
          </li>
        );
      })}
      {onAdd && remaining > 0 && (
        <li>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-line-strong text-slate-400 transition hover:border-brand-blue hover:text-white"
          >
            <Plus className="h-6 w-6" aria-hidden />
            <span className="text-xs">Add Image ({remaining} more)</span>
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={IMAGE_ACCEPT}
            className="hidden"
            tabIndex={-1}
            onChange={(e) => { onAdd(e.target.files); e.target.value = ''; }}
          />
        </li>
      )}
    </ul>
  );
}
