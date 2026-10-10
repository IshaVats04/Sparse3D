#!/usr/bin/env python3
"""Sparse3D unified reconstruction engine.

Stages (reported to the UI as five steps):
  1. image_analysis      quality/overlap analysis, view selection, preprocessing
  2. feature_extraction  COLMAP SIFT extraction + exhaustive matching
  3. camera_pose         COLMAP incremental SfM (sparse model, camera poses)
  4. reconstruction      classical: dense MVS when a CUDA GPU is present, else the sparse cloud; Open3D clean-up
                         and optional meshing.  neural: learned depth priors fused with the SfM poses
  5. evaluation          floating-artifact estimate and, when a ground-truth model is supplied, Chamfer
                         distance / F-score / completeness / accuracy

Both methods share stages 1-3 (the neural method needs the SfM poses), so each method's runtime includes the
shared SfM time. No metric is ever invented: values that cannot be measured are None.
"""

import csv
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from . import config as cfg
from .colmap_model import SparseModel, count_registered_images, read_model_txt, rotmat_to_qvec
from .metrics import (
    align_by_cameras,
    decompose_projection,
    floating_artifact_pct,
    load_reference_points,
    reference_metrics,
)
from .neural import NeuralUnavailable, reconstruct_neural, run_vggt
from .quality_check import analyze_images, public_report, read_image, write_image
from .view_selection import select_views

logger = logging.getLogger("Sparse3D.Pipeline")

STAGES = [
    ("image_analysis", "Image Analysis"),
    ("feature_extraction", "Feature Extraction"),
    ("camera_pose", "Camera Pose Estimation"),
    ("reconstruction", "3D Reconstruction"),
    ("evaluation", "Evaluation"),
]
# progress (%) at the start of each stage
STAGE_START = {"image_analysis": 0, "feature_extraction": 15, "camera_pose": 45,
               "reconstruction": 65, "evaluation": 90, "complete": 100}

# SfM attempts, tried in order until at least 3 views register. Photos differ a lot (baseline, texture, lighting),
# so a single parameter set cannot serve "any image": later strategies trade speed for tolerance.
SFM_STRATEGIES: List[Dict[str, Any]] = [
    {"name": "standard", "feature_factor": 1, "sift": {}, "match": {},
     "mapper": {"Mapper.init_min_num_inliers": "30", "Mapper.abs_pose_min_num_inliers": "15",
                "Mapper.abs_pose_min_inlier_ratio": "0.1", "Mapper.min_num_matches": "10",
                "Mapper.init_min_tri_angle": "8"}},
    {"name": "tolerant", "feature_factor": 2, "cpu_only": True,
     "sift": {"SiftExtraction.estimate_affine_shape": "1", "SiftExtraction.domain_size_pooling": "1"},
     "match": {"FeatureMatching.guided_matching": "1", "SiftMatching.max_ratio": "0.9"},
     "mapper": {"Mapper.init_min_num_inliers": "15", "Mapper.abs_pose_min_num_inliers": "10",
                "Mapper.abs_pose_min_inlier_ratio": "0.05", "Mapper.min_num_matches": "8",
                "Mapper.init_min_tri_angle": "3", "Mapper.init_max_forward_motion": "1.0"}},
]

METHOD_LABELS = {"classical": "Classical (COLMAP + Open3D)", "neural": "Neural (PyTorch)"}


class Cancelled(Exception):
    """Raised inside the pipeline when the user cancels the job."""


def _o3d_path(path: Path) -> Tuple[str, Optional[Path]]:
    """Open3D's C++ I/O can fail on non-ASCII Windows paths; route those through an ASCII temp file."""
    s = str(path)
    if s.isascii():
        return s, None
    tmp = Path(tempfile.mkdtemp(prefix="s3d_")) / path.name
    return str(tmp), path


def write_point_cloud(path: Path, pcd) -> None:
    import open3d as o3d
    tmp, final = _o3d_path(path)
    o3d.io.write_point_cloud(tmp, pcd)
    if final:
        shutil.move(tmp, final)


def write_mesh(path: Path, mesh) -> None:
    import open3d as o3d
    tmp, final = _o3d_path(path)
    o3d.io.write_triangle_mesh(tmp, mesh)
    if final:
        shutil.move(tmp, final)


class ReconstructionPipeline:
    """Runs one experiment (one image subset, one configuration) and returns a result dictionary."""

    def __init__(
        self,
        job_id: str,
        input_image_paths: List[Path],
        workspace_dir: Path,
        output_dir: Path,
        options: Optional[Dict[str, Any]] = None,
        ground_truth_path: Optional[Path] = None,
        gt_projections: Optional[Dict[str, Any]] = None,
        on_stage: Callable[[str, str], None] = lambda key, status: None,
        on_progress: Callable[[float], None] = lambda pct: None,
        on_log: Callable[[str], None] = lambda line: None,
        cancel_event: Optional[threading.Event] = None,
    ):
        o = {"recon_method": "both", "num_views": None, "view_arrangement": "auto", "quality": "standard",
             "estimate_poses": True, "run_evaluation": True, "generate_mesh": False, "save_intermediate": False,
             "mesh_method": "poisson", "seed": 0}
        o.update(options or {})
        if o["recon_method"] not in ("classical", "neural", "both"):
            raise ValueError(f"Unknown recon_method '{o['recon_method']}'")
        if o["quality"] not in cfg.QUALITY_PRESETS:
            raise ValueError(f"Unknown quality '{o['quality']}'")
        self.opt = o
        self.preset = cfg.QUALITY_PRESETS[o["quality"]]
        self.job_id = job_id
        self.raw_paths = [Path(p).resolve() for p in input_image_paths]
        self.workspace = Path(workspace_dir).resolve() / job_id
        self.out = Path(output_dir).resolve() / job_id
        self.gt_path = Path(ground_truth_path) if ground_truth_path else None
        # original image name -> known 3x4 projection matrix (e.g. DTU calibration), enables pose error and
        # camera-based alignment to the ground-truth cloud
        self.gt_proj = {k: np.asarray(v, dtype=np.float64) for k, v in (gt_projections or {}).items()}
        self.colmap = cfg.find_colmap()
        self.use_gpu = cfg.colmap_can_use_gpu()

        self.images_dir = self.workspace / "images"
        self.db_path = self.workspace / "database.db"
        self.sparse_dir = self.workspace / "sparse"
        self.dense_dir = self.workspace / "dense"
        self.model_txt = self.out / "sparse_model"
        for d in (self.images_dir, self.sparse_dir, self.out):
            d.mkdir(parents=True, exist_ok=True)

        self.on_stage, self.on_progress, self.on_log = on_stage, on_progress, on_log
        self.cancel_event = cancel_event or threading.Event()
        self.logs: List[str] = []
        self.warnings: List[str] = []
        self.stage_times: Dict[str, float] = {}
        self.name_map: Dict[str, str] = {}       # processed file name -> original upload name
        self.validation: Optional[Dict[str, Any]] = None
        self.selected: List[str] = []

    # ------------------------------------------------------------------ helpers
    def log(self, message: str, level: str = "INFO") -> None:
        line = f"[{time.strftime('%H:%M:%S')}] [{level}] {message}"
        self.logs.append(line)
        self.on_log(line)
        if level == "WARNING":
            self.warnings.append(message)
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        else:
            logger.info(message)

    def _check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled()

    def _begin(self, key: str) -> float:
        self._check_cancel()
        self.on_stage(key, "running")
        self.on_progress(STAGE_START[key])
        self.log(f"--- {dict(STAGES)[key]} ---")
        return time.time()

    def _end(self, key: str, t0: float, status: str = "complete") -> None:
        # accumulates, because the SfM stages can run more than once (retry strategies)
        self.stage_times[key] = round(self.stage_times.get(key, 0.0) + time.time() - t0, 2)
        self.on_stage(key, status)

    def _run(self, args: List[str], name: str) -> bool:
        """Run an external command without a shell, killing it promptly if the job is cancelled."""
        self.log(f"{name}: {os.path.basename(args[0])} {' '.join(args[1:3])} ...")
        t0 = time.time()
        log_file = self.workspace / f"{name}.log"
        with open(log_file, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT)
            while True:
                try:
                    proc.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancel_event.is_set():
                        proc.kill()
                        proc.wait()
                        raise Cancelled()
        elapsed = time.time() - t0
        self.stage_times[name] = round(elapsed, 2)
        if proc.returncode != 0:
            tail = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:]
            self.log(f"{name} failed (exit {proc.returncode}): {' | '.join(tail)}", "ERROR")
            return False
        self.log(f"{name} finished in {elapsed:.1f}s")
        return True

    # ------------------------------------------------------------ stage 1
    def stage_image_analysis(self) -> bool:
        t0 = self._begin("image_analysis")
        report = analyze_images(self.raw_paths)
        self.validation = public_report(report)
        for m in report["messages"]:
            if m["level"] == "warn":
                self.log(m["text"], "WARNING")
        bad = [i["name"] for i in report["images"] if i["status"] == "error"]
        usable = [p for p in self.raw_paths if p.name not in bad]
        if len(usable) < 3:
            self.log(f"Only {len(usable)} usable image(s); at least 3 are required", "ERROR")
            self._end("image_analysis", t0, "failed")
            return False

        k = self.opt["num_views"] or len(usable)
        k = min(k, len(usable))
        names = [p.name for p in usable]
        usable_pairs = [pr for pr in report["pairs"] if pr["a"] in names and pr["b"] in names]
        self.selected = select_views(names, k, self.opt["view_arrangement"], usable_pairs, self.opt["seed"])
        self.log(f"Using {len(self.selected)} of {len(usable)} images "
                 f"(arrangement: {self.opt['view_arrangement']}): {', '.join(self.selected)}")

        used_names = set()
        for p in usable:
            if p.name not in self.selected:
                continue
            img = read_image(p)
            h, w = img.shape[:2]
            dim = self.preset["max_image_dim"]
            if max(h, w) > dim:
                s = dim / max(h, w)
                img = cv2_resize(img, int(w * s), int(h * s))
                self.log(f"Resized {p.name}: {w}x{h} -> {img.shape[1]}x{img.shape[0]}")
            out_name = f"{p.stem}.png"
            n = 1
            while out_name in used_names:
                n += 1
                out_name = f"{p.stem}_{n}.png"
            used_names.add(out_name)
            if not write_image(self.images_dir / out_name, img):
                self.log(f"Could not write preprocessed image for {p.name}", "ERROR")
                self._end("image_analysis", t0, "failed")
                return False
            self.name_map[out_name] = p.name
        self._end("image_analysis", t0)
        return True

    # ------------------------------------------------------------ stage 2
    def _reset_sfm(self) -> None:
        """Clear the COLMAP database and models before a retry."""
        if self.db_path.is_file():
            self.db_path.unlink()
        shutil.rmtree(self.sparse_dir, ignore_errors=True)
        self.sparse_dir.mkdir(parents=True, exist_ok=True)
        for p in self.workspace.glob("txt_*"):
            shutil.rmtree(p, ignore_errors=True)

    def _camera_flags(self) -> List[str]:
        """One shared camera when all images have the same size (one device); otherwise one camera per image."""
        sizes = set()
        for p in self.images_dir.glob("*.png"):
            img = read_image(p)
            if img is not None:
                sizes.add(img.shape[:2])
        if len(sizes) <= 1:
            return ["--ImageReader.single_camera", "1"]
        self.log("Images have different sizes; using a separate camera model per image")
        return ["--ImageReader.single_camera_per_image", "1"]

    def stage_features(self, strategy: Dict[str, Any]) -> bool:
        t0 = self._begin("feature_extraction")
        if not self.colmap:
            self.log("COLMAP was not found. Install it (see README) or set SPARSE3D_COLMAP.", "ERROR")
            self._end("feature_extraction", t0, "failed")
            return False
        # Affine shape / domain-size pooling are CPU-only in COLMAP
        gpu = "1" if self.use_gpu and not strategy.get("cpu_only") else "0"
        self.log(f"COLMAP {'GPU' if gpu == '1' else 'CPU'} mode, strategy '{strategy['name']}'")
        extract = [
            self.colmap, "feature_extractor", "--database_path", str(self.db_path),
            "--image_path", str(self.images_dir), *self._camera_flags(),
            "--FeatureExtraction.use_gpu", gpu,
            "--SiftExtraction.max_num_features", str(self.preset["max_features"] * strategy["feature_factor"]),
        ]
        for k, v in strategy["sift"].items():
            extract += [f"--{k}", v]
        ok = self._run(extract, "sift_extraction")
        self.on_progress(30)
        match = [self.colmap, "exhaustive_matcher", "--database_path", str(self.db_path),
                 "--FeatureMatching.use_gpu", gpu]
        for k, v in strategy["match"].items():
            match += [f"--{k}", v]
        ok = ok and self._run(match, "sift_matching")
        self._end("feature_extraction", t0, "complete" if ok else "failed")
        return ok

    # ------------------------------------------------------------ stage 3
    def stage_poses(self, strategy: Dict[str, Any]) -> Optional[SparseModel]:
        t0 = self._begin("camera_pose")
        mapper = [
            self.colmap, "mapper", "--database_path", str(self.db_path),
            "--image_path", str(self.images_dir), "--output_path", str(self.sparse_dir),
            "--Mapper.min_model_size", "3",
        ]
        for k, v in strategy["mapper"].items():
            mapper += [f"--{k}", v]
        ok = self._run(mapper, "mapper")
        models = [d for d in self.sparse_dir.iterdir() if d.is_dir()] if ok else []
        if not models:
            self.log("COLMAP could not build any sparse model from these views", "ERROR")
            self._end("camera_pose", t0, "failed")
            return None

        # Convert every candidate model to text and keep the one that registered the most images
        best, best_n = None, -1
        for d in models:
            tmp = self.workspace / f"txt_{d.name}"
            tmp.mkdir(exist_ok=True)
            if not self._run([self.colmap, "model_converter", "--input_path", str(d),
                              "--output_path", str(tmp), "--output_type", "TXT"], f"export_{d.name}"):
                continue
            n = count_registered_images(tmp)
            if n > best_n:
                best, best_n = tmp, n
        if best is None:
            self._end("camera_pose", t0, "failed")
            return None
        if self.model_txt.exists():
            shutil.rmtree(self.model_txt)
        shutil.copytree(best, self.model_txt)
        model = read_model_txt(self.model_txt)
        total = len(self.name_map)
        self.log(f"Registered {len(model.images)} of {total} views, {len(model.points3D)} sparse points")
        if len(model.images) < total:
            self.log(f"{total - len(model.images)} view(s) failed to register", "WARNING")
        self._end("camera_pose", t0)
        return model

    # ------------------------------------------------------------ stage 4
    def _registration(self, model: SparseModel) -> Dict[str, Any]:
        errs = [p.error for p in model.points3D.values()]
        names = [self.name_map.get(i.name, i.name) for i in model.images.values()]
        total = len(self.name_map)
        return {"total_input": total, "registered": len(model.images),
                "ratio_pct": round(100.0 * len(model.images) / max(1, total), 1), "names": names,
                "mean_reprojection_error_px": round(float(np.mean(errs)), 3) if errs else None}

    def _model_cameras(self, model: SparseModel) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """name -> (world-to-camera rotation, camera centre) for every registered view."""
        return {self.name_map.get(i.name, i.name): (i.rotation(), i.center()) for i in model.images.values()}

    @staticmethod
    def _camera_json(cams: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> List[Dict[str, Any]]:
        """Camera centre and camera-to-world orientation (w, x, y, z; +z forward, +y down)."""
        out = []
        for name, (R, c) in cams.items():
            q = rotmat_to_qvec(R.T)
            out.append({"name": name, "position": [round(float(v), 5) for v in c],
                        "rotation": [round(float(v), 6) for v in q]})
        return out

    def _classical_cloud(self, model: SparseModel):
        """Dense MVS cloud when possible, otherwise the sparse cloud. Returns (pcd, mode)."""
        import open3d as o3d

        if self.use_gpu and cfg.colmap_has_cuda():
            self.log("Dense reconstruction (undistortion, PatchMatch stereo, fusion)")
            fused = self.dense_dir / "fused.ply"
            self.dense_dir.mkdir(parents=True, exist_ok=True)
            ok = (self._run([self.colmap, "image_undistorter", "--image_path", str(self.images_dir),
                             "--input_path", str(self.model_txt), "--output_path", str(self.dense_dir),
                             "--output_type", "COLMAP"], "dense_undistortion")
                  and self._run([self.colmap, "patch_match_stereo", "--workspace_path", str(self.dense_dir),
                                 "--workspace_format", "COLMAP", "--PatchMatchStereo.geom_consistency", "true"],
                                "patch_match_stereo")
                  and self._run([self.colmap, "stereo_fusion", "--workspace_path", str(self.dense_dir),
                                 "--workspace_format", "COLMAP", "--input_type", "geometric",
                                 # the default (5 consistent pixels) discards nearly everything with 3-6 views
                                 "--StereoFusion.min_num_pixels", "2",
                                 "--output_path", str(fused)], "stereo_fusion"))
            if ok and fused.is_file() and fused.stat().st_size > 0:
                tmp, _ = _o3d_path(fused)
                pcd = o3d.io.read_point_cloud(tmp)
                if len(pcd.points) > 0:
                    return pcd, "dense"
            self.log("Dense MVS failed; falling back to the sparse point cloud", "WARNING")
        else:
            self.log("Dense MVS skipped (needs a CUDA-enabled COLMAP and an NVIDIA GPU, e.g. a Colab worker); "
                     "using the sparse SfM point cloud", "WARNING")
        pts = np.array([p.xyz for p in model.points3D.values()])
        cols = np.array([p.rgb for p in model.points3D.values()])
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts)
        pcd.colors = o3d.utility.Vector3dVector(cols)
        return pcd, "sparse"

    def _clean_cloud(self, pcd):
        """Statistical outlier removal."""
        n0 = len(pcd.points)
        if n0 > 30:
            pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=min(20, n0 - 1), std_ratio=2.0)
        self.log(f"Outlier filtering: {n0} -> {len(pcd.points)} points")
        return pcd

    def _estimate_normals(self, pcd, cam_centres: np.ndarray) -> None:
        import open3d as o3d

        pts = np.asarray(pcd.points)
        extent = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) or 1.0
        pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=extent * 0.05, max_nn=30))
        if len(cam_centres):
            pcd.orient_normals_towards_camera_location(cam_centres.mean(axis=0))

    def _mesh(self, pcd, out_path: Path) -> Dict[str, int]:
        import open3d as o3d

        method = self.opt["mesh_method"]
        if not self.opt["generate_mesh"] or method == "none":
            return {"vertex_count": 0, "triangle_count": 0}
        if len(pcd.points) < 100:
            self.log("Too few points for meshing; skipped", "WARNING")
            return {"vertex_count": 0, "triangle_count": 0}
        try:
            if method == "ball_pivoting":
                d = float(np.mean(pcd.compute_nearest_neighbor_distance()))
                mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
                    pcd, o3d.utility.DoubleVector([d * r for r in (0.5, 1.0, 2.0, 4.0)]))
            else:
                mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                    pcd, depth=self.preset["poisson_depth"], linear_fit=True)
                dens = np.asarray(dens)
                mesh.remove_vertices_by_mask(dens < np.quantile(dens, 0.05))
                mesh = mesh.crop(pcd.get_axis_aligned_bounding_box())
            mesh.remove_degenerate_triangles()
            mesh.remove_duplicated_triangles()
            mesh.remove_duplicated_vertices()
            mesh.remove_non_manifold_edges()
            if len(mesh.triangles) == 0:
                self.log("Meshing produced no triangles", "WARNING")
                return {"vertex_count": 0, "triangle_count": 0}
            write_mesh(out_path, mesh)
            return {"vertex_count": len(mesh.vertices), "triangle_count": len(mesh.triangles)}
        except Exception as exc:
            self.log(f"Meshing failed: {exc}", "WARNING")
            return {"vertex_count": 0, "triangle_count": 0}

    def _empty_result(self, method: str, status: str, message: str) -> Dict[str, Any]:
        return {"status": status, "message": message, "label": METHOD_LABELS[method], "runtime_sec": None,
                "files": {"point_cloud": None, "mesh": None, "camera_poses": None}, "point_count": 0,
                "mesh": {"vertex_count": 0, "triangle_count": 0}, "registration": None, "cameras": [],
                "metrics": None, "metrics_note": None, "error_histogram": None}

    def _finish_method(self, method: str, pcd, base_sec: float, own_sec: float, prefix: str, note: str,
                       registration: Dict[str, Any], cams: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> Dict[str, Any]:
        """Write the cloud (and mesh) and build the method result. `base_sec` is the time of the stages this method
        depends on (image analysis, plus SfM when it needs it); `own_sec` is its own reconstruction time."""
        cams_json = self._camera_json(cams) if self.opt["estimate_poses"] else []
        centres = np.array([c[1] for c in cams.values()]) if cams else np.zeros((0, 3))
        self._estimate_normals(pcd, centres)
        pc_path = self.out / f"{prefix}point_cloud.ply"
        write_point_cloud(pc_path, pcd)
        t0 = time.time()
        mesh_stats = self._mesh(pcd, self.out / f"{prefix}mesh.ply")
        res = self._empty_result(method, "completed", note)
        res.update({
            "runtime_sec": round(base_sec + own_sec + (time.time() - t0), 1),
            "files": {"point_cloud": pc_path.name,
                      "mesh": f"{prefix}mesh.ply" if mesh_stats["triangle_count"] else None,
                      "camera_poses": "camera_poses.txt" if cams_json else None},
            "point_count": len(pcd.points), "mesh": mesh_stats, "registration": registration, "cameras": cams_json,
        })
        # private, consumed by the evaluation stage and removed before the report is saved
        res["_pcd"] = pcd
        res["_cams"] = cams
        return res

    def _vggt_inputs(self) -> List[Path]:
        """Preprocessed view images in the order the views were selected."""
        by_orig = {orig: out for out, orig in self.name_map.items()}
        return [self.images_dir / by_orig[n] for n in self.selected if n in by_orig]

    def _run_neural(self, model: Optional[SparseModel], sfm_error: Optional[str], analysis_sec: float,
                    sfm_sec: float) -> Dict[str, Any]:
        import open3d as o3d

        status = cfg.torch_status()
        backend = status["neural_backend"]
        if backend is None:
            msg = str(status["neural_reason"])
            self.log(f"Neural method unavailable: {msg}", "WARNING")
            return self._empty_result("neural", "unavailable", msg)
        n0 = time.time()
        try:
            if backend == "vggt":
                paths = self._vggt_inputs()
                pts, cols, cams, stats = run_vggt(paths, log=self.log, cancelled=self.cancel_event.is_set)
                cams = {self.name_map.get(p.name, p.name): rt for p, rt in zip(paths, cams)}
                registration = {"total_input": len(paths), "registered": len(cams), "ratio_pct": None,
                                "names": list(cams), "mean_reprojection_error_px": None}
                note = (f"{stats['model']} feed-forward reconstruction without SfM "
                        f"({len(paths)} view(s), device: {stats['device']})")
                base = analysis_sec
            else:
                if model is None:
                    msg = f"The depth-fusion fallback needs SfM poses: {sfm_error or 'SfM did not run'}"
                    self.log(msg, "WARNING")
                    return self._empty_result("neural", "failed", msg)
                pts, cols, stats = reconstruct_neural(
                    model, self.images_dir, stride=self.preset["depth_stride"], log=self.log,
                    cancelled=self.cancel_event.is_set)
                cams = self._model_cameras(model)
                registration = self._registration(model)
                note = (f"{stats['model']} depth prior fused with SfM poses "
                        f"({stats['views_used']} view(s), device: {stats['device']})")
                base = analysis_sec + sfm_sec
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(pts)
            pcd.colors = o3d.utility.Vector3dVector(cols)
            pcd = self._clean_cloud(pcd)
            res = self._finish_method("neural", pcd, base, time.time() - n0, "neural_", note, registration, cams)
            self.log(f"Neural ({backend}): {len(pcd.points)} points")
            return res
        except Cancelled:
            raise
        except NeuralUnavailable as exc:
            self.log(f"Neural method unavailable: {exc}", "WARNING")
            return self._empty_result("neural", "unavailable", str(exc))
        except Exception as exc:
            self.log(f"Neural reconstruction failed: {exc}", "ERROR")
            return self._empty_result("neural", "failed", str(exc))

    def stage_reconstruction(self, model: Optional[SparseModel], sfm_error: Optional[str]
                             ) -> Dict[str, Optional[Dict[str, Any]]]:
        t0 = self._begin("reconstruction")
        results: Dict[str, Optional[Dict[str, Any]]] = {"classical": None, "neural": None}
        method = self.opt["recon_method"]
        analysis_sec = self.stage_times.get("image_analysis", 0.0)
        sfm_sec = self.stage_times.get("feature_extraction", 0.0) + self.stage_times.get("camera_pose", 0.0)

        if method in ("classical", "both"):
            self._check_cancel()
            if model is None:
                results["classical"] = self._empty_result("classical", "failed", sfm_error or "SfM did not run")
            else:
                c0 = time.time()
                try:
                    pcd, mode = self._classical_cloud(model)
                    pcd = self._clean_cloud(pcd)
                    note = ("Dense multi-view stereo point cloud" if mode == "dense"
                            else "Sparse SfM point cloud (dense MVS needs a CUDA GPU; e.g. a Colab worker)")
                    results["classical"] = self._finish_method(
                        "classical", pcd, analysis_sec + sfm_sec, time.time() - c0, "", note,
                        self._registration(model), self._model_cameras(model))
                    self.log(f"Classical: {len(pcd.points)} points ({mode})")
                except Cancelled:
                    raise
                except Exception as exc:
                    self.log(f"Classical reconstruction failed: {exc}", "ERROR")
                    results["classical"] = self._empty_result("classical", "failed", str(exc))

        if method in ("neural", "both"):
            self._check_cancel()
            results["neural"] = self._run_neural(model, sfm_error, analysis_sec, sfm_sec)

        for m in ("classical", "neural"):
            if results[m] is None:
                results[m] = self._empty_result(m, "skipped", "Not selected for this experiment")
        done = any(r["status"] == "completed" for r in results.values())
        self._end("reconstruction", t0, "complete" if done else "failed")
        return results

    # ------------------------------------------------------------ stage 5
    def stage_evaluation(self, results: Dict[str, Dict[str, Any]]) -> bool:
        t0 = self._begin("evaluation")
        ref = None
        gt_cams = {n: decompose_projection(P) for n, P in self.gt_proj.items()} if self.gt_proj else {}
        if self.opt["run_evaluation"] and self.gt_path:
            try:
                ref = load_reference_points(self.gt_path)
                self.log(f"Ground-truth model loaded: {len(ref.points)} points")
            except Exception as exc:
                self.log(f"Could not read the ground-truth model: {exc}", "WARNING")

        for name, res in results.items():
            pcd = res.pop("_pcd", None)
            cams = res.pop("_cams", None)
            if res["status"] != "completed" or pcd is None:
                continue
            reg = res["registration"] or {}
            metrics = {"chamfer_distance": None, "f_score": None, "completeness_pct": None, "accuracy": None,
                       "camera_pose_error_deg": None, "runtime_sec": res["runtime_sec"],
                       "point_count": res["point_count"],
                       "reprojection_error_px": reg.get("mean_reprojection_error_px"),
                       "registration_ratio_pct": reg.get("ratio_pct"), "floating_artifact_pct": None}
            if self.opt["run_evaluation"]:
                sim3 = align_by_cameras(cams, gt_cams) if gt_cams and cams else None
                if gt_cams and sim3 is None:
                    self.log(f"{name}: fewer than 3 views have ground-truth poses; pose error not computed",
                             "WARNING")
                if sim3 is not None:
                    metrics["camera_pose_error_deg"] = sim3["pose_error_deg"]
                    self.log(f"{name}: camera pose error {sim3['pose_error_deg']} deg over {sim3['n_cameras']} views "
                             "(similarity-aligned to the ground-truth cameras)")
                    if sim3["relative_residual"] > 0.1:
                        self.log(f"{name}: cameras fit the ground-truth cameras poorly; pose-aligned metrics may "
                                 "be unreliable", "WARNING")
                try:
                    metrics["floating_artifact_pct"] = floating_artifact_pct(pcd)
                except Exception as exc:
                    self.log(f"{name}: artifact estimate failed: {exc}", "WARNING")
                if ref is not None:
                    try:
                        trusted = sim3 if sim3 and sim3["relative_residual"] <= 0.1 else None
                        rm = reference_metrics(pcd, ref, sim3=trusted)
                        for k in ("chamfer_distance", "f_score", "completeness_pct", "accuracy"):
                            metrics[k] = rm[k]
                        res["error_histogram"] = rm["error_histogram"]
                        self.log(f"{name}: Chamfer {rm['chamfer_distance']}, F-score {rm['f_score']} "
                                 f"(alignment: {rm['alignment']}, fitness {rm['alignment_fitness']})")
                        if rm["alignment_fitness"] < 0.3:
                            self.log(f"{name}: alignment to the ground truth is weak "
                                     f"(fitness {rm['alignment_fitness']}); reference metrics may be unreliable",
                                     "WARNING")
                    except Exception as exc:
                        self.log(f"{name}: reference evaluation failed: {exc}", "WARNING")
                res["metrics_note"] = None if ref is not None else (
                    "Chamfer distance, F-score, completeness and accuracy need a ground-truth model; "
                    "upload one with the experiment to enable them. Camera pose error needs known camera poses.")
            else:
                res["metrics_note"] = "Evaluation was disabled for this experiment."
            res["metrics"] = metrics
        self._end("evaluation", t0)
        return ref is not None

    # ------------------------------------------------------------ exports
    def _write_exports(self, results: Dict[str, Dict[str, Any]]) -> None:
        cams = next((r["cameras"] for r in results.values() if r.get("cameras")), [])
        if cams:
            with open(self.out / "camera_poses.txt", "w", encoding="utf-8") as f:
                f.write(f"# Camera poses for {self.job_id}; position in world coordinates, rotation = camera-to-world "
                        "quaternion (w x y z), COLMAP convention (+z forward, +y down)\n# NAME  X Y Z  QW QX QY QZ\n")
                for c in cams:
                    f.write(f"{c['name']} {' '.join(map(str, c['position']))} {' '.join(map(str, c['rotation']))}\n")
        with open(self.out / "evaluation_metrics.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            keys = ["chamfer_distance", "f_score", "completeness_pct", "accuracy", "camera_pose_error_deg",
                    "runtime_sec", "point_count", "reprojection_error_px", "registration_ratio_pct",
                    "floating_artifact_pct"]
            w.writerow(["metric", "classical", "neural"])
            for k in keys:
                row = [k]
                for m in ("classical", "neural"):
                    met = results[m].get("metrics")
                    row.append("" if not met or met.get(k) is None else met[k])
                w.writerow(row)

    # ------------------------------------------------------------ structure from motion driver
    def _needs_sfm(self) -> bool:
        """COLMAP is needed for the classical method and for the depth-fusion neural fallback. The feed-forward
        neural backend (VGGT) estimates poses itself, so a neural-only run works without COLMAP."""
        method = self.opt["recon_method"]
        if method in ("classical", "both"):
            return True
        return cfg.torch_status()["neural_backend"] != "vggt"

    def _run_sfm(self) -> Tuple[Optional[SparseModel], Optional[str]]:
        """Run feature extraction, matching and mapping with retries. Returns (model, error message)."""
        model = best = None
        error = None
        best_dir = self.workspace / "best_model"
        for attempt, strategy in enumerate(SFM_STRATEGIES):
            if attempt:
                self.log(f"Retrying structure-from-motion with the '{strategy['name']}' strategy", "WARNING")
                self._reset_sfm()
            if not self.stage_features(strategy):
                error = "Feature extraction or matching failed"
                break
            model = self.stage_poses(strategy)
            if model is not None and (best is None or len(model.images) > len(best.images)):
                best = model
                shutil.rmtree(best_dir, ignore_errors=True)
                shutil.copytree(self.model_txt, best_dir)
            if model is not None and len(model.images) >= 3:
                break
            if model is not None:
                self.log(f"Only {len(model.images)} view(s) registered", "WARNING")
        if best is not None and best is not model:  # a later attempt was worse; restore the best model
            shutil.rmtree(self.model_txt, ignore_errors=True)
            shutil.copytree(best_dir, self.model_txt)
        shutil.rmtree(best_dir, ignore_errors=True)
        if error:
            return None, error
        if best is None or len(best.images) < 2:
            return None, ("Camera pose estimation failed: the views do not overlap enough, the object lacks "
                          "texture, or the baseline between views is too small")
        return best, None

    # ------------------------------------------------------------ driver
    def run(self) -> Dict[str, Any]:
        t_start = time.time()
        self.log(f"Starting experiment {self.job_id}")
        results: Dict[str, Dict[str, Any]] = {m: self._empty_result(m, "skipped", "Not run") for m in METHOD_LABELS}
        status, error, has_gt = "failed", None, False
        try:
            if not self.stage_image_analysis():
                error = "Image validation failed"
            else:
                model, sfm_error = None, None
                if self._needs_sfm():
                    model, sfm_error = self._run_sfm()
                else:
                    self.log("Neural-only run with a feed-forward model: skipping COLMAP")
                    self.on_stage("feature_extraction", "skipped")
                    self.on_stage("camera_pose", "skipped")
                results = self.stage_reconstruction(model, sfm_error)
                has_gt = self.stage_evaluation(results)
                self._write_exports(results)
                wanted = [m for m in ("classical", "neural") if self.opt["recon_method"] in (m, "both")]
                ok = [m for m in wanted if results[m]["status"] == "completed"]
                status = "completed" if len(ok) == len(wanted) else ("partial_success" if ok else "failed")
                if not ok:
                    error = "; ".join(results[m]["message"] or m for m in wanted)
        except Cancelled:
            status, error = "cancelled", "Cancelled by user"
            self.log("Experiment cancelled", "WARNING")
        except Exception as exc:  # unexpected; surfaced to the user rather than swallowed
            logger.exception("Pipeline crashed")
            error = f"Unexpected error: {exc}"
            self.log(error, "ERROR")

        for res in results.values():
            res.pop("_pcd", None)
            res.pop("_cams", None)
        total = round(time.time() - t_start, 2)
        self.stage_times["total_pipeline"] = total
        if not self.opt["save_intermediate"]:
            shutil.rmtree(self.dense_dir, ignore_errors=True)
            shutil.rmtree(self.workspace / "sparse", ignore_errors=True)
            for p in self.workspace.glob("txt_*"):
                shutil.rmtree(p, ignore_errors=True)
            if self.db_path.is_file():
                self.db_path.unlink()
        self.log(f"Experiment finished: {status.upper()} in {total}s")
        report = {
            "job_id": self.job_id, "status": status, "error_message": error,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "selected_images": self.selected, "validation": self.validation, "has_ground_truth": has_gt,
            "options": self.opt, "hardware": {"colmap": self.colmap, "colmap_gpu": self.use_gpu},
            "stage_execution_times_sec": self.stage_times, "results": results,
            "warnings": self.warnings, "logs": self.logs,
        }
        with open(self.out / "report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
        return report


def cv2_resize(img: np.ndarray, w: int, h: int) -> np.ndarray:
    import cv2
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
