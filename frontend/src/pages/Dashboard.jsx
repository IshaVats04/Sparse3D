import { Link } from 'react-router-dom';
import { ArrowRight, FlaskConical, Plus } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge, { StatusBadge } from '../components/ui/Badge';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback';
import { useAsync } from '../hooks/useAsync';
import { useHealth } from '../hooks/useHealth';
import { listJobs } from '../services/experimentService';
import { describeDataset } from '../utils/datasets';
import { formatDate } from '../utils/formatters';
import { formatMetric } from '../utils/metrics';

export default function Dashboard() {
  const { health, error: healthError } = useHealth();
  const { data, error, loading, reload } = useAsync(() => listJobs(), []);
  const jobs = (Array.isArray(data) ? [...data] : [])
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .slice(0, 6);
  const env = health && health.environment;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your sparse-view reconstruction experiments."
        actions={<Button variant="primary" icon={Plus} to="/upload">New Experiment</Button>}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Classical pipeline" bodyClassName="p-5">
          {env ? <Badge tone={env.colmap_available ? 'green' : 'red'} dot>{env.colmap_available ? 'COLMAP available' : 'COLMAP not found'}</Badge> : <span className="text-sm text-slate-400">{healthError ? 'Backend offline' : 'Checking...'}</span>}
        </Card>
        <Card title="Neural pipeline" bodyClassName="p-5">
          {env ? (
            <div className="space-y-1.5">
              <Badge tone={env.neural_available ? 'green' : 'amber'} dot>{env.neural_available ? 'PyTorch available' : 'Unavailable'}</Badge>
              {!env.neural_available && env.neural_reason && <p className="text-xs text-slate-400">{env.neural_reason}</p>}
            </div>
          ) : <span className="text-sm text-slate-400">{healthError ? 'Backend offline' : 'Checking...'}</span>}
        </Card>
        <Card title="Compute" bodyClassName="p-5">
          {env ? <p className="text-sm text-slate-200">Device: <span className="font-mono">{env.device || 'n/a'}</span> - Active jobs: <span className="font-mono">{env.active_jobs_count ?? 'n/a'}</span></p> : <span className="text-sm text-slate-400">{healthError ? healthError.message : 'Checking...'}</span>}
        </Card>
      </div>

      <Card title="Recent experiments" actions={<Link to="/history" className="inline-flex items-center gap-1 text-sm text-blue-300 hover:underline">All experiments <ArrowRight className="h-4 w-4" aria-hidden /></Link>} bodyClassName="p-0">
        {loading && !data ? (
          <div className="space-y-2 p-5"><Skeleton className="h-9" /><Skeleton className="h-9" /></div>
        ) : error ? (
          <div className="p-5"><ErrorBanner error={error} title="Could not load experiments" onRetry={reload} /></div>
        ) : jobs.length === 0 ? (
          <div className="p-5"><EmptyState icon={FlaskConical} title="No experiments yet" action={<Button variant="primary" to="/upload">Start new experiment</Button>}>Run your first reconstruction to see it here.</EmptyState></div>
        ) : (
          <ul className="divide-y divide-line-soft">
            {jobs.map((j) => (
              <li key={j.job_id}>
                <Link to={j.status === 'queued' || j.status === 'processing' ? `/processing/${j.job_id}` : `/viewer/${j.job_id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 hover:bg-ink-700/40">
                  <div>
                    <span className="font-mono text-sm text-white">{j.job_id}</span>
                    <span className="ml-3 text-sm text-slate-400">{j.project_name}</span>
                    <div className="text-xs text-slate-500">{formatDate(j.created_at)} - {j.num_views ?? j.image_count} views{j.dataset ? ` - ${describeDataset(j.dataset)}` : ''}</div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-slate-400">F-score <span className="font-mono text-slate-200">{formatMetric('f_score', j.f_score)}</span></span>
                    <StatusBadge status={j.status} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
