"""Neural sparse-view reconstruction (Approach B). Pretrained models only; nothing is trained here.

Two backends (see config.torch_status):

1. VGGT (preferred), `run_vggt`: a feed-forward multi-view transformer (facebook/VGGT-1B) that predicts camera
   poses, depth maps and confidences for all views in one pass from 3-6 unposed photos. It needs no structure from
   motion, so it still works in the regime where COLMAP cannot register the views. Depth is unprojected with the
   predicted cameras, low-confidence pixels are dropped, and the result is one coloured point cloud.

2. Depth fusion (fallback), `reconstruct_neural`: a pretrained monocular depth network (Depth Anything V2) whose
   relative inverse depth is fitted to the sparse points COLMAP triangulated (inverse depth = a * relative + b,
   robust least squares) and back-projected with the COLMAP poses. It needs a successful SfM.

When PyTorch, the package or the weights are unavailable, `NeuralUnavailable` is raised and the pipeline reports
the method as unavailable; no results are simulated.
"""

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .colmap_model import SparseModel
from .config import DEPTH_MODEL as DEFAULT_DEPTH_MODEL
from .config import VGGT_MODEL

MIN_FIT_POINTS = 8


class NeuralUnavailable(RuntimeError):
    """Raised when the neural method cannot run (missing PyTorch, weights, or sparse model)."""


class VGGTPredictor:
    """Wrapper around facebook/VGGT-1B (Visual Geometry Grounded Transformer, Wang et al., CVPR 2025).

    Requires `pip install git+https://github.com/facebookresearch/vggt.git`. The weights are downloaded once from
    the Hugging Face hub. Check the model licence for your use case (the original release is non-commercial).
    """

    def __init__(self, model_name: str = VGGT_MODEL, device: Optional[str] = None):
        try:
            import torch
            from vggt.models.vggt import VGGT
        except Exception as exc:
            raise NeuralUnavailable(f"VGGT is not installed ({exc})") from exc
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        try:
            self.model = VGGT.from_pretrained(model_name).to(self.device).eval()
        except Exception as exc:
            raise NeuralUnavailable(
                f"Could not load '{model_name}' (the weights are downloaded once, so the first run needs internet "
                f"access): {exc}") from exc

    def predict(self, paths: List[Path]) -> Dict[str, np.ndarray]:
        """Run VGGT on the views. Returns numpy arrays for S views of size HxW:
        extrinsic (S,3,4) world-to-camera, intrinsic (S,3,3), depth (S,H,W), conf (S,H,W), images (S,H,W,3) in 0..1.
        """
        from vggt.utils.load_fn import load_and_preprocess_images
        from vggt.utils.pose_enc import pose_encoding_to_extri_intri

        torch = self.torch
        images = load_and_preprocess_images([str(p) for p in paths]).to(self.device)
        with torch.no_grad():
            if self.device == "cuda":
                dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
                with torch.autocast("cuda", dtype=dtype):
                    preds = self.model(images)
            else:
                preds = self.model(images)
            extrinsic, intrinsic = pose_encoding_to_extri_intri(preds["pose_enc"], images.shape[-2:])
        return {
            "extrinsic": extrinsic[0].float().cpu().numpy(),
            "intrinsic": intrinsic[0].float().cpu().numpy(),
            "depth": preds["depth"][0, ..., 0].float().cpu().numpy(),
            "conf": preds["depth_conf"][0].float().cpu().numpy(),
            "images": images.permute(0, 2, 3, 1).float().cpu().numpy(),
        }


def cloud_from_predictions(pred: Dict[str, np.ndarray], conf_percentile: float = 30.0, max_points: int = 400_000,
                           seed: int = 0) -> Tuple[np.ndarray, np.ndarray, List[Tuple[np.ndarray, np.ndarray]]]:
    """Unproject per-view depth with the predicted cameras into one coloured cloud.

    Pixels with confidence below the `conf_percentile`-th percentile (over all views) or non-positive depth are
    dropped; the cloud is randomly thinned to `max_points`. Returns (points, colours, cameras) where cameras is a
    list of (world-to-camera rotation, camera centre) per view, in the order of the input views.
    """
    ext, K, depth, conf, imgs = (pred[k] for k in ("extrinsic", "intrinsic", "depth", "conf", "images"))
    S, H, W = depth.shape
    thresh = float(np.percentile(conf, conf_percentile))
    ys, xs = np.mgrid[0:H, 0:W]
    pix = np.stack([xs.ravel(), ys.ravel(), np.ones(H * W)], axis=0)
    pts, cols, cams = [], [], []
    for s in range(S):
        R, t = ext[s][:, :3].astype(np.float64), ext[s][:, 3].astype(np.float64)
        cams.append((R, -R.T @ t))
        d = depth[s].ravel()
        keep = (conf[s].ravel() >= thresh) & (d > 0) & np.isfinite(d)
        cam_pts = (np.linalg.inv(K[s].astype(np.float64)) @ pix[:, keep]) * d[keep]
        pts.append((R.T @ (cam_pts - t.reshape(3, 1))).T)
        cols.append(imgs[s].reshape(-1, 3)[keep])
    points, colours = np.concatenate(pts), np.clip(np.concatenate(cols), 0.0, 1.0)
    if len(points) > max_points:
        idx = np.random.default_rng(seed).choice(len(points), max_points, replace=False)
        points, colours = points[idx], colours[idx]
    return points, colours, cams


def run_vggt(paths: List[Path], log: Callable[[str, str], None] = lambda msg, level="INFO": None,
             cancelled: Callable[[], bool] = lambda: False, predictor: Optional[VGGTPredictor] = None,
             conf_percentile: float = 30.0) -> Tuple[np.ndarray, np.ndarray, List[Tuple[np.ndarray, np.ndarray]],
                                                     Dict[str, Any]]:
    """Feed-forward reconstruction of the given views. Returns (points, colours, cameras, stats)."""
    if len(paths) < 2:
        raise NeuralUnavailable("At least 2 views are needed")
    t0 = time.time()
    predictor = predictor or VGGTPredictor()
    if cancelled():
        raise NeuralUnavailable("Cancelled")
    log(f"VGGT: predicting cameras and depth for {len(paths)} views on {predictor.device}", "INFO")
    pred = predictor.predict(paths)
    pts, cols, cams = cloud_from_predictions(pred, conf_percentile)
    stats = {"model": predictor.model_name, "device": predictor.device, "views_used": len(paths),
             "inference_sec": round(time.time() - t0, 2)}
    return pts, cols, cams, stats


class DepthEstimator:
    """Pretrained monocular depth network from the Hugging Face hub (safetensors weights, no remote code).

    The weights are downloaded once on first use and cached by `huggingface_hub`.
    """

    def __init__(self, model_name: str = DEFAULT_DEPTH_MODEL, device: Optional[str] = None):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        except Exception as exc:
            raise NeuralUnavailable(f"PyTorch/transformers is not installed ({exc})") from exc
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        try:
            self.processor = AutoImageProcessor.from_pretrained(model_name)
            self.model = AutoModelForDepthEstimation.from_pretrained(model_name)
        except Exception as exc:
            raise NeuralUnavailable(
                f"Could not load the depth network '{model_name}' (the weights are downloaded once, so the first "
                f"run needs internet access): {exc}") from exc
        self.model.to(self.device).eval()

    def inverse_depth(self, img_bgr: np.ndarray) -> np.ndarray:
        """Relative inverse depth (larger = nearer), resized to the input image size."""
        from PIL import Image

        torch = self.torch
        rgb = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        inputs = self.processor(images=rgb, return_tensors="pt").to(self.device)
        with torch.no_grad():
            pred = self.model(**inputs).predicted_depth
            pred = torch.nn.functional.interpolate(
                pred.unsqueeze(1), size=img_bgr.shape[:2], mode="bicubic", align_corners=False).squeeze()
        return pred.cpu().numpy().astype(np.float32)


def _fit_scale_shift(rel: np.ndarray, target: np.ndarray, iters: int = 3) -> Tuple[float, float, float]:
    """Robust fit target ~ a * rel + b. Returns (a, b, median absolute residual)."""
    keep = np.ones(len(rel), dtype=bool)
    a, b = 1.0, 0.0
    for _ in range(iters):
        A = np.stack([rel[keep], np.ones(keep.sum())], axis=1)
        (a, b), *_ = np.linalg.lstsq(A, target[keep], rcond=None)
        res = np.abs(a * rel + b - target)
        thresh = max(float(np.median(res)) * 2.5, 1e-9)
        new_keep = res <= thresh
        if new_keep.sum() < MIN_FIT_POINTS or new_keep.sum() == keep.sum():
            break
        keep = new_keep
    res = np.abs(a * rel + b - target)
    return float(a), float(b), float(np.median(res[keep]))


def reconstruct_neural(
    model: SparseModel,
    images_dir: Path,
    stride: int = 4,
    log: Callable[[str, str], None] = lambda msg, level="INFO": None,
    estimator: Optional[DepthEstimator] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Fuse learned depth priors into a coloured point cloud. Returns (points Nx3, colours Nx3 in 0..1, stats)."""
    if len(model.images) < 2 or len(model.points3D) < MIN_FIT_POINTS:
        raise NeuralUnavailable("The sparse model is too small to anchor the depth predictions")
    estimator = estimator or DepthEstimator()
    t0 = time.time()
    all_pts: List[np.ndarray] = []
    all_cols: List[np.ndarray] = []
    used, skipped = 0, []

    for image in model.images.values():
        if cancelled():
            raise NeuralUnavailable("Cancelled")
        path = Path(images_dir) / image.name
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            skipped.append(image.name)
            continue
        cam = model.cameras[image.camera_id]
        K = cam.intrinsics()
        R, t = image.rotation(), image.tvec
        H, W = img.shape[:2]

        # Sparse observations of this view -> (pixel, camera-space depth)
        ids = np.array(image.point3d_ids)
        mask = ids >= 0
        if mask.sum() < MIN_FIT_POINTS:
            skipped.append(image.name)
            log(f"{image.name}: only {int(mask.sum())} triangulated points; skipped by neural method", "WARNING")
            continue
        pairs = [(p, model.points3D[i].xyz) for p, i in zip(image.xys[mask], ids[mask]) if i in model.points3D]
        if len(pairs) < MIN_FIT_POINTS:
            skipped.append(image.name)
            continue
        xy = np.array([p for p, _ in pairs])
        xyz = np.array([x for _, x in pairs])
        z =(xyz @ R.T + t)[:, 2]
        ok = z > 1e-6
        xy, z = xy[ok], z[ok]
        if len(z) < MIN_FIT_POINTS:
            skipped.append(image.name)
            continue

        rel = estimator.inverse_depth(img)
        xi = np.clip(np.round(xy[:, 0]).astype(int), 0, W - 1)
        yi = np.clip(np.round(xy[:, 1]).astype(int), 0, H - 1)
        a, b, med = _fit_scale_shift(rel[yi, xi], 1.0 / z)
        inv = a * rel + b
        log(f"{image.name}: depth prior fitted to {len(z)} sparse points (median inverse-depth error {med:.4f})")

        # Restrict to the region the sparse points cover (the object), via their convex hull
        hull = cv2.convexHull(np.round(xy).astype(np.int32))
        region = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(region, hull, 1)
        region = cv2.erode(region, np.ones((5, 5), np.uint8))

        ys, xs = np.mgrid[0:H:stride, 0:W:stride]
        sel = region[ys, xs] > 0
        ys, xs = ys[sel], xs[sel]
        d_inv = inv[ys, xs]
        valid = d_inv > 1e-6
        ys, xs, d_inv = ys[valid], xs[valid], d_inv[valid]
        depth = 1.0 / d_inv
        zlo, zhi = float(np.percentile(z, 1)) * 0.6, float(np.percentile(z, 99)) * 1.6
        valid = (depth > zlo) & (depth < zhi)
        ys, xs, depth = ys[valid], xs[valid], depth[valid]
        if len(depth) == 0:
            skipped.append(image.name)
            continue

        pix = np.stack([xs, ys, np.ones_like(xs)], axis=0).astype(np.float64)
        cam_pts = (np.linalg.inv(K) @ pix) * depth
        world = (R.T @ (cam_pts - t.reshape(3, 1))).T
        colours = img[ys, xs][:, ::-1].astype(np.float64) / 255.0
        all_pts.append(world)
        all_cols.append(colours)
        used += 1

    if not all_pts:
        raise NeuralUnavailable("No view could be anchored to the sparse model")

    pts, cols = np.concatenate(all_pts), np.concatenate(all_cols)
    stats = {"views_used": used, "views_skipped": skipped, "model": estimator.model_name,
             "device": estimator.device, "depth_stage_sec": round(time.time() - t0, 2)}
    return pts, cols, stats
