from __future__ import annotations

from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def image_metadata(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    meta: dict[str, Any] = {"path": str(p), "extension": p.suffix.lower()}
    try:
        from PIL import Image

        with Image.open(p) as image:
            meta.update({"width": image.width, "height": image.height, "mode": image.mode})
    except Exception as exc:
        meta.update({"image_probe_error": str(exc)})
    return meta

