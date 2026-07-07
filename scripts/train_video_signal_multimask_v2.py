"""Train a v2 video-signal multi-mask checkpoint without replacing mainline config."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.train_keyframe_segmentation_proxy import train_keyframe_proxy  # noqa: E402
from src.core.paths import ensure_dir, resolve_path  # noqa: E402
from src.reports.writers import write_csv, write_json  # noqa: E402

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/video_signal_multimask_20260707/video_signal_multimask_training_manifest.csv"
)
DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/keyframe_video_signal_multimask_v2.pt"
BOUNDARY_NOTE = (
    "The v2 checkpoint is trained on multi-mask proxy or prompt-assisted review rows. "
    "It must not replace the current MP4/JPEG mainline until smoke tests, model inventory, and medical-boundary "
    "review pass."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", nargs="+", default=[DEFAULT_MANIFEST])
    parser.add_argument("--mask-types", default="fluorescence_hotspot,exposed_bone")
    parser.add_argument("--output-checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report-dir", default="research/reports/modeling")
    parser.add_argument("--report-stamp", default=datetime.now().strftime("%Y%m%d_multimask_v2"))
    parser.add_argument("--image-shape", default="96x128")
    parser.add_argument("--max-train-batches", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--base-channels", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260707)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def train_multimask_v2(args: argparse.Namespace) -> dict[str, Any]:
    mask_types = {item.strip() for item in str(args.mask_types).split(",") if item.strip()}
    rows = load_filtered_rows(args.manifest, mask_types=mask_types)
    if not rows:
        raise ValueError(f"No rows found for mask types {sorted(mask_types)} in {args.manifest}")
    report_dir = ensure_dir(resolve_path(args.report_dir))
    filtered_manifest = report_dir / f"video_signal_multimask_v2_filtered_{args.report_stamp}.csv"
    write_csv(filtered_manifest, rows, sorted({key for row in rows for key in row}))
    proxy_args = argparse.Namespace(
        manifest=[str(filtered_manifest)],
        output_checkpoint=args.output_checkpoint,
        report_dir=args.report_dir,
        report_stamp=args.report_stamp,
        model_id="convnext2d_video_signal_multimask_v2",
        runtime_allowed=False,
        image_shape=args.image_shape,
        synthetic_train_size=24,
        synthetic_val_size=6,
        max_train_batches=args.max_train_batches,
        batch_size=args.batch_size,
        base_channels=args.base_channels,
        learning_rate=args.learning_rate,
        threshold=args.threshold,
        seed=args.seed,
        device=args.device,
    )
    result = train_keyframe_proxy(proxy_args)
    summary = {
        "schema_version": "osteo-vision-video-signal-multimask-v2-training-summary",
        "filtered_manifest_path": str(filtered_manifest),
        "source_manifests": [str(resolve_path(item)) for item in args.manifest],
        "trained_mask_types": sorted(mask_types),
        "sample_count": len(rows),
        "mask_type_counts": value_counts(rows, "mask_type"),
        "review_state_counts": value_counts(rows, "review_state"),
        "checkpoint_path": result["checkpoint_path"],
        "metrics": result["metrics"],
        "runtime_allowed": False,
        "medical_boundary": BOUNDARY_NOTE,
    }
    summary_path = report_dir / f"video_signal_multimask_v2_training_{args.report_stamp}.json"
    write_json(summary_path, summary)
    return {**result, "v2_summary_path": str(summary_path), "v2_summary": summary}


def load_filtered_rows(paths: list[str], *, mask_types: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for manifest in paths:
        path = resolve_path(manifest)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("mask_type") or "") not in mask_types:
                    continue
                if not row.get("image_path") or not row.get("mask_path"):
                    continue
                rows.append({key: str(value) for key, value in row.items()})
    return rows


def value_counts(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def main() -> int:
    print(json.dumps(train_multimask_v2(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
