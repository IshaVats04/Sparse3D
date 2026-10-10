#!/usr/bin/env python3
"""3D RECON LAB FastAPI application. See docs/API_CONTRACT.md for the full API.

Run:  python src/backend/app.py   (serves the API and, when built, the React UI from frontend/dist)
"""

import hmac
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.analysis import build_analysis  # noqa: E402
from src.backend.db import Database  # noqa: E402
from src.backend.execution import NOTEBOOK_PATH, ExecutionManager  # noqa: E402
from src.backend.jobs import FILE_MAP, JOB_ID_RE, JobManager, NoWorkerError, new_id, safe_filename  # noqa: E402
from src.backend.remote import TOKEN_HEADER, RemoteError  # noqa: E402
from src.reconstruction import config as cfg  # noqa: E402
from src.reconstruction import datasets  # noqa: E402
from src.reconstruction.quality_check import HEIF_SUPPORTED, analyze_images, public_report  # noqa: E402
from src.reconstruction.view_selection import ARRANGEMENTS  # noqa: E402

VERSION = "3.0.0"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
if HEIF_SUPPORTED:  # iPhone photos, when pillow-heif is installed
    IMAGE_EXTS |= {".heic", ".heif"}
GT_EXTS = {".ply", ".obj", ".stl"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_GT_BYTES = 200 * 1024 * 1024
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="3D RECON LAB API", version=VERSION,
              description="Sparse-view 3D reconstruction and evaluation platform")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

API_TOKEN = os.environ.get("SPARSE3D_API_TOKEN", "")   # set on remote workers (e.g. Colab); empty = no auth


@app.middleware("http")
async def require_token(request: Request, call_next):
    """When SPARSE3D_API_TOKEN is set, every /api request must carry it in the X-Sparse3D-Token header."""
    if API_TOKEN and request.url.path.startswith("/api/") and request.method != "OPTIONS":
        if not hmac.compare_digest(request.headers.get(TOKEN_HEADER, ""), API_TOKEN):
            return JSONResponse({"detail": "Missing or wrong access token"}, status_code=401)
    return await call_next(request)


db = Database(cfg.DB_PATH)
execution = ExecutionManager()
manager = JobManager(db, execution)


# ------------------------------------------------------------------ helpers
def _check_job_id(job_id: str) -> str:
    if not JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")
    return job_id


def _examples() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if cfg.EXAMPLES_DIR.is_dir():
        for d in sorted(cfg.EXAMPLES_DIR.iterdir()):
            imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTS) if d.is_dir() else []
            if imgs:
                name = d.name.replace("_", " ")
                out[d.name] = {"id": d.name, "name": name, "dir": d, "paths": imgs}
    return out


async def _save_uploads(images: List[UploadFile], dest: Path) -> List[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    taken: set = set()
    saved: List[Path] = []
    for up in images:
        ext = Path(up.filename or "").suffix.lower()
        if ext not in IMAGE_EXTS:
            raise HTTPException(status_code=400, detail=f"Unsupported image format '{ext}' for "
                                                        f"'{up.filename}'. Allowed: {sorted(IMAGE_EXTS)}")
        data = await up.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail=f"'{up.filename}' is larger than "
                                                        f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
        target = dest / safe_filename(up.filename or "image", taken)
        target.write_bytes(data)
        saved.append(target)
    return saved


class Source:
    """Where an experiment's images (and optional ground truth) come from."""

    def __init__(self, paths: List[Path], gt_path: Optional[Path] = None, projections: Optional[Dict[str, Any]] = None,
                 dataset: Optional[Dict[str, Any]] = None):
        self.paths, self.gt_path, self.projections, self.dataset = paths, gt_path, projections or {}, dataset


async def _resolve_source(images: Optional[List[UploadFile]], example_id: Optional[str], dest: Path,
                          dataset_id: Optional[str] = None, scan_id: Optional[str] = None,
                          cameras: Optional[str] = None, lighting: Optional[int] = None,
                          use_dataset_gt: bool = True) -> Source:
    if dataset_id:
        ds = datasets.get_dataset(dataset_id)
        scan = ds.scans.get(scan_id or "") if ds else None
        if not ds or not scan:
            raise HTTPException(status_code=404, detail=f"Unknown dataset/scan '{dataset_id}/{scan_id}'.")
        try:
            cams = [int(c) for c in cameras.split(",") if c.strip()] if cameras else None
            refs = datasets.select_images(scan, cams, lighting)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        dest.mkdir(parents=True, exist_ok=True)
        paths, proj = [], {}
        for r in refs:
            shutil.copy2(r.path, dest / r.name)
            paths.append(dest / r.name)
            P = scan.projection(r.camera) if r.camera is not None else None
            if P is not None:
                proj[r.name] = P.tolist()
        meta = {"id": ds.id, "kind": ds.kind, "name": ds.name, "scan": scan.id,
                "cameras": [r.camera for r in refs if r.camera is not None], "lighting": refs[0].lighting}
        return Source(paths, scan.ground_truth if use_dataset_gt else None, proj, meta)
    if example_id:
        ex = _examples().get(example_id)
        if not ex:
            raise HTTPException(status_code=404, detail=f"Unknown example set '{example_id}'.")
        dest.mkdir(parents=True, exist_ok=True)
        paths = []
        for p in ex["paths"]:
            shutil.copy2(p, dest / p.name)
            paths.append(dest / p.name)
        return Source(paths)
    if not images:
        raise HTTPException(status_code=400, detail="Provide 'images' files, an 'example_id' or a 'dataset_id'.")
    return Source(await _save_uploads(images, dest))


async def _save_ground_truth(gt: Optional[UploadFile], dest_dir: Path) -> Optional[Path]:
    if gt is None or not gt.filename:
        return None
    ext = Path(gt.filename).suffix.lower()
    if ext not in GT_EXTS:
        raise HTTPException(status_code=400, detail=f"Ground truth must be one of {sorted(GT_EXTS)}.")
    data = await gt.read()
    if len(data) > MAX_GT_BYTES:
        raise HTTPException(status_code=400, detail="Ground-truth file is too large (limit 200 MB).")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"ground_truth{ext}"
    path.write_bytes(data)
    return path


def _options(recon_method: str, num_views: Optional[int], view_arrangement: str, quality: str,
             estimate_poses: bool, run_evaluation: bool, generate_mesh: bool, save_intermediate: bool,
             mesh_method: str, n_images: int) -> Dict[str, Any]:
    if recon_method not in ("classical", "neural", "both"):
        raise HTTPException(status_code=400, detail="recon_method must be classical, neural or both.")
    if view_arrangement not in ARRANGEMENTS:
        raise HTTPException(status_code=400, detail=f"view_arrangement must be one of {list(ARRANGEMENTS)}.")
    if quality not in cfg.QUALITY_PRESETS:
        raise HTTPException(status_code=400, detail=f"quality must be one of {list(cfg.QUALITY_PRESETS)}.")
    if mesh_method not in ("ball_pivoting", "poisson", "none"):
        raise HTTPException(status_code=400, detail="mesh_method must be ball_pivoting, poisson or none.")
    if num_views is not None and not 3 <= num_views <= 6:
        raise HTTPException(status_code=400, detail="num_views must be between 3 and 6.")
    if n_images < 3:
        raise HTTPException(status_code=400, detail="Minimum 3 images required for 3D reconstruction.")
    if num_views is None and n_images > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 images allowed unless num_views selects a subset.")
    if num_views is not None and num_views > n_images:
        raise HTTPException(status_code=400, detail=f"num_views ({num_views}) is larger than the number of "
                                                    f"images supplied ({n_images}).")
    return {"recon_method": recon_method, "num_views": num_views or n_images, "view_arrangement": view_arrangement,
            "quality": quality, "estimate_poses": estimate_poses, "run_evaluation": run_evaluation,
            "generate_mesh": generate_mesh, "save_intermediate": save_intermediate, "mesh_method": mesh_method}


# ------------------------------------------------------------------ health & examples
@app.get("/api/health", summary="Health and capabilities")
def health() -> Dict[str, Any]:
    torch_info = cfg.torch_status()
    colmap = cfg.find_colmap()
    return {
        "status": "healthy", "app_name": "3D RECON LAB", "version": VERSION,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "python_version": sys.version.split()[0], "platform": sys.platform,
            "colmap_available": colmap is not None, "colmap_path": colmap,
            "colmap_cuda": cfg.colmap_has_cuda(), "colmap_gpu_usable": cfg.colmap_can_use_gpu(),
            "data_dir": str(cfg.DATA_ROOT),
            "gpu": bool(cfg.nvidia_gpu_present() or torch_info.get("cuda_available")), "gpu_name": cfg.gpu_name(),
            **torch_info, "active_jobs_count": manager.active_count(),
        },
    }


# ------------------------------------------------------------------ execution target (local / remote worker)
class ExecutionUpdate(BaseModel):
    mode: Optional[str] = None
    connection_code: Optional[str] = None


@app.get("/api/execution", summary="Where experiments run")
def get_execution() -> Dict[str, Any]:
    return execution.status()


@app.put("/api/execution", summary="Set the execution mode and/or connect a worker")
def put_execution(body: ExecutionUpdate) -> Dict[str, Any]:
    try:
        if body.mode is not None:
            execution.set_mode(body.mode)
        if body.connection_code:
            execution.connect(body.connection_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return execution.status()


@app.delete("/api/execution/remote", summary="Disconnect the remote worker")
def delete_execution_remote() -> Dict[str, Any]:
    execution.disconnect()
    return execution.status()


@app.get("/api/colab/notebook", summary="The Colab worker notebook")
def colab_notebook():
    if not NOTEBOOK_PATH.is_file():
        raise HTTPException(status_code=404, detail="Notebook not found in this installation.")
    return FileResponse(NOTEBOOK_PATH, filename="sparse3d_colab_worker.ipynb", media_type="application/x-ipynb+json")


@app.get("/api/examples", summary="Bundled sample image sets")
def list_examples() -> List[Dict[str, Any]]:
    return [{"id": e["id"], "name": e["name"],
             "images": [{"name": p.name, "url": f"/api/examples/{e['id']}/{p.name}"} for p in e["paths"]]}
            for e in _examples().values()]


@app.get("/api/examples/{example_id}/{name}", summary="Sample image file")
def example_image(example_id: str, name: str):
    ex = _examples().get(example_id)
    match = next((p for p in ex["paths"] if p.name == name), None) if ex else None
    if not match:
        raise HTTPException(status_code=404, detail="Example image not found.")
    return FileResponse(match)


# ------------------------------------------------------------------ validation
@app.post("/api/validate", summary="Image quality and overlap check")
async def validate(images: Optional[List[UploadFile]] = File(None), example_id: Optional[str] = Form(None),
                   dataset_id: Optional[str] = Form(None), scan_id: Optional[str] = Form(None),
                   cameras: Optional[str] = Form(None), lighting: Optional[int] = Form(None)):
    with tempfile.TemporaryDirectory(prefix="s3d_validate_") as tmp:
        src = await _resolve_source(images, example_id, Path(tmp), dataset_id, scan_id, cameras, lighting)
        return public_report(analyze_images(src.paths))


# ------------------------------------------------------------------ datasets (large local collections)
def _dataset_json(ds: "datasets.Dataset") -> Dict[str, Any]:
    return {"id": ds.id, "kind": ds.kind, "name": ds.name, "scans": [
        {"id": s.id, "name": s.name, "image_count": len(s.images), "cameras": s.cameras, "lightings": s.lightings,
         "has_ground_truth": s.ground_truth is not None, "has_camera_poses": s.calibration_dir is not None,
         "default_cameras": datasets.default_cameras(s) if s.cameras else []}
        for s in ds.scans.values()]}


@app.get("/api/datasets", summary="Datasets found on this machine")
def list_datasets() -> List[Dict[str, Any]]:
    return [_dataset_json(d) for d in datasets.discover()]


@app.get("/api/datasets/{dataset_id}/{scan_id}/images", summary="Images of a dataset scan")
def dataset_images(dataset_id: str, scan_id: str, lighting: Optional[int] = Query(None),
                   limit: int = Query(200, ge=1, le=2000)) -> List[Dict[str, Any]]:
    ds = datasets.get_dataset(dataset_id)
    scan = ds.scans.get(scan_id) if ds else None
    if not scan:
        raise HTTPException(status_code=404, detail="Unknown dataset or scan.")
    imgs = [i for i in scan.images if lighting is None or i.lighting in (None, lighting)]
    return [{"name": i.name, "camera": i.camera, "lighting": i.lighting,
             "url": f"/api/datasets/{dataset_id}/{scan_id}/image/{i.name}?thumb=1"} for i in imgs[:limit]]


@app.get("/api/datasets/{dataset_id}/{scan_id}/image/{name}", summary="Dataset image (optionally a thumbnail)")
def dataset_image(dataset_id: str, scan_id: str, name: str, thumb: bool = Query(False)):
    ds = datasets.get_dataset(dataset_id)
    scan = ds.scans.get(scan_id) if ds else None
    ref = next((i for i in scan.images if i.name == name), None) if scan else None
    if not ref:
        raise HTTPException(status_code=404, detail="Image not found.")
    if not thumb:
        return FileResponse(ref.path)
    cache = cfg.DATA_ROOT / "workspace" / "thumbs"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{dataset_id}_{scan_id}_{Path(name).stem}.jpg"
    if not out.is_file():
        import cv2

        from src.reconstruction.quality_check import read_image
        img = read_image(ref.path)
        if img is None:
            raise HTTPException(status_code=422, detail="Image could not be decoded.")
        h, w = img.shape[:2]
        s = 320 / max(h, w)
        ok, buf = cv2.imencode(".jpg", cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA))
        out.write_bytes(buf.tobytes())
    return FileResponse(out, media_type="image/jpeg")


# ------------------------------------------------------------------ jobs
@app.post("/api/jobs", status_code=status.HTTP_202_ACCEPTED, summary="Create an experiment")
async def create_job(
    images: Optional[List[UploadFile]] = File(None),
    example_id: Optional[str] = Form(None),
    ground_truth: Optional[UploadFile] = File(None),
    project_name: str = Form("Experiment"),
    object_category: str = Form("General Object"),
    recon_method: str = Form("both"),
    num_views: Optional[int] = Form(None),
    view_arrangement: str = Form("auto"),
    quality: str = Form("standard"),
    estimate_poses: bool = Form(True),
    run_evaluation: bool = Form(True),
    generate_mesh: bool = Form(False),
    save_intermediate: bool = Form(False),
    mesh_method: str = Form("poisson"),
    group_id: Optional[str] = Form(None),
    dataset_id: Optional[str] = Form(None),
    scan_id: Optional[str] = Form(None),
    cameras: Optional[str] = Form(None),
    lighting: Optional[int] = Form(None),
    use_dataset_ground_truth: bool = Form(True),
    gt_projections: Optional[str] = Form(None),
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="s3d_upload_") as tmp:
        tmp_dir = Path(tmp)
        src = await _resolve_source(images, example_id, tmp_dir / "images", dataset_id, scan_id, cameras, lighting,
                                    use_dataset_ground_truth)
        opts = _options(recon_method, num_views, view_arrangement, quality, estimate_poses, run_evaluation,
                        generate_mesh, save_intermediate, mesh_method, len(src.paths))
        uploaded_gt = await _save_ground_truth(ground_truth, tmp_dir / "gt")
        gt_path, gt_ref = (uploaded_gt, False) if uploaded_gt else (src.gt_path, True)
        projections = src.projections
        if gt_projections:   # sent by a coordinating machine that owns the dataset
            try:
                projections = {k: v for k, v in json.loads(gt_projections).items()}
            except (ValueError, AttributeError):
                raise HTTPException(status_code=400, detail="gt_projections must be a JSON object.")
        try:
            meta = manager.create(src.paths, opts, project_name.strip() or "Experiment", object_category, gt_path,
                                  group_id, projections, src.dataset, gt_ref)
        except NoWorkerError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return {"job_id": meta["job_id"], "project_name": project_name, "status": "queued",
            "message": f"Experiment '{project_name}' ({meta['job_id']}) queued with {len(src.paths)} images."}


@app.post("/api/experiments/sweep", status_code=status.HTTP_202_ACCEPTED, summary="View-count / arrangement sweep")
async def create_sweep(
    images: Optional[List[UploadFile]] = File(None),
    example_id: Optional[str] = Form(None),
    ground_truth: Optional[UploadFile] = File(None),
    project_name: str = Form("Sweep"),
    object_category: str = Form("General Object"),
    recon_method: str = Form("both"),
    view_counts: str = Form("3,4,5,6"),
    arrangements: Optional[str] = Form(None),
    view_arrangement: str = Form("uniform"),
    quality: str = Form("standard"),
    estimate_poses: bool = Form(True),
    run_evaluation: bool = Form(True),
    generate_mesh: bool = Form(False),
    save_intermediate: bool = Form(False),
    mesh_method: str = Form("poisson"),
    dataset_id: Optional[str] = Form(None),
    scan_id: Optional[str] = Form(None),
    cameras: Optional[str] = Form(None),
    lighting: Optional[int] = Form(None),
    use_dataset_ground_truth: bool = Form(True),
) -> Dict[str, Any]:
    try:
        counts = sorted({int(x) for x in view_counts.split(",") if x.strip()})
    except ValueError:
        raise HTTPException(status_code=400, detail="view_counts must be a comma-separated list of integers.")
    arrs = [a.strip() for a in (arrangements or view_arrangement).split(",") if a.strip()]
    if not counts:
        raise HTTPException(status_code=400, detail="view_counts is empty.")
    with tempfile.TemporaryDirectory(prefix="s3d_sweep_") as tmp:
        tmp_dir = Path(tmp)
        src = await _resolve_source(images, example_id, tmp_dir / "images", dataset_id, scan_id, cameras, lighting,
                                    use_dataset_ground_truth)
        paths = src.paths
        if len(paths) < max(counts):
            raise HTTPException(status_code=400, detail=f"A sweep up to {max(counts)} views needs at least "
                                                        f"{max(counts)} images; got {len(paths)}.")
        uploaded_gt = await _save_ground_truth(ground_truth, tmp_dir / "gt")
        gt_path, gt_ref = (uploaded_gt, False) if uploaded_gt else (src.gt_path, True)
        group_id = new_id("GRP")
        job_ids = []
        for arr in arrs:
            for k in counts:
                opts = _options(recon_method, k, arr, quality, estimate_poses, run_evaluation, generate_mesh,
                                save_intermediate, mesh_method, len(paths))
                try:
                    meta = manager.create(paths, opts, f"{project_name} ({k} views, {arr})", object_category,
                                          gt_path, group_id, src.projections, src.dataset, gt_ref)
                except NoWorkerError as exc:
                    raise HTTPException(status_code=409, detail=str(exc))
                job_ids.append(meta["job_id"])
    return {"group_id": group_id, "job_ids": job_ids}


@app.get("/api/jobs", summary="List experiments")
def list_jobs() -> List[Dict[str, Any]]:
    return manager.list_summaries()


@app.get("/api/jobs/{job_id}", summary="Experiment details")
def get_job(job_id: str) -> Dict[str, Any]:
    meta = manager.get(_check_job_id(job_id))
    if not meta:
        raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")
    return meta


@app.get("/api/jobs/{job_id}/report", summary="Full experiment report")
def get_report(job_id: str):
    _check_job_id(job_id)
    report = cfg.OUTPUT_DIR / job_id / "report.json"
    if not report.is_file():
        raise HTTPException(status_code=404, detail=f"Report for '{job_id}' is not available yet.")
    return JSONResponse(json.loads(report.read_text(encoding="utf-8")))


@app.get("/api/jobs/{job_id}/images/{name}", summary="Input image")
def get_job_image(job_id: str, name: str):
    _check_job_id(job_id)
    raw = (cfg.WORKSPACE_DIR / job_id / "raw_images").resolve()
    target = (raw / Path(name).name).resolve()
    if target.parent != raw or not target.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(target)


@app.get("/api/jobs/{job_id}/files/{file_type}", summary="Download an output artifact")
def download(job_id: str, file_type: str):
    _check_job_id(job_id)
    if file_type not in FILE_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {sorted(FILE_MAP)}")
    out = (cfg.OUTPUT_DIR / job_id).resolve()
    target = (out / FILE_MAP[file_type]).resolve()
    if target.parent != out or not target.is_file():
        raise HTTPException(status_code=404, detail=f"'{FILE_MAP[file_type]}' was not generated for {job_id}.")
    media = {"report": "application/json", "metrics_csv": "text/csv", "camera_poses": "text/plain"}.get(
        file_type, "application/octet-stream")
    return FileResponse(target, filename=f"sparse3d_{job_id}_{FILE_MAP[file_type]}", media_type=media)


@app.delete("/api/jobs/{job_id}", summary="Delete an experiment")
def delete_job(job_id: str) -> Dict[str, str]:
    if not manager.delete(_check_job_id(job_id)):
        raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")
    return {"message": f"Experiment {job_id} deleted."}


@app.post("/api/jobs/{job_id}/cancel", summary="Cancel an experiment")
def cancel_job(job_id: str) -> Dict[str, str]:
    _check_job_id(job_id)
    if not manager.get(job_id):
        raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")
    if not manager.cancel(job_id):
        raise HTTPException(status_code=409, detail="Experiment already finished.")
    return {"message": f"Experiment {job_id} cancelled."}


# ------------------------------------------------------------------ analysis
@app.get("/api/analysis", summary="Aggregated view-count / arrangement analysis")
def analysis(group_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    if group_id and not JOB_ID_RE.match(group_id):
        raise HTTPException(status_code=404, detail="Unknown group.")
    return build_analysis(db.experiments_with_results(group_id))


# ------------------------------------------------------------------ frontend (built React app)
if FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {"app": "3D RECON LAB API", "version": VERSION, "docs": "/docs",
                "note": "The web UI is not built. Run 'npm install && npm run build' in frontend/."}


if __name__ == "__main__":
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
