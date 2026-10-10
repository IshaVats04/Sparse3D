import { request, requestBlob, saveBlob, apiUrl } from './api';
import { FILE_TYPES } from '../utils/constants';
import { appendDatasetFields } from './experimentService';

export function getHealth({ signal } = {}) {
  return request('/api/health', { signal });
}

/** POST /api/jobs from the wizard state. Returns {job_id, status, message}. */
export function startReconstruction({ files = [], exampleId = null, dataset = null, config, groundTruth = null }) {
  const fd = new FormData();
  if (dataset) {
    // An explicitly chosen reference model overrides the dataset's own.
    appendDatasetFields(fd, { ...dataset, useGroundTruth: !groundTruth });
  } else if (exampleId) fd.append('example_id', exampleId);
  else files.forEach((f) => fd.append('images', f, f.name));
  const c = config;
  fd.append('project_name', (c.project_name || 'Experiment').trim() || 'Experiment');
  fd.append('object_category', c.object_category);
  fd.append('recon_method', c.recon_method);
  fd.append('num_views', String(c.num_views));
  fd.append('view_arrangement', c.view_arrangement);
  fd.append('quality', c.quality);
  fd.append('estimate_poses', String(!!c.estimate_poses));
  fd.append('run_evaluation', String(!!c.run_evaluation));
  fd.append('generate_mesh', String(!!c.generate_mesh));
  fd.append('save_intermediate', String(!!c.save_intermediate));
  fd.append('mesh_method', c.generate_mesh ? c.mesh_method : 'none');
  if (groundTruth) fd.append('ground_truth', groundTruth, groundTruth.name);
  return request('/api/jobs', { method: 'POST', formData: fd });
}

export function fileUrl(jobId, type) {
  return apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/files/${type}`);
}

const EXT_BY_TYPE = {
  point_cloud: 'ply', mesh: 'ply', neural_point_cloud: 'ply', neural_mesh: 'ply',
  report: 'json', metrics_csv: 'csv', camera_poses: 'txt',
};

/** Download a job file through fetch so failures surface as errors instead of a blank tab. */
export async function downloadJobFile(jobId, type) {
  const { blob, filename } = await requestBlob(`/api/jobs/${encodeURIComponent(jobId)}/files/${type}`);
  saveBlob(blob, filename || `${jobId}_${type}.${EXT_BY_TYPE[type] || 'bin'}`);
}

/**
 * Which concrete file_type values to fetch for a download-card checkbox, given the job
 * (so we only request what exists). Without a job we fall back to the base type.
 */
export function resolveDownloadTypes(typeId, job) {
  const def = FILE_TYPES.find((t) => t.id === typeId);
  if (!def) return [];
  if (!job || !def.resultKey) return [typeId];
  const out = [];
  const c = job.results && job.results.classical;
  const n = job.results && job.results.neural;
  if (c && c.files && c.files[def.resultKey]) out.push(typeId);
  if (def.neuralType && n && n.files && n.files[def.resultKey]) out.push(def.neuralType);
  return out;
}

// ---------- execution target (local machine / remote Colab GPU worker) ----------
export function getExecution({ signal } = {}) {
  return request('/api/execution', { signal });
}

/** PUT /api/execution. `connection_code` is optional (omit to keep the current worker). */
export function setExecution({ mode, connection_code: code }) {
  const body = { mode };
  if (code) body.connection_code = code;
  return request('/api/execution', { method: 'PUT', json: body });
}

export function disconnectWorker() {
  return request('/api/execution/remote', { method: 'DELETE' });
}
