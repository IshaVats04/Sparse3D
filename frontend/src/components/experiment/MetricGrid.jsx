import MetricCard from '../ui/MetricCard';
import {
  METRICS, bestMethod, formatMetric, isImprovement, isNum, isResultOk, metricOf, pctDelta,
} from '../../utils/metrics';
import { METHOD_COLORS } from '../../utils/constants';

/**
 * Props for <MetricCard> for one metric, from the two method results.
 * Deltas are computed client-side (neural relative to classical).
 */
export function buildMetricCard(key, classical, neural) {
  const def = METRICS[key];
  const c = isResultOk(classical) ? classical : null;
  const n = isResultOk(neural) ? neural : null;
  const cv = metricOf(c, key);
  const nv = metricOf(n, key);
  const best = bestMethod(key, cv, nv);
  const both = c && n;
  const entry = (label, method, res, v) => ({
    label: both ? label : undefined,
    color: both ? METHOD_COLORS[method] : undefined,
    text: formatMetric(key, v),
    na: !isNum(v),
    best: best === method,
    title: !isNum(v) && res.metrics_note ? res.metrics_note : undefined,
  });
  const values = [];
  if (c) values.push(entry('Classical', 'classical', c, cv));
  if (n) values.push(entry('Neural', 'neural', n, nv));
  if (values.length === 0) values.push({ text: 'n/a', na: true });
  let delta = null;
  if (both) {
    const pct = pctDelta(cv, nv);
    if (pct !== null) delta = { pct, good: isImprovement(key, pct), title: 'Neural relative to Classical' };
  }
  return { key, label: def.label, hint: def.hint, values, delta };
}

export default function MetricGrid({ keys, classical, neural, className = 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3' }) {
  return (
    <div className={className}>
      {keys.map((k) => {
        const { key, ...props } = buildMetricCard(k, classical, neural);
        return <MetricCard key={key} {...props} />;
      })}
    </div>
  );
}
