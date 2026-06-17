from __future__ import annotations

from src.engine.inference import MedicalImagingInferenceService


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

