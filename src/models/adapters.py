from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol

from src.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec
from src.core.warnings import STATUS_CHECKPOINT_MISSING, warning
from src.models.classifier import DeterministicClassifier

DEPENDENCY_MODULES = {
    "core": [],
    "fixture": [],
    "timm": ["timm"],
    "monai": ["monai"],
    "nnunet": ["nnunetv2"],
    "sam": ["torch"],
    "vlm": ["open_clip"],
}


class ModelAdapter(Protocol):
    def describe(self) -> ModelSpec: ...

    def supports(self, task_type: str, input_type: str, modality: str) -> bool: ...

    def warmup(self) -> AdapterStatus: ...

    def predict(self, request: AdapterRequest) -> AdapterResult: ...


class BaseModelAdapter:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    def describe(self) -> ModelSpec:
        return self.spec

    def supports(self, task_type: str, input_type: str, modality: str) -> bool:
        task_ok = "*" in self.spec.task_types or task_type in self.spec.task_types
        input_ok = "*" in self.spec.input_types or input_type in self.spec.input_types
        modality_ok = not self.spec.extra.get("modalities") or modality in self.spec.extra.get("modalities", [])
        return task_ok and input_ok and modality_ok

    def warmup(self) -> AdapterStatus:
        reasons: list[str] = []
        warnings: list[dict[str, Any]] = []
        if not self.spec.enabled:
            reasons.append("model disabled")
        for module in DEPENDENCY_MODULES.get(self.spec.dependency_group, []):
            if importlib.util.find_spec(module) is None:
                reasons.append(f"missing dependency: {module}")
        if self.spec.checkpoint_path and not Path(self.spec.checkpoint_path).exists():
            reasons.append(f"missing checkpoint: {self.spec.checkpoint_path}")
            warnings.append(warning(STATUS_CHECKPOINT_MISSING, f"Missing checkpoint for {self.spec.model_id}"))
        if self.spec.bundle_path and not Path(self.spec.bundle_path).exists():
            reasons.append(f"missing bundle: {self.spec.bundle_path}")
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=not reasons,
            enabled=self.spec.enabled,
            reasons=reasons,
            warnings=warnings,
        )

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        unavailable_warning = warning(
            "model_unavailable",
            f"Model {self.spec.model_id} is unavailable: {'; '.join(status.reasons)}",
            True,
        )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction={"available": False, "reason": "; ".join(status.reasons)},
            warnings=status.warnings + [unavailable_warning],
        )


class FixtureAdapter(BaseModelAdapter):
    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self.classifier = DeterministicClassifier()

    def warmup(self) -> AdapterStatus:
        return AdapterStatus(model_id=self.spec.model_id, family=self.spec.family, available=self.spec.enabled, enabled=self.spec.enabled)

    def predict(self, request: AdapterRequest) -> AdapterResult:
        probability = self.classifier.predict_probability(request.input_path, request.metadata)
        label = self.classifier.class_label(probability)
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction={"label": label, "probability": probability, "adapter": "fixture"},
            probability=probability,
            score=probability,
            class_label=label,
            risk_level=_risk_level(probability),
            explanation_evidence={"type": "fixture_attention", "available": False},
        )


class TimmClassifierAdapter(BaseModelAdapter):
    pass


class MonaiBundleAdapter(BaseModelAdapter):
    pass


class NnUNetV2Adapter(BaseModelAdapter):
    pass


class MedSAMLikeAdapter(BaseModelAdapter):
    pass


class Vista3DLikeAdapter(BaseModelAdapter):
    pass


class VLMEncoderAdapter(BaseModelAdapter):
    pass


ADAPTER_CLASSES = {
    "fixture": FixtureAdapter,
    "timm_classifier": TimmClassifierAdapter,
    "monai_bundle": MonaiBundleAdapter,
    "nnunet_v2": NnUNetV2Adapter,
    "medsam_like": MedSAMLikeAdapter,
    "vista3d_like": Vista3DLikeAdapter,
    "vlm_encoder": VLMEncoderAdapter,
}


def model_spec_from_mapping(mapping: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        model_id=str(mapping["model_id"]),
        family=str(mapping.get("family", "fixture")),
        task_types=list(mapping.get("task_types") or ["classification"]),
        input_types=list(mapping.get("input_types") or ["2d_image", "npz_roi"]),
        spatial_dims=[int(item) for item in (mapping.get("spatial_dims") or [2])],
        checkpoint_path=mapping.get("checkpoint_path"),
        bundle_path=mapping.get("bundle_path"),
        source_url=mapping.get("source_url"),
        license=mapping.get("license"),
        dependency_group=str(mapping.get("dependency_group", mapping.get("family", "core"))),
        device_policy=str(mapping.get("device_policy", "auto")),
        precision=str(mapping.get("precision", "fp32")),
        enabled=bool(mapping.get("enabled", True)),
        intended_use=str(mapping.get("intended_use", "research_competition_prototype")),
        clinical_claim_allowed=bool(mapping.get("clinical_claim_allowed", False)),
        extra=dict(mapping.get("extra") or {}),
    )


def build_adapter(spec: ModelSpec) -> BaseModelAdapter:
    adapter_cls = ADAPTER_CLASSES.get(spec.family, BaseModelAdapter)
    return adapter_cls(spec)


def build_adapters(runtime: dict[str, Any]) -> list[BaseModelAdapter]:
    specs = runtime.get("models") or [{"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]}]
    return [build_adapter(model_spec_from_mapping(spec)) for spec in specs]


def inventory_from_adapters(adapters: list[BaseModelAdapter]) -> list[dict[str, Any]]:
    rows = []
    for adapter in adapters:
        spec = adapter.describe()
        status = adapter.warmup()
        rows.append({"spec": spec.to_dict(), "status": status.to_dict()})
    return rows


def select_adapter(
    adapters: list[BaseModelAdapter],
    *,
    task_type: str,
    input_type: str,
    modality: str,
    policy: str = "fixture_fallback",
    explicit_model_id: str | None = None,
) -> tuple[BaseModelAdapter | None, list[AdapterStatus]]:
    statuses: list[AdapterStatus] = []
    candidates = [adapter for adapter in adapters if not explicit_model_id or adapter.describe().model_id == explicit_model_id]
    for adapter in candidates:
        if not adapter.supports(task_type, input_type, modality):
            continue
        status = adapter.warmup()
        statuses.append(status)
        if status.available:
            return adapter, statuses
        if policy == "explicit":
            return adapter, statuses
    if policy == "fixture_fallback":
        for adapter in adapters:
            if adapter.describe().family != "fixture":
                continue
            status = adapter.warmup()
            statuses.append(status)
            if status.available and adapter.supports(task_type, input_type, modality):
                return adapter, statuses
    return None, statuses


def _risk_level(probability: float) -> str:
    if probability >= 0.66:
        return "high"
    if probability >= 0.33:
        return "medium"
    return "low"
