import { useEffect, useRef, useState } from 'react';
import { ChevronDown, SlidersHorizontal } from 'lucide-react';
import Checkbox from '../ui/Checkbox';

export const BACKGROUNDS = {
  dark: { label: 'Dark', color: '#05070f' },
  navy: { label: 'Navy', color: '#0b1030' },
  grey: { label: 'Grey', color: '#252a3a' },
  light: { label: 'Light', color: '#e6e9f2' },
};

export const ORIENTATIONS = {
  'y-up': { label: 'Y up (default)', rotation: [0, 0, 0] },
  'z-up': { label: 'Z up', rotation: [-Math.PI / 2, 0, 0] },
  'y-down': { label: 'Y down (COLMAP)', rotation: [Math.PI, 0, 0] },
};

export const DEFAULT_VIEW_OPTIONS = {
  background: 'dark',
  pointSize: 3,
  showCameras: true,
  showAxes: false,
  autoRotate: false,
  orientation: 'y-up',
};

export default function ViewOptionsMenu({ options, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const set = (patch) => onChange({ ...options, ...patch });

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-lg border border-line bg-ink-800 px-3.5 py-2 text-sm text-slate-100 hover:border-line-strong"
      >
        <SlidersHorizontal className="h-4 w-4" aria-hidden />
        View Options
        <ChevronDown className={`h-4 w-4 transition ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 space-y-4 rounded-xl border border-line bg-ink-800 p-4 shadow-2xl">
          <div>
            <label className="label" htmlFor="vo-bg">Background</label>
            <select id="vo-bg" className="field" value={options.background} onChange={(e) => set({ background: e.target.value })}>
              {Object.entries(BACKGROUNDS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="vo-ps">Point size ({options.pointSize})</label>
            <input
              id="vo-ps"
              type="range"
              min="1"
              max="10"
              step="1"
              value={options.pointSize}
              onChange={(e) => set({ pointSize: Number(e.target.value) })}
              className="w-full"
            />
          </div>
          <div>
            <label className="label" htmlFor="vo-or">Up axis</label>
            <select id="vo-or" className="field" value={options.orientation} onChange={(e) => set({ orientation: e.target.value })}>
              {Object.entries(ORIENTATIONS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div className="space-y-2.5">
            <Checkbox label="Show cameras" checked={options.showCameras} onChange={(v) => set({ showCameras: v })} id="vo-cam" />
            <Checkbox label="Show axes" checked={options.showAxes} onChange={(v) => set({ showAxes: v })} id="vo-axes" />
            <Checkbox label="Auto-rotate" checked={options.autoRotate} onChange={(v) => set({ autoRotate: v })} id="vo-rot" />
          </div>
        </div>
      )}
    </div>
  );
}
