import { Suspense, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNav from './TopNav';
import { PageSkeleton } from '../ui/Feedback';
import ErrorBoundary from '../ui/ErrorBoundary';
import { isMock } from '../../services/api';

export default function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    setMenuOpen(false);
    if (!loc.hash) window.scrollTo(0, 0);
  }, [loc.pathname, loc.hash]);

  return (
    <div className="flex min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav onMenu={() => setMenuOpen(true)} />
        {isMock() && (
          <div className="border-b border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-center text-xs text-violet-200 sm:px-6">
            Mock mode: sample data from the built-in mock layer, no backend calls are made.{' '}
            <a className="underline" href={`${window.location.pathname}?mock=0`}>Turn off</a>
          </div>
        )}
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <ErrorBoundary resetKey={loc.pathname}>
            <Suspense fallback={<PageSkeleton />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
