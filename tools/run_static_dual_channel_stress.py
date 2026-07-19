from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

from src.models.dual_channel_segmenter import (  # noqa: E402
    DUAL_CHANNEL_MODES,
    load_dual_channel_checkpoint,
)
from src.models.keyframe_segmenter import checkpoint_sha256, select_torch_device  # noqa: E402
from src.preprocess.fluorescence import apply_fluorescence_colormap, blend_pseudocolor_on_reference  # noqa: E402

DEFAULT_MANIFEST = ROOT / "research/datasets/public-candidates/d047_d048_static_paired_preview_manifest.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts/checkpoints/osteo_vision/dual_channel_proxy_20260710.pt"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts/platform_smoke/static_dual_channel_stress_20260711"
DEFAULT_REPORT_DIR = ROOT / "research/reports/modeling"


def run_static_dual_channel_stress(
    manifest_path: str | Path,
    checkpoint_path: str | Path,
    output_dir: str | Path,
    report_dir: str | Path,
    *,
    image_shape: tuple[int, int] = (128, 176),
    threshold: float = 0.5,
    device_policy: str = "auto",
) -> dict[str, Any]:
    manifest = Path(manifest_path).resolve()
    checkpoint = Path(checkpoint_path).resolve()
    output = Path(output_dir).resolve()
    reports = Path(report_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    pairs = [row for row in payload.get("pairs", []) if isinstance(row, dict)]
    if not pairs:
        raise ValueError("No complete paired preview records were found")
    device = select_torch_device(device_policy)
    model, checkpoint_metadata = load_dual_channel_checkpoint(checkpoint, device=device)
    rows = [
        _evaluate_pair(
            model,
            pair,
            device=device,
            output_dir=output,
            image_shape=image_shape,
            threshold=threshold,
        )
        for pair in pairs
    ]
    flag_counts = Counter(flag for row in rows for flag in row["risk_flags"])
    registration_counts = Counter(str(row["registration"]["status"]) for row in rows)
    mode_summary = {
        mode: {
            "mean_probability": _mean(row["modes"][mode]["mean_probability"] for row in rows),
            "mean_positive_fraction": _mean(row["modes"][mode]["positive_fraction"] for row in rows),
            "empty_mask_rate": _mean(row["modes"][mode]["positive_fraction"] <= 0.0 for row in rows),
            "full_mask_rate": _mean(row["modes"][mode]["positive_fraction"] >= 0.95 for row in rows),
        }
        for mode in DUAL_CHANNEL_MODES
    }
    result = {
        "schema_version": "osteo-vision-static-dual-channel-stress-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest),
        "manifest_checksum": _sha256_file(manifest),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256(checkpoint),
        "checkpoint_selected_mode": checkpoint_metadata.get("selected_mode"),
        "runtime_allowed": False,
        "offline_benchmark_only": True,
        "device": str(device),
        "image_shape": {"height": image_shape[0], "width": image_shape[1]},
        "threshold": threshold,
        "pair_count": len(rows),
        "pair_alignment_counts": dict(Counter(str(row["pair_alignment"]) for row in rows)),
        "registration_status_counts": dict(registration_counts),
        "risk_flag_counts": dict(flag_counts),
        "mode_summary": mode_summary,
        "mean_cross_mode_mae": {
            key: _mean(row["cross_mode_mae"][key] for row in rows)
            for key in (
                "white_vs_fluorescence",
                "early_vs_fluorescence",
                "intermediate_vs_fluorescence",
                "context_vs_fluorescence",
            )
        },
        "rows": rows,
        "clinical_claim_allowed": False,
        "medical_boundary": (
            "This benchmark uses publication-derived near-domain pairs without pixel alignment or disease masks. "
            "It measures engineering stability only and cannot support segmentation accuracy or clinical claims."
        ),
    }
    json_path = output / "static_dual_channel_stress.json"
    _write_json(json_path, result)
    result["json_path"] = str(json_path)
    zh_path = reports / "static_dual_channel_near_domain_stress_20260711_zh.md"
    en_path = reports / "static_dual_channel_near_domain_stress_20260711_en.md"
    zh_path.write_text(_report_zh(result), encoding="utf-8")
    en_path.write_text(_report_en(result), encoding="utf-8")
    result["report_zh_path"] = str(zh_path)
    result["report_en_path"] = str(en_path)
    return result


def _evaluate_pair(
    model: torch.nn.Module,
    pair: dict[str, Any],
    *,
    device: torch.device,
    output_dir: Path,
    image_shape: tuple[int, int],
    threshold: float,
) -> dict[str, Any]:
    height, width = image_shape
    white_path = Path(str(pair["white_image_path"])).resolve()
    fluorescence_path = Path(str(pair["fluorescence_image_path"])).resolve()
    with Image.open(white_path) as white_obj, Image.open(fluorescence_path) as fluorescence_obj:
        white_original_size = {"width": white_obj.width, "height": white_obj.height}
        fluorescence_original_size = {"width": fluorescence_obj.width, "height": fluorescence_obj.height}
        white = np.asarray(white_obj.convert("RGB").resize((width, height), Image.Resampling.BILINEAR))
        fluorescence_rgb = np.asarray(
            fluorescence_obj.convert("RGB").resize((width, height), Image.Resampling.BILINEAR)
        )
    fluorescence = cv2.cvtColor(fluorescence_rgb, cv2.COLOR_RGB2GRAY)
    white_gray = cv2.cvtColor(white, cv2.COLOR_RGB2GRAY)
    white_tensor = torch.from_numpy(white.transpose(2, 0, 1)[None].astype(np.float32) / 255.0).to(device)
    fluorescence_tensor = torch.from_numpy(fluorescence[None, None].astype(np.float32) / 255.0).to(device)
    probabilities: dict[str, np.ndarray] = {}
    mode_metrics: dict[str, dict[str, float]] = {}
    with torch.no_grad():
        for mode in DUAL_CHANNEL_MODES:
            probability = torch.sigmoid(model(white_tensor, fluorescence_tensor, mode=mode))[0, 0].cpu().numpy()
            probabilities[mode] = probability
            mode_metrics[mode] = {
                "mean_probability": float(probability.mean()),
                "max_probability": float(probability.max()),
                "positive_fraction": float((probability >= threshold).mean()),
                "mean_entropy": float(_binary_entropy(probability).mean()),
            }
    alignment = str(pair.get("pair_alignment") or "unverified")
    registration = _registration_probe(white_gray, fluorescence, alignment=alignment)
    cross_mode_mae = {
        "white_vs_fluorescence": float(np.abs(probabilities["white_only"] - probabilities["fluorescence_only"]).mean()),
        "early_vs_fluorescence": float(
            np.abs(probabilities["early_fusion"] - probabilities["fluorescence_only"]).mean()
        ),
        "intermediate_vs_fluorescence": float(
            np.abs(probabilities["intermediate_fusion"] - probabilities["fluorescence_only"]).mean()
        ),
        "context_vs_fluorescence": float(
            np.abs(probabilities["context_fusion"] - probabilities["fluorescence_only"]).mean()
        ),
    }
    risk_flags: list[str] = []
    if float(fluorescence.std()) < 12.0:
        risk_flags.append("low_fluorescence_dynamic_range")
    if cross_mode_mae["early_vs_fluorescence"] > 0.15:
        risk_flags.append("early_fusion_high_disagreement")
    if cross_mode_mae["intermediate_vs_fluorescence"] > 0.15:
        risk_flags.append("intermediate_fusion_high_disagreement")
    if cross_mode_mae["context_vs_fluorescence"] > 0.15:
        risk_flags.append("context_fusion_high_disagreement")
    if cross_mode_mae["context_vs_fluorescence"] < 0.005:
        risk_flags.append("context_fusion_low_white_sensitivity")
    if any(metrics["positive_fraction"] <= 0.0 for metrics in mode_metrics.values()):
        risk_flags.append("empty_prediction_mode")
    if any(metrics["positive_fraction"] >= 0.95 for metrics in mode_metrics.values()):
        risk_flags.append("near_full_prediction_mode")
    if registration["status"] in {"failed", "weak"}:
        risk_flags.append("pair_registration_unreliable")
    if alignment == "weak_sequential":
        risk_flags.append("weak_sequential_pair")
    safe_pair = _safe_name(str(pair["pair_id"]))
    probability_path = output_dir / f"{safe_pair}_early_fusion_probability.png"
    overlay_path = output_dir / f"{safe_pair}_early_fusion_overlay.png"
    Image.fromarray(np.clip(probabilities["early_fusion"] * 255, 0, 255).astype(np.uint8)).save(probability_path)
    pseudo = apply_fluorescence_colormap(probabilities["early_fusion"], "green")
    Image.fromarray(blend_pseudocolor_on_reference(white, pseudo, alpha=0.45)).save(overlay_path)
    return {
        "pair_id": str(pair["pair_id"]),
        "source_group_id": str(pair.get("source_group_id") or ""),
        "pair_alignment": alignment,
        "white_image_path": str(white_path),
        "fluorescence_image_path": str(fluorescence_path),
        "white_original_size": white_original_size,
        "fluorescence_original_size": fluorescence_original_size,
        "input_quality": {
            "white_laplacian_variance": float(cv2.Laplacian(white_gray, cv2.CV_64F).var()),
            "fluorescence_laplacian_variance": float(cv2.Laplacian(fluorescence, cv2.CV_64F).var()),
            "fluorescence_mean": float(fluorescence.mean()),
            "fluorescence_std": float(fluorescence.std()),
            "fluorescence_saturation_fraction": float((fluorescence >= 250).mean()),
        },
        "registration": registration,
        "modes": mode_metrics,
        "cross_mode_mae": cross_mode_mae,
        "risk_flags": sorted(set(risk_flags)),
        "probability_path": str(probability_path),
        "overlay_path": str(overlay_path),
        "ground_truth_available": False,
        "training_eligible": False,
    }


def _registration_probe(white: np.ndarray, fluorescence: np.ndarray, *, alignment: str) -> dict[str, Any]:
    if alignment in {"weak_sequential", "sequential"}:
        return {"status": "skipped", "reason": f"alignment_{alignment}", "match_count": 0, "inlier_ratio": None}
    orb = cv2.ORB_create(nfeatures=600)
    keypoints_white, descriptors_white = orb.detectAndCompute(white, None)
    keypoints_fluorescence, descriptors_fluorescence = orb.detectAndCompute(fluorescence, None)
    if descriptors_white is None or descriptors_fluorescence is None:
        return {"status": "failed", "reason": "missing_descriptors", "match_count": 0, "inlier_ratio": None}
    matches = sorted(
        cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(descriptors_white, descriptors_fluorescence),
        key=lambda match: match.distance,
    )[:100]
    if len(matches) < 8:
        return {"status": "failed", "reason": "insufficient_matches", "match_count": len(matches), "inlier_ratio": None}
    source = np.float32([keypoints_white[match.queryIdx].pt for match in matches]).reshape(-1, 1, 2)
    target = np.float32([keypoints_fluorescence[match.trainIdx].pt for match in matches]).reshape(-1, 1, 2)
    _homography, inliers = cv2.findHomography(source, target, cv2.RANSAC, 4.0)
    if inliers is None:
        return {"status": "failed", "reason": "homography_failed", "match_count": len(matches), "inlier_ratio": None}
    inlier_ratio = float(inliers.mean())
    status = "pass" if len(matches) >= 20 and inlier_ratio >= 0.35 else "weak"
    return {
        "status": status,
        "reason": "orb_homography_probe",
        "match_count": len(matches),
        "inlier_ratio": inlier_ratio,
    }


def _binary_entropy(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(probability, 1e-6, 1.0 - 1e-6)
    return -(clipped * np.log(clipped) + (1.0 - clipped) * np.log(1.0 - clipped))


def _mean(values: Any) -> float:
    items = [float(value) for value in values]
    return float(np.mean(items)) if items else math.nan


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_zh(result: dict[str, Any]) -> str:
    flags = result["risk_flag_counts"]
    return f"""# 静态近域双通道压力评估报告

生成时间：{result['generated_at_utc']}

## 结果摘要

- 真实公开近域白光/荧光配对：{result['pair_count']} 对。
- 配对边界：{json.dumps(result['pair_alignment_counts'], ensure_ascii=False)}。
- 配准探针：{json.dumps(result['registration_status_counts'], ensure_ascii=False)}。
- 风险标记：{json.dumps(flags, ensure_ascii=False)}。
- checkpoint SHA256：`{result['checkpoint_sha256']}`。
- 双通道 checkpoint 继续保持 `runtime_allowed=false`，本轮只执行离线压力评估。

## 方法

每对图像使用固定尺寸输入五种模式：`white_only`、`fluorescence_only`、`early_fusion`、`intermediate_fusion`、`context_fusion`。其中 `context_fusion` 只使用白光全局上下文调制荧光特征，避免依赖像素对齐。报告各模式平均概率、阳性面积比例和预测熵，同时计算跨模式概率差异。近似同视野配对使用 ORB 与 RANSAC 单应探针；弱时序配对跳过像素配准。

## 工程结论

- 这些数据已经替换了压力评估中的合成白光输入，能够直接暴露模型面对真实口腔/骨荧光近域图像时的退化与模式冲突。
- `context_fusion` 与荧光单模态的平均概率差异约为 {result['mean_cross_mode_mae']['context_vs_fluorescence']:.4f}，空间错配敏感性较低；差异过小同时提示白光贡献可能不足，当前不能作为双通道增益证据。
- 配对均缺少像素级病灶 mask，当前无法计算 Dice、IoU 或边界误差。
- `weak_sequential` 和 `approximate_view` 记录不进入像素配准监督。
- 出版物箭头、字母和比例框可能影响预测，后续需加入遮挡增强和人工复核。

## 证据

- JSON：`{result['json_path']}`
- 配对 manifest：`{result['manifest_path']}`
- checkpoint：`{result['checkpoint_path']}`

## 医学边界

该评估只描述非目标域近域输入下的工程稳定性，不提供病灶识别准确性或临床性能结论。
"""


def _report_en(result: dict[str, Any]) -> str:
    return f"""# Static Near-Domain Dual-Channel Stress Evaluation

Generated: {result['generated_at_utc']}

## Summary

- Publication-derived near-domain white-light/fluorescence pairs: {result['pair_count']}.
- Pair alignments: {json.dumps(result['pair_alignment_counts'])}.
- Registration probe: {json.dumps(result['registration_status_counts'])}.
- Risk flags: {json.dumps(result['risk_flag_counts'])}.
- Checkpoint SHA256: `{result['checkpoint_sha256']}`.
- The dual-channel checkpoint remains `runtime_allowed=false`; this run is an offline stress evaluation.

## Method

Each pair is evaluated with white-only, fluorescence-only, early-fusion, intermediate-fusion, and context-fusion modes. Context fusion uses global white-light context to avoid pixel-alignment dependence. The report records probability statistics, positive-area fractions, entropy, and cross-mode disagreement. ORB/RANSAC homography is used only as a feasibility probe for approximate-view pairs. Sequential pairs skip pixel registration.

## Boundary

These pairs replace synthetic white-light inputs in the stress test and expose near-domain failure modes. Context fusion differs from fluorescence-only output by {result['mean_cross_mode_mae']['context_vs_fluorescence']:.4f} on average; this indicates alignment stability and possible low white-light sensitivity. It does not demonstrate a causal dual-channel benefit. The pairs have no pixel disease masks and cannot provide Dice, IoU, boundary error, or clinical performance evidence. Publication annotations may create shortcut features and require later occlusion augmentation and authorized review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dual-channel stress evaluation on static near-domain pairs.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--image-shape", default="128x176")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu", "cuda"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    height, width = (int(value) for value in args.image_shape.lower().replace(",", "x").split("x"))
    result = run_static_dual_channel_stress(
        args.manifest,
        args.checkpoint,
        args.output_dir,
        args.report_dir,
        image_shape=(height, width),
        threshold=args.threshold,
        device_policy=args.device,
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "pair_count",
                    "pair_alignment_counts",
                    "registration_status_counts",
                    "risk_flag_counts",
                    "mean_cross_mode_mae",
                    "json_path",
                    "report_zh_path",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
