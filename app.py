"""AGON — Detect • Verify • Stay Informed | AI Image & Video Detection Server."""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

import numpy as np
from flask import Flask, jsonify, render_template, request
from PIL import Image

from detectors.external_models import get_external_capabilities, run_external_ml
from detectors.image_forensics import analyze_image_bytes
from detectors.metadata_analyzer import analyze_image_metadata, analyze_video_metadata
from detectors.sample_generator import (
    generate_ai_sample_image,
    generate_ai_sample_video,
    generate_camera_sample_image,
)
from detectors.video_forensics import analyze_video_bytes

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v"}
MAX_UPLOAD_MB = 80

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _detect_media_kind(filename: str, mimetype: str | None) -> str | None:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if mimetype:
        if mimetype.startswith("image/"):
            return "image"
        if mimetype.startswith("video/"):
            return "video"
    return None


def run_detection_pipeline(
    raw_bytes: bytes,
    filename: str,
    media_kind: str,
    hf_token: str | None = None,
    hf_model: str | None = None,
) -> dict[str, Any]:
    """Execute metadata + forensic + optional ML detection for an image or video."""
    t0 = time.perf_counter()

    if media_kind == "image":
        meta_res = analyze_image_metadata(raw_bytes, filename=filename)
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb_arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
        ext_ml = run_external_ml(rgb_arr, hf_token=hf_token, hf_model=hf_model)
        analysis = analyze_image_bytes(
            raw_bytes,
            metadata_result=meta_res,
            external_ml_result=ext_ml,
        )
        analysis["external_ml"] = ext_ml
    elif media_kind == "video":
        meta_res = analyze_video_metadata(raw_bytes, filename=filename)

        def _ml_cb(frame_rgb: np.ndarray) -> dict[str, Any]:
            return run_external_ml(frame_rgb, hf_token=hf_token, hf_model=hf_model)

        has_ml_configured = bool((hf_token or "").strip()) or get_external_capabilities()["local_onnx_available"] or get_external_capabilities()["hf_env_token_configured"]
        analysis = analyze_video_bytes(
            raw_bytes,
            filename=filename,
            metadata_result=meta_res,
            external_ml_fn=_ml_cb if has_ml_configured else None,
        )
    else:
        raise ValueError(f"Unsupported media kind: {media_kind}")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "media_type": media_kind,
        "filename": filename,
        "file_size_bytes": len(raw_bytes),
        "processing_time_ms": elapsed_ms,
        "metadata": meta_res,
        **analysis,
    }


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "supported_images": sorted(IMAGE_EXTENSIONS),
            "supported_videos": sorted(VIDEO_EXTENSIONS),
            "max_upload_mb": MAX_UPLOAD_MB,
            "external_ml": get_external_capabilities(),
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Please select an image or video file."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "Empty file upload."}), 400

    media_kind = _detect_media_kind(file.filename, file.mimetype)
    if media_kind is None:
        return jsonify(
            {
                "error": "Unsupported file format. Supported images: PNG, JPG, WEBP, BMP, TIFF. Supported videos: MP4, MOV, WEBM, AVI, MKV."
            }
        ), 400

    raw_bytes = file.read()
    if not raw_bytes:
        return jsonify({"error": "Uploaded file is empty (0 bytes)."}), 400

    hf_token = request.form.get("hf_token", "")
    hf_model = request.form.get("hf_model", "")

    try:
        result = run_detection_pipeline(
            raw_bytes=raw_bytes,
            filename=file.filename,
            media_kind=media_kind,
            hf_token=hf_token,
            hf_model=hf_model,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"Failed to analyze media: {exc}"}), 422


@app.route("/api/demo/<sample_type>", methods=["POST"])
def analyze_demo(sample_type: str):
    if sample_type == "ai_image":
        raw_bytes, filename = generate_ai_sample_image()
        media_kind = "image"
        mime = "image/png"
    elif sample_type == "camera_image":
        raw_bytes, filename = generate_camera_sample_image()
        media_kind = "image"
        mime = "image/jpeg"
    elif sample_type == "ai_video":
        raw_bytes, filename = generate_ai_sample_video()
        media_kind = "video"
        mime = "video/mp4"
    else:
        return jsonify({"error": f"Unknown demo sample type: {sample_type}"}), 400

    hf_token = request.form.get("hf_token", "")
    hf_model = request.form.get("hf_model", "")
    result = run_detection_pipeline(
        raw_bytes=raw_bytes,
        filename=filename,
        media_kind=media_kind,
        hf_token=hf_token,
        hf_model=hf_model,
    )
    if media_kind == "video":
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        result["demo_media_uri"] = f"data:{mime};base64,{b64}"
    else:
        result["demo_media_uri"] = result["visuals"].get("original")
    return jsonify(result)


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": f"File exceeds the {MAX_UPLOAD_MB} MB upload limit."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
