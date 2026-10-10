import {
  BarElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement, PointElement, Title, Tooltip,
} from 'chart.js';

ChartJS.register(BarElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Title, Tooltip);
ChartJS.defaults.color = '#94a3b8';
ChartJS.defaults.font.family = 'Inter, ui-sans-serif, system-ui, sans-serif';
ChartJS.defaults.borderColor = 'rgba(50, 59, 115, 0.45)';

export function baseOptions({ xLabel, yLabel, yBeginAtZero = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'top', align: 'end', labels: { usePointStyle: true, boxWidth: 8, color: '#cbd5e1' } },
      tooltip: {
        backgroundColor: '#11152e',
        borderColor: '#323b73',
        borderWidth: 1,
        titleColor: '#fff',
        bodyColor: '#cbd5e1',
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(50, 59, 115, 0.25)' },
        title: xLabel ? { display: true, text: xLabel, color: '#94a3b8' } : undefined,
      },
      y: {
        beginAtZero: yBeginAtZero,
        grid: { color: 'rgba(50, 59, 115, 0.25)' },
        title: yLabel ? { display: true, text: yLabel, color: '#94a3b8' } : undefined,
      },
    },
  };
}

export { ChartJS };
