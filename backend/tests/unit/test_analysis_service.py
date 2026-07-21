from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services import analysis_service as analysis_service_module
from backend.src.services.analysis_service import (
    AnalysisService,
    _analyze_keyframe_segmentations,
    _apply_live_frame_age_gate,
    _browser_frame_capture_report,
)
from backend.src.services.input_service import InputService
from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D


def _write_no_fallback_runtime_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "strict_no_fallback.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  allow_heuristic_keyframe_fallback: false",
                "  tasks:",
                "    segmentation:",
                "      pipeline: segmentation",
                "      model_id: missing_keyframe_segmenter",
                "  models: []",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def test_strict_runtime_requires_explicit_segmentation_model_binding(tmp_path: Path) -> None:
    config_path = tmp_path / "strict_missing_model.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  strict_startup: true",
                "  models: []",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )

    service = AnalysisService(JsonCaseRepository(tmp_path / "cases.json"), config_path=str(config_path))

    with pytest.raises(ValueError, match="runtime.tasks.segmentation.model_id"):
        service._configured_segmentation_model_id()


def test_analysis_service_creates_fluorescence_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_analysis", title="analysis")
    case = InputService().add_inputs(
        case,
        [
            InputCreateRequest(
                channel=InputChannel.WHITE_LIGHT,
                path=str(Path("tests/fixtures/platform/white.png").resolve()),
            ),
            InputCreateRequest(
                channel=InputChannel.FLUORESCENCE,
                path=str(Path("tests/fixtures/platform/fluorescence.png").resolve()),
            ),
        ],
    )
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(case, [], {"threshold": 0.6}, [])

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.quantitative_summary["positive_area_px"] > 0
    assert Path(run.fused_outputs["outputs"]["overlay_path"]).exists()
    dual_channel_ai = run.fused_outputs["dual_channel_ai"]
    assert dual_channel_ai["available"] is False
    assert dual_channel_ai["execution_state"] == "skipped"
    assert dual_channel_ai["reason"] == "adapter_warmup_unavailable"
    assert dual_channel_ai["traditional_fusion_fallback_available"] is True
    assert "runtime execution disabled by configuration" in dual_channel_ai["adapter_status"]["reasons"]


def test_analysis_service_prefers_latest_input_when_duplicate_channel_assets_exist(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_latest_input", title="latest input")
    service = AnalysisService(repo)
    first = InputService().add_inputs(
        case,
        [InputCreateRequest(channel=InputChannel.VIDEO, path="first.mp4")],
    )
    duplicated = first.model_copy(
        update={
            "inputs": [
                *first.inputs,
                InputService()._asset_from_request(InputCreateRequest(channel=InputChannel.VIDEO, path="latest.mp4")),
            ]
        }
    )

    selected = service._pick_input(duplicated.inputs, InputChannel.VIDEO)

    assert selected is not None
    assert selected.path == "latest.mp4"


def test_analysis_service_requires_explicit_selection_for_multiple_image_pairs(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    service = AnalysisService(repo)
    case = InputService().add_inputs(
        CaseRecord(case_id="case_multiple_pairs", title="multiple pairs"),
        [
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path="white-1.jpg"),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path="fluor-1.jpg"),
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path="white-2.jpg"),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path="fluor-2.jpg"),
        ],
        replace_existing_channels=False,
    )

    _selected, warnings = service._select_inputs(case, [])

    assert warnings[0]["code"] == "multiple_image_inputs_require_explicit_selection"
    assert warnings[0]["blocking"] is True


def test_analysis_service_rejects_selected_images_from_different_admitted_pairs(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    service = AnalysisService(repo)
    case = InputService().add_inputs(
        CaseRecord(case_id="case_mismatched_pair", title="mismatched pair"),
        [
            InputCreateRequest(
                channel=InputChannel.WHITE_LIGHT,
                path="white.jpg",
                metadata={"batch_id": "batch-1", "pair_id": "pair-1"},
            ),
            InputCreateRequest(
                channel=InputChannel.FLUORESCENCE,
                path="fluor.jpg",
                metadata={"batch_id": "batch-1", "pair_id": "pair-2"},
            ),
        ],
    )

    _selected, warnings = service._select_inputs(case, [asset.input_id for asset in case.inputs])

    assert warnings[0]["code"] == "selected_image_pair_mismatch"
    assert warnings[0]["blocking"] is True


def test_analysis_service_accepts_explicit_matching_admitted_pair(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    service = AnalysisService(repo)
    case = InputService().add_inputs(
        CaseRecord(case_id="case_matching_pair", title="matching pair"),
        [
            InputCreateRequest(
                channel=InputChannel.WHITE_LIGHT,
                path="white.jpg",
                metadata={"batch_id": "batch-1", "pair_id": "pair-1"},
            ),
            InputCreateRequest(
                channel=InputChannel.FLUORESCENCE,
                path="fluor.jpg",
                metadata={"batch_id": "batch-1", "pair_id": "pair-1"},
            ),
        ],
    )

    selected, warnings = service._select_inputs(case, [asset.input_id for asset in case.inputs])

    assert [asset.path for asset in selected] == ["white.jpg", "fluor.jpg"]
    assert warnings == []


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
    assert run.fused_outputs["mode"] == "realtime_preview_only"
    assert run.fused_outputs["source_path"] == "camera://browser/default"
    assert run.fused_outputs["stream_ai_connected"] is False
    assert run.fused_outputs["analysis_available"] is False
    assert run.fused_outputs["decision_support_available"] is False
    assert run.warnings[0]["code"] == "realtime_stream_not_connected"
    assert updated.status == "loaded"


def test_video_analysis_uses_segmentation_model_from_runtime_task(tmp_path: Path) -> None:
    config_path = tmp_path / "candidate_runtime.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  tasks:",
                "    segmentation:",
                "      pipeline: segmentation",
                "      model_id: keyframe_candidate",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_runtime_model", title="runtime model")
    repo.create(case)

    updated = AnalysisService(repo, config_path=str(config_path)).start_analysis(
        case,
        [],
        {"mode": "realtime_video", "source_path": "camera://browser/default"},
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.parameters["segmentation_model_id"] == "keyframe_candidate"


def test_realtime_keyframe_analysis_fails_when_strict_runtime_disallows_fallback(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "browser_frame.jpg"
    Image.fromarray(np.full((32, 48, 3), 180, dtype=np.uint8)).save(image_path)
    config_path = _write_no_fallback_runtime_config(tmp_path)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_strict_realtime", title="strict realtime")
    repo.create(case)

    updated = AnalysisService(repo, config_path=str(config_path)).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": "camera://browser/default",
            "browser_frame_paths": [str(image_path)],
            "keyframe_count": 1,
        },
        [],
    )

    run = updated.analysis_runs[-1]
    output = run.fused_outputs["keyframe_segmentations"][0]
    disallowed = next(item for item in run.warnings if item["code"] == "keyframe_heuristic_fallback_disallowed")

    assert run.status == "failed"
    assert run.fused_outputs["analysis_available"] is False
    assert output["analysis_method"] == "trainable_keyframe_segmenter_unavailable"
    assert output["display_allowed"] is False
    assert output["segmentation_mask"]["path"] is None
    assert disallowed["blocking"] is True
    assert not (tmp_path / "visual" / "cases" / case.case_id / "keyframe_segmentations").exists()


def test_mp4_keyframe_analysis_fails_when_strict_runtime_disallows_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "video_frame.jpg"
    Image.fromarray(np.full((32, 48, 3), 180, dtype=np.uint8)).save(image_path)
    config_path = _write_no_fallback_runtime_config(tmp_path)
    monkeypatch.setattr(
        analysis_service_module,
        "_keyframe_report_for_analysis",
        lambda *_args, **_kwargs: {
            "keyframe_count": 1,
            "keyframes": [
                {
                    "order": 1,
                    "frame_index": 0,
                    "timestamp_sec": 0.0,
                    "path": str(image_path),
                    "evidence_path": str(image_path),
                }
            ],
            "warnings": [],
        },
    )
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_strict_mp4", title="strict mp4")
    repo.create(case)

    updated = AnalysisService(repo, config_path=str(config_path)).start_analysis(
        case,
        [],
        {"mode": "video_file", "source_path": str(tmp_path / "input.mp4")},
        [],
    )

    run = updated.analysis_runs[-1]
    output = run.fused_outputs["keyframe_segmentations"][0]

    assert run.status == "failed"
    assert run.fused_outputs["analysis_available"] is False
    assert output["analysis_method"] == "trainable_keyframe_segmenter_unavailable"
    assert output["display_allowed"] is False
    assert any(
        item["code"] == "keyframe_heuristic_fallback_disallowed" and item["blocking"] is True for item in run.warnings
    )


def test_analysis_service_analyzes_uploaded_browser_camera_frame(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    image_path = tmp_path / "browser_frame.jpg"
    Image.fromarray(np.full((48, 64, 3), 180, dtype=np.uint8)).save(image_path)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_browser_frame", title="browser frame")
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": "camera://browser/default",
            "browser_frame_paths": [str(image_path)],
            "segmentation_model_id": "fluorescence_hotspot_2d_segmenter",
            "keyframe_count": 1,
            "live_max_frame_age_ms": 10000,
        },
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "browser_frame_keyframes"
    assert run.fused_outputs["stream_ai_connected"] is True
    assert run.fused_outputs["analysis_available"] is True
    assert run.fused_outputs["live_capture"]["capture_backend"] == "browser_canvas_jpeg_upload"
    assert run.fused_outputs["keyframes"][0]["selection_reason"] == "browser_current_frame_upload"
    assert run.quantitative_summary["live_keyframes_captured"] == 1
    manifest = json.loads(Path(run.fused_outputs["video_segmentation_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["analysis_mode"] == "browser_frame_keyframes"


def test_browser_camera_frame_preserves_capture_session_metadata(tmp_path: Path) -> None:
    image_path = tmp_path / "browser_session_frame.jpg"
    Image.fromarray(np.full((32, 48, 3), 120, dtype=np.uint8)).save(image_path)
    captured_at = datetime.now(timezone.utc).isoformat()
    report = _browser_frame_capture_report(
        [str(image_path)],
        tmp_path / "frame_index_manifest.json",
        max_frames=1,
        captured_at=captured_at,
        session_id="browser-camera-session-1",
        sequence=4,
        trigger="continuous",
    )

    assert report["camera_session_id"] == "browser-camera-session-1"
    assert report["camera_sequence"] == 4
    assert report["capture_trigger"] == "continuous"
    assert report["keyframes"][0]["capture_timestamp"] == captured_at
    assert report["keyframes"][0]["camera_sequence"] == 4


def test_browser_frame_capture_bounds_count_and_deduplicates_evidence_paths(tmp_path: Path) -> None:
    frame_paths: list[str] = []
    for index in range(10):
        image_path = tmp_path / f"browser_frame_{index}.jpg"
        Image.fromarray(np.full((16, 24, 3), 100 + index, dtype=np.uint8)).save(image_path)
        frame_paths.append(str(image_path))

    report = _browser_frame_capture_report(
        [frame_paths[0], frame_paths[0], *frame_paths[1:]],
        tmp_path / "frame_index_manifest.json",
        max_frames=100,
    )

    assert report["configured_max_keyframes"] == 8
    assert report["candidate_frame_count"] == 8
    assert report["frames_read"] == 7
    assert report["frames_dropped"] == 1
    assert [frame["path"] for frame in report["keyframes"]] == [frame_paths[0], *frame_paths[1:7]]
    assert {warning["code"] for warning in report["warnings"]} == {
        "realtime_keyframe_count_bounded",
        "browser_frame_duplicate_ignored",
    }


def test_analysis_service_runs_bounded_live_stream_keyframes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    image_path = tmp_path / "live_frame.jpg"
    Image.fromarray(np.full((48, 64, 3), 180, dtype=np.uint8)).save(image_path)
    frame_manifest_path = tmp_path / "frame_index_manifest.json"
    frame_manifest_path.write_text("{}", encoding="utf-8")

    capture_settings: dict[str, int | float] = {}

    def fake_capture(*_args, **kwargs):
        config = kwargs["config"]
        capture_settings.update(
            {
                "max_keyframes": config.max_keyframes,
                "keyframe_stride": config.keyframe_stride,
                "queue_size": config.queue_size,
                "open_timeout_sec": config.open_timeout_sec,
                "read_timeout_sec": config.read_timeout_sec,
                "capture_timeout_sec": config.capture_timeout_sec,
                "jpeg_quality": config.jpeg_quality,
            }
        )
        return {
            "schema_version": "osteo-vision-live-stream-capture-v1",
            "source_uri": "rtsp://127.0.0.1/live",
            "source_kind": "network_stream",
            "capture_backend": "opencv:test",
            "width": 64,
            "height": 48,
            "fps": 10.0,
            "frame_count": 1,
            "duration_sec": 0.1,
            "frames_read": 1,
            "frames_dropped": 0,
            "frame_index_manifest_path": str(frame_manifest_path),
            "quality_summary": {"frames_saved": 1},
            "warnings": [],
            "keyframes": [
                {
                    "order": 1,
                    "frame_index": 0,
                    "timestamp_sec": 0.0,
                    "capture_timestamp": datetime.now(timezone.utc).isoformat(),
                    "frame_age_ms": 1.0,
                    "path": str(image_path),
                    "evidence_path": str(image_path),
                    "width": 64,
                    "height": 48,
                }
            ],
        }

    monkeypatch.setattr("backend.src.services.analysis_service.capture_live_keyframes", fake_capture)
    write_counts = {"segmentation": 0, "details": 0}
    original_segmentation_writer = analysis_service_module._write_video_segmentation_outputs
    original_details_writer = analysis_service_module._write_video_frame_details_manifest

    def counted_segmentation_writer(*args, **kwargs):
        write_counts["segmentation"] += 1
        return original_segmentation_writer(*args, **kwargs)

    def counted_details_writer(*args, **kwargs):
        write_counts["details"] += 1
        return original_details_writer(*args, **kwargs)

    monkeypatch.setattr(analysis_service_module, "_write_video_segmentation_outputs", counted_segmentation_writer)
    monkeypatch.setattr(analysis_service_module, "_write_video_frame_details_manifest", counted_details_writer)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_live_stream", title="live stream")
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": "rtsp://127.0.0.1/live",
            "segmentation_model_id": "fluorescence_hotspot_2d_segmenter",
            "keyframe_count": 99,
            "live_keyframe_stride": "invalid",
            "live_queue_size": 99,
            "live_open_timeout_sec": "nan",
            "live_read_timeout_sec": 0,
            "live_capture_timeout_sec": 999,
            "live_jpeg_quality": -3,
            "live_max_frame_age_ms": 10000,
        },
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "realtime_stream_keyframes"
    assert run.fused_outputs["stream_ai_connected"] is True
    assert run.fused_outputs["analysis_available"] is True
    assert run.quantitative_summary["live_keyframes_captured"] == 1
    assert run.quantitative_summary["live_frame_age_gate"]["displayable_frame_count"] == 1
    assert capture_settings == {
        "max_keyframes": 8,
        "keyframe_stride": 15,
        "queue_size": 8,
        "open_timeout_sec": 5.0,
        "read_timeout_sec": 0.1,
        "capture_timeout_sec": 30.0,
        "jpeg_quality": 1,
    }
    assert run.fused_outputs["live_capture"]["configured_max_keyframes"] == 8
    assert {
        "realtime_keyframe_count_bounded",
        "realtime_live_keyframe_stride_invalid",
        "realtime_live_queue_size_bounded",
        "realtime_live_open_timeout_sec_invalid",
        "realtime_live_read_timeout_sec_bounded",
        "realtime_live_capture_timeout_sec_bounded",
        "realtime_live_jpeg_quality_bounded",
    }.issubset({item["code"] for item in run.warnings})
    manifest_path = Path(run.fused_outputs["video_segmentation_manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["analysis_mode"] == "realtime_stream_keyframes"
    assert manifest["summary"]["analysis_scope"] == "bounded_live_stream_keyframes_video_signal_segmentation"
    assert write_counts == {"segmentation": 1, "details": 1}


def test_live_frame_age_gate_fails_closed_for_unmatched_output() -> None:
    keyframes = [
        {
            "order": 1,
            "frame_index": 8,
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_age_ms": 1.0,
        }
    ]
    outputs = [{"frame_order": 9, "frame_index": 99}]

    summary = _apply_live_frame_age_gate(
        keyframes,
        outputs,
        max_frame_age_ms=1000.0,
    )

    assert outputs[0]["display_allowed"] is False
    assert outputs[0]["stale"] is True
    assert outputs[0]["frame_age_gate_reason"] == "unmatched_capture_frame"
    assert outputs[0]["max_frame_age_ms"] == 1000.0
    assert summary["unmatched_output_count"] == 1
    assert summary["displayable_output_count"] == 0


def test_live_frame_age_gate_rejects_missing_or_conflicting_identity() -> None:
    now = datetime.now(timezone.utc).isoformat()
    keyframes = [
        {"order": 1, "frame_index": 10, "capture_timestamp": now},
        {"order": 2, "frame_index": 20, "capture_timestamp": now},
    ]
    outputs = [
        {"frame_order": 1, "frame_index": 20},
        {"model_id": "missing_identity"},
    ]

    summary = _apply_live_frame_age_gate(
        keyframes,
        outputs,
        max_frame_age_ms=1000.0,
    )

    assert outputs[0]["display_allowed"] is False
    assert outputs[0]["frame_age_gate_reason"] == "frame_identity_conflict"
    assert outputs[1]["display_allowed"] is False
    assert outputs[1]["frame_age_gate_reason"] == "unmatched_capture_frame"
    assert summary["unmatched_output_count"] == 2


def test_realtime_analysis_fails_when_all_results_are_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    image_path = tmp_path / "stale_frame.jpg"
    Image.fromarray(np.full((32, 48, 3), 180, dtype=np.uint8)).save(image_path)
    frame_manifest_path = tmp_path / "frame_index_manifest.json"
    frame_manifest_path.write_text("{}", encoding="utf-8")

    def fake_capture(*_args, **_kwargs):
        return {
            "schema_version": "osteo-vision-live-stream-capture-v1",
            "source_uri": "rtsp://127.0.0.1/stale",
            "source_kind": "network_stream",
            "capture_backend": "opencv:test",
            "width": 48,
            "height": 32,
            "fps": 10.0,
            "frames_read": 1,
            "frames_dropped": 0,
            "frame_index_manifest_path": str(frame_manifest_path),
            "quality_summary": {"frames_saved": 1},
            "warnings": [],
            "keyframes": [
                {
                    "order": 1,
                    "frame_index": 0,
                    "timestamp_sec": 0.0,
                    "capture_timestamp": "2000-01-01T00:00:00+00:00",
                    "frame_age_ms": 1.0,
                    "path": str(image_path),
                    "evidence_path": str(image_path),
                    "width": 48,
                    "height": 32,
                }
            ],
        }

    monkeypatch.setattr("backend.src.services.analysis_service.capture_live_keyframes", fake_capture)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_stale_stream", title="stale stream")
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": "rtsp://127.0.0.1/stale",
            "segmentation_model_id": "fluorescence_hotspot_2d_segmenter",
            "live_max_frame_age_ms": 1000,
        },
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "failed"
    assert run.fused_outputs["analysis_available"] is False
    assert run.fused_outputs["decision_support_available"] is False
    assert run.candidate_regions == []
    assert updated.status == "draft"
    assert any(item["code"] == "all_live_results_stale" for item in run.warnings)
    manifest = json.loads(Path(run.fused_outputs["video_segmentation_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["summary"]["analysis_available"] is False
    assert manifest["summary"]["selected_frame_count"] == 0


def test_realtime_exception_is_persisted_as_failed_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    def failed_capture(*_args, **_kwargs):
        raise OSError("capture write failed")

    monkeypatch.setattr("backend.src.services.analysis_service.capture_live_keyframes", failed_capture)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_failed_stream", title="failed stream")
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": "rtsp://127.0.0.1/fail",
        },
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "failed"
    assert updated.status == "draft"
    assert run.warnings[-1]["code"] == "realtime_analysis_failed"
    assert run.warnings[-1]["error_type"] == "OSError"
    assert repo.get(case.case_id).analysis_runs[-1].status == "failed"


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
        [
            {
                "order": 1,
                "frame_index": 0,
                "timestamp_sec": 0.0,
                "evidence_path": str(image_path),
            }
        ],
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
    assert Path(outputs[0]["lesion_evidence"]["uncertainty_path"]).exists()
    assert Path(outputs[0]["lesion_evidence"]["overlay_path"]).exists()
    assert outputs[0]["review_priority"] == "high"
    assert outputs[0]["target_domain_flag"] is False
    assert outputs[0]["quantification"]["positive_area_px"] > 0


def test_keyframe_segmentation_falls_back_when_trainable_mask_is_empty(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "keyframe_empty.pt"
    model = TinyKeyframeSegmenter2D(base_channels=2)
    torch.save(
        {
            "model_id": "keyframe_empty",
            "model_family": "convnext2d_keyframe_segmenter",
            "model_config": {"in_channels": 3, "out_channels": 2, "base_channels": 2},
            "state_dict": model.state_dict(),
            "threshold": 1.1,
        },
        checkpoint_path,
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: keyframe_empty",
                "      family: convnext2d_keyframe_segmenter",
                "      task_types: [segmentation]",
                "      input_types: [2d_image]",
                f"      checkpoint_path: {json.dumps(str(checkpoint_path))}",
                "      dependency_group: torch",
                "      device_policy: cpu",
                "      extra:",
                "        threshold: 1.1",
            ]
        ),
        encoding="utf-8",
    )
    image_path = tmp_path / "frame.png"
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 16:36, 1] = 245
    Image.fromarray(image).save(image_path)

    outputs = _analyze_keyframe_segmentations(
        [
            {
                "order": 1,
                "frame_index": 0,
                "timestamp_sec": 0.0,
                "evidence_path": str(image_path),
            }
        ],
        tmp_path / "segmentation_outputs",
        case_id="case_video",
        config_path=str(config_path),
        model_id="keyframe_empty",
        threshold=0.6,
        colormap="green",
        roi_hints=[],
    )

    assert outputs[0]["analysis_method"] == "heuristic_hotspot_fallback"
    assert outputs[0]["model_id"] == "video_keyframe_hotspot_segmenter"
    assert outputs[0]["quantification"]["positive_area_px"] > 0
    assert any(item["code"] == "keyframe_segmenter_empty_mask_fallback" for item in outputs[0]["warnings"])
