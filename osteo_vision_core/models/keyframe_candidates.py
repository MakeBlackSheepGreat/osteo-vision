from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F
from torch import nn


class ResidualBlock2D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        groups = _group_count(out_channels)
        self.body = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
        )
        self.shortcut = (
            nn.Identity() if in_channels == out_channels else nn.Conv2d(in_channels, out_channels, 1, bias=False)
        )
        self.activation = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.activation(self.body(x) + self.shortcut(x))


class SqueezeExcitation2D(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        hidden = max(4, channels // 4)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.scale = nn.Sequential(
            nn.Conv2d(channels, hidden, 1),
            nn.SiLU(inplace=True),
            nn.Conv2d(hidden, channels, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * self.scale(self.pool(x))


class AttentionGate2D(nn.Module):
    def __init__(self, skip_channels: int, decoder_channels: int) -> None:
        super().__init__()
        hidden = max(4, min(skip_channels, decoder_channels) // 2)
        self.skip_projection = nn.Conv2d(skip_channels, hidden, 1, bias=False)
        self.decoder_projection = nn.Conv2d(decoder_channels, hidden, 1, bias=False)
        self.gate = nn.Sequential(nn.SiLU(inplace=True), nn.Conv2d(hidden, 1, 1), nn.Sigmoid())

    def forward(self, skip: torch.Tensor, decoder: torch.Tensor) -> torch.Tensor:
        if decoder.shape[2:] != skip.shape[2:]:
            decoder = F.interpolate(decoder, size=skip.shape[2:], mode="bilinear", align_corners=False)
        weights = self.gate(self.skip_projection(skip) + self.decoder_projection(decoder))
        return skip * weights


class PlainConvBlock2D(nn.Module):
    """Conventional U-Net block used as a lightweight architecture reference."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        groups = _group_count(out_channels)
        self.body = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.body(x)


class PlainUNet2D(nn.Module):
    """Plain 2D U-Net reference without residual or attention modules."""

    def __init__(self, in_channels: int = 3, out_channels: int = 2, base_channels: int = 12) -> None:
        super().__init__()
        c1, c2, c3 = base_channels, base_channels * 2, base_channels * 4
        self.enc0 = PlainConvBlock2D(in_channels, c1)
        self.down1 = nn.Conv2d(c1, c2, 3, stride=2, padding=1, bias=False)
        self.enc1 = PlainConvBlock2D(c2, c2)
        self.down2 = nn.Conv2d(c2, c3, 3, stride=2, padding=1, bias=False)
        self.bottleneck = PlainConvBlock2D(c3, c3)
        self.dec1 = PlainConvBlock2D(c3 + c2, c2)
        self.dec0 = PlainConvBlock2D(c2 + c1, c1)
        self.head = nn.Conv2d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = F.interpolate(x2, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = F.interpolate(y1, size=x0.shape[2:], mode="bilinear", align_corners=False)
        return self.head(self.dec0(torch.cat([y0, x0], dim=1)))


class NestedSkipUNet2D(nn.Module):
    """Compact U-Net++-style reference with dense decoder skip paths."""

    def __init__(self, in_channels: int = 3, out_channels: int = 2, base_channels: int = 12) -> None:
        super().__init__()
        c1, c2, c3 = base_channels, base_channels * 2, base_channels * 4
        self.x0_0 = PlainConvBlock2D(in_channels, c1)
        self.down1 = nn.Conv2d(c1, c2, 3, stride=2, padding=1, bias=False)
        self.x1_0 = PlainConvBlock2D(c2, c2)
        self.down2 = nn.Conv2d(c2, c3, 3, stride=2, padding=1, bias=False)
        self.x2_0 = PlainConvBlock2D(c3, c3)
        self.x0_1 = PlainConvBlock2D(c1 + c2, c1)
        self.x1_1 = PlainConvBlock2D(c2 + c3, c2)
        self.x0_2 = PlainConvBlock2D(c1 + c1 + c2, c1)
        self.head = nn.Conv2d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0_0 = self.x0_0(x)
        x1_0 = self.x1_0(self.down1(x0_0))
        x2_0 = self.x2_0(self.down2(x1_0))
        x0_1 = self.x0_1(
            torch.cat([x0_0, F.interpolate(x1_0, size=x0_0.shape[2:], mode="bilinear", align_corners=False)], dim=1)
        )
        x1_1 = self.x1_1(
            torch.cat([x1_0, F.interpolate(x2_0, size=x1_0.shape[2:], mode="bilinear", align_corners=False)], dim=1)
        )
        x0_2 = self.x0_2(
            torch.cat(
                [
                    x0_0,
                    x0_1,
                    F.interpolate(x1_1, size=x0_0.shape[2:], mode="bilinear", align_corners=False),
                ],
                dim=1,
            )
        )
        return self.head(x0_2)


class ResidualAttentionUNet2D(nn.Module):
    """Residual U-Net with channel and skip attention for keyframe masks."""

    def __init__(self, in_channels: int = 3, out_channels: int = 2, base_channels: int = 12) -> None:
        super().__init__()
        c1 = base_channels
        c2 = base_channels * 2
        c3 = base_channels * 4
        c4 = base_channels * 8
        self.enc0 = nn.Sequential(ResidualBlock2D(in_channels, c1), SqueezeExcitation2D(c1))
        self.down1 = nn.Conv2d(c1, c2, 3, stride=2, padding=1, bias=False)
        self.enc1 = nn.Sequential(ResidualBlock2D(c2, c2), SqueezeExcitation2D(c2))
        self.down2 = nn.Conv2d(c2, c3, 3, stride=2, padding=1, bias=False)
        self.enc2 = nn.Sequential(ResidualBlock2D(c3, c3), SqueezeExcitation2D(c3))
        self.down3 = nn.Conv2d(c3, c4, 3, stride=2, padding=1, bias=False)
        self.bottleneck = nn.Sequential(ResidualBlock2D(c4, c4), SqueezeExcitation2D(c4))
        self.attn2 = AttentionGate2D(c3, c4)
        self.dec2 = ResidualBlock2D(c4 + c3, c3)
        self.attn1 = AttentionGate2D(c2, c3)
        self.dec1 = ResidualBlock2D(c3 + c2, c2)
        self.attn0 = AttentionGate2D(c1, c2)
        self.dec0 = ResidualBlock2D(c2 + c1, c1)
        self.head = nn.Conv2d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.enc2(self.down2(x1))
        x3 = self.bottleneck(self.down3(x2))
        y2 = F.interpolate(x3, size=x2.shape[2:], mode="bilinear", align_corners=False)
        y2 = self.dec2(torch.cat([y2, self.attn2(x2, x3)], dim=1))
        y1 = F.interpolate(y2, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, self.attn1(x1, y2)], dim=1))
        y0 = F.interpolate(y1, size=x0.shape[2:], mode="bilinear", align_corners=False)
        y0 = self.dec0(torch.cat([y0, self.attn0(x0, y1)], dim=1))
        return self.head(y0)


class DepthwiseResidualBlock2D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, *, dilation: int = 1) -> None:
        super().__init__()
        self.projection = nn.Conv2d(in_channels, out_channels, 1, bias=False)
        self.body = nn.Sequential(
            nn.Conv2d(
                out_channels,
                out_channels,
                3,
                padding=dilation,
                dilation=dilation,
                groups=out_channels,
                bias=False,
            ),
            nn.GroupNorm(_group_count(out_channels), out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 1, bias=False),
        )
        self.norm = nn.GroupNorm(_group_count(out_channels), out_channels)
        self.activation = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        projected = self.projection(x)
        return self.activation(self.norm(projected + self.body(projected)))


class MultiScaleContext2D(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        branch_channels = max(4, channels // 4)
        self.branches = nn.ModuleList(
            DepthwiseResidualBlock2D(channels, branch_channels, dilation=dilation) for dilation in (1, 2, 4, 6)
        )
        self.fuse = nn.Sequential(
            nn.Conv2d(branch_channels * 4, channels, 1, bias=False),
            nn.GroupNorm(_group_count(channels), channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.fuse(torch.cat([branch(x) for branch in self.branches], dim=1))


class MultiScaleDepthwiseUNet2D(nn.Module):
    """Efficient depthwise U-Net with dilated multi-scale context aggregation."""

    def __init__(self, in_channels: int = 3, out_channels: int = 2, base_channels: int = 16) -> None:
        super().__init__()
        c1 = base_channels
        c2 = base_channels * 2
        c3 = base_channels * 4
        self.enc0 = DepthwiseResidualBlock2D(in_channels, c1)
        self.down1 = nn.Sequential(
            nn.Conv2d(c1, c2, 3, stride=2, padding=1, bias=False),
            nn.GroupNorm(_group_count(c2), c2),
            nn.SiLU(inplace=True),
        )
        self.enc1 = DepthwiseResidualBlock2D(c2, c2)
        self.down2 = nn.Sequential(
            nn.Conv2d(c2, c3, 3, stride=2, padding=1, bias=False),
            nn.GroupNorm(_group_count(c3), c3),
            nn.SiLU(inplace=True),
        )
        self.bottleneck = nn.Sequential(DepthwiseResidualBlock2D(c3, c3), MultiScaleContext2D(c3))
        self.dec1 = DepthwiseResidualBlock2D(c3 + c2, c2)
        self.dec0 = DepthwiseResidualBlock2D(c2 + c1, c1)
        self.head = nn.Conv2d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x0 = self.enc0(x)
        x1 = self.enc1(self.down1(x0))
        x2 = self.bottleneck(self.down2(x1))
        y1 = F.interpolate(x2, size=x1.shape[2:], mode="bilinear", align_corners=False)
        y1 = self.dec1(torch.cat([y1, x1], dim=1))
        y0 = F.interpolate(y1, size=x0.shape[2:], mode="bilinear", align_corners=False)
        return self.head(self.dec0(torch.cat([y0, x0], dim=1)))


def build_candidate_keyframe_segmenter(config: dict[str, Any]) -> nn.Module:
    architecture = str(config.get("architecture") or "convnext_unet")
    kwargs = {
        "in_channels": int(config.get("in_channels", 3)),
        "out_channels": int(config.get("out_channels", 2)),
        "base_channels": int(config.get("base_channels", 8)),
    }
    if architecture == "residual_attention_unet":
        return ResidualAttentionUNet2D(**kwargs)
    if architecture == "plain_unet":
        return PlainUNet2D(**kwargs)
    if architecture == "nested_skip_unet":
        return NestedSkipUNet2D(**kwargs)
    if architecture == "multiscale_depthwise_unet":
        return MultiScaleDepthwiseUNet2D(**kwargs)
    raise ValueError(f"Unsupported candidate keyframe architecture: {architecture}")


def _group_count(channels: int) -> int:
    for groups in (8, 4, 2):
        if channels % groups == 0:
            return groups
    return 1
