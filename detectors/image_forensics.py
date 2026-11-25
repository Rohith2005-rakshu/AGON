"""Visual Forensic Analysis Engine for Images (and Video Frames).

Performs 2D FFT spectral analysis, Error Level Analysis (ELA), high-pass
sensor noise residual & Bayer channel correlation checks, and color/texture
statistics, producing both quantitative scores and visual diagnostic maps.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage


def _to_base64_png(rgb_array: np.ndarray, max_dim: int = 512) -> str:
    """Convert a uint8 RGB numpy array into a base64 data URI PNG."""
    img = Image.fromarray(rgb_array.astype(np.uint8), mode="RGB")
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _inferno_colormap(norm_01: np.ndarray) -> np.ndarray:
    """Map a [0, 1] 2D float array to an Inferno-inspired RGB uint8 palette."""
    x = np.clip(norm_01, 0.0, 1.0)
    # Piecewise linear stops: dark purple -> magenta -> orange -> bright yellow
    stops = np.array([0.0, 0.25, 0.55, 0.80, 1.0])
    r_vals = np.array([8, 86, 188, 249, 252], dtype=np.float32)
    g_vals = np.array([6, 16, 55, 142, 255], dtype=np.float32)
    b_vals = np.array([28, 110, 84, 10, 164], dtype=np.float32)

    r = np.interp(x, stops, r_vals)
    g = np.interp(x, stops, g_vals)
    b = np.interp(x, stops, b_vals)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def _center_crop_native(arr: np.ndarray, max_size: int = 512) -> np.ndarray:
    """Take a native-resolution center crop up to max_size to avoid resampling artifacts."""
    h, w = arr.shape[:2]
    ch = min(h, max_size)
    cw = min(w, max_size)
    y0 = (h - ch) // 2
    x0 = (w - cw) // 2
    return arr[y0 : y0 + ch, x0 : x0 + cw]


def _analyze_fft_spectrum(rgb: np.ndarray, generate_visual: bool = True) -> dict[str, Any]:
    """Compute 2D FFT power spectrum, radial roll-off, and periodic grid-peak metrics."""
    crop = _center_crop_native(rgb, max_size=512).astype(np.float32) / 255.0
    gray = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
    gray = gray - np.mean(gray)

    h, w = gray.shape
    wy = np.hanning(h)[:, None]
    wx = np.hanning(w)[None, :]
    windowed = gray * (wy * wx)

    f_shift = np.fft.fftshift(np.fft.fft2(windowed))
    mag = np.log1p(np.abs(f_shift))

    # Normalized radial distance from center
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt(((yy - cy) / max(cy, 1)) ** 2 + ((xx - cx) / max(cx, 1)) ** 2)

    # Radial bins from r=0.05 to r=0.95
    bins = np.linspace(0.05, 0.95, 24)
    radial_profile = []
    for i in range(len(bins) - 1):
        mask = (radius >= bins[i]) & (radius < bins[i + 1])
        if np.any(mask):
            radial_profile.append(float(np.mean(mag[mask])))
        else:
            radial_profile.append(0.0)

    mid_energy = float(np.mean(radial_profile[:8])) if len(radial_profile) >= 8 else 1.0
    high_energy = float(np.mean(radial_profile[-8:])) if len(radial_profile) >= 8 else 0.0
    hf_ratio = high_energy / max(mid_energy, 1e-6)

    # Spectral slope in log-log space
    r_centers = 0.5 * (bins[:-1] + bins[1:])
    prof_arr = np.maximum(np.array(radial_profile), 1e-6)
    slope, _ = np.polyfit(np.log(r_centers), np.log(prof_arr), 1)

    # Periodic peak excess (detects GAN/diffusion upsampler checkerboard spikes)
    outer_mask = (radius > 0.22) & (radius < 0.95)
    local_med = ndimage.median_filter(mag, size=7)
    excess = np.where(outer_mask, mag - local_med, 0.0)
    peak_excess = float(np.percentile(excess[outer_mask], 99.8)) if np.any(outer_mask) else 0.0
    mean_excess = float(np.mean(np.maximum(excess[outer_mask], 0.0))) if np.any(outer_mask) else 0.0

    # Heuristic scoring in [0, 1]
    # Strong periodic spikes (> 1.15) or unusually steep spectral drop-off (hf_ratio < 0.28) raise AI score
    spike_score = np.clip((peak_excess - 0.70) / 0.85, 0.0, 1.0)
    rolloff_score = np.clip((0.46 - hf_ratio) / 0.28, 0.0, 1.0)
    slope_score = np.clip((-slope - 0.55) / 0.65, 0.0, 1.0)

    fft_score = float(np.clip(0.45 * spike_score + 0.35 * rolloff_score + 0.20 * slope_score, 0.08, 0.95))

    visual_uri = None
    if generate_visual:
        vmax = np.percentile(mag, 99.7)
        vmin = np.percentile(mag, 5.0)
        norm = np.clip((mag - vmin) / max(vmax - vmin, 1e-5), 0.0, 1.0)
        visual_uri = _to_base64_png(_inferno_colormap(norm), max_dim=440)

    return {
        "score": round(fft_score, 4),
        "hf_to_mid_ratio": round(hf_ratio, 4),
        "spectral_slope": round(float(slope), 4),
        "periodic_peak_excess": round(peak_excess, 4),
        "mean_spectral_excess": round(mean_excess, 4),
        "visual": visual_uri,
        "finding": (
            "Elevated periodic frequency spikes or steep high-frequency roll-off detected."
            if fft_score >= 0.60
            else "Natural 1/f spectral decay with low periodic upsampling artifacts."
        ),
    }


def _analyze_ela(pil_img: Image.Image, generate_visual: bool = True) -> dict[str, Any]:
    """Compute Error Level Analysis (ELA) against JPEG Q=90 recompression."""
    rgb_img = pil_img.convert("RGB")
    if max(rgb_img.size) > 768:
        work_img = rgb_img.copy()
        work_img.thumbnail((768, 768), Image.Resampling.LANCZOS)
    else:
        work_img = rgb_img

    buf = io.BytesIO()
    work_img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    recomp = Image.open(buf).convert("RGB")

    orig_arr = np.asarray(work_img, dtype=np.float32)
    recomp_arr = np.asarray(recomp, dtype=np.float32)
    diff = np.abs(orig_arr - recomp_arr)
    diff_gray = np.mean(diff, axis=2)

    mean_ela = float(np.mean(diff_gray))
    std_ela = float(np.std(diff_gray))
    p95_ela = float(np.percentile(diff_gray, 95))

    # Block-wise ELA dispersion (16x16 regions)
    h, w = diff_gray.shape
    bh, bw = max(h // 8, 8), max(w // 8, 8)
    region_means = []
    for r in range(0, h - bh + 1, bh):
        for c in range(0, w - bw + 1, bw):
            region_means.append(float(np.mean(diff_gray[r : r + bh, c : c + bw])))
    region_cv = float(np.std(region_means) / max(np.mean(region_means), 1e-4)) if region_means else 0.0

    # Very low uniform ELA (< 1.4) often indicates synthetic smooth gradients / uncompressed AI PNG
    # Very high erratic region CV (> 0.85) can indicate compositing / local inpainting
    low_residual_signal = np.clip((2.4 - mean_ela) / 1.8, 0.0, 1.0)
    inconsistency_signal = np.clip((region_cv - 0.55) / 0.50, 0.0, 1.0)
    ela_score = float(np.clip(0.55 * low_residual_signal + 0.45 * inconsistency_signal, 0.12, 0.90))

    visual_uri = None
    if generate_visual:
        amplified = np.clip(diff_gray * 14.0 / 255.0, 0.0, 1.0)
        visual_uri = _to_base64_png(_inferno_colormap(amplified), max_dim=440)

    return {
        "score": round(ela_score, 4),
        "mean_ela": round(mean_ela, 3),
        "std_ela": round(std_ela, 3),
        "p95_ela": round(p95_ela, 3),
        "spatial_cv": round(region_cv, 3),
        "visual": visual_uri,
        "finding": (
            "Unusually uniform/low compression residual or localized ELA inconsistency."
            if ela_score >= 0.58
            else "Consistent quantization residual profile across spatial regions."
        ),
    }


def _analyze_noise_residual(rgb: np.ndarray, generate_visual: bool = True) -> dict[str, Any]:
    """Inspect high-pass noise residual, patch smoothness, and RGB channel noise correlation."""
    crop = _center_crop_native(rgb, max_size=640).astype(np.float32) / 255.0
    blurred = ndimage.gaussian_filter(crop, sigma=(1.2, 1.2, 0.0))
    residual = crop - blurred

    res_gray = 0.299 * residual[:, :, 0] + 0.587 * residual[:, :, 1] + 0.114 * residual[:, :, 2]
    global_noise_std = float(np.std(res_gray))

    # Patch-wise noise floor analysis (32x32 patches)
    h, w = res_gray.shape
    patch_stds = []
    step = 32
    for y in range(0, h - step + 1, step):
        for x in range(0, w - step + 1, step):
            patch_stds.append(float(np.std(res_gray[y : y + step, x : x + step])))

    if patch_stds:
        p10_noise = float(np.percentile(patch_stds, 10))
        p50_noise = float(np.percentile(patch_stds, 50))
        p90_noise = float(np.percentile(patch_stds, 90))
        smooth_fraction = float(np.mean(np.array(patch_stds) < 0.006))
    else:
        p10_noise = p50_noise = p90_noise = global_noise_std
        smooth_fraction = 0.0

    # Cross-channel high-pass correlation (R-G and B-G)
    r_flat = residual[:, :, 0].ravel()
    g_flat = residual[:, :, 1].ravel()
    b_flat = residual[:, :, 2].ravel()
    rg_corr = float(np.corrcoef(r_flat, g_flat)[0, 1]) if np.std(r_flat) > 1e-6 and np.std(g_flat) > 1e-6 else 0.0
    bg_corr = float(np.corrcoef(b_flat, g_flat)[0, 1]) if np.std(b_flat) > 1e-6 and np.std(g_flat) > 1e-6 else 0.0
    avg_channel_corr = 0.5 * (rg_corr + bg_corr)

    # AI diffusion images frequently exhibit ultra-smooth background patches (low p10_noise, high smooth_fraction)
    # and very tight luminance-locked channel residuals (avg_channel_corr > 0.88) or anomalous decorrelation.
    smoothness_signal = np.clip((0.0085 - p10_noise) / 0.007, 0.0, 1.0)
    patch_signal = np.clip((smooth_fraction - 0.15) / 0.55, 0.0, 1.0)
    corr_signal = np.clip((avg_channel_corr - 0.84) / 0.14, 0.0, 1.0)

    noise_score = float(np.clip(0.40 * smoothness_signal + 0.35 * patch_signal + 0.25 * corr_signal, 0.10, 0.92))

    visual_uri = None
    if generate_visual:
        vis = np.clip(np.abs(residual) * 18.0, 0.0, 1.0)
        # Boost grayscale visibility while preserving subtle chromatic noise tint
        vis_uint8 = (vis * 255.0).astype(np.uint8)
        visual_uri = _to_base64_png(vis_uint8, max_dim=440)

    return {
        "score": round(noise_score, 4),
        "global_noise_std": round(global_noise_std, 5),
        "p10_patch_noise": round(p10_noise, 5),
        "p50_patch_noise": round(p50_noise, 5),
        "p90_patch_noise": round(p90_noise, 5),
        "smooth_patch_ratio": round(smooth_fraction, 3),
        "rgb_residual_correlation": round(avg_channel_corr, 4),
        "visual": visual_uri,
        "finding": (
            "Over-smoothed micro-texture patches or tightly coupled RGB residuals typical of synthetic generation."
            if noise_score >= 0.58
            else "Organic spatial sensor-noise floor and natural RGB residual variation."
        ),
    }


def _analyze_color_statistics(rgb: np.ndarray) -> dict[str, Any]:
    """Inspect saturation extremes, dynamic range clipping, and edge-to-texture balance."""
    crop = _center_crop_native(rgb, max_size=512).astype(np.float32) / 255.0
    cmax = np.max(crop, axis=2)
    cmin = np.min(crop, axis=2)
    delta = cmax - cmin
    sat = np.where(cmax > 1e-5, delta / np.maximum(cmax, 1e-5), 0.0)

    mean_sat = float(np.mean(sat))
    high_sat_ratio = float(np.mean(sat > 0.75))
    clipped_ratio = float(np.mean((cmax > 0.985) | (cmin < 0.015)))

    # Gradient magnitude entropy (Sobel-like finite difference)
    gray = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    grad = np.sqrt(gx**2 + gy**2)
    grad_kurtosis_proxy = float(np.percentile(grad, 99) / max(np.mean(grad), 1e-4))

    sat_signal = np.clip((high_sat_ratio - 0.12) / 0.25, 0.0, 1.0)
    contrast_signal = np.clip((grad_kurtosis_proxy - 6.5) / 5.5, 0.0, 1.0)
    color_score = float(np.clip(0.50 * sat_signal + 0.50 * contrast_signal, 0.15, 0.88))

    return {
        "score": round(color_score, 4),
        "mean_saturation": round(mean_sat, 3),
        "high_saturation_ratio": round(high_sat_ratio, 3),
        "clipped_pixel_ratio": round(clipped_ratio, 3),
        "edge_to_texture_ratio": round(grad_kurtosis_proxy, 2),
        "finding": (
            "Hyper-clean edge-to-texture ratio or elevated saturation distribution."
            if color_score >= 0.58
            else "Balanced tonal transitions and natural saturation distribution."
        ),
    }


def classify_verdict(probability: float) -> dict[str, str]:
    """Map calibrated AI likelihood [0, 1] into a human-readable verdict and tone."""
    if probability >= 0.68:
        return {
            "label": "Likely AI-Generated",
            "tone": "danger",
            "description": "Multiple forensic or provenance signals align with synthetic AI generation.",
        }
    if probability >= 0.42:
        return {
            "label": "Uncertain / Mixed Signals",
            "tone": "warning",
            "description": "Signals are mixed or inconclusive; heavy compression, editing, or stripped metadata may obscure origin.",
        }
    return {
        "label": "Likely Authentic Media",
        "tone": "success",
        "description": "Spectral, noise-floor, and provenance checks resemble natural camera capture.",
    }


def analyze_image_array(
    rgb: np.ndarray,
    pil_img: Image.Image | None = None,
    metadata_result: dict[str, Any] | None = None,
    external_ml_result: dict[str, Any] | None = None,
    generate_visuals: bool = True,
) -> dict[str, Any]:
    """Run the full forensic analysis pipeline on an RGB uint8 numpy image."""
    if pil_img is None:
        pil_img = Image.fromarray(rgb, mode="RGB")

    fft_res = _analyze_fft_spectrum(rgb, generate_visual=generate_visuals)
    ela_res = _analyze_ela(pil_img, generate_visual=generate_visuals)
    noise_res = _analyze_noise_residual(rgb, generate_visual=generate_visuals)
    color_res = _analyze_color_statistics(rgb)

    # Base visual forensic composite
    forensic_score = (
        0.34 * fft_res["score"]
        + 0.30 * noise_res["score"]
        + 0.22 * ela_res["score"]
        + 0.14 * color_res["score"]
    )

    meta_score = metadata_result.get("metadata_score", 0.5) if metadata_result else 0.5
    has_explicit_ai_meta = bool(metadata_result and metadata_result.get("ai_signatures"))
    camera_count = len(metadata_result.get("camera_fields", [])) if metadata_result else 0

    if has_explicit_ai_meta:
        combined_score = max(0.92, 0.55 * meta_score + 0.45 * forensic_score)
    elif camera_count >= 4:
        combined_score = 0.32 * meta_score + 0.68 * forensic_score
    else:
        combined_score = 0.14 * meta_score + 0.86 * forensic_score

    # Integrate optional external ML / ONNX classifier if available
    if external_ml_result and external_ml_result.get("available") and external_ml_result.get("ai_probability") is not None:
        ml_prob = float(external_ml_result["ai_probability"])
        if has_explicit_ai_meta:
            combined_score = max(combined_score, 0.5 * combined_score + 0.5 * ml_prob)
        else:
            combined_score = 0.55 * ml_prob + 0.45 * combined_score

    combined_score = float(np.clip(combined_score, 0.04, 0.98))
    verdict = classify_verdict(combined_score)

    visuals = {}
    if generate_visuals:
        visuals = {
            "original": _to_base64_png(rgb, max_dim=560),
            "fft_spectrum": fft_res.pop("visual", None),
            "ela_heatmap": ela_res.pop("visual", None),
            "noise_residual": noise_res.pop("visual", None),
        }
    else:
        fft_res.pop("visual", None)
        ela_res.pop("visual", None)
        noise_res.pop("visual", None)

    return {
        "ai_probability": round(combined_score, 4),
        "ai_percentage": round(combined_score * 100, 1),
        "verdict": verdict,
        "forensic_composite_score": round(float(forensic_score), 4),
        "signals": {
            "frequency_fft": fft_res,
            "noise_residual": noise_res,
            "error_level_ela": ela_res,
            "color_texture": color_res,
        },
        "visuals": visuals,
    }


def analyze_image_bytes(
    raw_bytes: bytes,
    metadata_result: dict[str, Any] | None = None,
    external_ml_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decode raw image bytes and run full forensic analysis."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        rgb_img = img.convert("RGB")
        rgb_arr = np.asarray(rgb_img, dtype=np.uint8)
        result = analyze_image_array(
            rgb_arr,
            pil_img=rgb_img,
            metadata_result=metadata_result,
            external_ml_result=external_ml_result,
            generate_visuals=True,
        )
        result["dimensions"] = {"width": rgb_img.width, "height": rgb_img.height}
    return result
