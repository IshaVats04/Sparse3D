import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Database, RefreshCw } from 'lucide-react';
import Button from '../ui/Button';
import Select from '../ui/Select';
import Badge from '../ui/Badge';
import { Alert, EmptyState, ErrorBanner, Skeleton } from '../ui/Feedback';
import { useAsync } from '../../hooks/useAsync';
import { listDatasets, listScanImages } from '../../services/experimentService';
import { apiUrl } from '../../services/api';
import { evenlySpaced } from '../../utils/datasets';
import { MAX_IMAGES, MIN_IMAGES } from '../../utils/constants';

/**
 * Local-dataset picker. Controlled through `value` / `onChange` (a selection object, see utils/datasets.js),
 * so both the Upload wizard and the sweep panel can use it. Only 320 px thumbnails are ever requested.
 * `autoPick`: select evenly spaced default cameras as soon as a DTU scan is chosen.
 */
export default function DatasetPicker({ value, onChange, autoPick = false, maxCameras = MAX_IMAGES }) {
  const ds = useAsync(() => listDatasets(), []);
  const datasets = Array.isArray(ds.data) ? ds.data : [];
  const [datasetId, setDatasetId] = useState(value ? value.datasetId : '');
  const [scanId, setScanId] = useState(value ? value.scanId : '');
  const [lightingSel, setLightingSel] = useState(value ? value.lighting : null);
  const [notice, setNotice] = useState('');

  const dataset = datasets.find((d) => d.id === datasetId) || datasets[0] || null;
  const scan = dataset ? ((dataset.scans || []).find((s) => s.id === scanId) || (dataset.scans || [])[0] || null) : null;
  const dtu = !!dataset && dataset.kind === 'dtu';
  const lightings = scan && Array.isArray(scan.lightings) ? scan.lightings : [];
  const lighting = lightings.length ? (lightings.includes(lightingSel) ? lightingSel : (lightings.includes(0) ? 0 : lightings[0])) : null;

  const images = useAsync(
    () => (dataset && scan ? listScanImages(dataset.id, scan.id, { lighting, limit: 200 }) : Promise.resolve(null)),
    [dataset && dataset.id, scan && scan.id, lighting],
  );
  const imageList = useMemo(() => (Array.isArray(images.data) ? images.data : []), [images.data]);

  const sameScan = !!value && !!dataset && !!scan && value.datasetId === dataset.id && value.scanId === scan.id;
  const selected = sameScan ? value.cameras : [];

  const build = (cameras) => {
    const byCam = new Map(imageList.map((i) => [i.camera, i]));
    const thumbs = dtu
      ? cameras.map((c) => byCam.get(c)).filter(Boolean).map((i) => ({ camera: i.camera, name: i.name, url: i.url }))
      : imageList.map((i) => ({ camera: i.camera ?? null, name: i.name, url: i.url }));
    return {
      datasetId: dataset.id,
      datasetName: dataset.name,
      kind: dataset.kind,
      scanId: scan.id,
      scanName: scan.name,
      cameras: dtu ? cameras : [],
      lighting,
      hasGroundTruth: !!scan.has_ground_truth,
      hasCameraPoses: !!scan.has_camera_poses,
      defaultCameras: scan.default_cameras || [],
      imageCount: scan.image_count || imageList.length,
      thumbs,
      useGroundTruth: true,
    };
  };

  // When the scan/lighting changes (or the thumbnails arrive), publish a selection for it.
  useEffect(() => {
    if (!dataset || !scan || images.loading || !Array.isArray(images.data)) return;
    if (sameScan && value.lighting === lighting) return;
    const cams = sameScan ? value.cameras : (dtu && autoPick ? evenlySpaced(scan.default_cameras || [], maxCameras) : []);
    onChange(build(cams));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [images.data, dataset && dataset.id, scan && scan.id, lighting]);

  const toggle = (camera) => {
    setNotice('');
    if (selected.includes(camera)) {
      onChange(build(selected.filter((c) => c !== camera)));
    } else if (selected.length >= maxCameras) {
      setNotice(`At most ${maxCameras} cameras can be selected. Deselect one first.`);
    } else {
      onChange(build([...selected, camera]));
    }
  };
  const pickSpaced = () => {
    setNotice('');
    onChange(build(evenlySpaced(scan.default_cameras || [], maxCameras)));
  };

  if (ds.loading && !ds.data) return <div className="space-y-3"><Skeleton className="h-12" /><Skeleton className="h-48" /></div>;
  if (ds.error) return <ErrorBanner error={ds.error} title="Could not load local datasets" onRetry={ds.reload} />;
  if (datasets.length === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No local datasets found"
        action={(
          <div className="flex flex-wrap justify-center gap-2">
            <Button icon={RefreshCw} onClick={ds.reload}>Check again</Button>
            <Button to="/settings">Open Settings</Button>
          </div>
        )}
      >
        The backend scans the folders in the SPARSE3D_DATASET_DIR environment variable (separate several with ; on Windows or : elsewhere),
        plus data/datasets and data/samples. Add a dataset there (for example the DTU MVS data) and restart the backend. You can check
        which backend you are connected to in <Link to="/settings" className="underline">Settings</Link>.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Select
          label="Dataset"
          value={dataset.id}
          onChange={(v) => { setDatasetId(v); setScanId(''); setNotice(''); }}
          options={datasets.map((d) => ({ value: d.id, label: d.name }))}
        />
        <Select
          label="Scan"
          value={scan ? scan.id : ''}
          onChange={(v) => { setScanId(v); setNotice(''); }}
          options={(dataset.scans || []).map((s) => ({ value: s.id, label: `${s.name} (${s.image_count} images)` }))}
        />
        {lightings.length > 0 && (
          <Select
            label="Lighting"
            value={String(lighting)}
            onChange={(v) => { setLightingSel(Number(v)); setNotice(''); }}
            options={lightings.map((l) => ({ value: String(l), label: `Lighting ${l}` }))}
          />
        )}
      </div>

      {scan && (
        <div className="flex flex-wrap items-center gap-2">
          {scan.has_ground_truth && <Badge tone="green" dot>Ground truth</Badge>}
          {scan.has_camera_poses && <Badge tone="blue" dot>Known camera poses</Badge>}
          {!scan.has_ground_truth && <Badge tone="slate">No reference model</Badge>}
        </div>
      )}

      {dtu ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-300">
              Select {MIN_IMAGES} to {maxCameras} cameras. Click again to deselect; the number is the capture order.
              {' '}<strong className="text-white">{selected.length}</strong> selected
              {selected.length > 0 && <span className="font-mono text-slate-400"> (cameras {selected.join(', ')})</span>}
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={pickSpaced} disabled={!(scan && scan.default_cameras && scan.default_cameras.length)} title="Apply the scan's default, evenly spaced cameras">
                Pick evenly spaced
              </Button>
              <Button size="sm" variant="ghost" onClick={() => onChange(build([]))} disabled={selected.length === 0}>Clear selection</Button>
            </div>
          </div>
          {notice && <Alert tone="warn">{notice}</Alert>}
          {images.error ? (
            <ErrorBanner error={images.error} title="Could not load thumbnails" onRetry={images.reload} />
          ) : images.loading && !images.data ? (
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 lg:grid-cols-8">{Array.from({ length: 16 }, (_, i) => <Skeleton key={i} className="aspect-square" />)}</div>
          ) : (
            <ul className="grid max-h-[440px] grid-cols-4 gap-3 overflow-y-auto pr-1 sm:grid-cols-6 lg:grid-cols-8" aria-label="Cameras">
              {imageList.map((im) => {
                const idx = selected.indexOf(im.camera);
                const on = idx >= 0;
                return (
                  <li key={im.name}>
                    <button
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(im.camera)}
                      title={`Camera ${im.camera}`}
                      className={`relative block aspect-square w-full overflow-hidden rounded-lg border-2 bg-ink-900 transition
                        ${on ? 'border-brand-blue shadow-glow' : 'border-line hover:border-line-strong'}`}
                    >
                      <img src={apiUrl(im.url)} alt={`Camera ${im.camera}`} loading="lazy" className="h-full w-full object-cover" />
                      {on && (
                        <span className="absolute left-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-brand-blue text-xs font-bold text-white">{idx + 1}</span>
                      )}
                      <span className="absolute bottom-0 inset-x-0 bg-black/60 py-0.5 text-center text-[10px] text-slate-200">Cam {im.camera}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-slate-300">
            This folder has {scan ? scan.image_count : imageList.length} images. All of them are available to the experiment; on the Configuration page,
            choose a view count and arrangement to use a subset.
          </p>
          {!value && <Button size="sm" onClick={() => onChange(build([]))}>Use this folder</Button>}
          {images.error ? (
            <ErrorBanner error={images.error} title="Could not load thumbnails" onRetry={images.reload} />
          ) : (
            <ul className="grid max-h-[300px] grid-cols-4 gap-3 overflow-y-auto sm:grid-cols-6 lg:grid-cols-8">
              {imageList.map((im) => (
                <li key={im.name} title={im.name}>
                  <img src={apiUrl(im.url)} alt={im.name} loading="lazy" className="aspect-square w-full rounded-lg border border-line object-cover" />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
