from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app
from backend.osteo_vision_api.domains.cases.schemas import MultichannelVideoChannel, MultichannelVideoSession
from backend.osteo_vision_api.services import multichannel_video_service


def _write_video(path, *, fps: float, frame_count: int, value: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for index in range(frame_count):
        writer.write(np.full((48, 64, 3), min(255, value + index), dtype=np.uint8))
    writer.release()


def _jpeg_data_url(value: int) -> str:
    ok, encoded = cv2.imencode(".jpg", np.full((48, 64, 3), value, dtype=np.uint8))
    assert ok
    return f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}"


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(tmp_path / "missing-videos.csv"))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(tmp_path / "missing-ofdvdnet.csv"))
    client = TestClient(create_app())
    case = client.post("/cases", json={"title": "paired video test"}).json()
    return client, case["case_id"], artifact_root


def test_paired_video_session_builds_common_interval_and_task2_manifest(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    overlay = artifact_root / "overlay.mp4"
    _write_video(white, fps=10.0, frame_count=30, value=40)
    _write_video(fluorescence, fps=8.0, frame_count=20, value=80)
    _write_video(overlay, fps=5.0, frame_count=15, value=120)

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
            "device_overlay_path": str(overlay),
            "fluorescence_offset_ms": 100,
            "device_overlay_offset_ms": -100,
            "keyframe_count": 4,
            "focus_timepoints_sec": [0.5],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["analysis_allowed"] is True
    assert payload["common_start_sec"] == 0.1
    assert payload["common_end_sec"] == 2.4
    assert len(payload["paired_sequence_manifest"]["frames"]) == 4
    assert {item["role"] for item in payload["channels"]} == {
        "white_light",
        "fluorescence",
        "device_overlay",
    }
    restored = client.get(
        f"/cases/{case_id}/multichannel-video-sessions/{payload['session_id']}",
    )
    assert restored.status_code == 200
    assert restored.json()["session_id"] == payload["session_id"]
    case = client.get(f"/cases/{case_id}").json()
    assert case["review_summary"]["multichannel_session_id"] == payload["session_id"]
    paired_assets = [item for item in case["inputs"] if item["metadata"].get("source") == "multichannel_video_keyframe"]
    assert len(paired_assets) == 12


def test_realtime_frame_runs_one_formal_task2_pair_without_batching_the_sequence(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=8.0, frame_count=24, value=40)
    _write_video(fluorescence, fps=8.0, frame_count=24, value=90)
    session = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
            "keyframe_count": 3,
        },
    ).json()

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions/{session['session_id']}/realtime-frame",
        json={"timestamp_sec": 0.6, "alpha": 0.45, "threshold": 0.6, "colormap": "green"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frame"]["frame_index"] in {0, 1, 2}
    assert len(payload["frame"]["performance"]) > 0
    assert Path(payload["frame"]["overlay_path"]).is_file()
    assert payload["compute_ms"] == payload["frame"]["performance"]["registration_fusion_compute_ms"]


def test_realtime_frame_uses_current_browser_pair_instead_of_nearest_offline_keyframe(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=8.0, frame_count=24, value=40)
    _write_video(fluorescence, fps=8.0, frame_count=24, value=90)
    session = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
            "keyframe_count": 3,
        },
    ).json()

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions/{session['session_id']}/realtime-frame",
        json={
            "timestamp_sec": 1.125,
            "alpha": 0.45,
            "threshold": 0.6,
            "colormap": "green",
            "white_frame_base64": _jpeg_data_url(40),
            "fluorescence_frame_base64": _jpeg_data_url(90),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frame_source"] == "browser_current_frame"
    assert payload["source_timestamp_sec"] == 1.125
    assert payload["frame"]["white_input_id"].endswith("live:white_light")
    assert payload["frame"]["normalized_path"] is None
    assert payload["frame"]["pseudocolor_path"] is None
    assert payload["frame"]["device_overlay_difference_path"] is None
    assert Path(payload["frame"]["overlay_path"]).is_file()


def test_browser_camera_session_requires_and_processes_two_current_frames(tmp_path, monkeypatch) -> None:
    client, case_id, _artifact_root = _client(tmp_path, monkeypatch)
    session_response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={"mode": "browser_cameras", "synchronization_tolerance_ms": 33.34},
    )

    assert session_response.status_code == 200
    session = session_response.json()
    assert session["mode"] == "browser_cameras"
    assert session["analysis_allowed"] is True
    assert session["synchronization_status"] == "review_required"
    assert session["paired_sequence_manifest"] is None
    assert [channel["path"] for channel in session["channels"]] == [
        "browser://white-light",
        "browser://fluorescence",
    ]

    missing_both = client.post(
        f"/cases/{case_id}/multichannel-video-sessions/{session['session_id']}/realtime-frame",
        json={"timestamp_sec": 0.0},
    )
    assert missing_both.status_code == 422
    assert missing_both.json()["detail"]["code"] == "multichannel_realtime_frame_pair_required"

    missing_pair = client.post(
        f"/cases/{case_id}/multichannel-video-sessions/{session['session_id']}/realtime-frame",
        json={
            "timestamp_sec": 0.0,
            "white_frame_base64": _jpeg_data_url(40),
        },
    )
    assert missing_pair.status_code == 422
    assert missing_pair.json()["detail"]["code"] == "multichannel_realtime_frame_pair_required"

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions/{session['session_id']}/realtime-frame",
        json={
            "timestamp_sec": 0.25,
            "alpha": 0.45,
            "threshold": 0.6,
            "colormap": "green",
            "white_frame_base64": _jpeg_data_url(40),
            "fluorescence_frame_base64": _jpeg_data_url(90),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["frame_source"] == "browser_current_frame"
    assert payload["source_timestamp_sec"] == 0.25
    assert Path(payload["frame"]["overlay_path"]).is_file()
    case = client.get(f"/cases/{case_id}").json()
    assert case["inputs"] == []
    assert case["review_summary"]["multichannel_video_mode"] == "browser_cameras"


def test_browser_camera_session_rejects_file_backed_inputs(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    stale_video = artifact_root / "stale.mp4"
    _write_video(stale_video, fps=5.0, frame_count=5, value=80)

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "browser_cameras",
            "video_path": str(stale_video),
        },
    )

    assert response.status_code == 422


def test_single_video_session_keeps_the_existing_analysis_path(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    video = artifact_root / "single.mp4"
    _write_video(video, fps=8.0, frame_count=16, value=40)

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={"mode": "single_video", "video_path": str(video)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["analysis_allowed"] is False
    assert payload["channels"][0]["role"] == "video"
    assert payload["warnings"][0]["code"] == "single_video_uses_existing_analysis_path"


def test_paired_video_session_blocks_when_offsets_remove_common_interval(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=5.0, frame_count=5, value=30)
    _write_video(fluorescence, fps=5.0, frame_count=5, value=60)

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
            "fluorescence_offset_ms": 5000,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["analysis_allowed"] is False
    assert payload["failure_reasons"] == ["multichannel_no_common_interval"]


def test_cached_session_becomes_the_case_active_session_again(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=8.0, frame_count=24, value=30)
    _write_video(fluorescence, fps=8.0, frame_count=24, value=60)
    base_request = {
        "mode": "paired_videos",
        "white_light_path": str(white),
        "fluorescence_path": str(fluorescence),
        "keyframe_count": 3,
    }

    automatic = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={**base_request, "fluorescence_offset_ms": None},
    ).json()
    adjusted = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={**base_request, "fluorescence_offset_ms": 100},
    ).json()
    restored = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={**base_request, "fluorescence_offset_ms": None},
    ).json()

    assert automatic["session_id"] != adjusted["session_id"]
    assert restored["session_id"] == automatic["session_id"]
    case = client.get(f"/cases/{case_id}").json()
    assert case["review_summary"]["multichannel_session_id"] == automatic["session_id"]


def test_paired_video_session_blocks_a_damaged_channel(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "damaged.mp4"
    _write_video(white, fps=8.0, frame_count=16, value=30)
    fluorescence.write_bytes(b"not-an-mp4")

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["analysis_allowed"] is False
    assert payload["failure_reasons"] in [
        ["multichannel_input_invalid"],
        ["multichannel_video_unreadable"],
    ]


def test_blocked_session_is_recomputed_after_the_input_is_fixed(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=8.0, frame_count=16, value=30)
    fluorescence.write_bytes(b"not-an-mp4")
    request = {
        "mode": "paired_videos",
        "white_light_path": str(white),
        "fluorescence_path": str(fluorescence),
        "keyframe_count": 3,
    }

    blocked = client.post(f"/cases/{case_id}/multichannel-video-sessions", json=request).json()
    assert blocked["status"] == "blocked"
    _write_video(fluorescence, fps=8.0, frame_count=16, value=60)

    retried = client.post(f"/cases/{case_id}/multichannel-video-sessions", json=request)

    assert retried.status_code == 200
    payload = retried.json()
    assert payload["session_id"] == blocked["session_id"]
    assert payload["status"] == "ready"
    assert payload["analysis_allowed"] is True


def test_unavailable_degraded_composite_session_is_recomputed_on_retry(tmp_path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    source = artifact_root / "composite.mp4"
    _write_video(source, fps=5.0, frame_count=10, value=70)
    manifest = tmp_path / "ofdvdnet.csv"
    manifest.write_text(
        "record_id,dataset_id,video_path,original_filename,view_layout,overlay_xyxy,"
        "fluorescence_xyxy,reference_xyxy,readable,domain_boundary\n"
        f"OFDVDNET_001,D046,{source},sample.mp4,three_views,0|0|32|24,32|0|64|24,"
        "0|24|32|48,True,public proxy\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(tmp_path / "missing-videos.csv"))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(multichannel_video_service, "find_runtime_executable", lambda _name: None)
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "composite retry"}).json()["case_id"]
    request = {"mode": "composite_layout", "composite_record_id": "OFDVDNET_001"}

    degraded = client.post(f"/cases/{case_id}/multichannel-video-sessions", json=request).json()
    assert degraded["status"] == "degraded"
    assert degraded["analysis_allowed"] is False

    def fake_paired(self, case, _request, session_id, _session_dir):
        channels = [
            MultichannelVideoChannel(
                role=role,
                input_id=f"{session_id}:{role}",
                path=str(source),
                probe={"readable": True, "duration_sec": 2.0},
                source_boundary="test",
            )
            for role in ("white_light", "fluorescence", "device_overlay")
        ]
        return (
            MultichannelVideoSession(
                schema_version="osteo-vision-multichannel-video-session-v1",
                session_id=session_id,
                case_id=case.case_id,
                mode="composite_layout",
                status="ready",
                analysis_allowed=True,
                channels=channels,
                synchronization_tolerance_ms=33.34,
                synchronization_status="aligned",
                source_boundary="test",
            ),
            case,
        )

    monkeypatch.setattr(multichannel_video_service.MultichannelVideoService, "_paired_session", fake_paired)
    retried = client.post(f"/cases/{case_id}/multichannel-video-sessions", json=request)

    assert retried.status_code == 200
    payload = retried.json()
    assert payload["session_id"] == degraded["session_id"]
    assert payload["status"] == "ready"
    assert payload["analysis_allowed"] is True


def test_partial_pair_extraction_keeps_a_degraded_analyzable_session(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    fluorescence = artifact_root / "fluorescence.mp4"
    _write_video(white, fps=8.0, frame_count=24, value=30)
    _write_video(fluorescence, fps=8.0, frame_count=24, value=60)
    original_extract = multichannel_video_service._extract_video_frame

    def fail_one_white_frame(source, time_sec, output):
        if output.name == "001_white_light.jpg":
            return False
        return original_extract(source, time_sec, output)

    monkeypatch.setattr(multichannel_video_service, "_extract_video_frame", fail_one_white_frame)
    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={
            "mode": "paired_videos",
            "white_light_path": str(white),
            "fluorescence_path": str(fluorescence),
            "keyframe_count": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["analysis_allowed"] is True
    assert len(payload["paired_sequence_manifest"]["frames"]) == 3
    assert any(item["code"] == "multichannel_keyframe_extract_failed" for item in payload["warnings"])


def test_multichannel_request_rejects_missing_fluorescence_video(tmp_path, monkeypatch) -> None:
    client, case_id, artifact_root = _client(tmp_path, monkeypatch)
    white = artifact_root / "white.mp4"
    _write_video(white, fps=5.0, frame_count=5, value=30)

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={"mode": "paired_videos", "white_light_path": str(white)},
    )

    assert response.status_code == 422


def test_composite_session_keeps_original_video_when_ffmpeg_is_unavailable(tmp_path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    source = artifact_root / "composite.mp4"
    _write_video(source, fps=5.0, frame_count=10, value=70)
    manifest = tmp_path / "ofdvdnet.csv"
    manifest.write_text(
        "record_id,dataset_id,video_path,original_filename,view_layout,overlay_xyxy,"
        "fluorescence_xyxy,reference_xyxy,readable,domain_boundary\n"
        f"OFDVDNET_001,D046,{source},sample.mp4,three_views,0|0|32|24,32|0|64|24,"
        "0|24|32|48,True,public proxy\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(tmp_path / "missing-videos.csv"))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(
        "backend.osteo_vision_api.services.multichannel_video_service.find_runtime_executable",
        lambda _name: None,
    )
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "composite fallback"}).json()["case_id"]

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={"mode": "composite_layout", "composite_record_id": "OFDVDNET_001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["analysis_allowed"] is False
    assert payload["channels"][0]["role"] == "video"
    assert payload["channels"][0]["path"] == str(source)
    assert payload["failure_reasons"] == ["ffmpeg_unavailable"]


def test_composite_session_reports_out_of_bounds_layout_and_keeps_original_video(tmp_path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    source = artifact_root / "composite.mp4"
    _write_video(source, fps=5.0, frame_count=10, value=70)
    manifest = tmp_path / "ofdvdnet.csv"
    manifest.write_text(
        "record_id,dataset_id,video_path,original_filename,view_layout,overlay_xyxy,"
        "fluorescence_xyxy,reference_xyxy,readable,domain_boundary\n"
        f"OFDVDNET_001,D046,{source},sample.mp4,three_views,0|0|32|24,32|0|80|24,"
        "0|24|32|48,True,public proxy\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_VIDEO_MANIFEST_PATH", str(tmp_path / "missing-videos.csv"))
    monkeypatch.setenv("OSTEO_OFDVD_MANIFEST_PATH", str(manifest))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "composite crop fallback"}).json()["case_id"]

    response = client.post(
        f"/cases/{case_id}/multichannel-video-sessions",
        json={"mode": "composite_layout", "composite_record_id": "OFDVDNET_001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["analysis_allowed"] is False
    assert payload["channels"][0]["path"] == str(source)
    assert payload["failure_reasons"] == ["composite_crop_out_of_bounds"]
    playback = client.get("/files/video", params={"path": str(source)})
    assert playback.status_code == 200


def test_composite_split_decodes_source_once_for_all_pending_channels(tmp_path, monkeypatch) -> None:
    source = tmp_path / "composite.mp4"
    source.write_bytes(b"source")
    output_dir = tmp_path / "channels"
    expected = {role: output_dir / f"{role}.mp4" for role in ("white_light", "fluorescence", "device_overlay")}
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        for path in expected.values():
            path.write_bytes(b"channel")
        return multichannel_video_service.subprocess.CompletedProcess(command, 0, "", "")

    service = object.__new__(multichannel_video_service.MultichannelVideoService)
    monkeypatch.setattr(service, "_required_video_probe", lambda _path, _role: {"width": 96, "height": 48})
    monkeypatch.setattr(multichannel_video_service, "find_runtime_executable", lambda _name: "ffmpeg")
    monkeypatch.setattr(multichannel_video_service.subprocess, "run", fake_run)

    outputs = service._split_composite(
        source,
        {
            "white_light": [0, 0, 32, 24],
            "fluorescence": [32, 0, 64, 24],
            "device_overlay": [64, 0, 96, 24],
        },
        output_dir,
    )

    assert outputs == expected
    assert len(calls) == 1
    assert calls[0].count("-map") == 3
    assert "split=3" in calls[0][calls[0].index("-filter_complex") + 1]


def test_sample_times_ignores_invalid_focus_values_without_numpy() -> None:
    sampled = multichannel_video_service._sample_times(
        0.0,
        1.0,
        4,
        [0.5, "bad", float("nan"), float("inf")],
    )

    assert sampled == [0.0, 0.45, 0.5, 0.9]


def test_probe_start_time_skips_non_finite_container_value() -> None:
    assert (
        multichannel_video_service._probe_start_time_sec(
            {"ffprobe": {"format": {"start_time": "nan"}, "stream": {"start_time": "0.125"}}}
        )
        == 0.125
    )
