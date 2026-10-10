"""Integration tests for FastAPI Backend API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import numpy as np
import cv2

from src.backend.app import app

client = TestClient(app)


def test_health_endpoint():
    """Test /api/health endpoint returns 200 OK and healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "colmap_available" in data["environment"]


def test_create_job_validation_error():
    """Test POST /api/jobs returns 400 when less than 3 images are uploaded."""
    response = client.post(
        "/api/jobs",
        files=[
            ("images", ("img1.png", b"fakecontent", "image/png"))
        ]
    )
    assert response.status_code == 400
    assert "At least 3 images" in response.json()["detail"]


def test_create_job_success(tmp_path):
    """Test POST /api/jobs successfully queues a job with 3 valid images."""
    # Create 3 small synthetic PNG images in memory
    images_payload = []
    for i in range(3):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        images_payload.append(
            ("images", (f"img_{i}.png", buf.tobytes(), "image/png"))
        )

    response = client.post(
        "/api/jobs",
        files=images_payload,
        data={
            "run_dense": "false",
            "mesh_method": "none",
            "max_image_dim": "800"
        }
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # Poll status for the created job
    job_id = data["job_id"]
    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == job_id


def test_download_file_traversal_protection():
    """Test security against directory traversal attacks."""
    response = client.get("/api/jobs/../etc/files/point_cloud")
    assert response.status_code in [400, 403, 404]
