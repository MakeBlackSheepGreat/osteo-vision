from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol

from osteo_vision_core.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec
from osteo_vision_core.core.warnings import STATUS_CHECKPOINT_MISSING, warning
from osteo_vision_core.models.classifier import DeterministicClassifier

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
        if not bool(self.spec.extra.get("runtime_allowed", True)):
            reasons.append("runtime execution disabled by configuration")
            warnings.append(
                warning(
                    "model_runtime_not_allowed",
                    f"Runtime execution is disabled for {self.spec.model_id}; the model remains inventory-only.",
                )
            )
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
        return super().warmup()

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
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
            reasons: list[str] = []
            warnings: list[dict[str, Any]] = []
            if not self.spec.enabled:
                reasons.append("model disabled")
            if not bool(self.spec.extra.get("runtime_allowed", True)):
                reasons.append("runtime execution disabled by configuration")
                warnings.append(
                    warning(
                        "model_runtime_not_allowed",
                        f"Runtime execution is disabled for {self.spec.model_id}; the model remains inventory-only.",
                    )
                )
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
                available=not reasons,
                enabled=self.spec.enabled,
                reasons=reasons,
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
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.prompt_segmenter import segment_2d_prompt_mask

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
                f"Model {self.spec.model_id} only supports npz_roi inputs in this platform workflow.",
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
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.lesion_segmenter import predict_npz_roi, select_torch_device

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
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.lesion_segmenter import load_lesion_segmenter_checkpoint, select_torch_device

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
                f"Model {self.spec.model_id} only supports 2d_image inputs in this platform workflow.",
                True,
            )
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "unsupported input for fluorescence hotspot segmenter"},
                warnings=status.warnings + [unsupported_warning],
            )
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.hotspot_segmenter import segment_2d_fluorescence_hotspots

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
            "2D fluorescence hotspot segmentation is a heuristic platform validation baseline and is not target-domain clinical diagnosis.",
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
                f"Model {self.spec.model_id} only supports 2d_image inputs in this platform workflow.",
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
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import predict_keyframe_image, select_torch_device

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
            tile_batch_size=int(self.spec.extra.get("tile_batch_size", 1)),
            force_tiled=bool(self.spec.extra.get("force_tiled", False)),
            max_whole_pixels=int(self.spec.extra.get("max_whole_pixels", 1024 * 1024)),
            target_domain=bool(self.spec.extra.get("target_domain", False)),
            input_domain=str(self.spec.extra.get("input_domain", "2D JPEG/MP4 keyframe fluorescence proxy")),
            data_boundary=str(
                self.spec.extra.get("training_data_boundary", "synthetic_or_pseudo_labeled_non_target_domain")
            ),
            temperature=float(
                self.spec.extra.get("temperature")
                or (self._metadata.get("calibration") or {}).get("temperature")
                or 1.0
            ),
            tta_enabled=bool(self.spec.extra.get("uncertainty_tta_enabled", False)),
            fast_output=bool(self.spec.extra.get("fast_output", False)),
            overlay_format=str(self.spec.extra.get("overlay_format", "png")),
            overlay_jpeg_quality=int(self.spec.extra.get("overlay_jpeg_quality", 85)),
            use_amp=bool(self.spec.extra.get("use_amp", False)),
            evidence_png_compression=int(self.spec.extra.get("evidence_png_compression", 3)),
            candidate_min_component_area=int(self.spec.extra.get("candidate_min_component_area", 16)),
            candidate_min_area_fraction=float(self.spec.extra.get("candidate_min_area_fraction", 0.0)),
            candidate_max_count=_optional_int(self.spec.extra.get("candidate_max_count")),
            rgb=request.metadata.get("predecoded_rgb"),
        )
        boundary_warning = warning(
            "convnext2d_keyframe_proxy_non_target_domain",
            (
                "The trainable 2D keyframe segmenter is trained on synthetic or pseudo-labeled fluorescence proxy "
                "frames; it is not real intraoperative ICG jaw osteomyelitis clinical evidence."
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
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import load_keyframe_segmenter_checkpoint, select_torch_device

        self._model, self._metadata = load_keyframe_segmenter_checkpoint(
            resolve_path(self.spec.checkpoint_path),
            device=select_torch_device(self.spec.device_policy),
        )


class DualChannelSegmenterAdapter(BaseModelAdapter):
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        fluorescence_path = request.metadata.get("fluorescence_path")
        if request.input_type != "dual_channel_image" or not fluorescence_path:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "dual channel paths are required"},
                warnings=status.warnings
                + [
                    warning(
                        "dual_channel_input_required", "White-light and fluorescence image paths are required.", True
                    )
                ],
            )
        if self._model is None:
            self._load_model()
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.dual_channel_segmenter import predict_dual_channel
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device

        assert self._model is not None
        payload = predict_dual_channel(
            self._model,
            request.input_path,
            str(fluorescence_path),
            device=select_torch_device(self.spec.device_policy),
            output_dir=resolve_path(
                self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/dual_channel_ai")
            ),
            case_id=request.case_id,
            threshold=float(self.spec.extra.get("threshold", self._metadata.get("threshold", 0.5))),
            mode=str(self.spec.extra.get("mode", "intermediate_fusion")),
        )
        payload["input_boundary"] = {
            "input_domain": str(self.spec.extra.get("input_domain", "non_target_domain_proxy")),
            "white_light_source": str(self.spec.extra.get("white_light_source", "synthetic_white_light_proxy")),
            "target_domain": bool(self.spec.extra.get("target_domain", False)),
        }
        payload["fallback_policy"] = str(self.spec.extra.get("fallback_policy", "traditional_registration_and_fusion"))
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload,
            score=float(payload.get("max_probability", 0.0)),
            segmentation_mask={
                "path": payload.get("mask_path"),
                "format": "png_binary_mask",
                "positive_area_px": payload.get("positive_area_px"),
            },
            lesion_evidence={
                "probability_path": payload.get("probability_path"),
                "overlay_path": payload.get("overlay_path"),
                "candidates": payload.get("candidates", []),
            },
            quantification={
                "positive_area_px": payload.get("positive_area_px"),
                "positive_area_fraction": payload.get("positive_area_fraction"),
                "mean_probability": payload.get("mean_probability"),
                "max_probability": payload.get("max_probability"),
            },
            warnings=[
                warning(
                    "dual_channel_proxy_non_target_domain",
                    "Dual-channel AI is proxy-data engineering evidence requiring physician review.",
                )
            ],
        )

    def _load_model(self) -> None:
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.dual_channel_segmenter import load_dual_channel_checkpoint
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device

        self._model, self._metadata = load_dual_channel_checkpoint(
            resolve_path(self.spec.checkpoint_path), device=select_torch_device(self.spec.device_policy)
        )


class PatientConditionedSegmenterAdapter(BaseModelAdapter):
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}
        self._runtime_evidence: Any | None = None

    def warmup(self) -> AdapterStatus:
        status = super().warmup()
        reasons = list(status.reasons)
        warnings = list(status.warnings)
        if reasons:
            return status
        manifest_value = str(self.spec.extra.get("checkpoint_manifest_path") or "").strip()
        if not manifest_value:
            reasons.append("patient-conditioned checkpoint manifest is required")
        else:
            try:
                self._ensure_runtime_loaded()
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                reasons.append(f"patient-conditioned runtime validation failed: {exc}")
                warnings.append(
                    warning(
                        "patient_conditioned_runtime_validation_failed",
                        f"Patient-conditioned checkpoint or manifest validation failed for {self.spec.model_id}.",
                        True,
                        error=str(exc),
                    )
                )
        runtime = self._runtime_evidence
        if self.spec.clinical_claim_allowed:
            reasons.append("patient-conditioned adapter cannot allow clinical claims")
        if runtime is not None and runtime.proxy_checkpoint:
            if not runtime.engineering_ready:
                reasons.append("proxy patient-conditioned checkpoint lacks engineering readiness")
            if self.spec.extra.get("candidate_only") is not True:
                reasons.append("proxy patient-conditioned checkpoint must remain candidate-only")
            if self.spec.extra.get("engineering_candidate_execution_allowed") is not True:
                reasons.append("proxy patient-conditioned engineering execution is not explicitly allowed")
            warnings.append(
                warning(
                    "patient_conditioned_proxy_candidate_only",
                    "Patient-conditioned proxy inference is limited to explicit engineering evidence and image-only fallback.",
                )
            )
        if (
            runtime is not None
            and self.spec.extra.get("runtime_replacement_allowed") is True
            and not runtime.runtime_replacement_allowed
        ):
            reasons.append("patient-conditioned runtime replacement lacks validated promotion evidence")
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=not reasons,
            enabled=self.spec.enabled,
            reasons=list(dict.fromkeys(reasons)),
            warnings=warnings,
        )

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        fluorescence_path = str(request.metadata.get("fluorescence_path") or "").strip()
        if request.input_type not in {"2d_image", "dual_channel_image"} or not fluorescence_path:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={
                    "available": False,
                    "spatial_effect_applied": False,
                    "failure_reasons": ["registered_white_light_and_fluorescence_inputs_required"],
                },
                warnings=status.warnings
                + [
                    warning(
                        "patient_conditioned_dual_channel_input_required",
                        "Registered white-light and fluorescence image paths are required.",
                        True,
                    )
                ],
            )
        assert self._model is not None
        assert self._runtime_evidence is not None
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device
        from osteo_vision_core.models.patient_conditioned_runtime import predict_patient_conditioned_image

        try:
            payload = predict_patient_conditioned_image(
                self._model,
                self._runtime_evidence,
                white_path=request.input_path,
                fluorescence_path=fluorescence_path,
                metadata=request.metadata,
                device=select_torch_device(self.spec.device_policy),
                output_dir=resolve_path(
                    self.spec.extra.get(
                        "output_dir",
                        "artifacts/visual_evidence/osteo_vision/patient_conditioned_segmentation",
                    )
                ),
                case_id=request.case_id,
                segmentation_threshold=float(self.spec.extra.get("threshold", self._metadata.get("threshold", 0.5))),
                uncertainty_threshold=float(self.spec.extra.get("uncertainty_threshold", 0.5)),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={
                    "available": False,
                    "spatial_effect_applied": False,
                    "failure_reasons": ["patient_conditioned_inference_failed"],
                    "detail": str(exc),
                    "checkpoint_sha256": self._runtime_evidence.checkpoint_sha256,
                    "manifest_sha256": self._runtime_evidence.manifest_sha256,
                    "runtime_replacement_allowed": False,
                },
                warnings=status.warnings
                + [
                    warning(
                        "patient_conditioned_inference_failed",
                        "Patient-conditioned inference failed closed before producing a spatial effect.",
                        True,
                        error=str(exc),
                    )
                ],
            )

        quantification = dict(payload["quantification"])
        evidence_keys = (
            "image_only_probability_path",
            "conditioned_probability_path",
            "delta_map_path",
            "difference_mask_path",
            "spatial_effect_mask_path",
            "uncertainty_path",
            "image_only_probability_array_path",
            "conditioned_probability_array_path",
            "delta_map_array_path",
            "uncertainty_array_path",
            "evidence_manifest_path",
        )
        lesion_evidence = {key: payload.get(key) for key in evidence_keys}
        lesion_evidence.update(
            {
                "available": payload["available"],
                "spatial_effect_applied": payload["spatial_effect_applied"],
                "failure_reasons": list(payload["failure_reasons"]),
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "manifest_sha256": payload["manifest_sha256"],
                "runtime_replacement_allowed": payload["runtime_replacement_allowed"],
                "asset_sha256": payload["asset_sha256"],
                "reviewed_bone_gate": payload["reviewed_bone_gate"],
                "source_inputs": payload["source_inputs"],
                "dual_channel_registration_verified": payload["dual_channel_registration_verified"],
                "medical_boundary": payload["medical_boundary"],
            }
        )
        result_warnings = list(status.warnings)
        if payload["failure_reasons"]:
            result_warnings.append(
                warning(
                    "patient_conditioned_image_only_fallback",
                    "Patient-conditioned safety gates retained the image-only segmentation for physician review.",
                    failure_reasons=list(payload["failure_reasons"]),
                )
            )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload,
            score=float(quantification["conditioned_probability_max"]),
            segmentation_mask={
                "path": payload["conditioned_mask_path"],
                "image_only_path": payload["image_only_mask_path"],
                "format": "png_binary_mask",
                "positive_area_px": quantification["positive_area_px"],
                "positive_area_fraction": quantification["positive_area_fraction"],
                "safe_fallback_applied": payload["safe_fallback_applied"],
                "physician_review_required": True,
            },
            lesion_evidence=lesion_evidence,
            quantification=quantification,
            warnings=result_warnings,
        )

    def _ensure_runtime_loaded(self) -> None:
        if self._model is not None and self._runtime_evidence is not None:
            return
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device
        from osteo_vision_core.models.patient_conditioned_runtime import load_validated_patient_conditioned_runtime

        manifest_path = resolve_path(str(self.spec.extra["checkpoint_manifest_path"]))
        self._model, self._metadata, self._runtime_evidence = load_validated_patient_conditioned_runtime(
            resolve_path(self.spec.checkpoint_path),
            manifest_path,
            device=select_torch_device(self.spec.device_policy),
            expected_manifest_sha256=(
                str(self.spec.extra.get("checkpoint_manifest_sha256"))
                if self.spec.extra.get("checkpoint_manifest_sha256")
                else None
            ),
            strict_promotion_authorized=self.spec.extra.get("strict_promotion_authorized") is True,
        )


class BoneActivityMultiTaskAdapter(BaseModelAdapter):
    implements_inference = True

    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self._model: Any | None = None
        self._metadata: dict[str, Any] = {}
        self._runtime_evidence: Any | None = None

    def warmup(self) -> AdapterStatus:
        status = super().warmup()
        reasons = list(status.reasons)
        warnings = list(status.warnings)
        if reasons:
            return status
        manifest_value = str(self.spec.extra.get("checkpoint_manifest_path") or "").strip()
        expected_manifest_sha256 = str(self.spec.extra.get("checkpoint_manifest_sha256") or "").strip()
        if not manifest_value:
            reasons.append("bone-activity checkpoint manifest is required")
        if len(expected_manifest_sha256) != 64:
            reasons.append("bone-activity checkpoint manifest SHA256 is required")
        if not reasons:
            try:
                self._ensure_runtime_loaded()
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                reasons.append(f"bone-activity runtime validation failed: {exc}")
                warnings.append(
                    warning(
                        "bone_activity_runtime_validation_failed",
                        f"Bone-activity checkpoint or manifest validation failed for {self.spec.model_id}.",
                        True,
                        error=str(exc),
                    )
                )
        runtime = self._runtime_evidence
        if self.spec.clinical_claim_allowed:
            reasons.append("bone-activity adapter cannot allow clinical claims")
        if runtime is not None and runtime.proxy_checkpoint:
            candidate_execution_allowed = bool(
                self.spec.extra.get("candidate_only") is True
                and self.spec.extra.get("engineering_candidate_execution_allowed") is True
            )
            if not runtime.engineering_ready and not candidate_execution_allowed:
                reasons.append("proxy bone-activity checkpoint lacks engineering readiness")
            if self.spec.extra.get("candidate_only") is not True:
                reasons.append("proxy bone-activity checkpoint must remain candidate-only")
            if self.spec.extra.get("engineering_candidate_execution_allowed") is not True:
                reasons.append("proxy bone-activity engineering execution is not explicitly allowed")
            if self.spec.extra.get("mainline_replacement_allowed") is True:
                reasons.append("proxy bone-activity checkpoint cannot replace the mainline")
            warnings.append(
                warning(
                    "bone_activity_proxy_engineering_only",
                    "Bone-activity proxy inference is restricted to checksum-bound engineering evidence with spatial fallback.",
                )
            )
            if not runtime.engineering_utility_ready:
                warnings.append(
                    warning(
                        "bone_activity_engineering_utility_gate_failed",
                        "The frozen proxy test did not pass its engineering utility constraints.",
                    )
                )
        if (
            runtime is not None
            and self.spec.extra.get("runtime_replacement_allowed") is True
            and not runtime.runtime_replacement_allowed
        ):
            reasons.append("bone-activity runtime replacement lacks validated promotion evidence")
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=not reasons,
            enabled=self.spec.enabled,
            reasons=list(dict.fromkeys(reasons)),
            warnings=warnings,
        )

    def predict(self, request: AdapterRequest) -> AdapterResult:
        status = self.warmup()
        if not status.available:
            return super().predict(request)
        fluorescence_path = str(request.metadata.get("fluorescence_path") or "").strip()
        if request.input_type != "dual_channel_image" or not fluorescence_path:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={
                    "available": False,
                    "engineering_inference_executed": False,
                    "spatial_candidates_available": False,
                    "failure_reasons": ["registered_white_light_and_fluorescence_inputs_required"],
                },
                warnings=status.warnings
                + [
                    warning(
                        "bone_activity_dual_channel_input_required",
                        "Registered white-light and fluorescence image paths are required.",
                        True,
                    )
                ],
            )
        assert self._model is not None
        assert self._runtime_evidence is not None
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.bone_activity_runtime import predict_bone_activity_image
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device

        shape_values = self.spec.extra.get("input_shape") or (192, 256)
        try:
            input_shape = (int(shape_values[0]), int(shape_values[1]))
            payload = predict_bone_activity_image(
                self._model,
                self._runtime_evidence,
                white_path=request.input_path,
                fluorescence_path=fluorescence_path,
                metadata=request.metadata,
                device=select_torch_device(self.spec.device_policy),
                output_dir=resolve_path(
                    self.spec.extra.get(
                        "output_dir",
                        "artifacts/visual_evidence/osteo_vision/bone_activity_multitask",
                    )
                ),
                case_id=request.case_id,
                input_shape=input_shape,
            )
        except (IndexError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={
                    "available": False,
                    "engineering_inference_executed": False,
                    "spatial_candidates_available": False,
                    "failure_reasons": ["bone_activity_inference_failed"],
                    "detail": str(exc),
                    "checkpoint_sha256": self._runtime_evidence.checkpoint_sha256,
                    "manifest_sha256": self._runtime_evidence.manifest_sha256,
                    "runtime_replacement_allowed": False,
                },
                warnings=status.warnings
                + [
                    warning(
                        "bone_activity_inference_failed",
                        "Bone-activity inference failed closed before spatial candidates were produced.",
                        True,
                        error=str(exc),
                    )
                ],
            )

        spectrum = dict(payload["bone_activity_spectrum"])
        spatial_available = payload["spatial_candidates_available"] is True
        quantification: dict[str, Any] = {
            "spatial_candidates_available": spatial_available,
            "raw_engineering_summary": dict(payload["raw_engineering_outputs"]["summary"]),
        }
        if spatial_available:
            for key in (
                "low_activity_candidate",
                "transition_candidate",
                "high_activity_candidate",
                "ignore_region",
            ):
                candidate = dict(spectrum.get(key) or {})
                quantification[f"{key}_area_px"] = candidate.get("positive_area_px")
                quantification[f"{key}_bone_gate_fraction"] = candidate.get("bone_gate_fraction")
        result_warnings = list(status.warnings)
        if not spatial_available:
            result_warnings.append(
                warning(
                    "bone_activity_spatial_fallback",
                    "Bone-activity spatial candidates remain unavailable under the active safety gates.",
                    failure_reasons=list(payload["failure_reasons"]),
                )
            )
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload,
            segmentation_mask={
                "available": spatial_available,
                "path": spectrum.get("activity_class_map_path") if spatial_available else None,
                "format": "png_bone_activity_class_map" if spatial_available else None,
                "physician_review_required": True,
                "safe_fallback_applied": payload["safe_fallback_applied"],
            },
            lesion_evidence={
                "available": spatial_available,
                "bone_activity_spectrum": spectrum,
                "raw_engineering_outputs": payload["raw_engineering_outputs"],
                "evidence_manifest_path": payload["evidence_manifest_path"],
                "evidence_manifest_sha256": payload["evidence_manifest_sha256"],
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "manifest_sha256": payload["manifest_sha256"],
                "source_inputs": payload["source_inputs"],
                "reviewed_bone_gate": payload["reviewed_bone_gate"],
                "medical_boundary": payload["medical_boundary"],
            },
            quantification=quantification,
            warnings=result_warnings,
        )

    def _ensure_runtime_loaded(self) -> None:
        if self._model is not None and self._runtime_evidence is not None:
            return
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.bone_activity_runtime import load_validated_bone_activity_runtime
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device

        self._model, self._metadata, self._runtime_evidence = load_validated_bone_activity_runtime(
            resolve_path(self.spec.checkpoint_path),
            resolve_path(str(self.spec.extra["checkpoint_manifest_path"])),
            device=select_torch_device(self.spec.device_policy),
            expected_manifest_sha256=str(self.spec.extra["checkpoint_manifest_sha256"]),
            strict_promotion_authorized=self.spec.extra.get("strict_promotion_authorized") is True,
        )


class VideoSignalMultiMaskAdapter(BaseModelAdapter):
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
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "2d_image input is required"},
                warnings=status.warnings
                + [
                    warning(
                        "multimask_2d_input_required",
                        "The video-signal multi-mask candidate requires a 2D image.",
                        True,
                    )
                ],
            )
        if self._model is None:
            self._load_model()
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device
        from osteo_vision_core.models.video_signal_multimask import predict_video_signal_multimask

        assert self._model is not None
        payload = predict_video_signal_multimask(
            self._model,
            request.input_path,
            device=select_torch_device(self.spec.device_policy),
            output_dir=resolve_path(
                self.spec.extra.get("output_dir", "artifacts/visual_evidence/osteo_vision/video_signal_multimask")
            ),
            case_id=request.case_id,
            model_id=self.spec.model_id,
            thresholds=dict(self.spec.extra.get("thresholds") or {}),
            input_shape=tuple(self.spec.extra.get("input_shape") or (128, 176)),
            metadata=self._metadata,
            review_weights=dict(self.spec.extra.get("review_weights") or {}),
        )
        fluorescence = payload["fluorescence_signal_mask"]
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=payload,
            score=float(fluorescence["positive_area_fraction"]),
            segmentation_mask=fluorescence,
            lesion_evidence={
                "type": "video_signal_multimask_candidate",
                "fluorescence_signal_mask": fluorescence,
                "bone_gate_mask": payload["bone_gate_mask"],
                "review_contract": payload["review_contract"],
                "target_domain_flag": False,
            },
            quantification={
                "fluorescence_signal_positive_area_px": fluorescence["positive_area_px"],
                "fluorescence_signal_positive_area_fraction": fluorescence["positive_area_fraction"],
                "bone_gate_positive_area_px": payload["bone_gate_mask"]["positive_area_px"],
                "bone_gate_positive_area_fraction": payload["bone_gate_mask"]["positive_area_fraction"],
            },
            warnings=status.warnings
            + [
                warning(
                    "video_signal_multimask_proxy_review_required",
                    "Multi-mask outputs come from non-target-domain proxy supervision; bone-gate output requires physician review.",
                )
            ],
        )

    def _load_model(self) -> None:
        if not self.spec.checkpoint_path:
            raise ValueError(f"Model {self.spec.model_id} has no checkpoint_path")
        from osteo_vision_core.core.paths import resolve_path
        from osteo_vision_core.models.keyframe_segmenter import select_torch_device
        from osteo_vision_core.models.video_signal_multimask import load_video_signal_multimask_checkpoint

        self._model, self._metadata = load_video_signal_multimask_checkpoint(
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
    "residual_attention_unet_keyframe_segmenter": ConvNeXt2DKeyframeSegmenterAdapter,
    "plain_unet_keyframe_segmenter": ConvNeXt2DKeyframeSegmenterAdapter,
    "nested_skip_unet_keyframe_segmenter": ConvNeXt2DKeyframeSegmenterAdapter,
    "multiscale_depthwise_unet_keyframe_segmenter": ConvNeXt2DKeyframeSegmenterAdapter,
    "dual_channel_segmenter": DualChannelSegmenterAdapter,
    "patient_conditioned_segmenter": PatientConditionedSegmenterAdapter,
    "bone_activity_multitask": BoneActivityMultiTaskAdapter,
    "video_signal_multimask": VideoSignalMultiMaskAdapter,
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
        intended_use=str(mapping.get("intended_use", "research_competition_platform_validation")),
        clinical_claim_allowed=bool(mapping.get("clinical_claim_allowed", False)),
        extra=dict(mapping.get("extra") or {}),
    )


def build_adapter(spec: ModelSpec) -> BaseModelAdapter:
    adapter_cls = ADAPTER_CLASSES.get(spec.family, BaseModelAdapter)
    return adapter_cls(spec)


def build_adapters(runtime: dict[str, Any]) -> list[BaseModelAdapter]:
    specs = list(runtime.get("models") or [])
    if not specs and bool(runtime.get("use_fixture_model", True)):
        specs = [{"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]}]
    if not bool(runtime.get("use_fixture_model", True)):
        specs = [spec for spec in specs if str(spec.get("family") or "") != "fixture"]
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
        spec = adapter.describe()
        if spec.extra.get("candidate_only") and explicit_model_id != spec.model_id:
            continue
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
