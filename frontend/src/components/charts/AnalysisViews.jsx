import { Link } from 'react-router-dom';
import { FlaskConical } from 'lucide-react';
import { MetricBarChart, MetricLineChart } from './MetricCharts';
import { EmptyState } from '../ui/Feedback';
import Button from '../ui/Button';
import Select from '../ui/Select';
import { ANALYSIS_METRICS, METHOD_COLORS } from '../../utils/constants';
import { METRICS, formatMetric, seriesFor } from '../../utils/metrics';

export function MetricSelect({ value, onChange, className = 'w-44' }) {
  return (
    <Select
      className={className}
      value={value}
      onChange={onChange}
      aria-label="Metric"
      options={ANALYSIS_METRICS.map((m) => ({ value: m.key, label: m.label }))}
    />
  );
}

export function NoAnalysisData() {
  return (
    <EmptyState
      icon={FlaskConical}
      title="No experiments yet"
      action={<Button variant="primary" to="/analysis#sweep">Run a view-count sweep</Button>}
    >
      Charts are built from finished experiments. Run a sweep over 3-6 views to see how quality changes with the number of views.
    </EmptyState>
  );
}

function metricLabel(key) {
  return (ANALYSIS_METRICS.find((m) => m.key === key) || METRICS[key] || { label: key }).label;
}

const EMPTY_GT = 'This metric is n/a for these experiments. Chamfer, F-score and completeness need a ground-truth model.';

export function ViewCountChart({ analysis, metricKey, height }) {
  const rows = analysis.view_count || [];
  const labels = rows.map((r) => `${r.views} views`);
  return (
    <MetricLineChart
      labels={labels}
      xLabel="Number of views"
      yLabel={metricLabel(metricKey)}
      height={height}
      emptyMessage={EMPTY_GT}
      series={[
        { label: 'Classical', color: METHOD_COLORS.classical, data: seriesFor(rows, 'classical', metricKey) },
        { label: 'Neural', color: METHOD_COLORS.neural, data: seriesFor(rows, 'neural', metricKey) },
      ]}
    />
  );
}

export function ArrangementChart({ analysis, metricKey, height }) {
  const rows = analysis.arrangement || [];
  const labels = rows.map((r) => r.arrangement.replace(/_/g, ' '));
  return (
    <MetricBarChart
      labels={labels}
      xLabel="View arrangement"
      yLabel={metricLabel(metricKey)}
      height={height}
      emptyMessage={EMPTY_GT}
      series={[
        { label: 'Classical', color: METHOD_COLORS.classical, data: seriesFor(rows, 'classical', metricKey) },
        { label: 'Neural', color: METHOD_COLORS.neural, data: seriesFor(rows, 'neural', metricKey) },
      ]}
    />
  );
}

const TABLE_COLS = [
  { key: 'chamfer_distance', label: 'Chamfer' },
  { key: 'f_score', label: 'F-score' },
  { key: 'completeness_pct', label: 'Completeness' },
  { key: 'runtime_sec', label: 'Runtime' },
];

/** Quantitative results table: one row per (setting, method). */
export function QuantTable({ rows, firstColLabel, firstColValue }) {
  const out = [];
  rows.forEach((r) => {
    ['classical', 'neural'].forEach((m) => {
      if (r[m]) out.push({ id: `${firstColValue(r)}-${m}`, first: firstColValue(r), method: m, data: r[m] });
    });
  });
  if (out.length === 0) return <p className="text-sm text-slate-400">No rows to show.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left">
        <thead className="border-b border-line">
          <tr>
            <th className="th">{firstColLabel}</th>
            <th className="th">Method</th>
            {TABLE_COLS.map((c) => <th key={c.key} className="th">{c.label}</th>)}
            <th className="th">Runs</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {out.map((o) => (
            <tr key={o.id}>
              <td className="td">{o.first}</td>
              <td className="td">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: METHOD_COLORS[o.method] }} aria-hidden />
                  <span className="capitalize">{o.method}</span>
                </span>
              </td>
              {TABLE_COLS.map((c) => (
                <td key={c.key} className="td font-mono" title={o.data[c.key] == null && c.key !== 'runtime_sec' ? 'n/a: needs a ground-truth model' : undefined}>
                  {formatMetric(c.key, o.data[c.key])}
                </td>
              ))}
              <td className="td font-mono text-slate-400">{o.data.runs ?? 'n/a'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Insights({ insights }) {
  if (!insights || insights.length === 0) {
    return <p className="text-sm text-slate-400">No observations yet. They are generated from the measured data only.</p>;
  }
  return (
    <ul className="space-y-2">
      {insights.map((t) => (
        <li key={t} className="flex gap-2.5 text-sm text-slate-200">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-blue" aria-hidden />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

export function FailureList({ failures }) {
  if (!failures || failures.length === 0) {
    return <p className="text-sm text-slate-400">No failure cases recorded in the selected experiments.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left">
        <thead className="border-b border-line">
          <tr><th className="th">Experiment</th><th className="th">Views</th><th className="th">Arrangement</th><th className="th">Method</th><th className="th">Reason</th></tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {failures.map((f, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <tr key={`${f.job_id}-${f.method}-${i}`}>
              <td className="td"><Link className="font-mono text-blue-300 hover:underline" to={`/viewer/${f.job_id}`}>{f.job_id}</Link></td>
              <td className="td font-mono">{f.num_views}</td>
              <td className="td">{String(f.view_arrangement || '').replace(/_/g, ' ')}</td>
              <td className="td capitalize">{f.method}</td>
              <td className="td text-amber-200">{f.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
