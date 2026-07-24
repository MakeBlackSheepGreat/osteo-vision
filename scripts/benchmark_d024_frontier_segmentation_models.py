from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.nn.functional as F
from torch import nn

from scripts.benchmark_d024_segmentation_models import (
    DEFAULT_NNUNET_DATASET,
    LABELS,
    ModelCandidate,
    _fmt,
    _result_table_row,
)
from scripts.benchmark_d024_segmentation_models import model_catalog as baseline_model_catalog
from scripts.benchmark_d024_segmentation_models import (
    prepare_downsampled_cache,
    train_and_evaluate_model,
    write_results_csv,
)
from scripts.convert_d024_to_nnunet import DEFAULT_NNUNET_ROOT
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.reports.writers import write_json

DEFAULT_OUTPUT_ROOT = Path("artifacts/runs/d024_frontier_segmentation_model_benchmark")
DEFAULT_REPORT_DIR = Path("research/reports/modeling")


@dataclass(frozen=True)
class EvidenceSource:
    name: str
    paper_url: str
    code_url: str
    local_reproduction: str
    notes: str


def frontier_model_catalog() -> dict[str, ModelCandidate]:
    return {
        "mednext_tiny_proxy": ModelCandidate(
            "mednext_tiny_proxy",
            "MedNeXt Tiny Proxy",
            "convnext_3d",
            "Lightweight local reproduction of the MedNeXt fully ConvNeXt encoder-decoder idea.",
            "https://github.com/MIC-DKFZ/MedNeXt",
            lambda shape, n: ConvNeXtUNet3D(1, n, base_channels=8, kernel_size=3),
        ),
        "mednext_k5_proxy": ModelCandidate(
            "mednext_k5_proxy",
            "MedNeXt K5 Proxy",
            "convnext_3d_large_kernel",
            "Kernel-size ablation for ConvNeXt-style 3D depthwise blocks.",
            "https://arxiv.org/html/2303.09975v5",
            lambda shape, n: ConvNeXtUNet3D(1, n, base_channels=8, kernel_size=5),
        ),
        "uxnet_large_kernel_proxy": ModelCandidate(
            "uxnet_large_kernel_proxy",
            "3D UX-Net Large-Kernel Proxy",
            "large_kernel_convnet",
            "Large-kernel depthwise ConvNet route inspired by 3D UX-Net.",
            "https://github.com/MASILab/3DUX-Net",
            lambda shape, n: LargeKernelUNet3D(1, n, base_channels=8, kernel_size=7),
        ),
        "repuxnet_multibranch_proxy": ModelCandidate(
            "repuxnet_multibranch_proxy",
            "RepUX-Net Multi-Branch Proxy",
            "reparameterized_large_kernel",
            "Train-time multi-branch large-kernel proxy inspired by RepUX-Net re-parameterization.",
            "https://github.com/MASILab/RepUX-Net",
            lambda shape, n: RepLargeKernelUNet3D(1, n, base_channels=8),
        ),
        "unetrpp_epa_proxy": ModelCandidate(
            "unetrpp_epa_proxy",
            "UNETR++ EPA Proxy",
            "efficient_paired_attention",
            "Efficient paired attention bottleneck approximating UNETR++ spatial and channel attention.",
            "https://github.com/amshaker/unetr_plus_plus",
            lambda shape, n: AttentionBottleneckUNet3D(1, n, base_channels=8, attention="epa"),
        ),
        "transbts_bottleneck_proxy": ModelCandidate(
            "transbts_bottleneck_proxy",
            "TransBTS Bottleneck Proxy",
            "transformer_bottleneck",
            "CNN encoder-decoder with a transformer bottleneck, following the TransBTS design route.",
            "https://github.com/Wenxuan-1119/TransBTS",
            lambda shape, n: AttentionBottleneckUNet3D(1, n, base_channels=8, attention="transformer"),
        ),
        "nnformer_window_proxy": ModelCandidate(
            "nnformer_window_proxy",
            "nnFormer Window-Attention Proxy",
            "interleaved_transformer",
            "Interleaved convolution and local window attention proxy for nnFormer-style 3D transformers.",
            "https://github.com/282857341/nnFormer",
            lambda shape, n: WindowAttentionUNet3D(1, n, base_channels=8),
        ),
        "segformer3d_mlp_proxy": ModelCandidate(
            "segformer3d_mlp_proxy",
            "SegFormer3D MLP-Decoder Proxy",
            "hierarchical_transformer_mlp_decoder",
            "Hierarchical encoder with an all-MLP style decoder inspired by SegFormer3D.",
            "https://github.com/OSUPCVLab/SegFormer3D",
            lambda shape, n: SegFormer3DProxy(1, n, base_channels=8),
        ),
        "umamba_bottleneck_proxy": ModelCandidate(
            "umamba_bottleneck_proxy",
            "U-Mamba Bottleneck Proxy",
            "cnn_ssm_hybrid",
            "Hybrid CNN plus gated sequence-mixing bottleneck inspired by U-Mamba.",
            "https://github.com/bowang-lab/U-Mamba",
            lambda shape, n: MambaProxyUNet3D(1, n, base_channels=8, placement="bottleneck"),
        ),
        "segmamba_multiscale_proxy": ModelCandidate(
            "segmamba_multiscale_proxy",
            "SegMamba Multi-Scale Proxy",
            "multiscale_ssm",
            "Multi-scale gated sequence-mixing proxy for whole-volume dependency modeling.",
            "https://github.com/ge-xing/SegMamba",
            lambda shape, n: MambaProxyUNet3D(1, n, base_channels=8, placement="multiscale"),
        ),
    }


def frontier_evidence_sources() -> list[EvidenceSource]:
    return [
        EvidenceSource(
            "MedNeXt",
            "https://arxiv.org/html/2303.09975v5",
            "https://github.com/MIC-DKFZ/MedNeXt",
            "Proxy: ConvNeXt-style 3D encoder-decoder with 3x3x3 and 5x5x5 depthwise blocks.",
            "Official code is feasible later, but the current run avoids adding a separate dependency stack.",
        ),
        EvidenceSource(
            "3D UX-Net",
            "https://arxiv.org/abs/2209.15076",
            "https://github.com/MASILab/3DUX-Net",
            "Proxy: large-kernel depthwise 3D U-Net.",
            "Tests whether large receptive fields help jaw ROI segmentation at low resolution.",
        ),
        EvidenceSource(
            "RepUX-Net",
            "https://github.com/MASILab/RepUX-Net",
            "https://github.com/MASILab/RepUX-Net",
            "Proxy: multi-branch large-kernel block that mimics train-time re-parameterization.",
            "Full Bayesian frequency re-parameterization is left for a later official reproduction.",
        ),
        EvidenceSource(
            "UNETR++",
            "https://arxiv.org/html/2212.04497v3",
            "https://github.com/amshaker/unetr_plus_plus",
            "Proxy: efficient paired spatial/channel attention at the bottleneck.",
            "Used as an efficient transformer route for 8GB-GPU screening.",
        ),
        EvidenceSource(
            "TransBTS",
            "https://github.com/Wenxuan-1119/TransBTS",
            "https://github.com/Wenxuan-1119/TransBTS",
            "Proxy: transformer sequence modeling only at the deepest feature map.",
            "Full BraTS-oriented training code is not imported into the project tree.",
        ),
        EvidenceSource(
            "nnFormer",
            "https://arxiv.org/pdf/2109.03201",
            "https://github.com/282857341/nnFormer",
            "Proxy: convolution blocks interleaved with local window attention.",
            "Useful to compare local attention behavior against pure convolution.",
        ),
        EvidenceSource(
            "SegFormer3D",
            "https://github.com/OSUPCVLab/SegFormer3D",
            "https://github.com/OSUPCVLab/SegFormer3D",
            "Proxy: multiscale encoder features fused by simple 1x1 projections.",
            "The official model is a stronger candidate for a later controlled reproduction.",
        ),
        EvidenceSource(
            "U-Mamba",
            "https://arxiv.org/abs/2401.04722",
            "https://github.com/bowang-lab/U-Mamba",
            "Proxy: CNN encoder-decoder with a gated sequence-mixing bottleneck.",
            "Official reproduction needs mamba/causal-conv setup and will be tracked separately.",
        ),
        EvidenceSource(
            "SegMamba",
            "https://arxiv.org/abs/2401.13560",
            "https://github.com/ge-xing/SegMamba",
            "Proxy: multi-scale gated sequence-mixing blocks.",
            "Official code depends on Mamba kernels and is better isolated in a future environment.",
        ),
        EvidenceSource(
            "Swin-UMamba",
            "https://arxiv.org/html/2402.03302v1",
            "https://github.com/JiarunLiu/Swin-UMamba",
            "Reference only in this benchmark.",
            "Promising route, but official setup pins older torch and mamba-ssm versions.",
        ),
        EvidenceSource(
            "SAM-Med3D",
            "https://arxiv.org/html/2310.15161v3",
            "https://github.com/uni-medical/SAM-Med3D",
            "Reference only in this benchmark.",
            "Promptable foundation segmentation is relevant to annotation assistance, not this supervised jaw-roi benchmark.",
        ),
    ]


class ConvBlock3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, *, kernel_size: int = 3, groups: int = 1) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.block = nn.Sequential(
            nn.Conv3d(in_channels, out_channels, kernel_size, padding=padding, groups=groups, bias=False),
            nn.InstanceNorm3d(out_channels, affine=True),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class ConvNeXtBlock3D(nn.Module):
    def __init__(self, channels: int, *, kernel_size: int = 3, expansion: int = 2) -> None:
        super().__init__()
        padding = kernel_size // 2
        hidden = channels * expansion
        self.depthwise = nn.Conv3d(channels, channels, kernel_size, padding=padding, groups=channels)
        self.norm = nn.InstanceNorm3d(channels, affine=True)
        self.pointwise = nn.Sequential(
            nn.Conv3d(channels, hidden, 1),
            nn.GELU(),
            nn.Conv3d(hidden, channels, 1),
        )
        self.gamma = nn.Parameter(torch.full((1, channels, 1, 1, 1), 1e-3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.gamma * self.pointwise(self.norm(self.depthwise(x)))


class LargeKernelBlock3D(nn.Module):
    def __init__(self, channels: int, *, kernel_size: int = 7) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.block = nn.Sequential(
            nn.Conv3d(channels, channels, kernel_size, padding=padding, groups=channels, bias=False),
            nn.InstanceNorm3d(channels, affine=True),
            nn.GELU(),
            nn.Conv3d(channels, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class RepLargeKernelBlock3D(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.k3 = nn.Conv3d(channels, channels, 3, padding=1, groups=channels, bias=False)
        self.k5 = nn.Conv3d(channels, channels, 5, padding=2, groups=channels, bias=False)
        self.k7 = nn.Conv3d(channels, channels, 7, padding=3, groups=channels, bias=False)
        self.mix = nn.Sequential(
            nn.InstanceNorm3d(channels, affine=True),
            nn.GELU(),
            nn.Conv3d(channels, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.mix(self.k3(x) + self.k5(x) + self.k7(x))


class EfficientPairedAttention3D(nn.Module):
    def __init__(self, channels: int, *, reduction: int = 4) -> None:
        super().__init__()
        hidden = max(4, channels // reduction)
        self.channel_gate = nn.Sequential(
            nn.AdaptiveAvgPool3d(1),
            nn.Conv3d(channels, hidden, 1),
            nn.GELU(),
            nn.Conv3d(hidden, channels, 1),
            nn.Sigmoid(),
        )
        self.spatial_gate = nn.Sequential(
            nn.Conv3d(2, 1, 7, padding=3, bias=False),
            nn.Sigmoid(),
        )
        self.proj = nn.Conv3d(channels, channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = torch.mean(x, dim=1, keepdim=True)
        maxv = torch.amax(x, dim=1, keepdim=True)
        spatial = self.spatial_gate(torch.cat([avg, maxv], dim=1))
        channel = self.channel_gate(x)
        return x + self.proj(x * spatial * channel)


class TransformerBottleneck3D(nn.Module):
    def __init__(self, channels: int, *, num_heads: int = 4) -> None:
        super().__init__()
        heads = max(1, min(num_heads, channels // 8))
        while channels % heads != 0 and heads > 1:
            heads -= 1
        self.norm = nn.LayerNorm(channels)
        self.attn = nn.MultiheadAttention(channels, heads, batch_first=True)
        self.ffn = nn.Sequential(
            nn.LayerNorm(channels), nn.Linear(channels, channels * 2), nn.GELU(), nn.Linear(channels * 2, channels)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, d, h, w = x.shape
        tokens = x.flatten(2).transpose(1, 2)
        attended, _ = self.attn(self.norm(tokens), self.norm(tokens), self.norm(tokens), need_weights=False)
        tokens = tokens + attended
        tokens = tokens + self.ffn(tokens)
        return tokens.transpose(1, 2).reshape(b, c, d, h, w)


class WindowAttentionBlock3D(nn.Module):
    def __init__(self, channels: int, *, window_size: int = 4) -> None:
        super().__init__()
        self.window_size = window_size
        self.norm = nn.LayerNorm(channels)
        self.attn = nn.MultiheadAttention(channels, max(1, min(4, channels // 8)), batch_first=True)
        self.proj = nn.Linear(channels, channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, d, h, w = x.shape
        ws = self.window_size
        pad_d = (ws - d % ws) % ws
        pad_h = (ws - h % ws) % ws
        pad_w = (ws - w % ws) % ws
        padded = F.pad(x, (0, pad_w, 0, pad_h, 0, pad_d))
        _, _, dp, hp, wp = padded.shape
        windows = (
            padded.view(b, c, dp // ws, ws, hp // ws, ws, wp // ws, ws)
            .permute(0, 2, 4, 6, 3, 5, 7, 1)
            .reshape(-1, ws * ws * ws, c)
        )
        attended, _ = self.attn(self.norm(windows), self.norm(windows), self.norm(windows), need_weights=False)
        windows = windows + self.proj(attended)
        restored = (
            windows.reshape(b, dp // ws, hp // ws, wp // ws, ws, ws, ws, c)
            .permute(0, 7, 1, 4, 2, 5, 3, 6)
            .reshape(b, c, dp, hp, wp)
        )
        return x + restored[:, :, :d, :h, :w]


class GatedSequenceMixing3D(nn.Module):
    def __init__(self, channels: int, *, kernel_size: int = 17) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.norm = nn.LayerNorm(channels)
        self.in_proj = nn.Linear(channels, channels * 2)
        self.sequence_conv = nn.Conv1d(channels, channels, kernel_size, padding=padding, groups=channels)
        self.out_proj = nn.Linear(channels, channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, d, h, w = x.shape
        tokens = x.flatten(2).transpose(1, 2)
        value, gate = self.in_proj(self.norm(tokens)).chunk(2, dim=-1)
        mixed = self.sequence_conv(value.transpose(1, 2)).transpose(1, 2)
        tokens = tokens + self.out_proj(mixed * torch.sigmoid(gate))
        return tokens.transpose(1, 2).reshape(b, c, d, h, w)


class UpBlock3D(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int, block_factory: Any) -> None:
        super().__init__()
        self.up = nn.ConvTranspose3d(in_channels, out_channels, 2, stride=2)
        self.fuse = ConvBlock3D(out_channels + skip_channels, out_channels)
        self.block = block_factory(out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        if x.shape[2:] != skip.shape[2:]:
            x = F.interpolate(x, size=skip.shape[2:], mode="trilinear", align_corners=False)
        return self.block(self.fuse(torch.cat([x, skip], dim=1)))


class GenericUNet3D(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        *,
        base_channels: int,
        block_factory: Any,
        bottleneck: nn.Module | None = None,
        multiscale_blocks: bool = False,
    ) -> None:
        super().__init__()
        c1, c2, c3, c4 = base_channels, base_channels * 2, base_channels * 4, base_channels * 8
        self.stem = nn.Sequential(ConvBlock3D(in_channels, c1), block_factory(c1))
        self.down1 = nn.Sequential(
            nn.Conv3d(c1, c2, 3, stride=2, padding=1), nn.InstanceNorm3d(c2, affine=True), nn.GELU(), block_factory(c2)
        )
        self.down2 = nn.Sequential(
            nn.Conv3d(c2, c3, 3, stride=2, padding=1), nn.InstanceNorm3d(c3, affine=True), nn.GELU(), block_factory(c3)
        )
        self.down3 = nn.Sequential(
            nn.Conv3d(c3, c4, 3, stride=2, padding=1), nn.InstanceNorm3d(c4, affine=True), nn.GELU(), block_factory(c4)
        )
        self.ms1 = block_factory(c1) if multiscale_blocks else nn.Identity()
        self.ms2 = block_factory(c2) if multiscale_blocks else nn.Identity()
        self.ms3 = block_factory(c3) if multiscale_blocks else nn.Identity()
        self.bottleneck = bottleneck if bottleneck is not None else block_factory(c4)
        self.up2 = UpBlock3D(c4, c3, c3, block_factory)
        self.up1 = UpBlock3D(c3, c2, c2, block_factory)
        self.up0 = UpBlock3D(c2, c1, c1, block_factory)
        self.head = nn.Conv3d(c1, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.ms1(self.stem(x))
        x2 = self.ms2(self.down1(x1))
        x3 = self.ms3(self.down2(x2))
        x4 = self.bottleneck(self.down3(x3))
        y = self.up2(x4, x3)
        y = self.up1(y, x2)
        y = self.up0(y, x1)
        return self.head(y)


class ConvNeXtUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int, kernel_size: int) -> None:
        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=lambda channels: ConvNeXtBlock3D(channels, kernel_size=kernel_size),
        )


class LargeKernelUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int, kernel_size: int) -> None:
        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=lambda channels: LargeKernelBlock3D(channels, kernel_size=kernel_size),
        )


class RepLargeKernelUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int) -> None:
        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=lambda channels: RepLargeKernelBlock3D(channels),
        )


class AttentionBottleneckUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int, attention: str) -> None:
        bottleneck_channels = base_channels * 8
        bottleneck = (
            EfficientPairedAttention3D(bottleneck_channels)
            if attention == "epa"
            else TransformerBottleneck3D(bottleneck_channels)
        )
        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=lambda channels: ConvNeXtBlock3D(channels, kernel_size=3),
            bottleneck=bottleneck,
        )


class WindowAttentionUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int) -> None:
        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=lambda channels: nn.Sequential(ConvNeXtBlock3D(channels), WindowAttentionBlock3D(channels)),
        )


class MambaProxyUNet3D(GenericUNet3D):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int, placement: str) -> None:
        bottleneck_channels = base_channels * 8

        def block_factory(channels: int) -> nn.Module:
            return nn.Sequential(ConvNeXtBlock3D(channels), GatedSequenceMixing3D(channels))

        super().__init__(
            in_channels,
            out_channels,
            base_channels=base_channels,
            block_factory=(block_factory if placement == "multiscale" else lambda channels: ConvNeXtBlock3D(channels)),
            bottleneck=GatedSequenceMixing3D(bottleneck_channels),
            multiscale_blocks=placement == "multiscale",
        )


class SegFormer3DProxy(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, *, base_channels: int) -> None:
        super().__init__()
        c1, c2, c3, c4 = base_channels, base_channels * 2, base_channels * 4, base_channels * 8
        self.enc1 = nn.Sequential(ConvBlock3D(in_channels, c1), ConvNeXtBlock3D(c1))
        self.enc2 = nn.Sequential(nn.Conv3d(c1, c2, 3, stride=2, padding=1), nn.GELU(), ConvNeXtBlock3D(c2))
        self.enc3 = nn.Sequential(nn.Conv3d(c2, c3, 3, stride=2, padding=1), nn.GELU(), WindowAttentionBlock3D(c3))
        self.enc4 = nn.Sequential(nn.Conv3d(c3, c4, 3, stride=2, padding=1), nn.GELU(), TransformerBottleneck3D(c4))
        self.proj1 = nn.Conv3d(c1, c1, 1)
        self.proj2 = nn.Conv3d(c2, c1, 1)
        self.proj3 = nn.Conv3d(c3, c1, 1)
        self.proj4 = nn.Conv3d(c4, c1, 1)
        self.fuse = nn.Sequential(ConvBlock3D(c1 * 4, c1), ConvNeXtBlock3D(c1), nn.Conv3d(c1, out_channels, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.enc1(x)
        x2 = self.enc2(x1)
        x3 = self.enc3(x2)
        x4 = self.enc4(x3)
        size = x1.shape[2:]
        features = [
            self.proj1(x1),
            F.interpolate(self.proj2(x2), size=size, mode="trilinear", align_corners=False),
            F.interpolate(self.proj3(x3), size=size, mode="trilinear", align_corners=False),
            F.interpolate(self.proj4(x4), size=size, mode="trilinear", align_corners=False),
        ]
        return self.fuse(torch.cat(features, dim=1))


def model_sources(catalog: dict[str, ModelCandidate]) -> list[dict[str, str]]:
    _ = catalog
    return [
        {
            "name": source.name,
            "paper_url": source.paper_url,
            "code_url": source.code_url,
            "local_reproduction": source.local_reproduction,
            "notes": source.notes,
        }
        for source in frontier_evidence_sources()
    ]


def write_summary_reports(payload: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh_path = report_dir / "d024_frontier_10_model_benchmark_zh.md"
    en_path = report_dir / "d024_frontier_10_model_benchmark_en.md"
    payload.setdefault("paths", {})
    payload["paths"]["zh_report"] = str(zh_path)
    payload["paths"]["en_report"] = str(en_path)
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    rows = sorted(
        payload["results"],
        key=lambda item: (
            -1 if item.get("foreground_mean_dice") is None else -float(item["foreground_mean_dice"]),
            item["model_id"],
        ),
    )
    label_names = ", ".join(f"{key}:{value}" for key, value in LABELS.items())
    if language == "zh":
        lines = [
            "# D024 DentVoxel 第二轮前沿分割模型测试报告（中文）",
            "",
            "## 定位",
            "",
            "本报告回答“再找十个新分割模型试试看”的问题。测试对象仍为 D024 DentVoxel jaw-roi，属于低分辨率、短训练预算下的结构路线筛选。这里的多数实现是论文关键模块的本地轻量复现或 proxy，用于快速判断是否值得后续拉官方仓库做完整复现。",
            "",
            "## 与论文复现的关系",
            "",
            "- 官方级复现：需要独立安装论文仓库、按原始训练协议和数据设置跑完整实验。本轮只完成资料定位和依赖判断。",
            "- 本地轻量复现：在当前 PyTorch/MONAI 环境内实现论文的关键结构思想，并用同一 D024 训练脚本测试可跑性和初始收敛。",
            "- 结果解释：本轮结果不能与论文指标直接对比，也不能作为颌骨骨髓炎临床诊断性能依据。",
            "",
            "## 数据与设置",
            "",
            f"- 数据集：D024 DentVoxel jaw-roi，{payload['data']['case_count']} 例。",
            f"- 标签：{label_names}。",
            f"- 划分：fold {payload['data']['fold']}，训练 {payload['data']['train_count']} 例，验证 {payload['data']['val_count']} 例。",
            f"- 输入尺寸：{payload['data']['target_shape']}，由原始 0.3 mm CBCT 下采样得到。",
            f"- 每模型训练批次数：{payload['config']['max_train_batches']}；验证病例数：{payload['config']['max_val_cases']}。",
            f"- 设备：{payload['environment']['device']}；GPU：{payload['environment'].get('cuda_device_name')}；PyTorch：{payload['environment']['torch_version']}。",
            "",
            "## 第二轮十模型结果",
            "",
            "| Rank | Model | Status | Mean Dice | Mean IoU | Params | Train Loss | Time(s) | Peak GPU MB |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, row in enumerate(rows, start=1):
            lines.append(_result_table_row(rank, row))
        lines.extend(
            [
                "",
                "## 初步判断",
                "",
                _best_model_sentence(rows, language="zh"),
                "- ConvNeXt/大核卷积类模型更适合先做工程化推进，因为依赖轻、显存可控，后续能自然接到 D024 和术中 ROI 任务。",
                "- Mamba 类模型值得保留为长程依赖实验，但官方 mamba/causal-conv 依赖在 Windows 和当前 torch 版本上需要单独环境验证。",
                "- Transformer 和 promptable foundation model 更适合后续做标注辅助、交互式边界修正或多模型融合，不建议抢在第一基线之前作为主线。",
                "",
                "## 前沿模型来源与本地复现状态",
                "",
                "| Model | Paper | Code | Local reproduction | Notes |",
                "|---|---|---|---|---|",
            ]
        )
        for item in payload["model_sources"]:
            lines.append(
                f"| {item['name']} | {item['paper_url']} | {item['code_url']} | {item['local_reproduction']} | {item['notes']} |"
            )
        lines.extend(
            [
                "",
                "## 下一步建议",
                "",
                "1. 把本轮 top-3 与第一轮 SegResNetDS、BasicUNet++ 放入同一训练预算做复测。",
                "2. 对 top-3 增加 Dice+CE、Dice+Focal 和类权重 CE 的消融，重点观察下颌管标签。",
                "3. 单独建立 Linux/CUDA 兼容环境复现 U-Mamba、SegMamba 和 MedNeXt 官方代码。",
                "4. 正式报告阶段回到 5-fold、HD95、NSD、clDice 和每类 Dice，不使用本轮低分辨率结果做临床表述。",
                "",
                "## 产物",
                "",
                f"- 结果 JSON：`{payload['paths']['summary_json']}`",
                f"- 结果 CSV：`{payload['paths']['results_csv']}`",
                f"- 中文报告：`{payload['paths']['zh_report']}`",
                f"- 英文报告：`{payload['paths']['en_report']}`",
                "",
                "## 医学边界",
                "",
                "D024 是 CBCT 解剖结构分割数据，不包含颌骨骨髓炎、坏死骨或 ICG 荧光标签。本报告只用于模型选型和工程可行性判断。",
            ]
        )
        return "\n".join(lines) + "\n"
    lines = [
        "# D024 DentVoxel Second-Round Frontier Segmentation Benchmark",
        "",
        "## Scope",
        "",
        "This report addresses the request to screen ten additional segmentation models. The benchmark still uses D024 DentVoxel jaw-roi under a low-resolution, short-budget setup. Most implementations are local lightweight reproductions or proxies of key paper ideas, intended to decide which official repositories deserve full reproduction next.",
        "",
        "## Reproduction Level",
        "",
        "- Official reproduction requires installing the paper repository and running its original protocol. This round records source discovery and dependency status only.",
        "- Local lightweight reproduction implements the key architectural idea inside the current PyTorch/MONAI environment and runs it under the same D024 protocol.",
        "- The results cannot be compared directly with paper scores and must not be used as clinical diagnostic performance.",
        "",
        "## Data and Setup",
        "",
        f"- Dataset: D024 DentVoxel jaw-roi, {payload['data']['case_count']} cases.",
        f"- Labels: {label_names}.",
        f"- Split: fold {payload['data']['fold']}, {payload['data']['train_count']} training cases and {payload['data']['val_count']} validation cases.",
        f"- Input size: {payload['data']['target_shape']}, downsampled from 0.3 mm CBCT volumes.",
        f"- Training batches per model: {payload['config']['max_train_batches']}; validation cases: {payload['config']['max_val_cases']}.",
        f"- Device: {payload['environment']['device']}; GPU: {payload['environment'].get('cuda_device_name')}; PyTorch: {payload['environment']['torch_version']}.",
        "",
        "## Results",
        "",
        "| Rank | Model | Status | Mean Dice | Mean IoU | Params | Train Loss | Time(s) | Peak GPU MB |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(rows, start=1):
        lines.append(_result_table_row(rank, row))
    lines.extend(
        [
            "",
            "## Initial Interpretation",
            "",
            _best_model_sentence(rows, language="en"),
            "- ConvNeXt and large-kernel ConvNet routes are the most practical near-term engineering candidates because they keep dependencies and memory under control.",
            "- Mamba-style models should remain long-range dependency experiments, but official mamba/causal-conv dependencies need a separate compatibility check.",
            "- Transformer and promptable foundation models are better suited for annotation assistance, interactive boundary correction, or later ensemble work than for the first production baseline.",
            "",
            "## Frontier Sources and Local Reproduction Status",
            "",
            "| Model | Paper | Code | Local reproduction | Notes |",
            "|---|---|---|---|---|",
        ]
    )
    for item in payload["model_sources"]:
        lines.append(
            f"| {item['name']} | {item['paper_url']} | {item['code_url']} | {item['local_reproduction']} | {item['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Next Steps",
            "",
            "1. Re-run the top three models together with first-round SegResNetDS and BasicUNet++ under the same training budget.",
            "2. Add Dice+CE, Dice+Focal, and class-weighted CE ablations, with special attention to mandibular canal labels.",
            "3. Create a separate Linux/CUDA-compatible environment for official MedNeXt, U-Mamba, and SegMamba reproduction.",
            "4. Return to 5-fold validation, HD95, NSD, clDice, and per-class Dice for formal reporting.",
            "",
            "## Artifacts",
            "",
            f"- Result JSON: `{payload['paths']['summary_json']}`",
            f"- Result CSV: `{payload['paths']['results_csv']}`",
            f"- Chinese report: `{payload['paths']['zh_report']}`",
            f"- English report: `{payload['paths']['en_report']}`",
            "",
            "## Medical Boundary",
            "",
            "D024 is an anatomical CBCT segmentation dataset. It does not include jaw osteomyelitis, necrotic bone, or ICG fluorescence labels. This report is only model-selection and engineering-feasibility evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _best_model_sentence(rows: list[dict[str, Any]], *, language: str) -> str:
    completed = [row for row in rows if row.get("foreground_mean_dice") is not None]
    if not completed:
        return (
            "- 本轮没有模型产生可用 Dice，需要先检查训练失败原因。"
            if language == "zh"
            else "- No model produced an available Dice score; inspect training failures first."
        )
    best = completed[0]
    dice = _fmt(best.get("foreground_mean_dice"))
    if language == "zh":
        return f"- 本轮最佳初始结果为 {best['display_name']}，mean Dice {dice}。该结果只代表短训练预算下的早期信号。"
    return f"- The best early result is {best['display_name']} with mean Dice {dice}. This is an early signal under a short training budget only."


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    target_shape = tuple(int(item) for item in args.target_shape)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = ensure_dir(Path(args.output_dir) / run_id)
    cache_dir = ensure_dir(Path(args.cache_dir))
    rows, data_info = prepare_downsampled_cache(
        Path(args.dataset_dir),
        cache_dir,
        target_shape=target_shape,
        fold=args.fold,
        force=args.force_cache,
    )
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    catalog = frontier_model_catalog()
    selected_ids = args.models.split(",") if args.models else list(catalog)
    selected = [catalog[model_id] for model_id in selected_ids]
    device = torch.device(args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu"))
    results = [
        train_and_evaluate_model(
            candidate,
            train_rows,
            val_rows,
            target_shape=target_shape,
            device=device,
            max_train_batches=args.max_train_batches,
            max_val_cases=args.max_val_cases,
            learning_rate=args.learning_rate,
            seed=args.seed,
        )
        for candidate in selected
    ]
    summary_json = output_dir / "d024_frontier_10_model_benchmark_summary.json"
    results_csv = output_dir / "d024_frontier_10_model_benchmark_results.csv"
    write_results_csv(results_csv, results)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "data": data_info,
        "config": {
            "target_shape": list(target_shape),
            "max_train_batches": args.max_train_batches,
            "max_val_cases": args.max_val_cases,
            "learning_rate": args.learning_rate,
            "seed": args.seed,
            "models": selected_ids,
            "benchmark_scope": "frontier_10_local_lightweight_reproduction",
            "baseline_catalog_overlap": sorted(set(selected_ids) & set(baseline_model_catalog())),
        },
        "environment": {
            "device": str(device),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "results": results,
        "model_sources": model_sources(catalog),
        "paths": {
            "output_dir": str(output_dir),
            "summary_json": str(summary_json),
            "results_csv": str(results_csv),
        },
    }
    report_paths = write_summary_reports(payload, Path(args.report_dir))
    payload["paths"].update(report_paths)
    write_json(summary_json, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark 10 frontier 3D segmentation model candidates on D024 jaw-roi."
    )
    parser.add_argument("--dataset-dir", default=str(DEFAULT_NNUNET_DATASET))
    parser.add_argument("--cache-dir", default=str(DEFAULT_NNUNET_ROOT / "monai_cache" / "jaw_roi_64"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--target-shape", nargs=3, type=int, default=[64, 64, 64])
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--max-train-batches", type=int, default=8)
    parser.add_argument("--max-val-cases", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=20260616)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument(
        "--models", default="", help="Comma-separated model IDs. Empty runs all 10 frontier candidates."
    )
    parser.add_argument("--force-cache", action="store_true")
    return parser.parse_args()


def main() -> int:
    payload = run_benchmark(parse_args())
    print(json.dumps({"run_id": payload["run_id"], "paths": payload["paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
