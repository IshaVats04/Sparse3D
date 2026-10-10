"""Quantitative evaluation: Chamfer distance, F-score, completeness, accuracy, floating artifacts.

Reconstructions from images are only defined up to a similarity transform, so before comparing against a
ground-truth model the prediction is aligned to it (scale normalisation, FPFH + RANSAC global registration,
point-to-point ICP). All distances are then reported in units of the ground-truth bounding-box diagonal,
which makes the numbers scale-invariant and comparable across objects.

Measurements that need a reference return None when no reference is supplied. Nothing is estimated or faked.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

F_SCORE_THRESHOLD = 0.02     # fraction of the ground-truth bounding-box diagonal
SAMPLE_POINTS = 50000        # points sampled from reference meshes


def load_reference_points(path: Path, n_points: int = SAMPLE_POINTS, max_points: int = 400000):
    """Load a ground-truth model (.ply/.obj/.stl point cloud or mesh) as an Open3D point cloud.

    Dense scans (the DTU reference clouds have millions of points) are randomly thinned to `max_points`.
    """
    import open3d as o3d

    path = Path(path)
    mesh = o3d.io.read_triangle_mesh(str(path))
    if len(mesh.triangles) > 0:
        return mesh.sample_points_uniformly(number_of_points=n_points)
    pcd = o3d.io.read_point_cloud(str(path))
    if len(pcd.points) == 0:
        raise ValueError(f"Could not read any geometry from {path.name}")
    if len(pcd.points) > max_points:
        pcd = pcd.random_down_sample(max_points / len(pcd.points))
    return pcd


def _normalise(pcd) -> Tuple[Any, np.ndarray, float]:
    """Centre on the centroid and scale to unit RMS radius. Returns (cloud, centre, scale)."""
    import open3d as o3d

    pts = np.asarray(pcd.points)
    centre = pts.mean(axis=0)
    scale = float(np.sqrt(((pts - centre) ** 2).sum(axis=1).mean())) or 1.0
    out = o3d.geometry.PointCloud()
    out.points = o3d.utility.Vector3dVector((pts - centre) / scale)
    return out, centre, scale


def align_to_reference(pred, ref) -> Tuple[Any, Any, float]:
    """Align `pred` to `ref` (similarity transform). Returns (aligned_pred, ref_normalised, icp_fitness).

    Both clouds are returned in the reference's normalised frame (bbox diagonal = 1).
    """
    import open3d as o3d

    pn, _, _ = _normalise(pred)
    rn, _, _ = _normalise(ref)
    # Express the reference in bbox-diagonal units; the prediction is rescaled by matching RMS radius first.
    voxel = 0.05
    ps, rs = pn.voxel_down_sample(voxel), rn.voxel_down_sample(voxel)
    for c in (ps, rs):
        c.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
    fp = o3d.pipelines.registration.compute_fpfh_feature(
        ps, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5, max_nn=100))
    fr = o3d.pipelines.registration.compute_fpfh_feature(
        rs, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5, max_nn=100))
    best = None
    for _ in range(3):  # RANSAC is randomised; keep the best of a few runs
        res = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
            ps, rs, fp, fr, True, voxel * 1.5,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3,
            [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
             o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(voxel * 1.5)],
            o3d.pipelines.registration.RANSACConvergenceCriteria(100000, 0.999))
        if best is None or res.fitness > best.fitness:
            best = res
    icp = o3d.pipelines.registration.registration_icp(
        pn, rn, voxel * 1.0, best.transformation,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=200))
    pn.transform(icp.transformation)

    # Convert both to bbox-diagonal units of the reference
    diag = float(np.linalg.norm(rn.get_max_bound() - rn.get_min_bound())) or 1.0
    aligned = o3d.geometry.PointCloud()
    aligned.points = o3d.utility.Vector3dVector(np.asarray(pn.points) / diag)
    ref_out = o3d.geometry.PointCloud()
    ref_out.points = o3d.utility.Vector3dVector(np.asarray(rn.points) / diag)
    return aligned, ref_out, float(icp.fitness)


def umeyama(src: np.ndarray, dst: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray, float]:
    """Least-squares similarity transform dst ~ s * R @ src + t. Returns (s, R, t, rms_residual)."""
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    var = (xs ** 2).sum() / len(src)
    s = float(np.trace(np.diag(D) @ S) / var) if var > 0 else 1.0
    t = mu_d - s * R @ mu_s
    resid = float(np.sqrt(((dst - (s * (R @ src.T).T + t)) ** 2).sum(axis=1).mean()))
    return s, R, t, resid


def decompose_projection(P: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """3x4 projection matrix -> (world-to-camera rotation, camera centre in world coordinates)."""
    import cv2

    P = np.asarray(P, dtype=np.float64).reshape(3, 4)
    _, R, c = cv2.decomposeProjectionMatrix(P)[:3]
    return R, (c[:3] / c[3]).ravel()


def align_by_cameras(pred_cams: Dict[str, Tuple[np.ndarray, np.ndarray]],
                     gt_cams: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> Optional[Dict[str, Any]]:
    """Similarity transform from the reconstruction frame to the ground-truth frame using shared cameras.

    Each camera is (world-to-camera rotation, centre). Returns the transform and the mean camera rotation error
    in degrees after alignment, or None when fewer than 3 cameras are shared.
    """
    names = [n for n in pred_cams if n in gt_cams]
    if len(names) < 3:
        return None
    src = np.array([pred_cams[n][1] for n in names])
    dst = np.array([gt_cams[n][1] for n in names])
    s, R, t, resid = umeyama(src, dst)
    errs = []
    for n in names:
        Rp = pred_cams[n][0]
        Rg = gt_cams[n][0]
        R_aligned = Rp @ R.T           # world-to-camera rotation expressed in the ground-truth frame
        cos = (np.trace(Rg.T @ R_aligned) - 1.0) / 2.0
        errs.append(float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))))
    extent = float(np.linalg.norm(dst.max(axis=0) - dst.min(axis=0))) or 1.0
    return {"scale": s, "R": R, "t": t, "residual": resid, "relative_residual": resid / extent,
            "pose_error_deg": round(float(np.mean(errs)), 2), "n_cameras": len(names)}


def reference_metrics(pred, ref, threshold: float = F_SCORE_THRESHOLD,
                      sim3: Optional[Dict[str, Any]] = None, crop_margin: float = 0.15) -> Dict[str, Any]:
    """Chamfer / F-score / completeness / accuracy and the error histogram, against a reference cloud.

    With `sim3` (from `align_by_cameras`) the prediction is moved into the reference frame using the known
    camera poses; otherwise it is aligned to the reference geometry (FPFH + RANSAC + ICP).
    The prediction is cropped to the reference bounding box (plus margin) so background clutter is not
    counted as error.
    """
    import open3d as o3d

    if sim3 is not None:
        pts = np.asarray(pred.points)
        moved = o3d.geometry.PointCloud()
        moved.points = o3d.utility.Vector3dVector(sim3["scale"] * (sim3["R"] @ pts.T).T + sim3["t"])
        bb_min, bb_max = ref.get_min_bound(), ref.get_max_bound()
        margin = (bb_max - bb_min) * crop_margin
        moved = moved.crop(o3d.geometry.AxisAlignedBoundingBox(bb_min - margin, bb_max + margin))
        if len(moved.points) < 10:
            raise ValueError("fewer than 10 reconstructed points fall inside the ground-truth region")
        diag = float(np.linalg.norm(bb_max - bb_min)) or 1.0
        aligned = o3d.geometry.PointCloud()
        aligned.points = o3d.utility.Vector3dVector(np.asarray(moved.points) / diag)
        ref_n = o3d.geometry.PointCloud()
        ref_n.points = o3d.utility.Vector3dVector(np.asarray(ref.points) / diag)
        fitness = 1.0
    else:
        aligned, ref_n, fitness = align_to_reference(pred, ref)
        bb_min, bb_max = ref_n.get_min_bound(), ref_n.get_max_bound()
        margin = (bb_max - bb_min) * crop_margin
        cropped = aligned.crop(o3d.geometry.AxisAlignedBoundingBox(bb_min - margin, bb_max + margin))
        if len(cropped.points) >= 10:
            aligned = cropped
    d_pr = np.asarray(aligned.compute_point_cloud_distance(ref_n))   # prediction -> reference
    d_rp = np.asarray(ref_n.compute_point_cloud_distance(aligned))   # reference -> prediction
    precision = float((d_pr < threshold).mean())
    recall = float((d_rp < threshold).mean())
    f = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    hi = float(max(np.percentile(d_pr, 99), 1e-6))
    counts, edges = np.histogram(np.clip(d_pr, 0, hi), bins=8, range=(0.0, hi))
    return {
        "chamfer_distance": round(float(d_pr.mean() + d_rp.mean()) / 2.0, 5),
        "f_score": round(f, 4),
        "completeness_pct": round(100.0 * recall, 1),
        "accuracy": round(precision, 4),
        "alignment_fitness": round(fitness, 3),
        "alignment": "ground_truth_cameras" if sim3 is not None else "geometry (FPFH + ICP)",
        "error_histogram": {"bins": [round(float(e), 5) for e in edges], "counts": [int(c) for c in counts],
                            "unit": "ground-truth bounding-box diagonal"},
    }


def floating_artifact_pct(pcd) -> Optional[float]:
    """Percent of points that are isolated from the main surface (a proxy for floating artifacts).

    A point is isolated when fewer than 3 neighbours lie within 6x the median nearest-neighbour distance.
    Needs no ground truth.
    """

    n = len(pcd.points)
    if n < 20:
        return None
    nn = np.asarray(pcd.compute_nearest_neighbor_distance())
    radius = float(np.median(nn)) * 6.0
    if radius <= 0:
        return None
    _, kept = pcd.remove_radius_outlier(nb_points=3, radius=radius)
    return round(100.0 * (n - len(kept)) / n, 1)

