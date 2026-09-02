from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osteo_vision_core.core.schemas import ExperimentSpec
from osteo_vision_core.experiments.spec import write_experiment_spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", default="medical_demo_fixture")
    parser.add_argument("--task-package", default="configs/tasks/osteo_vision.yml")
    parser.add_argument("--manifest", default="tests/fixtures/benchmark_manifest_v2.csv")
    parser.add_argument("--model-id", default="fixture_default")
    parser.add_argument("--model-family", default="fixture")
    parser.add_argument("--output-dir", default="artifacts/experiments")
    parser.add_argument("--run-output-dir", default="artifacts/runs")
    parser.add_argument("--split-strategy", choices=["fixed", "kfold", "external"], default="fixed")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--threshold-strategy", choices=["fixed", "youden", "sensitivity_first"], default="fixed")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--min-sensitivity", type=float, default=0.85)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    spec = build_experiment_spec(args)
    output_path = Path(args.output_dir) / spec.experiment_id / "experiment.yml"
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing experiment spec: {output_path}")
    path = write_experiment_spec(spec, output_path)
    print(json.dumps({"experiment_spec": path, "experiment_id": spec.experiment_id}, ensure_ascii=False, indent=2))
    return 0


def build_experiment_spec(args: argparse.Namespace) -> ExperimentSpec:
    split_strategy = _split_strategy(args)
    threshold_strategy = _threshold_strategy(args)
    model_spec = {
        "model_id": args.model_id,
        "family": args.model_family,
        "task_types": ["*"],
        "input_types": ["*"],
        "spatial_dims": [2, 3],
        "dependency_group": "fixture" if args.model_family == "fixture" else args.model_family,
        "device_policy": "cpu" if args.model_family == "fixture" else "auto",
        "precision": "deterministic" if args.model_family == "fixture" else "fp32",
        "enabled": True,
        "intended_use": "research_platform_platform_validation",
        "clinical_claim_allowed": False,
    }
    return ExperimentSpec(
        experiment_id=_slug(args.experiment_id),
        task_package=args.task_package,
        manifest_path=args.manifest,
        model_spec=model_spec,
        split_strategy=split_strategy,
        training_config={"mode": "fixture", "epochs": 0, "real_training": False},
        evaluation_config={"mode": "fixture_oof", "primary_metric": "accuracy"},
        threshold_strategy=threshold_strategy,
        promotion_gate={"require_no_leakage": True, "require_patient_id": True, "minimum_metrics": {"accuracy": 0.0}},
        output_dir=args.run_output_dir,
    )


def _split_strategy(args: argparse.Namespace) -> dict[str, object]:
    if args.split_strategy == "kfold":
        return {"type": "kfold", "folds": max(2, int(args.folds)), "group_column": "patient_id"}
    if args.split_strategy == "external":
        return {"type": "external", "external_split": "external"}
    return {"type": "fixed", "split_column": "split", "default_split": "validation"}


def _threshold_strategy(args: argparse.Namespace) -> dict[str, object]:
    if args.threshold_strategy == "youden":
        return {"type": "youden"}
    if args.threshold_strategy == "sensitivity_first":
        return {"type": "sensitivity_first", "min_sensitivity": args.min_sensitivity}
    return {"type": "fixed", "threshold": args.threshold}


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip().lower())
    return slug.strip("_") or "experiment"


if __name__ == "__main__":
    raise SystemExit(main())
