"""Video Frame Extraction & Temporal Forensic Analyzer.

Extracts evenly-spaced keyframes and consecutive frame pairs using OpenCV,
runs per-frame image forensics, evaluates temporal high-frequency flicker
and motion-residual anomalies, and produces a timeline report.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import cv2
import numpy as np
from scipy import ndimage

from detectors.image_forensics import (
    _to_base64_png,
    analyze_image_array,
    classify_verdict,
)


def _compute_pair_temporal_metrics(prev_rgb: np.ndarray, curr_rgb: np.ndarray) -> dict[str, float]:
    """Compare two consecutive frames for high-frequency temporal flicker vs scene motion."""
    # Downscale to max 384px for fast consistent comparison
    h, w = prev_rgb.shape[:2]
    scale = min(1.0, 384.0 / max(h, w))
    if scale < 1.0:
        nh, nw = max(32, int(h * scale)), max(32, int(w * scale))
        p = cv2.resize(prev_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        c = cv2.resize(curr_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        p, c = prev_rgb, curr_rgb

    p_gray = (0.299 * p[:, :, 0] + 0.587 * p[:, :, 1] + 0.114 * p[:, :, 2]).astype(np.float32) / 255.0
    c_gray = (0.299 * c[:, :, 0] + 0.587 * c[:, :, 1] + 0.114 * c[:, :, 2]).astype(np.float32) / 255.0

    # Gross motion (low-pass frame difference) vs high-frequency flicker (residual difference)
    p_low = ndimage.gaussian_filter(p_gray, sigma=2.5)
    c_low = ndimage.gaussian_filter(c_gray, sigma=2.5)
    low_diff = float(np.mean(np.abs(c_low - p_low)))

    p_high = p_gray - p_low
    c_high = c_gray - c_low
    high_diff = float(np.mean(np.abs(c_high - p_high)))

    # High-to-low temporal ratio: AI video generators often exhibit shimmering fine detail
    # even when global scene motion (low_diff) is small.
    hf_to_lf_ratio = high_diff / max(low_diff, 0.0025)

    # Color channel temporal drift
    chroma_diff = float(np.mean(np.abs(c.astype(np.float32) - p.astype(np.float32))) / 255.0)

    return {
        "low_motion": low_diff,
        "high_flicker": high_diff,
        "hf_to_lf_ratio": hf_to_lf_ratio,
        "chroma_diff": chroma_diff,
    }


def analyze_video_bytes(
    raw_bytes: bytes,
    filename: str = "upload.mp4",
    metadata_result: dict[str, Any] | None = None,
    external_ml_fn: Any = None,
    max_samples: int = 10,
) -> dict[str, Any]:
    """Decode video bytes, sample keyframes + adjacent pairs, and run temporal + spatial forensics."""
    ext = os.path.splitext(filename)[1].lower() or ".mp4"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Unable to decode video stream. Unsupported codec or corrupted file.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        # Fallback frame counting if container doesn't report frame_count cleanly
        if total_frames <= 0:
            frames_buf = []
            while len(frames_buf) < 180:
                ok, frm = cap.read()
                if not ok:
                    break
                frames_buf.append(frm)
            total_frames = len(frames_buf)
            if total_frames == 0:
                raise ValueError("Video contains no readable frames.")
            sample_indices = np.linspace(0, total_frames - 1, min(max_samples, total_frames), dtype=int).tolist()
            sampled_pairs = []
            for idx in sample_indices:
                curr_rgb = cv2.cvtColor(frames_buf[idx], cv2.COLOR_BGR2RGB)
                next_rgb = (
                    cv2.cvtColor(frames_buf[min(idx + 1, total_frames - 1)], cv2.COLOR_BGR2RGB)
                    if total_frames > 1
                    else None
                )
                sampled_pairs.append((int(idx), curr_rgb, next_rgb))
        else:
            num_samples = min(max_samples, max(1, total_frames))
            sample_indices = np.unique(np.linspace(0, max(0, total_frames - 1), num_samples, dtype=int)).tolist()
            sampled_pairs = []
            for idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frm = cap.read()
                if not ok or frm is None:
                    continue
                curr_rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
                next_rgb = None
                if idx + 1 < total_frames:
                    ok2, frm2 = cap.read()
                    if ok2 and frm2 is not None:
                        next_rgb = cv2.cvtColor(frm2, cv2.COLOR_BGR2RGB)
                sampled_pairs.append((int(idx), curr_rgb, next_rgb))

        cap.release()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    if not sampled_pairs:
        raise ValueError("Could not extract any frames from the uploaded video.")

    duration_sec = round(total_frames / fps, 2) if fps > 0 else None

    frame_results = []
    temporal_metrics = []
    best_frame_rgb = sampled_pairs[0][1]
    best_frame_score = -1.0

    # Optional external ML evaluation on up to 3 representative frames to keep latency low
    ml_frame_indices = set()
    if external_ml_fn is not None and len(sampled_pairs) > 0:
        picks = [0, len(sampled_pairs) // 2, len(sampled_pairs) - 1]
        ml_frame_indices = set(picks)

    ml_scores = []
    ml_provider_note = None

    for i, (frame_idx, curr_rgb, next_rgb) in enumerate(sampled_pairs):
        ext_ml_res = None
        if external_ml_fn is not None and i in ml_frame_indices:
            ext_ml_res = external_ml_fn(curr_rgb)
            if ext_ml_res and ext_ml_res.get("available") and ext_ml_res.get("ai_probability") is not None:
                ml_scores.append(float(ext_ml_res["ai_probability"]))
                ml_provider_note = ext_ml_res.get("provider")

        analysis = analyze_image_array(
            curr_rgb,
            metadata_result=None,
            external_ml_result=ext_ml_res,
            generate_visuals=False,
        )

        timestamp = round(frame_idx / fps, 2) if fps > 0 else float(i)
        frame_score = analysis["forensic_composite_score"]
        if frame_score > best_frame_score:
            best_frame_score = frame_score
            best_frame_rgb = curr_rgb

        pair_temp = None
        if next_rgb is not None:
            pair_temp = _compute_pair_temporal_metrics(curr_rgb, next_rgb)
            temporal_metrics.append(pair_temp)

        frame_results.append(
            {
                "frame_index": frame_idx,
                "timestamp_sec": timestamp,
                "ai_probability": analysis["ai_probability"],
                "ai_percentage": analysis["ai_percentage"],
                "forensic_score": frame_score,
                "fft_score": analysis["signals"]["frequency_fft"]["score"],
                "noise_score": analysis["signals"]["noise_residual"]["score"],
                "ela_score": analysis["signals"]["error_level_ela"]["score"],
                "temporal_hf_lf_ratio": round(pair_temp["hf_to_lf_ratio"], 3) if pair_temp else None,
                "thumbnail": _to_base64_png(curr_rgb, max_dim=220),
            }
        )

    # Generate full forensic visuals for the most suspicious frame
    peak_analysis = analyze_image_array(
        best_frame_rgb,
        metadata_result=metadata_result,
        external_ml_result=None,
        generate_visuals=True,
    )

    # Temporal consistency score
    if temporal_metrics:
        avg_hf_lf = float(np.mean([m["hf_to_lf_ratio"] for m in temporal_metrics]))
        std_hf_lf = float(np.std([m["hf_to_lf_ratio"] for m in temporal_metrics]))
        avg_high_flicker = float(np.mean([m["high_flicker"] for m in temporal_metrics]))
        # High ratio of high-freq residual change relative to global motion suggests synthetic texture shimmer
        flicker_signal = np.clip((avg_hf_lf - 0.85) / 1.40, 0.0, 1.0)
        variance_signal = np.clip((std_hf_lf - 0.20) / 0.65, 0.0, 1.0)
        temporal_score = float(np.clip(0.65 * flicker_signal + 0.35 * variance_signal, 0.12, 0.92))
    else:
        avg_hf_lf = 0.0
        std_hf_lf = 0.0
        avg_high_flicker = 0.0
        temporal_score = 0.50

    # Aggregate frame spatial scores (mean + top-quartile emphasis)
    frame_forensic_scores = [f["forensic_score"] for f in frame_results]
    mean_spatial = float(np.mean(frame_forensic_scores))
    p75_spatial = float(np.percentile(frame_forensic_scores, 75))
    spatial_aggregate = 0.60 * mean_spatial + 0.40 * p75_spatial

    meta_score = metadata_result.get("metadata_score", 0.5) if metadata_result else 0.5
    has_explicit_ai_meta = bool(metadata_result and metadata_result.get("ai_signatures"))

    if has_explicit_ai_meta:
        combined = max(0.92, 0.50 * meta_score + 0.30 * spatial_aggregate + 0.20 * temporal_score)
    else:
        combined = 0.58 * spatial_aggregate + 0.28 * temporal_score + 0.14 * meta_score

    if ml_scores:
        avg_ml = float(np.mean(ml_scores))
        combined = 0.52 * avg_ml + 0.48 * combined

    combined = float(np.clip(combined, 0.05, 0.98))
    verdict = classify_verdict(combined)

    # Average signal breakdown across frames
    avg_fft = round(float(np.mean([f["fft_score"] for f in frame_results])), 4)
    avg_noise = round(float(np.mean([f["noise_score"] for f in frame_results])), 4)
    avg_ela = round(float(np.mean([f["ela_score"] for f in frame_results])), 4)

    peak_signals = peak_analysis["signals"]
    peak_signals["frequency_fft"]["score"] = avg_fft
    peak_signals["noise_residual"]["score"] = avg_noise
    peak_signals["error_level_ela"]["score"] = avg_ela
    peak_signals["temporal_consistency"] = {
        "score": round(temporal_score, 4),
        "avg_hf_to_lf_ratio": round(avg_hf_lf, 3),
        "flicker_variance": round(std_hf_lf, 3),
        "mean_high_freq_delta": round(avg_high_flicker, 5),
        "finding": (
            "Elevated inter-frame high-frequency texture flicker relative to scene motion."
            if temporal_score >= 0.58
            else "Stable temporal texture and motion consistency across sampled frame pairs."
        ),
    }

    return {
        "ai_probability": round(combined, 4),
        "ai_percentage": round(combined * 100, 1),
        "verdict": verdict,
        "forensic_composite_score": round(spatial_aggregate, 4),
        "video_info": {
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "total_frames": total_frames,
            "duration_sec": duration_sec,
            "sampled_frames": len(frame_results),
        },
        "signals": peak_signals,
        "visuals": peak_analysis["visuals"],
        "timeline": frame_results,
        "external_ml": {
            "available": bool(ml_scores),
            "provider": ml_provider_note,
            "ai_probability": round(float(np.mean(ml_scores)), 4) if ml_scores else None,
        },
    }
