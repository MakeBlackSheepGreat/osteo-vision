from __future__ import annotations

from pathlib import Path

from src.core.config import load_yaml
from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapter, model_spec_from_mapping


def test_configured_video_signal_multimask_candidate_runs(tmp_path: Path) -> None:
    runtime = load_yaml("configs/inference/osteo_vision.yml")["runtime"]
    mapping = next(
        dict(item) for item in runtime["models"] if item["model_id"] == "convnext2d_video_signal_multimask_v2_grouped"
    )
    mapping["device_policy"] = "cpu"
    mapping["extra"] = {**mapping["extra"], "output_dir": str(tmp_path / "multimask")}
    adapter = build_adapter(model_spec_from_mapping(mapping))
    fixture_path = Path("tests/fixtures/platform/fluorescence.png").resolve()

    status = adapter.warmup()
    result = adapter.predict(
        AdapterRequest(
            case_id="smoke_multimask",
            input_path=str(fixture_path),
            input_type="2d_image",
            task_type="segmentation",
            modality="fluorescence",
        )
    )

    assert status.available is True
    assert result.prediction["available"] is True
    assert Path(result.prediction["fluorescence_signal_mask"]["path"]).exists()
    assert Path(result.prediction["bone_gate_mask"]["path"]).exists()
    assert result.prediction["bone_gate_mask"]["review_status"] == "review_required"
    assert result.prediction["candidate_only"] is True
