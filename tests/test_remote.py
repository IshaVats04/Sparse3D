"""Remote worker: connection codes, token auth, and a full job round trip against a stand-in worker."""

import socket
import threading
import time

import cv2
import pytest
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from src.backend.db import Database
from src.backend.execution import ExecutionManager
from src.backend.jobs import JobManager, NoWorkerError
from src.backend.remote import RemoteClient, RemoteError, make_connection_code, parse_connection_code
from src.reconstruction import config as cfg
from tests.conftest import textured_image

TOKEN = "secret-token"


def build_fake_worker(state):
    """Implements just the parts of the worker API that the coordinator uses."""
    app = FastAPI()

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if request.headers.get("x-sparse3d-token") != TOKEN:
            return JSONResponse({"detail": "Missing or wrong access token"}, status_code=401)
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"app_name": "3D RECON LAB", "environment": {
            "gpu": True, "gpu_name": "Fake T4", "colmap_available": True, "colmap_gpu_usable": True,
            "neural_available": True, "neural_backend": "vggt", "neural_reason": None}}

    @app.post("/api/jobs")
    async def create(images: list[UploadFile] = File(...), recon_method: str = Form("both"),
                     project_name: str = Form("x")):
        state["images"] = [i.filename for i in images]
        state["fields"] = {"recon_method": recon_method, "project_name": project_name}
        state["polls"] = 0
        return {"job_id": "EXP-AAAAAA"}

    @app.get("/api/jobs/{job_id}")
    def get(job_id: str):
        if job_id != "EXP-AAAAAA" or state.get("deleted"):
            raise HTTPException(404, "not found")
        state["polls"] += 1
        done = state["polls"] >= 3
        stages = [{"key": k, "label": k, "status": "complete" if done else "running"} for k in
                  ("image_analysis", "feature_extraction", "camera_pose", "reconstruction", "evaluation")]
        res = {"status": "completed", "message": "remote", "label": "x", "runtime_sec": 12.3, "point_count": 10,
               "mesh": {"vertex_count": 0, "triangle_count": 0}, "registration": None, "cameras": [],
               "metrics": {"runtime_sec": 12.3, "point_count": 10}, "metrics_note": None, "error_histogram": None,
               "files": {"point_cloud": "/api/jobs/EXP-AAAAAA/files/point_cloud", "mesh": None,
                         "camera_poses": "/api/jobs/EXP-AAAAAA/files/camera_poses"}}
        skipped = {**res, "status": "skipped", "files": {"point_cloud": None, "mesh": None, "camera_poses": None}}
        return {"job_id": job_id, "status": "completed" if done else "processing", "stage": "reconstruction",
                "progress": 100 if done else 50, "stages": stages, "logs": [f"worker log {state['polls']}"],
                "warnings": ["worker warning"], "error_message": None, "validation": None,
                "has_ground_truth": False, "configuration": {"selected_images": state.get("images", [])},
                "results": {"classical": res, "neural": skipped}}

    @app.get("/api/jobs/{job_id}/files/{ftype}")
    def files(job_id: str, ftype: str):
        if ftype in ("point_cloud", "camera_poses"):
            return PlainTextResponse(f"data for {ftype}")
        raise HTTPException(404, "missing")

    @app.delete("/api/jobs/{job_id}")
    def delete(job_id: str):
        state["deleted"] = True
        return {"message": "deleted"}

    return app


@pytest.fixture
def worker():
    state = {}
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(build_fake_worker(state), host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", state
    server.should_exit = True
    thread.join(timeout=5)


def test_connection_code_round_trip_and_validation():
    code = make_connection_code("https://abc-def.trycloudflare.com/", "tok")
    assert code.startswith("S3D1.")
    assert parse_connection_code(code) == ("https://abc-def.trycloudflare.com", "tok")
    for bad in ("", "hello", "S3D1.%%%", "S3D1." + "AAAA"):
        with pytest.raises(ValueError):
            parse_connection_code(bad)
    with pytest.raises(ValueError):   # plain http to a public host is refused
        parse_connection_code(make_connection_code("http://example.com", "t"))


def test_client_checks_token_and_identity(worker):
    url, _ = worker
    assert RemoteClient(url, TOKEN).health()["gpu_name"] == "Fake T4"
    with pytest.raises(RemoteError, match="token"):
        RemoteClient(url, "wrong").health()
    with pytest.raises(RemoteError, match="Cannot reach"):
        RemoteClient("http://127.0.0.1:9", TOKEN).health()


def test_execution_manager_modes_and_persistence(worker, tmp_path):
    url, _ = worker
    ex = ExecutionManager(tmp_path / "exec.json")
    assert ex.status()["remote"] is None and ex.status()["mode"] == "auto"
    with pytest.raises(ValueError):
        ex.connect("nonsense")
    with pytest.raises(RemoteError):
        ex.connect(make_connection_code(url, "wrong-token"))
    ex.connect(make_connection_code(url, TOKEN))
    st = ex.status()
    assert st["remote"]["connected"] and st["remote"]["gpu_name"] == "Fake T4"
    assert st["capabilities"]["neural_backend"] in ("vggt", None)

    ex.set_mode("remote")
    assert ex.status()["effective"] == "remote" and ex.status()["capabilities"]["neural_backend"] == "vggt"
    ex.set_mode("local")
    assert ex.status()["effective"] == "local"

    again = ExecutionManager(tmp_path / "exec.json")     # survives a restart
    assert again.mode == "local" and again.remote_status()["connected"]
    again.disconnect()
    assert again.status()["remote"] is None
    with pytest.raises(ValueError):
        again.set_mode("sideways")


def test_remote_job_round_trip(worker, tmp_path):
    url, state = worker
    ex = ExecutionManager(tmp_path / "exec.json")
    ex.connect(make_connection_code(url, TOKEN))
    ex.set_mode("remote")
    manager = JobManager(Database(tmp_path / "db.sqlite"), ex)

    imgs = []
    for i in range(3):
        p = tmp_path / f"p{i}.png"
        cv2.imwrite(str(p), textured_image(i, (480, 360)))
        imgs.append(p)
    meta = manager.create(imgs, {"recon_method": "classical", "num_views": 3, "quality": "fast"}, "remote test",
                          "General Object", None)
    job_id = meta["job_id"]
    assert meta["execution"]["target"] == "remote"

    for _ in range(100):
        job = manager.get(job_id)
        if job["status"] in ("completed", "failed", "partial_success"):
            break
        time.sleep(0.2)
    assert job["status"] == "completed", job["error_message"]
    assert job["execution"]["remote_job_id"] == "EXP-AAAAAA"
    assert state["images"] == ["p0.png", "p1.png", "p2.png"] and state["fields"]["recon_method"] == "classical"
    assert state.get("deleted")                                         # the worker's copy is cleaned up
    out = cfg.OUTPUT_DIR / job_id
    assert (out / "point_cloud.ply").read_text() == "data for point_cloud"   # outputs were downloaded locally
    classical = job["results"]["classical"]
    assert classical["files"]["point_cloud"] == f"/api/jobs/{job_id}/files/point_cloud"
    assert classical["files"]["mesh"] is None
    assert any("worker log" in ln for ln in job["logs"])


def test_remote_mode_without_worker_is_refused(tmp_path):
    ex = ExecutionManager(tmp_path / "exec.json")
    ex.set_mode("remote")
    manager = JobManager(Database(tmp_path / "db.sqlite"), ex)
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), textured_image(1))
    with pytest.raises(NoWorkerError):
        manager.create([p, p, p], {"recon_method": "classical"}, "x", "x", None)


def test_worker_token_middleware(monkeypatch):
    import src.backend.app as app_module
    monkeypatch.setattr(app_module, "API_TOKEN", "abc")
    client = TestClient(app_module.app)
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-Sparse3D-Token": "wrong"}).status_code == 401
    assert client.get("/api/health", headers={"X-Sparse3D-Token": "abc"}).status_code == 200


def test_execution_endpoints(tmp_path, monkeypatch):
    import src.backend.app as app_module
    monkeypatch.setattr(app_module.execution, "path", tmp_path / "exec.json")
    client = TestClient(app_module.app)
    body = client.get("/api/execution").json()
    assert body["mode"] in ("auto", "local", "remote") and body["colab"]["steps"]
    assert client.put("/api/execution", json={"mode": "banana"}).status_code == 400
    bad = client.put("/api/execution", json={"connection_code": "S3D1.nope"})
    assert bad.status_code == 400 and "damaged" in bad.json()["detail"]
    dead_code = make_connection_code("http://127.0.0.1:9", "t")
    assert client.put("/api/execution", json={"connection_code": dead_code}).status_code == 502
    assert client.get("/api/colab/notebook").status_code == 200
    assert client.delete("/api/execution/remote").status_code == 200
