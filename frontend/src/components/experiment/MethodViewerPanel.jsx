import { AlertTriangle, Ban, MinusCircle } from 'lucide-react';
import PointCloudViewport from '../viewer/PointCloudViewport';
import { MetricTile } from '../ui/MetricCard';
import { METRICS, bestMethod, formatMetric, isNum, metricOf } from '../../utils/metrics';
import { METHOD_COLORS } from '../../utils/constants';

const TILE_KEYS = [
  { key: 'chamfer_distance', arrow: '↓' },
  { key: 'f_score', arrow: '↑' },
  { key: 'completeness_pct', arrow: '↑' },
  { key: 'runtime_sec', arrow: '' },
];

/** Row of 4 small metric tiles (Chamfer down, F-score up, Completeness up, Runtime). */
export function MethodMetricTiles({ methodKey, classical, neural }) {
  const own = methodKey === 'classical' ? classical : neural;
  if (!own || !own.metrics) return null;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {TILE_KEYS.map(({ key, arrow }) => {
        const v = metricOf(own, key);
        const na = !isNum(v);
        const best = bestMethod(key, metricOf(classical, key), metricOf(neural, key)) === methodKey;
        return (
          <MetricTile
            key={key}
            label={METRICS[key].short}
            arrow={arrow}
            text={formatMetric(key, v)}
            na={na}
            best={best}
            title={na && own.metrics_note ? own.metrics_note : best ? 'Best of the two methods' : undefined}
          />
        );
      })}
    </div>
  );
}

function Unavailable({ result, height }) {
  const status = result ? result.status : 'skipped';
  const failed = status === 'failed';
  const Icon = !result ? MinusCircle : failed ? AlertTriangle : Ban;
  const message = result && result.message
    ? result.message
    : !result
      ? 'This method was not requested for this experiment.'
      : `This method ${status === 'unavailable' ? 'is unavailable' : status === 'skipped' ? 'was skipped' : 'did not complete'}.`;
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 text-center
        ${failed ? 'border-red-500/40 bg-red-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}
      style={{ height }}
      role="status"
    >
      <Icon className={`h-8 w-8 ${failed ? 'text-red-400' : 'text-amber-400'}`} aria-hidden />
      <div className="text-sm font-medium capitalize text-white">{result ? status : 'Not run'}</div>
      <p className="max-w-sm text-sm text-slate-300">{message}</p>
    </div>
  );
}

/**
 * One method's panel: title, viewer (or the method's message when not completed), metric tiles.
 */
export default function MethodViewerPanel({
  methodKey, result, classical, neural, options, height = 420, title, showTiles = true, showModeSwitch = true,
}) {
  const color = METHOD_COLORS[methodKey];
  const heading = title || (result && result.label) || (methodKey === 'classical' ? 'Classical (COLMAP + Open3D)' : 'Neural (PyTorch)');
  const ok = result && result.status === 'completed';
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line-soft px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />
        <h3 className="truncate text-sm font-semibold text-white">{heading}</h3>
      </div>
      <div className="space-y-3 p-3">
        {ok ? (
          <PointCloudViewport result={result} options={options} height={height} showModeSwitch={showModeSwitch} />
        ) : (
          <Unavailable result={result} height={height} />
        )}
        {showTiles && ok && <MethodMetricTiles methodKey={methodKey} classical={classical} neural={neural} />}
      </div>
    </div>
  );
}
