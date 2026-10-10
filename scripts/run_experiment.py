#!/usr/bin/env python3
"""Run one reconstruction experiment from the command line (no web server).

Any folder of 3-6 photos:
    python scripts/run_experiment.py path/to/photos --method both --mesh

A subset of views from a large local dataset (DTU MVS), with ground truth and known camera poses used
automatically for evaluation:
    python scripts/run_experiment.py --dataset-root D:/datasets/DTU --scan 1 --cameras 1,9,17,25 --views 4
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reconstruction import datasets  # noqa: E402
from src.reconstruction.pipeline import ReconstructionPipeline  # noqa: E402

IMAGE_EXTS = datasets.IMAGE_EXTS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images_dir", type=Path, nargs="?",
                    help="folder with the input images (capture order = file order)")
    ap.add_argument("--dataset-root", type=Path, help="folder containing a DTU MVS dataset (searched recursively)")
    ap.add_argument("--scan", type=int, help="DTU scan number")
    ap.add_argument("--cameras", help="comma-separated DTU camera ids (default: 6 evenly spaced)")
    ap.add_argument("--lighting", type=int, default=0, help="DTU lighting condition (default 0)")
    ap.add_argument("--views", type=int, default=None, help="number of views to use (3-6)")
    ap.add_argument("--arrangement", default="auto",
                    choices=["auto", "uniform", "non_uniform", "high_overlap", "low_overlap", "random"])
    ap.add_argument("--method", default="both", choices=["classical", "neural", "both"])
    ap.add_argument("--quality", default="standard", choices=["fast", "standard", "high"])
    ap.add_argument("--mesh", action="store_true", help="also generate a Poisson mesh")
    ap.add_argument("--ground-truth", type=Path, default=None, help="reference model (.ply/.obj/.stl) for metrics")
    ap.add_argument("--output", type=Path, default=None, help="output folder (default: a temp folder)")
    args = ap.parse_args()

    gt, projections = args.ground_truth, {}
    if args.dataset_root:
        if args.scan is None:
            ap.error("--scan is required with --dataset-root")
        os.environ["SPARSE3D_DATASET_DIR"] = str(args.dataset_root)
        scan = next((s for d in datasets.discover() if d.kind == "dtu" for s in d.scans.values()
                     if s.id == f"scan{args.scan}"), None)
        if scan is None:
            sys.exit(f"scan{args.scan} not found under {args.dataset_root}")
        cams = [int(c) for c in args.cameras.split(",")] if args.cameras else None
        refs = datasets.select_images(scan, cams, args.lighting)
        images = [r.path for r in refs]
        projections = {}
        for r in refs:
            P = scan.projection(r.camera)
            if P is not None:
                projections[r.name] = P.tolist()
        gt = gt or scan.ground_truth
        print(f"{len(images)} images from {scan.name}; ground truth: {gt}; known poses: {len(projections)}")
    elif args.images_dir:
        images = sorted(p for p in args.images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    else:
        ap.error("give an images folder or --dataset-root")

    base = args.output or Path(tempfile.mkdtemp(prefix="sparse3d_"))
    pipe = ReconstructionPipeline(
        job_id="cli", input_image_paths=images, workspace_dir=base / "workspace", output_dir=base / "outputs",
        options={"recon_method": args.method, "num_views": args.views, "view_arrangement": args.arrangement,
                 "quality": args.quality, "generate_mesh": args.mesh},
        ground_truth_path=gt, gt_projections=projections, on_log=print)
    report = pipe.run()
    summary = {k: report[k] for k in ("status", "error_message", "selected_images", "has_ground_truth")}
    summary["results"] = {m: {k: r[k] for k in ("status", "message", "runtime_sec", "point_count", "metrics")}
                          for m, r in report["results"].items()}
    print(json.dumps(summary, indent=2, default=str))
    print(f"Outputs: {base / 'outputs' / 'cli'}")
    return 0 if report["status"] in ("completed", "partial_success") else 1


if __name__ == "__main__":
    sys.exit(main())
