"""Build a high-value video keyframe review queue and training patch."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.osteo_vision_api.services.active_review_queue import (  # noqa: E402
    REVIEW_QUEUE_FIELDS,
    TRAINING_PATCH_FIELDS,
    ActiveReviewConfig,
    build_active_review_queue,
    build_training_manifest_patch,
    load_review_updates,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flattened = dict(row)
            for key, value in flattened.items():
                if isinstance(value, (list, dict)):
                    flattened[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            writer.writerow(flattened)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an active-review queue from video analysis manifests.")
    parser.add_argument("--input", nargs="+", required=True, help="frame_details or video_segmentation JSON paths")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--review-updates", help="Optional reviewed queue JSON/CSV containing review_id decisions")
    parser.add_argument("--max-frames", type=int, default=40)
    parser.add_argument("--max-frames-per-source", type=int, default=12)
    parser.add_argument("--min-interval-sec", type=float, default=2.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    updates = load_review_updates(args.review_updates) if args.review_updates else []
    config = ActiveReviewConfig(
        max_frames=max(0, args.max_frames),
        max_frames_per_source=max(1, args.max_frames_per_source),
        min_interval_sec=max(0.0, args.min_interval_sec),
    )
    queue = build_active_review_queue(args.input, config=config, review_updates=updates)
    queue_json_path = output_dir / "video_active_review_queue.json"
    queue_csv_path = output_dir / "video_active_review_queue.csv"
    patch_json_path = output_dir / "video_active_review_training_patch.json"
    patch_csv_path = output_dir / "video_active_review_training_patch.csv"
    patch = build_training_manifest_patch(queue, source_review_queue_path=queue_json_path)
    write_json(queue_json_path, queue)
    write_csv(queue_csv_path, list(queue["rows"]), REVIEW_QUEUE_FIELDS)
    write_json(patch_json_path, patch)
    write_csv(patch_csv_path, list(patch["rows"]), TRAINING_PATCH_FIELDS)
    result = {
        "queue_json_path": str(queue_json_path),
        "queue_csv_path": str(queue_csv_path),
        "training_patch_json_path": str(patch_json_path),
        "training_patch_csv_path": str(patch_csv_path),
        "selected_count": queue["summary"]["selected_count"],
        "training_patch_row_count": patch["summary"]["patch_row_count"],
        "medical_boundary": queue["medical_boundary"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
