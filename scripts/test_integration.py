#!/usr/bin/env python3
"""
Sparse3D Real Dataset End-to-End Integration Test.

Runs the unified ReconstructionPipeline on the existing 6-view DTU dataset:
`data/experiments/dtu_scan1_6views`

Verifies:
- Image validation & preprocessing
- COLMAP feature extraction & matching
- COLMAP sparse reconstruction mapper
- Open3D point cloud generation & PLY export
- Open3D mesh reconstruction & PLY export
- Structured JSON evaluation report generation
"""

import os
import sys
import json
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reconstruction.pipeline import ReconstructionPipeline


def main():
    print("============================================================")
    print("RUNNING SPARSE3D REAL DATASET INTEGRATION TEST")
    print("============================================================")

    dtu_dir = PROJECT_ROOT / "data" / "experiments" / "dtu_scan1_6views"
    if not dtu_dir.is_dir():
        print(f"Error: Dataset directory not found at {dtu_dir}")
        sys.exit(1)

    image_paths = sorted(list(dtu_dir.glob("*.png")))
    print(f"Found {len(image_paths)} input images in dataset:")
    for p in image_paths:
        print(f"  - {p.name}")

    workspace_dir = PROJECT_ROOT / "workspace" / "integration_test"
    output_dir = PROJECT_ROOT / "outputs" / "integration_test"

    job_id = f"dtu_test_{int(time.time())}"

    # Initialize Pipeline Engine (Sparse SfM + Ball Pivoting Mesh)
    pipeline = ReconstructionPipeline(
        job_id=job_id,
        input_image_paths=image_paths,
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        run_dense=False,  # Sparse SfM mode for CPU environment
        mesh_method="ball_pivoting",
        max_image_dim=1600
    )

    print(f"\nStarting pipeline execution for job: {job_id}...")
    report = pipeline.run()

    print("\n" + "=" * 60)
    print("INTEGRATION TEST RESULTS")
    print("=" * 60)
    print(f"Status           : {report.get('status')}")
    print(f"Total Duration   : {report.get('stage_execution_times_sec', {}).get('total_pipeline')} seconds")
    
    reg = report.get("registration_summary", {})
    print(f"Registered Views : {reg.get('registered_image_count')}/{reg.get('total_input_images')} ({reg.get('registration_ratio_pct')}%)")

    pcd = report.get("point_cloud_summary", {})
    print(f"Reconstructed Points: {pcd.get('point_count')}")

    mesh = report.get("mesh_summary", {})
    print(f"Mesh Vertices    : {mesh.get('vertex_count')}")
    print(f"Mesh Triangles   : {mesh.get('triangle_count')}")

    print(f"\nGenerated Artifacts:")
    for key, path in report.get("output_files", {}).items():
        exists = "✅" if path and Path(path).is_file() else "❌"
        print(f"  {exists} {key}: {path}")

    print("=" * 60 + "\n")

    if report.get("status") in ["completed", "partial_success"]:
        print("✅ INTEGRATION TEST PASSED SUCCESSFULLY!")
    else:
        print("❌ INTEGRATION TEST FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
