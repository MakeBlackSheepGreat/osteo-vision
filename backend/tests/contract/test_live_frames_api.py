from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Event, Lock
from time import sleep

import cv2
import numpy as np
import pytest
import torch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import ClientDisconnect

from backend.osteo_vision_api.api.app import create_app
from backend.osteo_vision_api.api.live_frames import _await_analysis_or_disconnect
from backend.osteo_vision_api.services.live_frame_service import (
    LiveFrameAnalysisService,
    LiveFrameCancelledError,
    LiveFrameCapacityError,
    LiveFrameInputError,
    _commit_staging_directory,
)
from osteo_vision_core.core.schemas import ModelSpec


def test_live_frame_service_uses_runtime_segmentation_task_as_default(tmp_path: Path) -> None:
    config_path = tmp_path / "candidate.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  tasks:",
                "    segmentation:",
                "      pipeline: segmentation",
                "      model_id: keyframe_candidate",
                "reports:",
                f"  visual_dir: {tmp_path.as_posix()}/visual",
            ]
        ),
        encoding="utf-8",
    )

    service = LiveFrameAnalysisService(str(config_path))

    assert service.default_model_id == "keyframe_candidate"


def test_live_frame_service_rejects_missing_model_binding_in_strict_runtime(tmp_path: Path) -> None:
    config_path = tmp_path / "strict.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  strict_startup: true",
                "reports:",
                f"  visual_dir: {tmp_path.as_posix()}/visual",
            ]
        ),
        encoding="utf-8",
    )

    service = LiveFrameAnalysisService(str(config_path))

    with pytest.raises(ValueError, match="runtime.tasks.segmentation.model_id"):
        _ = service.default_model_id


def test_live_frame_api_returns_renderable_segmentation_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case = client.post("/cases", json={"title": "live frame"}).json()
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    image[:, :, 1] = 180
    cv2.circle(image, (60, 40), 18, (25, 245, 45), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=encoded.tobytes(),
        headers={
            "content-type": "image/jpeg",
            "x-filename": "live.jpg",
            "x-frame-sequence": "1",
            "x-hotspot-threshold": "0.6",
            "x-colormap": "green",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inference_latency_ms"] >= 0
    assert payload["performance"]["total_ms"] == payload["inference_latency_ms"]
    assert payload["performance"]["model_ms"] >= 0
    assert payload["model_inference_latency_ms"] == payload["performance"]["model_ms"]
    assert payload["performance"]["decode_ms"] >= 0
    assert payload["performance"]["evidence_write_ms"] >= 0
    assert payload["performance"]["input_bytes"] == len(encoded.tobytes())
    assert payload["performance"]["decoded_width"] == 120
    assert payload["performance"]["decoded_height"] == 80
    assert payload["overlay_path"]
    assert payload["mask_path"]
    assert Path(payload["source_path"]).read_bytes() == encoded.tobytes()
    assert Path(payload["overlay_path"]).suffix == ".jpg"
    assert payload["probability_path"] is None
    assert payload["pseudo_color_path"] is None
    assert client.get("/files/preview", params={"path": payload["overlay_path"]}).status_code == 200
    assert "医生复核" in payload["medical_boundary"]
    assert payload["quantification"]["inference"]["tta_enabled"] is False
    assert payload["quantification"]["inference"]["output_profile"] == "live_fast"

    second = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=encoded.tobytes(),
        headers={
            "content-type": "image/jpeg",
            "x-filename": "live.jpg",
            "x-frame-sequence": "2",
            "x-hotspot-threshold": "0.6",
            "x-colormap": "green",
        },
    )
    assert second.status_code == 200
    assert second.json()["overlay_path"] != payload["overlay_path"]


def test_live_frame_warmup_preloads_configured_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())

    response = client.post("/live-frames/warmup", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["model_id"] == "keyframe_residual_attention_unet_s20260715_20260715"


def test_live_frame_warmup_executes_model_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    calls = {"count": 0}
    original_forward = torch.nn.Module._call_impl

    def counted_forward(self, *args, **kwargs):
        calls["count"] += 1
        return original_forward(self, *args, **kwargs)

    monkeypatch.setattr(torch.nn.Module, "_call_impl", counted_forward)
    client = TestClient(create_app())

    response = client.post("/live-frames/warmup", json={"model_id": "convnext2d_keyframe_proxy_segmenter"})

    assert response.status_code == 200
    assert calls["count"] >= 1


def test_live_frame_warmup_executes_any_2d_segmentation_keyframe_family() -> None:
    class CountingModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def forward(self, value: torch.Tensor) -> torch.Tensor:
            self.calls += 1
            return torch.cat((value[:, :1], value[:, :1]), dim=1)

    model = CountingModel()
    spec = ModelSpec(
        model_id="residual_candidate",
        family="residual_attention_unet_keyframe_segmenter",
        task_types=["segmentation"],
        input_types=["2d_image"],
        spatial_dims=[2],
        device_policy="cpu",
        extra={"input_channels": 3},
    )

    class Adapter:
        _model = model

        @staticmethod
        def describe() -> ModelSpec:
            return spec

    LiveFrameAnalysisService._run_warmup_inference(Adapter())

    assert model.calls == 1


def test_live_frame_adapter_is_created_once_under_concurrent_first_access(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: concurrent_model",
                "      family: convnext2d_keyframe_segmenter",
                "      task_types: [segmentation]",
                "      input_types: [2d_image]",
                "      spatial_dims: [2]",
                "reports:",
                f"  visual_dir: {tmp_path.as_posix()}/visual",
            ]
        ),
        encoding="utf-8",
    )
    service = LiveFrameAnalysisService(str(config_path))
    calls = 0
    calls_lock = Lock()
    adapter = object()

    def slow_build(_spec):
        nonlocal calls
        with calls_lock:
            calls += 1
        sleep(0.05)
        return adapter

    monkeypatch.setattr("backend.osteo_vision_api.services.live_frame_service.build_adapter", slow_build)
    with ThreadPoolExecutor(max_workers=4) as executor:
        adapters = list(executor.map(service._adapter, ["concurrent_model"] * 4))

    assert calls == 1
    assert all(item is adapter for item in adapters)


def test_live_frame_model_is_loaded_once_under_concurrent_first_inference(tmp_path) -> None:
    service = LiveFrameAnalysisService(_write_live_config(tmp_path))

    class Adapter:
        _model = None

        def __init__(self) -> None:
            self.load_calls = 0

        def _load_model(self) -> None:
            self.load_calls += 1
            sleep(0.05)
            self._model = object()

    adapter = Adapter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(service._load_model_if_needed, [adapter] * 4))

    assert adapter.load_calls == 1


def test_live_frame_service_rejects_backlog_and_releases_capacity(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  live_frames:",
                "    max_concurrent_inferences: 1",
                "reports:",
                f"  visual_dir: {tmp_path.as_posix()}/visual",
            ]
        ),
        encoding="utf-8",
    )
    service = LiveFrameAnalysisService(str(config_path))
    entered = Event()
    release = Event()
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    def slow_predict(**_kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return {
            "model_id": "test_model",
            "prediction": {},
            "segmentation_mask": {"path": "mask.png"},
            "lesion_evidence": {},
            "quantification": {},
        }

    monkeypatch.setattr(service, "_predict_frame", slow_predict)
    request = {
        "case_id": "case_capacity",
        "frame_bytes": encoded.tobytes(),
        "filename": "frame.jpg",
        "parameters": {},
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.analyze, **request)
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(LiveFrameCapacityError) as captured:
                service.analyze(**request)
            assert captured.value.max_concurrent == 1
        finally:
            release.set()
        result = first.result(timeout=5)

    assert result["performance"]["max_concurrent_inferences"] == 1
    assert service.analyze(**request)["mask_path"] == "mask.png"


def test_live_frame_service_honors_cancellation_before_writing(tmp_path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(["runtime: {}", "reports:", f"  visual_dir: {tmp_path.as_posix()}/visual"]),
        encoding="utf-8",
    )
    service = LiveFrameAnalysisService(str(config_path))
    cancelled = Event()
    cancelled.set()

    with pytest.raises(LiveFrameCancelledError):
        service.analyze(
            case_id="case_cancelled",
            frame_bytes=b"unreadable data is never decoded",
            filename="frame.jpg",
            parameters={},
            cancel_event=cancelled,
        )

    assert not (tmp_path / "visual" / "live_frames" / "case_cancelled").exists()


def test_live_frame_capacity_error_maps_to_retryable_http_response(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))

    def busy(*_args, **_kwargs):
        raise LiveFrameCapacityError(max_concurrent=1, waited_ms=0.0)

    monkeypatch.setattr(LiveFrameAnalysisService, "analyze", busy)
    client = TestClient(create_app())
    case = client.post("/cases", json={"title": "capacity"}).json()

    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"frame",
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert response.json()["detail"]["code"] == "live_frame_capacity_exceeded"


def test_live_frame_content_length_is_rejected_before_body_decode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case = client.post("/cases", json={"title": "oversized"}).json()

    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"small",
        headers={"content-type": "image/jpeg", "content-length": str(20 * 1024 * 1024 + 1)},
    )

    assert response.status_code == 413


def test_live_frame_api_preserves_empty_and_stream_limit_validation_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app(), raise_server_exceptions=False)
    case = client.post("/cases", json={"title": "body validation"}).json()

    empty = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"",
        headers={"content-type": "image/jpeg"},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"] == "Live frame is empty"

    async def reject_stream(*_args, **_kwargs):
        raise HTTPException(status_code=413, detail="Request body exceeds the streaming limit")

    monkeypatch.setattr("backend.osteo_vision_api.api.live_frames._read_bounded_body", reject_stream)
    oversized_stream = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"body with unknown declared length",
        headers={"content-type": "image/jpeg"},
    )
    assert oversized_stream.status_code == 413
    assert oversized_stream.json()["detail"] == "Request body exceeds the streaming limit"


def test_live_frame_api_times_out_stalled_upload_and_releases_admission(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))

    async def stalled_body(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return b"unreachable"

    monkeypatch.setattr("backend.osteo_vision_api.api.live_frames.MAX_LIVE_FRAME_UPLOAD_SECONDS", 0.001)
    monkeypatch.setattr("backend.osteo_vision_api.api.live_frames._read_bounded_body", stalled_body)
    client = TestClient(create_app(), raise_server_exceptions=False)
    case = client.post("/cases", json={"title": "stalled upload"}).json()

    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"partial",
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code == 408
    assert response.json()["detail"] == "Live frame upload timed out"


def test_live_frame_disconnect_monitor_sets_worker_cancellation() -> None:
    class DisconnectedRequest:
        async def receive(self):
            return {"type": "http.disconnect"}

    async def scenario() -> None:
        cancel_event = Event()
        analysis_task = asyncio.create_task(asyncio.sleep(10, result={"completed": True}))
        with pytest.raises(ClientDisconnect):
            await _await_analysis_or_disconnect(DisconnectedRequest(), analysis_task, cancel_event)  # type: ignore[arg-type]
        assert cancel_event.is_set()
        analysis_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await analysis_task

    asyncio.run(scenario())


def test_live_frame_service_rejects_oversized_and_unsupported_decoded_images(tmp_path) -> None:
    service = LiveFrameAnalysisService(_write_live_config(tmp_path))
    oversized = BytesIO()
    Image.new("RGB", (4097, 8), color=(0, 0, 0)).save(oversized, format="PNG")

    with pytest.raises(LiveFrameInputError, match="dimensions exceed"):
        service.analyze(
            case_id="case_oversized_pixels",
            frame_bytes=oversized.getvalue(),
            filename="frame.png",
            parameters={},
        )

    unsupported = BytesIO()
    Image.new("RGB", (16, 16), color=(0, 0, 0)).save(unsupported, format="BMP")
    with pytest.raises(LiveFrameInputError, match="JPEG or PNG"):
        service.analyze(
            case_id="case_unsupported_format",
            frame_bytes=unsupported.getvalue(),
            filename="frame.jpg",
            parameters={},
        )
    assert not (tmp_path / "visual" / "live_frames").exists()


def test_live_frame_service_rejects_animated_png(tmp_path) -> None:
    service = LiveFrameAnalysisService(_write_live_config(tmp_path))
    animated = BytesIO()
    Image.new("RGB", (16, 16), color=(0, 0, 0)).save(
        animated,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (16, 16), color=(255, 255, 255))],
    )

    with pytest.raises(LiveFrameInputError, match="Animated"):
        service.analyze(
            case_id="case_animated",
            frame_bytes=animated.getvalue(),
            filename="frame.png",
            parameters={},
        )


def test_live_frame_service_cleans_staging_and_model_outputs_after_failure(tmp_path, monkeypatch) -> None:
    model_output_dir = tmp_path / "model_outputs"
    config_path = _write_live_config(
        tmp_path,
        runtime_lines=[
            "  models:",
            "    - model_id: cleanup_model",
            "      family: convnext2d_keyframe_segmenter",
            "      task_types: [segmentation]",
            "      input_types: [2d_image]",
            "      spatial_dims: [2]",
            "      extra:",
            f"        output_dir: {model_output_dir.as_posix()}",
        ],
    )
    service = LiveFrameAnalysisService(config_path)
    image_bytes = _jpeg_bytes()

    def failing_predict(**kwargs):
        model_output_dir.mkdir(parents=True, exist_ok=True)
        (model_output_dir / f"{kwargs['frame_case_id']}_mask.png").write_bytes(b"partial")
        assert Path(kwargs["source_path"]).exists()
        raise RuntimeError("prediction failed")

    monkeypatch.setattr(service, "_predict_frame", failing_predict)
    with pytest.raises(RuntimeError, match="prediction failed"):
        service.analyze(
            case_id="case_cleanup",
            frame_bytes=image_bytes,
            filename="frame.jpg",
            parameters={"segmentation_model_id": "cleanup_model"},
        )

    assert not (tmp_path / "visual" / "live_frames" / "case_cleanup").exists()
    assert list(model_output_dir.glob("case_cleanup_*")) == []


def test_live_frame_cleanup_does_not_delete_payload_paths_outside_managed_roots(tmp_path, monkeypatch) -> None:
    model_output_dir = tmp_path / "model_outputs"
    outside_dir = tmp_path / "outside"
    config_path = _write_live_config(
        tmp_path,
        runtime_lines=[
            "  models:",
            "    - model_id: cleanup_model",
            "      family: convnext2d_keyframe_segmenter",
            "      task_types: [segmentation]",
            "      input_types: [2d_image]",
            "      spatial_dims: [2]",
            "      extra:",
            f"        output_dir: {model_output_dir.as_posix()}",
        ],
    )
    service = LiveFrameAnalysisService(config_path)
    cancelled = Event()
    external_path: Path | None = None

    def return_external_path(**kwargs):
        nonlocal external_path
        outside_dir.mkdir(parents=True, exist_ok=True)
        external_path = outside_dir / f"{kwargs['frame_case_id']}_external.png"
        external_path.write_bytes(b"must remain")
        cancelled.set()
        return {
            "model_id": "cleanup_model",
            "segmentation_mask": {"path": str(external_path)},
            "lesion_evidence": {"overlay_path": str(external_path)},
            "quantification": {},
        }

    monkeypatch.setattr(service, "_predict_frame", return_external_path)
    with pytest.raises(LiveFrameCancelledError):
        service.analyze(
            case_id="case_external_cleanup",
            frame_bytes=_jpeg_bytes(),
            filename="frame.jpg",
            parameters={"segmentation_model_id": "cleanup_model"},
            cancel_event=cancelled,
        )

    assert external_path is not None
    assert external_path.read_bytes() == b"must remain"
    assert not (tmp_path / "visual" / "live_frames" / "case_external_cleanup").exists()


def test_live_frame_service_retains_only_configured_recent_frames(tmp_path, monkeypatch) -> None:
    model_output_dir = tmp_path / "model_outputs"
    config_path = _write_live_config(
        tmp_path,
        runtime_lines=[
            "  live_frames:",
            "    max_retained_frames_per_case: 2",
            "  models:",
            "    - model_id: retention_model",
            "      family: convnext2d_keyframe_segmenter",
            "      task_types: [segmentation]",
            "      input_types: [2d_image]",
            "      spatial_dims: [2]",
            "      extra:",
            f"        output_dir: {model_output_dir.as_posix()}",
        ],
    )
    service = LiveFrameAnalysisService(config_path)

    def write_model_output(**kwargs):
        model_output_dir.mkdir(parents=True, exist_ok=True)
        mask_path = model_output_dir / f"{kwargs['frame_case_id']}_mask.png"
        overlay_path = model_output_dir / f"{kwargs['frame_case_id']}_overlay.jpg"
        mask_path.write_bytes(b"mask")
        overlay_path.write_bytes(b"overlay")
        return {
            "model_id": "retention_model",
            "segmentation_mask": {"path": str(mask_path)},
            "lesion_evidence": {"overlay_path": str(overlay_path)},
            "quantification": {},
        }

    monkeypatch.setattr(service, "_predict_frame", write_model_output)
    results = [
        service.analyze(
            case_id="case_retention",
            frame_bytes=_jpeg_bytes(),
            filename="frame.jpg",
            parameters={"segmentation_model_id": "retention_model", "sequence": sequence},
        )
        for sequence in range(3)
    ]

    assert not Path(results[0]["source_path"]).exists()
    assert not Path(results[0]["mask_path"]).exists()
    assert not Path(results[0]["manifest_path"]).exists()
    for result in results[1:]:
        assert Path(result["source_path"]).is_file()
        assert Path(result["mask_path"]).is_file()
        manifest_path = Path(result["manifest_path"])
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["frame_id"] == result["frame_id"]
        assert manifest["frame_case_id"] == f"case_retention_{result['frame_id']}"
        assert manifest["model_id"] == "retention_model"
        assert manifest["source_file"] == "frame.jpg"
        assert result["mask_path"] in manifest["managed_output_paths"]
    retained_dirs = [path for path in Path(results[-1]["manifest_path"]).parents[1].iterdir() if path.is_dir()]
    assert {path.name for path in retained_dirs} == {results[1]["frame_id"], results[2]["frame_id"]}
    assert results[-1]["retention"]["max_retained_frames_per_case"] == 2
    assert results[-1]["retention"]["retained_frame_count"] == 2
    assert results[-1]["retention"]["evicted_frame_ids"] == [results[0]["frame_id"]]


def test_live_frame_service_echoes_fixed_model_parameters_and_frame_identity(tmp_path, monkeypatch) -> None:
    config_path = _write_live_config(
        tmp_path,
        runtime_lines=[
            "  models:",
            "    - model_id: fixed_parameter_model",
            "      family: convnext2d_keyframe_segmenter",
            "      task_types: [segmentation]",
            "      input_types: [2d_image]",
            "      spatial_dims: [2]",
            "      extra:",
            "        threshold: 0.4",
            "        colormap: green",
        ],
    )
    service = LiveFrameAnalysisService(config_path)
    captured: dict = {}

    def capture_predict(**kwargs):
        captured.update(kwargs)
        return {
            "model_id": "fixed_parameter_model",
            "prediction": {},
            "segmentation_mask": {"path": "mask.png"},
            "lesion_evidence": {},
            "quantification": {},
        }

    monkeypatch.setattr(service, "_predict_frame", capture_predict)
    result = service.analyze(
        case_id="case_parameters",
        frame_bytes=_jpeg_bytes(),
        filename="frame.jpg",
        parameters={
            "segmentation_model_id": "fixed_parameter_model",
            "threshold": "0.6",
            "colormap": "amber",
            "sequence": "7",
            "timestamp_sec": "1.25",
        },
    )

    assert result["sequence"] == 7
    assert result["source_timestamp_sec"] == 1.25
    assert result["applied_parameters"]["threshold"] == 0.4
    assert result["applied_parameters"]["colormap"] == "green"
    assert result["applied_parameters"]["runtime_override_applied"] is False
    assert captured["live_parameters"] == result["applied_parameters"]
    assert {warning["code"] for warning in result["warnings"]} == {
        "live_frame_threshold_fixed_by_model",
        "live_frame_colormap_fixed_by_model",
    }


def test_live_frame_service_validates_configured_concurrency(tmp_path) -> None:
    service = LiveFrameAnalysisService(
        _write_live_config(tmp_path, runtime_lines=["  live_frames:", "    max_concurrent_inferences: 2"])
    )
    first = service.acquire_admission(wait=False)
    second = service.acquire_admission(wait=False)
    with pytest.raises(LiveFrameCapacityError):
        service.acquire_admission(wait=False)
    first.release()
    second.release()

    invalid_config = _write_live_config(
        tmp_path / "invalid",
        runtime_lines=["  live_frames:", "    max_concurrent_inferences: 0"],
    )
    with pytest.raises(ValueError, match="max_concurrent_inferences"):
        LiveFrameAnalysisService(invalid_config)

    invalid_retention_config = _write_live_config(
        tmp_path / "invalid_retention",
        runtime_lines=["  live_frames:", "    max_retained_frames_per_case: 5001"],
    )
    with pytest.raises(ValueError, match="max_retained_frames_per_case"):
        LiveFrameAnalysisService(invalid_retention_config)


def test_live_frame_api_redacts_internal_value_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))

    def fail_with_internal_path(*_args, **_kwargs):
        raise ValueError("broken checkpoint C:/private/checkpoint.pt")

    monkeypatch.setattr(LiveFrameAnalysisService, "analyze", fail_with_internal_path)
    client = TestClient(create_app(), raise_server_exceptions=False)
    case = client.post("/cases", json={"title": "redaction"}).json()
    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=_jpeg_bytes(),
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code == 503
    assert "checkpoint.pt" not in response.text
    assert "C:/private" not in response.text


def test_live_frame_api_rejects_capacity_before_reading_body(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    body_read = False

    def reject_admission(*_args, **_kwargs):
        raise LiveFrameCapacityError(max_concurrent=1, waited_ms=0.0)

    async def track_body_read(*_args, **_kwargs):
        nonlocal body_read
        body_read = True
        return b"unused"

    monkeypatch.setattr(LiveFrameAnalysisService, "acquire_admission", reject_admission)
    monkeypatch.setattr("backend.osteo_vision_api.api.live_frames._read_bounded_body", track_body_read)
    client = TestClient(create_app(), raise_server_exceptions=False)
    case = client.post("/cases", json={"title": "pre-body capacity"}).json()
    response = client.post(
        f"/cases/{case['case_id']}/live-frames",
        content=b"would otherwise be buffered",
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code == 429
    assert body_read is False


def test_live_frame_service_cleans_evidence_when_cancelled_after_prediction(tmp_path, monkeypatch) -> None:
    service = LiveFrameAnalysisService(_write_live_config(tmp_path))
    cancelled = Event()

    def cancel_during_prediction(**_kwargs):
        cancelled.set()
        return {
            "model_id": "test_model",
            "prediction": {},
            "segmentation_mask": {"path": "mask.png"},
            "lesion_evidence": {},
            "quantification": {},
        }

    monkeypatch.setattr(service, "_predict_frame", cancel_during_prediction)
    with pytest.raises(LiveFrameCancelledError):
        service.analyze(
            case_id="case_cancel_after_predict",
            frame_bytes=_jpeg_bytes(),
            filename="frame.jpg",
            parameters={},
            cancel_event=cancelled,
        )

    assert not (tmp_path / "visual" / "live_frames" / "case_cancel_after_predict").exists()


def test_live_frame_directory_commit_retries_transient_windows_permission_error(tmp_path, monkeypatch) -> None:
    staging_dir = tmp_path / ".live_frame.tmp"
    final_dir = tmp_path / "live_frame"
    staging_dir.mkdir()
    (staging_dir / "manifest.json").write_text("{}", encoding="utf-8")
    original_replace = os.replace
    calls = 0

    def transient_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError(13, "transient directory lock", str(source))
        original_replace(source, destination)

    monkeypatch.setattr("backend.osteo_vision_api.services.live_frame_service.os.replace", transient_replace)
    monkeypatch.setattr("backend.osteo_vision_api.services.live_frame_service.sleep", lambda _seconds: None)

    _commit_staging_directory(staging_dir, final_dir)

    assert calls == 3
    assert not staging_dir.exists()
    assert (final_dir / "manifest.json").is_file()


def test_live_frame_warmup_rejects_malformed_and_oversized_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app(), raise_server_exceptions=False)

    malformed = client.post(
        "/live-frames/warmup",
        content=b"{",
        headers={"content-type": "application/json"},
    )
    oversized = client.post(
        "/live-frames/warmup",
        content=b"x" * 4097,
        headers={"content-type": "application/json"},
    )

    assert malformed.status_code == 400
    assert oversized.status_code == 413


def _write_live_config(tmp_path: Path, *, runtime_lines: list[str] | None = None) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "live_config.yml"
    lines = [
        "runtime:",
        *(runtime_lines or ["  models: []"]),
        "reports:",
        f"  visual_dir: {tmp_path.as_posix()}/visual",
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return str(config_path)


def _jpeg_bytes() -> bytes:
    image = np.zeros((16, 24, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()
