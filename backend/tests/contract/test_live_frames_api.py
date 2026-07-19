from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from fastapi.testclient import TestClient

from backend.src.api.app import create_app
from backend.src.services.live_frame_service import LiveFrameAnalysisService
from src.core.schemas import ModelSpec


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
