from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.input_service import InputService
from backend.src.services.keyframe_segmentation import analyze_keyframe_segmentations
from backend.src.services.video_keyframe_metrics import (
    video_fluorescence_dynamics_summary,
    video_inference_performance_summary,
)
from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D
from src.preprocess.fluorescence import (
    decoded_frame_fluorescence_quantification,
    fluorescence_time_intensity_curve,
)


def test_decoded_frame_intensity_uses_signal_and_background_rois() -> None:
    image = np.full((10, 10), 25, dtype=np.uint8)
    image[2:8, 2:6] = 204
    result = decoded_frame_fluorescence_quantification(
        image,
        roi_hints=[
            {
                "roi_id": "signal",
                "label": "fluorescence signal",
                "geometry": {"type": "rect", "x": 0.2, "y": 0.2, "width": 0.4, "height": 0.6},
            },
            {
                "roi_id": "background",
                "label": "background",
                "geometry": {"type": "rect", "x": 0.0, "y": 0.0, "width": 0.2, "height": 1.0},
            },
        ],
    )

    assert result["available"] is True
    assert result["p95_intensity"] == 0.8
    assert abs(result["background_intensity"] - (25 / 255)) < 1e-6
    assert result["background_method"] == "explicit_background_roi_median"
    assert result["source"] == "decoded_keyframe_intensity"


def test_keyframe_analysis_reuses_one_rgb_decode_for_model_and_quantification(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "frame.jpg"
    Image.fromarray(np.full((18, 24, 3), 128, dtype=np.uint8)).save(image_path)
    received: dict[str, np.ndarray] = {}

    class Result:
        @staticmethod
        def to_dict() -> dict:
            return {
                "model_id": "predecoded_test",
                "model_family": "test",
                "prediction": {},
                "segmentation_mask": {"path": "mask.png", "positive_area_px": 1},
                "lesion_evidence": {},
                "quantification": {"positive_area_px": 1, "mean_probability": 0.6},
                "warnings": [],
            }

    class Adapter:
        @staticmethod
        def predict(request):
            received["model"] = request.metadata["predecoded_rgb"]
            return Result()

    def quantify(image, **_kwargs):
        received["quantification"] = image
        return {
            "available": True,
            "source": "decoded_keyframe_intensity",
            "intensity_domain": "decoded_8bit_luminance_unit_range",
            "p95_intensity": 0.5,
            "background_intensity": 0.5,
        }

    monkeypatch.setattr(
        "backend.src.services.keyframe_segmentation._keyframe_model_adapter",
        lambda *_args, **_kwargs: (Adapter(), []),
    )
    monkeypatch.setattr(
        "backend.src.services.keyframe_segmentation.decoded_frame_fluorescence_quantification",
        quantify,
    )

    outputs = analyze_keyframe_segmentations(
        [{"order": 1, "frame_index": 0, "timestamp_sec": 0.0, "evidence_path": str(image_path)}],
        tmp_path / "outputs",
        case_id="case_predecoded",
        config_path=str(tmp_path / "unused.yml"),
        model_id="predecoded_test",
        threshold=0.5,
        colormap="green",
        roi_hints=[],
    )

    assert outputs[0]["analysis_method"] == "trainable_keyframe_segmenter"
    assert received["model"] is received["quantification"]
    assert received["model"].shape == (18, 24, 3)
    assert outputs[0]["quantification"]["decoded_frame_intensity"]["source_path"] == str(image_path)


def test_time_intensity_curve_requires_real_distinct_timestamps() -> None:
    result = fluorescence_time_intensity_curve(
        [
            {"timestamp_sec": None, "p95_intensity": 0.4, "background_intensity": 0.1},
            {"timestamp_sec": 1.0, "p95_intensity": 0.5, "background_intensity": 0.1},
            {"timestamp_sec": 1.0, "p95_intensity": 0.8, "background_intensity": 0.1},
        ]
    )

    assert result["available"] is False
    assert result["reason"] == "at_least_two_distinct_timestamped_keyframes_required"
    assert result["curve_quality"]["invalid_timestamp_count"] == 1
    assert result["curve_quality"]["duplicate_timestamp_count"] == 1


def test_performance_summary_counts_whole_frame_and_tiled_modes() -> None:
    summary = video_inference_performance_summary(
        [
            {"inference": {"mode": "whole_frame", "elapsed_ms": 12.0}},
            {"inference": {"mode": "tiled", "elapsed_ms": 28.0}},
            {"inference": {"mode": "whole", "elapsed_ms": 16.0}},
        ]
    )

    assert summary["measured_frame_count"] == 3
    assert summary["whole_frame_count"] == 2
    assert summary["tiled_frame_count"] == 1
    assert summary["unknown_mode_frame_count"] == 0
    assert summary["latency_ms_p95"] is not None


def test_trainable_keyframe_quantification_uses_decoded_pixels(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "keyframe.pt"
    model = TinyKeyframeSegmenter2D(base_channels=2)
    torch.save(
        {
            "model_id": "keyframe_dynamic_test",
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
                "    - model_id: keyframe_dynamic_test",
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
    image = np.full((24, 32, 3), 51, dtype=np.uint8)
    image[6:18, 8:24] = 204
    Image.fromarray(image).save(image_path)

    outputs = analyze_keyframe_segmentations(
        [{"order": 1, "frame_index": 4, "timestamp_sec": 0.5, "evidence_path": str(image_path)}],
        tmp_path / "outputs",
        case_id="case_dynamic",
        config_path=str(config_path),
        model_id="keyframe_dynamic_test",
        threshold=0.6,
        colormap="green",
        roi_hints=[],
    )
    quantification = outputs[0]["quantification"]

    assert outputs[0]["analysis_method"] == "trainable_keyframe_segmenter"
    assert quantification["intensity_source"] == "decoded_keyframe_intensity"
    assert quantification["p95_intensity"] == 0.8
    assert quantification["background_intensity"] == 0.2
    assert quantification["model_probability_summary"]["mean_probability"] is not None
    assert quantification["p95_intensity"] != quantification["model_probability_summary"]["mean_probability"]


def test_mp4_analysis_emits_structured_dynamic_curve(tmp_path: Path) -> None:
    video_path = tmp_path / "dynamic.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 4.0, (64, 48))
    for level in (25, 80, 180, 110):
        frame = np.full((48, 64, 3), 10, dtype=np.uint8)
        frame[12:36, 16:48] = level
        writer.write(frame)
    writer.release()

    visual_dir = tmp_path / "visual"
    config_path = tmp_path / "analysis.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models: []",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(visual_dir))}",
            ]
        ),
        encoding="utf-8",
    )
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = InputService().add_inputs(
        CaseRecord(case_id="case_dynamic_mp4", title="dynamic mp4"),
        [InputCreateRequest(channel=InputChannel.VIDEO, path=str(video_path), mime_type="video/mp4")],
    )
    repo.create(case)

    updated = AnalysisService(repo, config_path=str(config_path)).start_analysis(
        case,
        [],
        {
            "mode": "video_file",
            "keyframe_count": 4,
            "keyframe_frame_indexes": [0, 1, 2, 3],
        },
        [],
    )
    run = updated.analysis_runs[-1]
    curve = run.quantitative_summary["fluorescence_time_intensity_curve"]

    assert run.status == "completed"
    assert curve["available"] is True
    assert curve["point_count"] == 4
    assert curve["time_to_peak_sec"] == 0.5
    assert curve["max_normalized_rise_slope_per_sec"] > 0
    assert curve["normalized_auc"] > 0
    assert curve["curve_quality"]["quality_status"] == "usable"
    assert [point["timestamp_sec"] for point in curve["points"]] == [0.0, 0.25, 0.5, 0.75]
    assert all(
        detail["intensity_source"] == "decoded_keyframe_intensity" for detail in run.fused_outputs["frame_details"]
    )

    manifest_path = Path(run.fused_outputs["frame_details_manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["frames"][0]["decoded_frame_intensity"]["source"] == "decoded_keyframe_intensity"


def test_video_dynamics_summary_excludes_probability_only_details() -> None:
    result = video_fluorescence_dynamics_summary(
        [
            {"timestamp_sec": 0.0, "mean_probability": 0.9},
            {"timestamp_sec": 1.0, "mean_probability": 0.1},
        ]
    )

    assert result["available"] is False
    assert result["source"] == "decoded_keyframe_intensity"
    assert result["excluded_non_intensity_frame_count"] == 2
