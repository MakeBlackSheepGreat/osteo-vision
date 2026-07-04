from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.core.config import load_yaml, runtime_config
from src.core.paths import artifact_dirs, resolve_path
from src.core.schemas import AdapterRequest, PredictionResult, TaskPackage, path_to_case_id
from src.core.task_package import default_task_package, load_task_package
from src.core.warnings import (
    DISCLAIMER_TEXT,
    STATUS_CLASSIFICATION_UNAVAILABLE,
    STATUS_COMPLETED,
    STATUS_FULL_VOLUME_REQUIRES_DETECTION,
    STATUS_INVALID_INPUT,
    STATUS_SEGMENTATION_UNAVAILABLE,
    warning,
)
from src.models.registry import (
    build_adapters,
    checkpoint_warning,
    inventory_from_adapters,
    load_fixture_models,
    select_adapter,
)
from src.pipelines.base import PipelineContext
from src.pipelines.classification import ClassificationPipeline
from src.pipelines.detection import DetectionPipeline
from src.pipelines.multitask import MultitaskPipeline
from src.pipelines.quantification import QuantificationPipeline
from src.pipelines.segmentation import SegmentationPipeline
from src.preprocess.ct_preprocess import ct_preprocess_summary
from src.preprocess.input_validation import validate_input
from src.reports.single_case import write_single_case_report

PIPELINE_CLASSES = {
    "classification": ClassificationPipeline,
    "segmentation": SegmentationPipeline,
    "detection": DetectionPipeline,
    "quantification": QuantificationPipeline,
    "multitask": MultitaskPipeline,
}


class MedicalImagingInferenceService:
    def __init__(self, config: dict[str, Any], config_path: str | Path):
        self.config = config
        self.config_path = str(resolve_path(config_path))
        self.runtime = runtime_config(config)
        self.model_version = str(self.runtime.get("model_version", "micf-fixture-v0"))
        self.artifacts = artifact_dirs(config)
        self.task_package = self._load_task_package()
        self.models = load_fixture_models(self.runtime, self.artifacts["visual"])
        self.adapters = build_adapters(self.runtime)
        self.startup_warnings = checkpoint_warning(self.runtime)

    @classmethod
    def from_config(cls, config_path: str | Path) -> "MedicalImagingInferenceService":
        return cls(load_yaml(config_path), config_path)

    def diagnose(
        self,
        input_path: str | Path,
        task_type: str | None = None,
        case_id: str | None = None,
        model_id: str | None = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        selected_task = task_type or str(self.runtime.get("default_task_type", "classification"))
        summary = validate_input(input_path)
        case = case_id or path_to_case_id(input_path)
        warnings = list(summary.warnings) + list(self.startup_warnings)
        adapter, adapter_statuses = select_adapter(
            self.adapters,
            task_type=selected_task,
            input_type=summary.input_type,
            modality=self.task_package.modality,
            policy=str(self.runtime.get("model_selection_policy", "fixture_fallback")),
            explicit_model_id=model_id,
        )
        adapter_result = None
        adapter_status_payload = [status.to_dict() for status in adapter_statuses]
        adapter_warnings: list[dict[str, Any]] = []
        model_provenance: dict[str, Any] = {}
        selected_model_id = None
        selected_model_family = None
        if adapter is not None and summary.accepted:
            spec = adapter.describe()
            selected_model_id = spec.model_id
            selected_model_family = spec.family
            model_provenance = {
                "source_url": spec.source_url,
                "license": spec.license,
                "intended_use": spec.intended_use,
                "clinical_claim_allowed": spec.clinical_claim_allowed,
                "dependency_group": spec.dependency_group,
            }
            request = AdapterRequest(
                case_id=case,
                input_path=str(input_path),
                input_type=summary.input_type,
                task_type=selected_task,
                modality=self.task_package.modality,
                metadata=summary.metadata,
            )
            adapter_result_obj = adapter.predict(request)
            adapter_result = adapter_result_obj.to_dict()
            adapter_warnings = adapter_result_obj.warnings
            warnings.extend(adapter_warnings)
        base: dict[str, Any] = {
            "case_id": case,
            "input_type": summary.input_type,
            "task_type": selected_task,
            "model_version": self.model_version,
            "warnings": warnings,
            "resource_summary": {"device_policy": self.runtime.get("device_policy", "auto"), "fixture": True},
            "input_filename": Path(input_path).name,
            "preprocessing_summary": summary.to_dict(),
            "disclaimer_shown": True,
            "disclaimer": DISCLAIMER_TEXT,
            "model_id": selected_model_id,
            "model_family": selected_model_family,
            "model_provenance": model_provenance,
            "adapter_status": {"selected_model_id": selected_model_id, "candidates": adapter_status_payload},
            "adapter_warnings": adapter_warnings,
        }
        if not summary.accepted:
            result = PredictionResult(status=STATUS_INVALID_INPUT, **base)
            return self._with_report(result)
        if adapter_result and adapter_result.get("prediction", {}).get("available") is False:
            status = (
                STATUS_SEGMENTATION_UNAVAILABLE
                if selected_task == "segmentation"
                else STATUS_CLASSIFICATION_UNAVAILABLE
            )
            result = PredictionResult(status=status, prediction=adapter_result.get("prediction", {}), **base)
            result.timing_ms["total"] = round((time.perf_counter() - start) * 1000, 3)
            return self._with_report(result)
        if summary.input_type in {"dicom_series", "nifti_volume"} and selected_task == "classification":
            base["warnings"].append(warning(STATUS_FULL_VOLUME_REQUIRES_DETECTION, blocking=True))
            base["preprocessing_summary"]["ct_summary"] = ct_preprocess_summary(summary.metadata)
            result = PredictionResult(status=STATUS_FULL_VOLUME_REQUIRES_DETECTION, prediction={}, **base)
            result.timing_ms["total"] = round((time.perf_counter() - start) * 1000, 3)
            return self._with_report(result)

        task_config = self._task_config(selected_task)
        pipeline_name = str(task_config.get("pipeline") or selected_task)
        pipeline_cls = PIPELINE_CLASSES.get(pipeline_name)
        if pipeline_cls is None:
            base["warnings"].append(warning(STATUS_INVALID_INPUT, f"Unknown task type: {selected_task}", True))
            return self._with_report(PredictionResult(status=STATUS_INVALID_INPUT, **base))
        context = PipelineContext(
            case_id=case,
            input_summary=summary,
            runtime=self.runtime,
            task_config=task_config,
            models=self.models,
            adapter_result=adapter_result,
        )
        payload = pipeline_cls().run(context)
        result = PredictionResult(status=STATUS_COMPLETED, **base)
        self._apply_payload(result, payload)
        result.timing_ms["total"] = round((time.perf_counter() - start) * 1000, 3)
        return self._with_report(result)

    def _task_config(self, task_type: str) -> dict[str, Any]:
        tasks = self.runtime.get("tasks") or {}
        return dict(tasks.get(task_type, {"pipeline": task_type}))

    def _load_task_package(self) -> TaskPackage:
        package_path = self.runtime.get("task_package")
        if not package_path:
            return default_task_package()
        return load_task_package(package_path)

    def model_inventory(self) -> list[dict[str, Any]]:
        return inventory_from_adapters(self.adapters)

    def _with_report(self, result: PredictionResult) -> PredictionResult:
        result.report_path = write_single_case_report(result.to_dict(), self.artifacts["reports"])
        return result

    @staticmethod
    def _apply_payload(result: PredictionResult, payload: dict[str, Any]) -> None:
        for key, value in payload.items():
            if key == "warnings":
                result.warnings.extend(value)
            elif hasattr(result, key):
                setattr(result, key, value)
            else:
                result.prediction[key] = value
