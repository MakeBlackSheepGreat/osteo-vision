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
    "torch": ["torch"],
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
    implements_inference = False

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
        if not self.implements_inference:
            reasons.append("adapter inference not implemented")
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
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self.classifier = DeterministicClassifier()

    def warmup(self) -> AdapterStatus:
        return AdapterStatus(
            model_id=self.spec.model_id, family=self.spec.family, available=self.spec.enabled, enabled=self.spec.enabled
        )

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
    implements_inference = True

    def warmup(self) -> AdapterStatus:
        if self.spec.extra.get("prompt_fallback_enabled"):
            warnings: list[dict[str, Any]] = []
            if self.spec.checkpoint_path and not Path(self.spec.checkpoint_path).exists():
                warnings.append(
                    warning(
                        "medsam_checkpoint_missing_prompt_fallback",
                        (
                            f"Missing checkpoint for {self.spec.model_id}; using deterministic prompt-contract "
                            "fallback instead of real MedSAM/SAM2 inference."
                        ),
                    )
                )
            return AdapterStatus(
                model_id=self.spec.model_id,
                family=self.spec.family,
                available=self.spec.enabled,
                enabled=self.spec.enabled,
                warnings=warnings,
            )
        return super().warmup()

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        if request.input_type != "2d_image":
            unsupported_warning = warning(
                "unsupported_input_for_medsam_prompt_fallback",
                f"Model {self.spec.model_id} currently supports only 2d_image prompt fallback inputs.",
                True,
            )
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "unsupported input for MedSAM-like prompt fallback"},
                warnings=status.warnings + [unsupported_warning],
            )
        from src.core.paths import resolve_path
        from src.models.prompt_segmenter import segment_2d_prompt_mask

        payload = segment_2d_prompt_mask(
            request.input_path,
            output_dir=resolve_path(
                self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/prompt_masks")
            ),
            case_id=request.case_id,
            model_id=self.spec.model_id,
            prompts=list(request.metadata.get("prompts") or request.metadata.get("prompt_hints") or []),
            roi_hints=list(request.metadata.get("roi_hints") or []),
            point_radius_px=int(self.spec.extra.get("point_radius_px", 12)),
        )
        boundary_warning = warning(
            "medsam_like_prompt_fallback_non_diagnostic",
            (
                "MedSAM-like prompt fallback is a deterministic bbox/point mask contract for annotation workflow; "
                "it is not real MedSAM/SAM2 checkpoint inference and is not diagnostic."
            ),
        )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload["prediction"],
            score=payload["score"],
            segmentation_mask=payload["segmentation_mask"],
            lesion_evidence=payload["lesion_evidence"],
            quantification=payload["quantification"],
            warnings=status.warnings + [boundary_warning],
        )


class D025LesionSegmenterAdapter(BaseModelAdapter):
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        if request.input_type != "npz_roi":
            unavailable_warning = warning(
                "unsupported_input_for_proxy_model",
                f"Model {self.spec.model_id} only supports npz_roi inputs in this prototype.",
                True,
            )
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "unsupported input for D025 proxy segmenter"},
                warnings=status.warnings + [unavailable_warning],
            )
        if self._model is None:
            self._load_model()
        from src.core.paths import resolve_path
        from src.models.lesion_segmenter import predict_npz_roi, select_torch_device

        device = select_torch_device(self.spec.device_policy)
        output_dir = resolve_path(
            self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/model_masks")
        )
        threshold = float(self.spec.extra.get("threshold", 0.5))
        assert self._model is not None
        payload = predict_npz_roi(
            self._model,
            request.input_path,
            device=device,
            output_dir=output_dir,
            case_id=request.case_id,
            threshold=threshold,
            model_id=self.spec.model_id,
        )
        boundary_warning = self._boundary_warning()
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload["prediction"],
            score=payload["score"],
            segmentation_mask=payload["segmentation_mask"],
            lesion_evidence=payload["lesion_evidence"],
            quantification=payload["quantification"],
            warnings=[boundary_warning],
        )

    def _load_model(self) -> None:
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from src.core.paths import resolve_path
        from src.models.lesion_segmenter import load_lesion_segmenter_checkpoint, select_torch_device

        device = select_torch_device(self.spec.device_policy)
        self._model, self._metadata = load_lesion_segmenter_checkpoint(
            resolve_path(self.spec.checkpoint_path), device=device
        )

    def _boundary_warning(self) -> dict[str, Any]:
        return warning(
            "proxy_model_non_target_domain",
            "D025 checkpoint is a CBCT lesion ROI proxy and is not intraoperative ICG jaw osteomyelitis evidence.",
        )


class ConvNeXt3DLesionSegmenterAdapter(D025LesionSegmenterAdapter):
    """ConvNeXt-style 3D lesion segmenter adapter for CBCT proxy segmentation."""

    def _boundary_warning(self) -> dict[str, Any]:
        return warning(
            "convnext3d_proxy_model_non_target_domain",
            "ConvNeXt-style 3D checkpoint is trained on CBCT lesion ROI proxy data and is not target-domain intraoperative ICG jaw osteomyelitis evidence.",
        )


class FluorescenceHotspotSegmenterAdapter(BaseModelAdapter):
    implements_inference = True

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        if request.input_type != "2d_image":
            unsupported_warning = warning(
                "unsupported_input_for_hotspot_segmenter",
                f"Model {self.spec.model_id} only supports 2d_image inputs in this prototype.",
                True,
            )
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "unsupported input for fluorescence hotspot segmenter"},
                warnings=status.warnings + [unsupported_warning],
            )
        from src.core.paths import resolve_path
        from src.models.hotspot_segmenter import segment_2d_fluorescence_hotspots

        payload = segment_2d_fluorescence_hotspots(
            request.input_path,
            output_dir=resolve_path(
                self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/hotspot_masks")
            ),
            case_id=request.case_id,
            threshold=float(self.spec.extra.get("threshold", 0.6)),
            min_component_area=int(self.spec.extra.get("min_component_area", 25)),
            colormap=str(self.spec.extra.get("colormap", "green")),
            alpha=float(self.spec.extra.get("alpha", 0.45)),
            model_id=self.spec.model_id,
            roi_hints=list(request.metadata.get("roi_hints") or []),
        )
        boundary_warning = warning(
            "heuristic_hotspot_segmenter_non_diagnostic",
            "2D fluorescence hotspot segmentation is a heuristic prototype baseline and is not target-domain clinical diagnosis.",
        )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload["prediction"],
            score=payload["score"],
            segmentation_mask=payload["segmentation_mask"],
            lesion_evidence=payload["lesion_evidence"],
            quantification=payload["quantification"],
            warnings=[boundary_warning],
        )


class ConvNeXt2DKeyframeSegmenterAdapter(BaseModelAdapter):
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        if request.input_type != "2d_image":
            unsupported_warning = warning(
                "unsupported_input_for_keyframe_segmenter",
                f"Model {self.spec.model_id} only supports 2d_image inputs in this prototype.",
                True,
            )
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "unsupported input for keyframe segmenter"},
                warnings=status.warnings + [unsupported_warning],
            )
        if self._model is None:
            self._load_model()
        from src.core.paths import resolve_path
        from src.models.keyframe_segmenter import predict_keyframe_image, select_torch_device

        assert self._model is not None
        payload = predict_keyframe_image(
            self._model,
            request.input_path,
            device=select_torch_device(self.spec.device_policy),
            output_dir=resolve_path(
                self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/keyframe_model_masks")
            ),
            case_id=request.case_id,
            threshold=float(self.spec.extra.get("threshold", 0.5)),
            model_id=self.spec.model_id,
            tile_size=_optional_int(self.spec.extra.get("tile_size")),
            tile_overlap=int(self.spec.extra.get("tile_overlap", 64)),
            force_tiled=bool(self.spec.extra.get("force_tiled", False)),
            max_whole_pixels=int(self.spec.extra.get("max_whole_pixels", 1024 * 1024)),
        )
        boundary_warning = warning(
            "convnext2d_keyframe_proxy_non_target_domain",
            (
                "Trainable 2D keyframe segmenter is trained on synthetic or pseudo-labeled fluorescence proxy frames; "
                "it is not real intraoperative ICG jaw osteomyelitis clinical evidence."
            ),
        )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload["prediction"],
            score=payload["score"],
            segmentation_mask=payload["segmentation_mask"],
            lesion_evidence=payload["lesion_evidence"],
            quantification=payload["quantification"],
            warnings=[boundary_warning],
        )

    def _load_model(self) -> None:
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from src.core.paths import resolve_path
        from src.models.keyframe_segmenter import load_keyframe_segmenter_checkpoint, select_torch_device

        self._model, self._metadata = load_keyframe_segmenter_checkpoint(
            resolve_path(self.spec.checkpoint_path),
            device=select_torch_device(self.spec.device_policy),
        )


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
    "d025_lesion_segmenter": D025LesionSegmenterAdapter,
    "convnext3d_segmenter": ConvNeXt3DLesionSegmenterAdapter,
    "fluorescence_hotspot_segmenter": FluorescenceHotspotSegmenterAdapter,
    "convnext2d_keyframe_segmenter": ConvNeXt2DKeyframeSegmenterAdapter,
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
    specs = runtime.get("models") or [
        {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]}
    ]
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
    candidates = [
        adapter for adapter in adapters if not explicit_model_id or adapter.describe().model_id == explicit_model_id
    ]
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


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
