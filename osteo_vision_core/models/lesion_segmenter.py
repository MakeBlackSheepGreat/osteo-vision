from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from osteo_vision_core.core.paths import ensure_dir


class ConvNeXtBlock3D(nn.Module):
    """Small ConvNeXt-style residual block for 64 cubed CBCT ROI smoke runs."""

    def __init__(self, channels: int, *, kernel_size: int = 5) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.depthwise = nn.Conv3d(channels, channels, kernel_size, padding=padding, groups=channels)
        self.norm = nn.GroupNorm(1, channels)
        self.pointwise = nn.Sequential(
            nn.Conv3d(channels, channels * 2, 1),
            nn.GELU(),
            nn.Conv3d(channels * 2, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pointwise(self.norm(self.depthwise(x)))


class ConvStage3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.stage = nn.Sequential(
            nn.Conv3d(in_channels, out_channels, 3, padding=1),
            nn.GroupNorm(1, out_channels),
            nn.GELU(),
            ConvNeXtBlock3D(out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.stage(x)


class TinyLesionSegmenter3D(nn.Module):
    """A compact 3D U-Net style segmenter for D025 lesion ROI proxy experiments."""

    def __init__(self, in_channels: int = 1, out_channels: int = 2, base_channels: int = 4) -> None:
        super().__init__()
        c1 = base_channels
        c2 = base_channels * 2
        c3 = base_channels * 4
        self.enc0 = ConvStage3D(in_channels, c1)
        self.down1 = nn.Sequential(nn.Conv3d(c1, c2, 3, stride=2, padding=1), nn.GroupNorm(1, c2), nn.GELU())
        self.enc1 = ConvStage3D(c2, c2)
        self.down2 = nn.Sequential(nn.Conv3d(c2, c3, 3, stride=2, padding=1), nn.GroupNorm(1, c3), nn.GELU())
        self.bottleneck = ConvStage3D(c3, c3)
        self.up1 = nn.ConvTranspose3d(c3, c2, 2, stride=2)
        self.dec1 = ConvStage3D(c2 + c2, c2)
        self.up0 = nn.ConvTranspose3d(c2, c1, 2, stride=2)
        self.dec0 = ConvStage3D(c1 + c1, c1)
        self.head = nn.Conv3d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = self.up1(x2)
        if y1.shape[2:] != x1.shape[2:]:
            y1 = F.interpolate(y1, size=x1.shape[2:], mode="trilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = self.up0(y1)
        if y0.shape[2:] != x0.shape[2:]:
            y0 = F.interpolate(y0, size=x0.shape[2:], mode="trilinear", align_corners=False)
        return self.head(self.dec0(torch.cat([y0, x0], dim=1)))


def build_tiny_lesion_segmenter(config: dict[str, Any] | None = None) -> TinyLesionSegmenter3D:
    model_config = dict(config or {})
    return TinyLesionSegmenter3D(
        in_channels=int(model_config.get("in_channels", 1)),
        out_channels=int(model_config.get("out_channels", 2)),
        base_channels=int(model_config.get("base_channels", 4)),
    )


def select_torch_device(policy: str = "auto") -> torch.device:
    if policy in {"auto", "gpu", "cuda"} and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_npz_image(input_path: str | Path) -> np.ndarray:
    path = Path(input_path)
    with np.load(path) as payload:
        if "image" not in payload.files:
            raise ValueError(f"{path} missing required 'image' array")
        image = payload["image"].astype(np.float32, copy=False)
    if image.ndim != 3:
        raise ValueError(f"{path} image must be a 3D array, got shape {image.shape}")
    return image


def load_npz_label(input_path: str | Path) -> np.ndarray:
    path = Path(input_path)
    with np.load(path) as payload:
        if "label" not in payload.files:
            raise ValueError(f"{path} missing required 'label' array")
        label = payload["label"].astype(np.int64, copy=False)
    if label.ndim != 3:
        raise ValueError(f"{path} label must be a 3D array, got shape {label.shape}")
    return label


def load_lesion_segmenter_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[TinyLesionSegmenter3D, dict[str, Any]]:
    checkpoint = _torch_load(checkpoint_path, device)
    if not isinstance(checkpoint, dict):
        raise ValueError(f"Unsupported checkpoint payload: {checkpoint_path}")
    model_config = dict(checkpoint.get("model_config") or {})
    model = build_tiny_lesion_segmenter(model_config).to(device)
    state_dict = checkpoint.get("state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError(f"Checkpoint missing state_dict: {checkpoint_path}")
    model.load_state_dict(state_dict)
    model.eval()
    metadata = {key: value for key, value in checkpoint.items() if key != "state_dict"}
    return model, metadata


def predict_npz_roi(
    model: nn.Module,
    input_path: str | Path,
    *,
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    threshold: float = 0.5,
    model_id: str = "d025_lesion_smoke_segmenter",
) -> dict[str, Any]:
    image = load_npz_image(input_path)
    tensor = torch.from_numpy(image[None, None]).to(device=device, dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        logits = model(tensor)
        probability = torch.softmax(logits, dim=1)[0, 1].detach().cpu().numpy().astype(np.float32)
    mask = (probability >= float(threshold)).astype(np.uint8)
    out_dir = ensure_dir(output_dir)
    mask_path = out_dir / f"{case_id}_{model_id}_mask.npz"
    np.savez_compressed(
        mask_path, mask=mask, probability=probability.astype(np.float16), threshold=np.float32(threshold)
    )
    positive_voxels = int(mask.sum())
    total_voxels = int(mask.size)
    quantification = {
        "available": True,
        "source": model_id,
        "threshold": float(threshold),
        "positive_voxels": positive_voxels,
        "total_voxels": total_voxels,
        "positive_fraction": float(positive_voxels / total_voxels) if total_voxels else 0.0,
        "mean_probability": float(probability.mean()),
        "max_probability": float(probability.max()),
    }
    segmentation_mask = {
        "case_id": case_id,
        "source": model_id,
        "format": "npz_volume_mask",
        "path": str(mask_path),
        "shape": [int(item) for item in mask.shape],
        "positive_voxels": positive_voxels,
        "threshold": float(threshold),
    }
    return {
        "segmentation_mask": segmentation_mask,
        "lesion_evidence": {
            "type": "volume_mask",
            "source": model_id,
            "path": str(mask_path),
            "input_domain": "D025 CBCT lesion ROI proxy",
        },
        "quantification": quantification,
        "prediction": {
            "segmentation_available": True,
            "mask_path": str(mask_path),
            "positive_fraction": quantification["positive_fraction"],
        },
        "score": quantification["positive_fraction"],
    }


def checkpoint_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _torch_load(path: str | Path, device: torch.device) -> Any:
    try:
        return torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=device)
