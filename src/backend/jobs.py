"""Job manager: persistence, background execution, progress tracking and cancellation of experiments."""

import json
import logging
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.reconstruction import config as cfg
from src.reconstruction.pipeline import STAGES, ReconstructionPipeline

from .db import Database
from .execution import ExecutionManager
from .remote import RemoteError

logger = logging.getLogger("Sparse3D.Jobs")

JOB_ID_RE = re.compile(r"^(EXP|GRP)-[A-Z0-9]{6}$")
TERMINAL = {"completed", "partial_success", "failed", "cancelled"}
FILE_MAP = {
    "point_cloud": "point_cloud.ply", "mesh": "mesh.ply",
    "neural_point_cloud": "neural_point_cloud.ply", "neural_mesh": "neural_mesh.ply",
    "report": "report.json", "metrics_csv": "evaluation_metrics.csv", "camera_poses": "camera_poses.txt",
}
_FILE_TYPE_FOR_RESULT = {
    "classical": {"point_cloud": "point_cloud", "mesh": "mesh", "camera_poses": "camera_poses"},
    "neural": {"point_cloud": "neural_point_cloud", "mesh": "neural_mesh", "camera_poses": "camera_poses"},
}


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def safe_filename(name: str, taken: set) -> str:
    """Reduce an upload name to a safe, unique base name (no directories, no odd characters)."""
    base = Path(name.replace("\\", "/")).name or "image"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(base).stem).strip("._") or "image"
    ext = Path(base).suffix.lower()
    candidate, n = f"{stem}{ext}", 1
    while candidate.lower() in taken:
        n += 1
        candidate = f"{stem}_{n}{ext}"
    taken.add(candidate.lower())
    return candidate


class NoWorkerError(RuntimeError):
    """The mode requires a remote worker but none is connected."""


class JobManager:
    def __init__(self, db: Database, execution: ExecutionManager, max_workers: int = 2):
        self.db = db
        self.execution = execution
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.RLock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self._last_save: Dict[str, float] = {}
        cfg.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._recover()

    # -------------------------------------------------------------- persistence
    def _meta_path(self, job_id: str) -> Path:
        return cfg.WORKSPACE_DIR / job_id / "job_meta.json"

    def _save(self, meta: Dict[str, Any], force: bool = True) -> None:
        """Persist job metadata. Progress updates are throttled; state changes (force) always write.

        Sync clients (OneDrive, Dropbox) can briefly lock files on Windows, which makes an atomic rename fail
        with PermissionError, so the rename is retried and finally replaced by a direct write. A persistence
        failure never aborts a running experiment: the in-memory state stays authoritative.
        """
        now = time.time()
        jid = meta["job_id"]
        if not force and now - self._last_save.get(jid, 0.0) < 1.0:
            return
        self._last_save[jid] = now
        path = self._meta_path(jid)
        text = json.dumps(meta, indent=1, default=str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            for attempt in range(5):
                try:
                    tmp.replace(path)
                    return
                except PermissionError:
                    time.sleep(0.1 * (attempt + 1))
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist %s: %s", jid, exc)

    def _recover(self) -> None:
        """Load stored jobs; anything left running by a previous server process is marked failed."""
        for d in cfg.WORKSPACE_DIR.iterdir():
            mp = d / "job_meta.json"
            if not (d.is_dir() and mp.is_file() and JOB_ID_RE.match(d.name)):
                continue
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("status") in ("queued", "processing"):
                meta.update(status="failed", stage="failed", error_message="Interrupted by a server restart")
                self._save(meta)
            self.jobs[meta["job_id"]] = meta
            self.db.upsert_experiment(meta)

    # -------------------------------------------------------------- creation
    def create(self, image_paths: List[Path], options: Dict[str, Any], project_name: str, object_category: str,
               ground_truth: Optional[Path], group_id: Optional[str] = None,
               gt_projections: Optional[Dict[str, Any]] = None, dataset: Optional[Dict[str, Any]] = None,
               gt_reference: bool = False) -> Dict[str, Any]:
        """Queue an experiment.

        `gt_reference` means the ground-truth file lives in a dataset on disk and is read in place instead of
        being copied (DTU reference clouds are hundreds of megabytes).
        """
        job_id = new_id("EXP")
        raw_dir = cfg.WORKSPACE_DIR / job_id / "raw_images"
        raw_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for p in image_paths:
            dest = raw_dir / p.name
            shutil.copy2(p, dest)
            saved.append(dest)
        gt_dest = None
        if ground_truth and gt_reference:
            gt_dest = Path(ground_truth)
        elif ground_truth:
            gt_dest = cfg.WORKSPACE_DIR / job_id / f"ground_truth{ground_truth.suffix.lower()}"
            shutil.copy2(ground_truth, gt_dest)

        num_views = options.get("num_views") or len(saved)
        meta = {
            "job_id": job_id, "project_name": project_name, "object_category": object_category,
            "status": "queued", "stage": "queued", "progress": 0,
            "stages": [{"key": k, "label": label, "status": "pending"} for k, label in STAGES],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "start_time": None, "end_time": None,
            "elapsed_sec": 0.0, "eta_sec": None, "image_count": len(saved), "group_id": group_id,
            "configuration": {**options, "num_views": min(num_views, len(saved)), "object_category": object_category,
                              "selected_images": []},
            "logs": [], "warnings": [], "error_message": None, "validation": None, "has_ground_truth": False,
            "results": {"classical": None, "neural": None}, "comparison": None, "dataset": dataset,
            "ground_truth_source": gt_dest.name if gt_dest else None,
            "known_camera_poses": len(gt_projections or {}),
        }
        decision = self.execution.decide()
        target = decision["effective"]
        if target == "remote" and not (decision["remote"] and decision["remote"]["connected"]):
            shutil.rmtree(cfg.WORKSPACE_DIR / job_id, ignore_errors=True)
            raise NoWorkerError("The execution mode is 'remote worker' but no worker is connected. "
                                "Connect one in Settings or switch to Automatic.")
        meta["execution"] = {"target": target, "remote_job_id": None}
        with self.lock:
            self.jobs[job_id] = meta
            self.cancel_events[job_id] = threading.Event()
            self._save(meta)
        self.db.upsert_experiment(meta)
        runner = self._run_remote if target == "remote" else self._run
        self.executor.submit(runner, job_id, saved, options, gt_dest, gt_projections)
        return meta

    # -------------------------------------------------------------- execution
    def _update(self, job_id: str, **changes: Any) -> None:
        with self.lock:
            meta = self.jobs[job_id]
            meta.update(changes)
            if meta.get("start_time") and meta["status"] == "processing":
                started = time.mktime(time.strptime(meta["start_time"], "%Y-%m-%d %H:%M:%S"))
                meta["elapsed_sec"] = round(time.time() - started, 1)
                p = meta.get("progress") or 0
                meta["eta_sec"] = round(meta["elapsed_sec"] * (100 - p) / p, 1) if p >= 8 else None
            self._save(meta, force="status" in changes or "stage" in changes)

    def _run(self, job_id: str, images: List[Path], options: Dict[str, Any], gt: Optional[Path],
             gt_projections: Optional[Dict[str, Any]] = None) -> None:
        event = self.cancel_events[job_id]
        if event.is_set():
            return
        self._update(job_id, status="processing", stage="image_analysis",
                     start_time=time.strftime("%Y-%m-%d %H:%M:%S"))

        def on_stage(key: str, status: str) -> None:
            with self.lock:
                for s in self.jobs[job_id]["stages"]:
                    if s["key"] == key:
                        s["status"] = status
            self._update(job_id, stage=key if status == "running" else self.jobs[job_id]["stage"])

        def on_progress(pct: float) -> None:
            self._update(job_id, progress=int(pct))

        def on_log(line: str) -> None:
            with self.lock:
                self.jobs[job_id]["logs"].append(line)
            self._update(job_id)

        try:
            pipe = ReconstructionPipeline(
                job_id=job_id, input_image_paths=images, workspace_dir=cfg.WORKSPACE_DIR, output_dir=cfg.OUTPUT_DIR,
                options=options, ground_truth_path=gt, gt_projections=gt_projections, on_stage=on_stage,
                on_progress=on_progress, on_log=on_log, cancel_event=event)
            report = pipe.run()
        except Exception as exc:  # configuration errors etc.
            report = {"status": "failed", "error_message": str(exc), "results": {}, "warnings": [], "logs": [],
                      "selected_images": [], "validation": None, "has_ground_truth": False}

        self._finalize(job_id, report)

    def _finalize(self, job_id: str, report: Dict[str, Any]) -> None:
        """Store the outcome of a finished experiment (local or remote) and index it."""
        status = report["status"]
        with self.lock:
            meta = self.jobs[job_id]
            for s in meta["stages"]:
                if s["status"] in ("running", "pending"):
                    s["status"] = "skipped" if status in ("completed", "partial_success") else (
                        "failed" if s["status"] == "running" else "pending")
        results = report.get("results") or {}
        self._update(
            job_id, status=status, stage="complete" if status in ("completed", "partial_success") else status,
            progress=100 if status in ("completed", "partial_success") else self.jobs[job_id]["progress"],
            end_time=time.strftime("%Y-%m-%d %H:%M:%S"), eta_sec=None, error_message=report.get("error_message"),
            warnings=report.get("warnings", []), validation=report.get("validation"),
            has_ground_truth=report.get("has_ground_truth", False),
            results={"classical": results.get("classical"), "neural": results.get("neural")},
            comparison=compare(results))
        with self.lock:
            meta = self.jobs[job_id]
            meta["configuration"]["selected_images"] = report.get("selected_images", [])
            if meta["start_time"]:
                started = time.mktime(time.strptime(meta["start_time"], "%Y-%m-%d %H:%M:%S"))
                meta["elapsed_sec"] = round(time.time() - started, 1)
            self._save(meta)
        self.db.upsert_experiment(meta)
        self.db.save_results(job_id, results)

    # -------------------------------------------------------------- remote execution
    def _remote_gt(self, job_id: str, gt: Optional[Path]) -> Optional[Path]:
        """A ground-truth file small enough to upload: dense reference scans are thinned first."""
        if gt is None:
            return None
        try:
            import open3d as o3d

            from src.reconstruction.metrics import load_reference_points
            ref = load_reference_points(gt)
            out = cfg.WORKSPACE_DIR / job_id / "ground_truth_upload.ply"
            o3d.io.write_point_cloud(str(out), ref)
            return out
        except Exception as exc:
            self._log(job_id, f"Ground truth could not be prepared for upload ({exc}); evaluating without it",
                      "WARNING")
            return None

    def _log(self, job_id: str, text: str, level: str = "INFO") -> None:
        with self.lock:
            self.jobs[job_id]["logs"].append(f"[{time.strftime('%H:%M:%S')}] [{level}] {text}")
        self._update(job_id)

    def _run_remote(self, job_id: str, images: List[Path], options: Dict[str, Any], gt: Optional[Path],
                    gt_projections: Optional[Dict[str, Any]] = None) -> None:
        """Run the experiment on the connected worker, mirror its progress, then download the outputs."""
        event = self.cancel_events[job_id]
        if event.is_set():
            return
        client = self.execution.client()
        self._update(job_id, status="processing", stage="image_analysis",
                     start_time=time.strftime("%Y-%m-%d %H:%M:%S"))
        meta = self.jobs[job_id]
        try:
            if client is None:
                raise RemoteError("No remote worker is connected")
            self._log(job_id, f"Uploading {len(images)} image(s) to the worker at {client.host}")
            fields = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in options.items()
                      if v is not None and k != "seed"}
            fields.update(project_name=meta["project_name"], object_category=meta["object_category"])
            if gt_projections:
                fields["gt_projections"] = json.dumps(gt_projections)
            remote_id = client.submit(images, fields, self._remote_gt(job_id, gt))
        except RemoteError as exc:
            if self.execution.mode == "auto":
                self._log(job_id, f"Remote worker unavailable ({exc}); running on this machine instead", "WARNING")
                with self.lock:
                    meta["execution"] = {"target": "local", "remote_job_id": None}
                self._run(job_id, images, options, gt, gt_projections)
            else:
                self._finalize(job_id, {"status": "failed", "error_message": str(exc), "results": {}})
            return

        with self.lock:
            meta["execution"]["remote_job_id"] = remote_id
        self._log(job_id, f"Running on the worker as {remote_id}")
        lost, cancel_sent, remote = 0, False, {}
        while True:
            if event.is_set() and not cancel_sent:
                try:
                    client.cancel(remote_id)
                except RemoteError:
                    pass
                cancel_sent = True
            try:
                remote = client.get(remote_id)
                lost = 0
            except RemoteError as exc:
                lost += 1
                if lost >= 30:
                    self._finalize(job_id, {"status": "failed", "results": {},
                                            "error_message": f"Lost the connection to the worker: {exc} "
                                                             f"(the job may still be running there as {remote_id})"})
                    return
                time.sleep(2)
                continue
            with self.lock:
                meta["stages"] = remote.get("stages", meta["stages"])
                meta["logs"] = [f"{ln}" for ln in remote.get("logs", [])]
            self._update(job_id, stage=remote.get("stage", meta["stage"]), progress=remote.get("progress", 0),
                         warnings=remote.get("warnings", []))
            if remote.get("status") in TERMINAL:
                break
            time.sleep(2)

        self._log(job_id, "Worker finished; downloading the results")
        out_dir = cfg.OUTPUT_DIR / job_id
        got = set()
        wanted = {"point_cloud", "mesh", "neural_point_cloud", "neural_mesh", "camera_poses", "metrics_csv", "report"}
        for ftype in sorted(wanted):
            try:
                if client.download(remote_id, ftype, out_dir / FILE_MAP[ftype]):
                    got.add(ftype)
            except RemoteError as exc:
                self._log(job_id, f"Could not download {ftype}: {exc}", "WARNING")
        results = remote.get("results") or {}
        for method, res in results.items():
            if res:
                for kind, url in list(res["files"].items()):
                    res["files"][kind] = FILE_MAP[_FILE_TYPE_FOR_RESULT[method][kind]] if (
                        url and _FILE_TYPE_FOR_RESULT[method][kind] in got) else None
        self._finalize(job_id, {
            "status": remote.get("status", "failed"), "error_message": remote.get("error_message"),
            "results": results, "warnings": remote.get("warnings", []), "validation": remote.get("validation"),
            "has_ground_truth": remote.get("has_ground_truth", False),
            "selected_images": (remote.get("configuration") or {}).get("selected_images", [])})
        try:
            client.delete(remote_id)   # free the worker's disk; everything needed is now local
        except RemoteError:
            pass

    # -------------------------------------------------------------- queries
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            meta = self.jobs.get(job_id)
            return self._decorate(json.loads(json.dumps(meta, default=str))) if meta else None

    def _decorate(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Add image URLs and turn result file names into download URLs."""
        jid = meta["job_id"]
        raw = cfg.WORKSPACE_DIR / jid / "raw_images"
        meta["images"] = [{"name": p.name, "url": f"/api/jobs/{jid}/images/{p.name}"}
                          for p in sorted(raw.iterdir())] if raw.is_dir() else []
        for method, res in (meta.get("results") or {}).items():
            if not res:
                continue
            for kind, fname in list(res["files"].items()):
                if fname:
                    res["files"][kind] = f"/api/jobs/{jid}/files/{_FILE_TYPE_FOR_RESULT[method][kind]}"
        return meta

    def list_summaries(self) -> List[Dict[str, Any]]:
        out = []
        with self.lock:
            metas = list(self.jobs.values())
        for m in metas:
            cls = (m.get("results") or {}).get("classical") or {}
            neu = (m.get("results") or {}).get("neural") or {}
            best = next((r for r in (neu, cls) if r.get("status") == "completed"), {})
            met = best.get("metrics") or {}
            cfgm = m.get("configuration", {})
            out.append({
                "job_id": m["job_id"], "project_name": m.get("project_name"),
                "object_category": m.get("object_category"),
                "status": m["status"], "stage": m.get("stage"), "created_at": m.get("created_at"),
                "image_count": m.get("image_count"), "num_views": cfgm.get("num_views"),
                "view_arrangement": cfgm.get("view_arrangement"), "recon_method": cfgm.get("recon_method"),
                "group_id": m.get("group_id"), "dataset": m.get("dataset"), "execution": m.get("execution"),
                "f_score": met.get("f_score"), "chamfer": met.get("chamfer_distance"),
                "runtime_sec": met.get("runtime_sec"),
            })
        out.sort(key=lambda x: (x.get("created_at") or "", x["job_id"]), reverse=True)
        return out

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            meta = self.jobs.get(job_id)
            if not meta or meta["status"] in TERMINAL:
                return False
            self.cancel_events[job_id].set()
            if meta["status"] == "queued":
                meta.update(status="cancelled", stage="cancelled", error_message="Cancelled by user")
                self._save(meta)
                self.db.upsert_experiment(meta)
        return True

    def delete(self, job_id: str) -> bool:
        with self.lock:
            meta = self.jobs.get(job_id)
            if not meta:
                return False
            if meta["status"] in ("queued", "processing"):
                self.cancel_events[job_id].set()
            self.jobs.pop(job_id, None)
        shutil.rmtree(cfg.WORKSPACE_DIR / job_id, ignore_errors=True)
        shutil.rmtree(cfg.OUTPUT_DIR / job_id, ignore_errors=True)
        self.db.delete(job_id)
        return True

    def active_count(self) -> int:
        with self.lock:
            return sum(1 for m in self.jobs.values() if m["status"] == "processing")


def compare(results: Dict[str, Optional[Dict[str, Any]]]) -> Optional[Dict[str, float]]:
    """Percent change of the neural metrics relative to the classical metrics (only where both were measured)."""
    c, n = results.get("classical") or {}, results.get("neural") or {}
    if c.get("status") != "completed" or n.get("status") != "completed":
        return None
    cm, nm = c.get("metrics") or {}, n.get("metrics") or {}
    names = {"chamfer_pct": "chamfer_distance", "f_score_pct": "f_score", "completeness_pct": "completeness_pct",
             "accuracy_pct": "accuracy", "pose_error_pct": "camera_pose_error_deg", "runtime_pct": "runtime_sec",
             "point_count_pct": "point_count", "reprojection_pct": "reprojection_error_px"}
    out = {}
    for out_key, key in names.items():
        a, b = cm.get(key), nm.get(key)
        if a not in (None, 0) and b is not None:
            out[out_key] = round(100.0 * (b - a) / a, 1)
    return out or None
