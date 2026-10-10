"""API tests. conftest.py points the backend at a temporary workspace."""

import time

import cv2
import pytest
from fastapi.testclient import TestClient

from src.backend.app import app
from tests.conftest import textured_image

client = TestClient(app)


def png_files(n, prefix="img"):
    out = []
    for i in range(n):
        ok, buf = cv2.imencode(".png", textured_image(i, (480, 360)))
        assert ok
        out.append(("images", (f"{prefix}_{i}.png", buf.tobytes(), "image/png")))
    return out


def test_health_reports_capabilities():
    r = client.get("/api/health")
    assert r.status_code == 200
    env = r.json()["environment"]
    for key in ("colmap_available", "colmap_cuda", "torch_available", "neural_available", "device"):
        assert key in env


def test_examples_listed_and_served():
    ex = client.get("/api/examples").json()
    assert ex and ex[0]["images"]
    assert client.get(ex[0]["images"][0]["url"]).status_code == 200
    assert client.get("/api/examples/nope/x.png").status_code == 404


def test_validate_endpoint():
    r = client.post("/api/validate", files=png_files(3))
    assert r.status_code == 200
    body = r.json()
    assert body["image_count"] == 3 and len(body["pairs"]) == 3 and "_duplicates" not in body


@pytest.mark.parametrize("n,expected", [(2, "Minimum 3"), (7, "Maximum 6")])
def test_job_requires_between_3_and_6_images(n, expected):
    r = client.post("/api/jobs", files=png_files(n))
    assert r.status_code == 400 and expected in r.json()["detail"]


def test_job_rejects_bad_parameters_and_formats():
    assert client.post("/api/jobs", files=png_files(3), data={"recon_method": "magic"}).status_code == 400
    assert client.post("/api/jobs", files=png_files(3), data={"view_arrangement": "spiral"}).status_code == 400
    assert client.post("/api/jobs", files=png_files(3), data={"num_views": "9"}).status_code == 400
    bad = [("images", ("a.exe", b"x", "application/octet-stream"))] * 3
    assert client.post("/api/jobs", files=bad).status_code == 400


def test_job_lifecycle_and_failure_is_reported_honestly():
    """Unrelated random images cannot be reconstructed: the job must fail with a reason, never fake metrics."""
    r = client.post("/api/jobs", files=png_files(3), data={"project_name": "t", "quality": "fast",
                                                          "recon_method": "classical"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    for _ in range(240):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "partial_success", "failed", "cancelled"):
            break
        time.sleep(0.5)
    assert job["status"] in ("failed", "completed", "partial_success")
    assert [s["key"] for s in job["stages"]] == ["image_analysis", "feature_extraction", "camera_pose",
                                                 "reconstruction", "evaluation"]
    assert len(job["images"]) == 3
    if job["status"] == "failed":
        assert job["error_message"]
    for res in (job["results"] or {}).values():
        if res and res.get("metrics"):
            # ground truth was not supplied, so reference metrics must be null rather than invented
            assert res["metrics"]["chamfer_distance"] is None and res["metrics"]["f_score"] is None
    assert any(j["job_id"] == job_id for j in client.get("/api/jobs").json())
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


@pytest.mark.parametrize("path", ["/api/jobs/../etc/files/point_cloud", "/api/jobs/EXP-ZZZZZZ/files/point_cloud",
                                  "/api/jobs/EXP-ZZZZZZ/images/..%2f..%2fsecret.png", "/api/jobs/x/files/mesh"])
def test_traversal_and_unknown_ids_are_rejected(path):
    assert client.get(path).status_code in (400, 403, 404)


def test_dataset_endpoints_with_dtu_layout(tmp_path, monkeypatch):
    from tests.test_datasets_and_poses import build_fake_dtu
    build_fake_dtu(tmp_path)
    monkeypatch.setenv("SPARSE3D_DATASET_DIR", str(tmp_path))
    ds = next(d for d in client.get("/api/datasets").json() if d["kind"] == "dtu")
    scan = ds["scans"][0]
    assert scan["id"] == "scan1" and scan["has_ground_truth"] and scan["has_camera_poses"]
    assert scan["cameras"] == [1, 9, 17, 25, 33, 41] and scan["lightings"] == [0, 3]

    imgs = client.get(f"/api/datasets/{ds['id']}/scan1/images", params={"lighting": 3}).json()
    assert len(imgs) == 6 and all(i["lighting"] == 3 for i in imgs)
    thumb = client.get(imgs[0]["url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"

    form = {"dataset_id": ds["id"], "scan_id": "scan1", "cameras": "1,9,17,25", "lighting": "0"}
    assert client.post("/api/validate", data=form).json()["image_count"] == 4
    assert client.post("/api/jobs", data={**form, "cameras": "1,2"}).status_code == 400   # camera 2 does not exist
    r = client.post("/api/jobs", data={**form, "recon_method": "classical"})
    assert r.status_code == 202
    job = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert job["dataset"]["scan"] == "scan1" and job["dataset"]["cameras"] == [1, 9, 17, 25]
    assert job["known_camera_poses"] == 4 and job["ground_truth_source"] == "stl001_total.ply"
    assert len(job["images"]) == 4
    client.post(f"/api/jobs/{job['job_id']}/cancel")
    assert client.get("/api/datasets/nope/scan1/images").status_code == 404


def test_analysis_empty_state():
    body = client.get("/api/analysis", params={"group_id": "GRP-AAAAAA"}).json()
    assert body["has_data"] is False and body["view_count"] == []


def test_sweep_needs_enough_images():
    r = client.post("/api/experiments/sweep", files=png_files(4), data={"view_counts": "3,4,5,6"})
    assert r.status_code == 400
