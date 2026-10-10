import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Cpu, XCircle } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Stepper from '../components/ui/Stepper';
import ProgressBar from '../components/ui/ProgressBar';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { RemoteBadge, StatusBadge } from '../components/ui/Badge';
import { Alert, EmptyState, ErrorBanner, PageSkeleton } from '../components/ui/Feedback';
import LogConsole from '../components/experiment/LogConsole';
import { useExperiment } from '../hooks/useExperiment';
import { useActiveJobId } from '../hooks/useUpload';
import { cancelJob } from '../services/experimentService';
import { STAGE_DESCRIPTIONS, STAGE_ORDER, SUCCESS_STATUSES } from '../utils/constants';
import { jobSubtitle } from '../utils/datasets';
import { formatDuration } from '../utils/formatters';

const REDIRECT_SECONDS = 4;

export default function Processing() {
  const jobId = useActiveJobId();
  const nav = useNavigate();
  const { job, error, loading, refresh } = useExperiment(jobId);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(null);
  const sawActive = useRef(false);
  const [countdown, setCountdown] = useState(null);

  const active = !!job && (job.status === 'queued' || job.status === 'processing');
  const success = !!job && SUCCESS_STATUSES.includes(job.status);
  const hasWarnings = !!job && Array.isArray(job.warnings) && job.warnings.length > 0;

  useEffect(() => {
    if (active) sawActive.current = true;
  }, [active]);

  // Auto-link to the viewer when the run we were watching completes cleanly.
  useEffect(() => {
    if (!(job && job.status === 'completed' && sawActive.current && !hasWarnings)) return undefined;
    setCountdown(REDIRECT_SECONDS);
    const t = setInterval(() => setCountdown((c) => (c === null ? c : c - 1)), 1000);
    return () => clearInterval(t);
  }, [job && job.status, hasWarnings]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (countdown === 0 && job) nav(`/viewer/${job.job_id}`);
  }, [countdown, job, nav]);

  const doCancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelJob(jobId);
      setConfirmCancel(false);
      refresh();
    } catch (e) {
      setCancelError(e);
      setConfirmCancel(false);
    } finally {
      setCancelling(false);
    }
  };

  if (!jobId) {
    return (
      <div>
        <PageHeader title="Reconstruction" subtitle="Track a running reconstruction." />
        <EmptyState icon={Cpu} title="No experiment running" action={<Button variant="primary" to="/upload">Start a new experiment</Button>}>
          Start an experiment from the Upload page, or open one from your history.
        </EmptyState>
      </div>
    );
  }
  if (!job && loading) return <PageSkeleton />;
  if (!job && error) {
    return (
      <div className="space-y-3">
        <ErrorBanner error={error} title={error.status === 404 ? `Experiment ${jobId} was not found` : 'Could not load the experiment'} onRetry={refresh} />
        <Link to="/history" className="text-sm text-blue-300 underline">Back to history</Link>
      </div>
    );
  }
  if (!job) return null;

  const stages = Array.isArray(job.stages) && job.stages.length
    ? job.stages
    : STAGE_ORDER.map((s) => ({ ...s, status: 'pending' }));
  const running = stages.find((s) => s.status === 'running') || stages.find((s) => s.status === 'failed');
  const currentKey = running ? running.key : job.stage;
  const currentLabel = (running && running.label) || (stages.find((s) => s.key === job.stage) || {}).label
    || (job.status === 'completed' ? 'Complete' : job.status === 'queued' ? 'Queued' : '');
  const description = STAGE_DESCRIPTIONS[currentKey] || (job.status === 'queued' ? 'Waiting for a worker to pick up the job.' : '');

  const title = active
    ? 'Reconstruction in Progress'
    : success
      ? 'Reconstruction Complete'
      : job.status === 'cancelled' ? 'Reconstruction Cancelled' : 'Reconstruction Failed';
  const subtitle = active ? `Please wait while we process your images...${job.dataset ? ` (${jobSubtitle(job)})` : ''}` : jobSubtitle(job);

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={(
          <>
            <StatusBadge status={job.status} />
            <RemoteBadge job={job} />
            {active && <Button variant="danger" icon={XCircle} onClick={() => setConfirmCancel(true)}>Cancel</Button>}
            {success && <Button variant="primary" iconRight={ArrowRight} to={`/viewer/${job.job_id}`}>View Results</Button>}
          </>
        )}
      />

      {error && <ErrorBanner className="mb-4" error={error} title="Connection problem while polling the backend" onRetry={refresh} />}
      {cancelError && <ErrorBanner className="mb-4" error={cancelError} title="Could not cancel the experiment" />}

      <Card className="mb-6" bodyClassName="px-4 py-6 sm:px-8">
        <Stepper steps={stages} />
      </Card>

      {countdown !== null && countdown > 0 && (
        <Alert tone="ok" className="mb-4" title="Reconstruction finished">
          Opening the 3D viewer in {countdown}s.{' '}
          <button type="button" className="underline" onClick={() => setCountdown(null)}>Stay on this page</button>
        </Alert>
      )}

      {job.status === 'failed' && (
        <Alert tone="error" className="mb-4" title="The reconstruction failed">
          {job.error_message || 'No error message was reported by the backend. Check the logs below.'}
        </Alert>
      )}
      {job.status === 'cancelled' && <Alert tone="warn" className="mb-4" title="This experiment was cancelled" />}
      {success && job.status === 'partial_success' && (
        <Alert tone="warn" className="mb-4" title="Finished with partial results">
          {job.error_message || 'One of the methods did not complete. Open the results to see which.'}
        </Alert>
      )}
      {hasWarnings && (
        <Alert tone="warn" className="mb-4" title={`Warnings (${job.warnings.length})`}>
          <ul className="list-disc pl-4">{job.warnings.map((w, i) => <li key={`${i}-${w}`}>{w}</li>)}</ul>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="Current Step" className="lg:col-span-2">
          <div className="space-y-5">
            <div>
              <div className="text-lg font-semibold text-white">{currentLabel || 'n/a'}</div>
              <p className="mt-1 text-sm text-slate-400">{description}</p>
            </div>
            <ProgressBar value={job.progress} label="Overall progress" />
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Elapsed Time</dt>
                <dd className="mt-0.5 font-mono text-slate-100">{formatDuration(job.elapsed_sec)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Estimated Time</dt>
                <dd className="mt-0.5 font-mono text-slate-100">{active ? formatDuration(job.eta_sec) : 'n/a'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Images</dt>
                <dd className="mt-0.5 text-slate-100">{job.image_count ?? 'n/a'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-400">Method</dt>
                <dd className="mt-0.5 capitalize text-slate-100">{(job.configuration && job.configuration.recon_method) || 'n/a'}</dd>
              </div>
            </dl>
          </div>
        </Card>

        <Card title="Live Logs" className="lg:col-span-3" bodyClassName="p-3">
          <LogConsole logs={job.logs || []} height={340} />
        </Card>
      </div>
    </div>
  );
}
