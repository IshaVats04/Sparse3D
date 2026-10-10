import { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { X } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Tabs from '../components/ui/Tabs';
import Card from '../components/ui/Card';
import { ErrorBanner, Skeleton } from '../components/ui/Feedback';
import SweepPanel from '../components/experiment/SweepPanel';
import {
  ArrangementChart, FailureList, Insights, MetricSelect, NoAnalysisData, QuantTable, ViewCountChart,
} from '../components/charts/AnalysisViews';
import { useAnalysis } from '../hooks/useAnalysis';
import { titleCase } from '../utils/formatters';

const TABS = [
  { id: 'views', label: 'Effect of View Count' },
  { id: 'arrangement', label: 'Effect of View Arrangement' },
  { id: 'failures', label: 'Failure Case Analysis' },
];

export default function Analysis() {
  const [params, setParams] = useSearchParams();
  const loc = useLocation();
  const groupId = params.get('group') || '';
  const [tab, setTab] = useState('views');
  const [metric, setMetric] = useState('f_score');
  const { data: a, error, loading, reload } = useAnalysis(groupId);

  useEffect(() => {
    if (loc.hash === '#sweep') {
      const el = document.getElementById('sweep');
      if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    }
  }, [loc.hash, a]);

  const clearGroup = () => { params.delete('group'); setParams(params); };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Experiment Analysis"
        subtitle="How reconstruction quality depends on the number and arrangement of input views."
      >
        {groupId && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-line bg-ink-800 px-3 py-1 text-xs text-slate-200">
            Sweep group <span className="font-mono">{groupId}</span>
            <button type="button" aria-label="Clear group filter" onClick={clearGroup}><X className="h-3.5 w-3.5 text-slate-400 hover:text-white" /></button>
          </div>
        )}
      </PageHeader>

      <Tabs tabs={TABS} value={tab} onChange={setTab} idPrefix="analysis" />

      {loading && !a ? (
        <div className="space-y-4"><Skeleton className="h-72" /><Skeleton className="h-48" /></div>
      ) : error ? (
        <ErrorBanner error={error} title="Could not load analysis" onRetry={reload} />
      ) : !a || !a.has_data ? (
        <NoAnalysisData />
      ) : (
        <>
          {tab === 'views' && (
            <>
              <div className="grid gap-6 xl:grid-cols-2">
                <Card title="Metrics vs Number of Views" actions={<MetricSelect value={metric} onChange={setMetric} />}>
                  <ViewCountChart analysis={a} metricKey={metric} />
                </Card>
                <Card title="Reconstruction Runtime vs Number of Views">
                  <ViewCountChart analysis={a} metricKey="runtime_sec" />
                </Card>
              </div>
              <div className="grid gap-6 xl:grid-cols-3">
                <Card title="Quantitative Results" className="xl:col-span-2">
                  <QuantTable rows={a.view_count || []} firstColLabel="Views" firstColValue={(r) => r.views} />
                </Card>
                <Card title="Observations / Insights">
                  <Insights insights={a.insights} />
                </Card>
              </div>
            </>
          )}
          {tab === 'arrangement' && (
            <>
              <Card title="Metrics vs View Arrangement" actions={<MetricSelect value={metric} onChange={setMetric} />}>
                {(a.arrangement || []).length > 0
                  ? <ArrangementChart analysis={a} metricKey={metric} />
                  : <p className="text-sm text-slate-400">No arrangement data. Run a sweep with several arrangements.</p>}
              </Card>
              <div className="grid gap-6 xl:grid-cols-3">
                <Card title="Quantitative Results" className="xl:col-span-2">
                  <QuantTable rows={a.arrangement || []} firstColLabel="Arrangement" firstColValue={(r) => titleCase(r.arrangement)} />
                </Card>
                <Card title="Observations / Insights"><Insights insights={a.insights} /></Card>
              </div>
            </>
          )}
          {tab === 'failures' && (
            <Card title="Failure Cases" subtitle="Runs where a method failed or registered fewer views than requested">
              <FailureList failures={a.failures} />
            </Card>
          )}
        </>
      )}

      <SweepPanel onStarted={reload} />
      <p className="text-xs text-slate-500">
        Averages are over the runs with each setting. <Link className="underline" to="/history">Open experiment history</Link>
      </p>
    </div>
  );
}
