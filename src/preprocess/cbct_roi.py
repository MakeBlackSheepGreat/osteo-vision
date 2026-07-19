from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from src.core.paths import ensure_dir

IMAGE_KEYS = ("image", "volume", "ct", "cbct")
LABEL_KEYS = ("label", "mask", "segmentation", "anatomy_mask")
SCHEMA_VERSION = "osteo-vision-cbct-anatomy-roi-v1"
MEDICAL_BOUNDARY = (
    "CBCT anatomy ROI preprocessing is a research/competition platform validation step. "
    "It is not intraoperative ICG jaw osteomyelitis diagnosis and requires physician review."
)
DATASET_BOUNDARY = (
    "Dental/anatomy masks and CBCT-derived crops are non-target-domain priors for the official "
    "4K JPEG/MP4 fluorescence workflow unless verified on real intraoperative samples."
)


@dataclass(frozen=True)
class CbctRoiResult:
    roi_npz_path: str
    manifest_path: str
    manifest: dict[str, Any]


def build_cbct_anatomy_roi(
    input_npz: str | Path,
    output_dir: str | Path,
    *,
    case_id: str | None = None,
    anatomy_mask_path: str | Path | None = None,
    foreground_labels: Iterable[int] | None = None,
    margin_voxels: int | Iterable[int] = 8,
    fallback_crop_shape: Iterable[int] | None = None,
    source_kind: str = "cbct_proxy_npz",
    image_key: str | None = None,
    label_key: str | None = None,
) -> CbctRoiResult:
    """Crop a CBCT NPZ to a traceable anatomy ROI.

    The anatomy mask can later come from DentalSegmentator. If no external mask is
    supplied, the function falls back to the input label and finally to non-zero image
    voxels. The output is intentionally a preprocessing contract, not a diagnostic model.
    """

    input_path = Path(input_npz)
    output_root = ensure_dir(output_dir)
    resolved_case_id = case_id or input_path.stem
    warnings: list[dict[str, Any]] = []

    payload = _load_npz_payload(input_path)
    image_name, image = _pick_array(payload, [image_key] if image_key else IMAGE_KEYS)
    label_name, label = _pick_optional_array(payload, [label_key] if label_key else LABEL_KEYS)
    image = np.asarray(image, dtype=np.float32)
    if image.ndim != 3:
        raise ValueError(f"CBCT ROI preprocessing expects a 3D image array, got shape {image.shape}")
    if label is not None and np.asarray(label).shape != image.shape:
        raise ValueError(f"Label shape {np.asarray(label).shape} does not match image shape {image.shape}")

    anatomy_mask: np.ndarray | None = None
    anatomy_mask_source: str | None = None
    if anatomy_mask_path:
        anatomy_mask_source = str(anatomy_mask_path)
        anatomy_payload = _load_array_payload(Path(anatomy_mask_path))
        anatomy_mask = np.asarray(anatomy_payload)
        if anatomy_mask.shape != image.shape:
            raise ValueError(f"Anatomy mask shape {anatomy_mask.shape} does not match image shape {image.shape}")

    foreground_mask, roi_source = _foreground_mask(
        image,
        label=label,
        anatomy_mask=anatomy_mask,
        foreground_labels=foreground_labels,
        warnings=warnings,
    )
    if not np.any(foreground_mask):
        bbox = _center_bbox(image.shape, _parse_optional_shape(fallback_crop_shape, image.shape))
        roi_source = "center_crop_fallback"
        warnings.append(
            {
                "code": "cbct_roi_center_crop_fallback",
                "message": "No anatomy, label, or image foreground was found; using deterministic center crop.",
                "blocking": False,
            }
        )
    else:
        bbox = _bbox_from_mask(foreground_mask, margin=_parse_margin(margin_voxels))

    crop_slices = tuple(slice(start, stop) for start, stop in zip(bbox[:3], bbox[3:]))
    image_crop = image[crop_slices].astype(np.float32, copy=False)
    label_crop = np.asarray(label[crop_slices], dtype=np.int16) if label is not None else None
    anatomy_crop = np.asarray(anatomy_mask[crop_slices], dtype=np.int16) if anatomy_mask is not None else None

    roi_npz_path = output_root / f"{resolved_case_id}_cbct_anatomy_roi.npz"
    npz_payload: dict[str, Any] = {
        "image": image_crop,
        "case_id": np.asarray(resolved_case_id),
        "source_shape": np.asarray(image.shape, dtype=np.int32),
        "roi_bbox_zyx": np.asarray(bbox, dtype=np.int32),
    }
    if label_crop is not None:
        npz_payload["label"] = label_crop
    if anatomy_crop is not None:
        npz_payload["anatomy_mask"] = anatomy_crop
    np.savez_compressed(roi_npz_path, **npz_payload)

    label_values = np.unique(label_crop).astype(int).tolist() if label_crop is not None else []
    anatomy_label_values = np.unique(anatomy_crop).astype(int).tolist() if anatomy_crop is not None else []
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(UTC).isoformat(),
        "case_id": resolved_case_id,
        "source_path": str(input_path),
        "source_kind": source_kind,
        "image_key": image_name,
        "label_key": label_name,
        "anatomy_mask_path": anatomy_mask_source,
        "roi_source": roi_source,
        "foreground_labels": [int(value) for value in foreground_labels] if foreground_labels is not None else None,
        "margin_voxels_zyx": list(_parse_margin(margin_voxels)),
        "source_shape_zyx": [int(item) for item in image.shape],
        "crop_shape_zyx": [int(item) for item in image_crop.shape],
        "bbox_zyx": [int(item) for item in bbox],
        "bbox_normalized_zyx": _normalized_bbox_zyx(bbox, image.shape),
        "label_values": label_values,
        "anatomy_label_values": anatomy_label_values,
        "foreground_voxel_count": int(np.count_nonzero(foreground_mask)),
        "foreground_voxel_fraction": round(float(np.count_nonzero(foreground_mask) / foreground_mask.size), 8),
        "roi_npz_path": str(roi_npz_path),
        "warnings": warnings,
        "dataset_boundary": DATASET_BOUNDARY,
        "medical_boundary": MEDICAL_BOUNDARY,
        "replacement_note": (
            "This contract can consume DentalSegmentator-style anatomy masks later; this run does not execute "
            "the DentalSegmentator checkpoint."
        ),
    }
    manifest_path = output_root / f"{resolved_case_id}_cbct_anatomy_roi_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return CbctRoiResult(roi_npz_path=str(roi_npz_path), manifest_path=str(manifest_path), manifest=manifest)


def _load_npz_payload(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".npz":
        raise ValueError(f"Expected .npz input, got: {path}")
    with np.load(path, allow_pickle=False) as payload:
        return {name: np.asarray(payload[name]) for name in payload.files}


def _load_array_payload(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return np.asarray(np.load(path, allow_pickle=False))
    if suffix == ".npz":
        payload = _load_npz_payload(path)
        _, array = _pick_array(payload, LABEL_KEYS + IMAGE_KEYS)
        return array
    raise ValueError(f"Expected .npy or .npz anatomy mask, got: {path}")


def _pick_array(payload: dict[str, np.ndarray], keys: Iterable[str]) -> tuple[str, np.ndarray]:
    for key in keys:
        if key and key in payload:
            return key, payload[key]
    available = ", ".join(sorted(payload))
    expected = ", ".join(key for key in keys if key)
    raise KeyError(f"Expected one of [{expected}] in NPZ payload; available keys: {available}")


def _pick_optional_array(payload: dict[str, np.ndarray], keys: Iterable[str]) -> tuple[str | None, np.ndarray | None]:
    for key in keys:
        if key and key in payload:
            return key, payload[key]
    return None, None


def _foreground_mask(
    image: np.ndarray,
    *,
    label: np.ndarray | None,
    anatomy_mask: np.ndarray | None,
    foreground_labels: Iterable[int] | None,
    warnings: list[dict[str, Any]],
) -> tuple[np.ndarray, str]:
    if anatomy_mask is not None:
        return _label_foreground(anatomy_mask, foreground_labels), "external_anatomy_mask"
    if label is not None:
        return _label_foreground(label, foreground_labels), "input_label"
    warnings.append(
        {
            "code": "cbct_roi_image_nonzero_fallback",
            "message": "No anatomy mask or label was supplied; using finite non-zero image voxels as a coarse ROI.",
            "blocking": False,
        }
    )
    return np.isfinite(image) & (image != 0), "image_nonzero_fallback"


def _label_foreground(label: np.ndarray, foreground_labels: Iterable[int] | None) -> np.ndarray:
    data = np.asarray(label)
    if foreground_labels is None:
        return data > 0
    labels = [int(value) for value in foreground_labels]
    return np.isin(data, labels)


def _bbox_from_mask(mask: np.ndarray, *, margin: tuple[int, int, int]) -> tuple[int, int, int, int, int, int]:
    coords = np.argwhere(mask)
    starts = coords.min(axis=0)
    stops = coords.max(axis=0) + 1
    shape = np.asarray(mask.shape, dtype=np.int64)
    starts = np.maximum(0, starts - np.asarray(margin, dtype=np.int64))
    stops = np.minimum(shape, stops + np.asarray(margin, dtype=np.int64))
    values = [int(item) for item in [*starts.tolist(), *stops.tolist()]]
    return (values[0], values[1], values[2], values[3], values[4], values[5])


def _center_bbox(
    shape: tuple[int, int, int],
    crop_shape: tuple[int, int, int],
) -> tuple[int, int, int, int, int, int]:
    starts = [max(0, (int(size) - int(crop)) // 2) for size, crop in zip(shape, crop_shape)]
    stops = [min(int(size), start + int(crop)) for size, start, crop in zip(shape, starts, crop_shape)]
    values = [*starts, *stops]
    return (values[0], values[1], values[2], values[3], values[4], values[5])


def _parse_margin(value: int | Iterable[int]) -> tuple[int, int, int]:
    items: tuple[int, ...]
    if isinstance(value, int):
        items = (value, value, value)
    else:
        items = tuple(int(item) for item in value)
    if len(items) != 3:
        raise ValueError(f"Expected 3 margin values for z/y/x, got: {items}")
    if any(item < 0 for item in items):
        raise ValueError(f"Margin must be non-negative, got: {items}")
    return (items[0], items[1], items[2])


def _parse_optional_shape(value: Iterable[int] | None, source_shape: tuple[int, int, int]) -> tuple[int, int, int]:
    if value is None:
        return (int(source_shape[0]), int(source_shape[1]), int(source_shape[2]))
    shape = tuple(int(item) for item in value)
    if len(shape) != 3:
        raise ValueError(f"Expected 3 crop shape values for z/y/x, got: {shape}")
    clipped = [max(1, min(int(size), int(source))) for size, source in zip(shape, source_shape)]
    return (clipped[0], clipped[1], clipped[2])


def _normalized_bbox_zyx(
    bbox: tuple[int, int, int, int, int, int],
    shape: tuple[int, int, int],
) -> dict[str, float]:
    z0, y0, x0, z1, y1, x1 = [float(value) for value in bbox]
    depth, height, width = [float(value) for value in shape]
    return {
        "z": round(z0 / depth, 6),
        "y": round(y0 / height, 6),
        "x": round(x0 / width, 6),
        "depth": round((z1 - z0) / depth, 6),
        "height": round((y1 - y0) / height, 6),
        "width": round((x1 - x0) / width, 6),
    }
