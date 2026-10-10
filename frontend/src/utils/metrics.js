import { formatInt, formatNumber, formatPercent, formatDuration } from './formatters';

// Definitions of the metrics shown in the UI. `better` drives green/red highlighting.
export const METRICS = {
  chamfer_distance: {
    key: 'chamfer_distance', label: 'Chamfer Distance', short: 'Chamfer', better: 'lower',
    hint: 'Lower is better', format: (v) => formatNumber(v, 4), needsGT: true,
  },
  f_score: {
    key: 'f_score', label: 'F-score', short: 'F-score', better: 'higher',
    hint: 'Higher is better', format: (v) => formatNumber(v, 3), needsGT: true,
  },
  completeness_pct: {
    key: 'completeness_pct', label: 'Completeness', short: 'Completeness', better: 'higher',
    hint: 'Higher is better', format: (v) => formatPercent(v, 1), needsGT: true,
  },
  accuracy: {
    key: 'accuracy', label: 'Accuracy', short: 'Accuracy', better: 'higher',
    hint: 'Higher is better', format: (v) => formatNumber(v, 3), needsGT: true,
  },
  runtime_sec: {
    key: 'runtime_sec', label: 'Runtime', short: 'Runtime', better: 'lower',
    hint: 'Lower is better', format: (v) => formatDuration(v),
  },
  camera_pose_error_deg: {
    key: 'camera_pose_error_deg', label: 'Camera Pose Error', short: 'Pose error', better: 'lower',
    hint: 'Lower is better', format: (v) => `${Number(v).toFixed(2)}°`,
  },
  registration_ratio_pct: {
    key: 'registration_ratio_pct', label: 'Registration ratio', short: 'Registration', better: 'higher',
    hint: 'Higher is better', format: (v) => formatPercent(v, 1),
  },
  reprojection_error_px: {
    key: 'reprojection_error_px', label: 'Reprojection error', short: 'Reproj. error', better: 'lower',
    hint: 'Lower is better', format: (v) => `${Number(v).toFixed(2)} px`,
  },
  floating_artifact_pct: {
    key: 'floating_artifact_pct', label: 'Floating artifacts', short: 'Floaters', better: 'lower',
    hint: 'Lower is better', format: (v) => formatPercent(v, 1),
  },
  point_count: {
    key: 'point_count', label: 'Point count', short: 'Points', better: null,
    hint: '', format: (v) => formatInt(v),
  },
};

export const OVERALL_METRIC_KEYS = [
  'chamfer_distance', 'f_score', 'completeness_pct', 'accuracy', 'runtime_sec', 'camera_pose_error_deg',
];

export function isNum(v) {
  return v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
}

export function formatMetric(key, value) {
  if (!isNum(value)) return 'n/a';
  const def = METRICS[key];
  return def ? def.format(Number(value)) : formatNumber(value);
}

// Percent delta of `b` relative to `a` ((b - a) / |a| * 100). null when not computable.
export function pctDelta(a, b) {
  if (!isNum(a) || !isNum(b)) return null;
  const av = Number(a);
  if (av === 0) return null;
  return ((Number(b) - av) / Math.abs(av)) * 100;
}

// Is `delta` an improvement for the metric? null when unknown/no change.
export function isImprovement(key, delta) {
  const def = METRICS[key];
  if (delta === null || !def || !def.better || delta === 0) return null;
  return def.better === 'higher' ? delta > 0 : delta < 0;
}

// Which method has the better value for a metric. null when either is missing or tied.
export function bestMethod(key, classical, neural) {
  const def = METRICS[key];
  if (!def || !def.better || !isNum(classical) || !isNum(neural)) return null;
  const c = Number(classical);
  const n = Number(neural);
  if (c === n) return null;
  if (def.better === 'higher') return c > n ? 'classical' : 'neural';
  return c < n ? 'classical' : 'neural';
}

export function metricOf(result, key) {
  if (!result || !result.metrics) return null;
  const v = result.metrics[key];
  return isNum(v) ? Number(v) : null;
}

export function isResultOk(result) {
  return !!result && result.status === 'completed';
}

// Distinct non-empty metrics notes across results.
export function collectNotes(results) {
  const out = [];
  Object.values(results || {}).forEach((r) => {
    if (r && r.metrics_note && !out.includes(r.metrics_note)) out.push(r.metrics_note);
  });
  return out;
}

// Chart series helper for /api/analysis rows. Returns values aligned with `rows`.
export function seriesFor(rows, method, metricKey) {
  return rows.map((row) => {
    const m = row ? row[method] : null;
    if (!m) return null;
    const v = m[metricKey];
    return isNum(v) ? Number(v) : null;
  });
}

export function hasAnyValue(series) {
  return series.some((v) => v !== null);
}
