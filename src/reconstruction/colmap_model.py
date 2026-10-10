"""Parser for COLMAP text models (cameras.txt, images.txt, points3D.txt) and camera geometry helpers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np


@dataclass
class Camera:
    camera_id: int
    model: str
    width: int
    height: int
    params: List[float]

    def intrinsics(self) -> np.ndarray:
        """3x3 pinhole intrinsics (lens distortion is ignored)."""
        p = self.params
        if self.model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
            f, cx, cy = p[0], p[1], p[2]
            fx = fy = f
        elif self.model in ("PINHOLE", "OPENCV", "FULL_OPENCV", "OPENCV_FISHEYE"):
            fx, fy, cx, cy = p[0], p[1], p[2], p[3]
        else:
            raise ValueError(f"Unsupported COLMAP camera model: {self.model}")
        return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


@dataclass
class Image:
    image_id: int
    qvec: np.ndarray          # world -> camera rotation (w, x, y, z)
    tvec: np.ndarray          # world -> camera translation
    camera_id: int
    name: str
    point3d_ids: List[int] = field(default_factory=list)
    xys: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))

    def rotation(self) -> np.ndarray:
        return qvec_to_rotmat(self.qvec)

    def center(self) -> np.ndarray:
        """Camera centre in world coordinates."""
        return -self.rotation().T @ self.tvec


@dataclass
class Point3D:
    xyz: np.ndarray
    rgb: np.ndarray
    error: float
    track_len: int


@dataclass
class SparseModel:
    cameras: Dict[int, Camera]
    images: Dict[int, Image]
    points3D: Dict[int, Point3D]


def qvec_to_rotmat(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
        [2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x],
        [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y],
    ])


def rotmat_to_qvec(R: np.ndarray) -> np.ndarray:
    """Rotation matrix -> unit quaternion (w, x, y, z) with w >= 0."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def _data_lines(path: Path) -> List[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def read_model_txt(model_dir: Path) -> SparseModel:
    """Read a COLMAP text model directory."""
    model_dir = Path(model_dir)
    cameras: Dict[int, Camera] = {}
    for ln in _data_lines(model_dir / "cameras.txt"):
        p = ln.split()
        cameras[int(p[0])] = Camera(int(p[0]), p[1], int(p[2]), int(p[3]), [float(x) for x in p[4:]])

    images: Dict[int, Image] = {}
    # images.txt stores two lines per image, and the second (2D points) line is empty for an image without
    # observations, so blank lines must be kept when pairing lines.
    with open(model_dir / "images.txt", "r", encoding="utf-8", errors="replace") as f:
        raw = [ln for ln in f.read().splitlines() if not ln.startswith("#")]
    i = 0
    while i < len(raw):
        head = raw[i].split()
        if len(head) < 10:
            i += 1
            continue
        pts_line = raw[i + 1].split() if i + 1 < len(raw) else []
        xys = np.array(pts_line, dtype=float).reshape(-1, 3) if pts_line else np.zeros((0, 3))
        images[int(head[0])] = Image(
            image_id=int(head[0]),
            qvec=np.array([float(x) for x in head[1:5]]),
            tvec=np.array([float(x) for x in head[5:8]]),
            camera_id=int(head[8]),
            name=" ".join(head[9:]),
            point3d_ids=[int(v) for v in xys[:, 2]] if len(xys) else [],
            xys=xys[:, :2] if len(xys) else np.zeros((0, 2)),
        )
        i += 2

    points: Dict[int, Point3D] = {}
    p3d = model_dir / "points3D.txt"
    if p3d.is_file():
        for ln in _data_lines(p3d):
            p = ln.split()
            if len(p) < 8:
                continue
            points[int(p[0])] = Point3D(
                xyz=np.array([float(p[1]), float(p[2]), float(p[3])]),
                rgb=np.array([float(p[4]), float(p[5]), float(p[6])]) / 255.0,
                error=float(p[7]),
                track_len=(len(p) - 8) // 2,
            )
    return SparseModel(cameras, images, points)


def count_registered_images(model_dir: Path) -> int:
    """Number of registered images in a text model directory (0 if unreadable)."""
    try:
        return len(read_model_txt(model_dir).images)
    except Exception:
        return 0
