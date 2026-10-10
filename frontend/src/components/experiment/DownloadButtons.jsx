import { useState } from 'react';
import { Download } from 'lucide-react';
import Button from '../ui/Button';
import { Alert } from '../ui/Feedback';
import { FILE_TYPES } from '../../utils/constants';
import { downloadJobFile, resolveDownloadTypes } from '../../services/reconstructionService';

/** Per-file download buttons for one job. Shows errors instead of swallowing them. */
export default function DownloadButtons({ job }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  if (!job) return null;

  const run = async (typeId) => {
    setBusy(typeId);
    setError(null);
    try {
      const types = resolveDownloadTypes(typeId, job);
      if (types.length === 0) throw new Error('This file was not produced for the experiment.');
      for (const t of types) {
        // eslint-disable-next-line no-await-in-loop
        await downloadJobFile(job.job_id, t);
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {FILE_TYPES.map((t) => {
          const available = resolveDownloadTypes(t.id, job).length > 0;
          return (
            <Button
              key={t.id}
              size="sm"
              icon={Download}
              loading={busy === t.id}
              disabled={!available}
              title={available ? undefined : 'Not produced for this experiment'}
              onClick={() => run(t.id)}
            >
              {t.label}
            </Button>
          );
        })}
      </div>
      {error && <Alert tone="error" title="Download failed" onDismiss={() => setError(null)}>{error.message}</Alert>}
    </div>
  );
}
