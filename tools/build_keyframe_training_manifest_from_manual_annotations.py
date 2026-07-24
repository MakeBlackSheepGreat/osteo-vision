"""Build an auditable keyframe fine-tuning manifest from physician annotations."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osteo_vision_core.core.paths import ensure_dir, resolve_path  # noqa: E402
from osteo_vision_core.datasets.training_admission import (  # noqa: E402
    MANUAL_ANNOTATION_TRAINING_FIELDS,
    admit_manual_annotation_training_rows,
)


def build_manual_annotation_training_manifest(args: argparse.Namespace) -> dict[str, Any]:
    source_manifest = resolve_path(args.input)
    output_dir = ensure_dir(resolve_path(args.output_dir))
    output_path = output_dir / str(args.manifest_name)
    summary_path = output_dir / "manual_annotation_training_admission_summary.json"
    result = admit_manual_annotation_training_rows(
        source_manifest,
        verify_checksums=True,
        validation_fraction=float(args.val_fraction),
        split_seed=int(args.seed),
        target_mask_type=str(getattr(args, "target_mask_type", "lesion")),
        target_task=getattr(args, "target_task", None),
    )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_ANNOTATION_TRAINING_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: _csv_value(row.get(field)) for field in MANUAL_ANNOTATION_TRAINING_FIELDS} for row in result.rows
        )

    payload = {
        **result.summary,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(output_path),
        "summary_path": str(summary_path),
        "sample_count": len(result.rows),
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Admit trusted physician manual annotations into a keyframe fine-tuning manifest."
    )
    parser.add_argument("--input", required=True, help="Manual annotation training manifest JSON.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--manifest-name",
        default="keyframe_training_manifest_from_manual_annotations.csv",
    )
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--target-mask-type", default="lesion")
    parser.add_argument(
        "--target-task",
        default=None,
        help="Training task recorded in the output; defaults to the selected mask type's task.",
    )
    return parser.parse_args()


def main() -> int:
    result = build_manual_annotation_training_manifest(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
