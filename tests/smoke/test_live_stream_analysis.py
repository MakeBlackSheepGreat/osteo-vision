from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord
from backend.osteo_vision_api.services.analysis_service import AnalysisService


def test_local_stream_runs_bounded_capture_and_keyframe_analysis(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    video_path = tmp_path / "live_source.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (96, 64))
    for index in range(24):
        frame = np.zeros((64, 96, 3), dtype=np.uint8)
        frame[:, :, 1] = min(255, 40 + index * 6)
        cv2.circle(frame, (20 + index * 2, 32), 10, (20, 220, 60), -1)
        writer.write(frame)
    writer.release()

    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="live_stream_smoke", title="bounded live stream smoke")
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {
            "mode": "realtime_video",
            "source_path": str(video_path),
            "segmentation_model_id": "fluorescence_hotspot_2d_segmenter",
            "keyframe_count": 3,
            "live_keyframe_stride": 3,
            "live_capture_timeout_sec": 5.0,
            "live_read_timeout_sec": 1.0,
            "live_max_frame_age_ms": 30000,
        },
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "realtime_stream_keyframes"
    assert run.fused_outputs["live_capture"]["source_kind"] == "local_video"
    assert run.quantitative_summary["live_keyframes_captured"] == 3
    assert run.quantitative_summary["live_frames_read"] >= 3
    assert run.quantitative_summary["live_frame_age_gate"]["displayable_frame_count"] == 3
    assert len(run.fused_outputs["keyframe_segmentation_outputs"]) == 3
    manifest_path = Path(run.fused_outputs["video_segmentation_manifest_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["analysis_mode"] == "realtime_stream_keyframes"
    assert payload["summary"]["selected_frame_count"] == 3
