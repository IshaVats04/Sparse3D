#!/usr/bin/env python3
"""
Sparse3D Unified Reconstruction Pipeline Engine.

Orchestrates the 3D reconstruction workflow from 2D images:
1. Input Image Validation & Preprocessing
2. COLMAP Feature Extraction & Feature Matching
3. COLMAP Sparse Reconstruction (Structure-from-Motion)
4. COLMAP Dense Reconstruction (PatchMatch Stereo & Fusion, if GPU supported)
5. Point Cloud Generation & Filtering (Open3D)
6. Mesh Reconstruction (Ball Pivoting / Poisson Surface Reconstruction)
7. Structured Evaluation Report Generation
"""

import os
import sys
import time
import json
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import cv2

# Set up logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("Sparse3D.Pipeline")


class ReconstructionPipeline:
    """Core Reconstruction Service managing job-isolated 3D reconstruction."""

    def __init__(
        self,
        job_id: str,
        input_image_paths: List[Path],
        workspace_dir: Path,
        output_dir: Path,
        colmap_path: Optional[str] = None,
        run_dense: bool = False,
        mesh_method: str = "ball_pivoting",  # 'none', 'ball_pivoting', 'poisson'
        max_image_dim: int = 1600,
        nb_neighbors: int = 20,
        std_ratio: float = 2.0
    ):
        self.job_id = job_id
        self.raw_image_paths = [Path(p).resolve() for p in input_image_paths]
        self.workspace_dir = Path(workspace_dir).resolve() / job_id
        self.output_dir = Path(output_dir).resolve() / job_id

        self.colmap_path = self._resolve_colmap_path(colmap_path)
        self.run_dense = run_dense
        self.mesh_method = mesh_method.lower()
        self.max_image_dim = max_image_dim
        self.nb_neighbors = nb_neighbors
        self.std_ratio = std_ratio

        # Internal workspace subdirectories
        self.images_dir = self.workspace_dir / "images"
        self.db_path = self.workspace_dir / "database.db"
        self.sparse_dir = self.workspace_dir / "sparse"
        self.dense_dir = self.workspace_dir / "dense"

        # Final output paths
        self.point_cloud_ply = self.output_dir / "point_cloud.ply"
        self.mesh_ply = self.output_dir / "mesh.ply"
        self.report_json = self.output_dir / "report.json"
        self.sparse_model_dir = self.output_dir / "sparse_model"

        # Ensure job directories exist
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.sparse_dir.mkdir(parents=True, exist_ok=True)
        self.dense_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Execution tracking state
        self.logs: List[str] = []
        self.warnings: List[str] = []
        self.stage_times: Dict[str, float] = {}

    def log(self, message: str, level: str = "INFO") -> None:
        """Log execution message and retain log entry."""
        entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}"
        self.logs.append(entry)
        if level == "WARNING":
            self.warnings.append(message)
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        else:
            logger.info(message)

    def _resolve_colmap_path(self, colmap_path: Optional[str]) -> str:
        """Find valid COLMAP executable path."""
        candidates = []
        if colmap_path:
            candidates.append(colmap_path)
        candidates.extend(["colmap", "colmap.exe", r"C:\Users\ishav\Downloads\colmap-x64-windows-cuda\bin\colmap.exe"])
        for cand in candidates:
            if shutil.which(cand) or Path(cand).is_file():
                return cand
        return colmap_path or "colmap"

    def _to_cmd_path(self, path: Path) -> str:
        """Convert path to relative path for Windows C++ executable CLI compatibility."""
        try:
            cwd = Path.cwd().resolve()
            rel = os.path.relpath(path.resolve(), cwd)
            return rel
        except ValueError:
            return str(path)

    def _run_subprocess(self, cmd_list: List[str], stage_name: str) -> bool:
        """Execute a subprocess command with logging and error handling."""
        use_shell = sys.platform == "win32"
        formatted_cmd = " ".join(f'"{arg}"' if " " in str(arg) else str(arg) for arg in cmd_list)
        self.log(f"Starting {stage_name}: {formatted_cmd}")

        start_t = time.time()
        try:
            result = subprocess.run(
                formatted_cmd,
                shell=use_shell,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            elapsed = time.time() - start_t
            self.stage_times[stage_name] = round(elapsed, 2)
            self.log(f"{stage_name} finished in {elapsed:.2f}s")
            return True
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_t
            self.stage_times[stage_name] = round(elapsed, 2)
            self.log(f"{stage_name} FAILED (Exit Code {e.returncode}). Error output: {e.stderr.strip()}", level="ERROR")
            return False

    # -------------------------------------------------------------------------
    # STAGE 1: Image Validation & Preprocessing
    # -------------------------------------------------------------------------
    def validate_and_preprocess_images(self) -> bool:
        """Validate input images and copy/resize to workspace images directory."""
        self.log("--- Stage 1: Image Validation & Preprocessing ---")
        start_t = time.time()

        if len(self.raw_image_paths) < 3:
            self.log(f"Insufficient images provided ({len(self.raw_image_paths)}). At least 3 images required.", level="ERROR")
            return False

        valid_count = 0
        hashes = set()

        for idx, img_path in enumerate(self.raw_image_paths, start=1):
            if not img_path.is_file():
                self.log(f"Image path not found: {img_path}", level="WARNING")
                continue

            # Read image using cv2.imdecode + np.fromfile for Unicode path compatibility on Windows
            try:
                img_data = np.fromfile(str(img_path), dtype=np.uint8)
                img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            except Exception:
                img = None

            if img is None:
                self.log(f"Corrupt or unreadable image file: {img_path.name}", level="WARNING")
                continue

            h, w = img.shape[:2]
            if min(h, w) < 64 or max(h, w) > 8192:
                self.log(f"Image {img_path.name} dimensions ({w}x{h}) outside valid bounds (64-8192px)", level="WARNING")
                continue

            # Check duplicates via simple downsampled mean/hash
            img_small = cv2.resize(img, (32, 32))
            img_hash = hash(img_small.tobytes())
            if img_hash in hashes:
                self.log(f"Duplicate image detected and skipped: {img_path.name}", level="WARNING")
                continue
            hashes.add(img_hash)

            # Resize if max dimension exceeded
            if max(h, w) > self.max_image_dim:
                scale = self.max_image_dim / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                self.log(f"Resized {img_path.name}: {w}x{h} -> {new_w}x{new_h}")

            out_filename = f"image_{idx:03d}.png"
            out_path = self.images_dir / out_filename
            try:
                success, buf = cv2.imencode(".png", img)
                if success:
                    buf.tofile(str(out_path))
                    valid_count += 1
                else:
                    self.log(f"Failed to encode image: {img_path.name}", level="WARNING")
            except Exception as e:
                self.log(f"Failed to save image {out_filename}: {e}", level="WARNING")

        self.stage_times["image_preprocessing"] = round(time.time() - start_t, 2)
        if valid_count < 3:
            self.log(f"Only {valid_count} valid images passed validation. Need at least 3.", level="ERROR")
            return False

        self.log(f"Preprocessing completed: {valid_count}/{len(self.raw_image_paths)} valid images ready.")
        return True

    # -------------------------------------------------------------------------
    # STAGE 2: COLMAP Feature Extraction & Matching
    # -------------------------------------------------------------------------
    def run_feature_extraction_and_matching(self) -> bool:
        """Run SIFT feature extraction and matcher."""
        self.log("--- Stage 2: COLMAP Feature Extraction & Matching ---")

        # Feature Extractor
        cmd_extract = [
            self.colmap_path, "feature_extractor",
            "--database_path", self._to_cmd_path(self.db_path),
            "--image_path", self._to_cmd_path(self.images_dir),
            "--FeatureExtraction.use_gpu", "0"
        ]
        if not self._run_subprocess(cmd_extract, "feature_extraction"):
            return False

        # Matcher (Use Exhaustive Matcher for small image sets <= 20 images)
        cmd_match = [
            self.colmap_path, "exhaustive_matcher",
            "--database_path", self._to_cmd_path(self.db_path),
            "--FeatureMatching.use_gpu", "0"
        ]
        if not self._run_subprocess(cmd_match, "feature_matching"):
            return False

        return True

    # -------------------------------------------------------------------------
    # STAGE 3: COLMAP Sparse Reconstruction (Mapper)
    # -------------------------------------------------------------------------
    def run_sparse_reconstruction(self) -> bool:
        """Run COLMAP mapper and export sparse model to TXT format."""
        self.log("--- Stage 3: COLMAP Sparse Reconstruction (Mapper) ---")

        cmd_mapper = [
            self.colmap_path, "mapper",
            "--database_path", self._to_cmd_path(self.db_path),
            "--image_path", self._to_cmd_path(self.images_dir),
            "--output_path", self._to_cmd_path(self.sparse_dir)
        ]
        if not self._run_subprocess(cmd_mapper, "sparse_mapping"):
            return False

        # Find best model output folder (usually sparse/0)
        model_dirs = [d for d in self.sparse_dir.iterdir() if d.is_dir()]
        if not model_dirs:
            self.log("No sparse reconstruction model folder generated by mapper.", level="ERROR")
            return False

        best_model_dir = sorted(model_dirs, key=lambda d: len(list(d.glob("*"))), reverse=True)[0]
        self.log(f"Selected sparse model folder: {best_model_dir.name}")

        # Ensure output folder exists for model_converter
        self.sparse_model_dir.mkdir(parents=True, exist_ok=True)

        # Export model to TXT format in output_dir/sparse_model
        cmd_export = [
            self.colmap_path, "model_converter",
            "--input_path", self._to_cmd_path(best_model_dir),
            "--output_path", self._to_cmd_path(self.sparse_model_dir),
            "--output_type", "TXT"
        ]
        if not self._run_subprocess(cmd_export, "export_sparse_txt"):
            # Copy raw binaries if export fails
            shutil.copytree(best_model_dir, self.sparse_model_dir, dirs_exist_ok=True)

        return True

    # -------------------------------------------------------------------------
    # STAGE 4: COLMAP Dense Reconstruction (Optional / GPU Dependent)
    # -------------------------------------------------------------------------
    def run_dense_reconstruction(self) -> bool:
        """Attempt COLMAP image undistortion, PatchMatch stereo, and stereo fusion."""
        if not self.run_dense:
            self.log("Dense reconstruction disabled by configuration. Skipping Stage 4.")
            return True

        self.log("--- Stage 4: COLMAP Dense Reconstruction ---")

        # 4.1 Undistortion
        cmd_undistort = [
            self.colmap_path, "image_undistorter",
            "--image_path", self._to_cmd_path(self.images_dir),
            "--input_path", self._to_cmd_path(self.sparse_model_dir),
            "--output_path", self._to_cmd_path(self.dense_dir),
            "--output_type", "COLMAP"
        ]
        if not self._run_subprocess(cmd_undistort, "dense_undistortion"):
            self.log("Dense image undistortion failed. Falling back to sparse output.", level="WARNING")
            return False

        # 4.2 PatchMatch Stereo
        cmd_patch_match = [
            self.colmap_path, "patch_match_stereo",
            "--workspace_path", self._to_cmd_path(self.dense_dir),
            "--workspace_format", "COLMAP"
        ]
        if not self._run_subprocess(cmd_patch_match, "patch_match_stereo"):
            self.log("PatchMatch stereo failed (Requires CUDA GPU). Falling back to sparse output.", level="WARNING")
            return False

        # 4.3 Stereo Fusion
        fused_ply = self.dense_dir / "fused.ply"
        cmd_fusion = [
            self.colmap_path, "stereo_fusion",
            "--workspace_path", self._to_cmd_path(self.dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", self._to_cmd_path(fused_ply)
        ]
        if not self._run_subprocess(cmd_fusion, "stereo_fusion"):
            self.log("Stereo fusion failed. Falling back to sparse output.", level="WARNING")
            return False

        if fused_ply.is_file() and fused_ply.stat().st_size > 0:
            shutil.copy(fused_ply, self.point_cloud_ply)
            self.log(f"Dense fused point cloud saved to {self.point_cloud_ply.name}")
            return True

        return False

    # -------------------------------------------------------------------------
    # STAGE 5: Point Cloud Generation & Processing (Open3D)
    # -------------------------------------------------------------------------
    def process_point_cloud(self) -> Tuple[Optional[Any], Dict[str, Any]]:
        """Parse points3D.txt (or fused PLY), filter outliers, compute normals & stats."""
        import open3d as o3d

        self.log("--- Stage 5: Point Cloud Generation & Processing ---")
        pcd = o3d.geometry.PointCloud()

        # If point_cloud.ply already generated by dense fusion, load it
        if self.point_cloud_ply.is_file() and self.point_cloud_ply.stat().st_size > 0:
            self.log("Loading dense point cloud from fused PLY.")
            pcd = o3d.io.read_point_cloud(self._to_cmd_path(self.point_cloud_ply))
        else:
            # Otherwise parse COLMAP points3D.txt sparse points
            pts3d_txt = self.sparse_model_dir / "points3D.txt"
            if not pts3d_txt.is_file():
                self.log(f"points3D.txt not found at {pts3d_txt}", level="ERROR")
                return None, {}

            points = []
            colors = []
            with open(pts3d_txt, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split()
                    if len(parts) >= 7:
                        xyz = [float(parts[1]), float(parts[2]), float(parts[3])]
                        rgb = [float(parts[4]) / 255.0, float(parts[5]) / 255.0, float(parts[6]) / 255.0]
                        points.append(xyz)
                        colors.append(rgb)

            if not points:
                self.log("No 3D points extracted from points3D.txt.", level="ERROR")
                return None, {}

            pcd.points = o3d.utility.Vector3dVector(np.array(points))
            pcd.colors = o3d.utility.Vector3dVector(np.array(colors))
            self.log(f"Extracted {len(points)} sparse 3D points.")

        # Statistical Outlier Removal
        if len(pcd.points) > 10:
            cl, ind = pcd.remove_statistical_outlier(
                nb_neighbors=min(self.nb_neighbors, len(pcd.points) - 1),
                std_ratio=self.std_ratio
            )
            pcd = pcd.select_by_index(ind)
            self.log(f"Statistical outlier filtering retained {len(pcd.points)} clean 3D points.")

        # Estimate Normals
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        pcd.orient_normals_consistent_tangent_plane(k=15)

        # Save processed point cloud PLY using relative ASCII path
        o3d.io.write_point_cloud(self._to_cmd_path(self.point_cloud_ply), pcd)
        self.log(f"Saved processed point cloud to {self.point_cloud_ply.name}")

        bbox = pcd.get_axis_aligned_bounding_box()
        stats = {
            "point_count": len(pcd.points),
            "has_normals": pcd.has_normals(),
            "has_colors": pcd.has_colors(),
            "bbox_min": bbox.get_min_bound().tolist(),
            "bbox_max": bbox.get_max_bound().tolist(),
            "centroid": pcd.get_center().tolist()
        }
        return pcd, stats

    # -------------------------------------------------------------------------
    # STAGE 6: Mesh Generation (Ball Pivoting / Poisson)
    # -------------------------------------------------------------------------
    def generate_mesh(self, pcd: Any) -> Tuple[bool, Dict[str, Any]]:
        """Generate 3D triangle mesh from point cloud."""
        import open3d as o3d

        if self.mesh_method == "none" or pcd is None or len(pcd.points) < 20:
            self.log("Mesh generation skipped or insufficient points.")
            return False, {"vertex_count": 0, "triangle_count": 0}

        self.log(f"--- Stage 6: Mesh Generation ({self.mesh_method.upper()}) ---")
        start_t = time.time()

        mesh = None
        try:
            if self.mesh_method == "ball_pivoting":
                distances = pcd.compute_nearest_neighbor_distance()
                avg_dist = np.mean(distances)
                radii = [avg_dist * r for r in [0.5, 1.0, 2.0, 4.0]]
                mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
                    pcd, o3d.utility.DoubleVector(radii)
                )

            elif self.mesh_method == "poisson":
                mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                    pcd, depth=8, linear_fit=True
                )
                # Crop Poisson mesh to bounding box of point cloud to remove extraneous surfaces
                bbox = pcd.get_axis_aligned_bounding_box()
                mesh = mesh.crop(bbox)

            if mesh is not None and len(mesh.triangles) > 0:
                mesh.remove_degenerate_triangles()
                mesh.remove_duplicated_triangles()
                mesh.remove_duplicated_vertices()
                mesh.remove_non_manifold_edges()

                o3d.io.write_triangle_mesh(self._to_cmd_path(self.mesh_ply), mesh)
                elapsed = time.time() - start_t
                self.stage_times["mesh_generation"] = round(elapsed, 2)
                self.log(f"Mesh generated: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles in {elapsed:.2f}s")
                return True, {
                    "vertex_count": len(mesh.vertices),
                    "triangle_count": len(mesh.triangles),
                    "mesh_method": self.mesh_method
                }

        except Exception as e:
            self.log(f"Mesh generation failed: {e}", level="WARNING")

        return False, {"vertex_count": 0, "triangle_count": 0}

    # -------------------------------------------------------------------------
    # STAGE 7: Evaluation Report & Metadata
    # -------------------------------------------------------------------------
    def parse_registration_stats(self) -> Dict[str, Any]:
        """Parse images.txt to calculate registered view ratio and count."""
        images_txt = self.sparse_model_dir / "images.txt"
        total_input = len(self.raw_image_paths)
        registered_count = 0
        registered_names = []

        if images_txt.is_file():
            with open(images_txt, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split()
                    if len(parts) >= 10 and parts[0].isdigit():
                        registered_count += 1
                        registered_names.append(parts[9])

        ratio = (registered_count / total_input * 100) if total_input > 0 else 0.0
        return {
            "total_input_images": total_input,
            "registered_image_count": registered_count,
            "registration_ratio_pct": round(ratio, 2),
            "registered_image_names": registered_names
        }

    def run(self) -> Dict[str, Any]:
        """Execute full reconstruction workflow."""
        pipeline_start = time.time()
        self.log(f"============================================================")
        self.log(f"STARTING RECONSTRUCTION JOB: {self.job_id}")
        self.log(f"============================================================")

        # Stage 1: Validation
        if not self.validate_and_preprocess_images():
            report = self._build_report(status="failed", error_message="Image validation failed.")
            self._save_report(report)
            return report

        # Stage 2: Feature Extraction & Matching
        if not self.run_feature_extraction_and_matching():
            report = self._build_report(status="failed", error_message="Feature extraction or matching failed.")
            self._save_report(report)
            return report

        # Stage 3: Sparse Reconstruction
        if not self.run_sparse_reconstruction():
            report = self._build_report(status="failed", error_message="Sparse reconstruction mapping failed.")
            self._save_report(report)
            return report

        # Stage 4: Dense Reconstruction (Optional / Hardware Dependent)
        dense_success = self.run_dense_reconstruction()

        # Stage 5: Point Cloud Processing
        pcd, pcd_stats = self.process_point_cloud()

        # Stage 6: Mesh Generation
        mesh_success, mesh_stats = self.generate_mesh(pcd)

        # Build Final Report
        status = "completed" if pcd is not None else "failed"
        if not dense_success and self.run_dense:
            status = "partial_success"

        elapsed_total = round(time.time() - pipeline_start, 2)
        self.stage_times["total_pipeline"] = elapsed_total

        report = self._build_report(
            status=status,
            pcd_stats=pcd_stats,
            mesh_stats=mesh_stats,
            elapsed_total=elapsed_total
        )
        self._save_report(report)

        self.log(f"============================================================")
        self.log(f"JOB {self.job_id} FINISHED - Status: {status.upper()} in {elapsed_total}s")
        self.log(f"============================================================")

        return report

    def _build_report(
        self,
        status: str,
        error_message: Optional[str] = None,
        pcd_stats: Optional[Dict] = None,
        mesh_stats: Optional[Dict] = None,
        elapsed_total: float = 0.0
    ) -> Dict[str, Any]:
        """Construct structured research evaluation report JSON."""
        reg_stats = self.parse_registration_stats()
        return {
            "job_id": self.job_id,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": error_message,
            "registration_summary": reg_stats,
            "point_cloud_summary": pcd_stats or {},
            "mesh_summary": mesh_stats or {},
            "stage_execution_times_sec": self.stage_times,
            "configuration": {
                "colmap_path": self.colmap_path,
                "run_dense": self.run_dense,
                "mesh_method": self.mesh_method,
                "max_image_dim": self.max_image_dim,
                "nb_neighbors": self.nb_neighbors,
                "std_ratio": self.std_ratio
            },
            "output_files": {
                "point_cloud_ply": str(self.point_cloud_ply) if self.point_cloud_ply.is_file() else None,
                "mesh_ply": str(self.mesh_ply) if self.mesh_ply.is_file() else None,
                "report_json": str(self.report_json)
            },
            "warnings": self.warnings,
            "logs": self.logs
        }

    def _save_report(self, report: Dict[str, Any]) -> None:
        """Write evaluation report to output directory."""
        with open(self.report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
