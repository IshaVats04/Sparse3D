import { useState } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Tabs from '../components/ui/Tabs';
import Button from '../components/ui/Button';
import JobGate from '../components/experiment/JobGate';
import MethodViewerPanel from '../components/experiment/MethodViewerPanel';
import ViewOptionsMenu, { DEFAULT_VIEW_OPTIONS } from '../components/viewer/ViewOptionsMenu';
import { Alert } from '../components/ui/Feedback';
import { RemoteBadge, StatusBadge } from '../components/ui/Badge';
import { jobSubtitle } from '../utils/datasets';
import { useActiveJobId } from '../hooks/useUpload';
import { useExperiment } from '../hooks/useExperiment';

const TABS = [
  { id: 'classical', label: 'Classical Result' },
  { id: 'neural', label: 'Neural Result' },
  { id: 'side', label: 'Side by Side' },
];

function ViewerBody({ job, options }) {
  const [tab, setTab] = useState('side');
  const classical = job.results ? job.results.classical : null;
  const neural = job.results ? job.results.neural : null;
  const common = { classical, neural, options };
  return (
    <>
      {job.status === 'partial_success' && (
        <Alert tone="warn" className="mb-4" title="Partial results">
          {job.error_message || 'One of the methods did not finish; its panel explains why.'}
        </Alert>
      )}
      <Tabs tabs={TABS} value={tab} onChange={setTab} className="mb-5" idPrefix="viewer" />
      {tab === 'side' ? (
        <div className="grid gap-5 xl:grid-cols-2">
          <MethodViewerPanel methodKey="classical" result={classical} title="Classical (COLMAP + Open3D)" height={400} {...common} />
          <MethodViewerPanel methodKey="neural" result={neural} title="Neural (PyTorch)" height={400} {...common} />
        </div>
      ) : (
        <MethodViewerPanel
          key={tab}
          methodKey={tab}
          result={tab === 'classical' ? classical : neural}
          title={tab === 'classical' ? 'Classical (COLMAP + Open3D)' : 'Neural (PyTorch)'}
          height={560}
          {...common}
        />
      )}
      {(classical && classical.metrics_note) || (neural && neural.metrics_note) ? (
        <p className="mt-4 text-xs text-slate-400">
          Note: {(classical && classical.metrics_note) || (neural && neural.metrics_note)}
        </p>
      ) : null}
    </>
  );
}

export default function Viewer3D() {
  const jobId = useActiveJobId();
  const exp = useExperiment(jobId, { poll: false });
  const [options, setOptions] = useState(DEFAULT_VIEW_OPTIONS);
  const job = exp.job;

  return (
    <div>
      <PageHeader
        title="3D Viewer"
        subtitle={job ? jobSubtitle(job) : 'Inspect reconstructed point clouds and meshes.'}
        actions={(
          <>
            {job && <StatusBadge status={job.status} />}
            <RemoteBadge job={job} />
            {job && <Button to={`/evaluation/${job.job_id}`}>Evaluation</Button>}
            <ViewOptionsMenu options={options} onChange={setOptions} />
          </>
        )}
      />
      <JobGate jobId={jobId} exp={exp}>
        {(j) => <ViewerBody job={j} options={options} />}
      </JobGate>
    </div>
  );
}
