from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.preprocess.video import extract_keyframes


def _write_signal_video(path: Path, *, signal_frame: int = 8) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (96, 64))
    for index in range(12):
        frame = np.full((64, 96, 3), 24, dtype=np.uint8)
        if index == signal_frame:
            frame[18:46, 28:68, 1] = 255
            frame[18:46, 28:68, 0] = 18
            frame[18:46, 28:68, 2] = 18
        writer.write(frame)
    writer.release()


def test_quality_peak_keyframes_prioritize_signal_frame(tmp_path: Path) -> None:
    video = tmp_path / "signal.mp4"
    _write_signal_video(video, signal_frame=8)

    report = extract_keyframes(video, tmp_path / "quality", max_frames=3, sampling_strategy="quality_peak")

    indexes = [frame["frame_index"] for frame in report["keyframes"]]
    assert report["sampling_strategy"] == "quality_peak"
    assert 8 in indexes
    assert report["quality_summary"]["selection_score_max"] is not None
    assert report["selection_trace"]["candidate_frame_count"] >= 3
    assert Path(report["keyframe_manifest_path"]).exists()
    frame_index_manifest = Path(report["frame_index_manifest_path"])
    assert frame_index_manifest.exists()
    frame_index_payload = json.loads(frame_index_manifest.read_text(encoding="utf-8"))
    assert frame_index_payload["schema_version"] == "osteo-vision-frame-index-manifest-v1"
    assert frame_index_payload["frame_index_scope"] == "selected_keyframes_with_candidate_trace"
    assert frame_index_payload["selected_frame_count"] == 3
    assert frame_index_payload["candidate_frame_count"] >= 3
    assert frame_index_payload["deduplication"]["enabled"] is True
    assert frame_index_payload["frames"][0]["evidence_path"]
    timeline_manifest = Path(report["timeline_manifest_path"])
    assert timeline_manifest.exists()
    timeline_payload = json.loads(timeline_manifest.read_text(encoding="utf-8"))
    assert timeline_payload["schema_version"] == "osteo-vision-video-timeline-manifest-v1"
    assert timeline_payload["timeline_scope"] == "full_duration_index_with_scored_candidates"
    assert timeline_payload["coverage"]["selected_frame_count"] == 3


def test_uniform_keyframes_remain_available(tmp_path: Path) -> None:
    video = tmp_path / "uniform.mp4"
    _write_signal_video(video, signal_frame=8)

    report = extract_keyframes(video, tmp_path / "uniform", max_frames=3, sampling_strategy="uniform")

    assert report["sampling"] == "uniform"
    assert [frame["frame_index"] for frame in report["keyframes"]] == [0, 6, 11]
    assert Path(report["frame_index_manifest_path"]).exists()
    assert Path(report["timeline_manifest_path"]).exists()


def test_quality_peak_marks_duplicate_candidate_frames(tmp_path: Path) -> None:
    video = tmp_path / "duplicates.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (96, 64))
    for index in range(12):
        frame = np.full((64, 96, 3), 24, dtype=np.uint8)
        if index == 6:
            frame[18:46, 28:68, 1] = 255
            frame[18:46, 28:68, 0] = 18
            frame[18:46, 28:68, 2] = 18
        writer.write(frame)
    writer.release()

    report = extract_keyframes(
        video,
        tmp_path / "duplicates",
        max_frames=3,
        sampling_strategy="quality_peak",
        candidate_pool_size=12,
        min_frame_gap=1,
    )

    indexes = [frame["frame_index"] for frame in report["keyframes"]]
    assert 6 in indexes
    dedup = report["selection_trace"]["deduplication"]
    assert dedup["enabled"] is True
    assert dedup["duplicate_candidate_count"] >= 1
    timeline = json.loads(Path(report["timeline_manifest_path"]).read_text(encoding="utf-8"))
    duplicate_frames = [frame for frame in timeline["frames"] if frame.get("skipped_as_duplicate")]
    assert duplicate_frames


def test_manual_requested_timestamps_select_expected_frames(tmp_path: Path) -> None:
    video = tmp_path / "manual.mp4"
    _write_signal_video(video, signal_frame=8)

    report = extract_keyframes(
        video,
        tmp_path / "manual",
        max_frames=3,
        requested_timestamps_sec=[0.2, 0.8, 99.0],
    )

    assert report["sampling_strategy"] == "manual"
    assert [frame["frame_index"] for frame in report["keyframes"]] == [2, 8, 11]
    assert report["selection_trace"]["manual_selection_applied"] is True
    assert report["selection_trace"]["requested_timestamps_sec"] == [0.2, 0.8, 99.0]


def test_manual_requested_frame_indexes_are_deduplicated_and_clipped(tmp_path: Path) -> None:
    video = tmp_path / "manual_indexes.mp4"
    _write_signal_video(video, signal_frame=8)

    report = extract_keyframes(
        video,
        tmp_path / "manual_indexes",
        max_frames=4,
        requested_frame_indexes=[-4, 5, 5, 99],
    )

    assert report["sampling"] == "manual"
    assert [frame["frame_index"] for frame in report["keyframes"]] == [0, 5, 11]
