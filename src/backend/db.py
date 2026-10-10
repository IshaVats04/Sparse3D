"""SQLite experiment history (Experiment ID, view configuration, method, metrics, runtime).

The tech-stack document lists PostgreSQL as an optional store for experiment history. SQLite keeps the same
schema with zero setup; swapping the connection for PostgreSQL only needs a different driver.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    job_id TEXT PRIMARY KEY,
    group_id TEXT,
    project_name TEXT,
    object_category TEXT,
    created_at TEXT,
    status TEXT,
    recon_method TEXT,
    num_views INTEGER,
    view_arrangement TEXT,
    image_count INTEGER,
    has_ground_truth INTEGER DEFAULT 0,
    summary TEXT              -- error message when the experiment failed
);
CREATE TABLE IF NOT EXISTS method_results (
    job_id TEXT NOT NULL,
    method TEXT NOT NULL,
    status TEXT,
    message TEXT,
    chamfer_distance REAL,
    f_score REAL,
    completeness_pct REAL,
    accuracy REAL,
    camera_pose_error_deg REAL,
    runtime_sec REAL,
    point_count INTEGER,
    reprojection_error_px REAL,
    registration_ratio_pct REAL,
    floating_artifact_pct REAL,
    registered INTEGER,
    total_input INTEGER,
    PRIMARY KEY (job_id, method)
);
"""

METRIC_KEYS = ["chamfer_distance", "f_score", "completeness_pct", "accuracy", "camera_pose_error_deg",
               "runtime_sec", "point_count", "reprojection_error_px", "registration_ratio_pct",
               "floating_artifact_pct"]


class Database:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def upsert_experiment(self, meta: Dict[str, Any]) -> None:
        cfg = meta.get("configuration", {})
        with self._lock:
            self._conn.execute(
                "INSERT INTO experiments (job_id, group_id, project_name, object_category, created_at, status,"
                " recon_method, num_views, view_arrangement, image_count, has_ground_truth, summary)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(job_id) DO UPDATE SET status=excluded.status, num_views=excluded.num_views,"
                " has_ground_truth=excluded.has_ground_truth, image_count=excluded.image_count,"
                " summary=excluded.summary",
                (meta["job_id"], meta.get("group_id"), meta.get("project_name"), meta.get("object_category"),
                 meta.get("created_at"), meta.get("status"), cfg.get("recon_method"), cfg.get("num_views"),
                 cfg.get("view_arrangement"), meta.get("image_count"), int(bool(meta.get("has_ground_truth"))),
                 meta.get("error_message")))
            self._conn.commit()

    def save_results(self, job_id: str, results: Dict[str, Optional[Dict[str, Any]]]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM method_results WHERE job_id=?", (job_id,))
            for method, res in results.items():
                if not res:
                    continue
                met = res.get("metrics") or {}
                reg = res.get("registration") or {}
                self._conn.execute(
                    "INSERT INTO method_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id, method, res.get("status"), res.get("message"), met.get("chamfer_distance"),
                     met.get("f_score"), met.get("completeness_pct"), met.get("accuracy"),
                     met.get("camera_pose_error_deg"), met.get("runtime_sec"), met.get("point_count"),
                     met.get("reprojection_error_px"), met.get("registration_ratio_pct"),
                     met.get("floating_artifact_pct"), reg.get("registered"), reg.get("total_input")))
            self._conn.commit()

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM experiments WHERE job_id=?", (job_id,))
            self._conn.execute("DELETE FROM method_results WHERE job_id=?", (job_id,))
            self._conn.commit()

    def list_experiments(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM experiments ORDER BY created_at DESC, job_id DESC").fetchall()
            res = self._conn.execute("SELECT * FROM method_results").fetchall()
        by_job: Dict[str, List[sqlite3.Row]] = {}
        for r in res:
            by_job.setdefault(r["job_id"], []).append(r)
        out = []
        for r in rows:
            d = dict(r)
            d["methods"] = {m["method"]: dict(m) for m in by_job.get(r["job_id"], [])}
            out.append(d)
        return out

    def experiments_with_results(self, group_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = [e for e in self.list_experiments() if e["status"] in ("completed", "partial_success", "failed")]
        if group_id:
            rows = [e for e in rows if e["group_id"] == group_id]
        return rows
