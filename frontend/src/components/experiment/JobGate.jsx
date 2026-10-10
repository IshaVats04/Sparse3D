import { Link } from 'react-router-dom';
import { FlaskConical, Hourglass } from 'lucide-react';
import { EmptyState, ErrorBanner, PageSkeleton } from '../ui/Feedback';
import Button from '../ui/Button';
import { SUCCESS_STATUSES } from '../../utils/constants';

/**
 * Wraps result pages: handles "no job selected", loading, error, still-running and failed states.
 * Renders children(job) only when the job has results.
 */
export default function JobGate({ jobId, exp, children }) {
  const { job, error, loading, refresh } = exp;
  if (!jobId) {
    return (
      <EmptyState
        icon={FlaskConical}
        title="No experiment selected"
        action={<div className="flex gap-2"><Button variant="primary" to="/upload">New experiment</Button><Button to="/history">Open history</Button></div>}
      >
        Run a reconstruction or pick one from your experiment history to see its results.
      </EmptyState>
    );
  }
  if (error && !job) {
    return (
      <div className="space-y-3">
        <ErrorBanner error={error} title={error.status === 404 ? `Experiment ${jobId} was not found` : 'Could not load the experiment'} onRetry={refresh} />
        <Link to="/history" className="text-sm text-blue-300 underline">Back to history</Link>
      </div>
    );
  }
  if (loading && !job) return <PageSkeleton />;
  if (!job) return null;

  if (!SUCCESS_STATUSES.includes(job.status)) {
    const active = job.status === 'queued' || job.status === 'processing';
    return (
      <div className="space-y-4">
        {error && <ErrorBanner error={error} title="Connection problem while polling" />}
        <EmptyState
          icon={Hourglass}
          title={active ? 'Reconstruction still in progress' : `Experiment ${job.status.replace('_', ' ')}`}
          action={<Button variant="primary" to={`/processing/${job.job_id}`}>View progress</Button>}
        >
          {active
            ? 'Results appear here once the pipeline finishes.'
            : job.error_message || 'This experiment has no results to display.'}
        </EmptyState>
      </div>
    );
  }
  return (
    <>
      {error && <ErrorBanner error={error} title="Connection problem" className="mb-4" />}
      {children(job)}
    </>
  );
}
