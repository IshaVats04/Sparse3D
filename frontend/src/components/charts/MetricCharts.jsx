import { Line, Bar } from 'react-chartjs-2';
import { LineChart as LineChartIcon } from 'lucide-react';
import { baseOptions } from './chartSetup';
import { hasAnyValue } from '../../utils/metrics';
import { EmptyState } from '../ui/Feedback';

function NoValues({ message }) {
  return (
    <EmptyState icon={LineChartIcon} title="No values to plot" className="py-10">
      {message || 'This metric is n/a for the selected experiments (for example it needs a ground-truth model).'}
    </EmptyState>
  );
}

/**
 * series: [{label, color, data: (number|null)[]}] aligned with labels. Null points are gaps.
 */
export function MetricLineChart({ labels, series, xLabel, yLabel, height = 288, emptyMessage }) {
  const usable = series.filter((s) => hasAnyValue(s.data));
  if (usable.length === 0) return <NoValues message={emptyMessage} />;
  const data = {
    labels,
    datasets: usable.map((s) => ({
      label: s.label,
      data: s.data,
      borderColor: s.color,
      backgroundColor: `${s.color}33`,
      pointBackgroundColor: s.color,
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0.3,
      spanGaps: false,
    })),
  };
  return (
    <div style={{ height }}>
      <Line data={data} options={baseOptions({ xLabel, yLabel })} aria-label={yLabel || 'Line chart'} role="img" />
    </div>
  );
}

export function MetricBarChart({ labels, series, xLabel, yLabel, height = 288, emptyMessage }) {
  const usable = series.filter((s) => hasAnyValue(s.data));
  if (usable.length === 0) return <NoValues message={emptyMessage} />;
  const data = {
    labels,
    datasets: usable.map((s) => ({
      label: s.label,
      data: s.data,
      backgroundColor: `${s.color}cc`,
      borderColor: s.color,
      borderWidth: 1,
      borderRadius: 4,
    })),
  };
  return (
    <div style={{ height }}>
      <Bar data={data} options={baseOptions({ xLabel, yLabel, yBeginAtZero: true })} aria-label={yLabel || 'Bar chart'} role="img" />
    </div>
  );
}
