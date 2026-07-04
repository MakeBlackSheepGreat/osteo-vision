"""Build a pseudo-labeled keyframe segmentation manifest from JPEG/MP4 inputs.

The output manifest can be passed to scripts/train_keyframe_segmentation_proxy.py.
It is a proxy-data builder for the competition software loop, not a target-domain
clinical annotation workflow.
"""

from __future__ import annotations

import argparse
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
from src.preprocess.fluorescence import enhance_fluorescence_signal  # noqa: E402
from src.reports.writers import write_csv, write_json  # noqa: E402

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
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
    "positive_area_fraction",
    "component_count",
    "largest_component_fraction",
    "sample_weight",
    "quality_status",
    "quality_reason",
    "review_priority",
    "width",
    "height",
]
REVIEW_SEED_FIELDS = [
    *MANIFEST_FIELDS,
    "review_queue",
    "review_reason",
]
BOUNDARY_NOTE = (
    "Pseudo masks are generated from fluorescence-like intensity thresholding. "
    "They are proxy labels for software/model plumbing and must not be described "
    "as physician-labeled intraoperative ICG jaw osteomyelitis segmentation masks."
)


def build_proxy_manifest(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(resolve_path(args.output_dir))
    frame_dir = ensure_dir(output_dir / "frames")
    mask_dir = ensure_dir(output_dir / "masks")
    manifest_path = output_dir / str(args.manifest_name)
    summary_path = output_dir / "keyframe_segmentation_proxy_summary.json"
    review_seed_csv_path = output_dir / "keyframe_segmentation_review_seed_manifest.csv"
    review_seed_json_path = output_dir / "keyframe_segmentation_review_seed_manifest.json"
    preview_grid_path = output_dir / "keyframe_segmentation_proxy_preview_grid.jpg"
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    sources = discover_sources([Path(item) for item in args.input])
    for source_path in sources:
        if args.max_samples and len(rows) >= int(args.max_samples):
            break
        try:
            source_rows, source_skipped = process_source(source_path, args, frame_dir=frame_dir, mask_dir=mask_dir)
        except Exception as exc:  # pragma: no cover - defensive CLI path
            skipped.append({"source_path": str(source_path), "reason": f"source_failed: {exc}"})
            continue
        for row in source_rows:
            if args.max_samples and len(rows) >= int(args.max_samples):
                break
            rows.append(row)
        skipped.extend(source_skipped)
    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    review_seed_rows = select_review_seed_rows(rows, sample_count=int(args.review_seed_sample_count))
    write_csv(review_seed_csv_path, review_seed_rows, REVIEW_SEED_FIELDS)
    write_json(
        review_seed_json_path,
        {
            "schema_version": "osteo-vision-keyframe-review-seed-v1",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_manifest_path": str(manifest_path),
            "review_seed_csv_path": str(review_seed_csv_path),
            "sample_count": len(review_seed_rows),
            "selection_policy": (
                "Rank accepted proxy masks by moderate positive area and source diversity. "
                "Rows are candidates for human or physician review, not ground-truth labels."
            ),
            "data_boundary": BOUNDARY_NOTE,
            "rows": review_seed_rows,
        },
    )
    preview_result = write_preview_grid(rows, preview_grid_path, max_samples=int(args.preview_sample_count))
    summary = {
        "schema_version": "osteo-vision-keyframe-proxy-manifest-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "review_seed_csv_path": str(review_seed_csv_path),
        "review_seed_json_path": str(review_seed_json_path),
        "preview_grid_path": str(preview_grid_path) if preview_result.get("written") else None,
        "output_dir": str(output_dir),
        "source_count": len(sources),
        "sample_count": len(rows),
        "skipped_count": len(skipped),
        "split_counts": split_counts(rows),
        "source_type_counts": value_counts(rows, "source_type"),
        "quality_status_counts": value_counts(rows, "quality_status"),
        "positive_area_fraction_stats": numeric_stats(rows, "positive_area_fraction"),
        "largest_component_fraction_stats": numeric_stats(rows, "largest_component_fraction"),
        "quality_gates": {
            "min_positive_area_fraction": float(args.min_positive_area_fraction),
            "max_positive_area_fraction": float(args.max_positive_area_fraction),
            "min_component_area": int(args.min_component_area),
            "include_empty": bool(args.include_empty),
        },
        "review_seed_count": len(review_seed_rows),
        "label_source": "fluorescence_intensity_proxy_mask",
        "data_boundary": BOUNDARY_NOTE,
        "inputs_first200": [str(path) for path in sources[:200]],
        "skipped": skipped,
        "preview": preview_result,
        "fields": MANIFEST_FIELDS,
    }
    write_json(summary_path, summary)
    return {"manifest_path": str(manifest_path), "summary_path": str(summary_path), **summary}


def discover_sources(inputs: list[Path]) -> list[Path]:
    sources: list[Path] = []
    for item in inputs:
        path = resolve_path(item)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            sources.append(path)
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                    sources.append(candidate)
    return sorted(dict.fromkeys(sources))


def process_source(
    source_path: Path,
    args: argparse.Namespace,
    *,
    frame_dir: Path,
    mask_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    suffix = source_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        rgb = load_image_rgb(source_path)
        row, skip_reason = write_proxy_sample(
            rgb,
            source_path=source_path,
            source_type="image",
            frame_index=None,
            timestamp_sec=None,
            args=args,
            frame_dir=frame_dir,
            mask_dir=mask_dir,
        )
        if row is None:
            return [], [{"source_path": str(source_path), "reason": skip_reason or "proxy_mask_rejected"}]
        return [row], []
    if suffix in VIDEO_EXTENSIONS:
        return process_video(source_path, args, frame_dir=frame_dir, mask_dir=mask_dir)
    return [], [{"source_path": str(source_path), "reason": "unsupported_extension"}]


def process_video(
    source_path: Path,
    args: argparse.Namespace,
    *,
    frame_dir: Path,
    mask_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import cv2

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        return [], [{"source_path": str(source_path), "reason": "video_open_failed"}]
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    indices = video_sample_indices(
        frame_count=frame_count,
        max_frames=int(args.max_frames_per_video),
        frame_stride=int(args.frame_stride),
    )
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for frame_index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame_bgr = capture.read()
        if not ok or frame_bgr is None:
            skipped.append({"source_path": str(source_path), "frame_index": frame_index, "reason": "frame_read_failed"})
            continue
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        row, skip_reason = write_proxy_sample(
            rgb,
            source_path=source_path,
            source_type="video",
            frame_index=frame_index,
            timestamp_sec=round(frame_index / fps, 6) if fps > 0 else None,
            args=args,
            frame_dir=frame_dir,
            mask_dir=mask_dir,
        )
        if row is None:
            skipped.append(
                {
                    "source_path": str(source_path),
                    "frame_index": frame_index,
                    "reason": skip_reason or "proxy_mask_rejected",
                }
            )
        else:
            rows.append(row)
    capture.release()
    return rows, skipped


def write_proxy_sample(
    rgb: np.ndarray,
    *,
    source_path: Path,
    source_type: str,
    frame_index: int | None,
    timestamp_sec: float | None,
    args: argparse.Namespace,
    frame_dir: Path,
    mask_dir: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    mask, mask_stats = pseudo_mask(
        rgb,
        threshold=float(args.threshold),
        min_component_area=int(args.min_component_area),
    )
    positive_fraction = float(mask_stats["positive_area_fraction"])
    quality_status, quality_reason = quality_gate(
        positive_fraction=positive_fraction,
        min_positive_area_fraction=float(args.min_positive_area_fraction),
        max_positive_area_fraction=float(args.max_positive_area_fraction),
    )
    if quality_status != "accepted" and not bool(args.include_empty):
        return None, quality_reason
    sample_id = sample_identifier(source_path, frame_index=frame_index, dataset_id=str(args.dataset_id))
    image_path = frame_dir / f"{sample_id}.jpg"
    mask_path = mask_dir / f"{sample_id}_mask.png"
    Image.fromarray(rgb.astype(np.uint8)).save(image_path, quality=92)
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    height, width = mask.shape
    return {
        "case_id": sample_id,
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "split": assign_split(sample_id, val_fraction=float(args.val_fraction), seed=int(args.seed)),
        "source_path": str(source_path),
        "source_type": source_type,
        "frame_index": "" if frame_index is None else int(frame_index),
        "timestamp_sec": "" if timestamp_sec is None else float(timestamp_sec),
        "label_source": "fluorescence_intensity_proxy_mask",
        "input_domain": str(args.input_domain),
        "fluorescence_attribute": str(args.fluorescence_attribute),
        "positive_area_fraction": round(float(positive_fraction), 8),
        "component_count": int(mask_stats["component_count"]),
        "largest_component_fraction": round(float(mask_stats["largest_component_fraction"]), 8),
        "sample_weight": 1.0,
        "quality_status": quality_status,
        "quality_reason": quality_reason,
        "review_priority": review_priority(positive_fraction),
        "width": int(width),
        "height": int(height),
    }, None


def pseudo_mask(rgb: np.ndarray, *, threshold: float, min_component_area: int) -> tuple[np.ndarray, dict[str, Any]]:
    enhanced = enhance_fluorescence_signal(rgb, threshold=threshold)
    signal = np.asarray(enhanced["enhanced"], dtype=np.float32)
    mask = signal >= float(threshold)
    mask, component_stats = remove_small_components(mask.astype(np.uint8), min_component_area=min_component_area)
    positive_fraction = float(mask.mean()) if mask.size else 0.0
    return mask, {
        **component_stats,
        "positive_area_fraction": positive_fraction,
    }


def remove_small_components(mask: np.ndarray, *, min_component_area: int) -> tuple[np.ndarray, dict[str, Any]]:
    empty_stats = {"component_count": 0, "largest_component_area_px": 0, "largest_component_fraction": 0.0}
    if min_component_area <= 1:
        area = int(mask.sum())
        return mask.astype(np.uint8), {
            "component_count": 1 if area else 0,
            "largest_component_area_px": area,
            "largest_component_fraction": float(area / mask.size) if mask.size else 0.0,
        }
    try:
        import cv2

        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8),
            connectivity=8,
        )
    except Exception:
        area = int(mask.sum())
        if area < min_component_area:
            return np.zeros_like(mask, dtype=np.uint8), empty_stats
        return mask.astype(np.uint8), {
            "component_count": 1,
            "largest_component_area_px": area,
            "largest_component_fraction": float(area / mask.size) if mask.size else 0.0,
        }
    output = np.zeros_like(mask, dtype=np.uint8)
    kept_areas: list[int] = []
    for label in range(1, component_count):
        area = int(stats[label, 4])
        if area >= min_component_area:
            output[labels == label] = 1
            kept_areas.append(area)
    largest = max(kept_areas) if kept_areas else 0
    return output, {
        "component_count": len(kept_areas),
        "largest_component_area_px": largest,
        "largest_component_fraction": float(largest / mask.size) if mask.size else 0.0,
    }


def quality_gate(
    *,
    positive_fraction: float,
    min_positive_area_fraction: float,
    max_positive_area_fraction: float,
) -> tuple[str, str]:
    if positive_fraction <= 0:
        return "rejected", "empty_proxy_mask"
    if positive_fraction < min_positive_area_fraction:
        return "rejected", "positive_area_too_small"
    if positive_fraction > max_positive_area_fraction:
        return "rejected", "positive_area_too_large"
    return "accepted", "passes_proxy_quality_gates"


def review_priority(positive_fraction: float) -> str:
    if 0.02 <= positive_fraction <= 0.25:
        return "high"
    if 0.005 <= positive_fraction <= 0.4:
        return "medium"
    return "low"


def video_sample_indices(*, frame_count: int, max_frames: int, frame_stride: int) -> list[int]:
    if frame_count <= 0:
        return []
    if frame_stride > 0:
        return list(range(0, frame_count, frame_stride))[:max(1, max_frames)]
    count = min(max(1, max_frames), frame_count)
    return sorted({int(round(value)) for value in np.linspace(0, frame_count - 1, count)})


def assign_split(sample_id: str, *, val_fraction: float, seed: int) -> str:
    val_fraction = max(0.0, min(0.9, val_fraction))
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    return "val" if bucket < val_fraction else "train"


def sample_identifier(source_path: Path, *, frame_index: int | None, dataset_id: str) -> str:
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in source_path.stem)
    digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:8]
    suffix = "image" if frame_index is None else f"frame_{frame_index:06d}"
    return f"{dataset_id}_{stem}_{digest}_{suffix}"


def load_image_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        split = str(row.get("split") or "unknown")
        counts[split] = counts.get(split, 0) + 1
    return counts


def value_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def numeric_stats(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get(key, "")))
        except (TypeError, ValueError):
            continue
    if not values:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None, "mean": None}
    array = np.asarray(values, dtype=np.float32)
    return {
        "count": int(array.size),
        "min": round(float(array.min()), 8),
        "p25": round(float(np.percentile(array, 25)), 8),
        "median": round(float(np.median(array)), 8),
        "p75": round(float(np.percentile(array, 75)), 8),
        "max": round(float(array.max()), 8),
        "mean": round(float(array.mean()), 8),
    }


def select_review_seed_rows(rows: list[dict[str, Any]], *, sample_count: int) -> list[dict[str, Any]]:
    if sample_count <= 0:
        return []

    def sort_key(row: dict[str, Any]) -> tuple[int, float]:
        priority_rank = {"high": 0, "medium": 1, "low": 2}.get(str(row.get("review_priority")), 3)
        area = _float_value(row.get("positive_area_fraction"))
        return priority_rank, abs(area - 0.08)

    selected: list[dict[str, Any]] = []
    source_seen: set[str] = set()
    for row in sorted(rows, key=sort_key):
        source = str(row.get("source_path") or "")
        if source in source_seen and len(source_seen) < sample_count:
            continue
        selected.append(_review_seed_row(row))
        source_seen.add(source)
        if len(selected) >= sample_count:
            return selected
    for row in sorted(rows, key=sort_key):
        if len(selected) >= sample_count:
            break
        case_id = str(row.get("case_id"))
        if any(str(item.get("case_id")) == case_id for item in selected):
            continue
        selected.append(_review_seed_row(row))
    return selected


def _review_seed_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "review_queue": "small_gold_standard_seed",
        "review_reason": (
            "Candidate proxy mask selected for human review. Accept, modify, or reject before using as "
            "higher-confidence training data."
        ),
    }


def write_preview_grid(rows: list[dict[str, Any]], output_path: Path, *, max_samples: int) -> dict[str, Any]:
    if not rows or max_samples <= 0:
        return {"written": False, "reason": "no_preview_requested_or_no_rows"}
    selected = select_review_seed_rows(rows, sample_count=min(max_samples, len(rows)))
    if not selected:
        return {"written": False, "reason": "no_selected_rows"}
    tile_w, tile_h = 192, 144
    cols = min(5, max(1, int(np.ceil(np.sqrt(len(selected))))))
    rows_count = int(np.ceil(len(selected) / cols))
    grid = Image.new("RGB", (cols * tile_w, rows_count * tile_h), color=(20, 20, 20))
    for index, row in enumerate(selected):
        image_path = Path(str(row.get("image_path")))
        mask_path = Path(str(row.get("mask_path")))
        if not image_path.exists() or not mask_path.exists():
            continue
        with Image.open(image_path) as image_obj, Image.open(mask_path) as mask_obj:
            image = image_obj.convert("RGB").resize((tile_w, tile_h))
            mask = np.asarray(mask_obj.convert("L").resize((tile_w, tile_h)), dtype=np.uint8) > 0
        overlay = np.asarray(image, dtype=np.float32)
        overlay[mask, 1] = np.maximum(overlay[mask, 1], 230)
        overlay[mask, 0] *= 0.45
        overlay[mask, 2] *= 0.45
        tile = Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8))
        x = (index % cols) * tile_w
        y = (index // cols) * tile_h
        grid.paste(tile, (x, y))
    ensure_dir(output_path.parent)
    grid.save(output_path, quality=90)
    return {"written": True, "path": str(output_path), "sample_count": len(selected), "tile_size": [tile_w, tile_h]}


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build pseudo-labeled JPEG/MP4 keyframe manifest for keyframe segmentation training."
    )
    parser.add_argument("--input", nargs="+", required=True, help="Input file(s) or folder(s) containing JPEG/PNG/MP4.")
    parser.add_argument(
        "--output-dir",
        default="research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/keyframe_proxy_manifest",
    )
    parser.add_argument("--manifest-name", default="keyframe_segmentation_proxy_manifest.csv")
    parser.add_argument("--dataset-id", default="keyframe_proxy")
    parser.add_argument("--input-domain", default="public_or_local_proxy_keyframe")
    parser.add_argument("--fluorescence-attribute", default="fluorescence_like_or_unknown")
    parser.add_argument("--threshold", type=float, default=0.62)
    parser.add_argument("--min-component-area", type=int, default=32)
    parser.add_argument("--min-positive-area-fraction", type=float, default=0.0005)
    parser.add_argument("--max-positive-area-fraction", type=float, default=0.6)
    parser.add_argument("--max-frames-per-video", type=int, default=12)
    parser.add_argument("--frame-stride", type=int, default=0, help="Use fixed frame stride when > 0; otherwise sample evenly.")
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--preview-sample-count", type=int, default=30)
    parser.add_argument("--review-seed-sample-count", type=int, default=50)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260704)
    parser.add_argument("--include-empty", action="store_true")
    return parser.parse_args()


def main() -> int:
    result = build_proxy_manifest(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
