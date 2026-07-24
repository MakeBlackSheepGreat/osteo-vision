from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from osteo_vision_core.core.paths import resolve_path
from osteo_vision_core.core.schemas import ExperimentSpec

REQUIRED_EXPERIMENT_FIELDS = {
    "experiment_id",
    "task_package",
    "manifest_path",
    "model_spec",
    "split_strategy",
    "training_config",
    "evaluation_config",
    "threshold_strategy",
    "promotion_gate",
}


def experiment_spec_from_mapping(mapping: dict[str, Any], *, source_path: str | None = None) -> ExperimentSpec:
    missing = sorted(REQUIRED_EXPERIMENT_FIELDS - set(mapping))
    if missing:
        raise ValueError(f"Experiment spec missing required fields: {missing}")
    return ExperimentSpec(
        experiment_id=str(mapping["experiment_id"]),
        task_package=str(mapping["task_package"]),
        manifest_path=str(mapping["manifest_path"]),
        model_spec=dict(mapping.get("model_spec") or {}),
        split_strategy=dict(mapping.get("split_strategy") or {"type": "fixed"}),
        training_config=dict(mapping.get("training_config") or {}),
        evaluation_config=dict(mapping.get("evaluation_config") or {}),
        threshold_strategy=dict(mapping.get("threshold_strategy") or {"type": "fixed", "threshold": 0.5}),
        promotion_gate=dict(mapping.get("promotion_gate") or {}),
        output_dir=str(mapping.get("output_dir") or "artifacts/runs"),
        source_path=source_path,
    )


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    p = resolve_path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Experiment spec must contain a mapping: {p}")
    return experiment_spec_from_mapping(data, source_path=str(p))


def write_experiment_spec(spec: ExperimentSpec, path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = spec.to_dict()
    payload.pop("source_path", None)
    p.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(p)
