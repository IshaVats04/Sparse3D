import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Images } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Alert, ErrorBanner } from '../components/ui/Feedback';
import Dropzone from '../components/upload/Dropzone';
import ImageGrid from '../components/upload/ImageGrid';
import ValidationPanel from '../components/upload/ValidationPanel';
import DatasetPicker from '../components/upload/DatasetPicker';
import Segmented from '../components/ui/Segmented';
import { useWizard } from '../hooks/useUpload';
import { listExamples } from '../services/experimentService';
import { MAX_IMAGES, MIN_IMAGES } from '../utils/constants';

const GUIDELINES = [
  'Use 3 to 6 clear images',
  'Capture from different angles',
  'Ensure good lighting',
  'Keep the object in focus',
  'More overlap = better results',
];

export default function Upload() {
  const nav = useNavigate();
  const {
    files, exampleId, exampleName, exampleImages, imageCount, notices, validation, validating, validationError,
    addFiles, removeFile, clearAll, selectExample, dataset, setDataset,
  } = useWizard();
  const [source, setSource] = useState(dataset ? 'dataset' : 'upload');
  const [exLoading, setExLoading] = useState(false);
  const [exError, setExError] = useState(null);
  const [exChoices, setExChoices] = useState(null);

  const loadSamples = async () => {
    setExLoading(true);
    setExError(null);
    try {
      const list = await listExamples();
      if (!Array.isArray(list) || list.length === 0) {
        setExError(new Error('The backend has no bundled sample image sets.'));
      } else if (list.length === 1) {
        selectExample(list[0]);
      } else {
        setExChoices(list);
      }
    } catch (e) {
      setExError(e);
    } finally {
      setExLoading(false);
    }
  };

  const items = useMemo(() => {
    const byName = new Map(((validation && validation.images) || []).map((v) => [v.name, v]));
    const base = dataset
      ? (dataset.kind === 'dtu' ? dataset.thumbs : dataset.thumbs.slice(0, 12)).map((t) => ({ key: t.name, name: t.name, url: t.url, camera: t.camera }))
      : exampleId
        ? exampleImages.map((im) => ({ key: im.name, name: im.name, url: im.url }))
        : files.map((f) => ({ key: f.id, name: f.name, url: f.url }));
    return base.map((it) => {
      const v = byName.get(it.name);
      return v ? { ...it, status: v.status, issues: v.issues } : it;
    });
  }, [dataset, exampleId, exampleImages, files, validation]);

  const removeCamera = (key) => {
    const t = items.find((i) => i.key === key);
    if (!t || !dataset) return;
    setDataset({
      ...dataset,
      cameras: dataset.cameras.filter((c) => c !== t.camera),
      thumbs: dataset.thumbs.filter((x) => x.name !== key),
    });
  };

  const tooFew = imageCount < MIN_IMAGES;
  const blocked = validation && validation.can_proceed === false;
  const canNext = !tooFew && !blocked && !validating;
  const nextHint = tooFew
    ? `Add at least ${MIN_IMAGES} images to continue.`
    : blocked
      ? 'Resolve the image errors to continue.'
      : validating
        ? 'Checking images...'
        : '';

  return (
    <div>
      <PageHeader title="Upload Images" subtitle="Upload 3-6 images of your object from different viewpoints." />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Segmented
            label="Image source"
            value={source}
            onChange={setSource}
            options={[{ value: 'upload', label: 'Upload photos' }, { value: 'dataset', label: 'Local dataset' }]}
          />
          {source === 'dataset' ? (
            <Card bodyClassName="p-4">
              <DatasetPicker value={dataset} onChange={setDataset} />
            </Card>
          ) : (
          <>
          <Dropzone onFiles={addFiles} disabled={imageCount >= MAX_IMAGES && !exampleId && !dataset} />
          <div className="flex flex-wrap items-center gap-3">
            <Button icon={Images} loading={exLoading} onClick={loadSamples}>Use bundled sample set</Button>
            {exampleId && <span className="text-sm text-slate-300">Using sample set: <strong className="text-white">{exampleName}</strong></span>}
          </div>
          {exChoices && (
            <Card title="Choose a sample set" bodyClassName="p-3">
              <ul className="space-y-1">
                {exChoices.map((ex) => (
                  <li key={ex.id}>
                    <button
                      type="button"
                      onClick={() => { selectExample(ex); setExChoices(null); }}
                      className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-ink-700"
                    >
                      <span>{ex.name}</span>
                      <span className="text-xs text-slate-400">{(ex.images || []).length} images</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {exError && <ErrorBanner error={exError} title="Could not load sample sets" onRetry={loadSamples} />}
          {notices.length > 0 && (
            <Alert tone="warn" title="Some files were not added">
              <ul className="list-disc pl-4">{notices.map((n) => <li key={n}>{n}</li>)}</ul>
            </Alert>
          )}
          </>
          )}
        </div>

        <Card title="View Guidelines">
          <ul className="space-y-3">
            {GUIDELINES.map((g) => (
              <li key={g} className="flex items-start gap-2.5 text-sm text-slate-200">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
                {g}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card
        className="mt-6"
        title={`Uploaded Images (${imageCount}/${MAX_IMAGES})`}
        actions={imageCount > 0 && (
          <button type="button" onClick={clearAll} className="text-sm text-red-300 hover:text-red-200 hover:underline">Clear All</button>
        )}
      >
        {imageCount === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">No images yet. Drop files above, use the bundled sample set, or pick cameras from a local dataset.</p>
        ) : (
          <div className="space-y-6">
            {dataset && (
              <p className="text-sm text-slate-300">
                {dataset.datasetName} / {dataset.scanName}
                {dataset.kind === 'dtu' ? `, lighting ${dataset.lighting ?? 'n/a'}` : ''}
                {dataset.hasGroundTruth ? ' - reference model attached' : ''}
              </p>
            )}
            <ImageGrid
              items={items}
              max={MAX_IMAGES}
              onRemove={dataset ? (dataset.kind === 'dtu' ? removeCamera : undefined) : exampleId ? undefined : removeFile}
              onAdd={dataset || exampleId ? undefined : addFiles}
            />
            {dataset && dataset.kind !== 'dtu' && dataset.thumbs.length > 12 && (
              <p className="text-xs text-slate-400">Showing 12 of {dataset.thumbs.length} images.</p>
            )}
            {validationError && (
              <Alert tone="warn" title="Image validation is unavailable">
                {validationError.message} You can still continue, but problems with your images will not be flagged.
              </Alert>
            )}
            <ValidationPanel validation={validation} validating={validating} />
          </div>
        )}
      </Card>

      <div className="mt-6 flex flex-wrap items-center justify-end gap-4">
        {nextHint && <span className="text-sm text-slate-400" role="status">{nextHint}</span>}
        <Button variant="primary" size="lg" disabled={!canNext} iconRight={ArrowRight} onClick={() => nav('/configuration')}>Next</Button>
      </div>
    </div>
  );
}
