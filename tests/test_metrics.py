import numpy as np
import open3d as o3d

from src.reconstruction.metrics import floating_artifact_pct, reference_metrics


def sphere(n=6000, r=1.0, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    v = v / np.linalg.norm(v, axis=1, keepdims=True) * r
    p = o3d.geometry.PointCloud()
    p.points = o3d.utility.Vector3dVector(v)
    return p


def transformed(pcd, scale=1.0, angle=0.7, shift=(3.0, -2.0, 1.0)):
    out = o3d.geometry.PointCloud(pcd)
    out.rotate(o3d.geometry.get_rotation_matrix_from_xyz((angle, 0.3, -0.5)), center=(0, 0, 0))
    out.scale(scale, center=(0, 0, 0))
    out.translate(shift)
    return out


def bumpy(n=8000, seed=0):
    """An asymmetric object (ellipsoid with a bump) so alignment has a unique solution."""
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    v = v / np.linalg.norm(v, axis=1, keepdims=True) * np.array([1.0, 0.6, 0.35])
    v[:, 2] += 0.25 * np.exp(-((v[:, 0] - 0.5) ** 2 + v[:, 1] ** 2) / 0.1)
    p = o3d.geometry.PointCloud()
    p.points = o3d.utility.Vector3dVector(v)
    return p


def test_identical_geometry_in_a_different_frame_scores_near_perfect():
    ref = bumpy(seed=0)
    pred = transformed(bumpy(seed=1), scale=2.5)   # different samples, arbitrary similarity transform
    m = reference_metrics(pred, ref)
    assert m["f_score"] > 0.9
    assert m["chamfer_distance"] < 0.02
    assert m["completeness_pct"] > 90 and m["accuracy"] > 0.9


def test_camera_based_alignment_and_background_cropping():
    ref = bumpy(seed=0)
    ang = 0.7
    R = np.array([[np.cos(ang), -np.sin(ang), 0], [np.sin(ang), np.cos(ang), 0], [0, 0, 1]])
    pred_pts = 0.4 * (R @ np.asarray(bumpy(seed=1).points).T).T + np.array([5.0, 1.0, -2.0])  # reconstruction frame
    clutter = np.random.default_rng(2).uniform(-40, 40, (2000, 3))                           # background far away
    pred = o3d.geometry.PointCloud()
    pred.points = o3d.utility.Vector3dVector(np.vstack([pred_pts, clutter]))
    # the transform that maps the reconstruction frame back onto the reference frame
    sim3 = {"scale": 1 / 0.4, "R": R.T, "t": -(1 / 0.4) * (R.T @ np.array([5.0, 1.0, -2.0]))}
    m = reference_metrics(pred, ref, sim3=sim3)
    assert m["alignment"] == "ground_truth_cameras"
    assert m["f_score"] > 0.9 and m["accuracy"] > 0.9   # the clutter was cropped away, not counted as error


def test_half_the_object_has_low_completeness():
    ref = bumpy(seed=0)
    pts = np.asarray(bumpy(seed=1).points)
    half = o3d.geometry.PointCloud()
    half.points = o3d.utility.Vector3dVector(pts[pts[:, 0] > 0])
    m = reference_metrics(transformed(half), ref)
    assert m["completeness_pct"] < 75
    assert m["accuracy"] > m["completeness_pct"] / 100


def test_floating_artifacts_detected():
    s = sphere()
    clean = floating_artifact_pct(s)
    pts = np.vstack([np.asarray(s.points), np.random.default_rng(3).uniform(-4, 4, (300, 3))])
    noisy = o3d.geometry.PointCloud()
    noisy.points = o3d.utility.Vector3dVector(pts)
    assert floating_artifact_pct(noisy) > clean + 3


def test_tiny_cloud_returns_none():
    p = o3d.geometry.PointCloud()
    p.points = o3d.utility.Vector3dVector(np.random.rand(5, 3))
    assert floating_artifact_pct(p) is None
