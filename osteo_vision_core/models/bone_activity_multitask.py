from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import torch
import torch.nn.functional as F
from torch import nn

from osteo_vision_core.models.keyframe_segmenter import ConvStage2D

BONE_ACTIVITY_CLASSES = ("low_activity", "transition", "high_activity")
MODEL_OUTPUTS = (
    "bone_gate",
    "activity_score",
    "class_logits",
    "class_probabilities",
    "uncertainty",
    "abstention",
)
IGNORE_INDEX = 255


class BoneActivityMultiTask2D(nn.Module):
    """Compact dual-channel network for bone gate, activity spectrum and abstention."""

    def __init__(self, *, base_channels: int = 8) -> None:
        super().__init__()
        channels = int(base_channels)
        if channels < 2:
            raise ValueError("base_channels must be at least 2")
        self.white_encoder = ConvStage2D(3, channels)
        self.fluorescence_encoder = ConvStage2D(1, channels)
        self.fusion = ConvStage2D(channels * 2, channels * 2)
        self.down = nn.Sequential(
            nn.Conv2d(channels * 2, channels * 4, 3, stride=2, padding=1),
            nn.GroupNorm(1, channels * 4),
            nn.GELU(),
        )
        self.bottleneck = ConvStage2D(channels * 4, channels * 4)
        self.up = nn.ConvTranspose2d(channels * 4, channels * 2, 2, stride=2)
        self.decoder = ConvStage2D(channels * 4, channels * 2)
        self.bone_gate_head = nn.Conv2d(channels * 2, 1, 1)
        self.activity_head = nn.Conv2d(channels * 2, 1, 1)
        self.class_head = nn.Conv2d(channels * 2, len(BONE_ACTIVITY_CLASSES), 1)
        self.uncertainty_head = nn.Conv2d(channels * 2, 1, 1)

    def forward(self, white: torch.Tensor, fluorescence: torch.Tensor) -> dict[str, torch.Tensor]:
        if white.ndim != 4 or white.shape[1] != 3:
            raise ValueError("white input must have shape Bx3xHxW")
        if fluorescence.ndim != 4 or fluorescence.shape[1] != 1:
            raise ValueError("fluorescence input must have shape Bx1xHxW")
        if white.shape[0] != fluorescence.shape[0] or white.shape[2:] != fluorescence.shape[2:]:
            raise ValueError("white and fluorescence inputs must share batch and spatial dimensions")
        encoded = self.fusion(
            torch.cat(
                [self.white_encoder(white), self.fluorescence_encoder(fluorescence)],
                dim=1,
            )
        )
        bottleneck = self.bottleneck(self.down(encoded))
        upsampled = self.up(bottleneck)
        if upsampled.shape[2:] != encoded.shape[2:]:
            upsampled = F.interpolate(upsampled, size=encoded.shape[2:], mode="bilinear", align_corners=False)
        decoded = self.decoder(torch.cat([upsampled, encoded], dim=1))
        return {
            "bone_gate_logits": self.bone_gate_head(decoded),
            "activity_score_logits": self.activity_head(decoded),
            "class_logits": self.class_head(decoded),
            "uncertainty_logits": self.uncertainty_head(decoded),
        }


def build_bone_activity_multitask(
    config: Mapping[str, Any] | None = None,
) -> BoneActivityMultiTask2D:
    values = dict(config or {})
    return BoneActivityMultiTask2D(base_channels=int(values.get("base_channels", 8)))


def load_bone_activity_multitask_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[BoneActivityMultiTask2D, dict[str, Any]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("state_dict"), dict):
        raise ValueError("Bone-activity checkpoint must contain a state_dict mapping")
    model = build_bone_activity_multitask(checkpoint.get("model_config")).to(device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model, {key: value for key, value in checkpoint.items() if key != "state_dict"}


def bone_activity_probabilities(
    outputs: Mapping[str, torch.Tensor],
) -> dict[str, torch.Tensor]:
    _require_outputs(outputs)
    return {
        "bone_gate_probability": torch.sigmoid(outputs["bone_gate_logits"]),
        "activity_score": torch.sigmoid(outputs["activity_score_logits"]),
        "class_probabilities": torch.softmax(outputs["class_logits"], dim=1),
        "uncertainty": torch.sigmoid(outputs["uncertainty_logits"]),
    }


def apply_bone_activity_safety_gate(
    outputs: Mapping[str, torch.Tensor],
    *,
    reviewed_bone_gate: torch.Tensor | None,
    physician_reviewed_bone_gate: bool,
    target_domain: bool,
    model_promotion_ready: bool = False,
    abstention_threshold: float = 0.5,
) -> dict[str, Any]:
    probabilities = bone_activity_probabilities(outputs)
    gate_probability = probabilities["bone_gate_probability"]
    reasons: list[str] = []
    if not all(bool(torch.isfinite(value).all()) for value in probabilities.values()):
        reasons.append("non_finite_model_output")
    if not target_domain:
        reasons.append("non_target_domain_proxy")
    if not model_promotion_ready:
        reasons.append("model_target_domain_promotion_missing")
    if not physician_reviewed_bone_gate or reviewed_bone_gate is None:
        reasons.append("physician_reviewed_bone_gate_missing")
        trusted_gate = torch.zeros_like(gate_probability, dtype=torch.bool)
    else:
        try:
            trusted_gate = _normalize_gate(reviewed_bone_gate, gate_probability)
        except ValueError:
            trusted_gate = torch.zeros_like(gate_probability, dtype=torch.bool)
            reasons.append("physician_reviewed_bone_gate_invalid")
        else:
            if not bool(trusted_gate.any()):
                reasons.append("physician_reviewed_bone_gate_empty")

    if reasons:
        abstention = torch.ones_like(gate_probability, dtype=torch.bool)
        class_prediction = torch.full_like(gate_probability[:, 0], IGNORE_INDEX, dtype=torch.long)
        return {
            "available": False,
            "spatial_candidates_available": False,
            "failure_reasons": reasons,
            "bone_gate": torch.zeros_like(gate_probability),
            "activity_score": torch.zeros_like(probabilities["activity_score"]),
            "class_probabilities": torch.zeros_like(probabilities["class_probabilities"]),
            "class_prediction": class_prediction,
            "uncertainty": torch.ones_like(gate_probability),
            "abstention_mask": abstention,
            "ignore_mask": abstention,
            "activity_score_available_mask": torch.zeros_like(abstention),
            "raw_engineering_outputs": probabilities,
            "target_domain_promotion_ready": False,
            "medical_boundary": _medical_boundary(),
        }

    threshold = float(abstention_threshold)
    if threshold <= 0.0 or threshold >= 1.0:
        raise ValueError("abstention_threshold must be within (0, 1)")
    uncertainty = probabilities["uncertainty"]
    abstention = (uncertainty >= threshold) | (~trusted_gate)
    activity_available = ~abstention
    class_probabilities = probabilities["class_probabilities"] * activity_available.to(dtype=torch.float32)
    activity_score = probabilities["activity_score"] * activity_available.to(dtype=torch.float32)
    class_prediction = torch.argmax(class_probabilities, dim=1)
    class_prediction = class_prediction.masked_fill(abstention[:, 0], IGNORE_INDEX)
    return {
        "available": True,
        "spatial_candidates_available": True,
        "failure_reasons": [],
        "bone_gate": trusted_gate.to(dtype=torch.float32),
        "activity_score": activity_score,
        "class_probabilities": class_probabilities,
        "class_prediction": class_prediction,
        "uncertainty": uncertainty,
        "abstention_mask": abstention,
        "ignore_mask": abstention,
        "activity_score_available_mask": activity_available,
        "raw_engineering_outputs": probabilities,
        "target_domain_promotion_ready": True,
        "medical_boundary": _medical_boundary(),
    }


def bone_activity_multitask_loss(
    outputs: Mapping[str, torch.Tensor],
    targets: Mapping[str, torch.Tensor],
    *,
    weights: Mapping[str, float] | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    _require_outputs(outputs)
    gate_target = targets["bone_gate"].to(dtype=torch.float32)
    activity_target = targets["activity_score"].to(dtype=torch.float32)
    class_target = targets["class_target"].to(dtype=torch.long)
    uncertainty_target = targets["uncertainty"].to(dtype=torch.float32)
    if gate_target.ndim == 3:
        gate_target = gate_target[:, None]
    if activity_target.ndim == 3:
        activity_target = activity_target[:, None]
    if uncertainty_target.ndim == 3:
        uncertainty_target = uncertainty_target[:, None]
    gate_logits = outputs["bone_gate_logits"]
    gate_probability = torch.sigmoid(gate_logits)
    gate_bce = F.binary_cross_entropy_with_logits(gate_logits, gate_target)
    intersection = (gate_probability * gate_target).sum(dim=(1, 2, 3))
    denominator = gate_probability.sum(dim=(1, 2, 3)) + gate_target.sum(dim=(1, 2, 3))
    gate_dice = 1.0 - ((2.0 * intersection + 1e-5) / (denominator + 1e-5)).mean()
    valid = (gate_target > 0.5) & (class_target[:, None] != IGNORE_INDEX)
    activity_probability = torch.sigmoid(outputs["activity_score_logits"])
    activity_loss = _masked_smooth_l1(activity_probability, activity_target, valid)
    class_loss = (
        F.cross_entropy(outputs["class_logits"], class_target, ignore_index=IGNORE_INDEX)
        if bool((class_target != IGNORE_INDEX).any())
        else outputs["class_logits"].sum() * 0.0
    )
    uncertainty_loss = F.binary_cross_entropy_with_logits(outputs["uncertainty_logits"], uncertainty_target)
    resolved = {
        "bone_gate": 1.0,
        "activity_score": 1.0,
        "class_logits": 1.0,
        "uncertainty": 0.5,
    }
    resolved.update({key: float(value) for key, value in dict(weights or {}).items() if key in resolved})
    components = {
        "bone_gate": 0.5 * gate_bce + 0.5 * gate_dice,
        "activity_score": activity_loss,
        "class_logits": class_loss,
        "uncertainty": uncertainty_loss,
    }
    total = outputs["bone_gate_logits"].sum() * 0.0
    for key, component in components.items():
        total = total + component * resolved[key]
    return total, components


def _normalize_gate(value: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    gate = value.to(device=reference.device)
    if gate.ndim == 3:
        gate = gate[:, None]
    if gate.shape != reference.shape:
        raise ValueError("reviewed_bone_gate must match Bx1xHxW model output shape")
    gate_float = gate.to(dtype=torch.float32)
    if not bool(torch.isfinite(gate_float).all()):
        raise ValueError("reviewed_bone_gate must contain only finite values")
    return gate_float > 0.5


def _masked_smooth_l1(prediction: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    if not bool(mask.any()):
        return prediction.sum() * 0.0
    return F.smooth_l1_loss(prediction[mask], target[mask])


def _require_outputs(outputs: Mapping[str, torch.Tensor]) -> None:
    required = {
        "bone_gate_logits",
        "activity_score_logits",
        "class_logits",
        "uncertainty_logits",
    }
    missing = sorted(required - set(outputs))
    if missing:
        raise ValueError(f"Bone-activity outputs missing keys: {missing}")


def _medical_boundary() -> str:
    return (
        "Bone-activity outputs are research validation candidates. Spatial classes require a trusted "
        "physician-reviewed bone gate and target-domain validation; abstained pixels remain unavailable."
    )
