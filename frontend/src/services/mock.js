// Mock backend for viewing the UI without the FastAPI server.
// Enabled with `?mock=1` (remembered for the browser session; `?mock=0` turns it off) or VITE_MOCK=1.
// This is the ONLY place sample numbers live. They are illustrative, not measurements.
import { ApiError } from './api';

const TOTAL_SEC = 14; // simulated run length
const STAGES = [
  { key: 'image_analysis', label: 'Image Analysis', from: 0, to: 2 },
  { key: 'feature_extraction', label: 'Feature Extraction', from: 2, to: 5 },
  { key: 'camera_pose', label: 'Camera Pose Estimation', from: 5, to: 8 },
  { key: 'reconstruction', label: '3D Reconstruction', from: 8, to: 12 },
  { key: 'evaluation', label: 'Evaluation', from: 12, to: 14 },
];

const delay = (ms = 120) => new Promise((r) => { setTimeout(r, ms); });
const pad = (n) => String(n).padStart(2, '0');
function stamp(ms) {
  const d = new Date(ms);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function clock(ms) {
  const d = new Date(ms);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// ---------- images ----------
function svgImage(i, label) {
  const hue = (i * 47 + 200) % 360;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${hue},55%,28%)"/><stop offset="1" stop-color="hsl(${(hue + 50) % 360},60%,16%)"/></linearGradient></defs>
  <rect width="320" height="320" fill="url(#g)"/>
  <g transform="rotate(${(i - 3) * 9} 160 170)"><path d="M135 60h50l-4 34c28 18 38 46 34 78-4 34-24 58-55 72-31-14-51-38-55-72-4-32 6-60 34-78z" fill="hsl(${hue},45%,62%)" opacity="0.9"/></g>
  <text x="14" y="302" font-family="monospace" font-size="16" fill="#e2e8f0">${label}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
const EXAMPLE = {
  id: 'dtu_scan1_6views',
  name: 'DTU scan1 (6 views, mock)',
  images: [1, 2, 3, 4, 5, 6].map((i) => ({ name: `image_00${i}.png`, url: svgImage(i, `view ${i}`) })),
};

// ---------- local datasets (fake DTU + a plain folder) ----------
const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
const DTU = {
  id: 'dtu-mock', kind: 'dtu', name: 'DTU MVS (mock)',
  scans: [
    { id: 'scan1', name: 'Scan 1', image_count: 49 * 3, cameras: range(1, 49), lightings: [0, 1, 2], has_ground_truth: true, has_camera_poses: true, default_cameras: [1, 10, 20, 30, 40, 49] },
    { id: 'scan4', name: 'Scan 4', image_count: 49 * 3, cameras: range(1, 49), lightings: [0, 1, 2], has_ground_truth: false, has_camera_poses: true, default_cameras: [1, 13, 25, 37, 49] },
  ],
};
const FOLDER = {
  id: 'folder-mock', kind: 'folder', name: 'my_mug',
  scans: [{ id: 'all', name: 'my_mug', image_count: 8, cameras: [], lightings: [], has_ground_truth: false, has_camera_poses: false, default_cameras: [] }],
};
const DATASETS = [DTU, FOLDER];
const dtuName = (cam, light) => `clean_${String(cam).padStart(3, '0')}_${light}_r5000.png`;
const folderName = (i) => `photo_${String(i).padStart(2, '0')}.jpg`;
function scanImages(ds, scan, lighting) {
  if (ds.kind === 'dtu') {
    const l = lighting ?? 0;
    return scan.cameras.map((c) => ({ name: dtuName(c, l), camera: c, lighting: l, url: svgImage(c, `cam ${c}`) }));
  }
  return range(1, scan.image_count).map((i) => ({ name: folderName(i), camera: null, lighting: null, url: svgImage(i, `photo ${i}`) }));
}

// ---------- PLY generation (illustrative vase) ----------
function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}
const profile = (t) => 0.32 + 0.3 * Math.sin(Math.PI * Math.min(1, t * 1.1)) ** 1.3 * (t > 0.75 ? 0.55 + 0.45 * (1 - (t - 0.75) / 0.25) : 1);
function colorAt(t, th, tint) {
  const band = Math.abs(Math.sin(t * 14)) > 0.9 ? 0.85 : 0;
  const stripe = 0.5 + 0.5 * Math.sin(th * 3);
  const r = 0.25 + 0.4 * t + band * 0.5 + tint * 0.15;
  const g = 0.35 + 0.25 * stripe + band * 0.4;
  const b = 0.8 - 0.3 * t + band * 0.2 - tint * 0.1;
  return [r, g, b].map((c) => Math.max(0, Math.min(255, Math.round(c * 255))));
}
function plyPoints(n, noise, seed, tint) {
  const R = rng(seed);
  const lines = [];
  for (let i = 0; i < n; i += 1) {
    const t = R();
    const th = R() * Math.PI * 2;
    const r = profile(t) + (R() - 0.5) * noise;
    const y = (t - 0.5) * 1.6 + (R() - 0.5) * noise;
    const [cr, cg, cb] = colorAt(t, th, tint);
    lines.push(`${(r * Math.cos(th)).toFixed(4)} ${y.toFixed(4)} ${(r * Math.sin(th)).toFixed(4)} ${cr} ${cg} ${cb}`);
  }
  // a few floating outliers
  for (let i = 0; i < Math.round(n * 0.01); i += 1) {
    lines.push(`${((R() - 0.5) * 2.4).toFixed(4)} ${((R() - 0.5) * 2.4).toFixed(4)} ${((R() - 0.5) * 2.4).toFixed(4)} 120 120 120`);
  }
  const total = lines.length;
  return `ply\nformat ascii 1.0\nelement vertex ${total}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n${lines.join('\n')}\n`;
}
function plyMesh(rings, segs, tint) {
  const v = [];
  const f = [];
  for (let i = 0; i <= rings; i += 1) {
    const t = i / rings;
    for (let j = 0; j < segs; j += 1) {
      const th = (j / segs) * Math.PI * 2;
      const r = profile(t);
      const [cr, cg, cb] = colorAt(t, th, tint);
      v.push(`${(r * Math.cos(th)).toFixed(4)} ${((t - 0.5) * 1.6).toFixed(4)} ${(r * Math.sin(th)).toFixed(4)} ${cr} ${cg} ${cb}`);
    }
  }
  for (let i = 0; i < rings; i += 1) {
    for (let j = 0; j < segs; j += 1) {
      const a = i * segs + j;
      const b = i * segs + ((j + 1) % segs);
      const c = (i + 1) * segs + j;
      const d = (i + 1) * segs + ((j + 1) % segs);
      f.push(`3 ${a} ${c} ${b}`, `3 ${b} ${c} ${d}`);
    }
  }
  return `ply\nformat ascii 1.0\nelement vertex ${v.length}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nelement face ${f.length}\nproperty list uchar int vertex_indices\nend_header\n${v.join('\n')}\n${f.join('\n')}\n`;
}
const plyCache = {};
function plyText(kind) {
  if (!plyCache[kind]) {
    plyCache[kind] = {
      classical_pc: () => plyPoints(9000, 0.025, 7, 0),
      neural_pc: () => plyPoints(14000, 0.012, 11, 1),
      classical_mesh: () => plyMesh(30, 40, 0),
      neural_mesh: () => plyMesh(40, 56, 1),
    }[kind]();
  }
  return plyCache[kind];
}
const plyUrlCache = {};
function plyUrl(kind) {
  if (!plyUrlCache[kind]) plyUrlCache[kind] = URL.createObjectURL(new Blob([plyText(kind)], { type: 'application/octet-stream' }));
  return plyUrlCache[kind];
}

// ---------- illustrative metrics (deterministic functions of the settings) ----------
const ARR_BONUS = { auto: 0.02, uniform: 0.03, non_uniform: -0.03, high_overlap: 0.0, low_overlap: -0.07, random: -0.02 };
function methodMetrics(rec, method) {
  const v = rec.config.num_views;
  const bonus = ARR_BONUS[rec.config.view_arrangement] || 0;
  const neural = method === 'neural';
  const f = Math.max(0.05, Math.min(0.98, (neural ? 0.66 + 0.04 * (v - 3) : 0.42 + 0.1 * (v - 3)) + bonus));
  const gt = rec.has_ground_truth;
  const ratio = neural ? 100 : [66.7, 80, 100, 100][Math.min(3, Math.max(0, v - 3))] + (bonus < -0.05 ? -20 : 0);
  return {
    chamfer_distance: gt ? Number((0.045 - 0.04 * f * 0.9).toFixed(4)) : null,
    f_score: gt ? Number(f.toFixed(3)) : null,
    completeness_pct: gt ? Number((f * 100 + 4).toFixed(1)) : null,
    accuracy: gt ? Number((f * 0.97).toFixed(3)) : null,
    camera_pose_error_deg: rec.known_poses ? Number((neural ? 3.1 : 1.8 + (6 - v) * 0.3).toFixed(2)) : null,
    runtime_sec: neural ? 70 + 12 * (v - 3) : 40 + 22 * (v - 3),
    point_count: neural ? 14140 : 9090,
    reprojection_error_px: neural ? null : Number((0.7 + 0.1 * (6 - v)).toFixed(2)),
    registration_ratio_pct: Number(ratio.toFixed(1)),
    floating_artifact_pct: neural ? 1.1 : 3.2 + (6 - v) * 0.6,
  };
}
const NOTE = 'Chamfer distance, F-score, completeness and accuracy need a ground-truth model. Upload one to enable them.';

function cameraList(names, radius) {
  return names.map((name, i) => {
    const a = (i / names.length) * Math.PI * 2;
    return { name, position: [Number((radius * Math.cos(a)).toFixed(3)), 0.6, Number((radius * Math.sin(a)).toFixed(3))], rotation: [1, 0, 0, 0] };
  });
}

function methodResult(rec, method, names) {
  const neural = method === 'neural';
  const m = methodMetrics(rec, method);
  const gt = rec.has_ground_truth;
  const total = names.length;
  const registered = Math.max(1, Math.round((m.registration_ratio_pct / 100) * total));
  const hist = gt ? { bins: [0, 0.01, 0.02, 0.03, 0.04, 0.05], counts: neural ? [5200, 5100, 2400, 1000, 440] : [3600, 3100, 1500, 700, 190] } : null;
  const cfg = rec.config;
  return {
    status: 'completed',
    message: '',
    label: neural ? 'Neural (PyTorch)' : 'Classical (COLMAP + Open3D)',
    runtime_sec: m.runtime_sec,
    files: {
      point_cloud: plyUrl(neural ? 'neural_pc' : 'classical_pc'),
      mesh: cfg.generate_mesh ? plyUrl(neural ? 'neural_mesh' : 'classical_mesh') : null,
      camera_poses: cfg.estimate_poses ? `/api/jobs/${rec.id}/files/camera_poses` : null,
    },
    point_count: m.point_count,
    mesh: cfg.generate_mesh ? { vertex_count: neural ? 2296 : 1240, triangle_count: neural ? 4480 : 2400 } : null,
    registration: {
      total_input: total, registered, ratio_pct: m.registration_ratio_pct, names: names.slice(0, registered),
      mean_reprojection_error_px: m.reprojection_error_px,
    },
    cameras: cfg.estimate_poses ? cameraList(names.slice(0, registered), 3.4) : [],
    metrics: m,
    metrics_note: gt ? '' : NOTE,
    error_histogram: hist,
  };
}

// ---------- job store ----------
const store = { jobs: new Map(), counter: 100 };
function nid(prefix) {
  store.counter += 1;
  return `${prefix}-${store.counter.toString(36).toUpperCase().padStart(6, 'M')}`;
}
const defaults = {
  recon_method: 'both', num_views: 5, view_arrangement: 'auto', quality: 'standard', estimate_poses: true, run_evaluation: true,
  generate_mesh: false, save_intermediate: false, mesh_method: 'poisson', object_category: 'General Object',
};
function addRec(rec) {
  store.jobs.set(rec.id, rec);
  return rec;
}
function seed() {
  const now = Date.now();
  const names = EXAMPLE.images.map((i) => i.name);
  addRec({
    id: 'EXP-MOCK01', project_name: 'Vase_Experiment_01', createdAt: now - 3600e3, startAt: now - 3600e3, mode: 'static', staticStatus: 'completed',
    config: { ...defaults, object_category: 'Vase', num_views: 5, generate_mesh: true }, image_names: names.slice(0, 5), has_ground_truth: true, group_id: null,
    dataset: { id: DTU.id, kind: 'dtu', name: DTU.name, scan: 'scan1', cameras: [1, 13, 25, 37, 49], lighting: 0 }, known_poses: 5, gt_source: 'scan1_reference.ply', execution: { target: 'remote', remote_job_id: 'EXP-R0001' },
  });
  addRec({
    id: 'EXP-MOCK02', project_name: 'Mug_NoGT', createdAt: now - 2 * 3600e3, startAt: now - 2 * 3600e3, mode: 'static', staticStatus: 'partial_success',
    config: { ...defaults, object_category: 'Mug', num_views: 4 }, image_names: names.slice(0, 4), has_ground_truth: false, group_id: null,
    neuralFailed: 'Neural reconstruction failed: CUDA out of memory (mock message).',
    warnings: ['Low overlap between image_002.png and image_004.png'],
  });
  addRec({
    id: 'EXP-MOCK03', project_name: 'Chair_Failed', createdAt: now - 5 * 3600e3, startAt: now - 5 * 3600e3, mode: 'static', staticStatus: 'failed',
    config: { ...defaults, object_category: 'Chair', num_views: 3 }, image_names: names.slice(0, 3), has_ground_truth: false, group_id: null,
    error_message: 'COLMAP registered only 1 of 3 images; not enough overlap to triangulate (mock message).',
  });
  [3, 4, 5, 6].forEach((v, i) => addRec({
    id: `EXP-MOCKG${v}`, project_name: 'Vase_Sweep', createdAt: now - (30 - i) * 60e3 * 60, startAt: now - 86400e3, mode: 'static', staticStatus: 'completed',
    config: { ...defaults, object_category: 'Vase', num_views: v, view_arrangement: 'uniform' }, image_names: names.slice(0, v), has_ground_truth: true, group_id: 'GRP-MOCK01',
  }));
}
seed();

function liveState(rec) {
  if (rec.cancelled) return { status: 'cancelled', elapsed: rec.cancelledAt ? (rec.cancelledAt - rec.startAt) / 1000 : 0, done: false };
  if (rec.mode === 'static') return { status: rec.staticStatus, elapsed: 0, done: true };
  const elapsed = (Date.now() - rec.startAt) / 1000;
  if (elapsed < 0.8) return { status: 'queued', elapsed: 0, done: false };
  if (elapsed < TOTAL_SEC) return { status: 'processing', elapsed, done: false };
  return { status: rec.staticStatus || 'completed', elapsed: TOTAL_SEC, done: true };
}

function logsFor(rec, elapsed, done, status) {
  const base = rec.startAt;
  const lines = [
    [0, 'INFO', `Loading ${rec.image_names.length} images...`],
    [1.2, 'INFO', 'Image quality check passed'],
    [2.2, 'INFO', 'Extracting SIFT features'],
    [3.8, 'INFO', 'Matching image pairs (exhaustive)'],
    [5.2, 'INFO', 'Running incremental mapping'],
    [7.0, 'INFO', 'Registered cameras; bundle adjustment done'],
    [8.3, 'INFO', 'Fusing depth into point cloud'],
    [10.0, 'INFO', rec.config.generate_mesh ? 'Meshing (Poisson)' : 'Mesh generation skipped'],
    [12.2, 'INFO', rec.has_ground_truth ? 'Computing metrics against ground truth' : 'No ground truth: reference metrics skipped'],
  ];
  if (rec.warnings) lines.splice(2, 0, [1.6, 'WARN', rec.warnings[0]]);
  if (rec.neuralFailed) lines.push([13, 'ERROR', rec.neuralFailed]);
  const out = lines.filter(([t]) => t <= elapsed).map(([t, lvl, msg]) => `[${clock(base + t * 1000)}] [${lvl}] ${msg}`);
  if (done && status === 'completed') out.push(`[${clock(base + TOTAL_SEC * 1000)}] [INFO] Done.`);
  if (status === 'failed') out.push(`[${clock(base + 3000)}] [ERROR] ${rec.error_message}`);
  if (status === 'cancelled') out.push(`[${clock(rec.cancelledAt || base)}] [WARN] Cancelled by user.`);
  return out;
}

function jobView(rec) {
  const st = liveState(rec);
  let { status } = st;
  const names = rec.image_names;
  const failedStatic = rec.mode === 'static' && status === 'failed';
  const elapsed = rec.mode === 'static' ? (failedStatic ? 4 : 98) : st.elapsed;
  const progress = failedStatic ? 25 : st.done && status !== 'cancelled' ? 100 : Math.min(99, Math.round((elapsed / TOTAL_SEC) * 100));
  let stage = 'complete';
  const stages = STAGES.map((s) => {
    let ss = 'pending';
    if (st.done && status !== 'failed' && status !== 'cancelled') ss = 'complete';
    else if (failedStatic) ss = s.key === 'image_analysis' ? 'complete' : s.key === 'feature_extraction' ? 'complete' : s.key === 'camera_pose' ? 'failed' : 'pending';
    else if (elapsed >= s.to) ss = 'complete';
    else if (elapsed >= s.from && status === 'processing') ss = 'running';
    if (ss === 'running') stage = s.key;
    return { key: s.key, label: s.label, status: ss };
  });
  if (failedStatic) stage = 'failed';
  if (status === 'queued') stage = 'image_analysis';
  if (status === 'cancelled') stage = 'failed';

  const view = {
    job_id: rec.id,
    project_name: rec.project_name,
    object_category: rec.config.object_category,
    status,
    stage,
    progress,
    stages,
    created_at: stamp(rec.createdAt),
    start_time: stamp(rec.startAt),
    end_time: st.done ? stamp(rec.startAt + (elapsed || 0) * 1000) : null,
    elapsed_sec: Number(elapsed.toFixed(1)),
    eta_sec: st.done ? 0 : Math.max(0, Number((TOTAL_SEC - elapsed).toFixed(1))),
    image_count: names.length,
    images: rec.imageUrls || names.map((n) => ({ name: n, url: (EXAMPLE.images.find((i) => i.name === n) || EXAMPLE.images[0]).url })),
    configuration: { ...rec.config, selected_images: names },
    logs: logsFor(rec, elapsed, st.done, status),
    warnings: rec.warnings || [],
    error_message: status === 'failed' ? rec.error_message : status === 'partial_success' ? rec.neuralFailed : null,
    validation: null,
    group_id: rec.group_id,
    has_ground_truth: rec.has_ground_truth,
    dataset: rec.dataset || null,
    execution: rec.execution || { target: 'local', remote_job_id: null },
    ground_truth_source: rec.gt_source || (rec.has_ground_truth ? 'ground_truth.ply' : null),
    known_camera_poses: rec.known_poses || 0,
    results: { classical: null, neural: null },
    comparison: null,
  };
  if ((status === 'completed' || status === 'partial_success') && st.done) {
    const m = rec.config.recon_method;
    if (m !== 'neural') view.results.classical = methodResult(rec, 'classical', names);
    if (m !== 'classical') {
      view.results.neural = rec.neuralFailed
        ? { status: 'failed', message: rec.neuralFailed, label: 'Neural (PyTorch)', runtime_sec: null, files: { point_cloud: null, mesh: null, camera_poses: null }, point_count: null, mesh: null, registration: null, cameras: [], metrics: {}, metrics_note: '', error_histogram: null }
        : methodResult(rec, 'neural', names);
    }
  }
  if (status === 'failed') {
    view.results.classical = { status: 'failed', message: rec.error_message, label: 'Classical (COLMAP + Open3D)', runtime_sec: null, files: { point_cloud: null, mesh: null, camera_poses: null }, point_count: null, mesh: null, registration: null, cameras: [], metrics: {}, metrics_note: '', error_histogram: null };
  }
  return view;
}

function listItem(rec) {
  const v = jobView(rec);
  const c = v.results.classical && v.results.classical.status === 'completed' ? v.results.classical.metrics : null;
  const n = v.results.neural && v.results.neural.status === 'completed' ? v.results.neural.metrics : null;
  const best = (key, better) => {
    const vals = [c && c[key], n && n[key]].filter((x) => x !== null && x !== undefined);
    if (!vals.length) return null;
    return better === 'max' ? Math.max(...vals) : Math.min(...vals);
  };
  return {
    job_id: rec.id, project_name: rec.project_name, object_category: rec.config.object_category, status: v.status, stage: v.stage,
    created_at: v.created_at, image_count: v.image_count, num_views: rec.config.num_views, view_arrangement: rec.config.view_arrangement,
    recon_method: rec.config.recon_method, group_id: rec.group_id, dataset: rec.dataset || null, execution: rec.execution || { target: 'local', remote_job_id: null }, f_score: best('f_score', 'max'), chamfer: best('chamfer_distance', 'min'),
    runtime_sec: best('runtime_sec', 'min'),
  };
}

// ---------- analysis aggregation ----------
function avg(arr) {
  const v = arr.filter((x) => x !== null && x !== undefined);
  return v.length ? Number((v.reduce((a, b) => a + b, 0) / v.length).toFixed(4)) : null;
}
function aggregate(list, method) {
  if (!list.length) return null;
  const keys = ['chamfer_distance', 'f_score', 'completeness_pct', 'runtime_sec', 'registration_ratio_pct', 'point_count', 'reprojection_error_px', 'floating_artifact_pct'];
  const out = { runs: list.length };
  keys.forEach((k) => { out[k] = avg(list.map((r) => methodMetrics(r, method)[k])); });
  return out;
}
function analysis(groupId) {
  const recs = [...store.jobs.values()].filter((r) => {
    const st = liveState(r);
    return st.done && (st.status === 'completed' || st.status === 'partial_success') && (!groupId || r.group_id === groupId);
  });
  if (!recs.length) return { has_data: false, view_count: [], arrangement: [], failures: [], insights: [] };
  const hasNeural = (r) => r.config.recon_method !== 'classical' && !r.neuralFailed;
  const hasClassical = (r) => r.config.recon_method !== 'neural';
  const views = [...new Set(recs.map((r) => r.config.num_views))].sort((a, b) => a - b);
  const arrs = [...new Set(recs.map((r) => r.config.view_arrangement))];
  const view_count = views.map((v) => {
    const g = recs.filter((r) => r.config.num_views === v);
    return { views: v, classical: aggregate(g.filter(hasClassical), 'classical'), neural: aggregate(g.filter(hasNeural), 'neural') };
  });
  const arrangement = arrs.map((a) => {
    const g = recs.filter((r) => r.config.view_arrangement === a);
    return { arrangement: a, classical: aggregate(g.filter(hasClassical), 'classical'), neural: aggregate(g.filter(hasNeural), 'neural') };
  });
  const failures = [];
  recs.forEach((r) => {
    if (hasClassical(r)) {
      const m = methodMetrics(r, 'classical');
      if (m.registration_ratio_pct < 100) {
        const reg = Math.round((m.registration_ratio_pct / 100) * r.config.num_views);
        failures.push({ job_id: r.id, num_views: r.config.num_views, view_arrangement: r.config.view_arrangement, method: 'classical', reason: `Only ${reg} of ${r.config.num_views} views registered` });
      }
    }
    if (r.neuralFailed) failures.push({ job_id: r.id, num_views: r.config.num_views, view_arrangement: r.config.view_arrangement, method: 'neural', reason: r.neuralFailed });
  });
  const insights = [];
  const first = view_count[0];
  const last = view_count[view_count.length - 1];
  if (first && last && first !== last && first.classical && last.classical) {
    insights.push(`Registration ratio rises from ${first.classical.registration_ratio_pct}% at ${first.views} views to ${last.classical.registration_ratio_pct}% at ${last.views} views (classical).`);
    insights.push(`Classical runtime grows from ${first.classical.runtime_sec}s at ${first.views} views to ${last.classical.runtime_sec}s at ${last.views} views.`);
  }
  return { has_data: true, view_count, arrangement, failures, insights };
}

// ---------- execution target (local / remote Colab worker) ----------
const LOCAL_CAPS = {
  gpu: false, colmap_available: true, colmap_gpu_usable: false,
  neural_available: false, neural_backend: null, neural_reason: 'Neural weights are not reachable from this computer (mock)',
};
const WORKER = {
  configured: true, connected: true, host: 'mock-worker.trycloudflare.com', gpu: true, gpu_name: 'Tesla T4',
  colmap_available: true, colmap_gpu_usable: true, neural_available: true, neural_backend: 'vggt', neural_reason: null, error: null,
};
const execState = { mode: 'auto', remote: null };
function effectiveTarget() {
  const connected = !!(execState.remote && execState.remote.connected);
  if (execState.mode === 'remote') {
    if (!connected) throw new ApiError('Execution mode is "remote" but no Colab worker is connected. Connect one in Settings.', 409);
    return 'remote';
  }
  if (execState.mode === 'auto' && connected && !LOCAL_CAPS.gpu) return 'remote';
  return 'local';
}
function execBody() {
  const connected = !!(execState.remote && execState.remote.connected);
  let effective;
  try { effective = effectiveTarget(); } catch { effective = 'local'; }
  const reason = effective === 'remote'
    ? (execState.mode === 'remote' ? 'Mode is Colab GPU worker; using the connected worker' : 'This machine has no GPU; using the connected remote worker')
    : execState.mode === 'remote'
      ? 'Mode is Colab GPU worker but no worker is connected, so experiments cannot start'
      : execState.mode === 'local' ? 'Mode is This computer' : (connected ? 'Using this computer' : 'No worker is connected; running on this computer');
  const c = effective === 'remote' ? execState.remote : LOCAL_CAPS;
  return {
    mode: execState.mode, effective, reason, local: { ...LOCAL_CAPS }, remote: execState.remote ? { ...execState.remote } : null,
    capabilities: {
      gpu: c.gpu, colmap_available: c.colmap_available, colmap_gpu_usable: c.colmap_gpu_usable,
      neural_available: c.neural_available, neural_backend: c.neural_backend, neural_reason: c.neural_reason,
    },
    colab: {
      notebook_open_url: 'https://colab.research.google.com/github/IshaVats04/Sparse3D/blob/main/notebooks/02_colab_backend.ipynb',
      notebook_download_url: `data:application/x-ipynb+json,${encodeURIComponent('{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}')}`,
      steps: ['Open the notebook in Colab', 'Runtime > Change runtime type > T4 GPU', 'Runtime > Run all',
        'Wait for the last cell to print a connection code (starts with S3D1.)', 'Paste the code below and press Connect'],
    },
  };
}
function execFields() {
  const target = effectiveTarget();
  return { execution: { target, remote_job_id: target === 'remote' ? nid('EXP') : null } };
}

// ---------- request handling ----------
function validation(names, fromFiles) {
  const images = names.map((name, i) => {
    const bad = /bad/i.test(name);
    const warn = i === 1;
    return {
      name, width: 1600, height: 1200, blur_score: warn ? 41.2 : 182.4, brightness: 121, keypoints: bad ? 12 : 2310,
      status: bad ? 'error' : warn ? 'warn' : 'ok',
      issues: bad ? ['Too few feature points detected'] : warn ? ['Image looks blurry'] : [],
    };
  });
  const pairs = names.length >= 4 ? [{ a: names[1], b: names[3], matches: 14, overlap_pct: 6.2, warning: true }] : [];
  const messages = [];
  if (images.some((i) => i.status === 'error')) messages.push({ level: 'error', text: 'Some images have too few features to be used' });
  else messages.push({ level: 'ok', text: 'Feature points detected in all images' });
  if (pairs.length) messages.push({ level: 'warn', text: `Low overlap between Image 2 and Image 4` });
  if (images.some((i) => i.status === 'warn')) messages.push({ level: 'warn', text: 'Image 2 looks blurry' });
  messages.push({ level: 'ok', text: fromFiles ? 'Image resolution is consistent' : 'Bundled sample set (mock)' });
  return { image_count: names.length, can_proceed: names.length >= 3 && !images.some((i) => i.status === 'error'), images, pairs, messages };
}

function parseConfig(fd) {
  const get = (k, d) => (fd.has(k) && fd.get(k) !== '' ? fd.get(k) : d);
  const bool = (k, d) => (fd.has(k) ? fd.get(k) === 'true' : d);
  return {
    recon_method: get('recon_method', 'both'), view_arrangement: get('view_arrangement', 'auto'), quality: get('quality', 'standard'),
    estimate_poses: bool('estimate_poses', true), run_evaluation: bool('run_evaluation', true), generate_mesh: bool('generate_mesh', false),
    save_intermediate: bool('save_intermediate', false), mesh_method: get('mesh_method', 'poisson'), object_category: get('object_category', 'General Object'),
  };
}
function datasetFromForm(fd) {
  const dsId = fd.get('dataset_id');
  const ds = DATASETS.find((d) => d.id === dsId);
  if (!ds) throw new ApiError(`Dataset ${dsId} not found`, 404);
  const scan = ds.scans.find((x) => x.id === fd.get('scan_id'));
  if (!scan) throw new ApiError(`Scan ${fd.get('scan_id')} not found`, 404);
  const lighting = fd.has('lighting') ? Number(fd.get('lighting')) : (scan.lightings.length ? 0 : null);
  let cameras = String(fd.get('cameras') || '').split(',').filter(Boolean).map(Number);
  if (ds.kind === 'dtu' && !cameras.length) cameras = scan.default_cameras;
  const urls = ds.kind === 'dtu'
    ? cameras.map((c) => ({ name: dtuName(c, lighting ?? 0), url: svgImage(c, `cam ${c}`) }))
    : scanImages(ds, scan, null).map((i) => ({ name: i.name, url: i.url }));
  return { ds, scan, lighting, cameras: ds.kind === 'dtu' ? cameras : [], names: urls.map((u) => u.name), urls, useGt: fd.get('use_dataset_ground_truth') !== 'false' };
}
function jobExtras(fd, d, nViews) {
  const gtFile = fd.get('ground_truth') && fd.get('ground_truth').name ? fd.get('ground_truth').name : null;
  const useDs = !!(d && d.scan.has_ground_truth && d.useGt);
  const cams = d && d.ds.kind === 'dtu' ? d.cameras.slice(0, nViews || d.cameras.length) : [];
  return {
    has_ground_truth: !!(gtFile || useDs),
    gt_source: gtFile || (useDs ? `${d.scan.id}_reference.ply` : null),
    dataset: d ? { id: d.ds.id, kind: d.ds.kind, name: d.ds.name, scan: d.scan.id, cameras: cams, lighting: d.lighting } : null,
    known_poses: d && d.scan.has_camera_poses ? (cams.length || d.names.length) : 0,
  };
}
function imagesFromForm(fd) {
  if (fd && fd.get('dataset_id')) { const d = datasetFromForm(fd); return { names: d.names, urls: d.urls, d }; }
  const exId = fd && fd.get('example_id');
  if (exId) return { names: EXAMPLE.images.map((i) => i.name), urls: EXAMPLE.images };
  const files = fd.getAll('images').filter((f) => f && f.name);
  return { names: files.map((f) => f.name), urls: files.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })) };
}

function route(method, path) {
  const url = new URL(path, 'http://x');
  return { p: url.pathname, q: url.searchParams, method };
}

export async function handle(method, path, { formData, json } = {}) {
  await delay();
  const { p, q } = route(method, path);
  if (method === 'GET' && p === '/api/health') {
    return {
      status: 'healthy', app_name: '3D RECON LAB', version: '3.0.0-mock',
      environment: {
        python_version: '3.11.0 (mock)', platform: 'mock', colmap_available: true, colmap_path: '/usr/bin/colmap (mock)', colmap_cuda: false,
        torch_available: true, neural_available: LOCAL_CAPS.neural_available, neural_reason: LOCAL_CAPS.neural_reason, neural_backend: LOCAL_CAPS.neural_backend, cuda_available: false, device: 'cpu',
        active_jobs_count: [...store.jobs.values()].filter((r) => ['queued', 'processing'].includes(liveState(r).status)).length,
      },
    };
  }
  if (p === '/api/execution' && method === 'GET') return execBody();
  if (p === '/api/execution' && method === 'PUT') {
    const mode = json && json.mode;
    if (!['auto', 'local', 'remote'].includes(mode)) throw new ApiError('mode must be one of auto, local, remote', 400);
    const code = json && json.connection_code;
    if (code) {
      if (!/^S3D1./.test(code) || code.length < 8) throw new ApiError('Malformed connection code: it must start with S3D1. (copy the whole line printed by the notebook).', 400);
      await delay(900);
      if (/unreachable/i.test(code)) throw new ApiError('Could not reach the worker (mock): is the Colab notebook still running?', 502);
      execState.remote = { ...WORKER, checked_at: stamp(Date.now()) };
    }
    execState.mode = mode;
    return execBody();
  }
  if (p === '/api/execution/remote' && method === 'DELETE') { execState.remote = null; return execBody(); }
  if (method === 'GET' && p === '/api/examples') return [EXAMPLE];
  if (method === 'GET' && p === '/api/datasets') return DATASETS;
  const dm = /^\/api\/datasets\/([^/]+)\/([^/]+)\/images$/.exec(p);
  if (method === 'GET' && dm) {
    const ds = DATASETS.find((d) => d.id === decodeURIComponent(dm[1]));
    const scan = ds && ds.scans.find((x) => x.id === decodeURIComponent(dm[2]));
    if (!scan) throw new ApiError('Scan not found', 404);
    const light = q.has('lighting') ? Number(q.get('lighting')) : null;
    return scanImages(ds, scan, light).slice(0, Number(q.get('limit')) || 200);
  }
  if (method === 'POST' && p === '/api/validate') {
    const { names } = imagesFromForm(formData);
    if (names.length === 0) throw new ApiError('No images were provided.', 400);
    return validation(names, !formData.get('example_id') && !formData.get('dataset_id'));
  }
  if (method === 'POST' && p === '/api/jobs') {
    const { names, urls, d } = imagesFromForm(formData);
    if (names.length < 3 || (names.length > 6 && !(d && d.ds.kind === 'folder'))) throw new ApiError('Provide between 3 and 6 images.', 400);
    const cfg = parseConfig(formData);
    cfg.num_views = Number(formData.get('num_views')) || names.length;
    const id = nid('EXP');
    const imgs = names.slice(0, cfg.view_arrangement === 'auto' ? names.length : cfg.num_views);
    addRec({
      id, project_name: formData.get('project_name') || 'Experiment', createdAt: Date.now(), startAt: Date.now(), mode: 'live', ...execFields(),
      config: cfg, image_names: imgs, imageUrls: urls.filter((u) => imgs.includes(u.name)), ...jobExtras(formData, d, imgs.length), group_id: formData.get('group_id') || null,
    });
    return { job_id: id, status: 'queued', message: 'Job accepted (mock).' };
  }
  if (method === 'GET' && p === '/api/jobs') return [...store.jobs.values()].map(listItem);
  const m = /^\/api\/jobs\/([^/]+)(?:\/(cancel|report))?$/.exec(p);
  if (m) {
    const rec = store.jobs.get(decodeURIComponent(m[1]));
    if (!rec) throw new ApiError(`Job ${m[1]} not found`, 404);
    if (method === 'GET' && !m[2]) return jobView(rec);
    if (method === 'GET' && m[2] === 'report') return jobView(rec);
    if (method === 'DELETE') { store.jobs.delete(rec.id); return { deleted: rec.id }; }
    if (method === 'POST' && m[2] === 'cancel') {
      const st = liveState(rec);
      if (st.done) throw new ApiError('Job already finished', 409);
      rec.cancelled = true;
      rec.cancelledAt = Date.now();
      return { job_id: rec.id, status: 'cancelled' };
    }
  }
  if (method === 'POST' && p === '/api/experiments/sweep') {
    const { names, urls, d } = imagesFromForm(formData);
    const counts = String(formData.get('view_counts') || '3,4,5,6').split(',').map(Number).filter(Boolean);
    const arrs = String(formData.get('arrangements') || formData.get('view_arrangement') || 'auto').split(',');
    if (names.length < Math.max(...counts)) throw new ApiError(`The sweep needs at least ${Math.max(...counts)} images.`, 400);
    const cfg = parseConfig(formData);
    const group = nid('GRP');
    const ids = [];
    let k = 0;
    counts.forEach((v) => arrs.forEach((a) => {
      const id = nid('EXP');
      ids.push(id);
      const imgs = names.slice(0, v);
      addRec({
        id, project_name: formData.get('project_name') || 'Sweep', createdAt: Date.now(), startAt: Date.now() + k * 4000, mode: 'live', ...execFields(),
        config: { ...cfg, num_views: v, view_arrangement: a }, image_names: imgs, imageUrls: urls.filter((u) => imgs.includes(u.name)),
        ...jobExtras(formData, d, v), group_id: group,
      });
      k += 1;
    }));
    return { group_id: group, job_ids: ids };
  }
  if (method === 'GET' && p === '/api/analysis') return analysis(q.get('group_id'));
  throw new ApiError(`Mock: no handler for ${method} ${p}`, 404);
}

export async function handleBlob(path) {
  await delay(200);
  const m = /^\/api\/jobs\/([^/]+)\/files\/([a-z_]+)$/.exec(new URL(path, 'http://x').pathname);
  if (!m) throw new ApiError('Mock: unknown file', 404);
  const rec = store.jobs.get(decodeURIComponent(m[1]));
  if (!rec) throw new ApiError(`Job ${m[1]} not found`, 404);
  const [, id, type] = m;
  const view = jobView(rec);
  const kinds = { point_cloud: 'classical_pc', neural_point_cloud: 'neural_pc', mesh: 'classical_mesh', neural_mesh: 'neural_mesh' };
  if (kinds[type]) {
    const isMesh = type.endsWith('mesh');
    if (isMesh && !rec.config.generate_mesh) throw new ApiError('No mesh was generated for this job.', 404);
    return { blob: new Blob([plyText(kinds[type])], { type: 'application/octet-stream' }), filename: `${id}_${type}.ply` };
  }
  if (type === 'report') return { blob: new Blob([JSON.stringify(view, null, 2)], { type: 'application/json' }), filename: `${id}_report.json` };
  if (type === 'metrics_csv') {
    const rows = ['method,metric,value'];
    ['classical', 'neural'].forEach((mm) => {
      const r = view.results[mm];
      if (r && r.metrics) Object.entries(r.metrics).forEach(([k, v]) => rows.push(`${mm},${k},${v === null ? '' : v}`));
    });
    return { blob: new Blob([rows.join('\n')], { type: 'text/csv' }), filename: `${id}_metrics.csv` };
  }
  if (type === 'camera_poses') {
    const cams = (view.results.classical && view.results.classical.cameras) || [];
    return { blob: new Blob([cams.map((c) => `${c.name} ${c.position.join(' ')} ${c.rotation.join(' ')}`).join('\n')], { type: 'text/plain' }), filename: `${id}_camera_poses.txt` };
  }
  throw new ApiError(`Unknown file type ${type}`, 404);
}
