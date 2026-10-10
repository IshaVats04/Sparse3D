import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Download, Eye, FlaskConical, Plus, Trash2 } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Select from '../components/ui/Select';
import Checkbox from '../components/ui/Checkbox';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { RemoteBadge, StatusBadge } from '../components/ui/Badge';
import { Alert, EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback';
import { useAsync } from '../hooks/useAsync';
import { useWizard } from '../hooks/useUpload';
import { deleteJob, getJob, listJobs } from '../services/experimentService';
import { downloadJobFile, resolveDownloadTypes } from '../services/reconstructionService';
import { FILE_TYPES, METHOD_SHORT, STATUS_META } from '../utils/constants';
import { describeDataset } from '../utils/datasets';
import { formatDate, titleCase } from '../utils/formatters';
import { formatMetric } from '../utils/metrics';

const FILTERS = [{ value: 'all', label: 'All statuses' }, ...Object.entries(STATUS_META).map(([value, m]) => ({ value, label: m.label }))];
const NOTE = 'n/a: needs a ground-truth model';

export default function History() {
  const loc = useLocation();
  const { jobId: currentJobId, setJobId } = useWizard();
  const { data, error, loading, reload } = useAsync(() => listJobs(), []);
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [checked, setChecked] = useState({ point_cloud: true, metrics_csv: true });
  const [downloading, setDownloading] = useState(false);
  const [dlReport, setDlReport] = useState(null); // [{label, ok, message}]
  const [dlError, setDlError] = useState(null);

  const jobs = useMemo(() => {
    const list = Array.isArray(data) ? [...data] : [];
    return list.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  }, [data]);
  const visible = jobs.filter((j) => filter === 'all' || j.status === filter);

  // Default selection: current experiment if present, otherwise the most recent.
  const effectiveSelected = selected && jobs.some((j) => j.job_id === selected)
    ? selected
    : (jobs.find((j) => j.job_id === currentJobId) || jobs[0] || {}).job_id || null;

  // Refresh periodically while something is running.
  const anyActive = jobs.some((j) => j.status === 'queued' || j.status === 'processing');
  useEffect(() => {
    if (!anyActive) return undefined;
    const t = setInterval(reload, 4000);
    return () => clearInterval(t);
  }, [anyActive, reload]);

  useEffect(() => {
    if (loc.hash === '#downloads') {
      const el = document.getElementById('downloads');
      if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    }
  }, [loc.hash, jobs.length]);

  const confirmDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteJob(toDelete.job_id);
      if (toDelete.job_id === currentJobId) setJobId(null);
      setToDelete(null);
      reload();
    } catch (e) {
      setDeleteError(e);
    } finally {
      setDeleting(false);
    }
  };

  const downloadSelected = async () => {
    setDownloading(true);
    setDlError(null);
    setDlReport(null);
    const report = [];
    try {
      const job = await getJob(effectiveSelected);
      const ids = FILE_TYPES.filter((t) => checked[t.id]);
      for (const t of ids) {
        const types = resolveDownloadTypes(t.id, job);
        if (types.length === 0) {
          report.push({ label: t.label, ok: false, message: 'Not produced for this experiment' });
          continue;
        }
        for (const type of types) {
          try {
            // eslint-disable-next-line no-await-in-loop
            await downloadJobFile(effectiveSelected, type);
            report.push({ label: `${t.label}${type.startsWith('neural_') ? ' (neural)' : types.length > 1 ? ' (classical)' : ''}`, ok: true });
          } catch (e) {
            report.push({ label: t.label, ok: false, message: e.message });
          }
        }
      }
      setDlReport(report);
    } catch (e) {
      setDlError(e);
    } finally {
      setDownloading(false);
    }
  };

  const anyChecked = FILE_TYPES.some((t) => checked[t.id]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Experiment History & Download"
        subtitle="Review past experiments and download their results."
        actions={<Button variant="primary" icon={Plus} to="/upload">New Experiment</Button>}
      />

      <Card
        title="Experiments"
        actions={<Select className="w-44" value={filter} onChange={setFilter} options={FILTERS} aria-label="Filter by status" />}
        bodyClassName="p-0"
      >
        {loading && !data ? (
          <div className="space-y-2 p-5"><Skeleton className="h-9" /><Skeleton className="h-9" /><Skeleton className="h-9" /></div>
        ) : error ? (
          <div className="p-5"><ErrorBanner error={error} title="Could not load experiments" onRetry={reload} /></div>
        ) : jobs.length === 0 ? (
          <div className="p-5">
            <EmptyState icon={FlaskConical} title="No experiments yet" action={<Button variant="primary" to="/upload">Start new experiment</Button>}>
              Finished and running experiments will be listed here.
            </EmptyState>
          </div>
        ) : visible.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-400">No experiments with status &quot;{filter}&quot;.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left">
              <thead className="border-b border-line">
                <tr>
                  <th className="th"><span className="sr-only">Select for download</span></th>
                  <th className="th">ID</th><th className="th">Date</th><th className="th">Object</th><th className="th">Views</th>
                  <th className="th">Method</th><th className="th">F-score</th><th className="th">Chamfer</th><th className="th">Status</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {visible.map((j) => (
                  <tr key={j.job_id} className={j.job_id === effectiveSelected ? 'bg-blue-500/5' : 'hover:bg-ink-700/40'}>
                    <td className="td">
                      <input
                        type="radio"
                        name="selected-job"
                        aria-label={`Select ${j.job_id} for download`}
                        checked={j.job_id === effectiveSelected}
                        onChange={() => setSelected(j.job_id)}
                        className="h-4 w-4 accent-blue-500"
                      />
                    </td>
                    <td className="td font-mono">
                      <Link to={j.status === 'queued' || j.status === 'processing' ? `/processing/${j.job_id}` : `/viewer/${j.job_id}`} className="text-blue-300 hover:underline">{j.job_id}</Link>
                      {j.project_name && <div className="max-w-[220px] truncate font-sans text-xs text-slate-400">{j.project_name}</div>}
                      {j.dataset && <div className="max-w-[220px] truncate font-sans text-xs text-slate-500" title={describeDataset(j.dataset, { lighting: true })}>{describeDataset(j.dataset)}</div>}
                    </td>
                    <td className="td whitespace-nowrap text-slate-300">{formatDate(j.created_at)}</td>
                    <td className="td">{j.object_category || 'n/a'}</td>
                    <td className="td font-mono">{j.num_views ?? j.image_count ?? 'n/a'}</td>
                    <td className="td">{METHOD_SHORT[j.recon_method] || titleCase(j.recon_method) || 'n/a'}</td>
                    <td className="td font-mono" title={j.f_score == null ? NOTE : undefined}>{formatMetric('f_score', j.f_score)}</td>
                    <td className="td font-mono" title={j.chamfer == null ? NOTE : undefined}>{formatMetric('chamfer_distance', j.chamfer)}</td>
                    <td className="td"><div className="flex flex-wrap items-center gap-1.5"><StatusBadge status={j.status} /><RemoteBadge job={j} /></div></td>
                    <td className="td">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" to={j.status === 'queued' || j.status === 'processing' ? `/processing/${j.job_id}` : `/viewer/${j.job_id}`} aria-label={`View ${j.job_id}`} title="View"><Eye className="h-4 w-4" /></Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Download ${j.job_id}`}
                          title="Choose files to download"
                          onClick={() => {
                            setSelected(j.job_id);
                            document.getElementById('downloads')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                          }}
                        ><Download className="h-4 w-4" /></Button>
                        <Button size="sm" variant="ghost" className="text-red-300 hover:bg-red-500/10 hover:text-red-200" aria-label={`Delete ${j.job_id}`} title="Delete" onClick={() => { setDeleteError(null); setToDelete(j); }}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card id="downloads" title="Download Results" subtitle={effectiveSelected ? `Experiment ${effectiveSelected}` : 'Select an experiment above'} className="scroll-mt-20">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FILE_TYPES.map((t) => (
            <Checkbox key={t.id} id={`dl-${t.id}`} label={t.label} checked={!!checked[t.id]} onChange={(v) => setChecked({ ...checked, [t.id]: v })} />
          ))}
        </div>
        {dlError && <ErrorBanner className="mt-4" error={dlError} title="Download failed" />}
        {dlReport && (
          <ul className="mt-4 space-y-1 text-sm" aria-live="polite">
            {dlReport.map((r, i) => (
              // eslint-disable-next-line react/no-array-index-key
              <li key={`${r.label}-${i}`} className={r.ok ? 'text-emerald-300' : 'text-red-300'}>
                {r.ok ? 'Downloaded' : 'Failed'}: {r.label}{r.message ? ` (${r.message})` : ''}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-5 flex justify-end">
          <Button variant="primary" size="lg" icon={Download} loading={downloading} disabled={!effectiveSelected || !anyChecked} onClick={downloadSelected}>
            Download Selected
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={!!toDelete}
        title="Delete experiment?"
        danger
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      >
        {toDelete && <p>This permanently removes <span className="font-mono text-white">{toDelete.job_id}</span> and its results. This cannot be undone.</p>}
        {deleteError && <Alert tone="error" className="mt-3" title="Delete failed">{deleteError.message}</Alert>}
      </ConfirmDialog>
    </div>
  );
}
