import { Bar } from 'react-chartjs-2';
import { baseOptions } from './chartSetup';
import { METHOD_COLORS } from '../../utils/constants';

function labelsFor(h) {
  const { bins = [], counts = [] } = h || {};
  if (counts.length === bins.length - 1) {
    return counts.map((_, i) => `${Number(bins[i]).toPrecision(2)}-${Number(bins[i + 1]).toPrecision(2)}`);
  }
  return counts.map((_, i) => String(Number(bins[i] ?? i).toPrecision(2)));
}

function validHist(h) {
  return !!h && Array.isArray(h.counts) && h.counts.length > 0 && Array.isArray(h.bins);
}

/**
 * Error distribution bar chart from MethodResult.error_histogram of each method.
 * Methods with identical bins share one chart; otherwise each gets its own.
 * Renders a note when there is no histogram.
 */
export default function ErrorHistogram({ classical, neural, height = 260 }) {
  const entries = [
    { key: 'classical', label: 'Classical', hist: classical && classical.error_histogram },
    { key: 'neural', label: 'Neural', hist: neural && neural.error_histogram },
  ].filter((e) => validHist(e.hist));

  if (entries.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-slate-400">
        No error distribution available. It needs a ground-truth model, which was not provided for this experiment.
      </p>
    );
  }

  const sameBins = entries.length === 2
    && JSON.stringify(entries[0].hist.bins) === JSON.stringify(entries[1].hist.bins);
  const groups = sameBins ? [entries] : entries.map((e) => [e]);

  return (
    <div className={`grid gap-6 ${groups.length > 1 ? 'lg:grid-cols-2' : ''}`}>
      {groups.map((g) => (
        <div key={g.map((e) => e.key).join('-')} style={{ height }}>
          <Bar
            aria-label="Error distribution"
            role="img"
            data={{
              labels: labelsFor(g[0].hist),
              datasets: g.map((e) => ({
                label: e.label,
                data: e.hist.counts,
                backgroundColor: `${METHOD_COLORS[e.key]}cc`,
                borderColor: METHOD_COLORS[e.key],
                borderWidth: 1,
                borderRadius: 3,
              })),
            }}
            options={baseOptions({ xLabel: 'Point-to-reference error', yLabel: 'Point count', yBeginAtZero: true })}
          />
        </div>
      ))}
    </div>
  );
}
