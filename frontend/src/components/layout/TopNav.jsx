import { Link, NavLink } from 'react-router-dom';
import { Menu, Server } from 'lucide-react';
import Logo from '../ui/Logo';
import Button from '../ui/Button';
import { useHealth } from '../../hooks/useHealth';
import { isMock } from '../../services/api';

export function BackendPill() {
  const { health, error, loading } = useHealth();
  let tone = 'bg-slate-500';
  let text = 'Checking backend';
  if (isMock()) { tone = 'bg-violet-400'; text = 'Mock data'; }
  else if (!loading && error) { tone = 'bg-red-500'; text = 'Backend offline'; }
  else if (health) { tone = 'bg-emerald-400'; text = health.status === 'healthy' ? 'Backend online' : `Backend ${health.status}`; }
  return (
    <Link
      to="/settings"
      title={error ? error.message : 'Open settings'}
      className="inline-flex items-center gap-2 rounded-full border border-line bg-ink-800 px-3 py-1.5 text-xs text-slate-300 hover:border-line-strong"
    >
      <span className={`h-2 w-2 rounded-full ${tone} ${loading ? 'animate-pulseDot' : ''}`} aria-hidden />
      <Server className="h-3.5 w-3.5 text-slate-400" aria-hidden />
      {text}
    </Link>
  );
}

const LANDING_LINKS = [
  { label: 'Home', href: '#top' },
  { label: 'Research', href: '#research' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Benchmarks', to: '/analysis' },
  { label: 'Contact', href: '#contact' },
];

/**
 * variant="landing": marketing navigation. variant="app": slim bar above authenticated pages.
 */
export default function TopNav({ variant = 'app', onMenu }) {
  if (variant === 'landing') {
    return (
      <header className="sticky top-0 z-30 border-b border-line-soft bg-ink-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {LANDING_LINKS.map((l) => (l.to ? (
              <NavLink key={l.label} to={l.to} className="rounded-md px-3 py-2 text-sm text-slate-300 hover:text-white">{l.label}</NavLink>
            ) : (
              <a key={l.label} href={l.href} className="rounded-md px-3 py-2 text-sm text-slate-300 hover:text-white">{l.label}</a>
            )))}
          </nav>
          <Button variant="primary" to="/upload">Get Started</Button>
        </div>
      </header>
    );
  }
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line-soft bg-ink-950/80 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open menu"
          className="rounded-lg border border-line p-2 text-slate-300 hover:bg-ink-700 lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Logo className="lg:hidden" />
      </div>
      <div className="flex items-center gap-3">
        <BackendPill />
        <Button variant="primary" size="sm" to="/upload" className="hidden sm:inline-flex">New Experiment</Button>
      </div>
    </header>
  );
}
