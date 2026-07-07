"""Build the first D046 video signal segmentation manifest.

This tool creates keyframe-level records for the platform's v1 video-signal
segmentation contract. It uses public/proxy D046 videos only and must not be
described as target-domain clinical jaw osteomyelitis annotation.
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
from src.models.video_signal_masks import save_video_signal_maps  # noqa: E402
from src.preprocess.fluorescence import enhance_fluorescence_signal  # noqa: E402
from src.reports.writers import write_csv, write_json  # noqa: E402

BOUNDARY_NOTE = (
    "D046 public/proxy videos and pseudo masks are for video-signal segmentation plumbing, "
    "quality checks, and review seeding. They are not real intraoperative ICG jaw osteomyelitis "
    "physician-labeled disease masks."
)

MANIFEST_FIELDS = [
    "case_id",
    "dataset_id",
    "source_video_path",
    "source_page_original_link",
    "source_record_id",
    "source_title",
    "frame_index",
    "timestamp_sec",
    "keyframe_path",
    "reference_frame_path",
    "fluorescence_frame_path",
    "overlay_frame_path",
    "fluorescence_signal_mask_path",
    "risk_mask_path",
    "uncertain_mask_path",
    "quality_status",
    "quality_reason",
    "label_source",
    "mask_type",
    "bone_gate_status",
    "review_state",
    "sample_weight",
    "positive_area_fraction",
    "uncertain_area_fraction",
    "width",
    "height",
    "view_layout",
    "input_domain",
    "medical_boundary",
]


def main() -> None:
    args = parse_args()
    summary = build_video_signal_manifest(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ofdvdnet-manifest",
        default="research/literature/inventory/ofdvdnet_video_manifest_20260704.csv",
    )
    parser.add_argument(
        "--video-library-manifest",
        default="research/literature/inventory/video_library_manifest_20260704.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
            "derived/video_signal_segmentation_20260706"
        ),
    )
    parser.add_argument("--max-videos", type=int, default=20)
    parser.add_argument("--keyframes-per-video", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--min-positive-area-fraction", type=float, default=0.0005)
    parser.add_argument("--max-positive-area-fraction", type=float, default=0.7)
    parser.add_argument("--manifest-name", default="video_signal_segmentation_manifest.csv")
    args = parser.parse_args()
    if args.max_videos <= 0:
        raise ValueError("--max-videos must be positive")
    if args.keyframes_per_video <= 0:
        raise ValueError("--keyframes-per-video must be positive")
    return args


def build_video_signal_manifest(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(resolve_path(args.output_dir))
    dirs = {
        name: ensure_dir(output_dir / name)
        for name in ("keyframes", "reference", "fluorescence", "overlay", "masks_proxy", "quality")
    }
    sources = discover_video_sources(args)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source in sources[: int(args.max_videos)]:
        source_rows, source_skipped = process_video_source(source, args, output_dirs=dirs)
        rows.extend(source_rows)
        skipped.extend(source_skipped)
    manifest_path = output_dir / str(args.manifest_name)
    summary_path = output_dir / "video_signal_segmentation_summary.json"
    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    summary = {
        "schema_version": "osteo-vision-video-signal-segmentation-manifest-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "source_count": len(sources),
        "processed_video_count": min(len(sources), int(args.max_videos)),
        "sample_count": len(rows),
        "skipped_count": len(skipped),
        "quality_status_counts": value_counts(rows, "quality_status"),
        "mask_type_counts": value_counts(rows, "mask_type"),
        "review_state_counts": value_counts(rows, "review_state"),
        "fields": MANIFEST_FIELDS,
        "data_boundary": BOUNDARY_NOTE,
        "skipped": skipped,
    }
    write_json(summary_path, summary)
    return {**summary, "summary_path": str(summary_path)}


def discover_video_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    ofdvd_path = resolve_path(args.ofdvdnet_manifest)
    if ofdvd_path.exists():
        for row in read_csv_rows(ofdvd_path):
            video_path = row.get("video_path")
            if not video_path or str(row.get("readable")).lower() != "true":
                continue
            path = resolve_path(video_path)
            if not path.exists():
                continue
            by_path[str(path)] = {
                "dataset_id": row.get("dataset_id") or "D046_OFDVDNET",
                "record_id": row.get("record_id"),
                "title": "OFDVDnet fluorescence-guided surgery proxy video",
                "video_path": str(path),
                "source_page_original_link": row.get("source_page_original_link"),
                "view_layout": row.get("view_layout") or "top_left_overlay__top_right_fluorescence__bottom_left_reference",
                "overlay_xyxy": row.get("overlay_xyxy"),
                "fluorescence_xyxy": row.get("fluorescence_xyxy"),
                "reference_xyxy": row.get("reference_xyxy"),
                "input_domain": row.get("domain_boundary") or "public_fluorescence_proxy_non_target_domain",
            }
    library_path = resolve_path(args.video_library_manifest)
    if library_path.exists():
        for row in read_csv_rows(library_path):
            local_path = row.get("local_path")
            if not local_path:
                continue
            path = resolve_path(local_path)
            if path.suffix.lower() != ".mp4" or not path.exists() or str(path) in by_path:
                continue
            by_path[str(path)] = {
                "dataset_id": "D046_VIDEO_LIBRARY",
                "record_id": row.get("record_id"),
                "title": row.get("title"),
                "video_path": str(path),
                "source_page_original_link": row.get("source_page_original_link"),
                "view_layout": "single_view_full_frame",
                "overlay_xyxy": "",
                "fluorescence_xyxy": "",
                "reference_xyxy": "",
                "input_domain": (
                    "public_fluorescence_proxy_non_target_domain"
                    if row.get("fluorescence") == "yes"
                    else "public_non_fluorescence_osteomyelitis_video_non_target_domain"
                ),
            }
    return [by_path[key] for key in sorted(by_path)]


def process_video_source(
    source: dict[str, Any],
    args: argparse.Namespace,
    *,
    output_dirs: dict[str, Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import cv2

    video_path = Path(str(source["video_path"]))
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return [], [{"source_video_path": str(video_path), "reason": "video_open_failed"}]
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    indices = sample_indices(frame_count, int(args.keyframes_per_video))
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for frame_index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame_bgr = capture.read()
        if not ok or frame_bgr is None:
            skipped.append({"source_video_path": str(video_path), "frame_index": frame_index, "reason": "read_failed"})
            continue
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        row = write_keyframe_record(
            source,
            frame_rgb,
            frame_index=int(frame_index),
            timestamp_sec=round(frame_index / fps, 6) if fps > 0 else "",
            args=args,
            output_dirs=output_dirs,
        )
        rows.append(row)
    capture.release()
    return rows, skipped


def write_keyframe_record(
    source: dict[str, Any],
    frame_rgb: np.ndarray,
    *,
    frame_index: int,
    timestamp_sec: float | str,
    args: argparse.Namespace,
    output_dirs: dict[str, Path],
) -> dict[str, Any]:
    sample_id = sample_identifier(str(source["video_path"]), frame_index, str(source.get("record_id") or "d046"))
    views = split_views(frame_rgb, source)
    keyframe_path = output_dirs["keyframes"] / f"{sample_id}.jpg"
    reference_path = output_dirs["reference"] / f"{sample_id}_reference.jpg"
    fluorescence_path = output_dirs["fluorescence"] / f"{sample_id}_fluorescence.jpg"
    overlay_path = output_dirs["overlay"] / f"{sample_id}_overlay.jpg"
    Image.fromarray(frame_rgb).save(keyframe_path, quality=92)
    Image.fromarray(views["reference"]).save(reference_path, quality=92)
    Image.fromarray(views["fluorescence"]).save(fluorescence_path, quality=92)
    Image.fromarray(views["overlay"]).save(overlay_path, quality=92)
    signal = proxy_signal(views["fluorescence"])
    mask = (signal >= float(args.threshold)).astype(np.uint8)
    positive_fraction = float(mask.mean()) if mask.size else 0.0
    quality_status, quality_reason = quality_gate(
        positive_fraction=positive_fraction,
        min_fraction=float(args.min_positive_area_fraction),
        max_fraction=float(args.max_positive_area_fraction),
    )
    mask_path = output_dirs["masks_proxy"] / f"{sample_id}_fluorescence_signal_mask.png"
    Image.fromarray((mask * 255).astype(np.uint8)).save(mask_path)
    signal_paths = save_video_signal_maps(
        probability=signal,
        mask=mask,
        uncertainty=None,
        output_dir=output_dirs["masks_proxy"],
        safe_case=sample_id,
        model_id="video_signal_manifest_proxy",
        threshold=float(args.threshold),
    )
    write_json(
        output_dirs["quality"] / f"{sample_id}_quality.json",
        {
            "case_id": sample_id,
            "quality_status": quality_status,
            "quality_reason": quality_reason,
            "positive_area_fraction": positive_fraction,
            "risk_summary": signal_paths.get("risk_summary", {}),
            "data_boundary": BOUNDARY_NOTE,
        },
    )
    height, width = signal.shape
    return {
        "case_id": sample_id,
        "dataset_id": source.get("dataset_id"),
        "source_video_path": source.get("video_path"),
        "source_page_original_link": source.get("source_page_original_link"),
        "source_record_id": source.get("record_id"),
        "source_title": source.get("title"),
        "frame_index": int(frame_index),
        "timestamp_sec": timestamp_sec,
        "keyframe_path": str(keyframe_path),
        "reference_frame_path": str(reference_path),
        "fluorescence_frame_path": str(fluorescence_path),
        "overlay_frame_path": str(overlay_path),
        "fluorescence_signal_mask_path": str(mask_path),
        "risk_mask_path": signal_paths["risk_mask_path"],
        "uncertain_mask_path": signal_paths["uncertain_mask_path"],
        "quality_status": quality_status,
        "quality_reason": quality_reason,
        "label_source": "fluorescence_intensity_proxy_mask",
        "mask_type": "fluorescence_hotspot",
        "bone_gate_status": "not_available_pending_review",
        "review_state": "review_required",
        "sample_weight": 1.0 if quality_status == "accepted" else 0.25,
        "positive_area_fraction": round(positive_fraction, 8),
        "uncertain_area_fraction": round(float(signal_paths.get("risk_summary", {}).get("uncertain_area_fraction", 0.0)), 8),
        "width": int(width),
        "height": int(height),
        "view_layout": source.get("view_layout"),
        "input_domain": source.get("input_domain"),
        "medical_boundary": BOUNDARY_NOTE,
    }


def split_views(frame_rgb: np.ndarray, source: dict[str, Any]) -> dict[str, np.ndarray]:
    height, width = frame_rgb.shape[:2]
    if source.get("view_layout") != "single_view_full_frame":
        return {
            "reference": crop_or_full(frame_rgb, source.get("reference_xyxy")),
            "fluorescence": crop_or_full(frame_rgb, source.get("fluorescence_xyxy")),
            "overlay": crop_or_full(frame_rgb, source.get("overlay_xyxy")),
        }
    return {"reference": frame_rgb, "fluorescence": frame_rgb, "overlay": frame_rgb if height and width else frame_rgb}


def crop_or_full(frame_rgb: np.ndarray, spec: Any) -> np.ndarray:
    bbox = parse_xyxy(spec)
    if bbox is None:
        return frame_rgb
    x0, y0, x1, y1 = bbox
    height, width = frame_rgb.shape[:2]
    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0))
    y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return frame_rgb
    return frame_rgb[y0:y1, x0:x1]


def parse_xyxy(value: Any) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    try:
        parts = [int(float(item)) for item in str(value).replace(",", "|").split("|")]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def proxy_signal(rgb: np.ndarray) -> np.ndarray:
    enhanced = enhance_fluorescence_signal(rgb, threshold=0.6)
    return np.asarray(enhanced["enhanced"], dtype=np.float32)


def quality_gate(*, positive_fraction: float, min_fraction: float, max_fraction: float) -> tuple[str, str]:
    if positive_fraction <= 0:
        return "warning", "empty_fluorescence_proxy_mask"
    if positive_fraction < min_fraction:
        return "warning", "positive_area_too_small"
    if positive_fraction > max_fraction:
        return "warning", "positive_area_too_large"
    return "accepted", "passes_video_signal_proxy_quality_gates"


def sample_indices(frame_count: int, count: int) -> list[int]:
    if frame_count <= 0:
        return [0]
    if count <= 1:
        return [0]
    return sorted({int(round(value)) for value in np.linspace(0, max(0, frame_count - 1), count)})


def sample_identifier(video_path: str, frame_index: int, record_id: str) -> str:
    digest = hashlib.sha1(f"{video_path}|{frame_index}".encode("utf-8")).hexdigest()[:10]
    safe_record = safe_name(record_id)
    return f"d046_video_signal_{safe_record}_frame_{frame_index:06d}_{digest}"


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "sample"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def value_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "")
        counts[key] = counts.get(key, 0) + 1
    return counts


if __name__ == "__main__":
    main()
