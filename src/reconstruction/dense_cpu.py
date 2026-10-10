"""Dense multi-view stereo on the CPU, using COLMAP's camera poses.

COLMAP's own dense stage (PatchMatch stereo) needs a CUDA GPU. Without one the classical result would be the sparse SfM
cloud, a few hundred points that do not look like the object. This module densifies it with a plane-sweep multi-view
stereo that needs nothing but OpenCV and NumPy:

1. every registered view in turn is the reference; its best neighbours are chosen from the sparse model (shared
   points, useful parallax),
2. a set of fronto-parallel depth planes spanning the depth range of the sparse points is swept; for each plane the
   neighbours are warped into the reference view with a homography and compared with zero-mean normalised
   cross-correlation (after local contrast enhancement, so dark surfaces keep matchable detail),
3. the best plane per pixel gives a depth map, restricted to the region covered by the sparse points,
4. depth maps are cross-checked against each other (a point must agree with the depth map of another view) and the
   survivors are merged into one coloured cloud in the world frame.

It is slower and less complete than PatchMatch on a GPU, but it works with the wide baselines of 3-6 view sets and
produces a dense, coloured surface that resembles the photographed object.
"""

from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .colmap_model import Image, SparseModel
from .quality_check import read_image

MIN_PARALLAX_DEG, MAX_PARALLAX_DEG = 1.5, 60.0
NEIGHBOURS = 3
PLANES = 128
WINDOW = 7
MIN_NCC = 0.55
DEPTH_AGREEMENT = 0.02          # relative depth difference accepted when cross-checking views
MAX_POINTS = 800_000


def _enhance(img: np.ndarray) -> np.ndarray:
    """Local contrast enhancement (CLAHE on lightness) so dark, low-texture surfaces still give matchable detail."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _shared_points(a: Image, b: Image) -> List[int]:
    ids_a = {i for i in a.point3d_ids if i >= 0}
    return [i for i in b.point3d_ids if i >= 0 and i in ids_a]


def _parallax_deg(model: SparseModel, a: Image, b: Image, shared: List[int]) -> float:
    xyz = np.array([model.points3D[i].xyz for i in shared if i in model.points3D])
    if len(xyz) == 0:
        return 0.0
    ra, rb = a.center() - xyz, b.center() - xyz
    cos = (ra * rb).sum(axis=1) / (np.linalg.norm(ra, axis=1) * np.linalg.norm(rb, axis=1) + 1e-12)
    return float(np.degrees(np.median(np.arccos(np.clip(cos, -1, 1)))))


def choose_neighbours(model: SparseModel, ref: Image, count: int = NEIGHBOURS) -> List[Image]:
    """Views that share the most sparse points with `ref` and see it from a useful angle."""
    cands = []
    for other in model.images.values():
        if other.image_id == ref.image_id:
            continue
        shared = _shared_points(ref, other)
        if len(shared) < 8:
            continue
        if MIN_PARALLAX_DEG <= _parallax_deg(model, ref, other, shared) <= MAX_PARALLAX_DEG:
            cands.append((len(shared), other.image_id))
    return [model.images[i] for _, i in sorted(cands, reverse=True)[:count]]


class _View:
    """One view prepared for stereo: scaled colour image, grey image, intrinsics (scaled) and pose."""

    def __init__(self, model: SparseModel, im: Image, images_dir, max_side: int):
        img = read_image(images_dir / im.name)
        if img is None:
            raise ValueError(f"cannot read {im.name}")
        cam = model.cameras[im.camera_id]
        s = min(1.0, max_side / max(img.shape[:2]))
        if s < 1.0:
            img = cv2.resize(img, (int(round(img.shape[1] * s)), int(round(img.shape[0] * s))),
                             interpolation=cv2.INTER_AREA)
        dist = cam.distortion()
        K = cam.intrinsics().copy()
        K[:2] *= img.shape[1] / cam.width
        if np.any(dist):                              # work on undistorted images so the pinhole model holds
            img = cv2.undistort(img, K, dist)
        self.name, self.bgr, self.K = im.name, img, K
        self.R, self.t = im.rotation(), im.tvec
        self.h, self.w = img.shape[:2]
        self.gray = cv2.cvtColor(_enhance(img), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        self.depth: Optional[np.ndarray] = None      # filled by the sweep (0 = no estimate)


def _box(x: np.ndarray) -> np.ndarray:
    return cv2.blur(x, (WINDOW, WINDOW))


def _sweep(model: SparseModel, im: Image, views: Dict[int, _View], images_dir,
           cancelled: Callable[[], bool]) -> Optional[np.ndarray]:
    """Depth map of one reference view by plane sweep. Returns None when the view cannot be processed."""
    ref = views[im.image_id]
    nbrs = [views[n.image_id] for n in choose_neighbours(model, im) if n.image_id in views]
    if not nbrs:
        return None
    pts = np.array([model.points3D[i].xyz for i in im.point3d_ids if i >= 0 and i in model.points3D])
    if len(pts) < 8:
        return None
    zc = pts @ ref.R.T + ref.t
    zc = zc[zc[:, 2] > 0, 2]
    if len(zc) < 8:
        return None
    z_lo, z_hi = 0.7 * float(np.percentile(zc, 2)), 1.4 * float(np.percentile(zc, 98))
    depths = 1.0 / np.linspace(1.0 / z_hi, 1.0 / z_lo, PLANES)

    mean_r = _box(ref.gray)
    var_r = np.maximum(_box(ref.gray * ref.gray) - mean_r * mean_r, 1e-6)
    K_inv = np.linalg.inv(ref.K)
    e3 = np.array([[0.0, 0.0, 1.0]])
    ones = np.ones((ref.h, ref.w), np.float32)
    best = np.full((ref.h, ref.w), -1.0, np.float32)
    best_idx = np.zeros((ref.h, ref.w), np.int32)

    rel = []
    for n in nbrs:
        R_rel = n.R @ ref.R.T
        t_rel = (n.t - R_rel @ ref.t).reshape(3, 1)
        rel.append((n, R_rel, t_rel))

    for k, d in enumerate(depths):
        if cancelled():
            raise RuntimeError("Cancelled")
        scores = []
        for n, R_rel, t_rel in rel:
            H = n.K @ (R_rel + t_rel @ e3 / d) @ K_inv
            flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
            warped = cv2.warpPerspective(n.gray, H, (ref.w, ref.h), flags=flags, borderValue=0)
            inside = cv2.warpPerspective(ones, H, (ref.w, ref.h), flags=flags, borderValue=0) > 0.99
            mean_w = _box(warped)
            var_w = np.maximum(_box(warped * warped) - mean_w * mean_w, 1e-6)
            cov = _box(ref.gray * warped) - mean_r * mean_w
            ncc = cov / np.sqrt(var_r * var_w)
            ncc[~inside] = -1.0
            scores.append(ncc)
        stack = np.sort(np.stack(scores), axis=0)[::-1]          # best neighbours first
        score = stack[:2].mean(axis=0) if len(scores) >= 2 else stack[0]
        better = score > best
        best[better] = score[better]
        best_idx[better] = k

    depth = depths[best_idx].astype(np.float32)
    valid = (best >= MIN_NCC) & (best_idx > 0) & (best_idx < PLANES - 1)

    # restrict to the region covered by the sparse points (the object), slightly enlarged
    uv = (ref.K @ zc_to_cam(pts, ref).T).T
    uv = np.round(uv[:, :2] / uv[:, 2:3]).astype(np.int32)
    region = np.zeros((ref.h, ref.w), np.uint8)
    cv2.fillConvexPoly(region, cv2.convexHull(uv), 1)
    grow = max(5, int(0.05 * max(ref.h, ref.w)))
    region = cv2.dilate(region, np.ones((grow, grow), np.uint8))
    valid &= region > 0

    depth[~valid] = 0.0
    depth = cv2.medianBlur(depth, 5)                              # removes isolated plane-index flips
    depth[~valid] = 0.0
    # drop small isolated islands
    scaled = (depth * 1000.0).astype(np.int16) if depth.max() < 30 else (depth * 10.0).astype(np.int16)
    cv2.filterSpeckles(scaled, 0, max(30, int(0.0005 * ref.h * ref.w)), int(0.02 * float(scaled.max() or 1)))
    depth[scaled == 0] = 0.0
    return depth


def zc_to_cam(world: np.ndarray, v: "_View") -> np.ndarray:
    return world @ v.R.T + v.t


def _backproject(v: _View) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """World points of the valid depth pixels: (points, pixel rows, pixel cols)."""
    vs, us = np.nonzero(v.depth > 0)
    z = v.depth[vs, us].astype(np.float64)
    x = (us - v.K[0, 2]) * z / v.K[0, 0]
    y = (vs - v.K[1, 2]) * z / v.K[1, 1]
    cam = np.stack([x, y, z], axis=1)
    return (cam - v.t) @ v.R, vs, us                               # R^T (X - t) for row vectors


def _cross_check(views: List[_View], per_view: List[Tuple[np.ndarray, np.ndarray, np.ndarray]]) -> List[np.ndarray]:
    """Boolean keep-mask per view: a point must agree with the depth map of at least one other view."""
    masks = []
    for vi, (world, _, _) in enumerate(per_view):
        ok = np.zeros(len(world), bool)
        for vj, other in enumerate(views):
            if vi == vj or other.depth is None:
                continue
            cam = zc_to_cam(world, other)
            front = cam[:, 2] > 1e-6
            uv = (other.K @ cam.T).T
            u = np.round(uv[:, 0] / np.where(front, uv[:, 2], 1)).astype(int)
            v = np.round(uv[:, 1] / np.where(front, uv[:, 2], 1)).astype(int)
            inside = front & (u >= 0) & (u < other.w) & (v >= 0) & (v < other.h)
            dv = np.zeros(len(world))
            dv[inside] = other.depth[v[inside], u[inside]]
            agree = inside & (dv > 0) & (np.abs(cam[:, 2] - dv) / np.maximum(cam[:, 2], 1e-9) < DEPTH_AGREEMENT)
            ok |= agree
        masks.append(ok)
    return masks


def dense_cpu(model: SparseModel, images_dir, max_side: int = 960,
              log: Callable[[str, str], None] = lambda msg, level="INFO": None,
              cancelled: Callable[[], bool] = lambda: False) -> Optional[Tuple[np.ndarray, np.ndarray, Dict]]:
    """Dense coloured cloud from a COLMAP sparse model. Returns (points, colours, stats) or None."""
    views: Dict[int, _View] = {}
    for im in model.images.values():
        try:
            views[im.image_id] = _View(model, im, images_dir, max_side)
        except ValueError as exc:
            log(f"CPU dense stereo: {exc}", "WARNING")
    done: List[_View] = []
    for im in model.images.values():
        if im.image_id not in views:
            continue
        depth = _sweep(model, im, views, images_dir, cancelled)
        if depth is None:
            log(f"CPU dense stereo: {im.name} skipped (no usable neighbour views)", "INFO")
            continue
        views[im.image_id].depth = depth
        done.append(views[im.image_id])
        log(f"CPU dense stereo: depth map for {im.name}: {int((depth > 0).sum())} px")
    if not done:
        return None

    per_view = [_backproject(v) for v in done]
    masks = _cross_check(done, per_view) if len(done) > 1 else [np.ones(len(p[0]), bool) for p in per_view]
    all_pts, all_cols = [], []
    for v, (world, vs, us), keep in zip(done, per_view, masks):
        all_pts.append(world[keep])
        all_cols.append(v.bgr[vs[keep], us[keep]][:, ::-1].astype(np.float64) / 255.0)
    pts, cols = np.concatenate(all_pts), np.concatenate(all_cols)
    log(f"CPU dense stereo: {sum(len(p[0]) for p in per_view)} raw points, {len(pts)} after cross-checking views")
    if len(pts) > MAX_POINTS:
        idx = np.random.default_rng(0).choice(len(pts), MAX_POINTS, replace=False)
        pts, cols = pts[idx], cols[idx]
    return pts, cols, {"views_used": len(done), "views_total": len(views), "max_side": max_side}
