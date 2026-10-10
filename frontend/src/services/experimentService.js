import { request } from './api';

/** Append the local-dataset form fields (dataset_id, scan_id, cameras, lighting, use_dataset_ground_truth). */
export function appendDatasetFields(fd, ds) {
  fd.append('dataset_id', ds.datasetId);
  fd.append('scan_id', ds.scanId);
  if (ds.cameras && ds.cameras.length) fd.append('cameras', ds.cameras.join(','));
  if (ds.lighting !== null && ds.lighting !== undefined) fd.append('lighting', String(ds.lighting));
  fd.append('use_dataset_ground_truth', String(ds.useGroundTruth !== false));
}

export function listDatasets() {
  return request('/api/datasets');
}

/** Thumbnails of one scan (optionally one lighting condition). Never loads full-size images. */
export function listScanImages(datasetId, scanId, { lighting = null, limit = 200, signal } = {}) {
  const q = new URLSearchParams();
  if (lighting !== null && lighting !== undefined) q.set('lighting', String(lighting));
  q.set('limit', String(limit));
  return request(`/api/datasets/${encodeURIComponent(datasetId)}/${encodeURIComponent(scanId)}/images?${q}`, { signal });
}

export function listExamples() {
  return request('/api/examples');
}

/** Validate uploaded files (File[]) or a bundled example set. */
export function validateImages({ files = [], exampleId = null, dataset = null, signal } = {}) {
  const fd = new FormData();
  if (dataset) appendDatasetFields(fd, dataset);
  else if (exampleId) fd.append('example_id', exampleId);
  else files.forEach((f) => fd.append('images', f, f.name));
  return request('/api/validate', { method: 'POST', formData: fd, signal });
}

export function listJobs() {
  return request('/api/jobs');
}

export function getJob(jobId, { signal } = {}) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`, { signal });
}

export function deleteJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
}

export function cancelJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
}

export function getReport(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/report`);
}

/**
 * Sweep: same fields as POST /api/jobs plus view_counts and arrangements.
 * `fields` is a plain object; `files` File[]; `groundTruth` optional File.
 */
export function startSweep({ fields = {}, files = [], exampleId = null, dataset = null, groundTruth = null }) {
  const fd = new FormData();
  Object.entries(fields).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') fd.append(k, String(v));
  });
  if (dataset) appendDatasetFields(fd, dataset);
  else if (exampleId) fd.append('example_id', exampleId);
  else files.forEach((f) => fd.append('images', f, f.name));
  if (groundTruth) fd.append('ground_truth', groundTruth, groundTruth.name);
  return request('/api/experiments/sweep', { method: 'POST', formData: fd });
}
