"""Tests for AGON image and video detection endpoints and forensic modules."""

from __future__ import annotations

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app
from detectors.metadata_analyzer import analyze_image_metadata
from detectors.sample_generator import (
    generate_ai_sample_image,
    generate_ai_sample_video,
    generate_camera_sample_image,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_index_and_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AGON" in resp.data
    assert b"agon-logo-dark.jpg" in resp.data
    assert b"agon-mark.png" in resp.data
    assert b"How AGON Considers Media AI-Generated" in resp.data

    health = client.get("/api/health")
    assert health.status_code == 200
    data = health.get_json()
    assert data["status"] == "ok"
    assert ".png" in data["supported_images"]
    assert ".mp4" in data["supported_videos"]


def test_metadata_analyzer_distinguishes_ai_vs_camera():
    ai_bytes, ai_name = generate_ai_sample_image()
    ai_meta = analyze_image_metadata(ai_bytes, filename=ai_name)
    assert len(ai_meta["ai_signatures"]) >= 1
    assert ai_meta["metadata_score"] >= 0.90

    cam_bytes, cam_name = generate_camera_sample_image()
    cam_meta = analyze_image_metadata(cam_bytes, filename=cam_name)
    assert cam_meta["ai_signatures"] == []
    assert len(cam_meta["camera_fields"]) >= 4
    assert cam_meta["metadata_score"] <= 0.25


def test_analyze_uploaded_images(client):
    ai_bytes, ai_name = generate_ai_sample_image()
    resp_ai = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(ai_bytes), ai_name)},
        content_type="multipart/form-data",
    )
    assert resp_ai.status_code == 200
    data_ai = resp_ai.get_json()
    assert data_ai["media_type"] == "image"
    assert data_ai["ai_probability"] >= 0.70
    assert data_ai["verdict"]["tone"] == "danger"
    assert data_ai["visuals"]["fft_spectrum"].startswith("data:image/png;base64,")
    assert data_ai["visuals"]["ela_heatmap"].startswith("data:image/png;base64,")
    assert data_ai["visuals"]["noise_residual"].startswith("data:image/png;base64,")

    cam_bytes, cam_name = generate_camera_sample_image()
    resp_cam = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(cam_bytes), cam_name)},
        content_type="multipart/form-data",
    )
    assert resp_cam.status_code == 200
    data_cam = resp_cam.get_json()
    assert data_cam["media_type"] == "image"
    assert data_cam["ai_probability"] < data_ai["ai_probability"]
    assert data_cam["ai_probability"] <= 0.45


def test_analyze_uploaded_video(client):
    vid_bytes, vid_name = generate_ai_sample_video()
    resp = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(vid_bytes), vid_name)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["media_type"] == "video"
    assert data["video_info"]["sampled_frames"] >= 4
    assert len(data["timeline"]) == data["video_info"]["sampled_frames"]
    assert "temporal_consistency" in data["signals"]
    assert data["visuals"]["fft_spectrum"].startswith("data:image/png;base64,")


def test_demo_endpoints(client):
    for sample_type in ("ai_image", "camera_image", "ai_video"):
        resp = client.post(f"/api/demo/{sample_type}")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert "ai_probability" in payload
        assert payload.get("demo_media_uri")


def test_invalid_uploads(client):
    resp_empty = client.post("/api/analyze", data={}, content_type="multipart/form-data")
    assert resp_empty.status_code == 400

    resp_bad_ext = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert resp_bad_ext.status_code == 400
