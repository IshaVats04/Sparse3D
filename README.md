# Sparse3D

[![CI](https://github.com/IshaVats04/Sparse3D/actions/workflows/ci.yml/badge.svg)](https://github.com/IshaVats04/Sparse3D/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Sparse-view 3D object reconstruction and evaluation. Sparse3D reconstructs an object from **3 to 6 ordinary photographs**
and measures how the **number of views** and the **viewpoint arrangement** affect geometric accuracy, completeness,
artifacts, camera estimation and computational cost, comparing a classical pipeline with a learned-prior method.

| Method | Pipeline |
|---|---|
| **Classical** | SIFT features and matching, incremental SfM (COLMAP) for camera poses, dense multi-view stereo when a CUDA GPU is available (otherwise the sparse cloud), outlier filtering, optional Poisson or ball-pivoting mesh (Open3D) |
| **Neural** | **VGGT** (feed-forward transformer, PyTorch): predicts cameras, depth and 3D points for all views in one pass, **without SfM**, so it still works when COLMAP cannot register 3 or 4 views. Falls back to Depth Anything V2 depth fused with COLMAP poses when VGGT is not installed |

Nothing is trained in this project. The neural backends are pretrained models whose weights are downloaded once from the
Hugging Face hub, plus our own geometric post-processing and evaluation. VGGT is the recommended method for the sparse-view
regime; the classical pipeline is kept as the baseline the experiments compare against. SpaRP, UFORecon and SparseRecon
remain literature references and are not re-implemented. Check the VGGT model licence for your use case (the original release is non-commercial).

## Features

- Reconstruct **any photo set**: mixed formats and sizes, EXIF orientation, unknown intrinsics, automatic retry with a more tolerant SfM strategy.
- **Local datasets** of any size (DTU MVS, plain folders) read in place, with the reference cloud and known camera poses used automatically for evaluation.
- Image quality and overlap analysis before reconstruction (blur, brightness, features, pairwise overlap).
- Controlled experiments: view count (3 to 6) and arrangement (uniform, non-uniform, high or low overlap, random), plus a one-call sweep.
- Evaluation: Chamfer distance, F-score, completeness, accuracy, camera pose error, floating-artifact estimate, registration ratio, reprojection error, runtime.
- Web UI (React, Three.js, Chart.js), REST API (FastAPI), experiment history (SQLite), CLI, and a Colab notebook for GPU runs.

### Measured, never estimated

Values that cannot be measured are `null` and the UI shows "n/a". Chamfer distance, F-score, completeness and accuracy
need a reference model, either a dataset's ground truth or one you upload. Camera pose error needs known camera poses
(DTU calibration). Registration ratio, reprojection error, point count, runtime and the floating-artifact estimate are
always measured. See [docs/methodology.md](docs/methodology.md).

## Getting the code

First time (clone):

```bash
git clone https://github.com/IshaVats04/Sparse3D.git
cd Sparse3D
```

Already cloned (get the latest version):

```bash
cd Sparse3D
git pull origin main
```

If `git pull` complains about local changes, keep them with `git stash`, then `git pull origin main`, then `git stash pop`.
To throw away every local change and match GitHub exactly: `git fetch origin && git reset --hard origin/main` (this deletes uncommitted work).
Check which version you have with `git log --oneline -1`; the latest commit is shown at https://github.com/IshaVats04/Sparse3D/commits/main.

## Quick start

Requirements: Python 3.10+, Node.js 18+ (to build the web UI), and [COLMAP](https://colmap.github.io/install.html).

```bash
python -m venv .venv
.venv\Scripts\activate                       # Linux/macOS: source .venv/bin/activate
python run.py
```

`run.py` is the one command to use, every time, on a fresh clone and after every `git pull`. It installs missing Python
packages, builds the web UI when it is missing or older than its sources, picks a free port (so an older server still
running can never hide the new one), starts the app and opens the browser. It prints the address to open.

COLMAP is found through `SPARSE3D_COLMAP`, then `tools/colmap/bin`, then `PATH`.
Windows: unzip a [release](https://github.com/colmap/colmap/releases) into `tools/colmap`. Linux: `sudo apt install colmap`. macOS: `brew install colmap`.
Optional neural method: `pip install -r requirements-neural.txt`.

## Usage

### Web application

```bash
python run.py                      # recommended: checks, builds, starts (http://localhost:8000)
python src/backend/app.py          # starts only the server; API docs at /docs
```

For UI development run `npm run dev` in `frontend/` (Vite proxies `/api` to port 8000).

### Command line

```bash
# any folder of photos
python scripts/run_experiment.py path/to/photos --method both --mesh

# a subset of views from a large local DTU dataset; ground truth and poses are picked up automatically
python scripts/run_experiment.py --dataset-root D:/datasets --scan 1 --cameras 1,9,17,25 --views 4
```

### Python

```python
from pathlib import Path
from src.reconstruction.pipeline import ReconstructionPipeline

pipe = ReconstructionPipeline(
    job_id="demo", input_image_paths=sorted(Path("photos").glob("*.jpg")),
    workspace_dir=Path("work"), output_dir=Path("out"),
    options={"recon_method": "both", "num_views": 4, "view_arrangement": "uniform"})
report = pipe.run()
print(report["results"]["classical"]["metrics"])
```

### Datasets

Point `SPARSE3D_DATASET_DIR` at the folder that holds your datasets (or place them in `data/datasets`). See
[docs/datasets.md](docs/datasets.md) for the recognised layouts, DTU specifics and how ground truth is used.

### GPU and Google Colab

Dense MVS, GPU SIFT and fast neural inference need an NVIDIA GPU. Without one the classical method falls back to the sparse
SfM cloud and says so in the log. In the web app, **Settings > Execution** offers three modes: *This computer*, *Colab GPU
worker*, and *Automatic* (use the worker whenever this machine has no GPU).

To connect a worker:

1. Open [notebooks/02_colab_backend.ipynb](notebooks/02_colab_backend.ipynb) in Colab (the Settings page has a button for it).
2. Runtime > Change runtime type > T4 GPU, then Runtime > Run all.
3. Copy the connection code printed at the bottom (starts with `S3D1.`) into **Settings > Execution > Connect**.

From then on, experiments created in the app are sent to the worker, progress and logs are mirrored live, and the results are
downloaded back so the viewer, history and exports work as usual. Traffic goes through a private tunnel protected by a random
access token contained in the connection code. The notebook pulls this repository's `main` branch from GitHub, so push your
changes before using it. The notebook has not been exercised on a live Colab runtime; its COLMAP install cell verifies CUDA
and reports what to do if it is missing.

The neural weights are downloaded once from huggingface.co. If that host is unreachable (some corporate networks),
`GET /api/health` reports `neural_available: false` with the reason and the UI marks the method unavailable instead of
producing a result. Colab does not have that restriction.

## Updating an existing checkout / troubleshooting

If you pulled this version over an older one and still see the old UI or old behaviour, one of these is the cause:

1. **An old server is still running.** It keeps answering on port 8000 and your browser shows it. Stop every old
   Python/uvicorn process (Windows: `Get-NetTCPConnection -LocalPort 8000 | % { Stop-Process -Id $_.OwningProcess -Force }`),
   then start again. The current server refuses to start on a busy port and says so.
2. **The UI was not built.** `frontend/dist` is git-ignored and must be built on each machine:
   `cd frontend && npm install && npm run build`. Without it, `http://localhost:8000/` shows a short JSON note instead of the UI.
3. **Old dependencies.** After `git pull`: `pip install -r requirements.txt` (new packages such as `httpx` were added).
4. **The browser cached the old page.** Hard-refresh (Ctrl+F5) or open a private window.

How to check you are on the new version: the start-up line prints `Sparse3D 3.0.0 | web UI: built`, and
`http://localhost:8000/api/health` returns `"version": "3.0.0"` (the old backend returned `2.0.0`).

All four are handled automatically by:

```bash
git pull origin main
python run.py
```

## System architecture

```
 Browser (React + Vite + Tailwind, Three.js viewer, Chart.js)
        |  REST / JSON, multipart uploads
        v
 FastAPI backend  (src/backend)
   app.py        endpoints, token check on workers
   jobs.py       job queue, progress, cancellation, persistence (JSON + SQLite history)
   execution.py  mode: local | remote | auto  ->  decides where a job runs
   remote.py     client for a remote worker (connection code, token, upload, mirror, download)
   analysis.py   aggregates finished experiments into view-count / arrangement tables
        |
        +--- target = this computer ----------------+--- target = remote worker (Colab GPU) ---+
        |                                           |   the same backend, started by the notebook |
        v                                           v                                             |
 Reconstruction engine (src/reconstruction) <-------+---------------------------------------------+
   quality_check  view_selection  datasets  pipeline  neural  metrics  colmap_model  config
        |
        +-- COLMAP (subprocess)   +-- PyTorch models (VGGT, Depth Anything)   +-- Open3D (clouds, meshes, metrics)
```

The remote worker is not a separate program: it is this backend, started on a GPU machine with an access token. The
coordinating backend uploads the images (and a thinned reference cloud), mirrors the worker's progress into the local job,
downloads the outputs, and deletes the worker's copy, so a remote job behaves exactly like a local one afterwards.

## Reconstruction pipeline

```
photos (3-6)  or  views chosen from a local dataset
   |
   v
[1] Image analysis        blur, brightness, features, pairwise overlap, duplicates -> warnings
   |                      view selection by arrangement (uniform, non-uniform, high/low overlap, random)
   |                      resize to the quality preset
   |
   +-------------------------------+--------------------------------------------------------+
   |  classical / both / depth-fusion fallback                    |  neural (VGGT) / both       |
   v                                                              v                             |
[2] Features + matching (COLMAP SIFT, exhaustive)        [N] VGGT feed-forward: cameras, depth,  |
   v                                                          confidence for all views at once  |
[3] Camera poses (COLMAP mapper)                              (no SfM needed)                   |
        retry with a tolerant strategy if < 3 views register                |                   |
   v                                                                        v                   |
[4] Reconstruction                                          unproject depth with predicted      |
      GPU:  undistort -> PatchMatch stereo -> fusion        cameras, drop low confidence        |
            (dense cloud, min 2 consistent pixels)                          |                   |
      CPU:  plane-sweep multi-view stereo on the COLMAP poses (dense, no GPU needed)                                                |                   |
      depth-fusion fallback: monocular depth fitted to SfM points           |                   |
   v                                                                        v                   |
   outlier filtering -> normals -> optional Poisson / ball-pivoting mesh  (both methods)         |
   +------------------------------------+---------------------------------------------------------+
                                        v
[5] Evaluation   floating artifacts, registration, reprojection error, runtime (always)
                 + Chamfer, F-score, completeness, accuracy, pose error when a reference / known poses exist
                                        v
        point cloud, mesh, camera poses, metrics CSV, report JSON -> viewer, history, exports
```

Which method to use:

| Situation | Best choice |
|---|---|
| 5-6 well-overlapping views, GPU available | **Classical** on a GPU (dense MVS + mesh): geometrically the most accurate where the views see the surface |
| 3-4 views, wide baselines, or SfM fails | **Neural (VGGT)**: needs no SfM and still produces cameras and a dense cloud |
| Research comparison | **Both**: same input, same evaluation, side by side |
| No GPU | Local CPU dense stereo on the COLMAP poses works; connect a Colab worker (Settings > Execution) for COLMAP PatchMatch and VGGT |

Reconstruction fidelity is bounded by what the photographs show. Surfaces that no view sees (the back of an object with
three front views) are not measured by COLMAP and are only inferred by the neural model, so no setting makes a 3-to-6 photo
reconstruction an exact copy. The evaluation reports exactly how close each result is to a reference when one exists.

Full API: [docs/API_CONTRACT.md](docs/API_CONTRACT.md). Method details: [docs/methodology.md](docs/methodology.md).

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). A `Dockerfile` builds the UI and API (CPU COLMAP).

## Limitations

- With 3 or 4 views, SfM often registers only some views or none; this is part of what the framework measures.
- Reference metrics assume the model and the reconstruction describe the same object, and they are not the official DTU benchmark protocol.
- The VGGT backend works without SfM; the depth-fusion fallback needs a successful SfM and fuses only the region covered by SfM points.
- COLMAP's own dense stage (PatchMatch) needs a CUDA GPU. Without one, a CPU plane-sweep stereo densifies the COLMAP result; it is slower (about 3 minutes for 6 views), and weaker on plain, dark or glossy surfaces with no texture to match.

## Citation

If you use the classical baseline, cite COLMAP: J. L. Schoenberger and J.-M. Frahm, "Structure-from-Motion Revisited", CVPR 2016.

## License

MIT, see [LICENSE](LICENSE).

