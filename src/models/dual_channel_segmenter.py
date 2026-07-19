from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch import nn

from src.core.paths import ensure_dir
from src.models.keyframe_segmenter import ConvStage2D, connected_probability_candidates
from src.preprocess.fluorescence import apply_fluorescence_colormap, blend_pseudocolor_on_reference

DUAL_CHANNEL_MODES = (
    "white_only",
    "fluorescence_only",
    "early_fusion",
    "intermediate_fusion",
    "context_fusion",
)


class TinyDualChannelSegmenter2D(nn.Module):
    """Dual-encoder baseline with explicit single-channel and fusion ablations."""

    def __init__(self, base_channels: int = 8) -> None:
        super().__init__()
        self.white_encoder = ConvStage2D(3, base_channels)
        self.fluorescence_encoder = ConvStage2D(1, base_channels)
        self.early_encoder = ConvStage2D(4, base_channels * 2)
        self.white_projection = nn.Conv2d(base_channels, base_channels * 2, 1)
        self.fluorescence_projection = nn.Conv2d(base_channels, base_channels * 2, 1)
        self.intermediate_fusion = ConvStage2D(base_channels * 2, base_channels * 2)
        self.head = nn.Sequential(
            ConvStage2D(base_channels * 2, base_channels),
            nn.Conv2d(base_channels, 1, 1),
        )

    def forward(self, white: torch.Tensor, fluorescence: torch.Tensor, *, mode: str) -> torch.Tensor:
        if mode not in DUAL_CHANNEL_MODES:
            raise ValueError(f"Unsupported dual-channel mode: {mode}")
        white_features = self.white_encoder(white)
        fluorescence_features = self.fluorescence_encoder(fluorescence)
        if mode == "white_only":
            fused = self.white_projection(white_features)
        elif mode == "fluorescence_only":
            fused = self.fluorescence_projection(fluorescence_features)
        elif mode == "early_fusion":
            fused = self.early_encoder(torch.cat([white, fluorescence], dim=1))
        elif mode == "intermediate_fusion":
            gate = torch.sigmoid(self.fluorescence_projection(fluorescence_features))
            white_projected = self.white_projection(white_features)
            fused = self.intermediate_fusion(white_projected * (0.5 + gate) + gate)
        else:
            white_context = torch.sigmoid(torch.mean(self.white_projection(white_features), dim=(2, 3), keepdim=True))
            fluorescence_projected = self.fluorescence_projection(fluorescence_features)
            fused = fluorescence_projected * (0.75 + 0.5 * white_context)
        return self.head(fused)


def load_dual_channel_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[TinyDualChannelSegmenter2D, dict[str, Any]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model_config = dict(checkpoint.get("model_config") or {})
    model = TinyDualChannelSegmenter2D(base_channels=int(model_config.get("base_channels", 8))).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, {key: value for key, value in checkpoint.items() if key != "state_dict"}


def load_dual_inputs(white_path: str | Path, fluorescence_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(white_path) as white_obj, Image.open(fluorescence_path) as fluorescence_obj:
        white = np.asarray(white_obj.convert("RGB"), dtype=np.uint8)
        fluorescence_image = fluorescence_obj.convert("L")
        if fluorescence_image.size != white_obj.size:
            fluorescence_image = fluorescence_image.resize(white_obj.size, Image.Resampling.BILINEAR)
        fluorescence = np.asarray(fluorescence_image, dtype=np.uint8)
    return white, fluorescence


def predict_dual_channel(
    model: TinyDualChannelSegmenter2D,
    white_path: str | Path,
    fluorescence_path: str | Path,
    *,
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    threshold: float,
    mode: str = "early_fusion",
) -> dict[str, Any]:
    white, fluorescence = load_dual_inputs(white_path, fluorescence_path)
    white_tensor = torch.from_numpy(white.transpose(2, 0, 1)[None].astype(np.float32) / 255.0).to(device)
    fluorescence_tensor = torch.from_numpy(fluorescence[None, None].astype(np.float32) / 255.0).to(device)
    with torch.no_grad():
        probability = torch.sigmoid(model(white_tensor, fluorescence_tensor, mode=mode))[0, 0].cpu().numpy()
    mask = (probability >= threshold).astype(np.uint8)
    safe_case = "".join(char if char.isalnum() or char in "._-" else "_" for char in case_id)
    out_dir = ensure_dir(output_dir)
    mask_path = out_dir / f"{safe_case}_{mode}_mask.png"
    probability_path = out_dir / f"{safe_case}_{mode}_probability.png"
    overlay_path = out_dir / f"{safe_case}_{mode}_overlay.png"
    pseudo = apply_fluorescence_colormap(probability, "green")
    overlay = blend_pseudocolor_on_reference(white, pseudo, alpha=0.45)
    Image.fromarray(mask * 255).save(mask_path)
    Image.fromarray(np.clip(probability * 255, 0, 255).astype(np.uint8)).save(probability_path)
    Image.fromarray(overlay).save(overlay_path)
    candidates = connected_probability_candidates(
        mask,
        probability,
        min_component_area=16,
        model_id="dual_channel_segmenter",
    )
    return {
        "available": True,
        "mode": mode,
        "mask_path": str(mask_path),
        "probability_path": str(probability_path),
        "overlay_path": str(overlay_path),
        "positive_area_px": int(mask.sum()),
        "positive_area_fraction": float(mask.mean()),
        "mean_probability": float(probability.mean()),
        "max_probability": float(probability.max()),
        "candidates": candidates,
        "medical_boundary": (
            "Dual-channel proxy segmentation for engineering validation; physician review is required and "
            "the output is not a disease-final mask."
        ),
    }
