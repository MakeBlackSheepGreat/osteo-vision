"""Build a second-round multi-mask training manifest for video signal segmentation.

The manifest merges D046 fluorescence proxy masks and prompt-assisted review
masks. It is a training bridge only; rows are not target-domain clinical labels.
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

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.reports.writers import write_csv, write_json  # noqa: E402

BOUNDARY_NOTE = (
    "This multi-mask manifest merges public/proxy video-signal masks and prompt-assisted review masks. "
    "It is for platform model training and error analysis only, not real intraoperative ICG jaw osteomyelitis "
    "clinical ground truth."
)

MANIFEST_FIELDS = [
    "case_id",
    "image_path",
    "mask_type",
    "mask_path",
    "review_state",
    "sample_weight",
    "label_source",
    "source_video_path",
    "frame_index",
    "timestamp_sec",
    "source_manifest_path",
    "source_record_type",
    "source_case_id",
    "source_candidate_id",
    "source_roi_id",
    "quality_status",
    "width",
    "height",
    "split",
    "input_domain",
    "medical_boundary",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--video-signal-manifest",
        default=(
            "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
            "derived/video_signal_segmentation_20260706/video_signal_segmentation_manifest.csv"
        ),
    )
    parser.add_argument("--review-manifest", nargs="*", default=[])
    parser.add_argument(
        "--output-dir",
        default=(
            "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
            "derived/video_signal_multimask_20260707"
        ),
    )
    parser.add_argument("--manifest-name", default="video_signal_multimask_training_manifest.csv")
    parser.add_argument(
        "--include-mask-types",
        default="fluorescence_hotspot,exposed_bone,boundary_risk,uncertain",
    )
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260707)
    return parser.parse_args()


def build_multimask_manifest(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ensure_dir(resolve_path(args.output_dir))
    manifest_path = output_dir / str(args.manifest_name)
    summary_path = output_dir / "video_signal_multimask_training_summary.json"
    allowed_mask_types = {item.strip() for item in str(args.include_mask_types).split(",") if item.strip()}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    video_manifest = resolve_path(args.video_signal_manifest)
    if video_manifest.exists():
        source_rows, source_skipped = rows_from_video_signal_manifest(
            video_manifest,
            allowed_mask_types=allowed_mask_types,
            val_fraction=float(args.val_fraction),
            seed=int(args.seed),
        )
        rows.extend(source_rows)
        skipped.extend(source_skipped)
    for review_manifest in args.review_manifest:
        review_path = resolve_path(review_manifest)
        source_rows, source_skipped = rows_from_review_manifest(
            review_path,
            allowed_mask_types=allowed_mask_types,
            val_fraction=float(args.val_fraction),
            seed=int(args.seed),
        )
        rows.extend(source_rows)
        skipped.extend(source_skipped)
    rows = deduplicate_rows(rows)
    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    summary = {
        "schema_version": "osteo-vision-video-signal-multimask-training-manifest-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path),
        "sample_count": len(rows),
        "mask_type_counts": value_counts(rows, "mask_type"),
        "review_state_counts": value_counts(rows, "review_state"),
        "label_source_counts": value_counts(rows, "label_source"),
        "split_counts": value_counts(rows, "split"),
        "allowed_mask_types": sorted(allowed_mask_types),
        "skipped_count": len(skipped),
        "skipped": skipped[:100],
        "fields": MANIFEST_FIELDS,
        "medical_boundary": BOUNDARY_NOTE,
    }
    write_json(summary_path, summary)
    return summary


def rows_from_video_signal_manifest(
    manifest_path: Path,
    *,
    allowed_mask_types: set[str],
    val_fraction: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source in read_csv_rows(manifest_path):
        image_path = source.get("keyframe_path") or source.get("overlay_frame_path")
        source_case_id = str(source.get("case_id") or "")
        entries = [
            ("fluorescence_hotspot", source.get("fluorescence_signal_mask_path"), source.get("label_source") or "fluorescence_intensity_proxy_mask"),
            ("boundary_risk", source.get("risk_mask_path"), "derived_risk_mask_proxy"),
            ("uncertain", source.get("uncertain_mask_path"), "derived_uncertain_mask_proxy"),
        ]
        for mask_type, mask_path, label_source in entries:
            if mask_type not in allowed_mask_types:
                continue
            row, reason = training_row(
                source_case_id=source_case_id,
                image_path=image_path,
                mask_path=mask_path,
                mask_type=mask_type,
                review_state=source.get("review_state") or "review_required",
                sample_weight=source.get("sample_weight") or 1.0,
                label_source=label_source,
                source_video_path=source.get("source_video_path"),
                frame_index=source.get("frame_index"),
                timestamp_sec=source.get("timestamp_sec"),
                source_manifest_path=manifest_path,
                source_record_type="video_signal_manifest",
                source_candidate_id="",
                source_roi_id="",
                quality_status=source.get("quality_status"),
                input_domain=source.get("input_domain"),
                val_fraction=val_fraction,
                seed=seed,
            )
            if row is None:
                skipped.append({"source_case_id": source_case_id, "mask_type": mask_type, "reason": reason})
            else:
                rows.append(row)
    return rows, skipped


def rows_from_review_manifest(
    manifest_path: Path,
    *,
    allowed_mask_types: set[str],
    val_fraction: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not manifest_path.exists():
        return [], [{"source_manifest_path": str(manifest_path), "reason": "missing_review_manifest"}]
    payload = load_review_payload(manifest_path)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for record in payload:
        mask_type = str(record.get("mask_type") or "")
        if not mask_type and record.get("bone_gate_mask_path"):
            mask_type = "exposed_bone"
        if mask_type not in allowed_mask_types:
            continue
        mask_path = record.get("bone_gate_mask_path") if mask_type == "exposed_bone" else record.get("mask_path")
        mask_path = mask_path or record.get("mask_path")
        row, reason = training_row(
            source_case_id=record.get("case_id"),
            image_path=record.get("source_path"),
            mask_path=mask_path,
            mask_type=mask_type,
            review_state=record.get("review_state") or record.get("status") or "review_required",
            sample_weight=record.get("sample_weight") or sample_weight_for_state(record.get("review_state")),
            label_source=record.get("label_source") or "review_manifest_feedback",
            source_video_path=record.get("source_video_path") or record.get("source_path"),
            frame_index=record.get("frame_index"),
            timestamp_sec=record.get("timestamp_sec"),
            source_manifest_path=manifest_path,
            source_record_type=record.get("record_type") or "review_manifest_record",
            source_candidate_id=record.get("candidate_id"),
            source_roi_id=record.get("roi_id"),
            quality_status="reviewed" if str(record.get("review_state") or "").lower() in {"accepted", "modified"} else "review_required",
            input_domain=record.get("input_domain") or "prompt_assisted_review_non_target_domain",
            val_fraction=val_fraction,
            seed=seed,
        )
        if row is None:
            skipped.append({"source_case_id": record.get("case_id"), "mask_type": mask_type, "reason": reason})
        else:
            rows.append(row)
    return rows, skipped


def training_row(
    *,
    source_case_id: Any,
    image_path: Any,
    mask_path: Any,
    mask_type: str,
    review_state: Any,
    sample_weight: Any,
    label_source: Any,
    source_video_path: Any,
    frame_index: Any,
    timestamp_sec: Any,
    source_manifest_path: Path,
    source_record_type: Any,
    source_candidate_id: Any,
    source_roi_id: Any,
    quality_status: Any,
    input_domain: Any,
    val_fraction: float,
    seed: int,
) -> tuple[dict[str, Any] | None, str]:
    image = existing_path(image_path)
    mask = existing_path(mask_path)
    if image is None:
        return None, "missing_image_path"
    if mask is None:
        return None, "missing_mask_path"
    width, height = image_size(image)
    sample_id = sample_id_for(source_case_id, mask_type, image, mask)
    return {
        "case_id": sample_id,
        "image_path": str(image),
        "mask_type": mask_type,
        "mask_path": str(mask),
        "review_state": normalize_state(review_state),
        "sample_weight": positive_float(sample_weight, default=sample_weight_for_state(review_state)),
        "label_source": str(label_source or ""),
        "source_video_path": str(source_video_path or ""),
        "frame_index": empty_if_none(frame_index),
        "timestamp_sec": empty_if_none(timestamp_sec),
        "source_manifest_path": str(source_manifest_path),
        "source_record_type": str(source_record_type or ""),
        "source_case_id": str(source_case_id or ""),
        "source_candidate_id": str(source_candidate_id or ""),
        "source_roi_id": str(source_roi_id or ""),
        "quality_status": str(quality_status or ""),
        "width": width,
        "height": height,
        "split": split_for(sample_id, val_fraction=val_fraction, seed=seed),
        "input_domain": str(input_domain or ""),
        "medical_boundary": BOUNDARY_NOTE,
    }, ""


def load_review_payload(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        records: list[dict[str, Any]] = []
        for key, record_type in (("candidates", "candidate_region"), ("rois", "roi")):
            for record in payload.get(key) or []:
                if isinstance(record, dict):
                    records.append({"record_type": record_type, **record})
        return records
    return read_csv_rows(path)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def existing_path(value: Any) -> Path | None:
    if not value:
        return None
    path = resolve_path(str(value))
    return path if path.exists() else None


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return int(image.width), int(image.height)


def sample_id_for(source_case_id: Any, mask_type: str, image_path: Path, mask_path: Path) -> str:
    raw = f"{source_case_id}:{mask_type}:{image_path}:{mask_path}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    safe_source = safe_name(str(source_case_id or image_path.stem))[:56]
    return f"vsm_{safe_source}_{safe_name(mask_type)}_{digest}"


def split_for(sample_id: str, *, val_fraction: float, seed: int) -> str:
    val_fraction = max(0.0, min(0.9, float(val_fraction)))
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    return "val" if bucket < val_fraction else "train"


def sample_weight_for_state(state: Any) -> float:
    normalized = normalize_state(state)
    if normalized in {"accepted", "modified"}:
        return 4.0
    if normalized == "rejected":
        return 0.5
    return 1.0


def positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed >= 0 else float(default)


def normalize_state(value: Any) -> str:
    return str(value or "review_required").split(".")[-1].lower()


def value_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("image_path")), str(row.get("mask_path")), str(row.get("mask_type")))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "sample"


def empty_if_none(value: Any) -> Any:
    return "" if value is None else value


def main() -> int:
    print(json.dumps(build_multimask_manifest(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
