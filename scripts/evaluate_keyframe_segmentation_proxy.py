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
    samples = collect_probabilities(model, rows, image_shape=image_shape, device=device)
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
        "split": args.split,
        "image_shape": [int(image_shape[0]), int(image_shape[1])],
        "sample_count": len(samples),
        "target_positive_fraction_stats": target_stats,
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
            "They are not real intraoperative ICG jaw osteomyelitis clinical segmentation performance."
        ),
    }
    write_json(json_path, payload)
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def load_eval_rows(manifest_paths: Iterable[str], *, split: str, max_samples: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    paths = [str(item) for item in manifest_paths if str(item).strip()]
    if not paths:
        raise ValueError("At least one --manifest path is required.")
    rows: list[dict[str, str]] = []
    for manifest in paths:
        rows.extend(load_manifest_rows(manifest))
    if split != "all":
        rows = [row for row in rows if row.get("split") == split]
    if max_samples > 0:
        rows = rows[:max_samples]
    if not rows:
        raise ValueError(f"No rows found for split={split!r} in manifests: {paths}")
    return rows, {"manifest_paths": [str(resolve_path(path)) for path in paths], "row_count": len(rows)}


def collect_probabilities(
    model: nn.Module,
    rows: list[dict[str, str]],
    *,
    image_shape: tuple[int, int],
    device: torch.device,
) -> list[dict[str, Any]]:
    dataset = ManifestKeyframeDataset(rows, image_shape=image_shape)
    samples: list[dict[str, Any]] = []
    model.eval()
    with torch.no_grad():
        for index, (image, target, _sample_weight) in enumerate(DataLoader(dataset, batch_size=1, shuffle=False)):
            image = image.to(device=device, dtype=torch.float32)
            probability = torch.softmax(model(image), dim=1)[0, 1].detach().cpu().numpy().astype(np.float32)
            target_np = target.numpy()[0] > 0
            samples.append(
                {
                    "case_id": rows[index].get("case_id") or f"sample_{index:04d}",
                    "probability": probability,
                    "target": target_np,
                    "target_positive_fraction": float(target_np.mean()),
                }
            )
    return samples


def threshold_metrics(
    samples: list[dict[str, Any]],
    *,
    threshold: float,
    over_segmentation_fraction: float,
) -> dict[str, Any]:
    dice_scores: list[float] = []
    iou_scores: list[float] = []
    positive_fractions: list[float] = []
    empty_count = 0
    over_count = 0
    for sample in samples:
        probability = cast(np.ndarray, sample["probability"])
        target = cast(np.ndarray, sample["target"])
        prediction = probability >= float(threshold)
        dice, iou = binary_dice_iou(prediction, target)
        positive_fraction = float(prediction.mean()) if prediction.size else 0.0
        dice_scores.append(dice)
        iou_scores.append(iou)
        positive_fractions.append(positive_fraction)
        if positive_fraction <= 0.0:
            empty_count += 1
        if positive_fraction > over_segmentation_fraction:
            over_count += 1
    return {
        "threshold": round(float(threshold), 6),
        "case_count": len(samples),
        "foreground_mean_dice": mean_or_none(dice_scores),
        "foreground_mean_iou": mean_or_none(iou_scores),
        "prediction_positive_fraction_mean": mean_or_none(positive_fractions),
        "prediction_positive_fraction_median": percentile_or_none(positive_fractions, 50),
        "prediction_positive_fraction_p25": percentile_or_none(positive_fractions, 25),
        "prediction_positive_fraction_p75": percentile_or_none(positive_fractions, 75),
        "empty_mask_count": empty_count,
        "empty_mask_rate": float(empty_count / len(samples)) if samples else None,
        "over_segmentation_count": over_count,
        "over_segmentation_rate": float(over_count / len(samples)) if samples else None,
        "over_segmentation_fraction": float(over_segmentation_fraction),
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
        "prediction_positive_fraction_mean",
        "prediction_positive_fraction_median",
        "empty_mask_count",
        "empty_mask_rate",
        "over_segmentation_count",
        "over_segmentation_rate",
        "over_segmentation_fraction",
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
            f"- 空 mask 率：{fmt(selected.get('empty_mask_rate'))}；过分割率：{fmt(selected.get('over_segmentation_rate'))}。",
            "",
            "## 阈值表",
            "",
            table,
            "",
            "## 医学边界",
            "",
            payload["medical_boundary"],
            "ICG 不是颌骨骨髓炎特异性探针，本报告只服务于平台软件的 MP4/JPEG keyframe 分割稳定性调参。",
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
            f"- Empty-mask rate: {fmt(selected.get('empty_mask_rate'))}; over-segmentation rate: {fmt(selected.get('over_segmentation_rate'))}.",
            "",
            "## Threshold Table",
            "",
            table,
            "",
            "## Medical Boundary",
            "",
            payload["medical_boundary"],
            "ICG is not a jaw-osteomyelitis-specific probe. This report is for MP4/JPEG keyframe segmentation stability tuning only.",
        ]
    return "\n".join(lines) + "\n"


def render_threshold_table(rows: list[dict[str, Any]], *, recommended_threshold: Any) -> str:
    lines = [
        "| Threshold | Recommended | Dice | IoU | Pred Pos Mean | Empty Rate | OverSeg Rate |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        recommended = str(row.get("threshold")) == str(recommended_threshold)
        lines.append(
            f"| {row.get('threshold')} | {recommended} | {fmt(row.get('foreground_mean_dice'))} | "
            f"{fmt(row.get('foreground_mean_iou'))} | {fmt(row.get('prediction_positive_fraction_mean'))} | "
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
    parser.add_argument("--split", default="val", choices=["train", "val", "all"])
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
