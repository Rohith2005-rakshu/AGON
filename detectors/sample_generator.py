"""Built-in Sample Media Generator for Interactive Testing.

Synthesizes realistic test images and short MP4 videos on the fly so users
can immediately test and explore the forensic pipeline without external files.
"""

from __future__ import annotations

import io
import os
import tempfile

import cv2
import numpy as np
from PIL import Image, PngImagePlugin
from scipy import ndimage


def generate_ai_sample_image() -> tuple[bytes, str]:
    """Generate a synthetic image with smooth gradients, periodic grid spikes, and SD metadata."""
    h, w = 512, 512
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # Smooth surreal radial + wave composition
    cx, cy = w * 0.48, h * 0.45
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r = 128 + 110 * np.sin(dist / 36.0) * np.exp(-dist / 360.0) + 25 * np.cos(xx / 60.0)
    g = 110 + 95 * np.cos(dist / 44.0) * np.exp(-dist / 420.0) + 30 * np.sin(yy / 55.0)
    b = 155 + 90 * np.sin((xx + yy) / 90.0)

    # Subtle latent upsampler periodic grid artifact
    grid = 2.6 * np.sin(2.0 * np.pi * xx / 8.0) * np.sin(2.0 * np.pi * yy / 8.0)
    img_arr = np.stack([r + grid, g + grid, b + grid], axis=-1)
    img_arr = np.clip(img_arr, 0, 255).astype(np.uint8)

    pil_img = Image.fromarray(img_arr, mode="RGB")
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text(
        "parameters",
        "neon iridescent glass sphere, volumetric studio lighting\n"
        "Negative prompt: blurry, lowres\n"
        "Steps: 28, Sampler: DPM++ 2M Karras, CFG scale: 7.0, Model: Stable Diffusion XL",
    )

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", pnginfo=pnginfo)
    return buf.getvalue(), "demo_ai_diffusion_sample.png"


def generate_camera_sample_image() -> tuple[bytes, str]:
    """Generate a natural-textured image with 1/f micro-detail, sensor noise, and camera EXIF."""
    rng = np.random.default_rng(42)
    h, w = 512, 512

    # Multi-scale natural 1/f texture (octave noise)
    base = np.zeros((h, w, 3), dtype=np.float32)
    for sigma, weight in [(28.0, 55.0), (10.0, 28.0), (3.5, 14.0), (1.1, 6.5)]:
        layer = rng.normal(0.0, 1.0, (h, w, 3)).astype(np.float32)
        for ch in range(3):
            layer[:, :, ch] = ndimage.gaussian_filter(layer[:, :, ch], sigma=sigma)
        layer = layer / max(float(np.std(layer)), 1e-5) * weight
        base += layer

    # Natural sky-to-earth gradient + independent per-channel photon/readout noise
    yy = np.linspace(0, 1, h)[:, None]
    base[:, :, 0] += 118.0 + 35.0 * yy
    base[:, :, 1] += 132.0 + 18.0 * yy
    base[:, :, 2] += 155.0 - 45.0 * yy

    sensor_noise = rng.normal(0.0, 3.8, (h, w, 3)).astype(np.float32)
    img_arr = np.clip(base + sensor_noise, 0, 255).astype(np.uint8)

    pil_img = Image.fromarray(img_arr, mode="RGB")
    exif = pil_img.getexif()
    exif[0x010F] = "Canon"          # Make
    exif[0x0110] = "Canon EOS R6"   # Model
    exif[0x0131] = "EOS Firmware 1.8"
    exif[0x9003] = "2026:10:14 16:22:09"  # DateTimeOriginal
    exif[0x829A] = (1, 250)         # ExposureTime
    exif[0x829D] = (28, 10)         # FNumber
    exif[0x8827] = 200              # ISOSpeedRatings
    exif[0x920A] = (35, 1)          # FocalLength

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=92, exif=exif)
    return buf.getvalue(), "demo_camera_photo_sample.jpg"


def generate_ai_sample_video() -> tuple[bytes, str]:
    """Generate a short MP4 video with smooth synthetic frames and high-frequency shimmer."""
    rng = np.random.default_rng(7)
    w, h, fps, n_frames = 384, 256, 12, 24
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp_path = tmp.name

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_path, fourcc, fps, (w, h))
        for i in range(n_frames):
            phase = i * 0.25
            r = 120 + 85 * np.sin((xx + phase * 18) / 42.0) * np.cos(yy / 48.0)
            g = 105 + 80 * np.cos((yy - phase * 14) / 38.0)
            b = 165 + 65 * np.sin((xx - yy) / 65.0 + phase)

            # High-frequency synthetic shimmer across frames while low-freq motion stays gentle
            shimmer = rng.normal(0.0, 5.5, (h, w)).astype(np.float32)
            grid = 2.8 * np.sin(2.0 * np.pi * xx / 8.0 + phase) * np.sin(2.0 * np.pi * yy / 8.0)
            bgr = np.stack([b + shimmer + grid, g + shimmer + grid, r + shimmer + grid], axis=-1)
            writer.write(np.clip(bgr, 0, 255).astype(np.uint8))
        writer.release()

        with open(tmp_path, "rb") as f:
            data = f.read()
        return data, "demo_ai_video_sample.mp4"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
