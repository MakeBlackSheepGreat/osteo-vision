from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.analysis_service import AnalysisService, _analyze_keyframe_segmentations
from backend.src.services.input_service import InputService
from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D


def test_analysis_service_creates_fluorescence_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_analysis", title="analysis")
    case = InputService().add_inputs(
        case,
        [
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(Path("tests/fixtures/platform/white.png").resolve())),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(Path("tests/fixtures/platform/fluorescence.png").resolve())),
        ],
    )
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(case, [], {"threshold": 0.6}, [])

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.quantitative_summary["positive_area_px"] > 0
    assert Path(run.fused_outputs["outputs"]["overlay_path"]).exists()


def test_analysis_service_accepts_realtime_video_preview(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_realtime", title="realtime")
    case = InputService().add_inputs(
        case,
        [InputCreateRequest(channel=InputChannel.VIDEO, path="camera://browser/default")],
    )
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {"mode": "realtime_video", "source_path": "camera://browser/default"},
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "realtime_video"
    assert run.fused_outputs["source_path"] == "camera://browser/default"
    assert run.warnings[0]["code"] == "realtime_stream_not_connected"
    assert updated.status == "analyzed"


def test_keyframe_segmentation_prefers_trainable_model(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "keyframe.pt"
    model = TinyKeyframeSegmenter2D(base_channels=2)
    torch.save(
        {
            "model_id": "keyframe_test",
            "model_family": "convnext2d_keyframe_segmenter",
            "model_config": {"in_channels": 3, "out_channels": 2, "base_channels": 2},
            "state_dict": model.state_dict(),
            "threshold": 0.0,
        },
        checkpoint_path,
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: keyframe_test",
                "      family: convnext2d_keyframe_segmenter",
                "      task_types: [segmentation]",
                "      input_types: [2d_image]",
                f"      checkpoint_path: {json.dumps(str(checkpoint_path))}",
                "      dependency_group: torch",
                "      device_policy: cpu",
                "      extra:",
                "        threshold: 0.0",
            ]
        ),
        encoding="utf-8",
    )
    image_path = tmp_path / "frame.png"
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 16:36, 1] = 220
    Image.fromarray(image).save(image_path)

    outputs = _analyze_keyframe_segmentations(
        [{"order": 1, "frame_index": 0, "timestamp_sec": 0.0, "evidence_path": str(image_path)}],
        tmp_path / "segmentation_outputs",
        case_id="case_video",
        config_path=str(config_path),
        model_id="keyframe_test",
        threshold=0.6,
        colormap="green",
        roi_hints=[],
    )

    assert outputs[0]["analysis_method"] == "trainable_keyframe_segmenter"
    assert outputs[0]["model_id"] == "keyframe_test"
    assert Path(outputs[0]["segmentation_mask"]["path"]).exists()
    assert Path(outputs[0]["lesion_evidence"]["probability_path"]).exists()
    assert Path(outputs[0]["lesion_evidence"]["overlay_path"]).exists()
    assert outputs[0]["quantification"]["positive_area_px"] > 0
