"""Shared fixtures. The backend is pointed at a throw-away workspace so tests never touch real experiments."""

import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="sparse3d_tests_"))
os.environ["SPARSE3D_WORKSPACE"] = str(_TMP / "workspace" / "jobs")
os.environ["SPARSE3D_OUTPUT"] = str(_TMP / "outputs" / "jobs")
os.environ["SPARSE3D_DB"] = str(_TMP / "workspace" / "experiments.db")


def textured_image(seed: int, size=(320, 240)) -> np.ndarray:
    """A random blob/line image with plenty of corners so SIFT finds features."""
    rng = np.random.default_rng(seed)
    img = np.full((size[1], size[0], 3), 90, np.uint8)
    for _ in range(60):
        c = tuple(int(v) for v in rng.integers(0, 255, 3))
        p1 = (int(rng.integers(0, size[0])), int(rng.integers(0, size[1])))
        p2 = (int(rng.integers(0, size[0])), int(rng.integers(0, size[1])))
        cv2.rectangle(img, p1, p2, c, -1 if rng.random() < 0.5 else 2)
    return img


@pytest.fixture
def image_files(tmp_path):
    paths = []
    for i in range(4):
        p = tmp_path / f"view_{i}.png"
        cv2.imwrite(str(p), textured_image(i))
        paths.append(p)
    return paths
