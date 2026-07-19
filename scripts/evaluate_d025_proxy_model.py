from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from PIL import Image
from torch import nn

from src.core.paths import ensure_dir, project_root, resolve_path
from src.metrics.segmentation import binary_segmentation_metrics
from src.models.lesion_segmenter import (
    checkpoint_sha256,
    load_lesion_segmenter_checkpoint,
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
DEFAULT_ASSET_ROOT = "research/reports/modeling/assets"
DEFAULT_THRESHOLDS = "0.30,0.40,0.50,0.60,0.70"
MEDICAL_BOUNDARY = (
    "D025 CBCT lesion ROI proxy evaluation only; not target-domain intraoperative ICG jaw osteomyelitis performance."
)


def evaluate_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    manifest_path = resolve_path(args.manifest)
    checkpoint_path = resolve_path(args.checkpoint)
    report_dir = ensure_dir(resolve_path(args.report_dir))
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    asset_dir = ensure_dir(resolve_path(args.asset_root) / f"d025_proxy_eval_{run_stamp}")

    rows = _select_rows(
        _load_manifest_rows(manifest_path),
        split=args.split,
        max_cases=args.max_cases,
    )
    if not rows:
        raise ValueError(f"No rows selected from {manifest_path} split={args.split}")
    thresholds = _parse_thresholds(args.thresholds)
    device = select_torch_device(args.device)
    model, checkpoint_metadata = load_lesion_segmenter_checkpoint(checkpoint_path, device=device)

    evaluated_cases = _predict_cases(model, rows, device=device)
    threshold_rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        for case in evaluated_cases:
            threshold_rows.append(_evaluate_case_at_threshold(case, threshold))

    threshold_summaries = [_summarize_threshold(threshold_rows, threshold) for threshold in thresholds]
    best_summary = _best_threshold_summary(threshold_summaries)
    best_threshold = float(best_summary["threshold"])
    best_case_rows = [row for row in threshold_rows if float(row["threshold"]) == best_threshold]
    failure_cases = _failure_cases(best_case_rows, limit=args.failure_count)
    _write_failure_previews(evaluated_cases, failure_cases, threshold=best_threshold, asset_dir=asset_dir)

    csv_path = report_dir / f"d025_proxy_model_evaluation_{date_stamp}_per_case.csv"
    json_path = report_dir / f"d025_proxy_model_evaluation_{date_stamp}.json"
    zh_report_path = report_dir / f"d025_proxy_model_evaluation_{date_stamp}_zh.md"
    en_report_path = report_dir / f"d025_proxy_model_evaluation_{date_stamp}_en.md"

    payload = {
        "schema_version": "osteo-vision-d025-proxy-evaluation-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256(checkpoint_path),
        "checkpoint_metadata": {
            "model_id": checkpoint_metadata.get("model_id"),
            "model_family": checkpoint_metadata.get("model_family"),
            "training": checkpoint_metadata.get("training", {}),
            "stored_metrics": checkpoint_metadata.get("metrics", {}),
        },
        "evaluation": {
            "split": args.split,
            "case_count": len(evaluated_cases),
            "thresholds": thresholds,
            "best_threshold": best_threshold,
            "best_summary": best_summary,
            "threshold_summaries": threshold_summaries,
            "failure_cases": failure_cases,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "device": str(device),
            "torch_version": torch.__version__,
            "clinical_claim_allowed": False,
            "medical_boundary": MEDICAL_BOUNDARY,
        },
        "outputs": {
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "zh_report_path": str(zh_report_path),
            "en_report_path": str(en_report_path),
            "asset_dir": str(asset_dir),
        },
    }

    _write_threshold_csv(csv_path, threshold_rows)
    write_json(json_path, payload)
    zh_report_path.write_text(_render_report(payload, language="zh"), encoding="utf-8")
    en_report_path.write_text(_render_report(payload, language="en"), encoding="utf-8")
    return payload


def _load_manifest_rows(manifest_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            cache_path = Path(row.get("cache_path") or row.get("input_path") or "")
            if not cache_path.is_absolute():
                cache_path = project_root() / cache_path
            if cache_path.exists():
                rows.append({**row, "cache_path": str(cache_path)})
    return rows


def _select_rows(rows: list[dict[str, Any]], *, split: str, max_cases: int | None) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("split") == split]
    if not selected:
        selected = rows
    selected = sorted(selected, key=lambda item: str(item.get("case_id") or ""))
    if max_cases and max_cases > 0:
        return selected[:max_cases]
    return selected


def _predict_cases(model: nn.Module, rows: list[dict[str, Any]], *, device: torch.device) -> list[dict[str, Any]]:
    model.eval()
    cases: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in rows:
            image = load_npz_image(row["cache_path"])
            target = load_npz_label(row["cache_path"]) > 0
            tensor = torch.from_numpy(image[None, None].astype(np.float32, copy=False)).to(device=device)
            probability = torch.softmax(model(tensor), dim=1)[0, 1].detach().cpu().numpy().astype(np.float32)
            cases.append({"row": row, "image": image, "target": target, "probability": probability})
    return cases


def _evaluate_case_at_threshold(case: dict[str, Any], threshold: float) -> dict[str, Any]:
    row = case["row"]
    target = np.asarray(case["target"]).astype(bool)
    probability = np.asarray(case["probability"], dtype=np.float32)
    prediction = probability >= threshold
    spacing = _derived_spacing(row)
    segmentation = binary_segmentation_metrics(prediction, target, spacing=spacing, nsd_tolerance_mm=1.0)
    tp = float(np.logical_and(prediction, target).sum())
    fp = float(np.logical_and(prediction, ~target).sum())
    fn = float(np.logical_and(~prediction, target).sum())
    tn = float(np.logical_and(~prediction, ~target).sum())
    total = float(target.size)
    return {
        "case_id": str(row.get("case_id") or ""),
        "split": str(row.get("split") or ""),
        "fold": str(row.get("fold") or ""),
        "diagnosis_group": str(row.get("diagnosis_group") or row.get("label") or ""),
        "threshold": float(threshold),
        "dice": segmentation.get("dice"),
        "iou": segmentation.get("iou"),
        "hd95": segmentation.get("hd95"),
        "nsd": segmentation.get("nsd"),
        "lesion_sensitivity": _safe_div(tp, tp + fn),
        "lesion_precision": _safe_div(tp, tp + fp),
        "specificity": _safe_div(tn, tn + fp),
        "pred_positive_fraction": _safe_div(float(prediction.sum()), total),
        "target_positive_fraction": _safe_div(float(target.sum()), total),
        "mean_probability": float(probability.mean()),
        "max_probability": float(probability.max()),
        "spacing": "x".join(_fmt_number(item) for item in spacing),
    }


def _summarize_threshold(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    selected = [row for row in rows if float(row["threshold"]) == float(threshold)]
    return {
        "threshold": float(threshold),
        "case_count": len(selected),
        "dice": _numeric_summary(row.get("dice") for row in selected),
        "iou": _numeric_summary(row.get("iou") for row in selected),
        "hd95": _numeric_summary(row.get("hd95") for row in selected),
        "nsd": _numeric_summary(row.get("nsd") for row in selected),
        "lesion_sensitivity": _numeric_summary(row.get("lesion_sensitivity") for row in selected),
        "lesion_precision": _numeric_summary(row.get("lesion_precision") for row in selected),
        "pred_positive_fraction": _numeric_summary(row.get("pred_positive_fraction") for row in selected),
        "target_positive_fraction": _numeric_summary(row.get("target_positive_fraction") for row in selected),
    }


def _best_threshold_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    def key(summary: dict[str, Any]) -> tuple[float, float]:
        dice_mean = _summary_mean(summary.get("dice"))
        iou_mean = _summary_mean(summary.get("iou"))
        return (dice_mean if dice_mean is not None else -1.0, iou_mean if iou_mean is not None else -1.0)

    return max(summaries, key=key)


def _failure_cases(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda item: float(item.get("dice") or -1.0))
    failures: list[dict[str, Any]] = []
    for row in sorted_rows[: max(0, limit)]:
        failures.append(
            {
                "case_id": row["case_id"],
                "diagnosis_group": row["diagnosis_group"],
                "threshold": row["threshold"],
                "dice": row["dice"],
                "iou": row["iou"],
                "hd95": row["hd95"],
                "nsd": row["nsd"],
                "lesion_sensitivity": row["lesion_sensitivity"],
                "lesion_precision": row["lesion_precision"],
                "pred_positive_fraction": row["pred_positive_fraction"],
                "target_positive_fraction": row["target_positive_fraction"],
            }
        )
    return failures


def _write_failure_previews(
    evaluated_cases: list[dict[str, Any]],
    failure_cases: list[dict[str, Any]],
    *,
    threshold: float,
    asset_dir: Path,
) -> None:
    case_by_id = {str(item["row"].get("case_id") or ""): item for item in evaluated_cases}
    for failure in failure_cases:
        case = case_by_id.get(str(failure["case_id"]))
        if not case:
            continue
        prediction = np.asarray(case["probability"], dtype=np.float32) >= threshold
        target = np.asarray(case["target"]).astype(bool)
        preview = _preview_overlay(np.asarray(case["image"], dtype=np.float32), prediction, target)
        preview_path = asset_dir / f"{failure['case_id']}_failure_preview.png"
        Image.fromarray(preview).save(preview_path)
        failure["preview_path"] = str(preview_path)


def _preview_overlay(image: np.ndarray, prediction: np.ndarray, target: np.ndarray) -> np.ndarray:
    slice_index = _representative_slice(target, prediction)
    image_slice = _normalize_slice(image[slice_index])
    pred_slice = prediction[slice_index]
    target_slice = target[slice_index]
    rgb = np.stack([image_slice, image_slice, image_slice], axis=-1)
    rgb[pred_slice, 0] = 255
    rgb[pred_slice, 1] = (rgb[pred_slice, 1] * 0.35).astype(np.uint8)
    rgb[pred_slice, 2] = (rgb[pred_slice, 2] * 0.35).astype(np.uint8)
    rgb[target_slice, 1] = 255
    rgb[target_slice, 0] = np.maximum(rgb[target_slice, 0], 190)
    overlap = np.logical_and(pred_slice, target_slice)
    rgb[overlap] = np.array([255, 230, 30], dtype=np.uint8)
    return rgb


def _representative_slice(target: np.ndarray, prediction: np.ndarray) -> int:
    union = np.logical_or(target, prediction)
    if union.any():
        indices = np.where(union)[0]
        return int(np.median(indices))
    return int(target.shape[0] // 2)


def _normalize_slice(slice_array: np.ndarray) -> np.ndarray:
    data = np.asarray(slice_array, dtype=np.float32)
    low = float(np.percentile(data, 1))
    high = float(np.percentile(data, 99))
    if high <= low:
        high = float(data.max())
        low = float(data.min())
    if high <= low:
        return np.zeros(data.shape, dtype=np.uint8)
    return np.clip((data - low) / (high - low) * 255.0, 0, 255).astype(np.uint8)


def _write_threshold_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "split",
        "fold",
        "diagnosis_group",
        "threshold",
        "dice",
        "iou",
        "hd95",
        "nsd",
        "lesion_sensitivity",
        "lesion_precision",
        "specificity",
        "pred_positive_fraction",
        "target_positive_fraction",
        "mean_probability",
        "max_probability",
        "spacing",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _render_report(payload: dict[str, Any], *, language: str) -> str:
    evaluation = payload["evaluation"]
    outputs = payload["outputs"]
    best = evaluation["best_summary"]
    threshold_rows = evaluation["threshold_summaries"]
    failures = evaluation["failure_cases"]
    if language == "zh":
        lines = [
            "# D025 CBCT 代理分割模型评估报告",
            "",
            "## 定位",
            "",
            "本报告评估当前工程可用的 D025 CBCT lesion ROI 代理 checkpoint。它用于补齐模型闭环的可审计证据，不能代表真实术中 ICG 颌骨骨髓炎视频或图片性能。",
            "",
            "## 输入与模型",
            "",
            f"- Manifest：`{payload['manifest_path']}`",
            f"- Checkpoint：`{payload['checkpoint_path']}`",
            f"- Checkpoint SHA256：`{payload['checkpoint_sha256']}`",
            f"- 评估 split：`{evaluation['split']}`；病例数：{evaluation['case_count']}。",
            f"- 设备：`{evaluation['device']}`；PyTorch：`{evaluation['torch_version']}`。",
            "",
            "## 最优阈值摘要",
            "",
            f"- 最优阈值：{_fmt_metric(best['threshold'])}",
            f"- Mean Dice：{_fmt_metric(best['dice'].get('mean'))}",
            f"- Mean IoU：{_fmt_metric(best['iou'].get('mean'))}",
            f"- Mean HD95：{_fmt_metric(best['hd95'].get('mean'))}",
            f"- Mean NSD：{_fmt_metric(best['nsd'].get('mean'))}",
            f"- Lesion sensitivity：{_fmt_metric(best['lesion_sensitivity'].get('mean'))}",
            f"- Lesion precision：{_fmt_metric(best['lesion_precision'].get('mean'))}",
            "",
            "## 阈值扫描",
            "",
            "| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            *_threshold_table_rows(threshold_rows),
            "",
            "## 低分样本",
            "",
            *_failure_lines(failures, language="zh"),
            "",
            "## 输出文件",
            "",
            f"- JSON：`{outputs['json_path']}`",
            f"- CSV：`{outputs['csv_path']}`",
            f"- 预览图目录：`{outputs['asset_dir']}`",
            "",
            "## 医学边界",
            "",
            evaluation["medical_boundary"],
        ]
    else:
        lines = [
            "# D025 CBCT Proxy Segmentation Model Evaluation",
            "",
            "## Scope",
            "",
            "This report evaluates the currently runnable D025 CBCT lesion ROI proxy checkpoint. It is auditable model-loop evidence, not target-domain intraoperative ICG jaw osteomyelitis performance.",
            "",
            "## Inputs and Model",
            "",
            f"- Manifest: `{payload['manifest_path']}`",
            f"- Checkpoint: `{payload['checkpoint_path']}`",
            f"- Checkpoint SHA256: `{payload['checkpoint_sha256']}`",
            f"- Evaluation split: `{evaluation['split']}`; cases: {evaluation['case_count']}.",
            f"- Device: `{evaluation['device']}`; PyTorch: `{evaluation['torch_version']}`.",
            "",
            "## Best Threshold Summary",
            "",
            f"- Best threshold: {_fmt_metric(best['threshold'])}",
            f"- Mean Dice: {_fmt_metric(best['dice'].get('mean'))}",
            f"- Mean IoU: {_fmt_metric(best['iou'].get('mean'))}",
            f"- Mean HD95: {_fmt_metric(best['hd95'].get('mean'))}",
            f"- Mean NSD: {_fmt_metric(best['nsd'].get('mean'))}",
            f"- Lesion sensitivity: {_fmt_metric(best['lesion_sensitivity'].get('mean'))}",
            f"- Lesion precision: {_fmt_metric(best['lesion_precision'].get('mean'))}",
            "",
            "## Threshold Sweep",
            "",
            "| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            *_threshold_table_rows(threshold_rows),
            "",
            "## Low-Scoring Cases",
            "",
            *_failure_lines(failures, language="en"),
            "",
            "## Outputs",
            "",
            f"- JSON: `{outputs['json_path']}`",
            f"- CSV: `{outputs['csv_path']}`",
            f"- Preview directory: `{outputs['asset_dir']}`",
            "",
            "## Medical Boundary",
            "",
            evaluation["medical_boundary"],
        ]
    return "\n".join(lines) + "\n"


def _threshold_table_rows(threshold_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in threshold_rows:
        lines.append(
            "| "
            f"{_fmt_metric(row['threshold'])} | "
            f"{_fmt_metric(row['dice'].get('mean'))} | "
            f"{_fmt_metric(row['iou'].get('mean'))} | "
            f"{_fmt_metric(row['hd95'].get('mean'))} | "
            f"{_fmt_metric(row['nsd'].get('mean'))} | "
            f"{_fmt_metric(row['lesion_sensitivity'].get('mean'))} | "
            f"{_fmt_metric(row['lesion_precision'].get('mean'))} |"
        )
    return lines


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


def _numeric_summary(values: Any) -> dict[str, Any]:
    numeric = [float(value) for value in values if value is not None and np.isfinite(float(value))]
    if not numeric:
        return {"available": False, "count": 0, "mean": None, "std": None, "median": None, "min": None, "max": None}
    array = np.asarray(numeric, dtype=np.float64)
    return {
        "available": True,
        "count": int(array.size),
        "mean": float(array.mean()),
        "std": float(array.std(ddof=0)),
        "median": float(np.median(array)),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def _summary_mean(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    mean = value.get("mean")
    if mean is None:
        return None
    return float(mean)


def _parse_thresholds(value: str) -> list[float]:
    thresholds = sorted({float(item.strip()) for item in value.split(",") if item.strip()})
    if not thresholds:
        raise ValueError("At least one threshold is required")
    for threshold in thresholds:
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError(f"Threshold must be in [0, 1], got {threshold}")
    return thresholds


def _derived_spacing(row: dict[str, Any]) -> tuple[float, ...]:
    original_spacing = _parse_x_numbers(str(row.get("original_spacing") or ""))
    original_shape = _parse_x_numbers(str(row.get("original_shape") or ""))
    target_shape = _parse_x_numbers(str(row.get("target_shape") or ""))
    if len(original_spacing) == 3 and len(original_shape) == 3 and len(target_shape) == 3:
        return tuple(
            float(spacing * original / max(1.0, target))
            for spacing, original, target in zip(original_spacing, original_shape, target_shape, strict=False)
        )
    return (1.0, 1.0, 1.0)


def _parse_x_numbers(value: str) -> list[float]:
    numbers: list[float] = []
    for item in value.lower().replace("|", "x").split("x"):
        try:
            numbers.append(float(item.strip()))
        except ValueError:
            continue
    return numbers


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0.0:
        return None
    return float(numerator) / float(denominator)


def _fmt_number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8g}"
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the D025 CBCT lesion ROI proxy checkpoint.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--asset-root", default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--split", default="val")
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all selected split rows.")
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--failure-count", type=int, default=6)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    payload = evaluate_checkpoint(parse_args())
    print(
        json.dumps({"outputs": payload["outputs"], "evaluation": payload["evaluation"]}, ensure_ascii=False, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
