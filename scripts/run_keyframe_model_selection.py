"""Run a configuration-bound keyframe segmentation comparison with locked testing."""

from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_keyframe_segmentation_proxy import evaluate_keyframe_thresholds
from scripts.train_keyframe_segmentation_proxy import train_keyframe_proxy
from tools.build_keyframe_model_selection_summary import build_summary, write_outputs


def run_selection(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config).resolve()
    config = _load_config(config_path)
    protocol = _mapping(config, "protocol")
    root = Path(args.selection_root or config_path.with_suffix("")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for entry in [_mapping(config, "baseline"), *_sequence_of_mappings(config, "candidates")]:
        for seed in _seeds(entry, fallback=int(protocol["seed"])):
            runs.append(_run_model(entry, seed=seed, protocol=protocol, root=root))

    summary = build_summary(
        root,
        baseline_model_id=str(_mapping(config, "baseline")["model_id"]),
        minimum_seeds=int(args.minimum_seeds),
    )
    outputs = write_outputs(summary, root, str(args.output_stem or f"{config_path.stem}_summary"))
    result = {
        "config_path": str(config_path),
        "selection_root": str(root),
        "runs": runs,
        "summary": {key: str(value) for key, value in outputs.items()},
        "recommendation": summary["recommendation"],
    }
    (root / "selection_execution.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _run_model(entry: dict[str, Any], *, seed: int, protocol: dict[str, Any], root: Path) -> dict[str, Any]:
    model_id = f"{entry['model_id']}_{seed}" if len(_seeds(entry, fallback=seed)) > 1 else str(entry["model_id"])
    checkpoint_path = Path(str(entry["checkpoint"])).with_name(f"{Path(str(entry['checkpoint'])).stem}_{seed}.pt")
    training = train_keyframe_proxy(
        Namespace(
            manifest=[str(protocol["evaluation_manifest"])],
            registry="",
            quality_report="",
            admission_stage="proxy_pretrain",
            output_checkpoint=str(checkpoint_path),
            resume_checkpoint="",
            pretrained_checkpoint="",
            restore_optimizer=False,
            freeze_encoder=False,
            report_dir=str(root / "training_reports"),
            report_stamp=model_id,
            model_id=model_id,
            runtime_allowed=False,
            image_shape="x".join(str(value) for value in protocol["image_shape"]),
            synthetic_train_size=24,
            synthetic_val_size=6,
            max_train_batches=int(protocol["train_batches"]),
            batch_size=int(protocol["batch_size"]),
            architecture=str(entry["architecture"]),
            base_channels=int(entry["base_channels"]),
            learning_rate=float(protocol["learning_rate"]),
            threshold=0.5,
            domain_aware=True,
            domain_adaptation_config=str(protocol["domain_adaptation_config"]),
            seed=seed,
            device=str(protocol["device"]),
        )
    )
    threshold_text = ",".join(str(value) for value in protocol["threshold_scan"])
    common = {
        "checkpoint": str(training["checkpoint_path"]),
        "manifest": [str(protocol["evaluation_manifest"])],
        "thresholds": threshold_text,
        "image_shape": "x".join(str(value) for value in protocol["image_shape"]),
        "max_samples": 0,
        "over_segmentation_fraction": float(protocol["over_segmentation_fraction"]),
        "max_empty_mask_rate": float(protocol["max_empty_mask_rate"]),
        "max_over_segmentation_rate": float(protocol["max_over_segmentation_rate"]),
        "device": str(protocol["device"]),
    }
    val = evaluate_keyframe_thresholds(
        Namespace(**common, output_dir=str(root / f"{model_id}_val"), split="val", fixed_threshold=None)
    )
    threshold = float(val["recommendation"]["threshold"])
    test = evaluate_keyframe_thresholds(
        Namespace(
            **common,
            output_dir=str(root / f"{model_id}_test"),
            split="test",
            fixed_threshold=threshold,
        )
    )
    return {
        "model_id": model_id,
        "architecture": entry["architecture"],
        "seed": seed,
        "checkpoint_path": training["checkpoint_path"],
        "validation_threshold": threshold,
        "validation_report": val["outputs"]["json"],
        "test_report": test["outputs"]["json"],
    }


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping configuration: {path}")
    return payload


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing mapping {key!r} in selection configuration.")
    return value


def _sequence_of_mappings(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Missing mapping list {key!r} in selection configuration.")
    return value


def _seeds(entry: dict[str, Any], *, fallback: int) -> list[int]:
    values = entry.get("seeds", [fallback])
    if not isinstance(values, list) or not values:
        raise ValueError(f"Invalid seeds for {entry.get('model_id')!r}")
    return [int(value) for value in values]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and compare keyframe segmentation candidates.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--selection-root", default="")
    parser.add_argument("--output-stem", default="")
    parser.add_argument("--minimum-seeds", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run_selection(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
