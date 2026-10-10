"""Feed-forward neural backend: unprojection geometry and the COLMAP-free pipeline path.

The real VGGT weights are not available in the test environment, so a stand-in predictor/function supplies
predictions with known geometry. These tests verify our code around the model, not the model's quality.
"""

import cv2
import numpy as np

from src.reconstruction import config as cfg
from src.reconstruction import pipeline as pipeline_module
from src.reconstruction.neural import cloud_from_predictions
from src.reconstruction.pipeline import ReconstructionPipeline
from tests.conftest import textured_image

W, H, F = 64, 48, 60.0
PLANE_Z = 3.0


def planar_predictions(n_views=3):
    """Cameras translated along x looking at the plane z = 3; predicted depth equals the true plane depth."""
    K = np.array([[F, 0, W / 2], [0, F, H / 2], [0, 0, 1.0]])
    ext, depth, conf, imgs = [], [], [], []
    for i in range(n_views):
        shift = 0.2 * i
        ext.append(np.hstack([np.eye(3), np.array([[-shift], [0.0], [0.0]])]))   # camera centre (shift, 0, 0)
        depth.append(np.full((H, W), PLANE_Z))
        c = np.ones((H, W))
        c[:, : W // 4] = 0.1                                                      # low-confidence strip
        conf.append(c)
        imgs.append(np.full((H, W, 3), 0.5))
    return {"extrinsic": np.array(ext), "intrinsic": np.array([K] * n_views), "depth": np.array(depth),
            "conf": np.array(conf), "images": np.array(imgs)}


def test_unprojection_lands_on_the_plane_and_drops_low_confidence():
    pred = planar_predictions()
    pts, cols, cams = cloud_from_predictions(pred, conf_percentile=30)   # the weak strip is 25% of all pixels
    assert np.allclose(pts[:, 2], PLANE_Z, atol=1e-6)
    assert len(pts) == 3 * H * (W - W // 4)            # the low-confidence strip is gone
    assert cols.shape == pts.shape
    R, centre = cams[2]
    assert np.allclose(R, np.eye(3)) and np.allclose(centre, [0.4, 0.0, 0.0])


def test_unprojection_is_thinned_to_max_points():
    pts, _, _ = cloud_from_predictions(planar_predictions(), conf_percentile=0, max_points=500)
    assert len(pts) == 500


def test_neural_only_run_skips_colmap_and_reports_poses(tmp_path, monkeypatch):
    paths = []
    for i in range(3):
        p = tmp_path / f"v{i}.png"
        cv2.imwrite(str(p), textured_image(i, (480, 360)))
        paths.append(p)

    monkeypatch.setattr(cfg, "torch_status", lambda: {
        "torch_available": True, "cuda_available": False, "device": "cpu", "neural_available": True,
        "neural_backend": "vggt", "neural_reason": None})

    def fake_run_vggt(view_paths, log=None, cancelled=None):
        rng = np.random.default_rng(0)
        v = rng.normal(size=(3000, 3))
        pts = v / np.linalg.norm(v, axis=1, keepdims=True)
        cams = [(np.eye(3), np.array([0.3 * i, 0.0, -4.0])) for i in range(len(view_paths))]
        return pts, rng.uniform(size=(3000, 3)), cams, {"model": "fake", "device": "cpu"}

    monkeypatch.setattr(pipeline_module, "run_vggt", fake_run_vggt)
    stages = {}
    pipe = ReconstructionPipeline("neural1", paths, tmp_path / "ws", tmp_path / "out",
                                  options={"recon_method": "neural", "quality": "fast"},
                                  on_stage=lambda k, s: stages.__setitem__(k, s))
    pipe.colmap = None   # prove that COLMAP is not needed
    report = pipe.run()

    assert report["status"] == "completed", report["error_message"]
    res = report["results"]["neural"]
    assert res["status"] == "completed" and res["point_count"] > 2000 and len(res["cameras"]) == 3
    assert res["registration"]["ratio_pct"] is None and res["registration"]["registered"] == 3
    assert report["results"]["classical"]["status"] == "skipped"
    assert stages["feature_extraction"] == "skipped" and stages["camera_pose"] == "skipped"
    assert (tmp_path / "out" / "neural1" / "neural_point_cloud.ply").is_file()


def test_pose_error_is_computed_for_the_neural_backend(tmp_path, monkeypatch):
    """Known projection matrices for the views let the feed-forward cameras be scored too."""
    paths = []
    for i in range(3):
        p = tmp_path / f"v{i}.png"
        cv2.imwrite(str(p), textured_image(i, (480, 360)))
        paths.append(p)
    monkeypatch.setattr(cfg, "torch_status", lambda: {
        "torch_available": True, "cuda_available": False, "device": "cpu", "neural_available": True,
        "neural_backend": "vggt", "neural_reason": None})
    centres = [np.array([1.0, 0, 0]), np.array([0, 2.0, 0]), np.array([0, 0, 3.0]), ]

    def fake_run_vggt(view_paths, log=None, cancelled=None):
        rng = np.random.default_rng(0)
        pts = rng.normal(size=(500, 3))
        # identical camera set (identity rotations) => zero pose error after similarity alignment
        return pts, np.full((500, 3), 0.5), [(np.eye(3), c) for c in centres[: len(view_paths)]], \
            {"model": "fake", "device": "cpu"}

    monkeypatch.setattr(pipeline_module, "run_vggt", fake_run_vggt)
    K = np.array([[100.0, 0, 160], [0, 100, 120], [0, 0, 1]])
    proj = {p.name: (K @ np.hstack([np.eye(3), (-c).reshape(3, 1)])).tolist() for p, c in zip(paths, centres)}
    pipe = ReconstructionPipeline("neural2", paths, tmp_path / "ws", tmp_path / "out",
                                  options={"recon_method": "neural", "quality": "fast"}, gt_projections=proj)
    report = pipe.run()
    assert report["results"]["neural"]["metrics"]["camera_pose_error_deg"] < 1e-3

