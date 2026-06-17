from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.training import write_training_template_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/reports")
    args = parser.parse_args()
    report = write_training_template_report("segmenter", args.output_dir)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

