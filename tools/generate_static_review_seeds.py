from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.osteo_vision_api.services.static_dataset_review import (  # noqa: E402
    StaticDatasetReviewError,
    StaticDatasetReviewService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate review-required heuristic masks for unseeded D047/D048 crops."
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--colormap", choices=("amber", "green", "magenta"), default="green")
    parser.add_argument("--dataset-id", action="append", choices=("d047", "d048"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=ROOT / "artifacts/data_review/static_seed_batch_latest.json",
    )
    return parser.parse_args()


def generate_seed_batch(
    service: StaticDatasetReviewService,
    *,
    threshold: float,
    colormap: str,
    dataset_ids: set[str] | None = None,
    limit: int = 0,
    force: bool = False,
) -> dict[str, Any]:
    queue = service.list_queue()
    selected = []
    skipped = []
    for item in queue["items"]:
        if dataset_ids and str(item["dataset_id"]) not in dataset_ids:
            continue
        if item.get("record_kind") == "human_review":
            skipped.append({"record_id": item["record_id"], "reason": "human_review_exists"})
            continue
        if item.get("record_kind") == "automated_seed" and not force:
            skipped.append({"record_id": item["record_id"], "reason": "seed_already_exists"})
            continue
        selected.append(item)
    if limit > 0:
        selected = selected[:limit]

    generated = []
    failed = []
    for item in selected:
        record_id = str(item["record_id"])
        try:
            result = service.generate_seed(
                record_id,
                threshold=threshold,
                colormap=colormap,
            )
        except (OSError, StaticDatasetReviewError) as exc:
            failed.append(
                {
                    "record_id": record_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        generated.append(
            {
                "record_id": record_id,
                "dataset_id": result["dataset_id"],
                "mask_path": result["mask_path"],
                "positive_area_fraction": result["positive_area_fraction"],
                "quality_status": result["quality_status"],
                "quality_warnings": result["quality_warnings"],
                "review_state": result["review_state"],
                "training_eligible": result["training_eligible"],
            }
        )

    refreshed = service.list_queue()
    return {
        "schema_version": "osteo-vision-static-seed-batch-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "threshold": float(threshold),
        "colormap": colormap,
        "selected_count": len(selected),
        "generated_count": len(generated),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "queue_record_count": refreshed["record_count"],
        "queue_seed_count": refreshed["seed_count"],
        "queue_reviewed_count": refreshed["reviewed_count"],
        "queue_training_eligible_count": refreshed["training_eligible_count"],
        "seed_manifest_path": str(service.seed_manifest_path),
        "reviewed_manifest_path": str(service.reviewed_manifest_path),
        "generated": generated,
        "failed": failed,
        "skipped": skipped,
        "medical_boundary": refreshed["medical_boundary"],
    }


def main() -> int:
    args = parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    service = StaticDatasetReviewService(args.project_root)
    summary = generate_seed_batch(
        service,
        threshold=args.threshold,
        colormap=args.colormap,
        dataset_ids=set(args.dataset_id or []) or None,
        limit=args.limit,
        force=args.force,
    )
    summary_path = args.summary_path.resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
