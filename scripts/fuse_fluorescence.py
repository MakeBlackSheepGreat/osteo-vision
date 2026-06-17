from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocess.fluorescence import fuse_white_light_fluorescence


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a basic white-light/fluorescence pseudo-color overlay.")
    parser.add_argument("--white-light", required=True, help="White-light image path.")
    parser.add_argument("--fluorescence", required=True, help="Fluorescence image path.")
    parser.add_argument("--output-dir", default="artifacts/visual_evidence/osteo_vision/fusion")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--alpha", type=float, default=0.45)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--colormap", choices=["green", "amber", "magenta"], default="green")
    args = parser.parse_args()

    report = fuse_white_light_fluorescence(
        args.white_light,
        args.fluorescence,
        args.output_dir,
        case_id=args.case_id,
        alpha=args.alpha,
        threshold=args.threshold,
        colormap=args.colormap,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
