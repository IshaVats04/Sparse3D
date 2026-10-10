import { useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Cloud, FileBox, Images, Lightbulb, X } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Select from '../components/ui/Select';
import Toggle from '../components/ui/Toggle';
import { Alert, EmptyState, ErrorBanner } from '../components/ui/Feedback';
import ImageGrid from '../components/upload/ImageGrid';
import { useWizard } from '../hooks/useUpload';
import { useHealth } from '../hooks/useHealth';
import { useExecution, targetLabel } from '../hooks/useExecution';
import { startReconstruction } from '../services/reconstructionService';
import { apiUrl } from '../services/api';
import {
  ARRANGEMENTS, GT_ACCEPT, MAX_IMAGES, METHODS, MESH_METHODS, MIN_IMAGES, OBJECT_CATEGORIES, QUALITIES,
} from '../utils/constants';

export default function Configuration() {
  const nav = useNavigate();
  const {
    files, exampleId, exampleImages, dataset, imageCount, config, setConfig, groundTruth, setGroundTruth, setJobId,
  } = useWizard();
  const { health, error: healthError } = useHealth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const gtRef = useRef(null);

  const { data: exec, error: execError } = useExecution();
  // Capabilities of the effective execution target; fall back to /api/health when /api/execution is unavailable.
  const env = health && health.environment;
  const caps = exec ? exec.capabilities : env ? { neural_available: env.neural_available, neural_reason: env.neural_reason } : null;
  const neuralOk = !caps || caps.neural_available !== false;
  const neuralReason = (caps && caps.neural_reason) || 'Neural reconstruction is not available on this execution target.';
  const workerConnected = !!(exec && exec.remote && exec.remote.connected);
  const showGpuHint = !!exec && exec.effective === 'local' && !(exec.local && exec.local.gpu) && !workerConnected;

  const viewOptions = useMemo(() => {
    const max = Math.min(MAX_IMAGES, imageCount);
    const out = [];
    for (let n = MIN_IMAGES; n <= Math.max(max, MIN_IMAGES); n += 1) out.push({ value: String(n), label: `${n} views` });
    return out;
  }, [imageCount]);

  const thumbs = useMemo(() => (dataset
    ? dataset.thumbs.slice(0, 12).map((t) => ({ key: t.name, name: t.camera != null ? `Camera ${t.camera}` : t.name, url: t.url }))
    : exampleId
      ? exampleImages.map((im) => ({ key: im.name, name: im.name, url: im.url }))
      : files.map((f) => ({ key: f.id, name: f.name, url: f.url }))), [dataset, exampleId, exampleImages, files]);

  if (imageCount < MIN_IMAGES) {
    return (
      <div>
        <PageHeader title="Experiment Configuration" subtitle="Set parameters for reconstruction and evaluation." />
        <EmptyState
          icon={Images}
          title="No images selected"
          action={<Button variant="primary" to="/upload">Go to Upload</Button>}
        >
          Choose between {MIN_IMAGES} and {MAX_IMAGES} images (or the bundled sample set) before configuring the experiment.
        </EmptyState>
      </div>
    );
  }

  const arrangement = ARRANGEMENTS.find((a) => a.value === config.view_arrangement) || ARRANGEMENTS[0];
  const auto = config.view_arrangement === 'auto';
  const method = config.recon_method;
  const effectiveMethod = !neuralOk && method !== 'classical' ? 'classical' : method;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await startReconstruction({
        files: files.map((f) => f.file),
        exampleId,
        dataset,
        config: { ...config, recon_method: effectiveMethod },
        groundTruth,
      });
      setJobId(res.job_id);
      nav(`/processing/${res.job_id}`);
    } catch (e) {
      setError(e);
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader title="Experiment Configuration" subtitle="Set parameters for reconstruction and evaluation." />

      {(execError || healthError) && !caps && (
        <Alert tone="warn" className="mb-4" title="Backend capabilities unknown">
          {(execError || healthError).message} Method availability could not be checked; the backend will report unavailable methods in the results.
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Basic Settings">
          <div className="space-y-5">
            <Input
              label="Project Name"
              value={config.project_name}
              maxLength={80}
              onChange={(e) => setConfig({ project_name: e.target.value })}
              placeholder="Vase_Experiment_01"
            />
            <div className="grid gap-5 sm:grid-cols-2">
              <Select
                label="Number of Views"
                value={String(config.num_views)}
                disabled={auto}
                onChange={(v) => setConfig({ num_views: Number(v) })}
                options={viewOptions}
                helper={auto ? `Auto uses all ${imageCount} images.` : `Subset chosen from ${imageCount} images by the arrangement.`}
              />
              <Select
                label="View Arrangement"
                value={config.view_arrangement}
                onChange={(v) => setConfig({ view_arrangement: v })}
                options={ARRANGEMENTS.map((a) => ({ value: a.value, label: a.label }))}
                helper={arrangement.help}
              />
            </div>

            <div>
              <div className="label">Selected images ({imageCount})</div>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {thumbs.map((t) => (
                  <div key={t.key} className="h-14 w-14 shrink-0 overflow-hidden rounded-md border border-line bg-ink-900" title={t.name}>
                    {t.url ? <img src={apiUrl(t.url)} alt={t.name} className="h-full w-full object-cover" /> : (
                      <div className="flex h-full items-center justify-center text-[9px] text-slate-500">No preview</div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Select
                label="Object Category"
                value={config.object_category}
                onChange={(v) => setConfig({ object_category: v })}
                options={OBJECT_CATEGORIES}
              />
              <Select
                label="Reconstruction Quality"
                value={config.quality}
                onChange={(v) => setConfig({ quality: v })}
                options={QUALITIES}
                helper="Higher quality = more time"
              />
            </div>
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Reconstruction Methods">
            <div role="radiogroup" aria-label="Reconstruction method" className="space-y-3">
              {METHODS.map((m) => {
                const disabled = m.value !== 'classical' && !neuralOk;
                const selected = effectiveMethod === m.value;
                return (
                  <button
                    key={m.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    disabled={disabled}
                    onClick={() => setConfig({ recon_method: m.value })}
                    className={`flex w-full items-start gap-3 rounded-xl border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-55
                      ${selected ? 'border-brand-blue bg-blue-500/10 shadow-glow' : 'border-line bg-ink-900/60 hover:border-line-strong'}`}
                  >
                    <span className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 ${selected ? 'border-brand-blue' : 'border-slate-500'}`}>
                      {selected && <span className="h-2 w-2 rounded-full bg-brand-blue" />}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-white">{m.title}</span>
                      <span className="block text-xs text-slate-400">{m.desc}</span>
                      {m.value !== 'classical' && !neuralOk && (
                        <span className="mt-1.5 block text-xs text-amber-300">Unavailable: {neuralReason}</span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          <Card title="Advanced Settings" bodyClassName="px-5 py-2">
            <div className="divide-y divide-line-soft">
              <Toggle label="Estimate Camera Poses" checked={config.estimate_poses} onChange={(v) => setConfig({ estimate_poses: v })} />
              <Toggle label="Run Evaluation Metrics" checked={config.run_evaluation} onChange={(v) => setConfig({ run_evaluation: v })} />
              <div>
                <Toggle label="Generate Mesh (Textured)" checked={config.generate_mesh} onChange={(v) => setConfig({ generate_mesh: v })} />
                {config.generate_mesh && (
                  <div className="pb-3">
                    <Select
                      label="Mesh method"
                      value={config.mesh_method === 'none' ? 'poisson' : config.mesh_method}
                      onChange={(v) => setConfig({ mesh_method: v })}
                      options={MESH_METHODS.filter((m) => m.value !== 'none')}
                    />
                  </div>
                )}
              </div>
              <Toggle label="Save Intermediate Results" checked={config.save_intermediate} onChange={(v) => setConfig({ save_intermediate: v })} />
              <div className="py-3">
                <div className="text-sm font-medium text-slate-100">Ground-truth model (.ply/.obj/.stl)</div>
                <p className="mt-0.5 text-xs text-slate-400">
                  {dataset && dataset.hasGroundTruth
                    ? (groundTruth
                      ? "Your file replaces the dataset's reference model."
                      : "Using the dataset's reference model. Choosing a file here is optional and replaces it.")
                    : 'Optional. Needed for Chamfer distance, F-score, completeness and accuracy; without it those show as n/a.'}
                </p>
                {dataset && dataset.hasGroundTruth && !groundTruth && (
                  <p className="mt-1.5 inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs text-emerald-300">
                    Using the dataset&apos;s reference model
                  </p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input
                    ref={gtRef}
                    type="file"
                    accept={GT_ACCEPT}
                    className="hidden"
                    onChange={(e) => { setGroundTruth(e.target.files[0] || null); e.target.value = ''; }}
                  />
                  <Button size="sm" icon={FileBox} onClick={() => gtRef.current?.click()}>{groundTruth ? 'Replace file' : 'Choose file'}</Button>
                  {groundTruth && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-ink-900 px-3 py-1 text-xs text-slate-200">
                      {groundTruth.name}
                      <button type="button" aria-label="Remove ground-truth file" onClick={() => setGroundTruth(null)} className="text-slate-400 hover:text-red-300">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  )}
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {exec && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-ink-800/80 px-4 py-3" role="status">
          <div className="flex min-w-0 items-start gap-3">
            <Cloud className="mt-0.5 h-5 w-5 shrink-0 text-slate-400" aria-hidden />
            <div className="min-w-0">
              <div className="text-sm text-slate-200">Runs on: <strong className="text-white">{targetLabel(exec)}</strong></div>
              {exec.reason && <div className="text-xs text-slate-400">{exec.reason}</div>}
            </div>
          </div>
          <Link to="/settings" className="text-sm text-blue-300 hover:underline">Change</Link>
        </div>
      )}
      {showGpuHint && (
        <p className="mt-3 flex items-start gap-2 text-sm text-slate-400">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden />
          <span>Dense reconstruction and the neural method are faster on a GPU: <Link to="/settings" className="text-blue-300 underline">connect a Colab worker</Link>.</span>
        </p>
      )}

      {error && <ErrorBanner className="mt-6" error={error} title="Could not start the reconstruction" />}

      <div className="mt-6 flex justify-between gap-3">
        <Button icon={ArrowLeft} to="/upload" disabled={submitting}>Back</Button>
        <Button variant="primary" size="lg" iconRight={ArrowRight} loading={submitting} onClick={submit}>Start Reconstruction</Button>
      </div>
    </div>
  );
}
