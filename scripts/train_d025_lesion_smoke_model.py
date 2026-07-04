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
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from src.core.paths import ensure_dir, project_root, resolve_path
from src.models.lesion_segmenter import (
    TinyLesionSegmenter3D,
    checkpoint_sha256,
    load_npz_image,
    load_npz_label,
    select_torch_device,
)
from src.reports.writers import write_json

DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d025_lesion_cbct/derived/local_preprocessed/lesion_roi_64/"
    "d025_dolchid_lesion_roi_64_manifest.csv"
)
DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt"
DEFAULT_REPORT_DIR = "research/reports/modeling"
DEFAULT_SEED = 20260703


class D025NpzDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path = self.rows[index]["cache_path"]
        image = load_npz_image(path)
        label = (load_npz_label(path) > 0).astype(np.int64, copy=False)
        return torch.from_numpy(image[None].astype(np.float32, copy=False)), torch.from_numpy(label)


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
    return {"train": train[:max_train_cases], "val": val[:max_val_cases]}


def train_smoke_model(args: argparse.Namespace) -> dict[str, Any]:
    _set_seed(args.seed)
    rows = load_manifest_rows(args.manifest)
    split = split_rows(rows, max_train_cases=args.max_train_cases, max_val_cases=args.max_val_cases)
    if not split["train"]:
        raise ValueError("No D025 training rows available")
    device = select_torch_device(args.device)
    model = TinyLesionSegmenter3D(base_channels=args.base_channels).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    class_weight = torch.tensor([1.0, args.positive_class_weight], dtype=torch.float32, device=device)
    loader = DataLoader(
        D025NpzDataset(split["train"]),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        generator=torch.Generator().manual_seed(args.seed),
    )
    started = time.perf_counter()
    losses: list[float] = []
    completed_batches = 0
    model.train()
    while completed_batches < args.max_train_batches:
        for image, target in loader:
            image = image.to(device=device, dtype=torch.float32)
            target = target.to(device=device, dtype=torch.long)
            optimizer.zero_grad(set_to_none=True)
            logits = model(image)
            loss = 0.5 * F.cross_entropy(logits, target, weight=class_weight) + 0.5 * foreground_dice_loss(
                logits, target
            )
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            completed_batches += 1
            if completed_batches >= args.max_train_batches:
                break
    metrics = evaluate_model(model, split["val"], device=device, threshold=args.threshold)
    elapsed = round(time.perf_counter() - started, 3)
    checkpoint_path = resolve_path(args.output_checkpoint)
    ensure_dir(checkpoint_path.parent)
    model_config = {"in_channels": 1, "out_channels": 2, "base_channels": args.base_channels}
    checkpoint_payload = {
        "model_id": "d025_lesion_smoke_segmenter",
        "model_family": "d025_lesion_segmenter",
        "model_config": model_config,
        "threshold": args.threshold,
        "state_dict": model.state_dict(),
        "training": {
            "manifest_path": str(resolve_path(args.manifest)),
            "train_cases": len(split["train"]),
            "val_cases": len(split["val"]),
            "max_train_batches": args.max_train_batches,
            "completed_train_batches": completed_batches,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "seed": args.seed,
            "elapsed_seconds": elapsed,
            "mean_train_loss": float(np.mean(losses)) if losses else None,
        },
        "metrics": metrics,
        "medical_boundary": "D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.",
        "clinical_claim_allowed": False,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    torch.save(checkpoint_payload, checkpoint_path)
    digest = checkpoint_sha256(checkpoint_path)
    artifact_manifest = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": digest,
        "model_id": checkpoint_payload["model_id"],
        "model_family": checkpoint_payload["model_family"],
        "runtime_allowed": True,
        "clinical_claim_allowed": False,
        "training": checkpoint_payload["training"],
        "metrics": metrics,
        "warnings": [
            "This checkpoint is for engineering smoke validation on D025 CBCT lesion ROI proxy data only.",
            "It must not be reported as clinical jaw osteomyelitis or intraoperative ICG performance.",
        ],
    }
    manifest_path = checkpoint_path.with_name("d025_lesion_smoke_manifest.json")
    model_card_path = checkpoint_path.with_name("d025_lesion_smoke_model_card.json")
    write_json(manifest_path, artifact_manifest)
    write_json(
        model_card_path,
        {
            "model_id": checkpoint_payload["model_id"],
            "model_family": checkpoint_payload["model_family"],
            "intended_use": "Engineering smoke model for adapter and segmentation pipeline integration.",
            "training_data": {
                "dataset": "D025 DOLCHID local 64 cubed CBCT lesion ROI cache",
                "manifest_path": str(resolve_path(args.manifest)),
                "case_count": len(rows),
            },
            "metrics": metrics,
            "limitations": artifact_manifest["warnings"],
            "clinical_claim_allowed": False,
        },
    )
    report_paths = write_reports(
        {
            "checkpoint_path": str(checkpoint_path),
            "manifest_path": str(manifest_path),
            "model_card_path": str(model_card_path),
            "checkpoint_sha256": digest,
            "training": checkpoint_payload["training"],
            "metrics": metrics,
            "environment": {
                "device": str(device),
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
            },
            "medical_boundary": checkpoint_payload["medical_boundary"],
        },
        report_dir=args.report_dir,
    )
    return {
        "checkpoint_path": str(checkpoint_path),
        "manifest_path": str(manifest_path),
        "model_card_path": str(model_card_path),
        "report_paths": report_paths,
        "metrics": metrics,
    }


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
    device: torch.device,
    threshold: float,
) -> dict[str, Any]:
    model.eval()
    dice_scores: list[float] = []
    iou_scores: list[float] = []
    true_positive = 0.0
    false_positive = 0.0
    false_negative = 0.0
    predicted_positive = 0
    target_positive = 0
    total_voxels = 0
    with torch.no_grad():
        for row in rows:
            image = load_npz_image(row["cache_path"])
            target = load_npz_label(row["cache_path"]) > 0
            tensor = torch.from_numpy(image[None, None].astype(np.float32, copy=False)).to(device)
            probability = torch.softmax(model(tensor), dim=1)[0, 1].detach().cpu().numpy()
            prediction = probability >= threshold
            scores = binary_scores(prediction, target)
            if scores["dice"] is not None:
                dice_scores.append(float(scores["dice"]))
            if scores["iou"] is not None:
                iou_scores.append(float(scores["iou"]))
            true_positive += float(np.logical_and(prediction, target).sum())
            false_positive += float(np.logical_and(prediction, ~target).sum())
            false_negative += float(np.logical_and(~prediction, target).sum())
            predicted_positive += int(prediction.sum())
            target_positive += int(target.sum())
            total_voxels += int(target.size)
    return {
        "case_count": len(rows),
        "foreground_mean_dice": float(np.mean(dice_scores)) if dice_scores else None,
        "foreground_mean_iou": float(np.mean(iou_scores)) if iou_scores else None,
        "lesion_sensitivity": safe_div(true_positive, true_positive + false_negative),
        "lesion_precision": safe_div(true_positive, true_positive + false_positive),
        "prediction_positive_fraction": safe_div(predicted_positive, total_voxels),
        "target_positive_fraction": safe_div(target_positive, total_voxels),
        "threshold": float(threshold),
    }


def binary_scores(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | None]:
    pred = np.asarray(prediction).astype(bool)
    true = np.asarray(target).astype(bool)
    pred_area = float(pred.sum())
    target_area = float(true.sum())
    intersection = float(np.logical_and(pred, true).sum())
    union = float(np.logical_or(pred, true).sum())
    if pred_area == 0 and target_area == 0:
        return {"dice": None, "iou": None}
    dice = 0.0 if pred_area + target_area == 0 else 2.0 * intersection / (pred_area + target_area)
    iou = 0.0 if union == 0 else intersection / union
    return {"dice": float(dice), "iou": float(iou)}


def safe_div(numerator: float | int, denominator: float | int) -> float | None:
    denominator_float = float(denominator)
    if denominator_float == 0.0:
        return None
    return float(numerator) / denominator_float


def write_reports(payload: dict[str, Any], *, report_dir: str | Path) -> dict[str, str]:
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    out_dir = ensure_dir(resolve_path(report_dir))
    zh_path = out_dir / f"d025_lesion_smoke_model_{date_stamp}_zh.md"
    en_path = out_dir / f"d025_lesion_smoke_model_{date_stamp}_en.md"
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    metrics = payload["metrics"]
    training = payload["training"]
    if language == "zh":
        lines = [
            "# D025 病灶 ROI 代理分割 Smoke 模型报告",
            "",
            "## 定位",
            "",
            "本报告记录一个小型 3D ConvNeXt-U-Net 风格分割模型在 D025 CBCT 病灶 ROI 64³ 缓存上的 smoke 训练。它用于验证训练、checkpoint、adapter 和主线 segmentation pipeline 能否闭环，不代表真实术中 ICG 颌骨骨髓炎性能。",
            "",
            "## 训练设置",
            "",
            f"- Checkpoint：`{payload['checkpoint_path']}`",
            f"- Manifest：`{payload['manifest_path']}`",
            f"- Model card：`{payload['model_card_path']}`",
            f"- 训练病例：{training['train_cases']}；验证病例：{training['val_cases']}。",
            f"- 训练 batch：{training['completed_train_batches']}；batch size：{training['batch_size']}。",
            f"- 平均训练 loss：{_fmt(training['mean_train_loss'])}。",
            f"- 设备：{payload['environment']['device']}；PyTorch：{payload['environment']['torch_version']}。",
            "",
            "## Smoke 指标",
            "",
            f"- Foreground Dice：{_fmt(metrics.get('foreground_mean_dice'))}",
            f"- Foreground IoU：{_fmt(metrics.get('foreground_mean_iou'))}",
            f"- Lesion sensitivity：{_fmt(metrics.get('lesion_sensitivity'))}",
            f"- Lesion precision：{_fmt(metrics.get('lesion_precision'))}",
            f"- Prediction positive fraction：{_fmt(metrics.get('prediction_positive_fraction'))}",
            f"- Target positive fraction：{_fmt(metrics.get('target_positive_fraction'))}",
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
        ]
    else:
        lines = [
            "# D025 Lesion ROI Proxy Segmentation Smoke Model",
            "",
            "## Scope",
            "",
            "This report records a small 3D ConvNeXt-U-Net style smoke training run on the D025 64 cubed CBCT lesion ROI cache. It verifies the training, checkpoint, adapter, and segmentation pipeline loop; it is not intraoperative ICG jaw osteomyelitis performance.",
            "",
            "## Training Setup",
            "",
            f"- Checkpoint: `{payload['checkpoint_path']}`",
            f"- Manifest: `{payload['manifest_path']}`",
            f"- Model card: `{payload['model_card_path']}`",
            f"- Train cases: {training['train_cases']}; validation cases: {training['val_cases']}.",
            f"- Training batches: {training['completed_train_batches']}; batch size: {training['batch_size']}.",
            f"- Mean train loss: {_fmt(training['mean_train_loss'])}.",
            f"- Device: {payload['environment']['device']}; PyTorch: {payload['environment']['torch_version']}.",
            "",
            "## Smoke Metrics",
            "",
            f"- Foreground Dice: {_fmt(metrics.get('foreground_mean_dice'))}",
            f"- Foreground IoU: {_fmt(metrics.get('foreground_mean_iou'))}",
            f"- Lesion sensitivity: {_fmt(metrics.get('lesion_sensitivity'))}",
            f"- Lesion precision: {_fmt(metrics.get('lesion_precision'))}",
            f"- Prediction positive fraction: {_fmt(metrics.get('prediction_positive_fraction'))}",
            f"- Target positive fraction: {_fmt(metrics.get('target_positive_fraction'))}",
            "",
            "## Medical Boundary",
            "",
            payload["medical_boundary"],
        ]
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a tiny D025 CBCT lesion ROI smoke segmentation model.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--max-train-cases", type=int, default=32)
    parser.add_argument("--max-val-cases", type=int, default=4)
    parser.add_argument("--max-train-batches", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--base-channels", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--positive-class-weight", type=float, default=2.0)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    payload = train_smoke_model(parse_args())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
