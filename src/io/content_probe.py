from __future__ import annotations

from pathlib import Path
from typing import Any


def probe_file_signature(path: str | Path, *, max_bytes: int = 4096) -> dict[str, Any]:
    p = Path(path)
    header = b""
    try:
        with p.open("rb") as handle:
            header = handle.read(max_bytes)
    except Exception as exc:
        return {
            "path": str(p),
            "extension": p.suffix.lower(),
            "detected_family": "unreadable",
            "detected_mime": None,
            "signature_error": str(exc),
        }

    detected_family = "unknown"
    detected_mime: str | None = None
    signature = "unknown"
    if header.startswith(b"\xff\xd8\xff"):
        detected_family = "image"
        detected_mime = "image/jpeg"
        signature = "jpeg_soi"
    elif header.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_family = "image"
        detected_mime = "image/png"
        signature = "png"
    elif header.startswith(b"BM"):
        detected_family = "image"
        detected_mime = "image/bmp"
        signature = "bmp"
    elif header.startswith((b"II*\x00", b"MM\x00*")):
        detected_family = "image"
        detected_mime = "image/tiff"
        signature = "tiff"
    elif len(header) >= 12 and header[4:8] == b"ftyp":
        detected_family = "video"
        detected_mime = "video/mp4"
        signature = "mp4_ftyp"
    elif header.lstrip().lower().startswith((b"<html", b"<!doctype html")):
        detected_family = "html"
        detected_mime = "text/html"
        signature = "html"

    return {
        "path": str(p),
        "extension": p.suffix.lower(),
        "detected_family": detected_family,
        "detected_mime": detected_mime,
        "signature": signature,
        "header_hex": header[:16].hex(),
        "mp4_ftyp_present": signature == "mp4_ftyp",
    }


def signature_matches_upload_suffix(path: str | Path, suffix: str) -> tuple[bool, str, dict[str, Any]]:
    probe = probe_file_signature(path)
    normalized_suffix = suffix.lower()
    detected_family = str(probe.get("detected_family") or "unknown")
    if normalized_suffix in {".dcm", ".dicom", ".nii", ".nii.gz", ".nrrd", ".mha", ".mhd", ".stl", ".glb", ".gltf"}:
        if detected_family == "html":
            return False, "uploaded medical 3D content looks like HTML, not CBCT or surface model data", probe
        return True, "", probe
    if normalized_suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}:
        if detected_family == "image":
            return True, "", probe
        return False, "uploaded image content does not match the filename extension", probe
    if normalized_suffix == ".mp4":
        if probe.get("mp4_ftyp_present"):
            return True, "", probe
        return False, "uploaded MP4 container signature is missing", probe
    return True, "", probe
