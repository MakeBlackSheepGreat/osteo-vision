"""Build prompt-assisted bone-gate review seed masks from D046 video-signal keyframes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osteo_vision_core.core.paths import ensure_dir, resolve_path  # noqa: E402
from osteo_vision_core.models.prompt_segmenter import segment_2d_prompt_mask  # noqa: E402
from osteo_vision_core.reports.writers import write_csv, write_json  # noqa: E402

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/video_signal_segmentation_20260706/video_signal_segmentation_manifest.csv"
)
DEFAULT_OUTPUT_DIR = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/bone_gate_review_batch_20260707"
)
BOUNDARY_NOTE = (
    "Prompt-assisted bone-gate seed masks are semi-automatic review seeds from public/proxy D046 videos. "
    "They are not real intraoperative ICG jaw osteomyelitis physician labels."
)
FIELDS = [
    "case_id",
    "candidate_id",
    "source_path",
    "bone_gate_mask_path",
    "bone_gate_overlay_path",
    "mask_type",
    "label_source",
    "prompt_source",
    "review_state",
    "sample_weight",
    "source_video_path",
    "frame_index",
    "timestamp_sec",
    "source_page_original_link",
    "input_domain",
    "medical_boundary",
    "record_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-signal-manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-per-video", type=int, default=3)
    parser.add_argument("--min-positive-area", type=float, default=0.005)
    parser.add_argument("--bbox-padding", type=float, default=0.08)
    return parser.parse_args()


def build_bone_gate_seed_batch(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = resolve_path(args.video_signal_manifest)
    output_dir = ensure_dir(resolve_path(args.output_dir))
    mask_dir = ensure_dir(output_dir / "masks")
    overlay_dir = ensure_dir(output_dir / "overlays")
    rows = select_seed_rows(
        read_csv_rows(manifest_path),
        limit=int(args.limit),
        max_per_video=int(args.max_per_video),
        min_positive_area=float(args.min_positive_area),
    )
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source in rows:
        record, reason = create_seed_record(
            source, mask_dir=mask_dir, overlay_dir=overlay_dir, bbox_padding=float(args.bbox_padding)
        )
        if record is None:
            skipped.append({"case_id": source.get("case_id"), "reason": reason})
            continue
        records.append(record)
    csv_path = output_dir / "bone_gate_review_seed_manifest.csv"
    json_path = output_dir / "bone_gate_review_seed_manifest.json"
    summary_path = output_dir / "bone_gate_review_seed_summary.json"
    write_csv(csv_path, records, FIELDS)
    write_json(
        json_path,
        {
            "schema_version": "osteo-vision-bone-gate-review-seed-batch-v1",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "candidates": records,
            "medical_boundary": BOUNDARY_NOTE,
        },
    )
    summary = {
        "schema_version": "osteo-vision-bone-gate-review-seed-summary-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "json_manifest_path": str(json_path),
        "csv_manifest_path": str(csv_path),
        "sample_count": len(records),
        "skipped_count": len(skipped),
        "skipped": skipped[:100],
        "review_state_counts": value_counts(records, "review_state"),
        "label_source_counts": value_counts(records, "label_source"),
        "medical_boundary": BOUNDARY_NOTE,
    }
    write_json(summary_path, summary)
    return summary


def select_seed_rows(
    rows: list[dict[str, str]],
    *,
    limit: int,
    max_per_video: int,
    min_positive_area: float,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    per_video: dict[str, int] = defaultdict(int)
    candidates = sorted(
        rows,
        key=lambda row: (
            row.get("quality_status") != "accepted",
            -float_or_zero(row.get("positive_area_fraction")),
            row.get("source_video_path") or "",
            float_or_zero(row.get("timestamp_sec")),
        ),
    )
    for row in candidates:
        if len(selected) >= max(0, limit):
            break
        video_key = row.get("source_video_path") or row.get("source_record_id") or "unknown"
        if per_video[video_key] >= max_per_video:
            continue
        if float_or_zero(row.get("positive_area_fraction")) < min_positive_area:
            continue
        if not existing_path(row.get("keyframe_path")) or not existing_path(row.get("fluorescence_signal_mask_path")):
            continue
        selected.append(row)
        per_video[video_key] += 1
    return selected


def create_seed_record(
    row: dict[str, str],
    *,
    mask_dir: Path,
    overlay_dir: Path,
    bbox_padding: float,
) -> tuple[dict[str, Any] | None, str]:
    image_path = existing_path(row.get("keyframe_path"))
    signal_mask_path = existing_path(row.get("fluorescence_signal_mask_path"))
    if image_path is None:
        return None, "missing_keyframe_path"
    if signal_mask_path is None:
        return None, "missing_fluorescence_signal_mask_path"
    geometry = geometry_from_mask(signal_mask_path, padding=bbox_padding)
    if geometry is None:
        return None, "empty_signal_mask"
    payload = segment_2d_prompt_mask(
        image_path,
        output_dir=mask_dir,
        case_id=str(row.get("case_id") or image_path.stem),
        model_id="medsam2_osteo_promptable",
        prompts=[{"geometry": geometry, "source": "batch_signal_bbox_prompt"}],
        roi_hints=[{"geometry": geometry, "label": "exposed_bone", "source": "batch_signal_bbox_prompt"}],
    )
    mask_path = Path(payload["segmentation_mask"]["path"])
    overlay_path = Path(payload["lesion_evidence"]["overlay_path"])
    final_overlay = overlay_dir / overlay_path.name
    if overlay_path.exists() and overlay_path.resolve() != final_overlay.resolve():
        final_overlay.write_bytes(overlay_path.read_bytes())
    else:
        final_overlay = overlay_path
    case_id = str(row.get("case_id") or image_path.stem)
    return {
        "case_id": case_id,
        "candidate_id": f"seed_{case_id}",
        "source_path": str(image_path),
        "bone_gate_mask_path": str(mask_path),
        "bone_gate_overlay_path": str(final_overlay),
        "mask_type": "exposed_bone",
        "label_source": "prompt_assisted_review",
        "prompt_source": "batch_signal_bbox_prompt",
        "review_state": "review_required",
        "sample_weight": 1.0,
        "source_video_path": row.get("source_video_path") or "",
        "frame_index": row.get("frame_index") or "",
        "timestamp_sec": row.get("timestamp_sec") or "",
        "source_page_original_link": row.get("source_page_original_link") or "",
        "input_domain": row.get("input_domain") or "D046 public/proxy non-target-domain video",
        "medical_boundary": BOUNDARY_NOTE,
        "record_type": "candidate_region",
    }, ""


def geometry_from_mask(mask_path: Path, *, padding: float) -> dict[str, Any] | None:
    with Image.open(mask_path) as image:
        mask = np.asarray(image.convert("L"), dtype=np.uint8) > 0
    ys, xs = np.where(mask)
    if xs.size == 0 or ys.size == 0:
        return None
    height, width = mask.shape
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    pad_x = int(round((x1 - x0) * max(0.0, padding)))
    pad_y = int(round((y1 - y0) * max(0.0, padding)))
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(width, x1 + pad_x)
    y1 = min(height, y1 + pad_y)
    return {
        "type": "rect",
        "coordinate_space": "normalized",
        "x": round(x0 / width, 6),
        "y": round(y0 / height, 6),
        "width": round((x1 - x0) / width, 6),
        "height": round((y1 - y0) / height, 6),
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def existing_path(value: Any) -> Path | None:
    if not value:
        return None
    path = resolve_path(str(value))
    return path if path.exists() else None


def float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def value_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def main() -> int:
    print(json.dumps(build_bone_gate_seed_batch(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
