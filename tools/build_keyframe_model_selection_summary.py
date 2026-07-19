from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRIC_KEYS = (
    "foreground_mean_dice",
    "foreground_mean_iou",
    "foreground_precision_mean",
    "foreground_recall_mean",
    "boundary_f1_mean",
    "ece",
    "brier_score",
    "empty_mask_rate",
    "over_segmentation_rate",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate multi-seed keyframe segmentation selection evidence.")
    parser.add_argument(
        "--selection-root",
        default="research/reports/modeling/keyframe_model_selection_20260715",
    )
    parser.add_argument("--baseline-model-id", default="keyframe_candidate_20260714")
    parser.add_argument("--output-stem", default="keyframe_model_selection_summary_20260715")
    parser.add_argument("--minimum-seeds", type=int, default=3)
    return parser.parse_args()


def build_summary(
    selection_root: Path,
    *,
    baseline_model_id: str,
    minimum_seeds: int,
) -> dict[str, Any]:
    test_runs = _load_runs(selection_root, split="test")
    val_runs = _load_runs(selection_root, split="val")
    baseline = next((run for run in test_runs if run["model_id"] == baseline_model_id), None)
    if baseline is None:
        raise ValueError(f"Baseline model {baseline_model_id!r} was not found under {selection_root}")

    baseline_dice = float(baseline["metrics"]["foreground_mean_dice"])
    baseline_iou = float(baseline["metrics"]["foreground_mean_iou"])
    families: list[dict[str, Any]] = []
    for family, runs in sorted(_group_candidates(test_runs, baseline_model_id).items()):
        aggregates = _aggregate_runs(runs)
        all_seeds_above_baseline = all(
            float(run["metrics"]["foreground_mean_dice"]) > baseline_dice
            and float(run["metrics"]["foreground_mean_iou"]) > baseline_iou
            for run in runs
        )
        seed_count_passed = len(runs) >= minimum_seeds
        safety_rates_passed = all(
            float(run["metrics"]["empty_mask_rate"]) <= 0.05 and float(run["metrics"]["over_segmentation_rate"]) <= 0.05
            for run in runs
        )
        eligible_for_runtime_gate = seed_count_passed and all_seeds_above_baseline and safety_rates_passed
        validation_choice = _validation_choice(val_runs, {run["model_id"] for run in runs})
        families.append(
            {
                "model_family": family,
                "seed_count": len(runs),
                "runs": runs,
                "aggregate": aggregates,
                "gates": {
                    "minimum_seed_count_passed": seed_count_passed,
                    "all_seeds_above_baseline_dice_and_iou": all_seeds_above_baseline,
                    "empty_and_over_segmentation_rates_passed": safety_rates_passed,
                    "eligible_for_4k_runtime_gate": eligible_for_runtime_gate,
                },
                "validation_selected_checkpoint": validation_choice,
            }
        )

    eligible = [family for family in families if family["gates"]["eligible_for_4k_runtime_gate"]]
    eligible.sort(key=lambda item: float(item["aggregate"]["foreground_mean_dice"]["mean"]), reverse=True)
    selected = eligible[0] if eligible else None
    recommendation = {
        "selected_family": selected["model_family"] if selected else None,
        "selected_checkpoint": (
            selected["validation_selected_checkpoint"]["checkpoint_path"]
            if selected and selected["validation_selected_checkpoint"]
            else None
        ),
        "selected_model_id": (
            selected["validation_selected_checkpoint"]["model_id"]
            if selected and selected["validation_selected_checkpoint"]
            else None
        ),
        "selected_threshold": (
            selected["validation_selected_checkpoint"]["threshold"]
            if selected and selected["validation_selected_checkpoint"]
            else None
        ),
        "runtime_replacement_allowed": False,
        "next_gate": "strict_4k_tiled_runtime_and_competition_flow_validation",
        "reason": (
            "multi_seed_accuracy_and_safety_gates_passed; checkpoint chosen by validation Dice"
            if selected
            else "no candidate passed every multi-seed accuracy and safety gate"
        ),
    }
    split_evidence = baseline.get("source_group_split", {})
    return {
        "schema_version": "osteo-vision-keyframe-model-selection-summary-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_root": str(selection_root.resolve()),
        "protocol": {
            "task": "video_signal_segmentation",
            "selection_rule": "validation threshold and checkpoint selection; locked test reporting",
            "minimum_seeds": minimum_seeds,
            "sample_count_test": baseline["sample_count"],
            "source_group_split": split_evidence,
            "target_domain": False,
        },
        "baseline": baseline,
        "candidate_families": families,
        "recommendation": recommendation,
        "medical_boundary": (
            "All metrics use public non-target-domain fluorescence proxy masks. They do not measure clinical "
            "performance on intraoperative ICG jaw osteomyelitis and cannot justify an autonomous diagnosis claim."
        ),
    }


def write_outputs(summary: dict[str, Any], output_dir: Path, output_stem: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_dir / f"{output_stem}.json",
        "csv": output_dir / f"{output_stem}.csv",
        "zh": output_dir.parent / f"{output_stem}_zh.md",
        "en": output_dir.parent / f"{output_stem}_en.md",
    }
    paths["json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [summary["baseline"]]
    for family in summary["candidate_families"]:
        rows.extend(family["runs"])
    with paths["csv"].open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "model_id",
            "model_family",
            "seed",
            "threshold",
            "checkpoint_path",
            *METRIC_KEYS,
            "mean_latency_ms",
            "p95_latency_ms",
            "peak_gpu_memory_mb",
            "parameter_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for run in rows:
            writer.writerow(_csv_row(run))
    paths["zh"].write_text(_render_report(summary, language="zh"), encoding="utf-8")
    paths["en"].write_text(_render_report(summary, language="en"), encoding="utf-8")
    return paths


def _load_runs(selection_root: Path, *, split: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in sorted(selection_root.glob("**/keyframe_threshold_eval.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("split") != split:
            continue
        selected = payload["recommendation"]["selected_row"]
        benchmark = payload.get("inference_benchmark") or {}
        checkpoint_metadata = payload.get("checkpoint_metadata") or {}
        training = checkpoint_metadata.get("training") or {}
        runs.append(
            {
                "model_id": checkpoint_metadata.get("model_id"),
                "model_family": checkpoint_metadata.get("model_family"),
                "seed": training.get("seed"),
                "threshold": payload["recommendation"]["threshold"],
                "checkpoint_path": payload["checkpoint_path"],
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "sample_count": payload["sample_count"],
                "metrics": {key: selected[key] for key in METRIC_KEYS},
                "video_group_bootstrap": selected.get("video_group_bootstrap", {}),
                "benchmark": {
                    "mean_latency_ms": benchmark.get("mean_latency_ms"),
                    "p95_latency_ms": benchmark.get("p95_latency_ms"),
                    "peak_gpu_memory_mb": benchmark.get("peak_gpu_memory_mb"),
                    "parameter_count": benchmark.get("parameter_count"),
                },
                "source_group_split": payload.get("source_group_split", {}),
                "report_path": str(path.resolve()),
            }
        )
    return runs


def _group_candidates(runs: list[dict[str, Any]], baseline_model_id: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        if run["model_id"] == baseline_model_id:
            continue
        grouped.setdefault(str(run["model_family"]), []).append(run)
    return grouped


def _aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in METRIC_KEYS:
        values = [float(run["metrics"][key]) for run in runs]
        output[key] = _stats(values)
    for key in ("mean_latency_ms", "p95_latency_ms", "peak_gpu_memory_mb", "parameter_count"):
        values = [float(run["benchmark"][key]) for run in runs if run["benchmark"].get(key) is not None]
        output[key] = _stats(values)
    return output


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _validation_choice(val_runs: list[dict[str, Any]], model_ids: set[str]) -> dict[str, Any] | None:
    candidates = [run for run in val_runs if run["model_id"] in model_ids]
    if not candidates:
        return None
    return max(candidates, key=lambda run: float(run["metrics"]["foreground_mean_dice"]))


def _csv_row(run: dict[str, Any]) -> dict[str, Any]:
    row = {
        "model_id": run["model_id"],
        "model_family": run["model_family"],
        "seed": run["seed"],
        "threshold": run["threshold"],
        "checkpoint_path": run["checkpoint_path"],
    }
    row.update(run["metrics"])
    row.update(run["benchmark"])
    return row


def _render_report(summary: dict[str, Any], *, language: str) -> str:
    baseline = summary["baseline"]
    recommendation = summary["recommendation"]
    chinese = language == "zh"
    title = "关键帧分割模型多随机种子选型报告" if chinese else "Multi-seed Keyframe Segmentation Model Selection"
    lines = [f"# {title}", ""]
    if chinese:
        lines.extend(
            [
                "## 结论",
                "",
                f"- 推荐候选族：`{recommendation['selected_family']}`。",
                f"- 验证集选定 checkpoint：`{recommendation['selected_checkpoint']}`。",
                f"- 锁定阈值：`{recommendation['selected_threshold']}`。",
                "- 当前保持 `runtime_replacement_allowed=false`，进入严格 4K tiled 与比赛闭环门控。",
                "",
                "## 独立测试集比较",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Conclusion",
                "",
                f"- Recommended family: `{recommendation['selected_family']}`.",
                f"- Validation-selected checkpoint: `{recommendation['selected_checkpoint']}`.",
                f"- Locked threshold: `{recommendation['selected_threshold']}`.",
                "- `runtime_replacement_allowed=false` remains in force until strict 4K tiled and competition-flow gates pass.",
                "",
                "## Held-out test comparison",
                "",
            ]
        )
    lines.append(
        "| 模型 | 随机种子数 | Dice 均值 +/- SD | IoU 均值 +/- SD | 召回率 | P95 ms | 峰值显存 MB | 门控 |"
        if chinese
        else "| Model | Seeds | Dice mean +/- SD | IoU mean +/- SD | Recall | P95 ms | Peak MB | Gate |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    baseline_metrics = baseline["metrics"]
    baseline_benchmark = baseline["benchmark"]
    lines.append(
        "| ConvNeXt U-Net baseline | 1 | "
        f"{baseline_metrics['foreground_mean_dice']:.4f} +/- 0.0000 | "
        f"{baseline_metrics['foreground_mean_iou']:.4f} +/- 0.0000 | "
        f"{baseline_metrics['foreground_recall_mean']:.4f} | "
        f"{baseline_benchmark['p95_latency_ms']:.2f} | {baseline_benchmark['peak_gpu_memory_mb']:.2f} | baseline |"
    )
    for family in summary["candidate_families"]:
        aggregate = family["aggregate"]
        gate = "pass" if family["gates"]["eligible_for_4k_runtime_gate"] else "hold"
        lines.append(
            f"| {family['model_family']} | {family['seed_count']} | "
            f"{aggregate['foreground_mean_dice']['mean']:.4f} +/- {aggregate['foreground_mean_dice']['std']:.4f} | "
            f"{aggregate['foreground_mean_iou']['mean']:.4f} +/- {aggregate['foreground_mean_iou']['std']:.4f} | "
            f"{aggregate['foreground_recall_mean']['mean']:.4f} | "
            f"{aggregate['p95_latency_ms']['mean']:.2f} | {aggregate['peak_gpu_memory_mb']['mean']:.2f} | {gate} |"
        )
    boundary = (
        "全部指标均基于公开、非目标域的荧光代理掩膜，不能用于衡量颌骨骨髓炎术中 ICG 场景的临床性能，"
        "也不能支持自动诊断结论。"
        if chinese
        else summary["medical_boundary"]
    )
    lines.extend(["", "## Evidence boundary" if not chinese else "## 证据边界", "", boundary, ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.selection_root)
    summary = build_summary(
        root,
        baseline_model_id=args.baseline_model_id,
        minimum_seeds=args.minimum_seeds,
    )
    outputs = write_outputs(summary, root, args.output_stem)
    print(json.dumps({key: str(value.resolve()) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
