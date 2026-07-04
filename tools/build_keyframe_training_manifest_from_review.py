"""Build a retraining manifest from exported review_manifest JSON/CSV files.

The review manifest is a feedback bridge: accepted or modified AI candidates
can become higher-confidence proxy training rows after de-identification and
review. This tool does not create clinical ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.reports.writers import write_csv, write_json  # noqa: E402
from tools.build_keyframe_segmentation_proxy_manifest import write_preview_grid  # noqa: E402

MANIFEST_FIELDS = [
    "case_id",
    "image_path",
    "mask_path",
    "split",
    "source_path",
    "source_type",
    "frame_index",
    "timestamp_sec",
    "label_source",
    "input_domain",
    "fluorescence_attribute",
    "review_manifest_path",
    "review_state",
    "candidate_id",
    "roi_id",
    "geometry",
    "positive_area_fraction",
    "sample_weight",
    "width",
    "height",
    "medical_boundary",
]
BOUNDARY_NOTE = (
    "Rows are derived from review manifests and may still be proxy/non-target-domain data. "
    "Only physician-reviewed, de-identified samples should be promoted for higher-weight training."
)


def build_training_manifest_from_review(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(resolve_path(args.output_dir))
    mask_dir = ensure_dir(output_dir / "review_masks")
    manifest_path = output_dir / str(args.manifest_name)
    summary_path = output_dir / "keyframe_training_from_review_summary.json"
    preview_grid_path = output_dir / "keyframe_training_from_review_preview_grid.jpg"
    allowed_states = {_normalize_state(item) for item in str(args.review_states).split(",") if item.strip()}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for manifest_input in args.input:
        manifest_file = resolve_path(manifest_input)
        payload = load_review_payload(manifest_file)
        candidate_map = {str(item.get("candidate_id")): item for item in payload["candidates"] if item.get("candidate_id")}
        for candidate in payload["candidates"]:
            row, reason = candidate_to_training_row(
                candidate,
                manifest_path=manifest_file,
                mask_dir=mask_dir,
                dataset_id=str(args.dataset_id),
                input_domain=str(args.input_domain),
                fluorescence_attribute=str(args.fluorescence_attribute),
                val_fraction=float(args.val_fraction),
                seed=int(args.seed),
                allowed_states=allowed_states,
                accepted_weight=float(args.accepted_weight),
                modified_weight=float(args.modified_weight),
                rejected_weight=float(args.rejected_weight),
            )
            if row is None:
                skipped.append({"record_type": "candidate_region", "candidate_id": candidate.get("candidate_id"), "reason": reason})
            else:
                rows.append(row)
        for roi in payload["rois"]:
            row, reason = roi_to_training_row(
                roi,
                candidate_map=candidate_map,
                manifest_path=manifest_file,
                mask_dir=mask_dir,
                dataset_id=str(args.dataset_id),
                input_domain=str(args.input_domain),
                fluorescence_attribute=str(args.fluorescence_attribute),
                val_fraction=float(args.val_fraction),
                seed=int(args.seed),
                allowed_states=allowed_states,
                accepted_weight=float(args.accepted_weight),
                modified_weight=float(args.modified_weight),
                rejected_weight=float(args.rejected_weight),
            )
            if row is None:
                skipped.append({"record_type": "roi", "roi_id": roi.get("roi_id"), "reason": reason})
            else:
                rows.append(row)
    rows = deduplicate_rows(rows)
    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    preview = write_preview_grid(rows, preview_grid_path, max_samples=int(args.preview_sample_count))
    summary = {
        "schema_version": "osteo-vision-keyframe-review-training-manifest-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path),
        "preview_grid_path": str(preview_grid_path) if preview.get("written") else None,
        "input_review_manifests": [str(resolve_path(item)) for item in args.input],
        "sample_count": len(rows),
        "split_counts": value_counts(rows, "split"),
        "review_state_counts": value_counts(rows, "review_state"),
        "label_source_counts": value_counts(rows, "label_source"),
    "positive_area_fraction_stats": numeric_stats(rows, "positive_area_fraction"),
        "sample_weight_stats": numeric_stats(rows, "sample_weight"),
        "allowed_review_states": sorted(allowed_states),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "data_boundary": BOUNDARY_NOTE,
        "preview": preview,
        "fields": MANIFEST_FIELDS,
    }
    write_json(summary_path, summary)
    return {"manifest_path": str(manifest_path), "summary_path": str(summary_path), **summary}


def load_review_payload(path: Path) -> dict[str, list[dict[str, Any]]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "candidates": list(payload.get("candidates") or []),
            "rois": list(payload.get("rois") or []),
            "review_events": list(payload.get("review_events") or []),
        }
    if path.suffix.lower() == ".csv":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
        return {
            "candidates": [row for row in rows if row.get("record_type") == "candidate_region"],
            "rois": [row for row in rows if row.get("record_type") == "roi"],
            "review_events": [row for row in rows if row.get("record_type") == "review_event"],
        }
    raise ValueError(f"Unsupported review manifest extension: {path}")


def candidate_to_training_row(
    candidate: dict[str, Any],
    *,
    manifest_path: Path,
    mask_dir: Path,
    dataset_id: str,
    input_domain: str,
    fluorescence_attribute: str,
    val_fraction: float,
    seed: int,
    allowed_states: set[str],
    accepted_weight: float,
    modified_weight: float,
    rejected_weight: float,
) -> tuple[dict[str, Any] | None, str]:
    state = _normalize_state(candidate.get("status") or candidate.get("review_state"))
    if state not in allowed_states:
        return None, f"review_state_not_allowed:{state}"
    image_path = _existing_path(candidate.get("source_path"))
    if image_path is None:
        return None, "missing_source_path"
    width, height = image_size(image_path)
    if state == "rejected":
        sample_id = sample_id_for(dataset_id, candidate.get("candidate_id") or image_path.stem, "rejected_candidate")
        mask_path = mask_dir / f"{sample_id}_negative_mask.png"
        Image.fromarray(np.zeros((height, width), dtype=np.uint8)).save(mask_path)
        positive_fraction = 0.0
        label_source = "human_rejected_ai_candidate_negative_mask"
    else:
        candidate_mask_path = _existing_path(candidate.get("mask_path"))
        if candidate_mask_path is None:
            return None, "missing_mask_path"
        mask_path = candidate_mask_path
        sample_id = sample_id_for(dataset_id, candidate.get("candidate_id") or image_path.stem, "candidate")
        positive_fraction = mask_positive_fraction(mask_path)
        label_source = "human_reviewed_ai_candidate_mask"
    return training_row(
        sample_id=sample_id,
        image_path=image_path,
        mask_path=mask_path,
        source_path=image_path,
        review_manifest_path=manifest_path,
        review_state=state,
        candidate_id=str(candidate.get("candidate_id") or ""),
        roi_id="",
        label_source=label_source,
        input_domain=input_domain,
        fluorescence_attribute=fluorescence_attribute,
        frame_index=candidate.get("frame_index"),
        timestamp_sec=candidate.get("timestamp_sec"),
        geometry=candidate.get("bbox_normalized") or candidate.get("bbox_xyxy"),
        width=width,
        height=height,
        positive_fraction=positive_fraction,
        sample_weight=weight_for_state(
            state,
            accepted_weight=accepted_weight,
            modified_weight=modified_weight,
            rejected_weight=rejected_weight,
        ),
        val_fraction=val_fraction,
        seed=seed,
    ), ""


def roi_to_training_row(
    roi: dict[str, Any],
    *,
    candidate_map: dict[str, dict[str, Any]],
    manifest_path: Path,
    mask_dir: Path,
    dataset_id: str,
    input_domain: str,
    fluorescence_attribute: str,
    val_fraction: float,
    seed: int,
    allowed_states: set[str],
    accepted_weight: float,
    modified_weight: float,
    rejected_weight: float,
) -> tuple[dict[str, Any] | None, str]:
    state = _normalize_state(roi.get("review_state") or roi.get("status"))
    if state not in allowed_states:
        return None, f"review_state_not_allowed:{state}"
    candidate_id = str(roi.get("candidate_id") or "")
    candidate = candidate_map.get(candidate_id, {})
    image_path = _existing_path(candidate.get("source_path") or roi.get("source_path"))
    if image_path is None:
        return None, "missing_linked_candidate_source_path"
    width, height = image_size(image_path)
    geometry = _json_value(roi.get("geometry")) or _json_value(candidate.get("bbox_normalized"))
    fallback_bbox = _json_value(candidate.get("bbox_xyxy"))
    mask = mask_from_geometry(geometry, fallback_bbox=fallback_bbox, width=width, height=height)
    if mask is None or int(mask.sum()) <= 0:
        return None, "missing_or_empty_roi_geometry"
    sample_id = sample_id_for(dataset_id, roi.get("roi_id") or candidate_id or image_path.stem, "roi")
    mask_path = mask_dir / f"{sample_id}_mask.png"
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    return training_row(
        sample_id=sample_id,
        image_path=image_path,
        mask_path=mask_path,
        source_path=image_path,
        review_manifest_path=manifest_path,
        review_state=state,
        candidate_id=candidate_id,
        roi_id=str(roi.get("roi_id") or ""),
        label_source="human_reviewed_roi_geometry_mask",
        input_domain=input_domain,
        fluorescence_attribute=fluorescence_attribute,
        frame_index=roi.get("frame_index") or candidate.get("frame_index"),
        timestamp_sec=roi.get("timestamp_sec") or candidate.get("timestamp_sec"),
        geometry=geometry,
        width=width,
        height=height,
        positive_fraction=float(mask.mean()),
        sample_weight=weight_for_state(
            state,
            accepted_weight=accepted_weight,
            modified_weight=modified_weight,
            rejected_weight=rejected_weight,
        ),
        val_fraction=val_fraction,
        seed=seed,
    ), ""


def training_row(
    *,
    sample_id: str,
    image_path: Path,
    mask_path: Path,
    source_path: Path,
    review_manifest_path: Path,
    review_state: str,
    candidate_id: str,
    roi_id: str,
    label_source: str,
    input_domain: str,
    fluorescence_attribute: str,
    frame_index: Any,
    timestamp_sec: Any,
    geometry: Any,
    width: int,
    height: int,
    positive_fraction: float,
    sample_weight: float,
    val_fraction: float,
    seed: int,
) -> dict[str, Any]:
    return {
        "case_id": sample_id,
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "split": assign_split(sample_id, val_fraction=val_fraction, seed=seed),
        "source_path": str(source_path),
        "source_type": "review_manifest_feedback",
        "frame_index": _empty_if_none(frame_index),
        "timestamp_sec": _empty_if_none(timestamp_sec),
        "label_source": label_source,
        "input_domain": input_domain,
        "fluorescence_attribute": fluorescence_attribute,
        "review_manifest_path": str(review_manifest_path),
        "review_state": review_state,
        "candidate_id": candidate_id,
        "roi_id": roi_id,
        "geometry": json.dumps(_json_value(geometry), ensure_ascii=False, separators=(",", ":")),
        "positive_area_fraction": round(float(positive_fraction), 8),
        "sample_weight": round(max(0.0, float(sample_weight)), 6),
        "width": int(width),
        "height": int(height),
        "medical_boundary": BOUNDARY_NOTE,
    }


def mask_from_geometry(
    geometry: Any,
    *,
    fallback_bbox: Any,
    width: int,
    height: int,
) -> np.ndarray | None:
    parsed = _json_value(geometry)
    mask = np.zeros((height, width), dtype=np.uint8)
    if isinstance(parsed, dict) and {"x", "y", "width", "height"} <= set(parsed):
        x = float(parsed["x"])
        y = float(parsed["y"])
        rect_width = float(parsed["width"])
        rect_height = float(parsed["height"])
        if str(parsed.get("coordinate_space", "normalized")) == "normalized":
            x0 = round(x * width)
            y0 = round(y * height)
            x1 = round((x + rect_width) * width)
            y1 = round((y + rect_height) * height)
        else:
            x0 = round(x)
            y0 = round(y)
            x1 = round(x + rect_width)
            y1 = round(y + rect_height)
        return _fill_rect(mask, x0, y0, x1, y1)
    bbox = _json_value(fallback_bbox)
    if isinstance(bbox, list) and len(bbox) == 4:
        return _fill_rect(mask, int(float(bbox[0])), int(float(bbox[1])), int(float(bbox[2])), int(float(bbox[3])))
    return None


def _fill_rect(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> np.ndarray | None:
    height, width = mask.shape
    x0 = max(0, min(width, int(x0)))
    x1 = max(0, min(width, int(x1)))
    y0 = max(0, min(height, int(y0)))
    y1 = max(0, min(height, int(y1)))
    if x1 <= x0 or y1 <= y0:
        return None
    mask[y0:y1, x0:x1] = 1
    return mask


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("image_path")), str(row.get("mask_path")), str(row.get("label_source")))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return int(image.width), int(image.height)


def mask_positive_fraction(path: Path) -> float:
    with Image.open(path) as image:
        mask = np.asarray(image.convert("L"), dtype=np.uint8) > 0
    return float(mask.mean()) if mask.size else 0.0


def sample_id_for(dataset_id: str, identifier: Any, suffix: str) -> str:
    raw = f"{dataset_id}:{identifier}:{suffix}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in str(identifier))[:60]
    return f"{dataset_id}_{safe}_{digest}_{suffix}"


def weight_for_state(
    state: str,
    *,
    accepted_weight: float,
    modified_weight: float,
    rejected_weight: float,
) -> float:
    if state == "modified":
        return max(0.0, float(modified_weight))
    if state == "rejected":
        return max(0.0, float(rejected_weight))
    return max(0.0, float(accepted_weight))


def assign_split(sample_id: str, *, val_fraction: float, seed: int) -> str:
    val_fraction = max(0.0, min(0.9, val_fraction))
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    return "val" if bucket < val_fraction else "train"


def value_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def numeric_stats(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [_float(row.get(key)) for row in rows if _float(row.get(key)) is not None]
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None, "mean": None}
    array = np.asarray(values, dtype=np.float32)
    return {
        "count": int(array.size),
        "min": round(float(array.min()), 8),
        "median": round(float(np.median(array)), 8),
        "max": round(float(array.max()), 8),
        "mean": round(float(array.mean()), 8),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _existing_path(value: Any) -> Path | None:
    if not value:
        return None
    path = resolve_path(str(value))
    return path if path.exists() else None


def _normalize_state(value: Any) -> str:
    return str(value or "").split(".")[-1].strip().lower()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _empty_if_none(value: Any) -> Any:
    return "" if value is None else value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build keyframe training manifest from review_manifest JSON/CSV.")
    parser.add_argument("--input", nargs="+", required=True, help="Review manifest JSON/CSV path(s).")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest-name", default="keyframe_training_manifest_from_review.csv")
    parser.add_argument("--dataset-id", default="review_feedback")
    parser.add_argument("--input-domain", default="reviewed_proxy_keyframe_non_target_domain")
    parser.add_argument("--fluorescence-attribute", default="proxy_or_unknown_fluorescence")
    parser.add_argument("--review-states", default="accepted,modified")
    parser.add_argument("--accepted-weight", type=float, default=3.0)
    parser.add_argument("--modified-weight", type=float, default=4.0)
    parser.add_argument("--rejected-weight", type=float, default=0.5)
    parser.add_argument("--preview-sample-count", type=int, default=40)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260705)
    return parser.parse_args()


def main() -> int:
    result = build_training_manifest_from_review(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
