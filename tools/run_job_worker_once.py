from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.osteo_vision_api.core.settings import load_settings
from backend.osteo_vision_api.services.job_worker import LocalJobWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drain queued osteo-vision platform jobs once.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum queued jobs to process.")
    parser.add_argument(
        "--kind",
        action="append",
        choices=["case_analysis", "upload_keyframe_extraction", "cbct_surface_modeling"],
        help="Restrict processing to one job kind. Can be repeated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    worker = LocalJobWorker(load_settings())
    result = worker.run_once(limit=args.limit, kinds=args.kind)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
