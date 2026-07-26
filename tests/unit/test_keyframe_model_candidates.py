from __future__ import annotations

from pathlib import Path

import pytest
import torch

from osteo_vision_core.models.adapters import ConvNeXt2DKeyframeSegmenterAdapter, build_adapter, model_spec_from_mapping
from osteo_vision_core.models.keyframe_candidates import (
    MultiScaleDepthwiseUNet2D,
    NestedSkipUNet2D,
    PlainUNet2D,
    ResidualAttentionUNet2D,
)
from osteo_vision_core.models.keyframe_segmenter import (
    build_keyframe_segmenter,
    load_keyframe_segmenter_checkpoint,
)


@pytest.mark.parametrize(
    ("architecture", "model_type"),
    [
        ("plain_unet", PlainUNet2D),
        ("nested_skip_unet", NestedSkipUNet2D),
        ("residual_attention_unet", ResidualAttentionUNet2D),
        ("multiscale_depthwise_unet", MultiScaleDepthwiseUNet2D),
    ],
)
def test_candidate_keyframe_architectures_preserve_spatial_shape(
    architecture: str,
    model_type: type[torch.nn.Module],
) -> None:
    model = build_keyframe_segmenter(
        {
            "architecture": architecture,
            "in_channels": 3,
            "out_channels": 2,
            "base_channels": 4,
        }
    ).eval()

    with torch.inference_mode():
        output = model(torch.rand(2, 3, 63, 95))

    assert isinstance(model, model_type)
    assert output.shape == (2, 2, 63, 95)


def test_candidate_checkpoint_round_trip(tmp_path: Path) -> None:
    config = {
        "architecture": "nested_skip_unet",
        "in_channels": 3,
        "out_channels": 2,
        "base_channels": 4,
    }
    model = build_keyframe_segmenter(config)
    checkpoint_path = tmp_path / "candidate.pt"
    torch.save(
        {
            "model_id": "candidate_round_trip",
            "model_family": "nested_skip_unet_keyframe_segmenter",
            "model_config": config,
            "state_dict": model.state_dict(),
        },
        checkpoint_path,
    )

    loaded, metadata = load_keyframe_segmenter_checkpoint(checkpoint_path, device=torch.device("cpu"))

    assert isinstance(loaded, NestedSkipUNet2D)
    assert metadata["model_id"] == "candidate_round_trip"
    assert metadata["model_config"]["architecture"] == "nested_skip_unet"


def test_unknown_candidate_architecture_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported candidate keyframe architecture"):
        build_keyframe_segmenter({"architecture": "unknown", "base_channels": 4})


@pytest.mark.parametrize(
    "family",
    [
        "plain_unet_keyframe_segmenter",
        "nested_skip_unet_keyframe_segmenter",
        "residual_attention_unet_keyframe_segmenter",
        "multiscale_depthwise_unet_keyframe_segmenter",
    ],
)
def test_candidate_families_use_trainable_keyframe_adapter(family: str) -> None:
    adapter = build_adapter(
        model_spec_from_mapping(
            {
                "model_id": "candidate",
                "family": family,
                "task_types": ["segmentation"],
                "input_types": ["2d_image"],
                "checkpoint_path": "candidate.pt",
                "enabled": True,
            }
        )
    )

    assert isinstance(adapter, ConvNeXt2DKeyframeSegmenterAdapter)
