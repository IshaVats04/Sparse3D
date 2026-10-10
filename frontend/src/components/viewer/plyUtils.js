import { useEffect, useState } from 'react';
import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import { fetchBuffer } from '../../services/api';

/** Fetch + parse a PLY file into a BufferGeometry. Normals are computed for meshes when missing. */
export async function loadPly(url, signal) {
  const buffer = await fetchBuffer(url, { signal });
  const geometry = new PLYLoader().parse(buffer);
  if (!geometry.getAttribute('position') || geometry.getAttribute('position').count === 0) {
    geometry.dispose();
    throw new Error('The PLY file contains no vertices.');
  }
  if (geometry.index && !geometry.getAttribute('normal')) geometry.computeVertexNormals();
  return geometry;
}

/**
 * Robust centre/scale so the object fits in a ~unit sphere. Uses 1%-99% quantiles of a
 * subsample, so a few floating outlier points do not shrink the object.
 */
export function computeNormalization(geometry) {
  const pos = geometry.getAttribute('position');
  const n = pos.count;
  const step = Math.max(1, Math.floor(n / 20000));
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < n; i += step) {
    xs.push(pos.getX(i));
    ys.push(pos.getY(i));
    zs.push(pos.getZ(i));
  }
  const q = (arr, p) => {
    arr.sort((a, b) => a - b);
    return arr[Math.min(arr.length - 1, Math.max(0, Math.floor(p * (arr.length - 1))))];
  };
  const lo = [q(xs, 0.01), q(ys, 0.01), q(zs, 0.01)];
  const hi = [q(xs, 0.99), q(ys, 0.99), q(zs, 0.99)];
  const center = new Vector3((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2);
  const extent = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  const scale = extent > 1e-9 ? 2 / extent : 1;
  return { center, scale };
}

/** Line-segment geometry for a camera frustum pointing at `target` (all in the object's raw coordinates). */
export function buildFrustumGeometry(position, target, size) {
  const p = new Vector3(...position);
  const dir = new Vector3().subVectors(target, p);
  if (dir.lengthSq() < 1e-12) dir.set(0, 0, -1);
  dir.normalize();
  const up0 = Math.abs(dir.y) > 0.95 ? new Vector3(0, 0, 1) : new Vector3(0, 1, 0);
  const right = new Vector3().crossVectors(dir, up0).normalize();
  const up = new Vector3().crossVectors(right, dir).normalize();
  const d = size;
  const w = size * 0.6;
  const h = size * 0.45;
  const base = p.clone().addScaledVector(dir, d);
  const c = [
    base.clone().addScaledVector(right, -w).addScaledVector(up, h),
    base.clone().addScaledVector(right, w).addScaledVector(up, h),
    base.clone().addScaledVector(right, w).addScaledVector(up, -h),
    base.clone().addScaledVector(right, -w).addScaledVector(up, -h),
  ];
  const pts = [];
  c.forEach((corner, i) => {
    pts.push(...p.toArray(), ...corner.toArray());
    pts.push(...corner.toArray(), ...c[(i + 1) % 4].toArray());
  });
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pts, 3));
  return g;
}

/** Load a PLY while `url` is set; disposes the geometry when replaced or unmounted. */
export function usePlyGeometry(url, enabled = true) {
  const [state, setState] = useState({ geometry: null, loading: false, error: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!url || !enabled) {
      setState({ geometry: null, loading: false, error: null });
      return undefined;
    }
    const ctrl = new AbortController();
    let geom = null;
    let cancelled = false;
    setState({ geometry: null, loading: true, error: null });
    loadPly(url, ctrl.signal)
      .then((g) => {
        if (cancelled) { g.dispose(); return; }
        geom = g;
        setState({ geometry: g, loading: false, error: null });
      })
      .catch((e) => {
        if (cancelled || (e && e.name === 'AbortError')) return;
        setState({ geometry: null, loading: false, error: e });
      });
    return () => {
      cancelled = true;
      ctrl.abort();
      if (geom) geom.dispose();
    };
  }, [url, enabled, attempt]);

  return { ...state, retry: () => setAttempt((a) => a + 1) };
}
