from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np
import torch
from monai.networks import nets
from scipy import ndimage as ndi
from torch import nn
from torch.utils.data import DataLoader, Dataset

from scripts.convert_d024_to_nnunet import DEFAULT_NNUNET_ROOT, convert_d024_to_nnunet
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.reports.writers import write_csv, write_json

DEFAULT_NNUNET_DATASET = DEFAULT_NNUNET_ROOT / "nnUNet_raw" / "Dataset124_DentVoxelJawROI"
DEFAULT_OUTPUT_ROOT = Path("artifacts/runs/d024_segmentation_model_benchmark")
DEFAULT_REPORT_DIR = Path("research/reports/modeling")
LABELS = {
    1: "maxilla",
    2: "mandible",
    3: "r_mandibular_canal",
    4: "l_mandibular_canal",
    5: "r_maxillary_sinus",
    6: "l_maxillary_sinus",
}


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    display_name: str
    family: str
    rationale: str
    source_url: str
    constructor: Callable[[tuple[int, int, int], int], nn.Module]


def model_catalog() -> dict[str, ModelCandidate]:
    return {
        "monai_unet": ModelCandidate(
            "monai_unet",
            "MONAI 3D U-Net",
            "cnn_unet",
            "Classic encoder-decoder baseline for volumetric medical segmentation.",
            "https://docs.monai.io/en/stable/networks.html#unet",
            lambda shape, n: nets.UNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                channels=(16, 32, 64, 128, 256),
                strides=(2, 2, 2, 2),
                num_res_units=1,
            ),
        ),
        "monai_basic_unet": ModelCandidate(
            "monai_basic_unet",
            "MONAI BasicUNet",
            "cnn_unet",
            "Compact 3D U-Net implementation with modest parameter count.",
            "https://docs.monai.io/en/stable/networks.html#basicunet",
            lambda shape, n: nets.BasicUNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                features=(16, 16, 32, 64, 128, 16),
            ),
        ),
        "monai_unetplusplus": ModelCandidate(
            "monai_unetplusplus",
            "MONAI BasicUNet++",
            "nested_unet",
            "UNet++-style nested skip connections for multiscale feature reuse.",
            "https://docs.monai.io/en/stable/networks.html#basicunetplusplus",
            lambda shape, n: nets.BasicUNetPlusPlus(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                features=(16, 16, 32, 64, 128, 16),
                deep_supervision=False,
            ),
        ),
        "monai_attention_unet": ModelCandidate(
            "monai_attention_unet",
            "MONAI Attention U-Net",
            "attention_unet",
            "Attention gates are relevant for suppressing irrelevant anatomy around jaw ROIs.",
            "https://docs.monai.io/en/stable/networks.html#attentionunet",
            lambda shape, n: nets.AttentionUnet(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                channels=(16, 32, 64, 128, 256),
                strides=(2, 2, 2, 2),
            ),
        ),
        "monai_dynunet": ModelCandidate(
            "monai_dynunet",
            "MONAI DynUNet ResBlock",
            "dynamic_unet",
            "nnU-Net-inspired configurable U-Net suitable for dataset-specific planning.",
            "https://docs.monai.io/en/stable/networks.html#dynunet",
            lambda shape, n: nets.DynUNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                kernel_size=[3, 3, 3, 3, 3],
                strides=[1, 2, 2, 2, 2],
                upsample_kernel_size=[2, 2, 2, 2],
                filters=(16, 32, 64, 128, 256),
                res_block=True,
            ),
        ),
        "monai_segresnet": ModelCandidate(
            "monai_segresnet",
            "MONAI SegResNet",
            "residual_cnn",
            "Residual 3D CNN baseline with favorable memory footprint.",
            "https://docs.monai.io/en/stable/networks.html#segresnet",
            lambda shape, n: nets.SegResNet(
                spatial_dims=3,
                init_filters=8,
                in_channels=1,
                out_channels=n,
                blocks_down=(1, 1, 2, 2),
                blocks_up=(1, 1, 1),
            ),
        ),
        "monai_segresnetds": ModelCandidate(
            "monai_segresnetds",
            "MONAI SegResNetDS",
            "residual_cnn_deep_supervision",
            "Residual encoder-decoder with deep-supervision support.",
            "https://docs.monai.io/en/stable/networks.html#segresnetds",
            lambda shape, n: nets.SegResNetDS(
                spatial_dims=3,
                init_filters=16,
                in_channels=1,
                out_channels=n,
                blocks_down=(1, 1, 2, 2),
                dsdepth=1,
            ),
        ),
        "monai_highresnet": ModelCandidate(
            "monai_highresnet",
            "MONAI HighResNet",
            "high_residual_cnn",
            "High-resolution residual CNN with a conservative memory profile.",
            "https://docs.monai.io/en/stable/networks.html#highresnet",
            lambda shape, n: nets.HighResNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=n,
                dropout_prob=0.0,
            ),
        ),
        "monai_unetr_tiny": ModelCandidate(
            "monai_unetr_tiny",
            "MONAI UNETR Tiny",
            "transformer_unet",
            "Transformer encoder baseline for global 3D context, reduced for 8 GB GPU testing.",
            "https://docs.monai.io/en/stable/networks.html#unetr",
            lambda shape, n: nets.UNETR(
                in_channels=1,
                out_channels=n,
                img_size=shape,
                feature_size=16,
                hidden_size=192,
                mlp_dim=768,
                num_heads=3,
                proj_type="conv",
                norm_name="instance",
                conv_block=True,
                res_block=True,
                dropout_rate=0.0,
                spatial_dims=3,
            ),
        ),
        "monai_swinunetr_tiny": ModelCandidate(
            "monai_swinunetr_tiny",
            "MONAI SwinUNETR Tiny",
            "swin_transformer_unet",
            "Shifted-window transformer baseline for hierarchical 3D context.",
            "https://docs.monai.io/en/stable/networks.html#swinunetr",
            lambda shape, n: nets.SwinUNETR(
                in_channels=1,
                out_channels=n,
                patch_size=2,
                depths=(1, 1, 1, 1),
                num_heads=(3, 6, 12, 24),
                window_size=4,
                qkv_bias=True,
                mlp_ratio=4.0,
                feature_size=24,
                norm_name="instance",
                drop_rate=0.0,
                attn_drop_rate=0.0,
                dropout_path_rate=0.0,
                normalize=True,
                patch_norm=False,
                use_checkpoint=False,
                spatial_dims=3,
                downsample="merging",
                use_v2=False,
            ),
        ),
    }


class CachedNiftiDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        item = self.rows[index]
        with np.load(item["cache_path"]) as payload:
            image = payload["image"].astype(np.float32, copy=False)
            label = payload["label"].astype(np.int64, copy=False)
        return torch.from_numpy(image[None]), torch.from_numpy(label)


def prepare_downsampled_cache(
    dataset_dir: Path,
    cache_dir: Path,
    *,
    target_shape: tuple[int, int, int],
    fold: int,
    force: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not dataset_dir.exists():
        convert_d024_to_nnunet(task="jaw-roi")
    images_dir = dataset_dir / "imagesTr"
    labels_dir = dataset_dir / "labelsTr"
    splits_path = dataset_dir / "splits_final.json"
    if not images_dir.exists() or not labels_dir.exists():
        raise FileNotFoundError(f"Missing nnU-Net raw directories under {dataset_dir}")
    if not splits_path.exists():
        raise FileNotFoundError(f"Missing split file: {splits_path}")
    splits = json.loads(splits_path.read_text(encoding="utf-8"))
    split = splits[fold]
    split_lookup = {case_id: "train" for case_id in split["train"]} | {case_id: "val" for case_id in split["val"]}
    ensure_dir(cache_dir)
    rows: list[dict[str, Any]] = []
    for image_path in sorted(images_dir.glob("*_0000.nii.gz")):
        case_id = image_path.name.replace("_0000.nii.gz", "")
        label_path = labels_dir / f"{case_id}.nii.gz"
        if not label_path.exists():
            continue
        cache_path = cache_dir / f"{case_id}_{'x'.join(map(str, target_shape))}.npz"
        if force or not cache_path.exists():
            _write_case_cache(image_path, label_path, cache_path, target_shape)
        rows.append(
            {
                "case_id": case_id,
                "image_path": str(image_path),
                "label_path": str(label_path),
                "cache_path": str(cache_path),
                "split": split_lookup.get(case_id, "unused"),
            }
        )
    info = {
        "dataset_dir": str(dataset_dir),
        "cache_dir": str(cache_dir),
        "target_shape": list(target_shape),
        "fold": fold,
        "case_count": len(rows),
        "train_count": sum(1 for row in rows if row["split"] == "train"),
        "val_count": sum(1 for row in rows if row["split"] == "val"),
    }
    return rows, info


def _write_case_cache(image_path: Path, label_path: Path, cache_path: Path, target_shape: tuple[int, int, int]) -> None:
    image = np.asanyarray(nib.load(str(image_path)).dataobj).astype(np.float32)
    label = np.asanyarray(nib.load(str(label_path)).dataobj).astype(np.int16)
    image_small = _resize_volume(image, target_shape, order=1)
    label_small = _resize_volume(label, target_shape, order=0).astype(np.int16)
    image_small = _normalize_image(image_small).astype(np.float16)
    np.savez_compressed(cache_path, image=image_small, label=label_small)


def _resize_volume(volume: np.ndarray, target_shape: tuple[int, int, int], *, order: int) -> np.ndarray:
    zoom = [target / source for target, source in zip(target_shape, volume.shape)]
    return ndi.zoom(volume, zoom, order=order)


def _normalize_image(image: np.ndarray) -> np.ndarray:
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros_like(image, dtype=np.float32)
    low = float(np.percentile(finite, 0.5))
    high = float(np.percentile(finite, 99.5))
    if high <= low:
        low = float(np.min(finite))
        high = float(np.max(finite))
    if high <= low:
        return np.zeros_like(image, dtype=np.float32)
    clipped = np.clip(image, low, high)
    return ((clipped - low) / (high - low) * 2.0 - 1.0).astype(np.float32)


def train_and_evaluate_model(
    candidate: ModelCandidate,
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    target_shape: tuple[int, int, int],
    device: torch.device,
    max_train_batches: int,
    max_val_cases: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    _set_seed(seed)
    torch.cuda.empty_cache() if device.type == "cuda" else None
    started = time.perf_counter()
    status = "completed"
    error = ""
    train_loss = math.nan
    peak_memory_mb: float | None = None
    parameter_count = 0
    model: nn.Module | None = None
    try:
        print(f"[start] {candidate.model_id}", flush=True)
        model = candidate.constructor(target_shape, 7).to(device)
        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        loss_fn = nn.CrossEntropyLoss()
        loader = DataLoader(CachedNiftiDataset(train_rows), batch_size=1, shuffle=True, num_workers=0)
        losses: list[float] = []
        model.train()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        for batch_index, (image, label) in enumerate(loader):
            if batch_index >= max_train_batches:
                break
            image = image.to(device, non_blocking=True)
            label = label.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = _primary_output(model(image))
            loss = loss_fn(logits, label)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        train_loss = float(np.mean(losses)) if losses else math.nan
        metrics = evaluate_model(model, val_rows[:max_val_cases], device=device)
        if device.type == "cuda":
            peak_memory_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
        print(f"[done] {candidate.model_id}", flush=True)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            status = "failed_oom"
            error = str(exc)
            metrics = empty_metrics()
            torch.cuda.empty_cache() if device.type == "cuda" else None
        else:
            status = "failed_runtime"
            error = str(exc)
            metrics = empty_metrics()
    except Exception as exc:  # noqa: BLE001
        status = "failed_runtime"
        error = f"{type(exc).__name__}: {exc}"
        metrics = empty_metrics()
    elapsed = time.perf_counter() - started
    if model is not None:
        del model
    torch.cuda.empty_cache() if device.type == "cuda" else None
    return {
        "model_id": candidate.model_id,
        "display_name": candidate.display_name,
        "family": candidate.family,
        "status": status,
        "error": error,
        "parameter_count": parameter_count,
        "train_batches": min(max_train_batches, len(train_rows)),
        "val_cases": int(metrics.get("case_count", 0)),
        "train_loss": train_loss,
        "foreground_mean_dice": metrics.get("foreground_mean_dice"),
        "foreground_mean_iou": metrics.get("foreground_mean_iou"),
        "per_label": metrics.get("per_label", {}),
        "elapsed_seconds": elapsed,
        "peak_memory_mb": peak_memory_mb,
        "rationale": candidate.rationale,
        "source_url": candidate.source_url,
    }


def evaluate_model(model: nn.Module, rows: list[dict[str, Any]], *, device: torch.device) -> dict[str, Any]:
    model.eval()
    per_label_scores: dict[int, list[dict[str, float]]] = {label: [] for label in LABELS}
    with torch.no_grad():
        for row in rows:
            with np.load(row["cache_path"]) as payload:
                image = torch.from_numpy(payload["image"].astype(np.float32, copy=False)[None, None]).to(device)
                target = payload["label"].astype(np.int16, copy=False)
            logits = _primary_output(model(image))
            prediction = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy().astype(np.int16)
            for label in LABELS:
                score = _label_dice_iou(prediction == label, target == label)
                per_label_scores[label].append(score)
    per_label = {
        str(label): {
            "name": LABELS[label],
            "dice": _nanmean([score["dice"] for score in scores]),
            "iou": _nanmean([score["iou"] for score in scores]),
            "present_target_cases": int(sum(1 for score in scores if score["target_present"])),
            "present_prediction_cases": int(sum(1 for score in scores if score["prediction_present"])),
        }
        for label, scores in per_label_scores.items()
    }
    foreground_dice = _nanmean([item["dice"] for item in per_label.values()])
    foreground_iou = _nanmean([item["iou"] for item in per_label.values()])
    return {
        "case_count": len(rows),
        "foreground_mean_dice": foreground_dice,
        "foreground_mean_iou": foreground_iou,
        "per_label": per_label,
    }


def empty_metrics() -> dict[str, Any]:
    return {"case_count": 0, "foreground_mean_dice": None, "foreground_mean_iou": None, "per_label": {}}


def _primary_output(output: Any) -> torch.Tensor:
    if isinstance(output, (tuple, list)):
        return output[0]
    return output


def _label_dice_iou(pred: np.ndarray, target: np.ndarray) -> dict[str, float]:
    pred_bool = np.asarray(pred).astype(bool)
    target_bool = np.asarray(target).astype(bool)
    pred_area = float(pred_bool.sum())
    target_area = float(target_bool.sum())
    intersection = float(np.logical_and(pred_bool, target_bool).sum())
    union = float(np.logical_or(pred_bool, target_bool).sum())
    if pred_area == 0 and target_area == 0:
        dice = 1.0
    elif pred_area + target_area == 0:
        dice = 0.0
    else:
        dice = 2.0 * intersection / (pred_area + target_area)
    iou = 1.0 if union == 0 else intersection / union
    return {
        "dice": float(dice),
        "iou": float(iou),
        "target_present": bool(target_area > 0),
        "prediction_present": bool(pred_area > 0),
    }


def _nanmean(values: Iterable[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not numbers:
        return None
    return float(np.mean(numbers))


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def write_summary_reports(payload: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh_path = report_dir / "d024_10_model_baseline_benchmark_zh.md"
    en_path = report_dir / "d024_10_model_baseline_benchmark_en.md"
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
    if language == "zh":
        lines = [
            "# D024 DentVoxel 十模型基础分割测试报告（中文）",
            "",
            "## 定位",
            "",
            "本报告用于早期筛选 3D 医学分割基础模型。测试对象是 D024 DentVoxel jaw-roi 任务，输出仅代表低分辨率、短训练预算下的工程可跑性和初始收敛信号，不能视为正式模型性能。",
            "",
            "## 数据与设置",
            "",
            f"- 数据集：D024 DentVoxel jaw-roi，{payload['data']['case_count']} 例。",
            f"- 划分：fold {payload['data']['fold']}，训练 {payload['data']['train_count']} 例，验证 {payload['data']['val_count']} 例。",
            f"- 测试输入尺寸：{payload['data']['target_shape']}，由原始 0.3 mm CBCT 下采样得到。",
            f"- 每模型训练批次数：{payload['config']['max_train_batches']}；验证病例数：{payload['config']['max_val_cases']}。",
            f"- 设备：{payload['environment']['device']}；PyTorch：{payload['environment']['torch_version']}。",
            "",
            "## 结果汇总",
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
                "- nnU-Net 仍应保留为正式基线；本报告中的 MONAI 模型用于快速筛选结构路线和显存/速度特征。",
                "- 低分辨率短训练下的 Dice 值主要反映模型是否能开始学习大结构，不足以判断下颌管等细小结构的最终潜力。",
                "- 后续正式实验应回到 nnU-Net/MedNeXt/U-Mamba 的高分辨率训练、5-fold 验证和 HD95/NSD/clDice 指标。",
                "",
                "## 候选模型依据",
                "",
            ]
        )
        for item in payload["model_sources"]:
            lines.append(f"- {item['name']}：{item['reason']}。来源：{item['url']}")
        lines.extend(
            [
                "",
                "## 产物",
                "",
                f"- 结果 JSON：`{payload['paths']['summary_json']}`",
                f"- 结果 CSV：`{payload['paths']['results_csv']}`",
                f"- 本报告：`{payload['paths']['zh_report']}`",
                f"- 英文报告：`{payload['paths']['en_report']}`",
                "",
                "## 医学边界",
                "",
                "D024 是 CBCT 解剖结构分割数据，不包含颌骨骨髓炎、坏死骨或 ICG 荧光标签。结果只能作为术前解剖 ROI 和后续模型选型依据，不能作为临床诊断结论。",
            ]
        )
        return "\n".join(lines) + "\n"
    lines = [
        "# D024 DentVoxel 10-Model Baseline Segmentation Benchmark",
        "",
        "## Scope",
        "",
        "This report screens 3D medical segmentation backbones on the D024 DentVoxel jaw-roi task. The results reflect low-resolution, short-budget engineering feasibility and early convergence only; they are not final model performance.",
        "",
        "## Data and Setup",
        "",
        f"- Dataset: D024 DentVoxel jaw-roi, {payload['data']['case_count']} cases.",
        f"- Split: fold {payload['data']['fold']}, {payload['data']['train_count']} training cases and {payload['data']['val_count']} validation cases.",
        f"- Test input size: {payload['data']['target_shape']}, downsampled from 0.3 mm CBCT volumes.",
        f"- Training batches per model: {payload['config']['max_train_batches']}; validation cases: {payload['config']['max_val_cases']}.",
        f"- Device: {payload['environment']['device']}; PyTorch: {payload['environment']['torch_version']}.",
        "",
        "## Summary Results",
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
            "- nnU-Net should remain the formal engineering baseline; the MONAI models here screen architecture families and resource behavior.",
            "- Low-resolution short-budget Dice mainly indicates whether a model starts learning large anatomical structures; it is not enough to judge final mandibular canal performance.",
            "- The next formal stage should return to high-resolution nnU-Net/MedNeXt/U-Mamba training, 5-fold validation, and HD95/NSD/clDice reporting.",
            "",
            "## Evidence Basis",
            "",
        ]
    )
    for item in payload["model_sources"]:
        lines.append(f"- {item['name']}: {item['reason']}. Source: {item['url']}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Result JSON: `{payload['paths']['summary_json']}`",
            f"- Result CSV: `{payload['paths']['results_csv']}`",
            f"- Chinese report: `{payload['paths']['zh_report']}`",
            f"- This report: `{payload['paths']['en_report']}`",
            "",
            "## Medical Boundary",
            "",
            "D024 is an anatomical CBCT segmentation dataset. It does not contain jaw osteomyelitis, necrotic bone, or ICG fluorescence labels. These outputs are only anatomical ROI and model-selection evidence, not clinical diagnostic claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def _result_table_row(rank: int, row: dict[str, Any]) -> str:
    return (
        f"| {rank} | {row['display_name']} | {row['status']} | {_fmt(row.get('foreground_mean_dice'))} | "
        f"{_fmt(row.get('foreground_mean_iou'))} | {int(row.get('parameter_count') or 0):,} | "
        f"{_fmt(row.get('train_loss'))} | {_fmt(row.get('elapsed_seconds'))} | {_fmt(row.get('peak_memory_mb'))} |"
    )


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return ""
    return f"{number:.4f}"


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    return write_csv(
        path,
        rows,
        [
            "model_id",
            "display_name",
            "family",
            "status",
            "parameter_count",
            "train_batches",
            "val_cases",
            "train_loss",
            "foreground_mean_dice",
            "foreground_mean_iou",
            "elapsed_seconds",
            "peak_memory_mb",
            "source_url",
            "error",
        ],
    )


def model_sources(catalog: dict[str, ModelCandidate]) -> list[dict[str, str]]:
    sources = [
        {
            "name": "nnU-Net v2 / ResEnc",
            "reason": "Dental CBCT and biomedical segmentation engineering baseline; retained for formal high-resolution experiments.",
            "url": "https://github.com/MIC-DKFZ/nnUNet",
        },
        {
            "name": "MedNeXt",
            "reason": "3D ConvNeXt-style segmentation baseline for a later high-resolution comparison.",
            "url": "https://github.com/MIC-DKFZ/MedNeXt",
        },
        {
            "name": "U-Mamba / SegMamba",
            "reason": "Mamba-based medical segmentation candidates for later long-range dependency experiments.",
            "url": "https://github.com/bowang-lab/U-Mamba",
        },
    ]
    sources.extend(
        {
            "name": candidate.display_name,
            "reason": candidate.rationale,
            "url": candidate.source_url,
        }
        for candidate in catalog.values()
    )
    return sources


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
    catalog = model_catalog()
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
    summary_json = output_dir / "d024_10_model_baseline_benchmark_summary.json"
    results_csv = output_dir / "d024_10_model_baseline_benchmark_results.csv"
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
    parser = argparse.ArgumentParser(description="Benchmark 10 3D segmentation model candidates on D024 jaw-roi.")
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
    parser.add_argument("--models", default="", help="Comma-separated model IDs. Empty runs all 10 candidates.")
    parser.add_argument("--force-cache", action="store_true")
    return parser.parse_args()


def main() -> int:
    payload = run_benchmark(parse_args())
    print(json.dumps({"run_id": payload["run_id"], "paths": payload["paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
