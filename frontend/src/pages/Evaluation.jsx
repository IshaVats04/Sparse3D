import { useState } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Tabs from '../components/ui/Tabs';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import MetricGrid from '../components/experiment/MetricGrid';
import { Alert } from '../components/ui/Feedback';
import { RemoteBadge, StatusBadge } from '../components/ui/Badge';
import JobGate from '../components/experiment/JobGate';
import DownloadButtons from '../components/experiment/DownloadButtons';
import MethodViewerPanel from '../components/experiment/MethodViewerPanel';
import ErrorHistogram from '../components/charts/ErrorHistogram';
import { DEFAULT_VIEW_OPTIONS } from '../components/viewer/ViewOptionsMenu';
import { jobSubtitle } from '../utils/datasets';
import { useActiveJobId } from '../hooks/useUpload';
import { useExperiment } from '../hooks/useExperiment';
import {
  METRICS, OVERALL_METRIC_KEYS, collectNotes, formatMetric, isImprovement, isNum, isResultOk, metricOf, pctDelta,
} from '../utils/metrics';
import { formatInt } from '../utils/formatters';

const TABS = [
  { id: 'overall', label: 'Overall Metrics' },
  { id: 'pointcloud', label: 'Point Cloud Analysis' },
  { id: 'mesh', label: 'Mesh Analysis' },
  { id: 'pose', label: 'Camera Pose Analysis' },
];

function CompareTable({ rows, classical, neural }) {
  const c = isResultOk(classical) ? classical : null;
  const n = isResultOk(neural) ? neural : null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left">
        <thead className="border-b border-line">
          <tr>
            <th className="th">Metric</th>
            {c && <th className="th">Classical</th>}
            {n && <th className="th">Neural</th>}
            {c && n && <th className="th">Neural vs Classical</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {rows.map((key) => {
            const cv = metricOf(c, key);
            const nv = metricOf(n, key);
            const pct = pctDelta(cv, nv);
            const good = isImprovement(key, pct);
            return (
              <tr key={key}>
                <td className="td text-slate-300">{METRICS[key].label}</td>
                {c && <td className="td font-mono" title={!isNum(cv) ? c.metrics_note : undefined}>{formatMetric(key, cv)}</td>}
                {n && <td className="td font-mono" title={!isNum(nv) ? n.metrics_note : undefined}>{formatMetric(key, nv)}</td>}
                {c && n && (
                  <td className={`td font-mono ${good === true ? 'text-emerald-400' : good === false ? 'text-red-300' : 'text-slate-400'}`}>
                    {pct === null ? 'n/a' : `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PerMethodNote({ classical, neural }) {
  const notes = [];
  [['Classical', classical], ['Neural', neural]].forEach(([label, r]) => {
    if (r && r.status !== 'completed') notes.push(`${label}: ${r.message || r.status}`);
  });
  if (!notes.length) return null;
  return <Alert tone="warn" className="mb-4" title="Some methods have no metrics"><ul>{notes.map((t) => <li key={t}>{t}</li>)}</ul></Alert>;
}

function Overall({ job, classical, neural }) {
  const notes = collectNotes({ classical, neural });
  const ok = [['classical', classical], ['neural', neural]].filter(([, r]) => isResultOk(r));
  return (
    <div className="space-y-6">
      <PerMethodNote classical={classical} neural={neural} />
      <MetricGrid keys={OVERALL_METRIC_KEYS} classical={classical} neural={neural} />
      {notes.length > 0 && (
        <div className="rounded-lg border border-line bg-ink-800/60 px-4 py-3 text-xs text-slate-400">
          {notes.map((n) => <p key={n}>Note: {n}</p>)}
        </div>
      )}

      <Card title="Point Cloud Comparison">
        {ok.length === 0 ? (
          <p className="text-sm text-slate-400">No completed reconstruction to show.</p>
        ) : (
          <div className={`grid gap-4 ${ok.length > 1 ? 'md:grid-cols-2' : ''}`}>
            {ok.map(([key, res]) => (
              <MethodViewerPanel
                key={key}
                methodKey={key}
                result={res}
                classical={classical}
                neural={neural}
                options={DEFAULT_VIEW_OPTIONS}
                height={260}
                showTiles={false}
                showModeSwitch={false}
              />
            ))}
          </div>
        )}
      </Card>

      <Card title="Error Distribution">
        <ErrorHistogram classical={classical} neural={neural} />
      </Card>

      <Card title="Download Results">
        <DownloadButtons job={job} />
      </Card>
    </div>
  );
}

function PointCloudTab({ classical, neural }) {
  return (
    <div className="space-y-6">
      <PerMethodNote classical={classical} neural={neural} />
      <Card title="Point cloud statistics">
        <CompareTable rows={['point_count', 'floating_artifact_pct', 'reprojection_error_px', 'chamfer_distance', 'accuracy']} classical={classical} neural={neural} />
      </Card>
      <Card title="Error Distribution">
        <ErrorHistogram classical={classical} neural={neural} />
      </Card>
    </div>
  );
}

function MeshTab({ classical, neural }) {
  const rows = [['Classical', classical], ['Neural', neural]].filter(([, r]) => isResultOk(r));
  return (
    <div className="space-y-6">
      <PerMethodNote classical={classical} neural={neural} />
      <Card title="Mesh statistics">
        {rows.length === 0 ? (
          <p className="text-sm text-slate-400">No completed reconstruction to analyse.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-left">
              <thead className="border-b border-line">
                <tr><th className="th">Method</th><th className="th">Vertices</th><th className="th">Triangles</th><th className="th">Mesh file</th></tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {rows.map(([label, r]) => (
                  <tr key={label}>
                    <td className="td">{label}</td>
                    <td className="td font-mono">{r.mesh ? formatInt(r.mesh.vertex_count) : 'n/a'}</td>
                    <td className="td font-mono">{r.mesh ? formatInt(r.mesh.triangle_count) : 'n/a'}</td>
                    <td className="td text-slate-400">{r.files && r.files.mesh ? 'Available' : 'Not generated (enable Generate Mesh)'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function PoseTab({ classical, neural }) {
  const rows = [['Classical', classical], ['Neural', neural]].filter(([, r]) => isResultOk(r));
  return (
    <div className="space-y-6">
      <PerMethodNote classical={classical} neural={neural} />
      <Card title="Registration and pose error">
        {rows.length === 0 ? (
          <p className="text-sm text-slate-400">No completed reconstruction to analyse.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead className="border-b border-line">
                <tr>
                  <th className="th">Method</th><th className="th">Registered</th><th className="th">Ratio</th>
                  <th className="th">Mean reprojection error</th><th className="th">Pose error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {rows.map(([label, r]) => {
                  const reg = r.registration;
                  return (
                    <tr key={label}>
                      <td className="td">{label}</td>
                      <td className="td font-mono">{reg ? `${reg.registered} / ${reg.total_input}` : 'n/a'}</td>
                      <td className="td font-mono">{formatMetric('registration_ratio_pct', reg ? reg.ratio_pct : null)}</td>
                      <td className="td font-mono">{formatMetric('reprojection_error_px', reg ? reg.mean_reprojection_error_px : null)}</td>
                      <td className="td font-mono" title={!isNum(metricOf(r, 'camera_pose_error_deg')) ? 'Needs ground-truth camera poses' : undefined}>
                        {formatMetric('camera_pose_error_deg', metricOf(r, 'camera_pose_error_deg'))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {rows.map(([label, r]) => (
        <Card key={label} title={`${label}: estimated cameras`}>
          {!r.cameras || r.cameras.length === 0 ? (
            <p className="text-sm text-slate-400">No camera poses were exported (enable Estimate Camera Poses).</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left">
                <thead className="border-b border-line"><tr><th className="th">Image</th><th className="th">Position (x, y, z)</th></tr></thead>
                <tbody className="divide-y divide-line-soft">
                  {r.cameras.map((c) => (
                    <tr key={c.name}>
                      <td className="td">{c.name}</td>
                      <td className="td font-mono text-xs">{(c.position || []).map((v) => Number(v).toFixed(3)).join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function EvaluationBody({ job }) {
  const [tab, setTab] = useState('overall');
  const classical = job.results ? job.results.classical : null;
  const neural = job.results ? job.results.neural : null;
  return (
    <>
      <Tabs tabs={TABS} value={tab} onChange={setTab} className="mb-6" idPrefix="eval" />
      {tab === 'overall' && <Overall job={job} classical={classical} neural={neural} />}
      {tab === 'pointcloud' && <PointCloudTab classical={classical} neural={neural} />}
      {tab === 'mesh' && <MeshTab classical={classical} neural={neural} />}
      {tab === 'pose' && <PoseTab classical={classical} neural={neural} />}
    </>
  );
}

export default function Evaluation() {
  const jobId = useActiveJobId();
  const exp = useExperiment(jobId, { poll: false });
  const job = exp.job;
  return (
    <div>
      <PageHeader
        title="Evaluation Metrics"
        subtitle={job ? `${jobSubtitle(job)} - ${job.ground_truth_source ? `ground truth: ${job.ground_truth_source}` : job.has_ground_truth ? 'ground truth provided' : 'no ground-truth model'}${job.known_camera_poses ? `, ${job.known_camera_poses} known camera poses` : ''}` : 'Quantitative comparison of the reconstructions.'}
        actions={(
          <>
            {job && <StatusBadge status={job.status} />}
            <RemoteBadge job={job} />
            {job && <Button to={`/comparison/${job.job_id}`}>Comparison</Button>}
          </>
        )}
      />
      <JobGate jobId={jobId} exp={exp}>{(j) => <EvaluationBody job={j} />}</JobGate>
    </div>
  );
}
