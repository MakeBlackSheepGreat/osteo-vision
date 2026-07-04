from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
import torch

from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapters, inventory_from_adapters, select_adapter
from src.models.lesion_segmenter import TinyLesionSegmenter3D


def test_adapter_inventory_reports_fixture_and_unavailable_models() -> None:
    runtime = {
        "models": [
            {
                "model_id": "missing_biomedclip",
                "family": "vlm_encoder",
                "task_types": ["classification"],
                "input_types": ["2d_image"],
                "checkpoint_path": "artifacts/checkpoints/missing_biomedclip.pt",
                "dependency_group": "vlm",
            },
            {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]},
        ]
    }
    adapters = build_adapters(runtime)
    inventory = inventory_from_adapters(adapters)
    assert any(row["spec"]["family"] == "fixture" and row["status"]["available"] for row in inventory)
    assert any(row["spec"]["family"] == "vlm_encoder" and not row["status"]["available"] for row in inventory)
    assert any(
        "adapter inference not implemented" in row["status"]["reasons"]
        for row in inventory
        if row["spec"]["family"] == "vlm_encoder"
    )


def test_select_adapter_falls_back_to_fixture() -> None:
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "missing_biomedclip",
                    "family": "vlm_encoder",
                    "task_types": ["classification"],
                    "input_types": ["2d_image"],
                    "checkpoint_path": "artifacts/checkpoints/missing_biomedclip.pt",
                    "dependency_group": "vlm",
                },
                {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]},
            ]
        }
    )
    adapter, statuses = select_adapter(adapters, task_type="classification", input_type="2d_image", modality="generic")
    assert adapter is not None
    assert adapter.describe().family == "fixture"
    assert len(statuses) >= 2


def test_fixture_adapter_predicts() -> None:
    adapters = build_adapters(
        {"models": [{"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]}]}
    )
    result = adapters[0].predict(
        AdapterRequest(
            case_id="case",
            input_path="tests/fixtures/sample_image.png",
            input_type="2d_image",
            task_type="classification",
            modality="generic",
        )
    )
    assert result.probability is not None
    assert result.model_family == "fixture"


def test_d025_lesion_segmenter_reports_missing_checkpoint(tmp_path: Path) -> None:
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "d025_missing",
                    "family": "d025_lesion_segmenter",
                    "task_types": ["segmentation"],
                    "input_types": ["npz_roi"],
                    "checkpoint_path": str(tmp_path / "missing.pt"),
                    "dependency_group": "torch",
                }
            ]
        }
    )
    status = inventory_from_adapters(adapters)[0]["status"]
    assert not status["available"]
    assert any("missing checkpoint" in reason for reason in status["reasons"])
    assert "adapter inference not implemented" not in status["reasons"]


def test_d025_lesion_segmenter_predicts_npz_roi(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "model.pt"
    _write_tiny_checkpoint(checkpoint_path, model_id="d025_test", model_family="d025_lesion_segmenter")
    input_path = tmp_path / "case.npz"
    _write_npz_roi(input_path)
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "d025_test",
                    "family": "d025_lesion_segmenter",
                    "task_types": ["segmentation"],
                    "input_types": ["npz_roi"],
                    "checkpoint_path": str(checkpoint_path),
                    "dependency_group": "torch",
                    "device_policy": "cpu",
                    "extra": {"output_dir": str(tmp_path / "masks"), "threshold": 0.5},
                }
            ]
        }
    )
    result = adapters[0].predict(
        AdapterRequest(
            case_id="case",
            input_path=str(input_path),
            input_type="npz_roi",
            task_type="segmentation",
            modality="cbct",
        )
    )
    assert result.model_family == "d025_lesion_segmenter"
    assert result.segmentation_mask["format"] == "npz_volume_mask"
    assert Path(result.segmentation_mask["path"]).exists()
    assert result.quantification["available"] is True


def test_convnext3d_segmenter_is_selectable_and_predicts_npz_roi(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "convnext3d.pt"
    _write_tiny_checkpoint(checkpoint_path, model_id="convnext3d_test", model_family="convnext3d_segmenter")
    input_path = tmp_path / "case.npz"
    _write_npz_roi(input_path)
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "convnext3d_test",
                    "family": "convnext3d_segmenter",
                    "task_types": ["segmentation"],
                    "input_types": ["npz_roi"],
                    "checkpoint_path": str(checkpoint_path),
                    "dependency_group": "torch",
                    "device_policy": "cpu",
                    "extra": {"output_dir": str(tmp_path / "convnext_masks"), "threshold": 0.5},
                },
                {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]},
            ]
        }
    )
    adapter, statuses = select_adapter(adapters, task_type="segmentation", input_type="npz_roi", modality="generic")
    assert adapter is not None
    assert adapter.describe().family == "convnext3d_segmenter"
    assert statuses[0].available is True

    result = adapter.predict(
        AdapterRequest(
            case_id="case",
            input_path=str(input_path),
            input_type="npz_roi",
            task_type="segmentation",
            modality="cbct",
        )
    )
    assert result.model_family == "convnext3d_segmenter"
    assert result.segmentation_mask["format"] == "npz_volume_mask"
    assert Path(result.segmentation_mask["path"]).exists()
    assert any(warning["code"] == "convnext3d_proxy_model_non_target_domain" for warning in result.warnings)


def test_fluorescence_hotspot_segmenter_predicts_2d_image(tmp_path: Path) -> None:
    image_path = tmp_path / "fluorescence.png"
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[16:32, 20:42, 1] = 255
    Image.fromarray(image).save(image_path)
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "hotspot_test",
                    "family": "fluorescence_hotspot_segmenter",
                    "task_types": ["segmentation"],
                    "input_types": ["2d_image"],
                    "dependency_group": "core",
                    "extra": {"output_dir": str(tmp_path / "hotspots"), "threshold": 0.6, "min_component_area": 5},
                }
            ]
        }
    )
    result = adapters[0].predict(
        AdapterRequest(
            case_id="case",
            input_path=str(image_path),
            input_type="2d_image",
            task_type="segmentation",
            modality="generic",
        )
    )
    assert result.model_family == "fluorescence_hotspot_segmenter"
    assert result.segmentation_mask["format"] == "png_binary_mask"
    assert Path(result.segmentation_mask["path"]).exists()
    assert result.quantification["positive_area_px"] > 0
    assert result.lesion_evidence["candidates"]
    assert any(warning["code"] == "heuristic_hotspot_segmenter_non_diagnostic" for warning in result.warnings)


def _write_tiny_checkpoint(path: Path, *, model_id: str, model_family: str) -> None:
    model = TinyLesionSegmenter3D(base_channels=2)
    torch.save(
        {
            "model_id": model_id,
            "model_family": model_family,
            "model_config": {"in_channels": 1, "out_channels": 2, "base_channels": 2},
            "state_dict": model.state_dict(),
            "threshold": 0.5,
        },
        path,
    )


def _write_npz_roi(path: Path) -> None:
    image = np.zeros((16, 16, 16), dtype=np.float32)
    image[4:8, 4:8, 4:8] = 1.0
    label = np.zeros((16, 16, 16), dtype=np.int16)
    np.savez_compressed(path, image=image, label=label)
