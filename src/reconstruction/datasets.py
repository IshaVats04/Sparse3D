"""Dataset discovery: large local datasets (DTU MVS) and plain image folders.

Datasets are never copied wholesale. Only the images chosen for an experiment are read, so a multi-gigabyte
dataset can sit on disk and any subset of views can be reconstructed from it.

Search roots (all are scanned, to a limited depth):
  * every path in the SPARSE3D_DATASET_DIR environment variable (separated by os.pathsep)
  * data/datasets and data/samples inside the repository

Recognised layouts
  DTU MVS (https://roboimagedata.compute.dtu.dk/?page_id=36), the "SampleSet" or the full set:
      <root>/**/Cleaned/scanN/clean_CCC_L_r5000.png   (or Rectified/scanN[_train]/rect_CCC_L_r5000.png)
      <root>/**/Calibration/cal18/pos_CCC.txt         3x4 projection matrices: known camera poses
      <root>/**/Points/stl/stlNNN_total.ply           ground-truth point cloud (millimetres)
  Image folder: any directory with at least 3 images, optionally containing ground_truth.ply/.obj/.stl.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from . import config as cfg

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
DTU_IMAGE_RE = re.compile(r"^(clean|rect)_(\d+)_(\d+)(?:_r\d+)?\.(png|jpg|jpeg)$", re.IGNORECASE)
SCAN_DIR_RE = re.compile(r"^scan(\d+)(?:_train)?$", re.IGNORECASE)
MAX_DEPTH = 6


@dataclass
class ImageRef:
    name: str
    path: Path
    camera: Optional[int] = None
    lighting: Optional[int] = None


@dataclass
class Scan:
    id: str
    name: str
    images: List[ImageRef]
    ground_truth: Optional[Path] = None
    calibration_dir: Optional[Path] = None

    @property
    def cameras(self) -> List[int]:
        return sorted({i.camera for i in self.images if i.camera is not None})

    @property
    def lightings(self) -> List[int]:
        return sorted({i.lighting for i in self.images if i.lighting is not None})

    def projection(self, camera: int) -> Optional[np.ndarray]:
        """Known 3x4 projection matrix of a DTU camera, if the calibration folder is present."""
        if not self.calibration_dir:
            return None
        f = self.calibration_dir / f"pos_{camera:03d}.txt"
        if not f.is_file():
            return None
        try:
            return np.loadtxt(f).reshape(3, 4)
        except Exception:
            return None


@dataclass
class Dataset:
    id: str
    kind: str                      # "dtu" | "folder"
    name: str
    root: Path
    scans: Dict[str, Scan] = field(default_factory=dict)


def _slug(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).lower().encode()).hexdigest()[:8]


def search_roots() -> List[Path]:
    roots: List[Path] = []
    for p in os.environ.get("SPARSE3D_DATASET_DIR", "").split(os.pathsep):
        if p.strip():
            roots.append(Path(p.strip()))
    roots += [cfg.PROJECT_ROOT / "data" / "datasets", cfg.PROJECT_ROOT / "data" / "samples"]
    return [r for r in roots if r.is_dir()]


def _images_in(d: Path) -> List[Path]:
    try:
        return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    except OSError:
        return []


def _find_ground_truth(d: Path) -> Optional[Path]:
    for ext in (".ply", ".obj", ".stl"):
        f = d / f"ground_truth{ext}"
        if f.is_file():
            return f
    return None


def _walk(root: Path, depth: int = 0):
    """Yield directories below root (bounded depth); never descends into hidden or build folders."""
    yield root
    if depth >= MAX_DEPTH:
        return
    try:
        children = sorted(c for c in root.iterdir() if c.is_dir() and not c.name.startswith((".", "$")))
    except OSError:
        return
    for c in children:
        if c.name in {"node_modules", "__pycache__", "Depth", "Surfaces"}:
            continue
        yield from _walk(c, depth + 1)


def _dtu_scans(images_root: Path, mvs_root: Path) -> Dict[str, Scan]:
    """Scans of one DTU `Cleaned` / `Rectified` directory."""
    scans: Dict[str, Scan] = {}
    cal = next((c for c in (mvs_root / "Calibration" / "cal18", mvs_root / "Calibration") if c.is_dir()), None)
    for d in sorted(images_root.iterdir()):
        m = SCAN_DIR_RE.match(d.name) if d.is_dir() else None
        if not m:
            continue
        scan_no = int(m.group(1))
        refs = []
        for p in _images_in(d):
            im = DTU_IMAGE_RE.match(p.name)
            if im:
                refs.append(ImageRef(p.name, p, int(im.group(2)), int(im.group(3))))
        if not refs:
            continue
        gt = None
        for cand in (f"stl{scan_no:03d}_total.ply", f"stl{scan_no:03d}_tot.ply"):
            for pts_dir in (mvs_root / "Points" / "stl", mvs_root / "Points"):
                if (pts_dir / cand).is_file():
                    gt = pts_dir / cand
                    break
            if gt:
                break
        scans[f"scan{scan_no}"] = Scan(f"scan{scan_no}", f"Scan {scan_no}", refs, gt, cal)
    return scans


def discover() -> List[Dataset]:
    """Scan the search roots and return the datasets found."""
    found: Dict[str, Dataset] = {}
    seen_dirs = set()
    for root in search_roots():
        for d in _walk(root):
            rd = d.resolve()
            if rd in seen_dirs:
                continue
            if d.name.lower() in ("cleaned", "rectified"):
                mvs_root = d.parent
                scans = _dtu_scans(d, mvs_root)
                if scans:
                    key = f"dtu-{_slug(d)}"
                    found[key] = Dataset(key, "dtu", f"DTU MVS ({mvs_root.name}/{d.name})", d, scans)
                    for s in d.iterdir():
                        seen_dirs.add(s.resolve())
                continue
            if d.parent.name.lower() in ("cleaned", "rectified"):
                continue
            imgs = _images_in(d)
            if len(imgs) >= 3 and not any(DTU_IMAGE_RE.match(p.name) for p in imgs):
                key = f"folder-{_slug(d)}"
                refs = [ImageRef(p.name, p) for p in imgs]
                scan = Scan("all", d.name, refs, _find_ground_truth(d))
                found[key] = Dataset(key, "folder", d.name, d, {"all": scan})
    return list(found.values())


def get_dataset(dataset_id: str) -> Optional[Dataset]:
    return next((d for d in discover() if d.id == dataset_id), None)


def default_cameras(scan: Scan, count: int = 6) -> List[int]:
    """Evenly spaced camera ids across the available ones."""
    cams = scan.cameras
    if len(cams) <= count:
        return cams
    idx = np.linspace(0, len(cams) - 1, count).round().astype(int)
    return [cams[i] for i in idx]


def select_images(scan: Scan, cameras: Optional[List[int]] = None, lighting: Optional[int] = None) -> List[ImageRef]:
    """Images of a scan for the given camera ids (DTU) and lighting condition, in camera order."""
    if scan.cameras:
        cams = cameras or default_cameras(scan)
        if lighting is None:
            lighting = 0 if 0 in scan.lightings else (scan.lightings[0] if scan.lightings else None)
        by_cam = {i.camera: i for i in scan.images if lighting is None or i.lighting == lighting}
        missing = [c for c in cams if c not in by_cam]
        if missing:
            raise ValueError(f"Camera(s) {missing} not available for {scan.name} (lighting {lighting})")
        return [by_cam[c] for c in cams]
    return list(scan.images)
