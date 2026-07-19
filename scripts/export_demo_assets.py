from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.paths import ensure_dir
from src.core.warnings import DISCLAIMER_TEXT
from src.utils.runtime import runtime_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/release")
    args = parser.parse_args()
    out = ensure_dir(args.output_dir)
    manifest = {
        "asset_type": "demo_assets_manifest",
        "runtime": runtime_summary(),
        "disclaimer": DISCLAIMER_TEXT,
        "notes": "Fixture framework assets only; no medical data or checkpoints are bundled.",
    }
    path = out / "demo_assets_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
