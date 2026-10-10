import { NavLink, useLocation } from 'react-router-dom';
import {
  BarChart3, Box, Cpu, FlaskConical, GitCompare, History, ImagePlus, LayoutDashboard, LineChart, Settings,
  SlidersHorizontal, X,
} from 'lucide-react';
import Logo from '../ui/Logo';
import { NAV_ITEMS } from '../../utils/constants';
import { useWizard } from '../../hooks/useUpload';

const ICONS = {
  LayoutDashboard, FlaskConical, ImagePlus, SlidersHorizontal, Cpu, Box, BarChart3, GitCompare, LineChart, History, Settings,
};

function isActive(item, loc) {
  const path = item.to.split('#')[0];
  if (item.id === 'history') return loc.pathname === '/history' && loc.hash === '#downloads';
  if (item.id === 'experiments') return loc.pathname === '/history' && loc.hash !== '#downloads';
  return loc.pathname === path || loc.pathname.startsWith(`${path}/`);
}

export default function Sidebar({ open, onClose }) {
  const loc = useLocation();
  const { jobId } = useWizard();

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} aria-hidden />}
      <aside
        aria-label="Primary"
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-ink-900/95 backdrop-blur transition-transform duration-200
          lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Logo />
          <button type="button" onClick={onClose} aria-label="Close menu" className="rounded p-1 text-slate-400 hover:text-white lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
          {NAV_ITEMS.map((item) => {
            const Icon = ICONS[item.icon];
            const to = item.job && jobId ? `${item.to}/${jobId}` : item.to;
            const active = isActive(item, loc);
            return (
              <NavLink
                key={item.id}
                to={to}
                onClick={onClose}
                aria-current={active ? 'page' : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition
                  ${active ? 'bg-brand-blue text-white shadow-[0_4px_16px_rgba(59,130,246,0.35)]' : 'text-slate-400 hover:bg-ink-700 hover:text-white'}`}
              >
                <Icon className="h-[18px] w-[18px]" aria-hidden />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        {jobId && (
          <div className="mx-3 mb-4 rounded-lg border border-line bg-ink-800 px-3 py-2.5 text-xs text-slate-400">
            <div className="uppercase tracking-wide">Current experiment</div>
            <div className="mt-0.5 truncate font-mono text-sm text-slate-200">{jobId}</div>
          </div>
        )}
      </aside>
    </>
  );
}
