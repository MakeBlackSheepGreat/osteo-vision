from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from osteo_vision_core.core.warnings import DISCLAIMER_TEXT, STATUS_COMPLETED


@dataclass
class InputSummary:
    path: str
    input_type: str
    accepted: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskPackage:
    task_id: str
    task_name: str
    modality: str
    input_contract: dict[str, Any] = field(default_factory=dict)
    label_contract: dict[str, Any] = field(default_factory=dict)
    pipelines: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    demo_outputs: list[str] = field(default_factory=list)
    benchmark_contract: dict[str, Any] = field(default_factory=dict)
    recommended_models: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelSpec:
    model_id: str
    family: str = "fixture"
    task_types: list[str] = field(default_factory=lambda: ["classification"])
    input_types: list[str] = field(default_factory=lambda: ["2d_image", "npz_roi"])
    spatial_dims: list[int] = field(default_factory=lambda: [2])
    checkpoint_path: str | None = None
    bundle_path: str | None = None
    source_url: str | None = None
    license: str | None = None
    dependency_group: str = "core"
    device_policy: str = "auto"
    precision: str = "fp32"
    enabled: bool = True
    intended_use: str = "research_platform_validation"
    clinical_claim_allowed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdapterStatus:
    model_id: str
    family: str
    available: bool
    enabled: bool = True
    reasons: list[str] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdapterRequest:
    case_id: str
    input_path: str
    input_type: str
    task_type: str
    modality: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdapterResult:
    model_id: str
    model_family: str
    prediction: dict[str, Any] = field(default_factory=dict)
    probability: float | None = None
    score: float | None = None
    class_label: str | None = None
    risk_level: str | None = None
    segmentation_mask: dict[str, Any] = field(default_factory=dict)
    lesion_evidence: dict[str, Any] = field(default_factory=dict)
    quantification: dict[str, Any] = field(default_factory=dict)
    explanation_evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictionResult:
    status: str = STATUS_COMPLETED
    case_id: str | None = None
    input_type: str = "unknown"
    task_type: str = "classification"
    model_version: str = "micf-fixture-v0"
    prediction: dict[str, Any] = field(default_factory=dict)
    probability: float | None = None
    score: float | None = None
    class_label: str | None = None
    risk_level: str | None = None
    segmentation_mask: dict[str, Any] = field(default_factory=dict)
    lesion_evidence: dict[str, Any] = field(default_factory=dict)
    quantification: dict[str, Any] = field(default_factory=dict)
    explanation_evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)
    resource_summary: dict[str, Any] = field(default_factory=dict)
    disclaimer_shown: bool = True
    report_path: str | None = None
    input_filename: str | None = None
    preprocessing_summary: dict[str, Any] = field(default_factory=dict)
    threshold: float | None = None
    disclaimer: str = DISCLAIMER_TEXT
    model_id: str | None = None
    model_family: str | None = None
    model_provenance: dict[str, Any] = field(default_factory=dict)
    adapter_status: dict[str, Any] = field(default_factory=dict)
    adapter_warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkReport:
    run_id: str
    config_path: str
    manifest_path: str
    output_dir: str
    model_version: str
    prediction_csv: str
    metrics_path: str
    metrics: dict[str, Any] = field(default_factory=dict)
    failure_summary: dict[str, Any] = field(default_factory=dict)
    threshold_analysis_path: str | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentSpec:
    experiment_id: str
    task_package: str
    manifest_path: str
    model_spec: dict[str, Any]
    split_strategy: dict[str, Any] = field(default_factory=lambda: {"type": "fixed"})
    training_config: dict[str, Any] = field(default_factory=dict)
    evaluation_config: dict[str, Any] = field(default_factory=dict)
    threshold_strategy: dict[str, Any] = field(default_factory=lambda: {"type": "fixed", "threshold": 0.5})
    promotion_gate: dict[str, Any] = field(default_factory=dict)
    output_dir: str = "artifacts/runs"
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingRun:
    run_id: str
    experiment_id: str
    task_package: str
    manifest_path: str
    model_spec: dict[str, Any]
    split_strategy: dict[str, Any]
    training_config: dict[str, Any]
    output_checkpoint: str | None = None
    fold_reports: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationRun:
    run_id: str
    experiment_id: str
    evaluation_config: dict[str, Any]
    threshold_strategy: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    threshold_analysis: dict[str, Any] = field(default_factory=dict)
    failure_summary: dict[str, Any] = field(default_factory=dict)
    evidence_paths: list[str] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelCard:
    model_id: str
    model_family: str
    intended_use: str
    task_package: str
    training_data: dict[str, Any]
    metrics: dict[str, Any]
    limitations: list[str] = field(default_factory=list)
    clinical_claim_allowed: bool = False
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckpointManifest:
    checkpoint_path: str
    checkpoint_hash: str
    source_run_id: str
    model_id: str
    task_package: str
    metrics: dict[str, Any]
    runtime_allowed: bool = False
    clinical_claim_allowed: bool = False
    warnings: list[dict[str, Any]] = field(default_factory=list)
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionRecord:
    run_id: str
    experiment_id: str
    model_id: str
    promoted: bool
    gate: dict[str, Any]
    reasons: list[str] = field(default_factory=list)
    runtime_patch: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    clinical_claim_allowed: bool = False
    disclaimer: str = DISCLAIMER_TEXT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_to_case_id(path: str | Path) -> str:
    stem = Path(path).stem or "case"
    return stem.replace(" ", "_")
