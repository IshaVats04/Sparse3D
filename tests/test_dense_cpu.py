"""Plane-sweep dense stereo on a synthetic textured plane with known cameras."""

import cv2
import numpy as np

from src.reconstruction.colmap_model import Camera, Image, Point3D, SparseModel, rotmat_to_qvec
from src.reconstruction.dense_cpu import choose_neighbours, dense_cpu

W, H, F = 320, 240, 300.0
PLANE_Z = 5.0
SCALE = 60.0      # texture pixels per world unit


def build_scene(tmp_path, n_views=3):
    """Cameras along x looking down +z at the plane z = 5 that carries a random texture."""
    # dense random texture: stereo needs texture everywhere, unlike the sparse rectangles of textured_image
    rng = np.random.default_rng(7)
    tex = cv2.GaussianBlur(rng.integers(0, 255, (1200, 1200, 3), dtype=np.uint8), (0, 0), 1.5)
    cam = Camera(1, "PINHOLE", W, H, [F, F, W / 2, H / 2])
    model = SparseModel({1: cam}, {}, {})
    rng = np.random.default_rng(0)
    world_pts = np.column_stack([rng.uniform(-0.9, 1.3, 80), rng.uniform(-1.0, 1.0, 80), np.full(80, PLANE_Z)])
    for pid, p in enumerate(world_pts, start=1):
        model.points3D[pid] = Point3D(p, np.array([0.5, 0.5, 0.5]), 0.3, n_views)
    for i in range(n_views):
        centre = np.array([0.35 * i, 0.0, 0.0])
        u, v = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        x = (u - W / 2) * PLANE_Z / F + centre[0]
        y = (v - H / 2) * PLANE_Z / F + centre[1]
        img = cv2.remap(tex, (x * SCALE + 600).astype(np.float32), (y * SCALE + 600).astype(np.float32),
                        cv2.INTER_LINEAR)
        name = f"v{i}.png"
        cv2.imwrite(str(tmp_path / name), img)
        t = -centre                                                  # R = I, so t = -C
        xy = np.array([[F * (p[0] - centre[0]) / PLANE_Z + W / 2, F * (p[1] - centre[1]) / PLANE_Z + H / 2]
                       for p in world_pts])
        model.images[i + 1] = Image(i + 1, rotmat_to_qvec(np.eye(3)), t, 1, name,
                                    list(range(1, 81)), xy)
    return model


def test_neighbours_need_shared_points_and_parallax(tmp_path):
    model = build_scene(tmp_path)
    nbrs = choose_neighbours(model, model.images[1])
    assert {n.image_id for n in nbrs} == {2, 3}


def test_dense_cloud_lies_on_the_plane(tmp_path):
    model = build_scene(tmp_path)
    out = dense_cpu(model, tmp_path, max_side=320)
    assert out is not None
    pts, cols, stats = out
    assert len(pts) > 5000 and stats["views_used"] == 3
    assert np.median(np.abs(pts[:, 2] - PLANE_Z)) < 0.05 * PLANE_Z      # within 5% of the true depth
    assert cols.shape == pts.shape and cols.min() >= 0 and cols.max() <= 1


def test_too_few_shared_points_gives_no_dense_cloud(tmp_path):
    model = build_scene(tmp_path)
    for im in model.images.values():
        im.point3d_ids = [-1] * len(im.point3d_ids)
    assert dense_cpu(model, tmp_path, max_side=320) is None
