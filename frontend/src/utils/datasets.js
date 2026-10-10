import { MAX_IMAGES } from './constants';

/**
 * Client-side dataset selection shape (kept in the wizard context and the sweep panel):
 * { datasetId, datasetName, kind, scanId, scanName, cameras: number[] (capture order),
 *   lighting: number|null, hasGroundTruth, hasCameraPoses, defaultCameras: number[],
 *   imageCount, thumbs: [{camera, name, url}] (selected cameras, or all images for folders),
 *   useGroundTruth }
 */

/** Number of images the selection contributes (DTU: chosen cameras; folder: every image). */
export function datasetCount(ds) {
  if (!ds) return 0;
  return ds.kind === 'dtu' ? (ds.cameras || []).length : (ds.imageCount || 0);
}

/** Key that changes when anything affecting validation / the job changes. */
export function datasetKey(ds) {
  if (!ds) return '';
  return [ds.datasetId, ds.scanId, (ds.cameras || []).join(','), ds.lighting ?? ''].join('|');
}

/** `count` indices-spaced picks from `list` (keeps order). */
export function evenlySpaced(list, count = MAX_IMAGES) {
  if (list.length <= count) return [...list];
  const out = [];
  for (let i = 0; i < count; i += 1) out.push(list[Math.round((i * (list.length - 1)) / (count - 1))]);
  return [...new Set(out)];
}

/** "DTU Scan 1, cameras 1/9/17/25" from a job's `dataset` object (null when absent). */
export function describeDataset(d, { lighting = false } = {}) {
  if (!d) return null;
  const scan = d.scan && d.scan !== 'all' ? String(d.scan).replace(/^scan\s*(\d+)$/i, 'Scan $1') : '';
  const base = d.kind === 'dtu' ? `DTU ${scan}`.trim() : [d.name, scan].filter(Boolean).join(' ');
  const parts = [base];
  if (Array.isArray(d.cameras) && d.cameras.length) parts.push(`cameras ${d.cameras.join('/')}`);
  if (lighting && d.lighting !== null && d.lighting !== undefined) parts.push(`lighting ${d.lighting}`);
  return parts.join(', ');
}

/** "Vase_Experiment_01 (EXP-AB12CD) - DTU Scan 1, cameras 1/9/17/25" */
export function jobSubtitle(job) {
  if (!job) return '';
  const d = describeDataset(job.dataset);
  return `${job.project_name || job.job_id} (${job.job_id})${d ? ` - ${d}` : ''}`;
}
