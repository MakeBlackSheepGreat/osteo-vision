from __future__ import annotations

from osteo_vision_core.engine.benchmark import evaluate_manifest
from osteo_vision_core.engine.inference import MedicalImagingInferenceService


def test_demo_and_benchmark_share_service(tmp_path, fixture_dir) -> None:
    service = MedicalImagingInferenceService.from_config("configs/inference/demo.yml")
    result = service.diagnose(fixture_dir / "sample_image.png", task_type="classification")
    report = evaluate_manifest(
        "configs/inference/demo.yml", "tests/fixtures/benchmark_manifest.csv", tmp_path / "benchmark"
    )
    assert result.model_version == report["model_version"]
    run_dir = report["run_dir"]
    assert (tmp_path / "benchmark").exists()
    assert "config_snapshot.yml" in [path.name for path in __import__("pathlib").Path(run_dir).iterdir()]
