import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Box } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Tabs from '../components/ui/Tabs';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { RemoteBadge, StatusBadge } from '../components/ui/Badge';
import { Alert, ErrorBanner, Skeleton } from '../components/ui/Feedback';
import MetricGrid from '../components/experiment/MetricGrid';
import {
  ArrangementChart, MetricSelect, NoAnalysisData, QuantTable, ViewCountChart,
} from '../components/charts/AnalysisViews';
import { useActiveJobId } from '../hooks/useUpload';
import { useExperiment } from '../hooks/useExperiment';
import { useAnalysis } from '../hooks/useAnalysis';
import { useAsync } from '../hooks/useAsync';
import { listJobs } from '../services/experimentService';
import { jobSubtitle } from '../utils/datasets';
import { METHOD_SHORT, SUCCESS_STATUSES } from '../utils/constants';
import { formatMetric } from '../utils/metrics';
import { titleCase } from '../utils/formatters';

const TABS = [
  { id: 'methods', label: 'Classical vs Neural' },
  { id: 'views', label: 'View Count Analysis' },
  { id: 'arrangement', label: 'View Arrangement Analysis' },
];

function ResultsStrip({ groupId }) {
  const { data, error, loading, reload } = useAsync(() => listJobs(), []);
  const jobs = useMemo(() => {
    const list = Array.isArray(data) ? data : [];
    return list
      .filter((j) => SUCCESS_STATUSES.includes(j.status) && (!groupId || j.group_id === groupId))
      .sort((a, b) => (a.num_views - b.num_views) || String(b.created_at).localeCompare(String(a.created_at)))
      .slice(0, 12);
  }, [data, groupId]);

  return (
    <Card title="Reconstructed Results (Different View Counts)" subtitle={groupId ? `Sweep group ${groupId}` : 'Finished experiments, ordered by number of views'}>
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
      ) : error ? (
        <ErrorBanner error={error} title="Could not load experiments" onRetry={reload} />
      ) : jobs.length === 0 ? (
        <p className="text-sm text-slate-400">No finished experiments to show.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
          {jobs.map((j) => (
            <li key={j.job_id}>
              <Link
                to={`/viewer/${j.job_id}`}
                className="block rounded-lg border border-line bg-ink-900/70 p-3 transition hover:border-brand-blue"
              >
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-white">{j.num_views}<span className="ml-1 text-xs font-normal text-slate-400">views</span></span>
                  <Box className="h-4 w-4 text-slate-500" aria-hidden />
                </div>
                <div className="mt-1 truncate text-xs text-slate-400">{titleCase(j.view_arrangement)} - {METHOD_SHORT[j.recon_method] || j.recon_method}</div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-slate-400">F-score</span>
                  <span className="font-mono text-slate-200">{formatMetric('f_score', j.f_score)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Runtime</span>
                  <span className="font-mono text-slate-200">{formatMetric('runtime_sec', j.runtime_sec)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function Comparison() {
  const jobId = useActiveJobId();
  const [params] = useSearchParams();
  const exp = useExperiment(jobId, { poll: false });
  const [tab, setTab] = useState('methods');
  const [metric, setMetric] = useState('f_score');

  const groupId = params.get('group') || (exp.job && exp.job.group_id) || '';
  const ready = !jobId || !!exp.job || !!exp.error;
  const analysis = useAnalysis(groupId, ready);
  const a = analysis.data;
  const job = exp.job;
  const results = job && job.results;
  const hasBoth = results && results.classical && results.neural;

  return (
    <div>
      <PageHeader
        title="Method & View Comparison"
        subtitle={job ? jobSubtitle(job) : 'Compare methods, view counts and arrangements across experiments.'}
        actions={job && (
          <>
            <StatusBadge status={job.status} />
            <RemoteBadge job={job} />
            <Button to={`/viewer/${job.job_id}`}>3D Viewer</Button>
          </>
        )}
      />
      <Tabs tabs={TABS} value={tab} onChange={setTab} className="mb-6" idPrefix="cmp" />

      {tab === 'methods' && (
        <div className="mb-6 space-y-4">
          {jobId && exp.error && !job && <ErrorBanner error={exp.error} title="Could not load the experiment" onRetry={exp.refresh} />}
          {job && hasBoth && (
            <MetricGrid
              keys={['f_score', 'chamfer_distance', 'completeness_pct', 'runtime_sec']}
              classical={results.classical}
              neural={results.neural}
              className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
            />
          )}
          {job && !hasBoth && (
            <Alert tone="info" title="This experiment has a single method">
              Run it with &quot;Both (Compare)&quot; to see Classical and Neural metrics side by side. The charts below still use all finished experiments.
            </Alert>
          )}
          {!jobId && (
            <Alert tone="info" title="Showing aggregate results">
              Open an experiment from History to compare its two methods directly.
            </Alert>
          )}
        </div>
      )}

      {analysis.loading && !a ? (
        <Skeleton className="h-80" />
      ) : analysis.error ? (
        <ErrorBanner error={analysis.error} title="Could not load analysis" onRetry={analysis.reload} />
      ) : !a || !a.has_data ? (
        <NoAnalysisData />
      ) : (
        <div className="space-y-6">
          {tab !== 'arrangement' ? (
            <Card
              title="Reconstruction Quality vs Number of Views"
              actions={<MetricSelect value={metric} onChange={setMetric} />}
            >
              <ViewCountChart analysis={a} metricKey={metric} />
            </Card>
          ) : (
            <Card
              title="Reconstruction Quality vs View Arrangement"
              actions={<MetricSelect value={metric} onChange={setMetric} />}
            >
              <ArrangementChart analysis={a} metricKey={metric} />
            </Card>
          )}
          {tab === 'methods' && <ResultsStrip groupId={groupId} />}
          {tab === 'views' && (
            <Card title="Quantitative Results by Number of Views">
              <QuantTable rows={a.view_count || []} firstColLabel="Views" firstColValue={(r) => r.views} />
            </Card>
          )}
          {tab === 'arrangement' && (
            <Card title="Quantitative Results by Arrangement">
              <QuantTable rows={a.arrangement || []} firstColLabel="Arrangement" firstColValue={(r) => titleCase(r.arrangement)} />
            </Card>
          )}
        </div>
      )}
      {groupId && <p className="mt-4 text-xs text-slate-500">Filtered to sweep group {groupId}.</p>}
    </div>
  );
}
