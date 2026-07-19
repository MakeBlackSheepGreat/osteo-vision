from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

from src.core.paths import ensure_dir, resolve_path
from src.datasets.ofdvdnet import DOMAIN_BOUNDARY, OFDVDnetRecord, read_ofdvdnet_manifest, read_ofdvdnet_sample
from src.preprocess.fluorescence import blend_pseudocolor_on_reference, enhance_fluorescence_signal

DEFAULT_MANIFEST = "research/literature/inventory/ofdvdnet_video_manifest_20260704.csv"
DEFAULT_OUTPUT_DIR = (
    "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/ofdvdnet/baseline_enhancement"
)
DEFAULT_BASELINE_MANIFEST = "research/literature/inventory/ofdvdnet_fluorescence_baseline_manifest_20260704.csv"
DEFAULT_REPORT_DIR = "research/reports/modeling"

BASELINE_FIELDS = [
    "record_id",
    "split",
    "video_path",
    "frame_index",
    "timestamp_sec",
    "reference_path",
    "fluorescence_enhanced_path",
    "pseudo_color_path",
    "fusion_overlay_path",
    "threshold",
    "mean_intensity",
    "max_intensity",
    "p95_intensity",
    "positive_area_px",
    "positive_area_fraction",
    "method",
    "domain_boundary",
]


def run_ofdvdnet_fluorescence_baseline(
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    baseline_manifest_path: str | Path = DEFAULT_BASELINE_MANIFEST,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
    max_records: int | None = None,
    frame_position: float = 0.5,
    threshold: float = 0.6,
    colormap: str = "green",
    alpha: float = 0.45,
) -> dict[str, Any]:
    records = read_ofdvdnet_manifest(resolve_path(manifest_path), readable_only=True)
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No readable OFDVDnet records were found for fluorescence baseline processing.")

    baseline_root = ensure_dir(resolve_path(output_dir))
    rows = [
        process_record(
            record,
            output_dir=baseline_root / record.record_id,
            frame_position=frame_position,
            threshold=threshold,
            colormap=colormap,
            alpha=alpha,
        )
        for record in records
    ]
    baseline_manifest = resolve_path(baseline_manifest_path)
    write_csv(baseline_manifest, rows, BASELINE_FIELDS)
    summary = summarize_rows(rows)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_manifest_path": str(resolve_path(manifest_path)),
        "baseline_manifest_path": str(baseline_manifest),
        "output_dir": str(baseline_root),
        "processed_record_count": len(rows),
        "frame_position": frame_position,
        "threshold": threshold,
        "colormap": colormap,
        "alpha": alpha,
        "method": "crop_fluorescence_view__gaussian_denoise__percentile_normalize__clahe__pseudocolor__reference_overlay",
        "summary": summary,
        "domain_boundary": DOMAIN_BOUNDARY,
    }
    report_paths = write_reports(payload, report_dir=resolve_path(report_dir))
    return {**payload, "report_paths": report_paths}


def process_record(
    record: OFDVDnetRecord,
    *,
    output_dir: Path,
    frame_position: float,
    threshold: float,
    colormap: str,
    alpha: float,
) -> dict[str, Any]:
    ensure_dir(output_dir)
    sample = read_ofdvdnet_sample(record, relative_position=frame_position)
    views = sample["views"]
    enhanced = enhance_fluorescence_signal(views["fluorescence"], threshold=threshold, colormap=colormap)
    fusion = blend_pseudocolor_on_reference(views["reference"], enhanced["pseudo_color"], alpha=alpha)

    reference_path = output_dir / f"{record.record_id}_reference.jpg"
    enhanced_path = output_dir / f"{record.record_id}_fluorescence_enhanced.jpg"
    pseudo_path = output_dir / f"{record.record_id}_pseudo_color.jpg"
    fusion_path = output_dir / f"{record.record_id}_fusion_overlay.jpg"
    _save_rgb(reference_path, views["reference"])
    _save_gray(enhanced_path, enhanced["enhanced_uint8"])
    _save_rgb(pseudo_path, enhanced["pseudo_color"])
    _save_rgb(fusion_path, fusion)

    quantification = enhanced["quantification"]
    return {
        "record_id": record.record_id,
        "split": record.split,
        "video_path": str(record.video_path),
        "frame_index": sample["frame_index"],
        "timestamp_sec": sample["timestamp_sec"],
        "reference_path": str(reference_path),
        "fluorescence_enhanced_path": str(enhanced_path),
        "pseudo_color_path": str(pseudo_path),
        "fusion_overlay_path": str(fusion_path),
        "threshold": quantification["threshold"],
        "mean_intensity": quantification["mean_intensity"],
        "max_intensity": quantification["max_intensity"],
        "p95_intensity": quantification["p95_intensity"],
        "positive_area_px": quantification["positive_area_px"],
        "positive_area_fraction": quantification["positive_area_fraction"],
        "method": quantification["source"],
        "domain_boundary": record.domain_boundary,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_fractions = [_float(row["positive_area_fraction"]) for row in rows]
    p95_values = [_float(row["p95_intensity"]) for row in rows]
    mean_values = [_float(row["mean_intensity"]) for row in rows]
    return {
        "mean_positive_area_fraction": float(np.mean(positive_fractions)) if positive_fractions else None,
        "mean_p95_intensity": float(np.mean(p95_values)) if p95_values else None,
        "mean_intensity": float(np.mean(mean_values)) if mean_values else None,
        "records_with_nonzero_positive_area": int(sum(value > 0 for value in positive_fractions)),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_reports(payload: dict[str, Any], *, report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh_path = report_dir / "ofdvdnet_fluorescence_baseline_20260704_zh.md"
    en_path = report_dir / "ofdvdnet_fluorescence_baseline_20260704_en.md"
    zh_path.write_text(render_report(payload, language="zh"), encoding="utf-8")
    en_path.write_text(render_report(payload, language="en"), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def render_report(payload: dict[str, Any], *, language: str) -> str:
    summary = payload["summary"]
    if language == "zh":
        lines = [
            "# OFDVDnet 荧光增强 Baseline 报告",
            "",
            "## 处理结果",
            "",
            f"- 处理视频记录数：{payload['processed_record_count']}",
            f"- 源 manifest：`{payload['source_manifest_path']}`",
            f"- baseline manifest：`{payload['baseline_manifest_path']}`",
            f"- 输出目录：`{payload['output_dir']}`",
            f"- 抽帧位置：视频相对位置 `{payload['frame_position']}`",
            f"- 阈值 / 伪彩 / 融合透明度：`{payload['threshold']}` / `{payload['colormap']}` / `{payload['alpha']}`",
            "",
            "## 方法",
            "",
            "对 OFDVDnet 三视图视频读取中间帧，裁剪右上角荧光视图和左下角参考视图；荧光视图经过高斯去噪、百分位归一化、CLAHE 对比度增强、伪彩映射后，与参考视图进行 alpha 融合。",
            "",
            "## 汇总指标",
            "",
            f"- 平均阳性面积比例：`{summary['mean_positive_area_fraction']}`",
            f"- 平均 P95 强度：`{summary['mean_p95_intensity']}`",
            f"- 平均强度：`{summary['mean_intensity']}`",
            f"- 非零阳性面积记录数：`{summary['records_with_nonzero_positive_area']}`",
            "",
            "## 医学边界",
            "",
            payload["domain_boundary"],
            "",
            "该 baseline 只用于多模态荧光处理中的增强、伪彩稳定性和证据展示链路验证，禁止作为颌骨骨髓炎诊断模型性能。",
        ]
    else:
        lines = [
            "# OFDVDnet Fluorescence Enhancement Baseline Report",
            "",
            "## Result",
            "",
            f"- Processed records: {payload['processed_record_count']}",
            f"- Source manifest: `{payload['source_manifest_path']}`",
            f"- Baseline manifest: `{payload['baseline_manifest_path']}`",
            f"- Output directory: `{payload['output_dir']}`",
            f"- Frame position: `{payload['frame_position']}`",
            f"- Threshold / colormap / alpha: `{payload['threshold']}` / `{payload['colormap']}` / `{payload['alpha']}`",
            "",
            "## Method",
            "",
            "The baseline samples the middle frame, crops the top-right fluorescence view and bottom-left reference view, applies Gaussian denoising, percentile normalization, CLAHE contrast enhancement, pseudo-color mapping, and alpha overlay on the reference view.",
            "",
            "## Summary Metrics",
            "",
            f"- Mean positive area fraction: `{summary['mean_positive_area_fraction']}`",
            f"- Mean P95 intensity: `{summary['mean_p95_intensity']}`",
            f"- Mean intensity: `{summary['mean_intensity']}`",
            f"- Records with nonzero positive area: `{summary['records_with_nonzero_positive_area']}`",
            "",
            "## Medical Boundary",
            "",
            payload["domain_boundary"],
            "",
            "This baseline is only for track-1 fluorescence enhancement, pseudo-color stability, and evidence-display validation. It is not jaw-osteomyelitis diagnostic model performance.",
        ]
    return "\n".join(lines) + "\n"


def _save_rgb(path: Path, image: Any) -> None:
    ensure_dir(path.parent)
    Image.fromarray(np.asarray(image, dtype=np.uint8)).save(path, quality=94)


def _save_gray(path: Path, image: Any) -> None:
    ensure_dir(path.parent)
    Image.fromarray(np.asarray(image, dtype=np.uint8)).save(path, quality=94)


def _float(value: Any) -> float:
    return float(value) if value not in {"", None} else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OFDVDnet fluorescence enhancement baseline.")
    parser.add_argument("--manifest-path", default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--baseline-manifest-path", default=DEFAULT_BASELINE_MANIFEST)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--frame-position", type=float, default=0.5)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--colormap", default="green", choices=["green", "amber", "magenta"])
    parser.add_argument("--alpha", type=float, default=0.45)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_ofdvdnet_fluorescence_baseline(
        manifest_path=args.manifest_path,
        output_dir=args.output_dir,
        baseline_manifest_path=args.baseline_manifest_path,
        report_dir=args.report_dir,
        max_records=args.max_records,
        frame_position=args.frame_position,
        threshold=args.threshold,
        colormap=args.colormap,
        alpha=args.alpha,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
