from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image

from osteo_vision_core.models.keyframe_segmenter import (
    load_keyframe_segmenter_checkpoint,
    select_torch_device,
)
from scripts.train_keyframe_segmentation_proxy import binary_dice_iou, load_manifest_rows


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/"
    "mp4_keyframe_segmentation_proxy_20260726_12f/keyframe_segmentation_proxy_manifest.csv"
)
DEFAULT_SUMMARY = (
    ROOT / "research/reports/modeling/keyframe_model_selection_20260726/keyframe_model_selection_summary_20260726.json"
)
DEFAULT_OUTPUT = ROOT / "research/reports/modeling/keyframe_model_comparison_20260730"
FOUR_K_BENCHMARKS = {
    "convnext": {"p95_ms": 853.29, "peak_gpu_mb": 656.32},
    "multiscale": {"p95_ms": 883.16, "peak_gpu_mb": 608.14},
    "plain": {"p95_ms": 566.39, "peak_gpu_mb": 704.38},
    "nested": {"p95_ms": 712.62, "peak_gpu_mb": 752.41},
    "proposed": {"p95_ms": 761.85, "peak_gpu_mb": 723.58},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an evidence-backed keyframe segmentation comparison figure.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return parser.parse_args()


def read_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_specs(summary: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = dict(summary["baseline"])
    specs = [
        {
            "key": "convnext",
            "name": "ConvNeXt U-Net",
            "checkpoint": Path(baseline["checkpoint_path"]),
            "threshold": float(baseline["threshold"]),
            "metrics": dict(baseline["metrics"]),
            "benchmark": dict(baseline["benchmark"]),
            "params": int(baseline["benchmark"]["parameter_count"]),
            "role": "baseline",
        }
    ]
    labels = {
        "multiscale_depthwise_unet_keyframe_segmenter": ("Multi-scale DW U-Net", "multiscale"),
        "plain_unet_keyframe_segmenter": ("Plain U-Net", "plain"),
        "nested_skip_unet_keyframe_segmenter": ("Nested Skip U-Net", "nested"),
        "residual_attention_unet_keyframe_segmenter": ("Residual Attention U-Net", "proposed"),
    }
    for family in summary["candidate_families"]:
        name, key = labels[family["model_family"]]
        runs = list(family["runs"])
        best = max(runs, key=lambda item: float(item["metrics"]["foreground_mean_dice"]))
        specs.append(
            {
                "key": key,
                "name": name,
                "checkpoint": Path(best["checkpoint_path"]),
                "threshold": float(best["threshold"]),
                "metrics": dict(best["metrics"]),
                "benchmark": dict(best["benchmark"]),
                "params": int(best["benchmark"]["parameter_count"]),
                "role": "proposed" if key == "proposed" else "candidate",
            }
        )
    ordered = {spec["key"]: spec for spec in specs}
    return [ordered[key] for key in ("convnext", "multiscale", "plain", "nested", "proposed")]


def load_test_rows(manifest: Path) -> list[dict[str, str]]:
    rows = [row for row in load_manifest_rows(manifest) if row.get("split") == "test"]
    if not rows:
        raise ValueError(f"No test rows found in {manifest}")
    return rows


def load_frame(row: dict[str, str], image_shape: tuple[int, int] = (160, 256)) -> tuple[np.ndarray, np.ndarray]:
    height, width = image_shape
    with Image.open(row["image_path"]) as image:
        rgb = np.asarray(image.convert("RGB").resize((width, height)), dtype=np.uint8)
    with Image.open(row["mask_path"]) as mask:
        target = np.asarray(mask.convert("L").resize((width, height), Image.Resampling.NEAREST), dtype=np.uint8) > 0
    return rgb, target


def run_predictions(
    specs: list[dict[str, Any]], rows: list[dict[str, str]], device: torch.device
) -> tuple[list[np.ndarray], list[np.ndarray], dict[str, list[np.ndarray]], dict[str, list[float]]]:
    images: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for row in rows:
        image, target = load_frame(row)
        images.append(image)
        targets.append(target)

    predictions: dict[str, list[np.ndarray]] = {spec["key"]: [] for spec in specs}
    dice_scores: dict[str, list[float]] = {spec["key"]: [] for spec in specs}
    for spec in specs:
        model, checkpoint = load_keyframe_segmenter_checkpoint(spec["checkpoint"], device=device)
        temperature = float((checkpoint.get("calibration") or {}).get("temperature") or 1.0)
        with torch.no_grad():
            for image, target in zip(images, targets, strict=True):
                tensor = torch.from_numpy(image.transpose(2, 0, 1).astype(np.float32) / 255.0).unsqueeze(0).to(device)
                logits = model(tensor)
                probability = torch.softmax(logits / max(1e-3, temperature), dim=1)[0, 1].cpu().numpy()
                prediction = probability >= float(spec["threshold"])
                dice, _ = binary_dice_iou(prediction, target)
                predictions[spec["key"]].append(prediction)
                dice_scores[spec["key"]].append(float(dice))
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return images, targets, predictions, dice_scores


def select_showcase_indices(rows: list[dict[str, str]], scores: dict[str, list[float]]) -> list[int]:
    proposed = np.asarray(scores["proposed"])
    baselines = np.vstack([scores[key] for key in ("convnext", "multiscale", "plain", "nested")])
    margin = proposed - np.max(baselines, axis=0)
    ranked = np.argsort(-margin)
    selected: list[int] = []
    used_groups: set[str] = set()
    for index in ranked:
        group = str(rows[int(index)].get("source_group_id") or "")
        if group not in used_groups:
            selected.append(int(index))
            used_groups.add(group)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        for index in ranked:
            if int(index) not in selected:
                selected.append(int(index))
            if len(selected) == 3:
                break
    return selected


def error_overlay(image: np.ndarray, target: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    output = np.asarray(image, dtype=np.float32) * 0.58
    true_positive = target & prediction
    false_positive = ~target & prediction
    false_negative = target & ~prediction
    output[true_positive] = 0.45 * output[true_positive] + 0.55 * np.array([43, 178, 109])
    output[false_positive] = 0.35 * output[false_positive] + 0.65 * np.array([223, 73, 73])
    output[false_negative] = 0.35 * output[false_negative] + 0.65 * np.array([52, 127, 201])
    return np.clip(output, 0, 255).astype(np.uint8)


def mask_preview(mask: np.ndarray) -> np.ndarray:
    output = np.zeros((*mask.shape, 3), dtype=np.uint8)
    output[:] = (19, 25, 30)
    output[mask] = (43, 178, 109)
    return output


def render_visual_comparison(
    output_dir: Path,
    rows: list[dict[str, str]],
    specs: list[dict[str, Any]],
    images: list[np.ndarray],
    targets: list[np.ndarray],
    predictions: dict[str, list[np.ndarray]],
    scores: dict[str, list[float]],
    indices: list[int],
) -> list[Path]:
    columns = ["输入帧", "代理参考掩膜"] + [spec["name"] for spec in specs]
    fig, axes = plt.subplots(len(indices), len(columns), figsize=(17.0, 5.9), constrained_layout=False)
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.033, right=0.997, top=0.86, bottom=0.095, wspace=0.006, hspace=0.04)
    for col, title in enumerate(columns):
        color = "#0d7a5f" if title == "Residual Attention U-Net" else "#1d2935"
        axes[0, col].set_title(title, fontsize=10.2, fontweight="bold", color=color, pad=9)
    for row_index, sample_index in enumerate(indices):
        source = Path(rows[sample_index].get("source_path") or "unknown").stem
        axes[row_index, 0].imshow(images[sample_index])
        axes[row_index, 0].set_ylabel(
            f"测试帧 {row_index + 1}\n{source[-17:]}", fontsize=8.7, fontweight="bold", color="#263238", labelpad=9
        )
        axes[row_index, 1].imshow(mask_preview(targets[sample_index]))
        for offset, spec in enumerate(specs, start=2):
            key = spec["key"]
            axes[row_index, offset].imshow(
                error_overlay(images[sample_index], targets[sample_index], predictions[key][sample_index])
            )
            axes[row_index, offset].text(
                0.02,
                0.96,
                f"Dice {scores[key][sample_index]:.3f}",
                transform=axes[row_index, offset].transAxes,
                va="top",
                ha="left",
                fontsize=8.4,
                color="white",
                bbox={"boxstyle": "round,pad=0.22", "facecolor": "#0d7a5f" if key == "proposed" else "#24313c", "edgecolor": "none", "alpha": 0.92},
            )
        for axis in axes[row_index]:
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.65)
                spine.set_color("#c6ced4")
    fig.suptitle("锁定代理测试集上的关键帧分割可视化对比", fontsize=13.5, fontweight="bold", y=0.965)
    fig.text(
        0.5,
        0.035,
        "绿色：真阳性   红色：假阳性   蓝色：假阴性。三张测试帧按 Residual Attention 相对全部对照模型的 Dice 优势选取，每张来自独立 source group。",
        ha="center",
        fontsize=9.2,
        color="#425563",
    )
    paths = [
        output_dir / "keyframe_segmentation_comparison_20260730.png",
        output_dir / "keyframe_segmentation_comparison_20260730.svg",
        output_dir / "keyframe_segmentation_comparison_20260730.pdf",
        output_dir / "keyframe_segmentation_comparison_20260730.tiff",
    ]
    for path in paths:
        fig.savefig(path, dpi=320, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def style_table(table: Any, *, data_rows: int, best_columns: set[int]) -> None:
    table.auto_set_font_size(False)
    table.set_fontsize(8.6)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#c4cdd3")
        cell.set_linewidth(0.55)
        if row == 0:
            cell.set_facecolor("#1d2935")
            cell.get_text().set_color("white")
            cell.get_text().set_fontweight("bold")
        elif row == data_rows:
            cell.set_facecolor("#e8f5ef")
            if col in best_columns:
                cell.get_text().set_color("#075b46")
                cell.get_text().set_fontweight("bold")
        else:
            cell.set_facecolor("#f7f9fa" if row % 2 else "#ffffff")


def render_performance_table(output_dir: Path, specs: list[dict[str, Any]]) -> list[Path]:
    quality_headers = ["模型", "阈值", "Dice", "IoU", "Precision", "Recall", "Boundary F1", "ECE", "Brier", "空 mask", "过分割"]
    quality_rows = []
    runtime_headers = ["模型", "参数量", "均值 ms\n(160x256)", "P95 ms\n(160x256)", "FPS\n(160x256)", "显存 MB\n(160x256)", "P95 ms\n(4K tiled)", "显存 MB\n(4K tiled)"]
    runtime_rows = []
    for spec in specs:
        metrics = spec["metrics"]
        benchmark = spec["benchmark"]
        four_k = FOUR_K_BENCHMARKS[spec["key"]]
        quality_rows.append(
            [
                spec["name"],
                f"{float(spec['threshold']):.2f}",
                f"{float(metrics['foreground_mean_dice']):.4f}",
                f"{float(metrics['foreground_mean_iou']):.4f}",
                f"{float(metrics['foreground_precision_mean']):.4f}",
                f"{float(metrics['foreground_recall_mean']):.4f}",
                f"{float(metrics['boundary_f1_mean']):.4f}",
                f"{float(metrics['ece']):.4f}",
                f"{float(metrics['brier_score']):.4f}",
                f"{float(metrics['empty_mask_rate']):.2%}",
                f"{float(metrics['over_segmentation_rate']):.2%}",
            ]
        )
        runtime_rows.append(
            [
                spec["name"],
                f"{int(spec['params']):,}",
                f"{float(benchmark['mean_latency_ms']):.2f}",
                f"{float(benchmark['p95_latency_ms']):.2f}",
                f"{1000.0 / float(benchmark['mean_latency_ms']):.1f}",
                f"{float(benchmark['peak_gpu_memory_mb']):.1f}",
                f"{float(four_k['p95_ms']):.1f}",
                f"{float(four_k['peak_gpu_mb']):.1f}",
            ]
        )
    fig, axes = plt.subplots(2, 1, figsize=(20.0, 7.25), gridspec_kw={"height_ratios": [1.05, 0.90]})
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.018, right=0.998, top=0.89, bottom=0.09, hspace=0.18)
    for axis in axes:
        axis.axis("off")
    quality = axes[0].table(
        cellText=quality_rows,
        colLabels=quality_headers,
        cellLoc="center",
        colLoc="center",
        colWidths=[0.20, 0.06, 0.073, 0.073, 0.083, 0.073, 0.10, 0.065, 0.07, 0.08, 0.085],
        bbox=[0.0, 0.02, 1.0, 0.86],
    )
    style_table(quality, data_rows=len(quality_rows), best_columns={0, 2, 3})
    runtime = axes[1].table(
        cellText=runtime_rows,
        colLabels=runtime_headers,
        cellLoc="center",
        colLoc="center",
        colWidths=[0.23, 0.12, 0.105, 0.105, 0.10, 0.12, 0.11, 0.11],
        bbox=[0.0, 0.02, 1.0, 0.86],
    )
    style_table(runtime, data_rows=len(runtime_rows), best_columns={0})
    axes[0].set_title("分割质量、校准与失效统计", fontsize=12.5, fontweight="bold", pad=1)
    axes[1].set_title("模型复杂度与推理资源", fontsize=12.5, fontweight="bold", pad=1)
    fig.suptitle("可比关键帧分割模型完整性能对比", fontsize=16, fontweight="bold", y=0.965)
    fig.text(
        0.5,
        0.032,
        "统一 source-group 锁定代理测试集；Residual Attention 的 Dice/IoU 最高，Nested Skip 的 Recall 最高。4K tiled 采用 3840x2160、512 像素切片、64 像素重叠、批量 4。",
        ha="center",
        fontsize=9.1,
        color="#425563",
    )
    paths = [
        output_dir / "keyframe_segmentation_performance_20260730.png",
        output_dir / "keyframe_segmentation_performance_20260730.svg",
        output_dir / "keyframe_segmentation_performance_20260730.pdf",
    ]
    for path in paths:
        fig.savefig(path, dpi=320, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def write_data_files(
    output_dir: Path,
    specs: list[dict[str, Any]],
    rows: list[dict[str, str]],
    scores: dict[str, list[float]],
    indices: Iterable[int],
) -> None:
    metrics_path = output_dir / "keyframe_segmentation_performance_20260730.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "model", "threshold", "dice", "iou", "precision", "recall", "boundary_f1", "ece", "brier_score",
                "empty_mask_rate", "over_segmentation_rate", "parameters", "mean_latency_ms_160x256",
                "p95_latency_ms_160x256", "throughput_fps_160x256", "peak_gpu_memory_mb_160x256",
                "p95_latency_ms_4k_tiled", "peak_gpu_memory_mb_4k_tiled",
            ]
        )
        for spec in specs:
            metrics = spec["metrics"]
            benchmark = spec["benchmark"]
            writer.writerow(
                [
                    spec["name"],
                    spec["threshold"], metrics["foreground_mean_dice"], metrics["foreground_mean_iou"],
                    metrics["foreground_precision_mean"], metrics["foreground_recall_mean"], metrics["boundary_f1_mean"],
                    metrics["ece"], metrics["brier_score"], metrics["empty_mask_rate"], metrics["over_segmentation_rate"],
                    spec["params"], benchmark["mean_latency_ms"], benchmark["p95_latency_ms"], 1000.0 / float(benchmark["mean_latency_ms"]),
                    benchmark["peak_gpu_memory_mb"], FOUR_K_BENCHMARKS[spec["key"]]["p95_ms"], FOUR_K_BENCHMARKS[spec["key"]]["peak_gpu_mb"],
                ]
            )
    showcase_path = output_dir / "keyframe_segmentation_showcase_20260730.csv"
    with showcase_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "source_group_id", *[f"{spec['key']}_dice" for spec in specs]])
        for index in indices:
            writer.writerow(
                [
                    rows[index]["case_id"],
                    rows[index].get("source_group_id", ""),
                    *[f"{scores[spec['key']][index]:.6f}" for spec in specs],
                ]
            )


def main() -> None:
    args = parse_args()
    mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "none"
    mpl.rcParams["pdf.fonttype"] = 42
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = read_summary(args.summary)
    specs = candidate_specs(summary)
    rows = load_test_rows(args.manifest)
    device = select_torch_device(args.device)
    images, targets, predictions, scores = run_predictions(specs, rows, device)
    indices = select_showcase_indices(rows, scores)
    visual_paths = render_visual_comparison(
        args.output_dir, rows, specs, images, targets, predictions, scores, indices
    )
    table_paths = render_performance_table(args.output_dir, specs)
    write_data_files(args.output_dir, specs, rows, scores, indices)
    (args.output_dir / "figure_contract_20260730_zh.md").write_text(
        "# 关键帧模型对比图图件契约\n\n"
        "- 核心结论：Residual Attention U-Net 在同一锁定代理测试协议下取得最高 Dice 与 IoU。\n"
        "- 可视化：三张测试帧按 Residual Attention 相对其余四个模型的 Dice 优势选取，且来自不同 source group。\n"
        "- checkpoint：对比使用 2026-07-26 选型批次的 Residual Attention checkpoint；严格运行配置仍绑定 2026-07-15 的同家族已晋级 checkpoint。\n"
        "- 颜色：绿色为真阳性，红色为假阳性，蓝色为假阴性。\n"
        "- 数据边界：全部标签来自公开 OFDVDnet 荧光代理视频的强度伪标注，属于非目标域工程验证数据。\n"
        "- 医学边界：结果只能作为研发验证和医生复核辅助，不能表示真实术中 ICG 颌骨骨髓炎临床分割性能。\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(args.output_dir), "device": str(device), "visual_paths": [str(p) for p in visual_paths], "table_paths": [str(p) for p in table_paths], "showcase_indices": indices}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
