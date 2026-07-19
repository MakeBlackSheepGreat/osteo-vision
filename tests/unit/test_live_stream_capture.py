from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.io.live_stream import LiveStreamCaptureConfig, capture_live_keyframes


def _write_video(path: Path, *, frame_count: int = 12, fps: float = 10.0) -> None:
    fourcc = getattr(cv2, "VideoWriter_fourcc")(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (96, 64))
    assert writer.isOpened()
    for frame_index in range(frame_count):
        frame = np.full((64, 96, 3), 20 + frame_index, dtype=np.uint8)
        frame[16:48, 24:72, 1] = min(255, 80 + frame_index * 10)
        writer.write(frame)
    writer.release()


def test_capture_local_video_saves_bounded_keyframes_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "stream.mp4"
    _write_video(source)

    report = capture_live_keyframes(
        str(source),
        tmp_path / "frames",
        config=LiveStreamCaptureConfig(max_keyframes=3, keyframe_stride=2, queue_size=16),
    )

    assert report["source_uri"] == str(source)
    assert report["capture_backend"].startswith("opencv:")
    assert report["width"] == 96
    assert report["height"] == 64
    assert report["fps"] > 0
    assert report["frames_read"] >= 5
    assert report["frames_dropped"] >= 0
    assert report["keyframe_count"] == 3
    assert [item["frame_index"] for item in report["keyframes"]] == [0, 2, 4]
    for item in report["keyframes"]:
        assert Path(item["path"]).is_file()
        assert item["evidence_path"] == item["path"]
        assert item["timestamp_sec"] >= 0
        assert item["capture_timestamp"]
        assert item["frame_age_ms"] >= 0
        assert item["selection_reason"] == "live_stream_stride"
        assert item["width"] == 96
        assert item["height"] == 64
    assert report["quality_summary"]["frames_saved"] == 3
    assert Path(report["frame_index_manifest_path"]).is_file()


def test_capture_open_failure_returns_blocking_warning(tmp_path: Path) -> None:
    unreadable_video = tmp_path / "unreadable.mp4"
    unreadable_video.write_text("invalid video payload", encoding="utf-8")

    report = capture_live_keyframes(str(unreadable_video), tmp_path / "frames")

    assert report["keyframe_count"] == 0
    assert report["warnings"][0]["code"] == "capture_open_failed"
    assert report["warnings"][0]["blocking"] is True


def test_browser_camera_source_is_explicitly_rejected(tmp_path: Path) -> None:
    report = capture_live_keyframes("camera://browser/default", tmp_path / "frames")

    assert report["keyframe_count"] == 0
    assert report["warnings"][0]["code"] == "browser_camera_source_rejected"
    assert report["warnings"][0]["blocking"] is True


def test_capture_read_timeout_and_frame_age_metadata(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    source = tmp_path / "slow_stream.mp4"
    _write_video(source, frame_count=4)
    real_video_capture = cv2.VideoCapture

    class SlowCapture:
        def __init__(self) -> None:
            self._capture = real_video_capture()

        def set(self, property_id: int, value: float) -> bool:
            return bool(self._capture.set(property_id, value))

        def open(self, value: int | str) -> bool:
            return bool(self._capture.open(value))

        def isOpened(self) -> bool:
            return bool(self._capture.isOpened())

        def get(self, property_id: int) -> float:
            return float(self._capture.get(property_id))

        def getBackendName(self) -> str:
            return str(self._capture.getBackendName())

        def read(self) -> tuple[bool, Any]:
            time.sleep(0.08)
            return self._capture.read()

        def release(self) -> None:
            self._capture.release()

    monkeypatch.setattr(cv2, "VideoCapture", SlowCapture)
    report = capture_live_keyframes(
        str(source),
        tmp_path / "frames",
        config=LiveStreamCaptureConfig(
            max_keyframes=2,
            queue_size=2,
            read_timeout_sec=0.02,
            capture_timeout_sec=0.5,
        ),
    )

    assert report["keyframe_count"] == 0
    assert any(item["code"] == "capture_read_timeout" for item in report["warnings"])
    assert report["frames_read"] == 0


def test_capture_frame_age_is_recorded_for_successful_slow_stream(tmp_path: Path) -> None:
    source = tmp_path / "aged_stream.mp4"
    _write_video(source, frame_count=6)

    report = capture_live_keyframes(
        str(source),
        tmp_path / "frames",
        config=LiveStreamCaptureConfig(max_keyframes=2, queue_size=6, read_timeout_sec=1.0),
    )

    assert report["keyframe_count"] == 2
    assert all(isinstance(item["frame_age_ms"], float) for item in report["keyframes"])
    assert all(item["frame_age_ms"] >= 0.0 for item in report["keyframes"])
