from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.config import load_yaml
from src.core.schemas import TaskPackage

REQUIRED_TASK_PACKAGE_FIELDS = {
    "task_id",
    "task_name",
    "modality",
    "input_contract",
    "label_contract",
    "pipelines",
    "metrics",
    "demo_outputs",
    "benchmark_contract",
    "recommended_models",
    "safety",
}


def task_package_from_mapping(mapping: dict[str, Any], *, source_path: str | None = None) -> TaskPackage:
    missing = sorted(REQUIRED_TASK_PACKAGE_FIELDS - set(mapping))
    if missing:
        raise ValueError(f"Task package missing required fields: {missing}")
    return TaskPackage(
        task_id=str(mapping["task_id"]),
        task_name=str(mapping["task_name"]),
        modality=str(mapping["modality"]),
        input_contract=dict(mapping.get("input_contract") or {}),
        label_contract=dict(mapping.get("label_contract") or {}),
        pipelines=list(mapping.get("pipelines") or []),
        metrics=list(mapping.get("metrics") or []),
        demo_outputs=list(mapping.get("demo_outputs") or []),
        benchmark_contract=dict(mapping.get("benchmark_contract") or {}),
        recommended_models=list(mapping.get("recommended_models") or []),
        safety=dict(mapping.get("safety") or {}),
        source_path=source_path,
    )


def load_task_package(path: str | Path) -> TaskPackage:
    data = load_yaml(path)
    source = data.pop("_config_path", str(path))
    data.pop("_project_root", None)
    return task_package_from_mapping(data, source_path=source)


def default_task_package() -> TaskPackage:
    return TaskPackage(
        task_id="default_fixture_task",
        task_name="Default Fixture Task",
        modality="generic",
        input_contract={
            "input_types": ["2d_image", "video_file", "video_stream", "npz_roi", "dicom_series", "nifti_volume"]
        },
        label_contract={"type": "binary_or_missing"},
        pipelines=["classification", "segmentation", "detection", "quantification", "multitask"],
        metrics=["accuracy", "sensitivity", "specificity", "precision", "f1", "dice", "iou"],
        demo_outputs=["prediction", "warnings", "report_path"],
        benchmark_contract={"manifest_version": "v1_v2_compatible"},
        recommended_models=[{"model_id": "fixture_default", "family": "fixture"}],
        safety={"disclaimer_required": True, "clinical_claim_allowed": False},
    )
