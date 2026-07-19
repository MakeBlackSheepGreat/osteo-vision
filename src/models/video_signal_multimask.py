from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn

from src.core.paths import ensure_dir
from src.models.keyframe_segmenter import ConvStage2D
from src.preprocess.fluorescence import apply_fluorescence_colormap, blend_pseudocolor_on_reference

VIDEO_SIGNAL_HEADS = ("fluorescence_signal", "bone_gate")
MASK_TYPE_TO_HEAD = {
    "fluorescence_hotspot": "fluorescence_signal",
    "exposed_bone": "bone_gate",
}
REVIEW_STATES = ("accepted", "modified", "rejected", "review_required")
DEFAULT_REVIEW_WEIGHTS = {
    "accepted": 4.0,
    "modified": 4.0,
    "rejected": 0.5,
    "review_required": 1.0,
}


class VideoSignalMultiMask2D(nn.Module):
    """Compact shared encoder with independent video-signal mask heads."""

    def __init__(
        self, in_channels: int = 3, heads: tuple[str, ...] = VIDEO_SIGNAL_HEADS, base_channels: int = 8
    ) -> None:
        super().__init__()
        if not heads:
            raise ValueError("At least one video-signal head is required")
        self.head_names = tuple(heads)
        c1 = base_channels
        c2 = base_channels * 2
        c3 = base_channels * 4
        self.enc0 = ConvStage2D(in_channels, c1)
        self.down1 = nn.Sequential(nn.Conv2d(c1, c2, 3, stride=2, padding=1), nn.GroupNorm(1, c2), nn.GELU())
        self.enc1 = ConvStage2D(c2, c2)
        self.down2 = nn.Sequential(nn.Conv2d(c2, c3, 3, stride=2, padding=1), nn.GroupNorm(1, c3), nn.GELU())
        self.bottleneck = ConvStage2D(c3, c3)
        self.up1 = nn.ConvTranspose2d(c3, c2, 2, stride=2)
        self.dec1 = ConvStage2D(c2 + c2, c2)
        self.up0 = nn.ConvTranspose2d(c2, c1, 2, stride=2)
        self.dec0 = ConvStage2D(c1 + c1, c1)
        self.head = nn.Conv2d(c1, len(self.head_names), 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = self.up1(x2)
        if y1.shape[2:] != x1.shape[2:]:
            y1 = F.interpolate(y1, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = self.up0(y1)
        if y0.shape[2:] != x0.shape[2:]:
            y0 = F.interpolate(y0, size=x0.shape[2:], mode="bilinear", align_corners=False)
        return self.head(self.dec0(torch.cat([y0, x0], dim=1)))


def build_video_signal_multimask(config: dict[str, Any] | None = None) -> VideoSignalMultiMask2D:
    model_config = dict(config or {})
    return VideoSignalMultiMask2D(
        in_channels=int(model_config.get("in_channels", 3)),
        heads=tuple(model_config.get("heads") or VIDEO_SIGNAL_HEADS),
        base_channels=int(model_config.get("base_channels", 8)),
    )


def load_video_signal_multimask_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[VideoSignalMultiMask2D, dict[str, Any]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model_config = dict(checkpoint.get("model_config") or {})
    model = build_video_signal_multimask(model_config).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    metadata = {key: value for key, value in checkpoint.items() if key != "state_dict"}
    return model, metadata


def predict_video_signal_multimask(
    model: VideoSignalMultiMask2D,
    input_path: str | Path,
    *,
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    model_id: str,
    thresholds: dict[str, Any] | None = None,
    input_shape: tuple[int, int] = (128, 176),
    metadata: dict[str, Any] | None = None,
    review_weights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    height, width = _validated_input_shape(input_shape)
    with Image.open(input_path) as image_obj:
        rgb = np.asarray(image_obj.convert("RGB"), dtype=np.uint8)
    resized = np.asarray(Image.fromarray(rgb).resize((width, height), Image.Resampling.BILINEAR), dtype=np.uint8)
    tensor = torch.from_numpy(resized.transpose(2, 0, 1)[None].astype(np.float32) / 255.0).to(device)
    model.eval()
    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.sigmoid(logits)[0].cpu().numpy()
    if probabilities.shape[0] != len(model.head_names):
        raise ValueError("Multi-mask checkpoint head count does not match the loaded model")

    resolved_thresholds = _head_thresholds(model.head_names, thresholds or {}, metadata or {})
    weights = _review_weights(review_weights or {})
    out_dir = ensure_dir(output_dir)
    safe_case = _safe_name(case_id)
    outputs: dict[str, Any] = {}
    for index, head in enumerate(model.head_names):
        probability = np.asarray(
            Image.fromarray(probabilities[index].astype(np.float32)).resize(
                (rgb.shape[1], rgb.shape[0]),
                Image.Resampling.BILINEAR,
            ),
            dtype=np.float32,
        )
        threshold = resolved_thresholds[head]
        mask = (probability >= threshold).astype(np.uint8)
        mask_path = out_dir / f"{safe_case}_{head}_mask.png"
        probability_path = out_dir / f"{safe_case}_{head}_probability.png"
        overlay_path = out_dir / f"{safe_case}_{head}_overlay.png"
        Image.fromarray(mask * 255).save(mask_path)
        Image.fromarray(np.clip(probability * 255.0, 0, 255).astype(np.uint8)).save(probability_path)
        pseudo = apply_fluorescence_colormap(probability, "green" if head == "fluorescence_signal" else "red")
        Image.fromarray(blend_pseudocolor_on_reference(rgb, pseudo, alpha=0.45)).save(overlay_path)
        positive_area = int(mask.sum())
        output_key = f"{head}_mask"
        outputs[output_key] = {
            "case_id": case_id,
            "source": model_id,
            "format": "png_binary_mask",
            "path": str(mask_path),
            "probability_path": str(probability_path),
            "overlay_path": str(overlay_path),
            "width": int(mask.shape[1]),
            "height": int(mask.shape[0]),
            "threshold": float(threshold),
            "positive_area_px": positive_area,
            "positive_area_fraction": float(mask.mean()),
            "review_status": "review_required",
            "sample_weight": weights["review_required"],
            "physician_reviewed": False,
            "training_role": "semi_automatic_seed_pending_review",
            "target_domain_flag": False,
        }

    return {
        "available": True,
        "adapter_mode": "video_signal_multimask_candidate",
        "model_id": model_id,
        "fluorescence_signal_mask": outputs["fluorescence_signal_mask"],
        "bone_gate_mask": outputs["bone_gate_mask"],
        "review_contract": _review_contract(weights),
        "candidate_only": True,
        "disease_final_mask_allowed": False,
        "target_domain_flag": False,
        "medical_boundary": (
            "Fluorescence-signal and bone-gate masks are non-target-domain engineering outputs. "
            "Bone-gate masks remain semi-automatic seeds until physician review."
        ),
    }


def _head_thresholds(
    heads: tuple[str, ...],
    configured: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, float]:
    validation_heads = dict((metadata.get("validation") or {}).get("heads") or {})
    resolved: dict[str, float] = {}
    for head in heads:
        validation = dict(validation_heads.get(head) or {})
        threshold = configured.get(head)
        if threshold is None:
            threshold = validation.get("recommended_threshold")
        if threshold is None:
            threshold = 0.5
        value = float(threshold)
        if value <= 0.0 or value >= 1.0:
            raise ValueError(f"Threshold for {head} must be within (0, 1)")
        resolved[head] = value
    return resolved


def _validated_input_shape(value: tuple[int, int]) -> tuple[int, int]:
    if len(value) != 2:
        raise ValueError("input_shape must contain height and width")
    height, width = (int(item) for item in value)
    if height < 16 or width < 16:
        raise ValueError("input_shape dimensions must be at least 16 pixels")
    return height, width


def _review_weights(configured: dict[str, Any]) -> dict[str, float]:
    weights = {state: float(configured.get(state, default)) for state, default in DEFAULT_REVIEW_WEIGHTS.items()}
    if any(value < 0.0 for value in weights.values()):
        raise ValueError("Review sample weights must be non-negative")
    return weights


def _review_contract(weights: dict[str, float]) -> dict[str, Any]:
    return {
        "states": list(REVIEW_STATES),
        "sample_weights": weights,
        "training_roles": {
            "accepted": "high_weight_positive_supervision",
            "modified": "high_weight_corrected_supervision",
            "rejected": "negative_or_error_analysis",
            "review_required": "low_weight_seed_pending_review",
        },
        "bone_gate_default_state": "review_required",
        "bone_gate_physician_review_required": True,
    }


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
