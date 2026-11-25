"""Metadata & Provenance Analyzer for Images and Videos.

Inspects EXIF tags, PNG text chunks, XMP/C2PA/JUMBF headers, and MP4/MOV container
atoms for known AI generator signatures and authentic camera provenance fields.
"""

from __future__ import annotations

import io
import re
from typing import Any

from PIL import ExifTags, Image

AI_GENERATOR_PATTERNS: list[tuple[str, str]] = [
    (r"midjourney", "Midjourney"),
    (r"dall[\s\-_]*e", "DALL-E"),
    (r"openai", "OpenAI / ChatGPT Image"),
    (r"stable\s*diffusion", "Stable Diffusion"),
    (r"automatic1111|a1111", "AUTOMATIC1111 WebUI"),
    (r"comfyui|\"class_type\"\s*:\s*\"ksampler\"", "ComfyUI Workflow"),
    (r"invokeai", "InvokeAI"),
    (r"novelai", "NovelAI"),
    (r"adobe\s*firefly|firefly", "Adobe Firefly"),
    (r"black\s*forest\s*labs|flux\.?1", "Flux (Black Forest Labs)"),
    (r"ideogram", "Ideogram"),
    (r"leonardo\.ai|leonardo\s*ai", "Leonardo AI"),
    (r"google\s*imagen|imagen\s*\d|synthid", "Google Imagen / SynthID"),
    (r"sora", "OpenAI Sora"),
    (r"runway\s*ml|runway\s*gen", "Runway Gen"),
    (r"kling\s*ai|kuaishou\s*kling", "Kling AI"),
    (r"luma\s*dream\s*machine|lumalabs", "Luma Dream Machine"),
    (r"pika\s*labs|pika\.art", "Pika"),
    (r"hailuo|minimax", "Hailuo / MiniMax"),
    (r"veo\s*\d|google\s*veo", "Google Veo"),
    (r"trainedalgorithmicmedia|digitalCapture", "IPTC/C2PA Algorithmic Media Tag"),
    (r"cfg\s*scale\s*:|negative\s*prompt\s*:|sampler\s*:", "Diffusion Generation Parameters"),
]

CAMERA_PROVENANCE_TAGS = {
    "Make",
    "Model",
    "LensMake",
    "LensModel",
    "ExposureTime",
    "FNumber",
    "ISOSpeedRatings",
    "PhotographicSensitivity",
    "FocalLength",
    "ShutterSpeedValue",
    "ApertureValue",
    "DateTimeOriginal",
    "WhiteBalance",
    "Flash",
}


def _safe_str(value: Any, max_len: int = 300) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
    else:
        text = str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _scan_text_for_ai_signatures(text: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for pattern, label in AI_GENERATOR_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m and label not in seen_labels:
            seen_labels.add(label)
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 50)
            snippet = _safe_str(text[start:end], max_len=140)
            matches.append({"generator": label, "evidence": snippet})
    return matches


def analyze_image_metadata(raw_bytes: bytes, filename: str = "") -> dict[str, Any]:
    """Analyze image EXIF, PNG info chunks, XMP, and C2PA/JUMBF bytes."""
    exif_summary: dict[str, str] = {}
    png_chunks: dict[str, str] = {}
    camera_fields_found: list[str] = []
    software_tags: list[str] = []

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img_format = img.format or "UNKNOWN"
            width, height = img.size
            mode = img.mode

            # Extract PNG tEXt / iTXt / zTXt info
            for k, v in (img.info or {}).items():
                if k in ("icc_profile", "exif"):
                    continue
                val_str = _safe_str(v, max_len=500)
                if val_str:
                    png_chunks[str(k)] = val_str

            # Extract EXIF tags
            exif_obj = img.getexif()
            if exif_obj:
                for tag_id, value in exif_obj.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    val_str = _safe_str(value, max_len=240)
                    if val_str:
                        exif_summary[str(tag_name)] = val_str
                        if tag_name in CAMERA_PROVENANCE_TAGS:
                            camera_fields_found.append(str(tag_name))
                        if tag_name in ("Software", "ProcessingSoftware", "Artist", "ImageDescription", "UserComment"):
                            software_tags.append(f"{tag_name}: {val_str}")

                # Check ExifIFD sub-IFD (ExposureTime, LensModel, DateTimeOriginal live here)
                try:
                    exif_ifd = exif_obj.get_ifd(0x8769)
                    for tag_id, value in exif_ifd.items():
                        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                        val_str = _safe_str(value, max_len=240)
                        if val_str:
                            exif_summary[str(tag_name)] = val_str
                            if tag_name in CAMERA_PROVENANCE_TAGS and str(tag_name) not in camera_fields_found:
                                camera_fields_found.append(str(tag_name))
                            if tag_name in ("UserComment", "LensModel") and tag_name == "UserComment":
                                software_tags.append(f"{tag_name}: {val_str}")
                except Exception:
                    pass
    except Exception as exc:
        return {
            "error": str(exc),
            "ai_signatures": [],
            "has_c2pa": False,
            "camera_fields": [],
            "exif": {},
            "png_chunks": {},
            "metadata_score": 0.5,
            "summary": "Could not parse image metadata.",
        }

    # Inspect raw header/XMP/JUMBF bytes (first 512 KB + trailing 256 KB)
    head = raw_bytes[:524288]
    tail = raw_bytes[-262144:] if len(raw_bytes) > 524288 else b""
    combined_ascii = (head + b"\n" + tail).decode("latin-1", errors="ignore")

    has_c2pa = bool(re.search(r"c2pa|jumb|jumd|cr\.contentauth", combined_ascii, flags=re.IGNORECASE))
    has_xmp = bool(re.search(r"x:xmpmeta|xmlns:xmp|photoshop:|dc:creator", combined_ascii, flags=re.IGNORECASE))

    searchable_corpus = "\n".join(
        [filename]
        + [f"{k}: {v}" for k, v in png_chunks.items()]
        + [f"{k}: {v}" for k, v in exif_summary.items()]
        + [combined_ascii]
    )
    ai_signatures = _scan_text_for_ai_signatures(searchable_corpus)

    # Filter out false-positive "digitalCapture" unless paired with AI or explicit C2PA algorithmic tag
    filtered_signatures = []
    for sig in ai_signatures:
        if sig["generator"] == "IPTC/C2PA Algorithmic Media Tag":
            if "trainedalgorithmicmedia" in sig["evidence"].lower():
                filtered_signatures.append(sig)
        else:
            filtered_signatures.append(sig)
    ai_signatures = filtered_signatures

    # Score metadata signal in [0, 1] where 1 = strongly AI, 0 = strongly authentic camera, 0.5 = neutral/stripped
    if ai_signatures:
        metadata_score = 0.96
        summary = f"Explicit AI generator metadata detected ({', '.join(s['generator'] for s in ai_signatures)})."
    elif len(camera_fields_found) >= 4:
        metadata_score = 0.14
        make = exif_summary.get("Make", "")
        model = exif_summary.get("Model", "")
        cam = f"{make} {model}".strip() or "Camera EXIF"
        summary = f"Rich authentic camera EXIF present ({cam}; {len(camera_fields_found)} capture tags)."
    elif len(camera_fields_found) >= 1:
        metadata_score = 0.30
        summary = f"Partial camera EXIF found ({', '.join(camera_fields_found[:4])})."
    elif not exif_summary and not png_chunks:
        metadata_score = 0.54
        summary = "No EXIF or generator metadata present (common for both AI exports and social-media re-uploads)."
    else:
        metadata_score = 0.50
        summary = "Metadata present without explicit AI generator tags or full camera capture details."

    return {
        "format": img_format,
        "dimensions": {"width": width, "height": height},
        "color_mode": mode,
        "ai_signatures": ai_signatures,
        "has_c2pa": has_c2pa,
        "has_xmp": has_xmp,
        "camera_fields": camera_fields_found,
        "software_tags": software_tags[:10],
        "exif": dict(list(exif_summary.items())[:25]),
        "png_chunks": dict(list(png_chunks.items())[:15]),
        "metadata_score": round(metadata_score, 4),
        "summary": summary,
    }


def analyze_video_metadata(raw_bytes: bytes, filename: str = "") -> dict[str, Any]:
    """Inspect MP4/MOV/WebM/AVI header and trailer strings for encoder/AI generator signatures."""
    head = raw_bytes[:524288]
    tail = raw_bytes[-524288:] if len(raw_bytes) > 524288 else b""
    ascii_blob = (head + b"\n" + tail).decode("latin-1", errors="ignore")

    ai_signatures = _scan_text_for_ai_signatures(filename + "\n" + ascii_blob)
    # Remove noisy false-positive matches on short words like "sora" inside binary gibberish unless word-bounded
    cleaned_sigs = []
    for sig in ai_signatures:
        if sig["generator"] == "OpenAI Sora":
            if re.search(r"\bopenai\s+sora\b|\bsora\b", sig["evidence"], flags=re.IGNORECASE):
                cleaned_sigs.append(sig)
        elif sig["generator"] == "IPTC/C2PA Algorithmic Media Tag":
            if "trainedalgorithmicmedia" in sig["evidence"].lower():
                cleaned_sigs.append(sig)
        else:
            cleaned_sigs.append(sig)

    has_c2pa = bool(re.search(r"c2pa|jumb|cr\.contentauth", ascii_blob, flags=re.IGNORECASE))

    # Extract readable encoder / creation strings (e.g., Lavf, HandBrake, Apple, Android)
    encoder_matches = re.findall(
        r"(?:Lavf[\d\.]+|HandBrake[\s\d\.]+|Apple[\s\w]{0,20}|Google[\s\w]{0,20}|Samsung[\s\w]{0,20}|DJI[\s\w]{0,20}|GoPro[\s\w]{0,20}|FFmpeg[\s\w\.]*)",
        ascii_blob,
    )
    encoders = list(dict.fromkeys(_safe_str(e, 60) for e in encoder_matches if len(e.strip()) > 3))[:8]

    camera_vendor_hit = any(
        any(v in e.lower() for v in ("apple", "samsung", "dji", "gopro", "sony", "canon", "nikon"))
        for e in encoders
    )

    if cleaned_sigs:
        metadata_score = 0.94
        summary = f"Explicit AI video generator signature found ({', '.join(s['generator'] for s in cleaned_sigs)})."
    elif camera_vendor_hit:
        metadata_score = 0.25
        summary = f"Hardware/camera device signature found in container ({', '.join(encoders[:3])})."
    elif encoders:
        metadata_score = 0.50
        summary = f"Software muxer/encoder metadata found ({', '.join(encoders[:3])}); no explicit AI tag."
    else:
        metadata_score = 0.52
        summary = "Minimal container metadata; relying on visual and temporal frame forensics."

    return {
        "ai_signatures": cleaned_sigs,
        "has_c2pa": has_c2pa,
        "encoders": encoders,
        "metadata_score": round(metadata_score, 4),
        "summary": summary,
    }
