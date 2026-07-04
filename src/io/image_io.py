from __future__ import annotations

from pathlib import Path
from typing import Any

from src.io.content_probe import probe_file_signature
from src.io.official_device_quality import assess_official_image_profile

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def image_metadata(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    meta: dict[str, Any] = {"path": str(p), "extension": p.suffix.lower(), "content_probe": probe_file_signature(p)}
    try:
        from PIL import Image

        with Image.open(p) as image:
            meta.update({"width": image.width, "height": image.height, "mode": image.mode})
        official_profile, quality_warnings = assess_official_image_profile(meta)
        meta.update(
            {
                "official_input_profile": official_profile,
                "official_format_match": official_profile["format_match"],
                "official_resolution_match": official_profile["resolution_match"],
                "quality_warnings": quality_warnings,
            }
        )
    except Exception as exc:
        meta.update({"image_probe_error": str(exc)})
    return meta

