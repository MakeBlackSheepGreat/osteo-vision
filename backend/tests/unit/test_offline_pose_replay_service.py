from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import backend.src.services.offline_pose_replay_service as replay_service


def test_decode_video_skips_opencv_timestamp_collection_when_pts_are_verified(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Capture:
        def __init__(self) -> None:
            self.index = 0
            self.released = False

        def isOpened(self) -> bool:
            return True

        def get(self, property_id: int) -> float:
            values = {
                cv2.CAP_PROP_FRAME_COUNT: 3,
                cv2.CAP_PROP_FPS: 10.0,
                cv2.CAP_PROP_FRAME_WIDTH: 6,
                cv2.CAP_PROP_FRAME_HEIGHT: 4,
            }
            if property_id == cv2.CAP_PROP_POS_MSEC:
                raise AssertionError("verified PTS path must not request OpenCV frame timestamps")
            return values[property_id]

        def read(self) -> tuple[bool, np.ndarray | None]:
            if self.index >= 3:
                return False, None
            self.index += 1
            return True, np.zeros((4, 6, 3), dtype=np.uint8)

        def release(self) -> None:
            self.released = True

    capture = Capture()
    monkeypatch.setattr(replay_service.cv2, "VideoCapture", lambda _path: capture)
    monkeypatch.setattr(
        replay_service,
        "_ffprobe_frame_timestamps",
        lambda _path: ([0.0, 0.1, 0.2], None),
    )

    result = replay_service._decode_video(tmp_path / "admitted.mp4")

    assert capture.released is True
    assert result["timestamps_s"] == [0.0, 0.1, 0.2]
    assert result["timestamps_verified"] is True
    assert result["timestamp_source"] == "ffprobe_best_effort_timestamp_time"


def test_frames_csv_write_is_atomic_and_returns_replay_summary(tmp_path) -> None:
    path = tmp_path / "pose_replay_frames.csv"
    path.write_text("previous evidence\n", encoding="utf-8")

    with pytest.raises(AttributeError):
        replay_service._write_frames_csv(
            path,
            [object()],
            global_navigation_ready=True,
            poses=[],
        )

    assert path.read_text(encoding="utf-8") == "previous evidence\n"
    assert not path.with_suffix(".csv.part").exists()

    frame = SimpleNamespace(
        frame_index=2,
        frame_timestamp_s=0.2,
        pose_index=0,
        pose_timestamp_s=0.2,
        time_offset_ms=-3.0,
        intrinsics_id="scope_4x",
        magnification=4.0,
        working_distance_mm=250.0,
        magnification_rate_per_s=1.5,
        working_distance_rate_mm_per_s=12.0,
        intrinsics_switched=False,
        intrinsics_switch_rate_hz=None,
        calibration_candidate_count=1,
        calibration_selection_distance=0.0,
        calibration_selection_ambiguous=False,
        drift_proxy_mm=0.4,
        tre_proxy_mm=0.5,
        dynamic_target_error_mm=0.6,
        projected_point_count=4,
        visible_projected_point_count=3,
        navigation_ready=True,
        failure_reasons=[],
        projected_points_px=[[1.0, 2.0]],
        composed_transform=[[1.0, 0.0, 0.0, 0.0]],
    )

    summary = replay_service._write_frames_csv(
        path,
        [frame],
        global_navigation_ready=True,
        poses=[{"magnification": 4.0, "working_distance_mm": 250.0}],
    )

    assert path.read_text(encoding="utf-8").startswith("frame_index,")
    assert not path.with_suffix(".csv.part").exists()
    assert summary["worst_frame"] is frame
    assert summary["max_dynamic_target_error_mm"] == 0.6
    assert summary["max_drift_mm"] == 0.4
    assert summary["minimum_visible_projected_count"] == 3
    assert summary["selected_intrinsics_ids"] == ["scope_4x"]
    assert summary["per_frame"] == [
        {
            "frame_index": 2,
            "pose_index": 0,
            "intrinsics_id": "scope_4x",
            "magnification": 4.0,
            "working_distance_mm": 250.0,
            "magnification_rate_per_s": 1.5,
            "working_distance_rate_mm_per_s": 12.0,
            "intrinsics_switched": False,
            "intrinsics_switch_rate_hz": None,
            "candidate_count": 1,
            "selection_distance": 0.0,
            "ambiguous": False,
            "failure_reasons": [],
        }
    ]
