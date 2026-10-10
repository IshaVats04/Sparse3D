import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileBox, Play, X } from 'lucide-react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Checkbox from '../ui/Checkbox';
import Segmented from '../ui/Segmented';
import { Alert, ErrorBanner } from '../ui/Feedback';
import Dropzone from '../upload/Dropzone';
import ImageGrid from '../upload/ImageGrid';
import DatasetPicker from '../upload/DatasetPicker';
import { datasetCount } from '../../utils/datasets';
import { useExamples } from '../../hooks/useUpload';
import { startSweep } from '../../services/experimentService';
import {
  ARRANGEMENTS, GT_ACCEPT, IMAGE_EXTENSIONS, MAX_IMAGES, MAX_IMAGE_BYTES, METHODS, OBJECT_CATEGORIES, QUALITIES,
  VIEW_COUNT_OPTIONS,
} from '../../utils/constants';
import { fileExt, formatBytes } from '../../utils/formatters';

let uid = 0;

/** Run a view-count sweep: POST /api/experiments/sweep, then link to the group's jobs. */
export default function SweepPanel({ onStarted }) {
  const { examples, loading: exLoading, error: exError, reload } = useExamples();
  const [source, setSource] = useState('example');
  const [exampleId, setExampleId] = useState('');
  const [dataset, setDataset] = useState(null);
  const [files, setFiles] = useState([]); // [{id, file, url, name}]
  const [notices, setNotices] = useState([]);
  const [viewCounts, setViewCounts] = useState([3, 4, 5, 6]);
  const [arrangements, setArrangements] = useState(['uniform']);
  const [method, setMethod] = useState('both');
  const [quality, setQuality] = useState('standard');
  const [category, setCategory] = useState('General Object');
  const [name, setName] = useState('Sweep');
  const [gt, setGt] = useState(null);
  const gtRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!exampleId && examples.length) setExampleId(examples[0].id);
  }, [examples, exampleId]);

  const urls = useRef(new Set());
  useEffect(() => {
    const u = urls.current;
    return () => { u.forEach((x) => URL.revokeObjectURL(x)); u.clear(); };
  }, []);

  const addFiles = (incoming) => {
    const msgs = [];
    const next = [...files];
    Array.from(incoming || []).forEach((file) => {
      const ext = fileExt(file.name);
      if (!IMAGE_EXTENSIONS.includes(ext)) { msgs.push(`"${file.name}" is not a supported image type.`); return; }
      if (file.size > MAX_IMAGE_BYTES) { msgs.push(`"${file.name}" is ${formatBytes(file.size)} (limit 10 MB).`); return; }
      if (next.some((f) => f.name === file.name && f.file.size === file.size)) { msgs.push(`"${file.name}" was already added.`); return; }
      if (next.length >= MAX_IMAGES) { msgs.push(`Maximum ${MAX_IMAGES} images: "${file.name}" not added.`); return; }
      const url = URL.createObjectURL(file);
      if (url) urls.current.add(url);
      uid += 1;
      next.push({ id: `s${uid}`, file, name: file.name, url });
    });
    setFiles(next);
    setNotices(msgs);
  };
  const removeFile = (id) => {
    const t = files.find((f) => f.id === id);
    if (t && t.url) { URL.revokeObjectURL(t.url); urls.current.delete(t.url); }
    setFiles(files.filter((f) => f.id !== id));
  };

  const example = examples.find((e) => e.id === exampleId);
  const available = source === 'dataset' ? datasetCount(dataset) : source === 'example' ? (example ? (example.images || []).length : 0) : files.length;
  const maxViews = viewCounts.length ? Math.max(...viewCounts) : 0;

  const toggle = (list, setList, v) => setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const problem = useMemo(() => {
    if (source === 'example' && exLoading) return 'Loading sample sets...';
    if (viewCounts.length === 0) return 'Choose at least one view count.';
    if (arrangements.length === 0) return 'Choose at least one arrangement.';
    if (available < maxViews) return `The sweep needs at least ${maxViews} ${source === 'dataset' ? 'cameras selected' : 'images'}; ${source === 'example' ? 'this sample set has' : source === 'dataset' ? 'you have selected' : 'you have added'} ${available}.`;
    return null;
  }, [viewCounts, arrangements, available, maxViews, source, exLoading]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const sortedViews = [...viewCounts].sort((a, b) => a - b);
      const res = await startSweep({
        fields: {
          project_name: name || 'Sweep',
          object_category: category,
          recon_method: method,
          quality,
          view_counts: sortedViews.join(','),
          arrangements: arrangements.join(','),
          view_arrangement: arrangements[0],
        },
        files: files.map((f) => f.file),
        exampleId: source === 'example' ? exampleId : null,
        dataset: source === 'dataset' && dataset ? { ...dataset, useGroundTruth: !gt } : null,
        groundTruth: gt,
      });
      setResult(res);
      if (onStarted) onStarted(res);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      id="sweep"
      title="Run view-count sweep"
      subtitle="Reconstruct the same object with different numbers of views and arrangements, then compare the results."
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <div>
            <div className="label">Images</div>
            <Segmented
              label="Image source"
              value={source}
              onChange={setSource}
              options={[{ value: 'example', label: 'Sample set' }, { value: 'upload', label: 'Upload images' }, { value: 'dataset', label: 'Local dataset' }]}
            />
          </div>
          {source === 'dataset' ? (
            <DatasetPicker value={dataset} onChange={setDataset} autoPick />
          ) : source === 'example' ? (
            exError ? (
              <ErrorBanner error={exError} title="Could not load sample sets" onRetry={reload} />
            ) : (
              <Select
                label="Sample set"
                value={exampleId}
                onChange={setExampleId}
                disabled={exLoading || examples.length === 0}
                options={examples.length ? examples.map((e) => ({ value: e.id, label: `${e.name} (${(e.images || []).length} images)` })) : [{ value: '', label: exLoading ? 'Loading...' : 'No sample sets available' }]}
              />
            )
          ) : (
            <div className="space-y-3">
              <Dropzone compact onFiles={addFiles} disabled={files.length >= MAX_IMAGES} hint="Upload at least as many images as your largest view count" />
              {files.length > 0 && <ImageGrid items={files.map((f) => ({ key: f.id, name: f.name, url: f.url }))} onRemove={removeFile} max={MAX_IMAGES} />}
              {notices.length > 0 && <Alert tone="warn">{notices.join(' ')}</Alert>}
            </div>
          )}
          <Input label="Project name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Object category" value={category} onChange={setCategory} options={OBJECT_CATEGORIES} />
            <Select label="Quality" value={quality} onChange={setQuality} options={QUALITIES} />
          </div>
        </div>

        <div className="space-y-4">
          <fieldset>
            <legend className="label">View counts</legend>
            <div className="flex flex-wrap gap-4">
              {VIEW_COUNT_OPTIONS.map((n) => (
                <Checkbox key={n} id={`sw-v-${n}`} label={`${n} views`} checked={viewCounts.includes(n)} onChange={() => toggle(viewCounts, setViewCounts, n)} />
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="label">Arrangements</legend>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {ARRANGEMENTS.map((a) => (
                <Checkbox key={a.value} id={`sw-a-${a.value}`} label={a.label} checked={arrangements.includes(a.value)} onChange={() => toggle(arrangements, setArrangements, a.value)} />
              ))}
            </div>
          </fieldset>
          <Select label="Method" value={method} onChange={setMethod} options={METHODS.map((m) => ({ value: m.value, label: m.title }))} />
          <div>
            <div className="label">Ground-truth model (optional)</div>
            <div className="flex flex-wrap items-center gap-2">
              <input ref={gtRef} type="file" accept={GT_ACCEPT} className="hidden" onChange={(e) => { setGt(e.target.files[0] || null); e.target.value = ''; }} />
              <Button size="sm" icon={FileBox} onClick={() => gtRef.current?.click()}>{gt ? 'Replace file' : 'Choose file'}</Button>
              {gt && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-ink-900 px-3 py-1 text-xs">
                  {gt.name}
                  <button type="button" aria-label="Remove ground-truth file" onClick={() => setGt(null)}><X className="h-3.5 w-3.5 text-slate-400 hover:text-red-300" /></button>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {error && <ErrorBanner className="mt-5" error={error} title="Could not start the sweep" />}
      {result && (
        <Alert tone="ok" className="mt-5" title={`Sweep ${result.group_id} started (${(result.job_ids || []).length} experiments)`}>
          <div className="mt-1 flex flex-wrap gap-2">
            {(result.job_ids || []).map((id) => (
              <Link key={id} to={`/processing/${id}`} className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-xs hover:bg-emerald-500/20">{id}</Link>
            ))}
          </div>
          <div className="mt-2">
            <Link to={`/analysis?group=${encodeURIComponent(result.group_id)}`} className="text-sm underline">View this group&apos;s analysis</Link>
            <span className="text-xs opacity-80"> (charts fill in as experiments finish)</span>
          </div>
        </Alert>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-end gap-3">
        {problem && <span className="text-sm text-amber-300" role="status">{problem}</span>}
        <Button variant="primary" icon={Play} loading={busy} disabled={!!problem} onClick={submit}>Run sweep</Button>
      </div>
    </Card>
  );
}
