"""Optional External Deep-Learning Detector Integration.

Supports:
1. Local ONNX classifier (`models/ai_detector.onnx`) via onnxruntime if present.
2. Optional Hugging Face Inference API (`umm-maybe/AI-image-detector`) when a
   user supplies an API token in the UI or `HF_API_TOKEN` environment variable.
"""

from __future__ import annotations

import io
import os
from typing import Any

import numpy as np
import requests
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None


DEFAULT_HF_MODEL = "umm-maybe/AI-image-detector"
LOCAL_ONNX_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "ai_detector.onnx")

_onnx_session = None


def _get_onnx_session():
    global _onnx_session
    if _onnx_session is not None:
        return _onnx_session
    if ort is not None and os.path.isfile(LOCAL_ONNX_PATH):
        _onnx_session = ort.InferenceSession(LOCAL_ONNX_PATH, providers=["CPUExecutionProvider"])
        return _onnx_session
    return None


def get_external_capabilities() -> dict[str, Any]:
    """Report which optional ML backends are currently configured."""
    has_onnx = ort is not None and os.path.isfile(LOCAL_ONNX_PATH)
    has_env_hf = bool(os.environ.get("HF_API_TOKEN", "").strip())
    return {
        "local_onnx_available": has_onnx,
        "onnx_model_path": LOCAL_ONNX_PATH,
        "hf_env_token_configured": has_env_hf,
        "default_hf_model": DEFAULT_HF_MODEL,
    }


def _run_local_onnx(rgb: np.ndarray) -> dict[str, Any] | None:
    sess = _get_onnx_session()
    if sess is None:
        return None
    try:
        inp = sess.get_inputs()[0]
        # Expect NCHW [1, 3, H, W] float32 normalized with ImageNet stats
        shape = inp.shape
        h = shape[2] if len(shape) == 4 and isinstance(shape[2], int) else 224
        w = shape[3] if len(shape) == 4 and isinstance(shape[3], int) else 224

        img = Image.fromarray(rgb, mode="RGB").resize((w, h), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        tensor = np.transpose(arr, (2, 0, 1))[None, ...]

        outputs = sess.run(None, {inp.name: tensor})
        logits = np.asarray(outputs[0]).ravel()
        if logits.size >= 2:
            exp = np.exp(logits - np.max(logits))
            probs = exp / np.sum(exp)
            ai_prob = float(probs[1])
        else:
            ai_prob = float(1.0 / (1.0 + np.exp(-logits[0])))
        return {
            "available": True,
            "provider": "Local ONNX Model",
            "ai_probability": round(ai_prob, 4),
        }
    except Exception as exc:
        return {"available": False, "error": f"ONNX inference failed: {exc}"}


def run_hf_inference(rgb: np.ndarray, api_token: str, model_id: str = DEFAULT_HF_MODEL) -> dict[str, Any]:
    """Query Hugging Face Inference API with a JPEG-encoded image."""
    img = Image.fromarray(rgb, mode="RGB")
    if max(img.size) > 768:
        img.thumbnail((768, 768), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    payload = buf.getvalue()

    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "image/jpeg",
    }
    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=18)
        if resp.status_code != 200:
            return {
                "available": False,
                "provider": f"Hugging Face ({model_id})",
                "error": f"HTTP {resp.status_code}: {resp.text[:160]}",
            }
        data = resp.json()
        if isinstance(data, list) and data:
            ai_prob = None
            for item in data:
                label = str(item.get("label", "")).lower()
                score = float(item.get("score", 0.0))
                if any(k in label for k in ("artificial", "ai", "fake", "generated", "sdxl")):
                    ai_prob = score
                    break
            if ai_prob is None:
                # If only human/real label matched, invert it
                for item in data:
                    label = str(item.get("label", "")).lower()
                    score = float(item.get("score", 0.0))
                    if any(k in label for k in ("human", "real", "natural")):
                        ai_prob = 1.0 - score
                        break
            if ai_prob is not None:
                return {
                    "available": True,
                    "provider": f"Hugging Face ({model_id})",
                    "ai_probability": round(float(np.clip(ai_prob, 0.0, 1.0)), 4),
                    "raw_labels": data[:4],
                }
        return {"available": False, "provider": f"Hugging Face ({model_id})", "error": "Unexpected API response format."}
    except Exception as exc:
        return {"available": False, "provider": f"Hugging Face ({model_id})", "error": str(exc)}


def run_external_ml(rgb: np.ndarray, hf_token: str | None = None, hf_model: str | None = None) -> dict[str, Any]:
    """Run local ONNX or optional Hugging Face classifier if configured."""
    onnx_res = _run_local_onnx(rgb)
    if onnx_res is not None and onnx_res.get("available"):
        return onnx_res

    token = (hf_token or "").strip() or os.environ.get("HF_API_TOKEN", "").strip()
    if token:
        model = (hf_model or "").strip() or DEFAULT_HF_MODEL
        return run_hf_inference(rgb, token, model_id=model)

    return {
        "available": False,
        "provider": None,
        "ai_probability": None,
        "note": "Running in standalone local forensic mode (no external API token required).",
    }
