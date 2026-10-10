import { Suspense, lazy } from 'react';
import { Route, Routes } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import ErrorBoundary from './components/ui/ErrorBoundary';
import { PageSkeleton } from './components/ui/Feedback';
import Button from './components/ui/Button';
import { HealthProvider } from './hooks/useHealth';
import { WizardProvider } from './hooks/useUpload';

const Landing = lazy(() => import('./pages/Landing'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Upload = lazy(() => import('./pages/Upload'));
const Configuration = lazy(() => import('./pages/Configuration'));
const Processing = lazy(() => import('./pages/Processing'));
const Viewer3D = lazy(() => import('./pages/Viewer3D'));
const Evaluation = lazy(() => import('./pages/Evaluation'));
const Comparison = lazy(() => import('./pages/Comparison'));
const Analysis = lazy(() => import('./pages/Analysis'));
const History = lazy(() => import('./pages/History'));
const Settings = lazy(() => import('./pages/Settings'));

function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center text-center">
      <h1 className="text-5xl font-bold gradient-text">404</h1>
      <p className="mt-3 text-slate-300">That page does not exist.</p>
      <Button variant="primary" to="/" className="mt-6">Back to home</Button>
    </div>
  );
}

export default function App() {
  return (
    <HealthProvider>
      <WizardProvider>
        <ErrorBoundary title="The application hit an unexpected error">
          <Suspense fallback={<div className="p-8"><PageSkeleton /></div>}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route element={<AppShell />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/configuration" element={<Configuration />} />
                <Route path="/processing/:jobId?" element={<Processing />} />
                <Route path="/viewer/:jobId?" element={<Viewer3D />} />
                <Route path="/evaluation/:jobId?" element={<Evaluation />} />
                <Route path="/comparison/:jobId?" element={<Comparison />} />
                <Route path="/analysis" element={<Analysis />} />
                <Route path="/history" element={<History />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </WizardProvider>
    </HealthProvider>
  );
}

