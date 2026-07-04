from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
import torch

from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapters, inventory_from_adapters, select_adapter
from src.models.keyframe_segmenter import TinyKeyframeSegmenter2D
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


def test_convnext2d_keyframe_segmenter_predicts_2d_image(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "keyframe.pt"
    _write_tiny_keyframe_checkpoint(checkpoint_path, model_id="keyframe_test")
    image_path = tmp_path / "keyframe.png"
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 16:36, 1] = 220
    image[10:20, 20:30, 0] = 40
    Image.fromarray(image).save(image_path)
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "keyframe_test",
                    "family": "convnext2d_keyframe_segmenter",
                    "task_types": ["segmentation"],
                    "input_types": ["2d_image"],
                    "checkpoint_path": str(checkpoint_path),
                    "dependency_group": "torch",
                    "device_policy": "cpu",
                    "extra": {
                        "output_dir": str(tmp_path / "keyframe_masks"),
                        "threshold": 0.0,
                        "force_tiled": True,
                        "tile_size": 16,
                        "tile_overlap": 4,
                    },
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
            modality="surgical_keyframe",
        )
    )

    assert result.model_family == "convnext2d_keyframe_segmenter"
    assert result.prediction["adapter_mode"] == "trainable_convnext2d_keyframe_segmenter"
    assert result.prediction["inference_mode"] == "tiled"
    assert result.segmentation_mask["format"] == "png_binary_mask"
    assert result.segmentation_mask["inference"]["tile_count"] > 1
    assert Path(result.segmentation_mask["path"]).exists()
    assert Path(result.lesion_evidence["probability_path"]).exists()
    assert Path(result.lesion_evidence["pseudo_color_path"]).exists()
    assert Path(result.lesion_evidence["overlay_path"]).exists()
    assert result.quantification["available"] is True
    assert result.quantification["positive_area_px"] > 0
    assert result.lesion_evidence["candidates"]
    assert any(warning["code"] == "convnext2d_keyframe_proxy_non_target_domain" for warning in result.warnings)


def test_medsam_like_prompt_fallback_predicts_bbox_mask(tmp_path: Path) -> None:
    image_path = tmp_path / "keyframe.png"
    image = np.zeros((50, 80, 3), dtype=np.uint8)
    image[10:30, 20:50, 1] = 180
    Image.fromarray(image).save(image_path)
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "medsam_prompt_contract",
                    "family": "medsam_like",
                    "task_types": ["segmentation"],
                    "input_types": ["2d_image"],
                    "checkpoint_path": str(tmp_path / "missing_medsam.pt"),
                    "dependency_group": "sam",
                    "extra": {
                        "prompt_fallback_enabled": True,
                        "output_dir": str(tmp_path / "prompt_masks"),
                        "point_radius_px": 5,
                    },
                }
            ]
        }
    )
    status = adapters[0].warmup()
    assert status.available is True
    assert any(warning["code"] == "medsam_checkpoint_missing_prompt_fallback" for warning in status.warnings)

    result = adapters[0].predict(
        AdapterRequest(
            case_id="case",
            input_path=str(image_path),
            input_type="2d_image",
            task_type="segmentation",
            modality="surgical_keyframe",
            metadata={
                "prompts": [{"bbox_xyxy": [20, 10, 50, 30], "source": "hotspot_candidate"}],
                "roi_hints": [
                    {
                        "roi_id": "doctor_roi_1",
                        "geometry": {"type": "rect", "x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2},
                    }
                ],
            },
        )
    )

    assert result.model_family == "medsam_like"
    assert result.prediction["adapter_mode"] == "prompt_contract_fallback"
    assert result.prediction["prompt_count"] == 2
    assert result.segmentation_mask["format"] == "png_binary_mask"
    assert result.segmentation_mask["prompt_defined"] is True
    assert Path(result.segmentation_mask["path"]).exists()
    assert result.quantification["positive_area_px"] > 0
    assert len(result.lesion_evidence["candidates"]) == 2
    assert result.lesion_evidence["prompt_contract"]["fallback_mode"] is True
    assert any(warning["code"] == "medsam_like_prompt_fallback_non_diagnostic" for warning in result.warnings)


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


def _write_tiny_keyframe_checkpoint(path: Path, *, model_id: str) -> None:
    model = TinyKeyframeSegmenter2D(base_channels=2)
    torch.save(
        {
            "model_id": model_id,
            "model_family": "convnext2d_keyframe_segmenter",
            "model_config": {"in_channels": 3, "out_channels": 2, "base_channels": 2},
            "state_dict": model.state_dict(),
            "threshold": 0.0,
        },
        path,
    )


def _write_npz_roi(path: Path) -> None:
    image = np.zeros((16, 16, 16), dtype=np.float32)
    image[4:8, 4:8, 4:8] = 1.0
    label = np.zeros((16, 16, 16), dtype=np.int16)
    np.savez_compressed(path, image=image, label=label)
