from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from scripts.train_keyframe_segmentation_proxy import (
    ManifestKeyframeDataset,
    binary_dice_iou,
    load_manifest_rows,
)
from src.core.paths import ensure_dir, resolve_path
from src.datasets.group_splits import assert_no_group_leakage
from src.metrics.calibration import binary_brier_score, expected_calibration_error
from src.models.keyframe_segmenter import (
    checkpoint_sha256,
    load_keyframe_segmenter_checkpoint,
    select_torch_device,
)
from src.reports.writers import write_json

DEFAULT_CHECKPOINT = "artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy.pt"
DEFAULT_MANIFEST = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/"
    "derived/mp4_keyframe_segmentation_proxy_20260705/keyframe_segmentation_proxy_manifest.csv"
)
DEFAULT_OUTPUT_DIR = "research/reports/modeling/keyframe_threshold_eval_20260705"
DEFAULT_THRESHOLDS = "0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60"


def evaluate_keyframe_thresholds(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    device = select_torch_device(args.device)
    image_shape = parse_shape(args.image_shape)
    thresholds = parse_thresholds(args.thresholds)
    rows, manifest_summary = load_eval_rows(args.manifest, split=args.split, max_samples=args.max_samples)
    model, checkpoint_metadata = load_keyframe_segmenter_checkpoint(resolve_path(args.checkpoint), device=device)
    temperature = float((checkpoint_metadata.get("calibration") or {}).get("temperature") or 1.0)
    samples = collect_probabilities(
        model,
        rows,
        image_shape=image_shape,
        device=device,
        temperature=temperature,
    )
    inference_benchmark = summarize_inference_benchmark(samples, model=model, device=device)
    threshold_rows = [
        threshold_metrics(
            samples,
            threshold=threshold,
            over_segmentation_fraction=float(args.over_segmentation_fraction),
        )
        for threshold in thresholds
    ]
    target_stats = numeric_stats([sample["target_positive_fraction"] for sample in samples])
    recommendation = select_recommended_threshold(
        threshold_rows,
        target_positive_fraction_stats=target_stats,
        max_empty_mask_rate=float(args.max_empty_mask_rate),
        max_over_segmentation_rate=float(args.max_over_segmentation_rate),
    )
    output_dir = ensure_dir(resolve_path(args.output_dir))
    csv_path = output_dir / "keyframe_threshold_eval.csv"
    json_path = output_dir / "keyframe_threshold_eval.json"
    zh_path = output_dir / "keyframe_threshold_eval_zh.md"
    en_path = output_dir / "keyframe_threshold_eval_en.md"
    write_threshold_csv(csv_path, threshold_rows, recommended_threshold=recommendation["threshold"])
    payload = {
        "schema_version": "osteo-vision-keyframe-threshold-eval-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "checkpoint_path": str(resolve_path(args.checkpoint)),
        "checkpoint_sha256": checkpoint_sha256(resolve_path(args.checkpoint)),
        "checkpoint_metadata": {
            "model_id": checkpoint_metadata.get("model_id"),
            "model_family": checkpoint_metadata.get("model_family"),
            "checkpoint_metric_threshold": checkpoint_metadata.get("threshold"),
            "checkpoint_metrics": checkpoint_metadata.get("metrics") or {},
            "training": checkpoint_metadata.get("training") or {},
        },
        "manifest_paths": manifest_summary["manifest_paths"],
        "source_group_split": manifest_summary["source_group_split"],
        "split": args.split,
        "image_shape": [int(image_shape[0]), int(image_shape[1])],
        "sample_count": len(samples),
        "target_positive_fraction_stats": target_stats,
        "calibration": calibration_summary(samples),
        "inference_benchmark": inference_benchmark,
        "thresholds": threshold_rows,
        "recommendation": recommendation,
        "outputs": {
            "json": str(json_path),
            "csv": str(csv_path),
            "zh_report": str(zh_path),
            "en_report": str(en_path),
        },
        "elapsed_seconds": round(float(time.perf_counter() - started), 3),
        "environment": {
            "device": str(device),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
        "medical_boundary": (
            "Threshold metrics are computed against pseudo masks from public/proxy keyframes only. "
            "Clinical performance on intraoperative ICG jaw osteomyelitis remains unmeasured."
        ),
    }
    write_json(json_path, payload)
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def load_eval_rows(
    manifest_paths: Iterable[str], *, split: str, max_samples: int
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    paths = [str(item) for item in manifest_paths if str(item).strip()]
    if not paths:
        raise ValueError("At least one --manifest path is required.")
    rows: list[dict[str, str]] = []
    for manifest in paths:
        rows.extend(load_manifest_rows(manifest))
    leakage_report = assert_no_group_leakage(rows, context="keyframe evaluation manifests")
    if split != "all":
        rows = [row for row in rows if row.get("split") == split]
    if max_samples > 0:
        rows = rows[:max_samples]
    if not rows:
        raise ValueError(f"No rows found for split={split!r} in manifests: {paths}")
    return rows, {
        "manifest_paths": [str(resolve_path(path)) for path in paths],
        "row_count": len(rows),
        "source_group_split": leakage_report,
    }


def collect_probabilities(
    model: nn.Module,
    rows: list[dict[str, str]],
    *,
    image_shape: tuple[int, int],
    device: torch.device,
    temperature: float = 1.0,
) -> list[dict[str, Any]]:
    dataset = ManifestKeyframeDataset(rows, image_shape=image_shape)
    samples: list[dict[str, Any]] = []
    model.eval()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    with torch.no_grad():
        for index, (image, target, _sample_weight) in enumerate(DataLoader(dataset, batch_size=1, shuffle=False)):
            image = image.to(device=device, dtype=torch.float32)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            inference_started = time.perf_counter()
            logits = model(image)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            inference_ms = (time.perf_counter() - inference_started) * 1000.0
            probability = (
                torch.softmax(logits / max(1e-3, float(temperature)), dim=1)[0, 1]
                .detach()
                .cpu()
                .numpy()
                .astype(np.float32)
            )
            target_np = target.numpy()[0] > 0
            samples.append(
                {
                    "case_id": rows[index].get("case_id") or f"sample_{index:04d}",
                    "probability": probability,
                    "target": target_np,
                    "target_positive_fraction": float(target_np.mean()),
                    "inference_ms": float(inference_ms),
                    "source_group_id": rows[index].get("source_group_id")
                    or rows[index].get("source_video_path")
                    or rows[index].get("source_path")
                    or rows[index].get("case_id"),
                }
            )
    return samples


def summarize_inference_benchmark(
    samples: list[dict[str, Any]],
    *,
    model: nn.Module,
    device: torch.device,
) -> dict[str, Any]:
    all_latencies = [float(sample["inference_ms"]) for sample in samples]
    measured_latencies = all_latencies[1:] if len(all_latencies) > 1 else all_latencies
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    parameter_bytes = sum(parameter.numel() * parameter.element_size() for parameter in model.parameters())
    return {
        "warmup_samples_excluded": 1 if len(all_latencies) > 1 else 0,
        "measured_sample_count": len(measured_latencies),
        "mean_latency_ms": mean_or_none(measured_latencies),
        "median_latency_ms": percentile_or_none(measured_latencies, 50),
        "p95_latency_ms": percentile_or_none(measured_latencies, 95),
        "throughput_fps": (
            float(1000.0 / np.mean(measured_latencies))
            if measured_latencies and float(np.mean(measured_latencies)) > 0.0
            else None
        ),
        "peak_gpu_memory_mb": (
            float(torch.cuda.max_memory_allocated(device) / (1024**2)) if device.type == "cuda" else None
        ),
        "parameter_count": int(parameter_count),
        "parameter_memory_mb": float(parameter_bytes / (1024**2)),
        "input_batch_size": 1,
        "device": str(device),
    }


def threshold_metrics(
    samples: list[dict[str, Any]],
    *,
    threshold: float,
    over_segmentation_fraction: float,
) -> dict[str, Any]:
    dice_scores: list[float] = []
    iou_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    boundary_scores: list[float] = []
    positive_fractions: list[float] = []
    empty_count = 0
    over_count = 0
    for sample in samples:
        probability = cast(np.ndarray, sample["probability"])
        target = cast(np.ndarray, sample["target"])
        prediction = probability >= float(threshold)
        dice, iou = binary_dice_iou(prediction, target)
        precision, recall = binary_precision_recall(prediction, target)
        boundary_scores.append(boundary_f1(prediction, target))
        positive_fraction = float(prediction.mean()) if prediction.size else 0.0
        dice_scores.append(dice)
        iou_scores.append(iou)
        precision_scores.append(precision)
        recall_scores.append(recall)
        positive_fractions.append(positive_fraction)
        if positive_fraction <= 0.0:
            empty_count += 1
        if positive_fraction > over_segmentation_fraction:
            over_count += 1
    group_intervals = video_group_bootstrap(samples, threshold=float(threshold))
    calibration = calibration_summary(samples)
    return {
        "threshold": round(float(threshold), 6),
        "case_count": len(samples),
        "foreground_mean_dice": mean_or_none(dice_scores),
        "foreground_mean_iou": mean_or_none(iou_scores),
        "foreground_precision_mean": mean_or_none(precision_scores),
        "foreground_recall_mean": mean_or_none(recall_scores),
        "boundary_f1_mean": mean_or_none(boundary_scores),
        "prediction_positive_fraction_mean": mean_or_none(positive_fractions),
        "prediction_positive_fraction_median": percentile_or_none(positive_fractions, 50),
        "prediction_positive_fraction_p25": percentile_or_none(positive_fractions, 25),
        "prediction_positive_fraction_p75": percentile_or_none(positive_fractions, 75),
        "empty_mask_count": empty_count,
        "empty_mask_rate": float(empty_count / len(samples)) if samples else None,
        "over_segmentation_count": over_count,
        "over_segmentation_rate": float(over_count / len(samples)) if samples else None,
        "over_segmentation_fraction": float(over_segmentation_fraction),
        "video_group_bootstrap": group_intervals,
        "ece": calibration["ece"],
        "brier_score": calibration["brier_score"],
    }


def binary_precision_recall(prediction: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    pred = np.asarray(prediction, dtype=bool)
    true = np.asarray(target, dtype=bool)
    true_positive = float(np.logical_and(pred, true).sum())
    false_positive = float(np.logical_and(pred, np.logical_not(true)).sum())
    false_negative = float(np.logical_and(np.logical_not(pred), true).sum())
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = (
        1.0
        if precision_denominator == 0.0 and recall_denominator == 0.0
        else (true_positive / max(1.0, precision_denominator))
    )
    recall = 1.0 if recall_denominator == 0.0 else true_positive / recall_denominator
    return float(precision), float(recall)


def boundary_f1(prediction: np.ndarray, target: np.ndarray, *, tolerance_px: int = 2) -> float:
    pred = np.asarray(prediction, dtype=np.uint8)
    true = np.asarray(target, dtype=np.uint8)
    if pred.shape != true.shape:
        raise ValueError("prediction and target must have identical shapes")
    pred_boundary: np.ndarray
    true_boundary: np.ndarray
    pred_dilated: np.ndarray
    true_dilated: np.ndarray
    try:
        import cv2

        kernel = np.ones((3, 3), dtype=np.uint8)
        pred_boundary = pred - cv2.erode(pred, kernel, iterations=1)
        true_boundary = true - cv2.erode(true, kernel, iterations=1)
        tolerance_kernel = np.ones((2 * tolerance_px + 1, 2 * tolerance_px + 1), dtype=np.uint8)
        pred_dilated = cv2.dilate(pred_boundary, tolerance_kernel, iterations=1)
        true_dilated = cv2.dilate(true_boundary, tolerance_kernel, iterations=1)
    except Exception:
        pred_boundary = pred
        true_boundary = true
        pred_dilated = pred
        true_dilated = true
    pred_count = int(pred_boundary.sum())
    true_count = int(true_boundary.sum())
    if pred_count == 0 and true_count == 0:
        return 1.0
    precision = float(np.logical_and(pred_boundary > 0, true_dilated > 0).sum()) / max(1, pred_count)
    recall = float(np.logical_and(true_boundary > 0, pred_dilated > 0).sum()) / max(1, true_count)
    return float(2.0 * precision * recall / max(1e-8, precision + recall))


def calibration_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"available": False, "reason": "no_samples"}
    targets = np.concatenate([cast(np.ndarray, item["target"]).reshape(-1) for item in samples]).astype(np.float32)
    probabilities = np.concatenate([cast(np.ndarray, item["probability"]).reshape(-1) for item in samples])
    ece = expected_calibration_error(targets, probabilities)
    return {
        "available": True,
        "ece": ece["ece"],
        "brier_score": binary_brier_score(targets, probabilities),
        "reliability_bins": ece["bins"],
    }


def video_group_bootstrap(
    samples: list[dict[str, Any]],
    *,
    threshold: float,
    iterations: int = 1000,
    seed: int = 20260710,
) -> dict[str, Any]:
    by_group: dict[str, list[tuple[float, float, float]]] = {}
    for sample in samples:
        probability = cast(np.ndarray, sample["probability"])
        target = cast(np.ndarray, sample["target"])
        prediction = probability >= threshold
        dice, iou = binary_dice_iou(prediction, target)
        boundary = boundary_f1(prediction, target)
        by_group.setdefault(str(sample["source_group_id"]), []).append((dice, iou, boundary))
    group_metrics = [np.mean(np.asarray(values, dtype=np.float32), axis=0) for values in by_group.values()]
    if not group_metrics:
        return {"available": False, "reason": "no_groups"}
    matrix = np.asarray(group_metrics, dtype=np.float32)
    rng = np.random.default_rng(seed)
    draws = np.empty((iterations, 3), dtype=np.float32)
    for index in range(iterations):
        sample_indexes = rng.integers(0, len(matrix), size=len(matrix))
        draws[index] = matrix[sample_indexes].mean(axis=0)
    names = ("dice", "iou", "boundary_f1")
    return {
        "available": True,
        "group_count": len(matrix),
        "iterations": int(iterations),
        "metrics": {
            name: {
                "mean": float(matrix[:, metric_index].mean()),
                "ci95_low": float(np.percentile(draws[:, metric_index], 2.5)),
                "ci95_high": float(np.percentile(draws[:, metric_index], 97.5)),
            }
            for metric_index, name in enumerate(names)
        },
    }


def select_recommended_threshold(
    threshold_rows: list[dict[str, Any]],
    *,
    target_positive_fraction_stats: dict[str, Any],
    max_empty_mask_rate: float,
    max_over_segmentation_rate: float,
) -> dict[str, Any]:
    if not threshold_rows:
        return {"threshold": None, "reason": "no_threshold_rows", "selected_row": None}
    target_median = safe_float(target_positive_fraction_stats.get("median"), default=0.0)

    def quality_key(row: dict[str, Any]) -> tuple[int, float, float, float]:
        empty_rate = safe_float(row.get("empty_mask_rate"), default=1.0)
        over_rate = safe_float(row.get("over_segmentation_rate"), default=1.0)
        dice = safe_float(row.get("foreground_mean_dice"), default=-1.0)
        positive_mean = safe_float(row.get("prediction_positive_fraction_mean"), default=1.0)
        passes = int(empty_rate <= max_empty_mask_rate and over_rate <= max_over_segmentation_rate)
        area_distance = abs(positive_mean - target_median)
        return passes, dice, -area_distance, -empty_rate

    selected = max(threshold_rows, key=quality_key)
    empty_rate = safe_float(selected.get("empty_mask_rate"), default=1.0)
    over_rate = safe_float(selected.get("over_segmentation_rate"), default=1.0)
    reason = (
        "max_dice_with_empty_and_oversegmentation_guards"
        if empty_rate <= max_empty_mask_rate and over_rate <= max_over_segmentation_rate
        else "fallback_best_available_threshold_guards_not_fully_met"
    )
    return {
        "threshold": selected.get("threshold"),
        "reason": reason,
        "selected_row": selected,
        "selection_policy": (
            "Prefer thresholds with empty_mask_rate <= max_empty_mask_rate and "
            "over_segmentation_rate <= max_over_segmentation_rate; then maximize Dice and prefer "
            "prediction positive fraction close to pseudo-mask median."
        ),
        "max_empty_mask_rate": float(max_empty_mask_rate),
        "max_over_segmentation_rate": float(max_over_segmentation_rate),
        "target_positive_fraction_median": target_median,
    }


def write_threshold_csv(path: Path, rows: list[dict[str, Any]], *, recommended_threshold: Any) -> None:
    fieldnames = [
        "threshold",
        "recommended",
        "case_count",
        "foreground_mean_dice",
        "foreground_mean_iou",
        "foreground_precision_mean",
        "foreground_recall_mean",
        "boundary_f1_mean",
        "prediction_positive_fraction_mean",
        "prediction_positive_fraction_median",
        "empty_mask_count",
        "empty_mask_rate",
        "over_segmentation_count",
        "over_segmentation_rate",
        "over_segmentation_fraction",
        "ece",
        "brier_score",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames if key != "recommended"},
                    "recommended": str(row.get("threshold")) == str(recommended_threshold),
                }
            )


def render_report(payload: dict[str, Any], *, language: str) -> str:
    recommendation = payload["recommendation"]
    selected = recommendation.get("selected_row") or {}
    rows = payload["thresholds"]
    benchmark = payload.get("inference_benchmark") or {}
    table = render_threshold_table(rows, recommended_threshold=recommendation.get("threshold"))
    if language == "zh":
        lines = [
            "# 2D Keyframe 分割阈值扫描报告",
            "",
            "## 结论",
            "",
            f"- Checkpoint：`{payload['checkpoint_path']}`",
            f"- Manifest：{len(payload['manifest_paths'])} 个；split：`{payload['split']}`；样本数：{payload['sample_count']}。",
            f"- 推荐运行阈值：`{recommendation.get('threshold')}`；选择原因：`{recommendation.get('reason')}`。",
            f"- 推荐阈值 Dice：{fmt(selected.get('foreground_mean_dice'))}；IoU：{fmt(selected.get('foreground_mean_iou'))}。",
            f"- 精确率：{fmt(selected.get('foreground_precision_mean'))}；召回率：{fmt(selected.get('foreground_recall_mean'))}。",
            f"- 空 mask 率：{fmt(selected.get('empty_mask_rate'))}；过分割率：{fmt(selected.get('over_segmentation_rate'))}。",
            f"- 单帧延迟：{fmt(benchmark.get('mean_latency_ms'))} ms；P95：{fmt(benchmark.get('p95_latency_ms'))} ms；峰值显存：{fmt(benchmark.get('peak_gpu_memory_mb'))} MB。",
            "",
            "## 阈值表",
            "",
            table,
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
            "ICG 主要反映灌注与组织活性差异；本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。",
        ]
    else:
        lines = [
            "# 2D Keyframe Segmentation Threshold Sweep",
            "",
            "## Summary",
            "",
            f"- Checkpoint: `{payload['checkpoint_path']}`",
            f"- Manifests: {len(payload['manifest_paths'])}; split: `{payload['split']}`; samples: {payload['sample_count']}.",
            f"- Recommended runtime threshold: `{recommendation.get('threshold')}`; reason: `{recommendation.get('reason')}`.",
            f"- Recommended Dice: {fmt(selected.get('foreground_mean_dice'))}; IoU: {fmt(selected.get('foreground_mean_iou'))}.",
            f"- Precision: {fmt(selected.get('foreground_precision_mean'))}; recall: {fmt(selected.get('foreground_recall_mean'))}.",
            f"- Empty-mask rate: {fmt(selected.get('empty_mask_rate'))}; over-segmentation rate: {fmt(selected.get('over_segmentation_rate'))}.",
            f"- Per-frame latency: {fmt(benchmark.get('mean_latency_ms'))} ms; P95: {fmt(benchmark.get('p95_latency_ms'))} ms; peak GPU memory: {fmt(benchmark.get('peak_gpu_memory_mb'))} MB.",
            "",
            "## Threshold Table",
            "",
            table,
            "",
            "## Medical Boundary",
            "",
            payload["medical_boundary"],
            "ICG mainly reflects perfusion and tissue-activity differences. This report supports MP4/JPEG keyframe segmentation stability tuning only.",
        ]
    return "\n".join(lines) + "\n"


def render_threshold_table(rows: list[dict[str, Any]], *, recommended_threshold: Any) -> str:
    lines = [
        "| Threshold | Recommended | Dice | IoU | Precision | Recall | Pred Pos Mean | Empty Rate | OverSeg Rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        recommended = str(row.get("threshold")) == str(recommended_threshold)
        lines.append(
            f"| {row.get('threshold')} | {recommended} | {fmt(row.get('foreground_mean_dice'))} | "
            f"{fmt(row.get('foreground_mean_iou'))} | {fmt(row.get('foreground_precision_mean'))} | "
            f"{fmt(row.get('foreground_recall_mean'))} | {fmt(row.get('prediction_positive_fraction_mean'))} | "
            f"{fmt(row.get('empty_mask_rate'))} | {fmt(row.get('over_segmentation_rate'))} |"
        )
    return "\n".join(lines)


def parse_thresholds(value: str | Iterable[Any]) -> list[float]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace(" ", ",").split(",")
    else:
        raw_items = [str(item) for item in value]
    thresholds = sorted({round(float(item), 6) for item in raw_items if str(item).strip()})
    if not thresholds:
        raise ValueError("At least one threshold is required.")
    for threshold in thresholds:
        if threshold <= 0.0 or threshold >= 1.0:
            raise ValueError(f"Threshold must be in (0, 1), got: {threshold}")
    return thresholds


def parse_shape(value: str) -> tuple[int, int]:
    parts = [part for part in value.lower().replace(",", "x").split("x") if part]
    if len(parts) != 2:
        raise ValueError(f"Expected image shape like 160x256, got: {value}")
    height, width = (int(parts[0]), int(parts[1]))
    if height <= 0 or width <= 0:
        raise ValueError(f"Image shape must be positive, got: {value}")
    return height, width


def numeric_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None, "mean": None}
    array = np.asarray(values, dtype=np.float32)
    return {
        "count": int(array.size),
        "min": round(float(array.min()), 8),
        "p25": round(float(np.percentile(array, 25)), 8),
        "median": round(float(np.median(array)), 8),
        "p75": round(float(np.percentile(array, 75)), 8),
        "max": round(float(array.max()), 8),
        "mean": round(float(array.mean()), 8),
    }


def mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def percentile_or_none(values: list[float], percentile: float) -> float | None:
    return float(np.percentile(np.asarray(values, dtype=np.float32), percentile)) if values else None


def safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate threshold stability for the 2D keyframe proxy segmenter.")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--manifest", nargs="+", default=[DEFAULT_MANIFEST])
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--image-shape", default="160x256")
    parser.add_argument("--split", default="val", choices=["train", "val", "test", "all"])
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--over-segmentation-fraction", type=float, default=0.6)
    parser.add_argument("--max-empty-mask-rate", type=float, default=0.05)
    parser.add_argument("--max-over-segmentation-rate", type=float, default=0.05)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    evaluate_keyframe_thresholds(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
