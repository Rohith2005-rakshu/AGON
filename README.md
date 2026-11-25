# AGON — Detect • Verify • Stay Informed

A full-stack web application (**AI Generated or Not?**) for analyzing whether images and videos are AI-generated or captured naturally.

## Features

- **Image & Video Upload**: Drag-and-drop or browse `PNG`, `JPG`, `JPEG`, `WEBP`, `BMP`, `TIFF`, `MP4`, `MOV`, `WEBM`, `AVI`, `MKV` (up to 80 MB).
- **2D FFT Spectral Analysis**: Computes centered log-magnitude power spectra, radial roll-off slopes, and periodic upsampling grid peak excess.
- **Error Level Analysis (ELA)**: Recompresses media at JPEG Q=90 to expose anomalous quantization residuals and spatial inconsistencies.
- **Sensor Noise Residual Analysis**: Evaluates high-pass micro-texture smoothness, spatial patch noise floor variance, and R/G/B channel noise correlations.
- **Video Temporal Forensics**: Extracts evenly-spaced keyframes and consecutive frame pairs via OpenCV (`cv2`), charts frame-by-frame AI likelihood over time, and measures inter-frame high-frequency shimmer relative to scene motion.
- **Metadata & Provenance Inspection**: Scans EXIF tags, PNG text chunks (`tEXt`/`iTXt`/`zTXt`), XMP/C2PA/JUMBF headers, and video container atoms for AI generator signatures (e.g., Stable Diffusion, ComfyUI, Midjourney, DALL-E, Firefly, Sora, Runway, Kling) and camera capture tags.
- **Optional Deep-Learning Boost**: Supports plugging in a local ONNX model (`models/ai_detector.onnx` via `onnxruntime`) or an optional Hugging Face Inference API token (`umm-maybe/AI-image-detector`) directly from the UI.
- **Built-in Demo Samples**: Test an AI-style diffusion PNG, a camera-style JPEG, and an AI-style MP4 directly from the UI.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Running Tests

```bash
python -m pytest -v
```
