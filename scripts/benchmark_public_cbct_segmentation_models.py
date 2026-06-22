from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from scripts.benchmark_d024_frontier_segmentation_models import frontier_model_catalog
from scripts.benchmark_d024_segmentation_models import ModelCandidate, _primary_output, model_catalog as monai_model_catalog
from src.core.paths import ensure_dir
from src.reports.writers import write_csv, write_json


DEFAULT_OUTPUT_ROOT = Path("artifacts/runs/public_cbct_segmentation_benchmark")
DEFAULT_REPORT_DIR = Path("research/reports/modeling")
DEFAULT_SEED = 20260617
DEFAULT_TOP_MODELS = [
    "monai_segresnetds",
    "monai_unetplusplus",
    "monai_segresnet",
    "monai_swinunetr_tiny",
    "segmamba_multiscale_proxy",
    "uxnet_large_kernel_proxy",
]
LOSS_CHOICES = ["auto", "ce", "dice_ce", "dice_focal", "tversky_focal"]
CLASS_WEIGHTING_CHOICES = ["none", "inverse", "sqrt_inverse"]
TARGET_LABEL_CHOICES = ["all", "foreground", "lesion"]


@dataclass(frozen=True)
class DatasetSpec:
    dataset_key: str
    dataset_id: str
    task_group: str
    task_name: str
    display_name: str
    manifest_path: Path
    metric_profile: str
    medical_boundary: str


DATASETS = {
    "d024_jaw_roi": DatasetSpec(
        dataset_key="d024_jaw_roi",
        dataset_id="D024",
        task_group="anatomy_roi",
        task_name="jaw_roi_64",
        display_name="D024 DentVoxel jaw ROI",
        manifest_path=Path("research/datasets/public-candidates/d024_dentvoxel/derived/local_preprocessed/jaw_roi_64_manifest.csv"),
        metric_profile="anatomy",
        medical_boundary="Anatomical CBCT structure segmentation only; no osteomyelitis, necrotic-bone, or ICG labels.",
    ),
    "d036_anatomy_roi": DatasetSpec(
        dataset_key="d036_anatomy_roi",
        dataset_id="D036",
        task_group="anatomy_roi",
        task_name="anatomy_roi_64",
        display_name="D036 ToothFairy2 anatomy ROI",
        manifest_path=Path(
            "research/datasets/public-candidates/d036_toothfairy2/derived/local_preprocessed/anatomy_roi_64/d036_toothfairy2_anatomy_roi_64_manifest.csv"
        ),
        metric_profile="anatomy",
        medical_boundary="Anatomical CBCT structure segmentation only; no osteomyelitis, necrotic-bone, or ICG labels.",
    ),
    "d025_lesion_roi": DatasetSpec(
        dataset_key="d025_lesion_roi",
        dataset_id="D025",
        task_group="lesion_roi",
        task_name="lesion_roi_64",
        display_name="D025 DOLCHID lesion ROI",
        manifest_path=Path(
            "research/datasets/public-candidates/d025_lesion_cbct/derived/local_preprocessed/lesion_roi_64/d025_dolchid_lesion_roi_64_manifest.csv"
        ),
        metric_profile="lesion",
        medical_boundary="CBCT lesion-mask segmentation proxy; still not intraoperative ICG fluorescence or clinical diagnosis evidence.",
    ),
}


class ManifestNpzDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        with np.load(row["cache_path"]) as payload:
            image = payload["image"].astype(np.float32, copy=False)
            label = payload["label"].astype(np.int64, copy=False)
        return torch.from_numpy(image[None]), torch.from_numpy(label)


class SegmentationLoss(nn.Module):
    def __init__(
        self,
        *,
        loss_name: str,
        dice_labels: list[int],
        class_weight: torch.Tensor | None,
    ) -> None:
        super().__init__()
        self.loss_name = loss_name
        self.dice_labels = dice_labels
        self.register_buffer("class_weight", class_weight if class_weight is not None else None)

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        if self.loss_name == "ce":
            return F.cross_entropy(logits, target, weight=self.class_weight)
        ce = F.cross_entropy(logits, target, weight=self.class_weight)
        dice = soft_dice_loss(logits, target, self.dice_labels)
        if self.loss_name == "dice_ce":
            return 0.5 * ce + 0.5 * dice
        focal = focal_loss(logits, target, weight=self.class_weight)
        if self.loss_name == "dice_focal":
            return 0.5 * dice + 0.5 * focal
        if self.loss_name == "tversky_focal":
            return 0.5 * tversky_loss(logits, target, self.dice_labels) + 0.5 * focal
        raise ValueError(f"Unsupported loss: {self.loss_name}")


def soft_dice_loss(logits: torch.Tensor, target: torch.Tensor, labels: list[int], *, smooth: float = 1e-5) -> torch.Tensor:
    probabilities = torch.softmax(logits, dim=1)
    losses = []
    for label in labels:
        if label < 0 or label >= probabilities.shape[1]:
            continue
        pred = probabilities[:, label]
        true = (target == label).float()
        intersection = torch.sum(pred * true)
        denominator = torch.sum(pred) + torch.sum(true)
        losses.append(1.0 - (2.0 * intersection + smooth) / (denominator + smooth))
    if not losses:
        return logits.sum() * 0.0
    return torch.stack(losses).mean()


def focal_loss(logits: torch.Tensor, target: torch.Tensor, *, weight: torch.Tensor | None, gamma: float = 2.0) -> torch.Tensor:
    log_prob = F.log_softmax(logits, dim=1)
    log_pt = log_prob.gather(1, target.unsqueeze(1)).squeeze(1)
    pt = log_pt.exp()
    loss = -((1.0 - pt) ** gamma) * log_pt
    if weight is not None:
        loss = loss * weight[target]
    return loss.mean()


def tversky_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    labels: list[int],
    *,
    alpha: float = 0.3,
    beta: float = 0.7,
    smooth: float = 1e-5,
) -> torch.Tensor:
    probabilities = torch.softmax(logits, dim=1)
    losses = []
    for label in labels:
        if label < 0 or label >= probabilities.shape[1]:
            continue
        pred = probabilities[:, label]
        true = (target == label).float()
        tp = torch.sum(pred * true)
        fp = torch.sum(pred * (1.0 - true))
        fn = torch.sum((1.0 - pred) * true)
        losses.append(1.0 - (tp + smooth) / (tp + alpha * fp + beta * fn + smooth))
    if not losses:
        return logits.sum() * 0.0
    return torch.stack(losses).mean()


def row_label_stats(row: dict[str, Any]) -> dict[str, Any]:
    with np.load(row["cache_path"]) as payload:
        label = payload["label"]
        values, counts = np.unique(label, return_counts=True)
    label_counts = {int(value): int(count) for value, count in zip(values, counts)}
    total_voxels = int(label.size)
    foreground_voxels = int(sum(count for value, count in label_counts.items() if value > 0))
    return {
        "total_voxels": total_voxels,
        "foreground_voxels": foreground_voxels,
        "foreground_voxel_fraction": safe_div(foreground_voxels, total_voxels) or 0.0,
        "label_counts": label_counts,
    }


def annotate_rows_with_label_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for row in rows:
        if "foreground_voxel_fraction" in row and "label_counts" in row:
            annotated.append(row)
            continue
        annotated.append({**row, **row_label_stats(row)})
    return annotated


def foreground_sampling_weights(rows: list[dict[str, Any]], foreground_oversample_ratio: float) -> list[float]:
    if not rows:
        return []
    ratio = min(1.0, max(0.0, foreground_oversample_ratio))
    if ratio == 0.0:
        return [1.0] * len(rows)
    annotated = annotate_rows_with_label_stats(rows)
    fractions = np.asarray([float(row.get("foreground_voxel_fraction", 0.0)) for row in annotated], dtype=np.float64)
    if float(fractions.max(initial=0.0)) <= 0.0:
        return [1.0] * len(rows)
    normalized = fractions / max(float(fractions.mean()), 1e-12)
    weights = (1.0 - ratio) + ratio * normalized
    return [float(max(weight, 1e-6)) for weight in weights]


def build_training_loader(
    rows: list[dict[str, Any]],
    *,
    batch_size: int,
    foreground_oversample_ratio: float,
    seed: int,
    epoch_index: int,
) -> DataLoader[tuple[torch.Tensor, torch.Tensor]]:
    dataset = ManifestNpzDataset(rows)
    if foreground_oversample_ratio <= 0.0:
        generator = torch.Generator().manual_seed(seed + epoch_index)
        return DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0, generator=generator)
    weights = torch.as_tensor(foreground_sampling_weights(rows, foreground_oversample_ratio), dtype=torch.double)
    generator = torch.Generator().manual_seed(seed + epoch_index)
    sampler = WeightedRandomSampler(weights, num_samples=len(rows), replacement=True, generator=generator)
    return DataLoader(dataset, batch_size=batch_size, sampler=sampler, num_workers=0)


def resolve_loss_name(requested_loss: str, spec: DatasetSpec) -> str:
    if requested_loss == "auto":
        return "dice_focal" if spec.metric_profile == "lesion" else "dice_ce"
    return requested_loss


def resolve_target_labels(data_info: dict[str, Any], target_labels: str) -> list[int]:
    n_classes = int(data_info["n_classes"])
    foreground = [int(label) for label in data_info.get("foreground_labels", [])]
    if target_labels == "all":
        return list(range(n_classes))
    if target_labels == "lesion":
        return [1] if n_classes > 1 else foreground
    return foreground


def class_weight_tensor(data_info: dict[str, Any], mode: str, device: torch.device) -> torch.Tensor | None:
    if mode == "none":
        return None
    counts = np.asarray(data_info.get("label_voxel_counts", []), dtype=np.float64)
    if counts.size == 0:
        return None
    present = counts > 0
    weights = np.ones_like(counts, dtype=np.float64)
    if mode == "inverse":
        weights[present] = 1.0 / np.maximum(counts[present], 1.0)
    elif mode == "sqrt_inverse":
        weights[present] = 1.0 / np.sqrt(np.maximum(counts[present], 1.0))
    else:
        raise ValueError(f"Unsupported class weighting mode: {mode}")
    weights[~present] = 0.0
    mean_present = float(weights[present].mean()) if present.any() else 1.0
    weights = weights / max(mean_present, 1e-12)
    weights = np.clip(weights, 0.05, 10.0)
    return torch.as_tensor(weights, dtype=torch.float32, device=device)


def build_segmentation_loss(
    *,
    loss_name: str,
    data_info: dict[str, Any],
    target_labels: str,
    class_weighting: str,
    device: torch.device,
) -> SegmentationLoss:
    return SegmentationLoss(
        loss_name=loss_name,
        dice_labels=resolve_target_labels(data_info, target_labels),
        class_weight=class_weight_tensor(data_info, class_weighting, device),
    )


def combined_model_catalog() -> dict[str, ModelCandidate]:
    catalog = {
        "nnunet_v2_plainconv_external": ModelCandidate(
            model_id="nnunet_v2_plainconv_external",
            display_name="nnU-Net v2 PlainConvUNet (external)",
            family="external_nnunet",
            rationale="External nnU-Net smoke/fullres training path; tracked in this catalog but not run by the lightweight PyTorch benchmark.",
            source_url="https://github.com/MIC-DKFZ/nnUNet",
            constructor=_external_constructor,
        )
    }
    catalog.update(monai_model_catalog())
    catalog.update(frontier_model_catalog())
    return catalog


def load_manifest_rows(spec: DatasetSpec) -> list[dict[str, Any]]:
    if not spec.manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest for {spec.dataset_key}: {spec.manifest_path}")
    with spec.manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    normalized: list[dict[str, Any]] = []
    for row in rows:
        cache_path = Path(row.get("cache_path") or row.get("input_path") or row.get("mask_path") or "")
        normalized.append({**row, "cache_path": str(cache_path)})
    return normalized


def dataset_smoke_summary(spec: DatasetSpec, *, limit: int = 2) -> dict[str, Any]:
    rows = load_manifest_rows(spec)
    inspected = []
    label_values: set[int] = set()
    shapes: set[tuple[int, ...]] = set()
    for row in rows[:limit]:
        cache_path = Path(row["cache_path"])
        if not cache_path.exists():
            raise FileNotFoundError(f"Missing NPZ cache: {cache_path}")
        with np.load(cache_path) as payload:
            missing = {"image", "label"} - set(payload.files)
            if missing:
                raise ValueError(f"{cache_path} missing required fields: {sorted(missing)}")
            image = payload["image"]
            label = payload["label"]
            shapes.add(tuple(image.shape))
            label_values.update(int(value) for value in np.unique(label))
            inspected.append(
                {
                    "case_id": row.get("case_id"),
                    "cache_path": str(cache_path),
                    "image_shape": list(image.shape),
                    "image_dtype": str(image.dtype),
                    "label_shape": list(label.shape),
                    "label_dtype": str(label.dtype),
                    "label_values": [int(value) for value in np.unique(label)],
                }
            )
    return {
        "dataset_key": spec.dataset_key,
        "dataset_id": spec.dataset_id,
        "task_group": spec.task_group,
        "case_count": len(rows),
        "train_count": sum(1 for row in rows if row.get("split") == "train"),
        "val_count": sum(1 for row in rows if row.get("split") == "val"),
        "inspected_count": len(inspected),
        "sample_shapes": [list(shape) for shape in sorted(shapes)],
        "sample_label_values": sorted(label_values),
        "samples": inspected,
        "manifest_path": str(spec.manifest_path),
    }


def infer_dataset_info(spec: DatasetSpec, rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_values: set[int] = set()
    shape: tuple[int, int, int] | None = None
    label_voxel_counts: dict[int, int] = {}
    label_case_counts: dict[int, int] = {}
    total_voxels = 0
    foreground_voxels = 0
    for row in rows:
        with np.load(row["cache_path"]) as payload:
            image = payload["image"]
            label = payload["label"]
            if shape is None:
                shape = tuple(int(item) for item in image.shape)
            values, counts = np.unique(label, return_counts=True)
            total_voxels += int(label.size)
            for value, count in zip(values.astype(int), counts.astype(int)):
                label_values.add(int(value))
                label_voxel_counts[int(value)] = label_voxel_counts.get(int(value), 0) + int(count)
                label_case_counts[int(value)] = label_case_counts.get(int(value), 0) + 1
                if int(value) > 0:
                    foreground_voxels += int(count)
    if shape is None:
        raise ValueError(f"No rows available for dataset {spec.dataset_key}")
    labels = sorted(value for value in label_values if value > 0)
    max_label = max(label_values) if label_values else 0
    label_counts_list = [int(label_voxel_counts.get(index, 0)) for index in range(int(max_label) + 1)]
    label_case_counts_list = [int(label_case_counts.get(index, 0)) for index in range(int(max_label) + 1)]
    return {
        "dataset_key": spec.dataset_key,
        "dataset_id": spec.dataset_id,
        "display_name": spec.display_name,
        "task_group": spec.task_group,
        "task_name": spec.task_name,
        "metric_profile": spec.metric_profile,
        "case_count": len(rows),
        "train_count": sum(1 for row in rows if row.get("split") == "train"),
        "val_count": sum(1 for row in rows if row.get("split") == "val"),
        "target_shape": list(shape),
        "label_values": sorted(label_values),
        "foreground_labels": labels,
        "n_classes": int(max_label) + 1,
        "label_voxel_counts": label_counts_list,
        "label_case_counts": label_case_counts_list,
        "total_voxels": total_voxels,
        "foreground_voxels": foreground_voxels,
        "foreground_voxel_fraction": safe_div(foreground_voxels, total_voxels) or 0.0,
        "manifest_path": str(spec.manifest_path),
        "medical_boundary": spec.medical_boundary,
    }


def train_and_evaluate_on_dataset(
    candidate: ModelCandidate,
    spec: DatasetSpec,
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    data_info: dict[str, Any],
    *,
    device: torch.device,
    max_train_batches: int,
    max_val_cases: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    loss_name: str,
    max_epochs: int,
    foreground_oversample_ratio: float,
    class_weighting: str,
    target_labels: str,
    overfit_cases: int,
) -> dict[str, Any]:
    if candidate.family == "external_nnunet":
        return skipped_external_result(candidate, spec, data_info)
    _set_seed(seed)
    torch.cuda.empty_cache() if device.type == "cuda" else None
    started = time.perf_counter()
    status = "completed"
    error = ""
    train_loss = math.nan
    peak_memory_mb: float | None = None
    parameter_count = 0
    completed_train_batches = 0
    epochs_seen = 0
    samples_seen = 0
    model: nn.Module | None = None
    metrics: dict[str, Any] = empty_metrics()
    resolved_loss_name = resolve_loss_name(loss_name, spec)
    train_rows_effective = train_rows[:overfit_cases] if overfit_cases > 0 else train_rows
    val_rows_effective = train_rows_effective if overfit_cases > 0 else val_rows[:max_val_cases]
    try:
        print(f"[start] {spec.dataset_key} :: {candidate.model_id}", flush=True)
        if not train_rows_effective:
            raise ValueError(f"No training rows for {spec.dataset_key}")
        target_shape = tuple(int(item) for item in data_info["target_shape"])
        model = candidate.constructor(target_shape, int(data_info["n_classes"])).to(device)
        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        loss_fn = build_segmentation_loss(
            loss_name=resolved_loss_name,
            data_info=data_info,
            target_labels=target_labels,
            class_weighting=class_weighting,
            device=device,
        )
        losses: list[float] = []
        model.train()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        while completed_train_batches < max_train_batches and epochs_seen < max_epochs:
            loader = build_training_loader(
                train_rows_effective,
                batch_size=batch_size,
                foreground_oversample_ratio=foreground_oversample_ratio,
                seed=seed,
                epoch_index=epochs_seen,
            )
            epochs_seen += 1
            for image, label in loader:
                if completed_train_batches >= max_train_batches:
                    break
                image = image.to(device, non_blocking=True)
                label = label.to(device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                logits = _primary_output(model(image))
                loss = loss_fn(logits, label)
                loss.backward()
                optimizer.step()
                completed_train_batches += 1
                samples_seen += int(image.shape[0])
                losses.append(float(loss.detach().cpu()))
        train_loss = float(np.mean(losses)) if losses else math.nan
        metrics = evaluate_model(
            model,
            val_rows_effective,
            labels=[int(item) for item in data_info["foreground_labels"]],
            metric_profile=spec.metric_profile,
            device=device,
        )
        if device.type == "cuda":
            peak_memory_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
        print(f"[done] {spec.dataset_key} :: {candidate.model_id}", flush=True)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            status = "failed_oom"
            error = str(exc)
            torch.cuda.empty_cache() if device.type == "cuda" else None
        else:
            status = "failed_runtime"
            error = str(exc)
    except Exception as exc:  # noqa: BLE001
        status = "failed_runtime"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    if model is not None:
        del model
    torch.cuda.empty_cache() if device.type == "cuda" else None
    return {
        "dataset_key": spec.dataset_key,
        "dataset_id": spec.dataset_id,
        "task_group": spec.task_group,
        "task_name": spec.task_name,
        "metric_profile": spec.metric_profile,
        "model_id": candidate.model_id,
        "display_name": candidate.display_name,
        "family": candidate.family,
        "status": status,
        "error": error,
        "parameter_count": parameter_count,
        "train_batches": completed_train_batches,
        "epochs_seen": epochs_seen,
        "samples_seen": samples_seen,
        "val_cases": int(metrics.get("case_count", 0)),
        "n_classes": data_info["n_classes"],
        "loss_name": resolved_loss_name,
        "class_weighting": class_weighting,
        "foreground_oversample_ratio": foreground_oversample_ratio,
        "overfit_cases": overfit_cases,
        "target_labels": target_labels,
        "train_loss": train_loss,
        "foreground_voxel_fraction": data_info.get("foreground_voxel_fraction"),
        "prediction_positive_fraction": metrics.get("prediction_positive_fraction"),
        "target_positive_fraction": metrics.get("target_positive_fraction"),
        "foreground_mean_dice": metrics.get("foreground_mean_dice"),
        "foreground_mean_iou": metrics.get("foreground_mean_iou"),
        "lesion_sensitivity": metrics.get("lesion_sensitivity"),
        "lesion_precision": metrics.get("lesion_precision"),
        "case_detection_sensitivity": metrics.get("case_detection_sensitivity"),
        "false_positive_case_rate": metrics.get("false_positive_case_rate"),
        "lesion_false_positive_voxels": metrics.get("lesion_false_positive_voxels"),
        "lesion_false_negative_voxels": metrics.get("lesion_false_negative_voxels"),
        "per_label": metrics.get("per_label", {}),
        "elapsed_seconds": elapsed,
        "peak_memory_mb": peak_memory_mb,
        "rationale": candidate.rationale,
        "source_url": candidate.source_url,
    }


def evaluate_model(
    model: nn.Module,
    rows: list[dict[str, Any]],
    *,
    labels: list[int],
    metric_profile: str,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    per_label_scores: dict[int, list[dict[str, Any]]] = {label: [] for label in labels}
    lesion_accumulator = {
        "tp": 0.0,
        "fp": 0.0,
        "fn": 0.0,
        "target_positive_cases": 0,
        "prediction_positive_cases": 0,
        "detected_positive_cases": 0,
        "target_negative_cases": 0,
        "false_positive_cases": 0,
    }
    total_voxels = 0
    prediction_positive_voxels = 0
    target_positive_voxels = 0
    with torch.no_grad():
        for row in rows:
            with np.load(row["cache_path"]) as payload:
                image = torch.from_numpy(payload["image"].astype(np.float32, copy=False)[None, None]).to(device)
                target = payload["label"].astype(np.int16, copy=False)
            logits = _primary_output(model(image))
            prediction = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy().astype(np.int16)
            total_voxels += int(target.size)
            prediction_positive_voxels += int((prediction > 0).sum())
            target_positive_voxels += int((target > 0).sum())
            for label in labels:
                score = binary_dice_iou(prediction == label, target == label)
                per_label_scores[label].append(score)
            if metric_profile == "lesion":
                update_lesion_accumulator(lesion_accumulator, prediction > 0, target > 0)
    per_label = {
        str(label): {
            "name": label_name(label),
            "dice": nanmean([score["dice"] for score in scores]),
            "iou": nanmean([score["iou"] for score in scores]),
            "present_target_cases": int(sum(1 for score in scores if score["target_present"])),
            "present_prediction_cases": int(sum(1 for score in scores if score["prediction_present"])),
        }
        for label, scores in per_label_scores.items()
    }
    valid_label_items = [item for item in per_label.values() if item["present_target_cases"] > 0]
    result: dict[str, Any] = {
        "case_count": len(rows),
        "prediction_positive_fraction": safe_div(prediction_positive_voxels, total_voxels),
        "target_positive_fraction": safe_div(target_positive_voxels, total_voxels),
        "foreground_mean_dice": nanmean([item["dice"] for item in valid_label_items]),
        "foreground_mean_iou": nanmean([item["iou"] for item in valid_label_items]),
        "per_label": per_label,
    }
    if metric_profile == "lesion":
        result.update(lesion_metrics_from_accumulator(lesion_accumulator))
    return result


def update_lesion_accumulator(accumulator: dict[str, float | int], prediction: np.ndarray, target: np.ndarray) -> None:
    pred_bool = np.asarray(prediction).astype(bool)
    target_bool = np.asarray(target).astype(bool)
    tp = float(np.logical_and(pred_bool, target_bool).sum())
    fp = float(np.logical_and(pred_bool, ~target_bool).sum())
    fn = float(np.logical_and(~pred_bool, target_bool).sum())
    accumulator["tp"] = float(accumulator["tp"]) + tp
    accumulator["fp"] = float(accumulator["fp"]) + fp
    accumulator["fn"] = float(accumulator["fn"]) + fn
    target_present = bool(target_bool.any())
    pred_present = bool(pred_bool.any())
    if target_present:
        accumulator["target_positive_cases"] = int(accumulator["target_positive_cases"]) + 1
        if pred_present:
            accumulator["detected_positive_cases"] = int(accumulator["detected_positive_cases"]) + 1
    else:
        accumulator["target_negative_cases"] = int(accumulator["target_negative_cases"]) + 1
        if pred_present:
            accumulator["false_positive_cases"] = int(accumulator["false_positive_cases"]) + 1
    if pred_present:
        accumulator["prediction_positive_cases"] = int(accumulator["prediction_positive_cases"]) + 1


def lesion_metrics_from_accumulator(accumulator: dict[str, float | int]) -> dict[str, Any]:
    tp = float(accumulator["tp"])
    fp = float(accumulator["fp"])
    fn = float(accumulator["fn"])
    target_positive_cases = int(accumulator["target_positive_cases"])
    target_negative_cases = int(accumulator["target_negative_cases"])
    return {
        "lesion_sensitivity": safe_div(tp, tp + fn),
        "lesion_precision": safe_div(tp, tp + fp),
        "lesion_false_positive_voxels": fp,
        "lesion_false_negative_voxels": fn,
        "case_detection_sensitivity": safe_div(int(accumulator["detected_positive_cases"]), target_positive_cases),
        "false_positive_case_rate": safe_div(int(accumulator["false_positive_cases"]), target_negative_cases),
        "target_positive_cases": target_positive_cases,
        "prediction_positive_cases": int(accumulator["prediction_positive_cases"]),
    }


def binary_dice_iou(pred: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    pred_bool = np.asarray(pred).astype(bool)
    target_bool = np.asarray(target).astype(bool)
    pred_area = float(pred_bool.sum())
    target_area = float(target_bool.sum())
    intersection = float(np.logical_and(pred_bool, target_bool).sum())
    union = float(np.logical_or(pred_bool, target_bool).sum())
    if pred_area == 0 and target_area == 0:
        dice = None
        iou = None
    elif pred_area + target_area == 0:
        dice = 0.0
        iou = 0.0
    else:
        dice = 2.0 * intersection / (pred_area + target_area)
        iou = 0.0 if union == 0 else intersection / union
    return {
        "dice": None if dice is None else float(dice),
        "iou": None if iou is None else float(iou),
        "target_present": bool(target_area > 0),
        "prediction_present": bool(pred_area > 0),
    }


def run_forward_backward_smoke(candidate: ModelCandidate, spec: DatasetSpec, rows: list[dict[str, Any]], data_info: dict[str, Any]) -> dict[str, Any]:
    if candidate.family == "external_nnunet":
        return {"model_id": candidate.model_id, "dataset_key": spec.dataset_key, "status": "skipped_external"}
    if not rows:
        return {"model_id": candidate.model_id, "dataset_key": spec.dataset_key, "status": "failed_runtime", "error": "no training rows"}
    _set_seed(DEFAULT_SEED)
    target_shape = tuple(int(item) for item in data_info["target_shape"])
    model = candidate.constructor(target_shape, int(data_info["n_classes"]))
    loader = DataLoader(ManifestNpzDataset(rows[:2]), batch_size=min(2, len(rows)), shuffle=False, num_workers=0)
    image, label = next(iter(loader))
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    logits = _primary_output(model(image))
    loss = nn.CrossEntropyLoss()(logits, label)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()
    return {
        "model_id": candidate.model_id,
        "dataset_key": spec.dataset_key,
        "status": "completed",
        "loss": float(loss.detach().cpu()),
        "output_shape": list(logits.shape),
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    catalog = combined_model_catalog()
    selected_ids = parse_model_ids(args.models)
    selected = [catalog[model_id] for model_id in selected_ids]
    specs = selected_dataset_specs(args.task)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = ensure_dir(Path(args.output_dir) / run_id)
    device = torch.device(args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu"))
    smoke: list[dict[str, Any]] = []
    dataset_infos: dict[str, dict[str, Any]] = {}
    dataset_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for spec in specs:
        smoke.append(dataset_smoke_summary(spec, limit=2))
        rows = load_manifest_rows(spec)
        train_rows = [row for row in rows if row.get("split") == "train"]
        val_rows = [row for row in rows if row.get("split") == "val"]
        info = infer_dataset_info(spec, rows)
        dataset_infos[spec.dataset_key] = info
        dataset_rows[spec.dataset_key] = {"train": train_rows, "val": val_rows}
        if args.forward_backward_smoke:
            for candidate in selected:
                smoke.append(run_forward_backward_smoke(candidate, spec, train_rows, info))
    results: list[dict[str, Any]] = []
    if not args.smoke_only:
        for spec in specs:
            info = dataset_infos[spec.dataset_key]
            rows = dataset_rows[spec.dataset_key]
            for candidate in selected:
                results.append(
                    train_and_evaluate_on_dataset(
                        candidate,
                        spec,
                        rows["train"],
                        rows["val"],
                        info,
                        device=device,
                        max_train_batches=args.max_train_batches,
                        max_val_cases=args.max_val_cases,
                        batch_size=args.batch_size,
                        learning_rate=args.learning_rate,
                        seed=args.seed,
                        loss_name=args.loss,
                        max_epochs=args.max_epochs,
                        foreground_oversample_ratio=args.foreground_oversample_ratio,
                        class_weighting=args.class_weighting,
                        target_labels=args.target_labels,
                        overfit_cases=args.overfit_cases,
                    )
                )
    summary_json = output_dir / "public_cbct_3dataset_segmentation_benchmark_summary.json"
    results_csv = output_dir / "public_cbct_3dataset_segmentation_benchmark_results.csv"
    write_results_csv(results_csv, results)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "task": args.task,
        "data": dataset_infos,
        "smoke": smoke,
        "config": {
            "models": selected_ids,
            "catalog_model_count": len(catalog),
            "max_train_batches": args.max_train_batches,
            "max_val_cases": args.max_val_cases,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "seed": args.seed,
            "loss": args.loss,
            "max_epochs": args.max_epochs,
            "foreground_oversample_ratio": args.foreground_oversample_ratio,
            "class_weighting": args.class_weighting,
            "target_labels": args.target_labels,
            "overfit_cases": args.overfit_cases,
            "smoke_only": args.smoke_only,
        },
        "environment": {
            "device": str(device),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "model_catalog": [model_catalog_row(candidate) for candidate in catalog.values()],
        "results": results,
        "rankings": build_rankings(results),
        "paths": {
            "output_dir": str(output_dir),
            "summary_json": str(summary_json),
            "results_csv": str(results_csv),
        },
    }
    payload["paths"].update(write_summary_reports(payload, Path(args.report_dir)))
    write_json(summary_json, payload)
    return payload


def build_rankings(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_dataset: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        by_dataset.setdefault(str(row["dataset_key"]), []).append(row)
    dataset_rankings = {
        dataset_key: sorted(rows, key=lambda item: metric_sort_value(item.get("foreground_mean_dice")), reverse=True)
        for dataset_key, rows in by_dataset.items()
    }
    anatomy_rows = [row for row in results if row.get("task_group") == "anatomy_roi" and row.get("foreground_mean_dice") is not None]
    anatomy_by_model: dict[str, list[float]] = {}
    for row in anatomy_rows:
        anatomy_by_model.setdefault(str(row["model_id"]), []).append(float(row["foreground_mean_dice"]))
    anatomy_aggregate = sorted(
        [
            {
                "model_id": model_id,
                "mean_anatomy_dice": float(np.mean(scores)),
                "dataset_count": len(scores),
            }
            for model_id, scores in anatomy_by_model.items()
        ],
        key=lambda item: item["mean_anatomy_dice"],
        reverse=True,
    )
    lesion = sorted(
        [row for row in results if row.get("task_group") == "lesion_roi"],
        key=lambda item: (metric_sort_value(item.get("foreground_mean_dice")), metric_sort_value(item.get("lesion_sensitivity"))),
        reverse=True,
    )
    return {"by_dataset": dataset_rankings, "anatomy_aggregate": anatomy_aggregate, "lesion": lesion}


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    return write_csv(
        path,
        rows,
        [
            "dataset_key",
            "dataset_id",
            "task_group",
            "task_name",
            "model_id",
            "display_name",
            "family",
            "status",
            "n_classes",
            "parameter_count",
            "train_batches",
            "epochs_seen",
            "samples_seen",
            "val_cases",
            "loss_name",
            "class_weighting",
            "foreground_oversample_ratio",
            "overfit_cases",
            "target_labels",
            "train_loss",
            "foreground_voxel_fraction",
            "prediction_positive_fraction",
            "target_positive_fraction",
            "foreground_mean_dice",
            "foreground_mean_iou",
            "lesion_sensitivity",
            "lesion_precision",
            "case_detection_sensitivity",
            "false_positive_case_rate",
            "lesion_false_positive_voxels",
            "lesion_false_negative_voxels",
            "elapsed_seconds",
            "peak_memory_mb",
            "source_url",
            "error",
        ],
    )


def write_summary_reports(payload: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh_path = report_dir / "public_cbct_3dataset_segmentation_benchmark_zh.md"
    en_path = report_dir / "public_cbct_3dataset_segmentation_benchmark_en.md"
    payload["paths"]["zh_report"] = str(zh_path)
    payload["paths"]["en_report"] = str(en_path)
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    if language == "zh":
        lines = [
            "# 公开 CBCT 三数据集分割模型复测报告（中文）",
            "",
            "## 定位",
            "",
            "本报告使用项目本地 64³ NPZ 缓存，对 D024、D025、D036 三个公开 CBCT 数据集进行轻量分割模型复测。结果用于模型筛选和工程可行性判断，不代表正式高分辨率训练性能。",
            "",
            "## 数据与设置",
            "",
        ]
        for info in payload["data"].values():
            lines.append(
                f"- {info['display_name']}：{info['case_count']} 例，训练 {info['train_count']}，验证 {info['val_count']}，类别数 {info['n_classes']}。"
            )
        lines.extend(
            [
                f"- 模型数：登记 {payload['config']['catalog_model_count']} 个；本轮运行 {len(payload['config']['models'])} 个。",
                f"- 训练批次：{payload['config']['max_train_batches']}；验证病例：{payload['config']['max_val_cases']}；batch size：{payload['config']['batch_size']}。",
                f"- Loss：{payload['config']['loss']}；类别权重：{payload['config']['class_weighting']}；前景重采样比例：{payload['config']['foreground_oversample_ratio']}；overfit 病例数：{payload['config']['overfit_cases']}。",
                f"- 设备：{payload['environment']['device']}；GPU：{payload['environment'].get('cuda_device_name')}；PyTorch：{payload['environment']['torch_version']}。",
                "",
                "## 结果汇总",
                "",
                "| Dataset | Model | Status | Dice | IoU | Lesion Sens. | Lesion Prec. | Params | Loss | Time(s) | GPU MB |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
    else:
        lines = [
            "# Public CBCT Three-Dataset Segmentation Benchmark",
            "",
            "## Scope",
            "",
            "This report reruns lightweight segmentation candidates on local 64³ NPZ caches for D024, D025, and D036. The results are for model selection and engineering feasibility only, not formal high-resolution performance.",
            "",
            "## Data and Setup",
            "",
        ]
        for info in payload["data"].values():
            lines.append(
                f"- {info['display_name']}: {info['case_count']} cases, {info['train_count']} train, {info['val_count']} validation, {info['n_classes']} classes."
            )
        lines.extend(
            [
                f"- Catalog size: {payload['config']['catalog_model_count']} registered models; {len(payload['config']['models'])} models run in this round.",
                f"- Training batches: {payload['config']['max_train_batches']}; validation cases: {payload['config']['max_val_cases']}; batch size: {payload['config']['batch_size']}.",
                f"- Loss: {payload['config']['loss']}; class weighting: {payload['config']['class_weighting']}; foreground oversampling ratio: {payload['config']['foreground_oversample_ratio']}; overfit cases: {payload['config']['overfit_cases']}.",
                f"- Device: {payload['environment']['device']}; GPU: {payload['environment'].get('cuda_device_name')}; PyTorch: {payload['environment']['torch_version']}.",
                "",
                "## Results",
                "",
                "| Dataset | Model | Status | Dice | IoU | Lesion Sens. | Lesion Prec. | Params | Loss | Time(s) | GPU MB |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
    for row in sorted(payload["results"], key=lambda item: (str(item.get("dataset_key")), -metric_sort_value(item.get("foreground_mean_dice")))):
        lines.append(result_table_row(row))
    if language == "zh":
        lines.extend(["", "## 解剖结构综合排名", ""])
        for rank, row in enumerate(payload["rankings"]["anatomy_aggregate"], start=1):
            lines.append(f"{rank}. `{row['model_id']}`：D024+D036 mean Dice = {_fmt(row['mean_anatomy_dice'])}。")
        lines.extend(["", "## 病灶分割排名", ""])
        for rank, row in enumerate(payload["rankings"]["lesion"], start=1):
            lines.append(
                f"{rank}. `{row['model_id']}`：Dice = {_fmt(row.get('foreground_mean_dice'))}，Sensitivity = {_fmt(row.get('lesion_sensitivity'))}。"
            )
        lines.extend(
            [
                "",
                "## 产物",
                "",
                f"- 结果 JSON：`{payload['paths']['summary_json']}`",
                f"- 结果 CSV：`{payload['paths']['results_csv']}`",
                f"- 英文报告：`{payload['paths']['en_report']}`",
                "",
                "## 医学边界",
                "",
                "D024 和 D036 仅用于解剖结构分割；D025 是 CBCT lesion-mask 代理任务。三者都不是术中 ICG 荧光数据，本轮结果不能作为颌骨骨髓炎临床诊断性能。",
            ]
        )
    else:
        lines.extend(["", "## Anatomy Aggregate Ranking", ""])
        for rank, row in enumerate(payload["rankings"]["anatomy_aggregate"], start=1):
            lines.append(f"{rank}. `{row['model_id']}`: D024+D036 mean Dice = {_fmt(row['mean_anatomy_dice'])}.")
        lines.extend(["", "## Lesion Ranking", ""])
        for rank, row in enumerate(payload["rankings"]["lesion"], start=1):
            lines.append(
                f"{rank}. `{row['model_id']}`: Dice = {_fmt(row.get('foreground_mean_dice'))}, Sensitivity = {_fmt(row.get('lesion_sensitivity'))}."
            )
        lines.extend(
            [
                "",
                "## Artifacts",
                "",
                f"- Result JSON: `{payload['paths']['summary_json']}`",
                f"- Result CSV: `{payload['paths']['results_csv']}`",
                f"- Chinese report: `{payload['paths']['zh_report']}`",
                "",
                "## Medical Boundary",
                "",
                "D024 and D036 are anatomical segmentation sources; D025 is a CBCT lesion-mask proxy. None is intraoperative ICG fluorescence data, so this benchmark must not be presented as clinical jaw-osteomyelitis diagnostic performance.",
            ]
        )
    return "\n".join(lines) + "\n"


def result_table_row(row: dict[str, Any]) -> str:
    return (
        f"| {row['dataset_key']} | {row['display_name']} | {row['status']} | {_fmt(row.get('foreground_mean_dice'))} | "
        f"{_fmt(row.get('foreground_mean_iou'))} | {_fmt(row.get('lesion_sensitivity'))} | {_fmt(row.get('lesion_precision'))} | "
        f"{int(row.get('parameter_count') or 0):,} | {_fmt(row.get('train_loss'))} | {_fmt(row.get('elapsed_seconds'))} | {_fmt(row.get('peak_memory_mb'))} |"
    )


def selected_dataset_specs(task: str) -> list[DatasetSpec]:
    if task == "anatomy_roi":
        return [DATASETS["d024_jaw_roi"], DATASETS["d036_anatomy_roi"]]
    if task == "lesion_roi":
        return [DATASETS["d025_lesion_roi"]]
    return [DATASETS["d024_jaw_roi"], DATASETS["d036_anatomy_roi"], DATASETS["d025_lesion_roi"]]


def parse_model_ids(models: str) -> list[str]:
    catalog = combined_model_catalog()
    if models.strip().lower() == "all":
        selected = list(catalog)
    else:
        selected = [item.strip() for item in models.split(",") if item.strip()] if models else list(DEFAULT_TOP_MODELS)
    unknown = [model_id for model_id in selected if model_id not in catalog]
    if unknown:
        raise KeyError(f"Unknown model ids: {unknown}. Available: {sorted(catalog)}")
    return selected


def model_catalog_row(candidate: ModelCandidate) -> dict[str, str]:
    return {
        "model_id": candidate.model_id,
        "display_name": candidate.display_name,
        "family": candidate.family,
        "rationale": candidate.rationale,
        "source_url": candidate.source_url,
    }


def skipped_external_result(candidate: ModelCandidate, spec: DatasetSpec, data_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_key": spec.dataset_key,
        "dataset_id": spec.dataset_id,
        "task_group": spec.task_group,
        "task_name": spec.task_name,
        "metric_profile": spec.metric_profile,
        "model_id": candidate.model_id,
        "display_name": candidate.display_name,
        "family": candidate.family,
        "status": "skipped_external",
        "error": "nnU-Net is tracked as an external baseline and must be run through the nnU-Net CLI path.",
        "parameter_count": 0,
        "train_batches": 0,
        "epochs_seen": 0,
        "samples_seen": 0,
        "val_cases": 0,
        "n_classes": data_info["n_classes"],
        "loss_name": None,
        "class_weighting": None,
        "foreground_oversample_ratio": None,
        "overfit_cases": 0,
        "target_labels": None,
        "train_loss": None,
        "foreground_voxel_fraction": data_info.get("foreground_voxel_fraction"),
        "prediction_positive_fraction": None,
        "target_positive_fraction": None,
        "foreground_mean_dice": None,
        "foreground_mean_iou": None,
        "lesion_sensitivity": None,
        "lesion_precision": None,
        "case_detection_sensitivity": None,
        "false_positive_case_rate": None,
        "lesion_false_positive_voxels": None,
        "lesion_false_negative_voxels": None,
        "per_label": {},
        "elapsed_seconds": 0.0,
        "peak_memory_mb": None,
        "rationale": candidate.rationale,
        "source_url": candidate.source_url,
    }


def empty_metrics() -> dict[str, Any]:
    return {"case_count": 0, "foreground_mean_dice": None, "foreground_mean_iou": None, "per_label": {}}


def nanmean(values: Iterable[float | None]) -> float | None:
    numbers = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not numbers:
        return None
    return float(np.mean(numbers))


def safe_div(numerator: float | int, denominator: float | int) -> float | None:
    denominator_float = float(denominator)
    if denominator_float == 0:
        return None
    return float(numerator) / denominator_float


def metric_sort_value(value: Any) -> float:
    try:
        if value is None:
            return -1.0
        number = float(value)
        return -1.0 if math.isnan(number) else number
    except (TypeError, ValueError):
        return -1.0


def label_name(label: int) -> str:
    names = {
        1: "label_1_or_lesion",
        2: "label_2",
        3: "label_3",
        4: "label_4",
        5: "label_5",
        6: "label_6",
    }
    return names.get(label, f"label_{label}")


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


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _external_constructor(shape: tuple[int, int, int], n_classes: int) -> nn.Module:
    raise RuntimeError("nnU-Net external baseline must be run through the nnU-Net CLI path.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark public CBCT segmentation models on D024, D025, and D036 local caches.")
    parser.add_argument("--task", default="all", choices=["anatomy_roi", "lesion_roi", "all"])
    parser.add_argument("--models", default=",".join(DEFAULT_TOP_MODELS))
    parser.add_argument("--max-train-batches", type=int, default=80)
    parser.add_argument("--max-epochs", type=int, default=100)
    parser.add_argument("--max-val-cases", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--loss", default="auto", choices=LOSS_CHOICES)
    parser.add_argument("--foreground-oversample-ratio", type=float, default=0.0)
    parser.add_argument("--class-weighting", default="sqrt_inverse", choices=CLASS_WEIGHTING_CHOICES)
    parser.add_argument("--overfit-cases", type=int, default=0)
    parser.add_argument("--target-labels", default="foreground", choices=TARGET_LABEL_CHOICES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--forward-backward-smoke", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_models:
        print(json.dumps([model_catalog_row(candidate) for candidate in combined_model_catalog().values()], ensure_ascii=False, indent=2))
        return 0
    payload = run_benchmark(args)
    print(json.dumps({"run_id": payload["run_id"], "paths": payload["paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
