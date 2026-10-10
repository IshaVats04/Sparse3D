#!/usr/bin/env python3
"""
COLMAP pipeline script for 3D reconstruction.

This script runs COLMAP's Structure-from-Motion pipeline:
- Feature extraction
- Feature matching
- Sparse reconstruction
- (Optional) Dense reconstruction

Note: COLMAP must be installed separately. See README for installation instructions.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict
import json
import time


class COLMAPRunner:
    """Runs COLMAP SfM pipeline."""

    def __init__(
        self,
        image_dir: str,
        workspace_dir: str,
        output_dir: str,
        use_gpu: bool = True,
        colmap_path: Optional[str] = None
    ):
        self.image_dir = Path(image_dir)
        self.workspace_dir = Path(workspace_dir)
        self.output_dir = Path(output_dir)
        self.use_gpu = use_gpu
        self.colmap_path = colmap_path or "colmap"

        # Create directories
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # COLMAP subdirectories
        self.db_path = self.workspace_dir / "database.db"
        self.sparse_dir = self.workspace_dir / "sparse"
        self.sparse_dir.mkdir(exist_ok=True)

    def check_colmap_installed(self) -> bool:
        """Check if COLMAP is installed and accessible."""
        try:
            print(f"Checking COLMAP at: {self.colmap_path}")
            # On Windows, use shell=True for better compatibility
            use_shell = sys.platform == 'win32'
            result = subprocess.run(
                f'"{self.colmap_path}" --help',
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=5
            )
            print(f"COLMAP check return code: {result.returncode}")
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            print(f"COLMAP check failed: {e}")
            return False

    def print_installation_instructions(self) -> None:
        """Print COLMAP installation instructions."""
        print("\n" + "="*60)
        print("COLMAP NOT FOUND")
        print("="*60)
        print("\nCOLMAP is required for this pipeline.")
        print("\nInstallation instructions:")
        print("\n--- Windows ---")
        print("1. Download from: https://github.com/colmap/colmap/releases")
        print("2. Install the executable")
        print("3. Add COLMAP to your PATH")
        print("\n--- Linux ---")
        print("1. Ubuntu/Debian:")
        print("   sudo apt-get install colmap")
        print("\n2. From source:")
        print("   git clone https://github.com/colmap/colmap.git")
        print("   cd colmap")
        print("   mkdir build && cd build")
        print("   cmake ..")
        print("   make -j8")
        print("   sudo make install")
        print("\n--- macOS ---")
        print("1. Using Homebrew:")
        print("   brew install colmap")
        print("\n2. From source (similar to Linux)")
        print("\n" + "="*60 + "\n")

    def feature_extraction(self) -> bool:
        """Run COLMAP feature extraction."""
        print("\n" + "="*60)
        print("STEP 1: Feature Extraction")
        print("="*60 + "\n")

        cmd_list = [
            self.colmap_path,
            "feature_extractor",
            "--database_path", str(self.db_path),
            "--image_path", str(self.image_dir)
        ]

        # Force CPU for now to avoid GPU issues
        cmd_list.extend(["--FeatureExtraction.use_gpu", "0"])

        # Use shell on Windows for path compatibility
        use_shell = sys.platform == 'win32'
        cmd = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd_list)

        print(f"Running: {cmd}\n")

        try:
            result = subprocess.run(cmd, shell=use_shell, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            print("\n[OK] Feature extraction completed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n[X] Feature extraction failed with error code {e.returncode}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False
        except FileNotFoundError:
            print("\n[X] COLMAP not found in PATH")
            return False

    def feature_matching(self) -> bool:
        """Run COLMAP feature matching."""
        print("\n" + "="*60)
        print("STEP 2: Feature Matching")
        print("="*60 + "\n")

        cmd_list = [
            self.colmap_path,
            "sequential_matcher",
            "--database_path", str(self.db_path)
        ]

        # Force CPU for now to avoid GPU issues
        cmd_list.extend(["--FeatureMatching.use_gpu", "0"])

        use_shell = sys.platform == 'win32'
        cmd = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd_list)

        print(f"Running: {cmd}\n")

        try:
            result = subprocess.run(cmd, shell=use_shell, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            print("\n[OK] Feature matching completed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n[X] Feature matching failed with error code {e.returncode}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False
        except FileNotFoundError:
            print("\n[X] COLMAP not found in PATH")
            return False

    def sparse_reconstruction(self) -> bool:
        """Run COLMAP sparse reconstruction."""
        print("\n" + "="*60)
        print("STEP 3: Sparse Reconstruction")
        print("="*60 + "\n")

        cmd_list = [
            self.colmap_path,
            "mapper",
            "--database_path", str(self.db_path),
            "--image_path", str(self.image_dir),
            "--output_path", str(self.sparse_dir)
        ]

        use_shell = sys.platform == 'win32'
        cmd = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd_list)

        print(f"Running: {cmd}\n")

        try:
            result = subprocess.run(cmd, shell=use_shell, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            print("\n[OK] Sparse reconstruction completed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n[X] Sparse reconstruction failed with error code {e.returncode}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False
        except FileNotFoundError:
            print("\n[X] COLMAP not found in PATH")
            return False

    def export_model(self, model_path: str, output_path: str) -> bool:
        """Export COLMAP model to standard format."""
        print("\n" + "="*60)
        print("STEP 4: Export Model")
        print("="*60 + "\n")

        cmd_list = [
            self.colmap_path,
            "model_converter",
            "--input_path", model_path,
            "--output_path", output_path,
            "--output_type", "TXT"
        ]

        use_shell = sys.platform == 'win32'
        cmd = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd_list)

        print(f"Running: {cmd}\n")

        try:
            result = subprocess.run(cmd, shell=use_shell, check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            print("\n[OK] Model export completed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n[X] Model export failed with error code {e.returncode}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False
        except FileNotFoundError:
            print("\n[X] COLMAP not found in PATH")
            return False

    def run_pipeline(self) -> Dict:
        """Run the complete COLMAP pipeline."""
        start_time = time.time()

        print("\n" + "="*60)
        print("COLMAP STRUCTURE-FROM-MOTION PIPELINE")
        print("="*60)
        print(f"Image directory: {self.image_dir}")
        print(f"Workspace directory: {self.workspace_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Use GPU: {self.use_gpu}")
        print("="*60 + "\n")

        # Check if COLMAP is installed
        if not self.check_colmap_installed():
            self.print_installation_instructions()
            return {
                "status": "error",
                "message": "COLMAP not installed",
                "elapsed_time": 0
            }

        # Step 1: Feature extraction
        if not self.feature_extraction():
            return {
                "status": "error",
                "message": "Feature extraction failed",
                "elapsed_time": time.time() - start_time
            }

        # Step 2: Feature matching
        if not self.feature_matching():
            return {
                "status": "error",
                "message": "Feature matching failed",
                "elapsed_time": time.time() - start_time
            }

        # Step 3: Sparse reconstruction
        if not self.sparse_reconstruction():
            return {
                "status": "error",
                "message": "Sparse reconstruction failed",
                "elapsed_time": time.time() - start_time
            }

        # Step 4: Export model
        # Find the reconstructed model (usually in sparse/0)
        model_dirs = [d for d in self.sparse_dir.iterdir() if d.is_dir()]
        if not model_dirs:
            print("\n[X] No reconstructed model found")
            return {
                "status": "error",
                "message": "No reconstructed model found",
                "elapsed_time": time.time() - start_time
            }

        # Use the first (usually best) model
        model_path = model_dirs[0]
        export_path = self.output_dir / "sparse_reconstruction"

        if not self.export_model(str(model_path), str(export_path)):
            return {
                "status": "error",
                "message": "Model export failed",
                "elapsed_time": time.time() - start_time
            }

        elapsed_time = time.time() - start_time

        print("\n" + "="*60)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"Elapsed time: {elapsed_time:.2f} seconds")
        print(f"Model exported to: {export_path}")
        print("="*60 + "\n")

        return {
            "status": "success",
            "message": "Pipeline completed successfully",
            "elapsed_time": elapsed_time,
            "model_path": str(model_path),
            "export_path": str(export_path),
            "database_path": str(self.db_path)
        }

    def save_report(self, result: Dict, output_path: str) -> None:
        """Save pipeline report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Pipeline report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python run_colmap.py <image_dir> <workspace_dir> <output_dir> [--cpu] [--colmap-path PATH]")
        print("\nArguments:")
        print("  image_dir    : Directory containing images")
        print("  workspace_dir: Directory for COLMAP workspace")
        print("  output_dir   : Directory for output models")
        print("  --cpu        : Use CPU instead of GPU (optional)")
        print("  --colmap-path: Path to COLMAP executable (optional)")
        print("\nExample:")
        print("  python run_colmap.py data/processed workspace outputs/sparse")
        print("  python run_colmap.py data/processed workspace outputs/sparse --cpu")
        print("  python run_colmap.py data/processed workspace outputs/sparse --colmap-path 'C:\\path\\to\\colmap.exe'")
        sys.exit(1)

    image_dir = sys.argv[1]
    workspace_dir = sys.argv[2]
    output_dir = sys.argv[3]
    use_gpu = "--cpu" not in sys.argv

    # Parse optional colmap-path
    colmap_path = None
    if "--colmap-path" in sys.argv:
        idx = sys.argv.index("--colmap-path")
        if idx + 1 < len(sys.argv):
            colmap_path = sys.argv[idx + 1]
            print(f"Using COLMAP from: {colmap_path}")

    runner = COLMAPRunner(
        image_dir=image_dir,
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        use_gpu=use_gpu,
        colmap_path=colmap_path
    )

    result = runner.run_pipeline()

    # Save report
    report_path = Path(output_dir) / "colmap_report.json"
    runner.save_report(result, str(report_path))

    # Exit with error code if failed
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
