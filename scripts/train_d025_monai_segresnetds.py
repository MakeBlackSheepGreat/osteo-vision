from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from monai.networks import nets
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from scripts.evaluate_d025_proxy_model import (
    _best_threshold_summary,
    _evaluate_case_at_threshold,
    _failure_cases,
    _summarize_threshold,
    _write_failure_previews,
    _write_threshold_csv,
)
from src.core.paths import ensure_dir, project_root, resolve_path
from src.models.lesion_segmenter import checkpoint_sha256, load_npz_image, load_npz_label, select_torch_device
from src.reports.writers import write_json

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d025_lesion_cbct/derived/local_preprocessed/lesion_roi_64/"
    "d025_dolchid_lesion_roi_64_manifest.csv"
)
DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/d025_monai_segresnetds.pt"
DEFAULT_REPORT_DIR = "research/reports/modeling"
DEFAULT_ASSET_ROOT = "research/reports/modeling/assets"
DEFAULT_THRESHOLDS = "0.20,0.30,0.40,0.50,0.60,0.70,0.80"
DEFAULT_SEED = 20260704
MODEL_ID = "d025_monai_segresnetds_proxy_segmenter"
MODEL_FAMILY = "monai_segresnetds"
MEDICAL_BOUNDARY = (
    "D025 CBCT lesion ROI proxy training only; not target-domain intraoperative ICG jaw osteomyelitis performance."
)


class D025NpzDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path = self.rows[index]["cache_path"]
        image = load_npz_image(path).astype(np.float32, copy=False)
        label = (load_npz_label(path) > 0).astype(np.int64, copy=False)
        return torch.from_numpy(image[None]), torch.from_numpy(label)


def build_model(*, init_filters: int, dsdepth: int) -> nn.Module:
    return nets.SegResNetDS(
        spatial_dims=3,
        init_filters=int(init_filters),
        in_channels=1,
        out_channels=2,
        blocks_down=(1, 1, 2, 2),
        dsdepth=int(dsdepth),
    )


def load_manifest_rows(manifest_path: str | Path) -> list[dict[str, Any]]:
    path = resolve_path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing D025 manifest: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            cache_path = Path(row.get("cache_path") or row.get("input_path") or "")
            if not cache_path.is_absolute():
                cache_path = project_root() / cache_path
            rows.append({**row, "cache_path": str(cache_path)})
    return rows


def split_rows(
    rows: list[dict[str, Any]], *, max_train_cases: int, max_val_cases: int
) -> dict[str, list[dict[str, Any]]]:
    train = [row for row in rows if row.get("split") == "train"]
    val = [row for row in rows if row.get("split") == "val"]
    if not train:
        train = rows[: max(1, len(rows) - max_val_cases)]
    if not val:
        val = rows[-max_val_cases:]
    return {
        "train": train[:max_train_cases] if max_train_cases > 0 else train,
        "val": val[:max_val_cases] if max_val_cases > 0 else val,
    }


def train_model(args: argparse.Namespace) -> dict[str, Any]:
    _set_seed(args.seed)
    started = time.perf_counter()
    rows = load_manifest_rows(args.manifest)
    split = split_rows(rows, max_train_cases=args.max_train_cases, max_val_cases=args.max_val_cases)
    if not split["train"]:
        raise ValueError("No D025 training rows available")
    if not split["val"]:
        raise ValueError("No D025 validation rows available")

    device = select_torch_device(args.device)
    model = build_model(init_filters=args.init_filters, dsdepth=args.dsdepth).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    class_weight = torch.tensor([1.0, args.positive_class_weight], dtype=torch.float32, device=device)
    loader = DataLoader(
        D025NpzDataset(split["train"]),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        generator=torch.Generator().manual_seed(args.seed),
    )

    losses: list[float] = []
    completed_batches = 0
    epochs_seen = 0
    peak_memory_mb: float | None = None
    model.train()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    while completed_batches < args.max_train_batches and epochs_seen < args.max_epochs:
        epochs_seen += 1
        for image, target in loader:
            if completed_batches >= args.max_train_batches:
                break
            image = image.to(device=device, dtype=torch.float32, non_blocking=True)
            target = target.to(device=device, dtype=torch.long, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = _primary_output(model(image))
            loss = 0.5 * F.cross_entropy(logits, target, weight=class_weight) + 0.5 * foreground_dice_loss(
                logits, target
            )
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            completed_batches += 1
    if device.type == "cuda":
        peak_memory_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))

    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = ensure_dir(resolve_path(args.report_dir))
    asset_dir = ensure_dir(resolve_path(args.asset_root) / f"d025_monai_segresnetds_{run_stamp}")

    evaluation = evaluate_model(
        model,
        split["val"],
        thresholds=_parse_thresholds(args.thresholds),
        device=device,
        asset_dir=asset_dir,
        failure_count=args.failure_count,
    )
    best_metrics = _flat_best_metrics(evaluation["best_summary"])

    checkpoint_path = resolve_path(args.output_checkpoint)
    ensure_dir(checkpoint_path.parent)
    checkpoint_payload = {
        "model_id": MODEL_ID,
        "model_family": MODEL_FAMILY,
        "model_config": {
            "architecture": "monai.networks.nets.SegResNetDS",
            "in_channels": 1,
            "out_channels": 2,
            "init_filters": int(args.init_filters),
            "blocks_down": [1, 1, 2, 2],
            "dsdepth": int(args.dsdepth),
        },
        "state_dict": model.state_dict(),
        "threshold": float(evaluation["best_threshold"]),
        "training": {
            "manifest_path": str(resolve_path(args.manifest)),
            "train_cases": len(split["train"]),
            "val_cases": len(split["val"]),
            "max_train_batches": args.max_train_batches,
            "completed_train_batches": completed_batches,
            "epochs_seen": epochs_seen,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "positive_class_weight": args.positive_class_weight,
            "seed": args.seed,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "mean_train_loss": float(np.mean(losses)) if losses else None,
        },
        "metrics": best_metrics,
        "medical_boundary": MEDICAL_BOUNDARY,
        "clinical_claim_allowed": False,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(checkpoint_payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)

    manifest_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_manifest.json")
    model_card_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_model_card.json")
    artifact_manifest = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "model_id": MODEL_ID,
        "model_family": MODEL_FAMILY,
        "runtime_allowed": False,
        "clinical_claim_allowed": False,
        "training": checkpoint_payload["training"],
        "metrics": best_metrics,
        "warnings": [
            "This checkpoint is trained on D025 CBCT lesion ROI proxy data only.",
            "It must not be reported as clinical jaw osteomyelitis or intraoperative ICG performance.",
            "Runtime adapter integration is not enabled unless this candidate is selected after comparison.",
        ],
    }
    write_json(manifest_path, artifact_manifest)
    write_json(
        model_card_path,
        {
            "model_id": MODEL_ID,
            "model_family": MODEL_FAMILY,
            "intended_use": "SegResNetDS baseline for D025 CBCT lesion ROI proxy model comparison.",
            "training_data": {
                "dataset": "D025 DOLCHID local 64 cubed CBCT lesion ROI cache",
                "manifest_path": str(resolve_path(args.manifest)),
                "case_count": len(rows),
            },
            "metrics": best_metrics,
            "limitations": artifact_manifest["warnings"],
            "clinical_claim_allowed": False,
        },
    )

    output_paths = {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "model_card_path": str(model_card_path),
        "json_path": str(report_dir / f"d025_monai_segresnetds_training_{date_stamp}.json"),
        "csv_path": str(report_dir / f"d025_monai_segresnetds_training_{date_stamp}_per_case.csv"),
        "zh_report_path": str(report_dir / f"d025_monai_segresnetds_training_{date_stamp}_zh.md"),
        "en_report_path": str(report_dir / f"d025_monai_segresnetds_training_{date_stamp}_en.md"),
        "asset_dir": str(asset_dir),
    }
    payload = {
        "schema_version": "osteo-vision-d025-monai-segresnetds-training-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(resolve_path(args.manifest)),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "model": {
            "model_id": MODEL_ID,
            "model_family": MODEL_FAMILY,
            "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
            "config": checkpoint_payload["model_config"],
        },
        "training": checkpoint_payload["training"],
        "evaluation": {
            **evaluation,
            "device": str(device),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "peak_memory_mb": peak_memory_mb,
            "clinical_claim_allowed": False,
            "medical_boundary": MEDICAL_BOUNDARY,
        },
        "comparison": load_convnext_baseline(report_dir, date_stamp),
        "outputs": output_paths,
    }
    _write_threshold_csv(Path(output_paths["csv_path"]), evaluation["threshold_rows"])
    write_json(output_paths["json_path"], payload)
    Path(output_paths["zh_report_path"]).write_text(render_report(payload, language="zh"), encoding="utf-8")
    Path(output_paths["en_report_path"]).write_text(render_report(payload, language="en"), encoding="utf-8")
    return payload


def foreground_dice_loss(logits: torch.Tensor, target: torch.Tensor, *, smooth: float = 1e-5) -> torch.Tensor:
    probability = torch.softmax(logits, dim=1)[:, 1]
    foreground = (target > 0).float()
    intersection = torch.sum(probability * foreground)
    denominator = torch.sum(probability) + torch.sum(foreground)
    return 1.0 - (2.0 * intersection + smooth) / (denominator + smooth)


def evaluate_model(
    model: nn.Module,
    rows: list[dict[str, Any]],
    *,
    thresholds: list[float],
    device: torch.device,
    asset_dir: Path,
    failure_count: int,
) -> dict[str, Any]:
    model.eval()
    evaluated_cases: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in rows:
            image = load_npz_image(row["cache_path"])
            target = load_npz_label(row["cache_path"]) > 0
            tensor = torch.from_numpy(image[None, None].astype(np.float32, copy=False)).to(device)
            probability = (
                torch.softmax(_primary_output(model(tensor)), dim=1)[0, 1].detach().cpu().numpy().astype(np.float32)
            )
            evaluated_cases.append({"row": row, "image": image, "target": target, "probability": probability})

    threshold_rows = []
    for threshold in thresholds:
        for case in evaluated_cases:
            threshold_rows.append(_evaluate_case_at_threshold(case, threshold))
    threshold_summaries = [_summarize_threshold(threshold_rows, threshold) for threshold in thresholds]
    best_summary = _best_threshold_summary(threshold_summaries)
    best_threshold = float(best_summary["threshold"])
    best_case_rows = [row for row in threshold_rows if float(row["threshold"]) == best_threshold]
    failure_cases = _failure_cases(best_case_rows, limit=failure_count)
    _write_failure_previews(evaluated_cases, failure_cases, threshold=best_threshold, asset_dir=asset_dir)
    return {
        "case_count": len(evaluated_cases),
        "thresholds": thresholds,
        "best_threshold": best_threshold,
        "best_summary": best_summary,
        "threshold_summaries": threshold_summaries,
        "threshold_rows": threshold_rows,
        "failure_cases": failure_cases,
    }


def _flat_best_metrics(best_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_count": int(best_summary.get("case_count") or 0),
        "foreground_mean_dice": _summary_mean(best_summary.get("dice")),
        "foreground_mean_iou": _summary_mean(best_summary.get("iou")),
        "foreground_mean_hd95": _summary_mean(best_summary.get("hd95")),
        "foreground_mean_nsd": _summary_mean(best_summary.get("nsd")),
        "lesion_sensitivity": _summary_mean(best_summary.get("lesion_sensitivity")),
        "lesion_precision": _summary_mean(best_summary.get("lesion_precision")),
        "prediction_positive_fraction": _summary_mean(best_summary.get("pred_positive_fraction")),
        "target_positive_fraction": _summary_mean(best_summary.get("target_positive_fraction")),
        "threshold": float(best_summary.get("threshold")),
    }


def load_convnext_baseline(report_dir: Path, date_stamp: str) -> dict[str, Any] | None:
    path = report_dir / f"d025_proxy_model_evaluation_{date_stamp}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    best = (payload.get("evaluation") or {}).get("best_summary") or {}
    if not best:
        return None
    return {
        "baseline_id": "convnext3d_d025_proxy_segmenter",
        "source_path": str(path),
        "best_metrics": _flat_best_metrics(best),
    }


def render_report(payload: dict[str, Any], *, language: str) -> str:
    evaluation = payload["evaluation"]
    training = payload["training"]
    outputs = payload["outputs"]
    best = evaluation["best_summary"]
    comparison = payload.get("comparison")
    if language == "zh":
        lines = [
            "# D025 MONAI SegResNetDS 代理分割训练报告",
            "",
            "## 定位",
            "",
            "本报告记录 MONAI SegResNetDS 在 D025 CBCT lesion ROI 64³ 缓存上的训练与验证。它是模型路线对比证据，不代表真实术中 ICG 颌骨骨髓炎视频或图片性能。",
            "",
            "## 模型与训练",
            "",
            f"- 模型：`{payload['model']['model_id']}` / `{payload['model']['model_family']}`。",
            f"- 参数量：{payload['model']['parameter_count']:,}。",
            f"- Manifest：`{payload['manifest_path']}`",
            f"- 训练病例：{training['train_cases']}；验证病例：{training['val_cases']}。",
            f"- 完成 batch：{training['completed_train_batches']}；epoch：{training['epochs_seen']}；batch size：{training['batch_size']}。",
            f"- 学习率：{training['learning_rate']}；正类权重：{training['positive_class_weight']}；平均训练 loss：{_fmt_metric(training['mean_train_loss'])}。",
            f"- 设备：`{evaluation['device']}`；GPU：`{evaluation.get('cuda_device_name')}`；峰值显存 MB：{_fmt_metric(evaluation.get('peak_memory_mb'))}。",
            "",
            "## 最优阈值摘要",
            "",
            *_best_metric_lines(best, language="zh"),
            "",
            "## 阈值扫描",
            "",
            "| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            *_threshold_table_rows(evaluation["threshold_summaries"]),
            "",
            "## 与当前 ConvNeXt-style 代理模型对比",
            "",
            *_comparison_lines(comparison, best, language="zh"),
            "",
            "## 低分样本",
            "",
            *_failure_lines(evaluation["failure_cases"], language="zh"),
            "",
            "## 输出文件",
            "",
            f"- Checkpoint：`{outputs['checkpoint_path']}`",
            f"- JSON：`{outputs['json_path']}`",
            f"- CSV：`{outputs['csv_path']}`",
            f"- 预览图目录：`{outputs['asset_dir']}`",
            "",
            "## 医学边界",
            "",
            evaluation["medical_boundary"],
        ]
        return "\n".join(lines) + "\n"

    lines = [
        "# D025 MONAI SegResNetDS Proxy Segmentation Training",
        "",
        "## Scope",
        "",
        "This report records MONAI SegResNetDS training and validation on the D025 64 cubed CBCT lesion ROI cache. It is model-route comparison evidence, not target-domain intraoperative ICG jaw osteomyelitis performance.",
        "",
        "## Model and Training",
        "",
        f"- Model: `{payload['model']['model_id']}` / `{payload['model']['model_family']}`.",
        f"- Parameters: {payload['model']['parameter_count']:,}.",
        f"- Manifest: `{payload['manifest_path']}`",
        f"- Training cases: {training['train_cases']}; validation cases: {training['val_cases']}.",
        f"- Completed batches: {training['completed_train_batches']}; epochs: {training['epochs_seen']}; batch size: {training['batch_size']}.",
        f"- Learning rate: {training['learning_rate']}; positive class weight: {training['positive_class_weight']}; mean train loss: {_fmt_metric(training['mean_train_loss'])}.",
        f"- Device: `{evaluation['device']}`; GPU: `{evaluation.get('cuda_device_name')}`; peak GPU MB: {_fmt_metric(evaluation.get('peak_memory_mb'))}.",
        "",
        "## Best Threshold Summary",
        "",
        *_best_metric_lines(best, language="en"),
        "",
        "## Threshold Sweep",
        "",
        "| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        *_threshold_table_rows(evaluation["threshold_summaries"]),
        "",
        "## Comparison With Current ConvNeXt-Style Proxy",
        "",
        *_comparison_lines(comparison, best, language="en"),
        "",
        "## Low-Scoring Cases",
        "",
        *_failure_lines(evaluation["failure_cases"], language="en"),
        "",
        "## Outputs",
        "",
        f"- Checkpoint: `{outputs['checkpoint_path']}`",
        f"- JSON: `{outputs['json_path']}`",
        f"- CSV: `{outputs['csv_path']}`",
        f"- Preview directory: `{outputs['asset_dir']}`",
        "",
        "## Medical Boundary",
        "",
        evaluation["medical_boundary"],
    ]
    return "\n".join(lines) + "\n"


def _best_metric_lines(best: dict[str, Any], *, language: str) -> list[str]:
    names = {
        "zh": {
            "threshold": "最优阈值",
            "dice": "Mean Dice",
            "iou": "Mean IoU",
            "hd95": "Mean HD95",
            "nsd": "Mean NSD",
            "lesion_sensitivity": "Lesion sensitivity",
            "lesion_precision": "Lesion precision",
        },
        "en": {
            "threshold": "Best threshold",
            "dice": "Mean Dice",
            "iou": "Mean IoU",
            "hd95": "Mean HD95",
            "nsd": "Mean NSD",
            "lesion_sensitivity": "Lesion sensitivity",
            "lesion_precision": "Lesion precision",
        },
    }[language]
    return [
        (
            f"- {names['threshold']}：{_fmt_metric(best.get('threshold'))}"
            if language == "zh"
            else f"- {names['threshold']}: {_fmt_metric(best.get('threshold'))}"
        ),
        (
            f"- {names['dice']}：{_fmt_metric((best.get('dice') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['dice']}: {_fmt_metric((best.get('dice') or {}).get('mean'))}"
        ),
        (
            f"- {names['iou']}：{_fmt_metric((best.get('iou') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['iou']}: {_fmt_metric((best.get('iou') or {}).get('mean'))}"
        ),
        (
            f"- {names['hd95']}：{_fmt_metric((best.get('hd95') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['hd95']}: {_fmt_metric((best.get('hd95') or {}).get('mean'))}"
        ),
        (
            f"- {names['nsd']}：{_fmt_metric((best.get('nsd') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['nsd']}: {_fmt_metric((best.get('nsd') or {}).get('mean'))}"
        ),
        (
            f"- {names['lesion_sensitivity']}：{_fmt_metric((best.get('lesion_sensitivity') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['lesion_sensitivity']}: {_fmt_metric((best.get('lesion_sensitivity') or {}).get('mean'))}"
        ),
        (
            f"- {names['lesion_precision']}：{_fmt_metric((best.get('lesion_precision') or {}).get('mean'))}"
            if language == "zh"
            else f"- {names['lesion_precision']}: {_fmt_metric((best.get('lesion_precision') or {}).get('mean'))}"
        ),
    ]


def _threshold_table_rows(threshold_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in threshold_rows:
        lines.append(
            "| "
            f"{_fmt_metric(row['threshold'])} | "
            f"{_fmt_metric((row.get('dice') or {}).get('mean'))} | "
            f"{_fmt_metric((row.get('iou') or {}).get('mean'))} | "
            f"{_fmt_metric((row.get('hd95') or {}).get('mean'))} | "
            f"{_fmt_metric((row.get('nsd') or {}).get('mean'))} | "
            f"{_fmt_metric((row.get('lesion_sensitivity') or {}).get('mean'))} | "
            f"{_fmt_metric((row.get('lesion_precision') or {}).get('mean'))} |"
        )
    return lines


def _comparison_lines(comparison: dict[str, Any] | None, best: dict[str, Any], *, language: str) -> list[str]:
    if not comparison:
        return (
            ["- 暂无同日 ConvNeXt-style 评估 JSON 可自动对比。"]
            if language == "zh"
            else ["- No same-day ConvNeXt-style evaluation JSON was available for automatic comparison."]
        )
    baseline = comparison["best_metrics"]
    current = _flat_best_metrics(best)
    dice_delta = _delta(current.get("foreground_mean_dice"), baseline.get("foreground_mean_dice"))
    iou_delta = _delta(current.get("foreground_mean_iou"), baseline.get("foreground_mean_iou"))
    if language == "zh":
        return [
            f"- ConvNeXt-style baseline：Dice={_fmt_metric(baseline.get('foreground_mean_dice'))}，IoU={_fmt_metric(baseline.get('foreground_mean_iou'))}，threshold={_fmt_metric(baseline.get('threshold'))}。",
            f"- SegResNetDS 本轮：Dice={_fmt_metric(current.get('foreground_mean_dice'))}，IoU={_fmt_metric(current.get('foreground_mean_iou'))}，threshold={_fmt_metric(current.get('threshold'))}。",
            f"- 差值：Dice {dice_delta}；IoU {iou_delta}。若未超过当前 baseline，不应替换主线 checkpoint。",
        ]
    return [
        f"- ConvNeXt-style baseline: Dice={_fmt_metric(baseline.get('foreground_mean_dice'))}, IoU={_fmt_metric(baseline.get('foreground_mean_iou'))}, threshold={_fmt_metric(baseline.get('threshold'))}.",
        f"- SegResNetDS run: Dice={_fmt_metric(current.get('foreground_mean_dice'))}, IoU={_fmt_metric(current.get('foreground_mean_iou'))}, threshold={_fmt_metric(current.get('threshold'))}.",
        f"- Delta: Dice {dice_delta}; IoU {iou_delta}. If it does not beat the current baseline, it should not replace the main checkpoint.",
    ]


def _failure_lines(failures: list[dict[str, Any]], *, language: str) -> list[str]:
    if not failures:
        return ["暂无。"] if language == "zh" else ["None."]
    lines: list[str] = []
    for failure in failures:
        prefix = "病例" if language == "zh" else "Case"
        preview = failure.get("preview_path")
        line = (
            f"- {prefix} `{failure['case_id']}` "
            f"({failure['diagnosis_group']}): Dice={_fmt_metric(failure.get('dice'))}, "
            f"IoU={_fmt_metric(failure.get('iou'))}, HD95={_fmt_metric(failure.get('hd95'))}"
        )
        if preview:
            line += f"; preview=`{preview}`"
        lines.append(line)
    return lines


def _primary_output(output: Any) -> torch.Tensor:
    if isinstance(output, (tuple, list)):
        return output[0]
    return output


def _summary_mean(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    mean = value.get("mean")
    if mean is None:
        return None
    return float(mean)


def _delta(current: Any, baseline: Any) -> str:
    if current is None or baseline is None:
        return "N/A"
    return f"{float(current) - float(baseline):+.4f}"


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _parse_thresholds(value: str) -> list[float]:
    thresholds = sorted({float(item.strip()) for item in value.split(",") if item.strip()})
    if not thresholds:
        raise ValueError("At least one threshold is required")
    for threshold in thresholds:
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError(f"Threshold must be in [0, 1], got {threshold}")
    return thresholds


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train MONAI SegResNetDS on the D025 CBCT lesion ROI proxy cache.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--asset-root", default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--max-train-cases", type=int, default=0, help="0 means all training rows.")
    parser.add_argument("--max-val-cases", type=int, default=0, help="0 means all validation rows.")
    parser.add_argument("--max-train-batches", type=int, default=3000)
    parser.add_argument("--max-epochs", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=6e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--positive-class-weight", type=float, default=8.0)
    parser.add_argument("--init-filters", type=int, default=16)
    parser.add_argument("--dsdepth", type=int, default=1)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--failure-count", type=int, default=8)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> int:
    payload = train_model(parse_args())
    print(
        json.dumps(
            {
                "checkpoint_path": payload["checkpoint_path"],
                "outputs": payload["outputs"],
                "best_summary": payload["evaluation"]["best_summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
