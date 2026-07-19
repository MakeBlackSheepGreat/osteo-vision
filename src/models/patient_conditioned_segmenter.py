from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
import torch.nn.functional as F
from torch import nn

from src.models.keyframe_segmenter import ConvStage2D


@dataclass(frozen=True)
class PatientConditionedSegmentationOutput:
    image_only_logits: torch.Tensor
    conditioned_logits: torch.Tensor
    delta_map: torch.Tensor
    uncertainty: torch.Tensor
    context_eligible: torch.Tensor
    effective_present_fraction: torch.Tensor


class PatientConditionedUNetBackbone2D(nn.Module):
    """Compact multi-scale feature backbone for spatially contextual segmentation."""

    def __init__(self, *, in_channels: int, base_channels: int) -> None:
        super().__init__()
        c1 = int(base_channels)
        c2 = c1 * 2
        c3 = c1 * 4
        self.output_channels = c1
        self.enc0 = ConvStage2D(in_channels, c1)
        self.down1 = nn.Sequential(
            nn.Conv2d(c1, c2, 3, stride=2, padding=1),
            nn.GroupNorm(1, c2),
            nn.GELU(),
        )
        self.enc1 = ConvStage2D(c2, c2)
        self.down2 = nn.Sequential(
            nn.Conv2d(c2, c3, 3, stride=2, padding=1),
            nn.GroupNorm(1, c3),
            nn.GELU(),
        )
        self.bottleneck = ConvStage2D(c3, c3)
        self.up1 = nn.ConvTranspose2d(c3, c2, 2, stride=2)
        self.dec1 = ConvStage2D(c2 + c2, c2)
        self.up0 = nn.ConvTranspose2d(c2, c1, 2, stride=2)
        self.dec0 = ConvStage2D(c1 + c1, c1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(value)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = self.up1(x2)
        if y1.shape[2:] != x1.shape[2:]:
            y1 = F.interpolate(y1, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = self.up0(y1)
        if y0.shape[2:] != x0.shape[2:]:
            y0 = F.interpolate(y0, size=x0.shape[2:], mode="bilinear", align_corners=False)
        return self.dec0(torch.cat([y0, x0], dim=1))


class TinyPatientConditionedSegmenter2D(nn.Module):
    """Dual-channel segmenter with bounded, fail-closed clinical modulation."""

    def __init__(
        self,
        *,
        clinical_feature_count: int,
        base_channels: int = 8,
        modulation_basis_count: int = 4,
        clinical_hidden_channels: int = 16,
        max_logit_delta: float = 0.75,
        min_present_fraction: float = 0.5,
        image_backbone: str = "local",
        clinical_mean: Sequence[float] | None = None,
        clinical_scale: Sequence[float] | None = None,
    ) -> None:
        super().__init__()
        if clinical_feature_count <= 0:
            raise ValueError("clinical_feature_count must be positive")
        if modulation_basis_count <= 0:
            raise ValueError("modulation_basis_count must be positive")
        if max_logit_delta < 0:
            raise ValueError("max_logit_delta must be non-negative")
        if not 0 <= min_present_fraction <= 1:
            raise ValueError("min_present_fraction must be within [0, 1]")

        self.clinical_feature_count = int(clinical_feature_count)
        self.base_channels = int(base_channels)
        self.modulation_basis_count = int(modulation_basis_count)
        self.clinical_hidden_channels = int(clinical_hidden_channels)
        self.max_logit_delta = float(max_logit_delta)
        self.min_present_fraction = float(min_present_fraction)
        self.image_backbone = str(image_backbone).strip().lower()
        self.image_encoder: nn.Module
        self.image_only_head: nn.Module
        if self.image_backbone == "local":
            feature_channels = int(base_channels) * 2
            self.image_encoder = nn.Sequential(
                ConvStage2D(4, feature_channels),
                ConvStage2D(feature_channels, feature_channels),
            )
            self.image_only_head = nn.Sequential(
                ConvStage2D(feature_channels, int(base_channels)),
                nn.Conv2d(int(base_channels), 1, kernel_size=1),
            )
        elif self.image_backbone == "unet":
            backbone = PatientConditionedUNetBackbone2D(in_channels=4, base_channels=int(base_channels))
            feature_channels = backbone.output_channels
            self.image_encoder = backbone
            self.image_only_head = nn.Conv2d(feature_channels, 1, kernel_size=1)
        else:
            raise ValueError("image_backbone must be local or unet")
        self.modulation_basis_head = nn.Conv2d(
            feature_channels,
            int(modulation_basis_count),
            kernel_size=1,
        )
        self.clinical_encoder = nn.Sequential(
            nn.Linear(self.clinical_feature_count * 2, int(clinical_hidden_channels)),
            nn.ReLU(inplace=True),
            nn.Linear(int(clinical_hidden_channels), int(modulation_basis_count)),
        )
        mean = _feature_vector(clinical_mean, self.clinical_feature_count, default=0.0)
        scale = _feature_vector(clinical_scale, self.clinical_feature_count, default=1.0)
        if torch.any(scale <= 0):
            raise ValueError("clinical_scale values must be positive")
        self.clinical_mean: torch.Tensor
        self.clinical_scale: torch.Tensor
        self.register_buffer("clinical_mean", mean, persistent=True)
        self.register_buffer("clinical_scale", scale, persistent=True)

    def forward(
        self,
        white: torch.Tensor,
        fluorescence: torch.Tensor,
        clinical_values: torch.Tensor,
        clinical_present_mask: torch.Tensor,
        *,
        context_trusted: torch.Tensor | bool | None = None,
        conditioning_authorized: torch.Tensor | bool | None = None,
    ) -> PatientConditionedSegmentationOutput:
        _validate_image_inputs(white, fluorescence)
        batch_size = white.shape[0]
        _validate_clinical_inputs(
            clinical_values,
            clinical_present_mask,
            batch_size=batch_size,
            feature_count=self.clinical_feature_count,
        )
        trusted = _trusted_mask(context_trusted, batch_size=batch_size, device=white.device)
        authorized = _trusted_mask(conditioning_authorized, batch_size=batch_size, device=white.device)
        declared_present = clinical_present_mask.to(device=white.device, dtype=torch.bool)
        values = clinical_values.to(device=white.device, dtype=white.dtype)
        finite = torch.isfinite(values)
        effective_present = declared_present & finite
        invalid_declared = torch.any(declared_present & ~finite, dim=1)
        present_fraction = effective_present.to(dtype=white.dtype).mean(dim=1)
        eligible = authorized & trusted & ~invalid_declared & (present_fraction >= self.min_present_fraction)

        safe_values = torch.where(effective_present, values, self.clinical_mean)
        normalized = (safe_values - self.clinical_mean) / self.clinical_scale
        normalized = torch.clamp(normalized, min=-8.0, max=8.0)
        clinical_input = torch.cat(
            [normalized, effective_present.to(dtype=white.dtype)],
            dim=1,
        )

        image_features = self.image_encoder(torch.cat([white, fluorescence], dim=1))
        image_only_logits = self.image_only_head(image_features)
        spatial_basis = torch.tanh(self.modulation_basis_head(image_features))
        coefficients = torch.tanh(self.clinical_encoder(clinical_input))[:, :, None, None]
        raw_delta = torch.mean(spatial_basis * coefficients, dim=1, keepdim=True)
        raw_delta = torch.clamp(
            raw_delta * self.max_logit_delta,
            -self.max_logit_delta,
            self.max_logit_delta,
        )
        delta_map = raw_delta * eligible[:, None, None, None].to(dtype=raw_delta.dtype)
        conditioned_logits = image_only_logits + delta_map
        probability = torch.sigmoid(conditioned_logits).clamp(1e-6, 1.0 - 1e-6)
        uncertainty = -(
            probability * torch.log(probability) + (1.0 - probability) * torch.log(1.0 - probability)
        ) / torch.log(torch.tensor(2.0, device=probability.device, dtype=probability.dtype))
        return PatientConditionedSegmentationOutput(
            image_only_logits=image_only_logits,
            conditioned_logits=conditioned_logits,
            delta_map=delta_map,
            uncertainty=uncertainty,
            context_eligible=eligible,
            effective_present_fraction=present_fraction,
        )

    def model_config(self) -> dict[str, Any]:
        return {
            "clinical_feature_count": self.clinical_feature_count,
            "base_channels": self.base_channels,
            "modulation_basis_count": self.modulation_basis_count,
            "clinical_hidden_channels": self.clinical_hidden_channels,
            "max_logit_delta": self.max_logit_delta,
            "min_present_fraction": self.min_present_fraction,
            "image_backbone": self.image_backbone,
            "clinical_mean": self.clinical_mean.detach().cpu().tolist(),
            "clinical_scale": self.clinical_scale.detach().cpu().tolist(),
        }


def load_patient_conditioned_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[TinyPatientConditionedSegmenter2D, dict[str, Any]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model_config"), dict):
        raise ValueError("Patient-conditioned checkpoint is missing model_config")
    model = TinyPatientConditionedSegmenter2D(**checkpoint["model_config"]).to(device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    metadata = {key: value for key, value in checkpoint.items() if key != "state_dict"}
    return model, metadata


def apply_patient_conditioning_safety_gate(
    output: PatientConditionedSegmentationOutput,
    *,
    reviewed_bone_gate: torch.Tensor | None,
    physician_reviewed_bone_gate: torch.Tensor | bool | None,
    clinical_context_verified: torch.Tensor | bool | None,
    target_domain: torch.Tensor | bool | None,
    model_promotion_ready: torch.Tensor | bool | None = None,
    uncertainty_threshold: float = 0.5,
    segmentation_threshold: float = 0.5,
) -> dict[str, Any]:
    """Restrict clinical modulation to reviewed bone and image-uncertain pixels."""

    reference = output.image_only_logits
    if reference.ndim != 4 or reference.shape[1] != 1:
        raise ValueError("image_only_logits must have shape Bx1xHxW")
    for name, value in (
        ("conditioned_logits", output.conditioned_logits),
        ("delta_map", output.delta_map),
        ("uncertainty", output.uncertainty),
    ):
        if value.shape != reference.shape:
            raise ValueError(f"{name} must match image_only_logits shape")
    uncertainty_limit = float(uncertainty_threshold)
    segmentation_limit = float(segmentation_threshold)
    if not 0.0 < uncertainty_limit <= 1.0:
        raise ValueError("uncertainty_threshold must be within (0, 1]")
    if not 0.0 < segmentation_limit < 1.0:
        raise ValueError("segmentation_threshold must be within (0, 1)")

    batch_size = reference.shape[0]
    device = reference.device
    physician_reviewed = _trusted_mask(physician_reviewed_bone_gate, batch_size=batch_size, device=device)
    context_verified = _trusted_mask(clinical_context_verified, batch_size=batch_size, device=device)
    target_domain_mask = _trusted_mask(target_domain, batch_size=batch_size, device=device)
    promoted = _trusted_mask(model_promotion_ready, batch_size=batch_size, device=device)

    gate_error: str | None = None
    if reviewed_bone_gate is None:
        reviewed_gate = torch.zeros_like(reference, dtype=torch.bool)
        gate_error = "physician_reviewed_bone_gate_missing"
    else:
        try:
            reviewed_gate = _normalize_spatial_gate(reviewed_bone_gate, reference)
        except ValueError:
            reviewed_gate = torch.zeros_like(reference, dtype=torch.bool)
            gate_error = "physician_reviewed_bone_gate_invalid"

    finite_outputs = (
        torch.isfinite(reference).flatten(1).all(dim=1)
        & torch.isfinite(output.delta_map).flatten(1).all(dim=1)
        & torch.isfinite(output.uncertainty).flatten(1).all(dim=1)
    )
    gate_nonempty = reviewed_gate.flatten(1).any(dim=1)
    eligible = output.context_eligible.to(device=device, dtype=torch.bool).reshape(-1)
    if eligible.numel() != batch_size:
        raise ValueError("context_eligible must contain one value per batch item")

    sample_failure_reasons: list[list[str]] = []
    for index in range(batch_size):
        reasons: list[str] = []
        if not bool(target_domain_mask[index]):
            reasons.append("non_target_domain_proxy")
        if not bool(promoted[index]):
            reasons.append("model_target_domain_promotion_missing")
        if not bool(context_verified[index]):
            reasons.append("clinical_context_not_verified")
        if not bool(eligible[index]):
            reasons.append("clinical_context_ineligible")
        if not bool(physician_reviewed[index]):
            reasons.append("physician_reviewed_bone_gate_missing")
        if gate_error is not None:
            reasons.append(gate_error)
        elif not bool(gate_nonempty[index]):
            reasons.append("physician_reviewed_bone_gate_empty")
        if not bool(finite_outputs[index]):
            reasons.append("non_finite_model_output")
        sample_failure_reasons.append(list(dict.fromkeys(reasons)))

    sample_available = torch.tensor(
        [not reasons for reasons in sample_failure_reasons],
        dtype=torch.bool,
        device=device,
    )
    uncertainty_region = torch.isfinite(output.uncertainty) & (output.uncertainty >= uncertainty_limit)
    spatial_effect_mask = reviewed_gate & uncertainty_region & sample_available[:, None, None, None]
    finite_delta = torch.where(torch.isfinite(output.delta_map), output.delta_map, torch.zeros_like(output.delta_map))
    safe_delta = torch.where(spatial_effect_mask, finite_delta, torch.zeros_like(finite_delta))
    safe_image_only_logits = torch.where(torch.isfinite(reference), reference, torch.zeros_like(reference))
    conditioned_logits = safe_image_only_logits + safe_delta
    image_only_probability = torch.sigmoid(safe_image_only_logits)
    conditioned_probability = torch.sigmoid(conditioned_logits)
    difference_mask = (image_only_probability >= segmentation_limit) ^ (conditioned_probability >= segmentation_limit)
    failure_reasons = list(dict.fromkeys(reason for reasons in sample_failure_reasons for reason in reasons))
    return {
        "available": bool(sample_available.all()),
        "sample_available_mask": sample_available,
        "spatial_effect_applied": bool(torch.count_nonzero(safe_delta).item()),
        "failure_reasons": failure_reasons,
        "sample_failure_reasons": sample_failure_reasons,
        "image_only_logits": safe_image_only_logits,
        "image_only_probability": image_only_probability,
        "conditioned_logits": conditioned_logits,
        "conditioned_probability": conditioned_probability,
        "delta_map": safe_delta,
        "difference_mask": difference_mask,
        "spatial_effect_mask": spatial_effect_mask,
        "reviewed_bone_gate": reviewed_gate,
        "image_uncertainty_region": uncertainty_region,
        "uncertainty": torch.where(
            torch.isfinite(output.uncertainty),
            output.uncertainty,
            torch.ones_like(output.uncertainty),
        ),
        "raw_engineering_outputs": output,
        "target_domain_promotion_ready": bool((target_domain_mask & promoted).all()),
        "medical_boundary": (
            "Patient-conditioned spatial effects require verified clinical context, target-domain "
            "promotion, a physician-reviewed bone gate, and image uncertainty. Failed gates preserve "
            "the image-only result for physician review."
        ),
    }


def _feature_vector(values: Sequence[float] | None, count: int, *, default: float) -> torch.Tensor:
    source = [default] * count if values is None else [float(value) for value in values]
    if len(source) != count:
        raise ValueError(f"Expected {count} clinical normalization values, got {len(source)}")
    tensor = torch.tensor(source, dtype=torch.float32)
    if not torch.isfinite(tensor).all():
        raise ValueError("Clinical normalization values must be finite")
    return tensor


def _validate_image_inputs(white: torch.Tensor, fluorescence: torch.Tensor) -> None:
    if white.ndim != 4 or white.shape[1] != 3:
        raise ValueError("white must have shape Bx3xHxW")
    if fluorescence.ndim != 4 or fluorescence.shape[1] != 1:
        raise ValueError("fluorescence must have shape Bx1xHxW")
    if white.shape[0] != fluorescence.shape[0] or white.shape[2:] != fluorescence.shape[2:]:
        raise ValueError("White-light and fluorescence tensors must share batch and spatial shape")


def _validate_clinical_inputs(
    values: torch.Tensor,
    present_mask: torch.Tensor,
    *,
    batch_size: int,
    feature_count: int,
) -> None:
    expected = (batch_size, feature_count)
    if tuple(values.shape) != expected or tuple(present_mask.shape) != expected:
        raise ValueError(f"Clinical values and present mask must have shape {expected}")


def _trusted_mask(
    value: torch.Tensor | bool | None,
    *,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    if value is None:
        return torch.zeros(batch_size, dtype=torch.bool, device=device)
    if isinstance(value, bool):
        return torch.full((batch_size,), value, dtype=torch.bool, device=device)
    flattened = value.to(device=device, dtype=torch.bool).reshape(-1)
    if flattened.numel() != batch_size:
        raise ValueError(f"context_trusted must contain {batch_size} values")
    return flattened


def _normalize_spatial_gate(value: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    gate = value.to(device=reference.device)
    if gate.ndim == 3:
        gate = gate[:, None]
    if gate.shape != reference.shape:
        raise ValueError("reviewed_bone_gate must match Bx1xHxW model output shape")
    gate_float = gate.to(dtype=torch.float32)
    if not bool(torch.isfinite(gate_float).all()):
        raise ValueError("reviewed_bone_gate must contain only finite values")
    return gate_float > 0.5
