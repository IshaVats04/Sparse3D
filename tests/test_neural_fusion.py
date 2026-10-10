"""Check the neural fusion geometry with a stand-in depth estimator.

The real network needs downloaded weights, so this test injects an estimator that returns an affinely
distorted *true* inverse depth (what a monocular network gives: correct ordering, unknown scale/shift).
The fusion must undo the distortion using the sparse points and land back on the true surface.
This verifies the geometry only; it says nothing about the quality of the pretrained network.
"""

import cv2
import numpy as np

from src.reconstruction.colmap_model import Camera, Image, Point3D, SparseModel, rotmat_to_qvec
from src.reconstruction.neural import _fit_scale_shift, reconstruct_neural

W, H, F = 160, 120, 150.0
Z_PLANE = 4.0  # the scene is the plane z = 4 in world coordinates; cameras look down +z


def make_model(tmp_path):
    cam = Camera(1, "SIMPLE_PINHOLE", W, H, [F, W / 2, H / 2])
    rng = np.random.default_rng(0)
    model = SparseModel({1: cam}, {}, {})
    for iid, shift in enumerate((-0.3, 0.0, 0.3), start=1):
        R = np.eye(3)
        t = np.array([-shift, 0.0, 0.0])            # camera centre at (shift, 0, 0)
        xys, ids = [], []
        for j in range(60):
            u, v = rng.uniform(40, W - 40), rng.uniform(30, H - 30)
            xyz_cam = np.array([(u - W / 2) / F * Z_PLANE, (v - H / 2) / F * Z_PLANE, Z_PLANE])
            xyz = R.T @ (xyz_cam - t)
            pid = len(model.points3D) + 1
            model.points3D[pid] = Point3D(xyz, np.array([0.5, 0.5, 0.5]), 0.3, 3)
            xys.append([u, v])
            ids.append(pid)
        model.images[iid] = Image(iid, rotmat_to_qvec(R), t, 1, f"v{iid}.png", ids, np.array(xys))
        cv2.imwrite(str(tmp_path / f"v{iid}.png"), np.full((H, W, 3), 128, np.uint8))
    return model


class FakeEstimator:
    model_name, device = "fake", "cpu"

    def inverse_depth(self, img):
        true_inv = np.full(img.shape[:2], 1.0 / Z_PLANE, np.float32)
        true_inv += np.linspace(-0.01, 0.01, img.shape[1], dtype=np.float32)[None, :]  # slight slope
        return 3.7 * true_inv - 0.08  # unknown scale and shift, as from a monocular network


def test_fusion_recovers_scale_and_surface(tmp_path):
    model = make_model(tmp_path)
    pts, cols, stats = reconstruct_neural(model, tmp_path, stride=4, estimator=FakeEstimator())
    assert stats["views_used"] == 3 and len(pts) > 500
    assert np.abs(pts[:, 2] - Z_PLANE).max() < 0.15   # depth ~ plane after scale/shift recovery
    assert cols.shape == pts.shape and cols.max() <= 1.0


def test_scale_shift_fit_is_robust_to_outliers():
    rng = np.random.default_rng(1)
    rel = rng.uniform(0.1, 1.0, 200)
    target = 2.0 * rel + 0.3
    target[:20] += rng.uniform(1, 3, 20)  # gross outliers (bad triangulations)
    a, b, _ = _fit_scale_shift(rel, target)
    assert abs(a - 2.0) < 0.1 and abs(b - 0.3) < 0.1
