"""Shared configuration: project paths, COLMAP discovery, hardware detection and quality presets."""

import os
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def _default_data_root() -> Path:
    """Where job workspaces, outputs and the history database live.

    Inside the project folder, except when that folder is synced by OneDrive: sync clients lock and re-upload
    the many small/large files (including COLMAP's SQLite database) that a run produces, which makes runs fail
    and slow. In that case a local per-user folder is used. Override with SPARSE3D_DATA_DIR.
    """
    env = os.environ.get("SPARSE3D_DATA_DIR")
    if env:
        return Path(env)
    if "onedrive" in str(PROJECT_ROOT).lower():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        return Path(base) / "Sparse3D"
    return PROJECT_ROOT


DATA_ROOT = _default_data_root()
WORKSPACE_DIR = Path(os.environ.get("SPARSE3D_WORKSPACE", DATA_ROOT / "workspace" / "jobs"))
OUTPUT_DIR = Path(os.environ.get("SPARSE3D_OUTPUT", DATA_ROOT / "outputs" / "jobs"))
EXAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
DB_PATH = Path(os.environ.get("SPARSE3D_DB", DATA_ROOT / "workspace" / "experiments.db"))

# Per-quality settings: image long side, SIFT features per image, Poisson depth, dense (MVS) window
QUALITY_PRESETS: Dict[str, Dict[str, int]] = {
    "fast": {"max_image_dim": 1024, "max_features": 4096, "poisson_depth": 7, "depth_stride": 6,
             "dense_cpu_side": 640},
    "standard": {"max_image_dim": 1600, "max_features": 8192, "poisson_depth": 8, "depth_stride": 4,
                 "dense_cpu_side": 960},
    "high": {"max_image_dim": 2400, "max_features": 16384, "poisson_depth": 9, "depth_stride": 2,
             "dense_cpu_side": 1400},
}


@lru_cache(maxsize=1)
def find_colmap() -> Optional[str]:
    """Locate the COLMAP executable.

    Order: SPARSE3D_COLMAP env var, tools/colmap bundled with the project, PATH.
    """
    candidates = []
    env = os.environ.get("SPARSE3D_COLMAP")
    if env:
        candidates.append(env)
    exe = "colmap.exe" if sys.platform == "win32" else "colmap"
    candidates.append(str(PROJECT_ROOT / "tools" / "colmap" / "bin" / exe))
    candidates.append(str(PROJECT_ROOT / "tools" / "colmap" / exe))
    for name in ("colmap", "colmap.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for cand in candidates:
        if cand and Path(cand).is_file():
            return str(Path(cand).resolve())
    return None


@lru_cache(maxsize=1)
def colmap_has_cuda() -> bool:
    """True when the located COLMAP build reports CUDA support."""
    exe = find_colmap()
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "help"], capture_output=True, text=True, timeout=30)
        return "with CUDA" in (out.stdout + out.stderr)
    except Exception:
        return False


@lru_cache(maxsize=1)
def nvidia_gpu_present() -> bool:
    """True when an NVIDIA GPU is usable (nvidia-smi answers)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        out = subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=15)
        return out.returncode == 0 and "GPU" in out.stdout
    except Exception:
        return False


@lru_cache(maxsize=1)
def gpu_name() -> Optional[str]:
    """Name of the first NVIDIA GPU, or None."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run([smi, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                             timeout=15)
        names = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        return names[0] if out.returncode == 0 and names else None
    except Exception:
        return None


def colmap_can_use_gpu() -> bool:
    """COLMAP GPU stages (SIFT on GPU, PatchMatch dense stereo) need a CUDA build and an NVIDIA GPU."""
    return bool(find_colmap()) and colmap_has_cuda() and nvidia_gpu_present()


VGGT_MODEL = "facebook/VGGT-1B"
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
_weights_cache: Dict[str, Tuple[float, Tuple[bool, Optional[str]]]] = {}


def _weights_obtainable(model_id: str) -> Tuple[bool, Optional[str]]:
    """A model is usable when its weights are cached locally or the Hugging Face hub is reachable.

    Results are cached for a minute so /api/health stays cheap.
    """
    now = time.time()
    hit = _weights_cache.get(model_id)
    if hit and now - hit[0] < 60:
        return hit[1]
    value: Tuple[bool, Optional[str]]
    try:
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(model_id, "config.json")
        if isinstance(cached, str):
            value = (True, None)
        else:
            import urllib.request
            urllib.request.urlopen(f"https://huggingface.co/{model_id}/resolve/main/config.json", timeout=3).close()
            value = (True, None)
    except Exception as exc:
        value = (False, f"weights for {model_id} are not cached and huggingface.co is not reachable "
                        f"from this machine ({type(exc).__name__})")
    _weights_cache[model_id] = (now, value)
    return value


def torch_status() -> Dict[str, object]:
    """Which neural backend can run here, without loading a model.

    Backends, best first:
      "vggt"          feed-forward multi-view transformer (facebook/VGGT-1B): cameras, depth and 3D points from
                      3-6 unposed photos, no SfM needed. Needs the `vggt` package.
      "depth_fusion"  Depth Anything V2 depth fused with COLMAP poses. Needs `transformers`.
    Override with SPARSE3D_NEURAL_BACKEND=vggt|depth_fusion.
    """
    try:
        import torch
    except Exception as exc:  # ImportError or a broken install
        return {"torch_available": False, "cuda_available": False, "device": "cpu", "neural_available": False,
                "neural_backend": None, "neural_reason": f"PyTorch is not installed ({type(exc).__name__})"}
    cuda = bool(torch.cuda.is_available())
    base = {"torch_available": True, "cuda_available": cuda, "device": "cuda" if cuda else "cpu"}

    import importlib.util
    forced = os.environ.get("SPARSE3D_NEURAL_BACKEND", "").strip().lower()
    reasons = []
    if forced != "depth_fusion":
        if importlib.util.find_spec("vggt") is None:
            reasons.append("VGGT is not installed (pip install git+https://github.com/facebookresearch/vggt.git)")
        else:
            ok, why = _weights_obtainable(VGGT_MODEL)
            if ok:
                return {**base, "neural_available": True, "neural_backend": "vggt", "neural_reason": None}
            reasons.append(f"VGGT: {why}")
    if forced != "vggt":
        if importlib.util.find_spec("transformers") is None:
            reasons.append("the 'transformers' package is required for the depth-fusion backend")
        else:
            ok, why = _weights_obtainable(DEPTH_MODEL)
            if ok:
                return {**base, "neural_available": True, "neural_backend": "depth_fusion", "neural_reason": None}
            reasons.append(f"depth fusion: {why}")
    return {**base, "neural_available": False, "neural_backend": None, "neural_reason": "; ".join(reasons)}
