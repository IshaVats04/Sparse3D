import { Suspense, lazy } from 'react';
import { ArrowRight, BarChart3, Box, Camera, GitCompare, Layers, LineChart, Upload } from 'lucide-react';
import TopNav from '../components/layout/TopNav';
import Button from '../components/ui/Button';
import ErrorBoundary from '../components/ui/ErrorBoundary';
import Logo from '../components/ui/Logo';

const HeroScene = lazy(() => import('../components/viewer/HeroScene'));

const FEATURES = [
  { icon: GitCompare, title: 'Multiple Methods', sub: 'Classical + Neural' },
  { icon: Camera, title: '3-6 Views', sub: 'Sparse-view setup' },
  { icon: BarChart3, title: 'Quantitative Evaluation', sub: 'Chamfer, F-score, etc.' },
  { icon: Box, title: 'Interactive 3D Viewer', sub: 'Rotate, Zoom, Inspect' },
  { icon: LineChart, title: 'Research Insights', sub: 'Compare & Analyze' },
];

const STEPS = [
  { icon: Upload, title: 'Upload 3-6 views', text: 'Provide a handful of photographs of one object, or use the bundled sample set.' },
  { icon: Layers, title: 'Configure', text: 'Choose the method, view count, arrangement and quality; optionally add a ground-truth model.' },
  { icon: Box, title: 'Reconstruct', text: 'The classical pipeline (COLMAP + Open3D) and the neural pipeline run on the same views.' },
  { icon: BarChart3, title: 'Evaluate', text: 'Inspect the 3D results and compare metrics across methods, view counts and arrangements.' },
];

const THUMB_GRADIENTS = [
  'from-sky-500/40 to-indigo-700/50',
  'from-indigo-500/40 to-violet-700/50',
  'from-violet-500/40 to-fuchsia-700/40',
  'from-blue-500/40 to-cyan-700/40',
];

function VaseSilhouette({ tilt = 0 }) {
  return (
    <svg viewBox="0 0 40 52" className="h-full w-full" aria-hidden style={{ transform: `rotate(${tilt}deg)` }}>
      <path d="M14 4h12l-1 8c7 4 9 10 8 18-1 8-6 14-13 18h0c-7-4-12-10-13-18-1-8 1-14 8-18z" fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
    </svg>
  );
}

export default function Landing() {
  return (
    <div id="top" className="min-h-screen">
      <TopNav variant="landing" />

      <section className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 pb-10 pt-12 sm:px-6 lg:grid-cols-2 lg:pt-20">
        <div>
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-ink-800/70 px-3 py-1 text-xs text-slate-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden /> Sparse-view 3D reconstruction research
          </p>
          <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-6xl">
            Reconstruct the <span className="gradient-text">3D World</span> from Just a Few Images
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-300">
            A research platform for sparse-view 3D object reconstruction. Compare classical and neural methods, and evaluate the effect of
            view count and viewpoint arrangement with quantitative metrics.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button variant="primary" size="lg" to="/upload" iconRight={ArrowRight}>Start New Experiment</Button>
            <Button size="lg" href="#how-it-works">Learn More</Button>
          </div>
        </div>

        <div className="relative flex items-stretch gap-3">
          <div className="hidden flex-col gap-3 sm:flex" aria-hidden>
            {THUMB_GRADIENTS.map((g, i) => (
              <div key={g} className={`flex h-[84px] w-[84px] items-center justify-center rounded-lg border border-line bg-gradient-to-br p-2 ${g}`}>
                <VaseSilhouette tilt={(i - 1.5) * 8} />
              </div>
            ))}
          </div>
          <div className="relative h-[380px] flex-1 overflow-hidden rounded-2xl border border-line bg-ink-900/60 sm:h-[400px]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_55%,rgba(99,102,241,0.35),transparent_60%)]" aria-hidden />
            <ErrorBoundary fallback={() => <div className="flex h-full items-center justify-center text-sm text-slate-400">3D preview unavailable (WebGL not supported).</div>}>
              <Suspense fallback={<div className="flex h-full items-center justify-center text-sm text-slate-400">Loading 3D preview...</div>}>
                <HeroScene />
              </Suspense>
            </ErrorBoundary>
            <span className="absolute left-3 top-3 rounded-md bg-black/40 px-2 py-1 text-[11px] text-slate-300">Textured | Wireframe</span>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6" aria-label="Features">
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {FEATURES.map(({ icon: Icon, title, sub }) => (
            <li key={title} className="flex items-center gap-3 rounded-xl border border-line bg-ink-800/80 px-4 py-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-brand-blue">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <div>
                <div className="text-sm font-semibold text-white">{title}</div>
                <div className="text-xs text-slate-400">{sub}</div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section id="research" className="mx-auto max-w-7xl scroll-mt-20 px-4 pb-16 sm:px-6">
        <h2 className="text-2xl font-bold text-white">Research question</h2>
        <p className="mt-3 max-w-3xl text-slate-300">
          How does reconstruction quality change as the number of input views drops from six to three, and how much does the arrangement of those
          viewpoints matter? 3D RECON LAB runs a classical structure-from-motion pipeline and a neural pipeline on identical inputs, measures the
          results against a ground-truth model when one is available, and reports a metric as n/a when it cannot be measured.
        </p>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl scroll-mt-20 px-4 pb-20 sm:px-6">
        <h2 className="text-2xl font-bold text-white">How it works</h2>
        <ol className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="card p-5">
              <div className="mb-3 flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-gradient text-sm font-bold text-white">{i + 1}</span>
                <Icon className="h-5 w-5 text-slate-400" aria-hidden />
              </div>
              <h3 className="font-semibold text-white">{title}</h3>
              <p className="mt-1.5 text-sm text-slate-400">{text}</p>
            </li>
          ))}
        </ol>
        <div className="mt-8">
          <Button variant="primary" to="/upload" iconRight={ArrowRight}>Get Started</Button>
        </div>
      </section>

      <footer id="contact" className="border-t border-line-soft py-8">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 sm:px-6">
          <Logo />
          <p className="text-xs text-slate-500">Research prototype. See the project README for setup, backend and contact details.</p>
        </div>
      </footer>
    </div>
  );
}
