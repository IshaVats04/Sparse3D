#!/usr/bin/env python3
"""
Sparse3D real-dataset end-to-end integration test.

Runs the unified ReconstructionPipeline (classical method, with a mesh) on the bundled 6-view DTU set
`data/experiments/dtu_scan1_6views` and checks that poses, a point cloud and the report were produced.
Needs COLMAP (tools/colmap, SPARSE3D_COLMAP, or PATH). Takes a minute or two on a CPU.
"""

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reconstruction import config as cfg  # noqa: E402
from src.reconstruction.pipeline import ReconstructionPipeline  # noqa: E402


def main() -> None:
    dtu_dir = PROJECT_ROOT / "data" / "experiments" / "dtu_scan1_6views"
    if not dtu_dir.is_dir():
        sys.exit(f"Dataset directory not found: {dtu_dir}")
    if not cfg.find_colmap():
        sys.exit("COLMAP not found. See the README (tools/colmap or SPARSE3D_COLMAP).")

    image_paths = sorted(dtu_dir.glob("*.png"))
    print(f"{len(image_paths)} input images in {dtu_dir.name}")
    job_id = f"dtu_test_{int(time.time())}"
    pipeline = ReconstructionPipeline(
        job_id=job_id, input_image_paths=image_paths,
        workspace_dir=PROJECT_ROOT / "workspace" / "integration_test",
        output_dir=PROJECT_ROOT / "outputs" / "integration_test",
        options={"recon_method": "classical", "generate_mesh": True, "mesh_method": "poisson"},
        on_log=print)
    report = pipeline.run()

    classical = report["results"]["classical"]
    print("\n" + "=" * 60)
    print(f"Status            : {report['status']}")
    print(f"Duration          : {report['stage_execution_times_sec'].get('total_pipeline')} s")
    reg = classical.get("registration") or {}
    print(f"Registered views  : {reg.get('registered')}/{reg.get('total_input')}")
    print(f"Points            : {classical['point_count']}")
    print(f"Mesh triangles    : {classical['mesh']['triangle_count']}")
    print("=" * 60)

    out = PROJECT_ROOT / "outputs" / "integration_test" / job_id
    checks = {
        "report completed": report["status"] == "completed",
        "all views registered": reg.get("registered") == reg.get("total_input"),
        "point cloud written": (out / "point_cloud.ply").is_file(),
        "camera poses written": (out / "camera_poses.txt").is_file(),
        "report written": (out / "report.json").is_file(),
    }
    for name, ok in checks.items():
        print(("PASS  " if ok else "FAIL  ") + name)
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
