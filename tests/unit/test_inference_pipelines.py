from __future__ import annotations

from src.core.schemas import InputSummary
from src.engine.inference import MedicalImagingInferenceService
from src.pipelines.base import PipelineContext
from src.pipelines.segmentation import SegmentationPipeline


def test_classification_fixture_completes(fixture_dir) -> None:
    service = MedicalImagingInferenceService.from_config("configs/inference/demo.yml")
    result = service.diagnose(fixture_dir / "sample_image.png", task_type="classification")
    payload = result.to_dict()
    assert payload["status"] == "completed"
    assert payload["probability"] is not None
    assert payload["report_path"]
    assert any(item["code"] == "checkpoint_missing" for item in payload["warnings"])


def test_multitask_combines_outputs(fixture_dir) -> None:
    service = MedicalImagingInferenceService.from_config("configs/inference/demo.yml")
    result = service.diagnose(fixture_dir / "sample_roi.npz", task_type="multitask")
    payload = result.to_dict()
    assert payload["status"] == "completed"
    assert payload["segmentation_mask"].get("path")
    assert payload["lesion_evidence"]
    assert payload["quantification"]


def test_full_volume_direct_classification_is_blocked(fixture_dir) -> None:
    service = MedicalImagingInferenceService.from_config("configs/inference/demo.yml")
    result = service.diagnose(fixture_dir / "sample_volume.nii.gz", task_type="classification")
    assert result.status == "full_volume_requires_detection"
    assert any(item["code"] == "full_volume_requires_detection" for item in result.warnings)


def test_osteo_vision_2d_segmentation_uses_hotspot_adapter() -> None:
    service = MedicalImagingInferenceService.from_config("configs/inference/osteo_vision.yml")
    result = service.diagnose("tests/fixtures/platform/fluorescence.png", task_type="segmentation")
    assert result.status == "completed"
    assert result.model_family == "fluorescence_hotspot_segmenter"
    assert result.segmentation_mask["format"] == "png_binary_mask"
    assert result.quantification["available"] is True


def test_segmentation_pipeline_prefers_adapter_result() -> None:
    result = SegmentationPipeline().run(
        PipelineContext(
            case_id="case",
            input_summary=InputSummary(path="case.npz", input_type="npz_roi", accepted=True),
            runtime={},
            task_config={},
            models={},
            adapter_result={
                "segmentation_mask": {"path": "adapter_mask.npz", "source": "adapter"},
                "lesion_evidence": {"type": "volume_mask", "source": "adapter"},
                "quantification": {"available": True, "source": "adapter"},
                "prediction": {"segmentation_available": True},
            },
        )
    )
    assert result["segmentation_mask"]["source"] == "adapter"
    assert result["quantification"]["source"] == "adapter"
