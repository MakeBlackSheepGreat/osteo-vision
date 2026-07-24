from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.models.three_priority_promotion import (  # noqa: E402
    build_three_priority_promotion_target,
    evaluate_three_priority_model_promotion,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate engineering gates, replay SHA-bound per-case prediction evidence, "
            "and enforce target-domain promotion gates."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--gates",
        type=Path,
        default=Path("configs/training/three_priority_promotion.yml"),
    )
    parser.add_argument("--output", type=Path, help="Write the complete gate and recomputed-metric report as JSON.")
    parser.add_argument("--approval-bundle", type=Path, help="Signed two-role approval bundle exported by the API.")
    parser.add_argument(
        "--approval-trust-store",
        type=Path,
        default=Path("configs/security/promotion_trusted_keys.json"),
        help="Trusted Ed25519 public-key registry used to replay the approval bundle.",
    )
    parser.add_argument(
        "--write-approval-target",
        type=Path,
        help="Write the exact checkpoint, policy, and evidence target for offline reviewer payload preparation.",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    gates = yaml.safe_load(args.gates.read_text(encoding="utf-8")) or {}
    approval_target = build_three_priority_promotion_target(manifest, policy=gates)
    if args.write_approval_target:
        args.write_approval_target.parent.mkdir(parents=True, exist_ok=True)
        args.write_approval_target.write_text(
            json.dumps(approval_target, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    approval_bundle = json.loads(args.approval_bundle.read_text(encoding="utf-8")) if args.approval_bundle else None
    approval_trust_store = json.loads(args.approval_trust_store.read_text(encoding="utf-8"))
    report = evaluate_three_priority_model_promotion(
        manifest,
        policy=gates,
        approval_bundle=approval_bundle,
        approval_trust_store=approval_trust_store,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["target_domain_promotion_ready"] else 2 if report["engineering_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
