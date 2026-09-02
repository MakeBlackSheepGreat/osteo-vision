from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.models.runtime_promotion import (  # noqa: E402
    build_keyframe_runtime_promotion,
    write_runtime_promotion_sidecar,
)

DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy_grouped_20260710.pt"
DEFAULT_TRAINING_SIDECAR = "artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy_grouped_20260710_manifest.json"
DEFAULT_VAL_EVAL = "research/reports/modeling/keyframe_threshold_eval_20260710_grouped_val/keyframe_threshold_eval.json"
DEFAULT_TEST_EVAL = (
    "research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/keyframe_threshold_eval.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote a keyframe checkpoint for platform runtime after auditable validation gates."
    )
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--training-sidecar", default=DEFAULT_TRAINING_SIDECAR)
    parser.add_argument("--val-eval", default=DEFAULT_VAL_EVAL)
    parser.add_argument("--test-eval", default=DEFAULT_TEST_EVAL)
    parser.add_argument("--output-sidecar")
    parser.add_argument("--max-empty-mask-rate", type=float, default=0.05)
    parser.add_argument("--max-over-segmentation-rate", type=float, default=0.05)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checkpoint = Path(args.checkpoint).resolve()
    output = (
        Path(args.output_sidecar).resolve()
        if args.output_sidecar
        else checkpoint.with_name(f"{checkpoint.stem}_runtime_promotion.json")
    )
    report = build_keyframe_runtime_promotion(
        checkpoint_path=checkpoint,
        training_sidecar_path=args.training_sidecar,
        val_eval_path=args.val_eval,
        test_eval_path=args.test_eval,
        max_empty_mask_rate=args.max_empty_mask_rate,
        max_over_segmentation_rate=args.max_over_segmentation_rate,
    )
    if report["passed"]:
        destination = write_runtime_promotion_sidecar(output, report)
        result = {
            "passed": True,
            "output_sidecar": str(destination),
            "checkpoint_sha256": report["checkpoint_sha256"],
            "threshold": report["promotion_sidecar"]["threshold"],
            "errors": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
