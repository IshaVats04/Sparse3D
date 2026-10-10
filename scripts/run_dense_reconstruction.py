#!/usr/bin/env python3
"""
COLMAP Dense 3D Reconstruction Script for Sparse3D.

This script takes an existing sparse COLMAP model and original image directory,
and performs:
1. Image Undistortion (colmap image_undistorter)
2. PatchMatch Stereo Depth Estimation (colmap patch_match_stereo)
3. Stereo Fusion Point Cloud Generation (colmap stereo_fusion)

Outputs are saved in the specified dense workspace directory without
modifying existing sparse reconstruction files.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List
import json
import time

# Ensure UTF-8 output formatting on Windows console to prevent UnicodeEncodeError on paths
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass



class DenseReconstructionRunner:
    """Manages execution of COLMAP dense reconstruction pipeline."""

    def __init__(
        self,
        image_dir: str,
        sparse_dir: str,
        dense_dir: str,
        colmap_path: Optional[str] = None,
        max_image_size: int = -1
    ):
        self.image_dir = Path(image_dir).resolve()
        self.sparse_dir = Path(sparse_dir).resolve()
        self.dense_dir = Path(dense_dir).resolve()
        self.max_image_size = max_image_size

        self.colmap_path = self._resolve_colmap_path(colmap_path)

        # Output subdirectories expected from COLMAP dense pipeline
        self.dense_images_dir = self.dense_dir / "images"
        self.dense_sparse_dir = self.dense_dir / "sparse"
        self.dense_stereo_dir = self.dense_dir / "stereo"
        self.fused_ply_path = self.dense_dir / "fused.ply"

    def _to_cmd_path(self, path: Path) -> str:
        """Convert path to relative path or short path for COLMAP CLI compatibility on Windows."""
        try:
            cwd = Path.cwd().resolve()
            rel = os.path.relpath(path, cwd)
            return rel
        except ValueError:
            return str(path)

    def _resolve_colmap_path(self, colmap_path: Optional[str]) -> str:

        """Find valid COLMAP executable path."""
        candidates = []
        if colmap_path:
            candidates.append(colmap_path)
        candidates.append("colmap")
        candidates.append(r"C:\Users\ishav\Downloads\colmap-x64-windows-cuda\bin\colmap.exe")

        for cand in candidates:
            if shutil.which(cand) or Path(cand).is_file():
                return cand
        return colmap_path or "colmap"

    def check_inputs(self) -> None:
        """Validate input directories and files exist."""
        if not self.image_dir.is_dir():
            raise FileNotFoundError(f"Image directory does not exist: {self.image_dir}")
        if not self.sparse_dir.is_dir():
            raise FileNotFoundError(f"Sparse model directory does not exist: {self.sparse_dir}")

        # Check sparse model files (TXT or BIN format)
        txt_files = list(self.sparse_dir.glob("*.txt"))
        bin_files = list(self.sparse_dir.glob("*.bin"))
        if not txt_files and not bin_files:
            raise FileNotFoundError(
                f"No sparse model files (.txt or .bin) found in {self.sparse_dir}"
            )

        print(f"[OK] Input image directory: {self.image_dir}")
        print(f"[OK] Input sparse model: {self.sparse_dir} ({len(txt_files)} TXT / {len(bin_files)} BIN files)")

    def check_colmap_installed(self) -> bool:
        """Check if COLMAP executable works."""
        print(f"Checking COLMAP executable: {self.colmap_path}")
        use_shell = sys.platform == "win32"
        cmd = f'"{self.colmap_path}" --help'
        try:
            res = subprocess.run(cmd, shell=use_shell, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                print(f"[OK] COLMAP found and working.")
                return True
            else:
                print(f"[X] COLMAP returned error code {res.returncode}")
                return False
        except Exception as e:
            print(f"[X] Failed to execute COLMAP: {e}")
            return False

    def _run_command(self, cmd_list: List[str], step_name: str) -> bool:
        """Run a command with full logging and error reporting."""
        use_shell = sys.platform == "win32"
        formatted_cmd = " ".join(f'"{arg}"' if " " in str(arg) else str(arg) for arg in cmd_list)

        print("\n" + "=" * 60)
        print(f"RUNNING STAGE: {step_name}")
        print("=" * 60)
        print(f"Command: {formatted_cmd}\n")

        try:
            result = subprocess.run(
                formatted_cmd,
                shell=use_shell,
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            print(f"\n[OK] {step_name} completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n[X] {step_name} FAILED with exit code {e.returncode}")
            print("Failed Command:", formatted_cmd)
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False

    def stage1_image_undistortion(self) -> bool:
        """Stage 1: Image Undistortion."""
        self.dense_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.colmap_path,
            "image_undistorter",
            "--image_path", self._to_cmd_path(self.image_dir),
            "--input_path", self._to_cmd_path(self.sparse_dir),
            "--output_path", self._to_cmd_path(self.dense_dir),
            "--output_type", "COLMAP"
        ]
        if self.max_image_size > 0:
            cmd.extend(["--max_image_size", str(self.max_image_size)])

        if not self._run_command(cmd, "Stage 1: Image Undistortion"):
            return False

        # Verification of Stage 1 output
        if not self.dense_images_dir.is_dir() or not any(self.dense_images_dir.iterdir()):
            print(f"[X] Stage 1 Verification Failed: Undistorted images directory missing or empty at {self.dense_images_dir}")
            return False
        if not self.dense_stereo_dir.is_dir():
            print(f"[X] Stage 1 Verification Failed: Stereo workspace directory missing at {self.dense_stereo_dir}")
            return False

        undistorted_count = len(list(self.dense_images_dir.glob("*")))
        print(f"[OK] Stage 1 Verified: {undistorted_count} undistorted images ready in {self.dense_images_dir}")
        return True

    def stage2_patch_match_stereo(self) -> bool:
        """Stage 2: PatchMatch Stereo Depth & Normal Estimation."""
        cmd = [
            self.colmap_path,
            "patch_match_stereo",
            "--workspace_path", self._to_cmd_path(self.dense_dir),
            "--workspace_format", "COLMAP"
        ]
        if self.max_image_size > 0:
            cmd.extend(["--PatchMatchStereo.max_image_size", str(self.max_image_size)])

        if not self._run_command(cmd, "Stage 2: PatchMatch Stereo"):
            return False

        # Verification of Stage 2 output
        depth_maps_dir = self.dense_stereo_dir / "depth_maps"
        normal_maps_dir = self.dense_stereo_dir / "normal_maps"

        if not depth_maps_dir.is_dir() or not list(depth_maps_dir.glob("*.bin")):
            print(f"[X] Stage 2 Verification Failed: Depth maps missing or empty at {depth_maps_dir}")
            return False
        if not normal_maps_dir.is_dir() or not list(normal_maps_dir.glob("*.bin")):
            print(f"[X] Stage 2 Verification Failed: Normal maps missing or empty at {normal_maps_dir}")
            return False

        depth_count = len(list(depth_maps_dir.glob("*.bin")))
        print(f"[OK] Stage 2 Verified: {depth_count} depth maps generated in {depth_maps_dir}")
        return True

    def stage3_stereo_fusion(self) -> bool:
        """Stage 3: Stereo Fusion Point Cloud Generation."""
        cmd = [
            self.colmap_path,
            "stereo_fusion",
            "--workspace_path", self._to_cmd_path(self.dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", self._to_cmd_path(self.fused_ply_path)
        ]

        if not self._run_command(cmd, "Stage 3: Stereo Fusion"):
            return False

        # Verification of Stage 3 output
        if not self.fused_ply_path.is_file() or self.fused_ply_path.stat().st_size == 0:
            print(f"[X] Stage 3 Verification Failed: Output PLY file missing or empty at {self.fused_ply_path}")
            return False

        file_size_mb = self.fused_ply_path.stat().st_size / (1024 * 1024)
        print(f"[OK] Stage 3 Verified: Dense point cloud created ({file_size_mb:.2f} MB) at {self.fused_ply_path}")
        return True

    def count_ply_points(self, ply_path: Path) -> int:
        """Count number of 3D points in a PLY file header/body."""
        try:
            with open(ply_path, 'rb') as f:
                header = ""
                for line in f:
                    line_str = line.decode('ascii', errors='ignore')
                    header += line_str
                    if "end_header" in line_str:
                        break
                for line in header.splitlines():
                    if line.startswith("element vertex"):
                        return int(line.split()[-1])
        except Exception as e:
            print(f"Warning: Could not parse PLY point count: {e}")
        return -1

    def run_pipeline(self) -> Dict:
        """Execute all dense reconstruction stages sequentially."""
        start_time = time.time()

        print("\n" + "=" * 60)
        print("COLMAP DENSE RECONSTRUCTION PIPELINE")
        print("=" * 60)
        print(f"Image Dir    : {self.image_dir}")
        print(f"Sparse Dir   : {self.sparse_dir}")
        print(f"Dense Dir    : {self.dense_dir}")
        print(f"COLMAP Path  : {self.colmap_path}")
        print("=" * 60 + "\n")

        try:
            self.check_inputs()
        except FileNotFoundError as e:
            return {
                "status": "error",
                "stage": "input_check",
                "message": str(e),
                "elapsed_time": time.time() - start_time
            }

        if not self.check_colmap_installed():
            return {
                "status": "error",
                "stage": "colmap_check",
                "message": "COLMAP not found or not executable.",
                "elapsed_time": time.time() - start_time
            }

        # Stage 1: Undistortion
        if not self.stage1_image_undistortion():
            return {
                "status": "error",
                "stage": "stage1_image_undistortion",
                "message": "Image undistortion failed.",
                "elapsed_time": time.time() - start_time
            }

        # Stage 2: PatchMatch Stereo
        if not self.stage2_patch_match_stereo():
            return {
                "status": "error",
                "stage": "stage2_patch_match_stereo",
                "message": "PatchMatch stereo failed.",
                "elapsed_time": time.time() - start_time
            }

        # Stage 3: Stereo Fusion
        if not self.stage3_stereo_fusion():
            return {
                "status": "error",
                "stage": "stage3_stereo_fusion",
                "message": "Stereo fusion failed.",
                "elapsed_time": time.time() - start_time
            }

        elapsed_time = time.time() - start_time
        num_points = self.count_ply_points(self.fused_ply_path)

        print("\n" + "=" * 60)
        print("DENSE RECONSTRUCTION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Output Point Cloud : {self.fused_ply_path}")
        print(f"Number of 3D Points: {num_points if num_points >= 0 else 'Unknown'}")
        print(f"Elapsed Time       : {elapsed_time:.2f} seconds")
        print("=" * 60 + "\n")

        return {
            "status": "success",
            "message": "Dense reconstruction completed successfully.",
            "elapsed_time": elapsed_time,
            "fused_ply_path": str(self.fused_ply_path),
            "num_points": num_points,
            "dense_dir": str(self.dense_dir)
        }


def main():
    """Main CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Run COLMAP Dense Reconstruction Pipeline")
    parser.add_argument(
        "--image_dir",
        default="data/experiments/dtu_scan1_6views",
        help="Path to input original images directory"
    )
    parser.add_argument(
        "--sparse_dir",
        default="outputs/dtu_scan1_6views_lighting0/sparse_reconstruction_retry",
        help="Path to input sparse reconstruction model directory"
    )
    parser.add_argument(
        "--dense_dir",
        default="outputs/dtu_scan1_6views_lighting0/dense",
        help="Path to dense output workspace directory"
    )
    parser.add_argument(
        "--colmap-path",
        default=None,
        help="Path to COLMAP executable"
    )
    parser.add_argument(
        "--max_image_size",
        type=int,
        default=-1,
        help="Maximum image dimension for PatchMatch stereo processing"
    )

    args = parser.parse_args()

    runner = DenseReconstructionRunner(
        image_dir=args.image_dir,
        sparse_dir=args.sparse_dir,
        dense_dir=args.dense_dir,
        colmap_path=args.colmap_path,
        max_image_size=args.max_image_size
    )

    result = runner.run_pipeline()

    # Save execution report
    report_path = Path(args.dense_dir) / "dense_report.json"
    with open(report_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Dense report saved to: {report_path}")

    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
