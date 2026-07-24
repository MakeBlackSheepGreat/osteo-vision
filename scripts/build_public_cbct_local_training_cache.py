from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

from scripts.preprocess_public_cbct_datasets import build_dolchid_cases, build_toothfairy2_cases
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.datasets.manifests import read_manifest
from osteo_vision_core.reports.writers import write_json

PROJECT_DATASET_ROOT = Path("research/datasets/public-candidates")
ARCHIVE_DATASET_ROOT = Path("D:/projects/osteo-vision/research/datasets/public-candidates")
REPORT_DIR = Path("research/reports/preprocessing")
CACHE_MANIFEST_FIELDS = [
    "case_id",
    "input_path",
    "label",
    "task_type",
    "input_type",
    "modality",
    "mask_path",
    "split",
    "fold",
    "label_source",
    "dataset_id",
    "cache_path",
    "source_image_path",
    "source_mask_path",
    "diagnosis_group",
    "original_shape",
    "original_spacing",
    "target_shape",
    "label_values",
]


def parse_target_shape(value: str) -> tuple[int, int, int]:
    normalized = value.lower().replace(",", "x")
    parts = [part.strip() for part in normalized.split("x") if part.strip()]
    if len(parts) != 3:
        raise ValueError(f"Expected target shape like 64x64x64, got: {value}")
    shape = tuple(int(part) for part in parts)
    if any(item <= 0 for item in shape):
        raise ValueError(f"Target shape must contain positive integers, got: {value}")
    return shape  # type: ignore[return-value]


def resize_volume(volume: np.ndarray, target_shape: tuple[int, int, int], *, order: int) -> np.ndarray:
    if tuple(volume.shape) == target_shape:
        return np.asarray(volume).copy()
    zoom = [target / source for target, source in zip(target_shape, volume.shape)]
    return ndi.zoom(volume, zoom, order=order)


def normalize_image(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros_like(data, dtype=np.float32)
    low = float(np.percentile(finite, 0.5))
    high = float(np.percentile(finite, 99.5))
    if high <= low:
        low = float(np.min(finite))
        high = float(np.max(finite))
    if high <= low:
        return np.zeros_like(data, dtype=np.float32)
    clipped = np.clip(data, low, high)
    return ((clipped - low) / (high - low) * 2.0 - 1.0).astype(np.float32)


def write_npz_cache(
    image: np.ndarray,
    label: np.ndarray,
    cache_path: Path,
    target_shape: tuple[int, int, int],
    *,
    spacing: Iterable[float],
) -> dict[str, Any]:
    ensure_dir(cache_path.parent)
    image_small = resize_volume(np.asarray(image, dtype=np.float32), target_shape, order=1)
    label_small = resize_volume(np.asarray(label, dtype=np.int16), target_shape, order=0).astype(np.int16)
    image_small = normalize_image(image_small).astype(np.float16)
    label_values = np.unique(label_small).astype(int).tolist()
    np.savez_compressed(
        cache_path,
        image=image_small,
        label=label_small,
        original_shape=np.asarray(image.shape, dtype=np.int32),
        target_shape=np.asarray(target_shape, dtype=np.int32),
        original_spacing=np.asarray(list(spacing), dtype=np.float32),
        label_values=np.asarray(label_values, dtype=np.int16),
    )
    return {
        "original_shape": format_tuple(image.shape),
        "original_spacing": format_tuple(round(float(item), 6) for item in spacing),
        "target_shape": format_tuple(target_shape),
        "label_values": "|".join(str(value) for value in label_values),
    }


def build_d024_cache_manifest(project_dataset_root: Path, target_shape: tuple[int, int, int]) -> dict[str, Any]:
    dataset_dir = project_dataset_root / "d024_dentvoxel"
    cache_dir = dataset_dir / "derived" / "nnunet" / "monai_cache" / f"jaw_roi_{target_shape[0]}"
    shape_suffix = "x".join(map(str, target_shape))
    if not cache_dir.exists():
        raise FileNotFoundError(f"Missing local D024 cache: {cache_dir}")
    rows = []
    for index, cache_path in enumerate(sorted(cache_dir.glob(f"*_{shape_suffix}.npz"))):
        case_id = cache_path.name.replace(f"_{shape_suffix}.npz", "")
        fold = index % 5
        rows.append(
            {
                "case_id": case_id,
                "input_path": str(cache_path),
                "label": "available",
                "task_type": "segmentation",
                "input_type": "npz_roi",
                "modality": "cbct",
                "mask_path": str(cache_path),
                "split": "val" if fold == 0 else "train",
                "fold": fold,
                "label_source": "DentVoxel jaw ROI local nnU-Net cache",
                "dataset_id": "D024",
                "cache_path": str(cache_path),
                "source_image_path": "",
                "source_mask_path": "",
                "diagnosis_group": "",
                "original_shape": "",
                "original_spacing": "",
                "target_shape": format_tuple(target_shape),
                "label_values": "",
            }
        )
    manifest_path = dataset_dir / "derived" / "local_preprocessed" / f"jaw_roi_{target_shape[0]}_manifest.csv"
    manifest_info = write_cache_manifest(rows, manifest_path)
    return {
        "dataset_id": "D024",
        "task_name": "jaw_roi",
        "source": "existing_local_nnunet_monai_cache",
        "cache_dir": str(cache_dir),
        "manifest": manifest_info,
        "case_count": len(rows),
        "generated_count": 0,
        "reused_count": len(rows),
        "runtime_independent_of_archive": True,
    }


def build_d025_cache(
    archive_dataset_root: Path,
    project_dataset_root: Path,
    target_shape: tuple[int, int, int],
    *,
    force: bool,
    limit: int | None,
) -> dict[str, Any]:
    archive_raw = archive_dataset_root / "d025_lesion_cbct" / "raw" / "DOLCHID"
    cases, pairing = build_dolchid_cases(archive_raw)
    if limit is not None:
        cases = cases[:limit]
    output_dir = (
        project_dataset_root / "d025_lesion_cbct" / "derived" / "local_preprocessed" / f"lesion_roi_{target_shape[0]}"
    )
    rows, generated_count, reused_count = build_case_cache(
        cases,
        output_dir,
        target_shape,
        loader=load_nifti_pair,
        case_to_paths=lambda case: (case["cbct_image_path"], case["cbct_label_path"]),
        dataset_id="D025",
        task_label_source="DOLCHID CBCT lesion mask local cache",
        force=force,
    )
    for row, case in zip(rows, cases):
        row["label"] = case["diagnosis_group"]
        row["diagnosis_group"] = case["diagnosis_group"]
    manifest_info = write_cache_manifest(rows, output_dir / f"d025_dolchid_lesion_roi_{target_shape[0]}_manifest.csv")
    return {
        "dataset_id": "D025",
        "task_name": "lesion_roi",
        "archive_raw_source": str(archive_raw),
        "local_cache_dir": str(output_dir),
        "pairing": pairing,
        "manifest": manifest_info,
        "case_count": len(rows),
        "generated_count": generated_count,
        "reused_count": reused_count,
        "runtime_independent_of_archive": True,
    }


def build_d036_cache(
    archive_dataset_root: Path,
    project_dataset_root: Path,
    target_shape: tuple[int, int, int],
    *,
    force: bool,
    limit: int | None,
) -> dict[str, Any]:
    archive_raw = archive_dataset_root / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    cases, pairing = build_toothfairy2_cases(archive_raw)
    if limit is not None:
        cases = cases[:limit]
    output_dir = (
        project_dataset_root / "d036_toothfairy2" / "derived" / "local_preprocessed" / f"anatomy_roi_{target_shape[0]}"
    )
    rows, generated_count, reused_count = build_case_cache(
        cases,
        output_dir,
        target_shape,
        loader=load_mha_pair,
        case_to_paths=lambda case: (case["image_path"], case["label_path"]),
        dataset_id="D036",
        task_label_source="ToothFairy2 anatomical mask local cache",
        force=force,
    )
    manifest_info = write_cache_manifest(
        rows, output_dir / f"d036_toothfairy2_anatomy_roi_{target_shape[0]}_manifest.csv"
    )
    return {
        "dataset_id": "D036",
        "task_name": "anatomy_roi",
        "archive_raw_source": str(archive_raw),
        "local_cache_dir": str(output_dir),
        "pairing": pairing,
        "manifest": manifest_info,
        "case_count": len(rows),
        "generated_count": generated_count,
        "reused_count": reused_count,
        "runtime_independent_of_archive": True,
    }


def build_case_cache(
    cases: list[dict[str, Any]],
    output_dir: Path,
    target_shape: tuple[int, int, int],
    *,
    loader: Callable[[Path, Path], tuple[np.ndarray, np.ndarray, tuple[float, ...]]],
    case_to_paths: Callable[[dict[str, Any]], tuple[Path, Path]],
    dataset_id: str,
    task_label_source: str,
    force: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    npz_dir = ensure_dir(output_dir / "npz")
    rows: list[dict[str, Any]] = []
    generated_count = 0
    reused_count = 0
    shape_suffix = "x".join(map(str, target_shape))
    for index, case in enumerate(cases):
        image_path, label_path = case_to_paths(case)
        case_id = case["case_id"]
        cache_path = npz_dir / f"{case_id}_{shape_suffix}.npz"
        if force or not cache_path.exists():
            image, label, spacing = loader(image_path, label_path)
            cache_meta = write_npz_cache(image, label, cache_path, target_shape, spacing=spacing)
            generated_count += 1
            del image, label
        else:
            cache_meta = inspect_npz_cache(cache_path)
            reused_count += 1
        fold = index % 5
        rows.append(
            {
                "case_id": case_id,
                "input_path": str(cache_path),
                "label": "available",
                "task_type": "segmentation",
                "input_type": "npz_roi",
                "modality": "cbct",
                "mask_path": str(cache_path),
                "split": "val" if fold == 0 else "train",
                "fold": fold,
                "label_source": task_label_source,
                "dataset_id": dataset_id,
                "cache_path": str(cache_path),
                "source_image_path": "",
                "source_mask_path": "",
                "diagnosis_group": case.get("diagnosis_group", ""),
                **cache_meta,
            }
        )
    return rows, generated_count, reused_count


def load_nifti_pair(image_path: Path, label_path: Path) -> tuple[np.ndarray, np.ndarray, tuple[float, ...]]:
    image_obj = nib.load(str(image_path))
    label_obj = nib.load(str(label_path))
    image = np.asanyarray(image_obj.dataobj).astype(np.float32)
    label = np.asanyarray(label_obj.dataobj).astype(np.int16)
    return image, label, tuple(float(item) for item in image_obj.header.get_zooms()[:3])


def load_mha_pair(image_path: Path, label_path: Path) -> tuple[np.ndarray, np.ndarray, tuple[float, ...]]:
    import SimpleITK as sitk

    image_obj = sitk.ReadImage(str(image_path))
    label_obj = sitk.ReadImage(str(label_path))
    image = sitk.GetArrayFromImage(image_obj).astype(np.float32)
    label = sitk.GetArrayFromImage(label_obj).astype(np.int16)
    spacing = tuple(float(item) for item in image_obj.GetSpacing())
    return image, label, spacing


def inspect_npz_cache(cache_path: Path) -> dict[str, str]:
    with np.load(cache_path) as payload:
        image = payload["image"]
        label = payload["label"]
        original_shape = payload["original_shape"].tolist() if "original_shape" in payload.files else []
        original_spacing = payload["original_spacing"].tolist() if "original_spacing" in payload.files else []
        target_shape = payload["target_shape"].tolist() if "target_shape" in payload.files else list(image.shape)
        label_values = (
            payload["label_values"].tolist()
            if "label_values" in payload.files
            else np.unique(label).astype(int).tolist()
        )
    return {
        "original_shape": format_tuple(original_shape),
        "original_spacing": format_tuple(round(float(item), 6) for item in original_spacing),
        "target_shape": format_tuple(target_shape),
        "label_values": "|".join(str(int(value)) for value in label_values),
    }


def write_cache_manifest(rows: list[dict[str, Any]], manifest_path: Path) -> dict[str, Any]:
    ensure_dir(manifest_path.parent)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CACHE_MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CACHE_MANIFEST_FIELDS})
    _, info = read_manifest(manifest_path)
    info["manifest_path"] = str(manifest_path)
    return info


def write_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh = report_dir / "public_cbct_local_training_cache_zh.md"
    en = report_dir / "public_cbct_local_training_cache_en.md"
    zh.write_text(render_report(summary, language="zh"), encoding="utf-8")
    en.write_text(render_report(summary, language="en"), encoding="utf-8")
    return {"zh_report": str(zh), "en_report": str(en)}


def render_report(summary: dict[str, Any], *, language: str) -> str:
    datasets = summary["datasets"]
    rows = []
    for dataset_id, item in datasets.items():
        manifest = item.get("manifest", {})
        rows.append(
            f"| {dataset_id} | {item.get('task_name', '')} | {item.get('case_count', 0)} | "
            f"{item.get('generated_count', 0)} | {item.get('reused_count', 0)} | `{manifest.get('manifest_path', '')}` |"
        )
    table = "\n".join(rows)
    if language == "zh":
        return f"""# 公开 CBCT 本地训练缓存报告

## 目标

本次把训练和推理可直接读取的数据层固定在项目本地 `derived/` 目录下。D 盘只作为静态原始数据归档来源，不作为运行时依赖。

## 处理策略

- 目标尺寸：`{format_tuple(summary['target_shape'])}`
- 图像：0.5/99.5 百分位裁剪后归一化到 `[-1, 1]`，保存为 `float16`
- 标签：最近邻重采样，保存为 `int16`
- 缓存格式：压缩 NPZ，字段包含 `image`、`label`、`original_shape`、`target_shape`、`original_spacing`、`label_values`
- manifest：`input_path` 和 `mask_path` 均指向项目本地缓存文件

## 数据集结果

| 数据集 | 任务缓存 | 病例数 | 新生成 | 复用 | 本地 manifest |
| --- | --- | ---: | ---: | ---: | --- |
{table}

## 运行边界

训练、推理和 smoke benchmark 应优先读取本地 manifest 或 D024 已有 nnU-Net 预处理目录。若 D 盘不可用，现有本地缓存仍可读取；只有重新生成缓存或重做 raw 级预处理时才需要 D 盘归档。

## 局限性

D025 和 D036 当前缓存是低分辨率工程缓存，适合 smoke 训练、模型结构筛选和推理接口验证。正式高分辨率训练仍需要后续做任务级 nnU-Net/MONAI 转换，并记录新的实验报告。
"""
    return f"""# Public CBCT Local Training Cache Report

## Objective

This run fixes training- and inference-readable data under the local project `derived/` directories. Drive D is treated only as a static raw-data archive source and is not a runtime dependency.

## Method

- Target shape: `{format_tuple(summary['target_shape'])}`
- Image preprocessing: 0.5/99.5 percentile clipping, normalization to `[-1, 1]`, stored as `float16`
- Label preprocessing: nearest-neighbor resampling, stored as `int16`
- Cache format: compressed NPZ with `image`, `label`, `original_shape`, `target_shape`, `original_spacing`, and `label_values`
- Manifest contract: `input_path` and `mask_path` point to local project cache files

## Dataset Results

| Dataset | Cache task | Cases | Generated | Reused | Local manifest |
| --- | --- | ---: | ---: | ---: | --- |
{table}

## Runtime Boundary

Training, inference, and smoke benchmarks should use the local manifests or the existing local D024 nnU-Net preprocessing directories. If drive D is unavailable, the local caches remain readable; the archive is needed only when regenerating caches or repeating raw-level preprocessing.

## Limitations

D025 and D036 caches are low-resolution engineering caches for smoke training, architecture screening, and inference-interface validation. Formal high-resolution training still needs task-specific nnU-Net/MONAI conversion and a separate experiment report.
"""


def format_tuple(values: Iterable[Any]) -> str:
    return "x".join(str(item) for item in values)


def build_local_training_cache(
    *,
    datasets: list[str],
    archive_dataset_root: Path,
    project_dataset_root: Path,
    target_shape: tuple[int, int, int],
    force: bool,
    limit: int | None,
    report_dir: Path,
) -> dict[str, Any]:
    results: dict[str, Any] = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "archive_dataset_root": str(archive_dataset_root),
        "project_dataset_root": str(project_dataset_root),
        "target_shape": list(target_shape),
        "runtime_policy": "Local derived caches are runtime inputs; archive paths are source provenance only.",
        "datasets": {},
    }
    requested = {dataset.lower().strip() for dataset in datasets}
    if "d024" in requested:
        results["datasets"]["d024"] = build_d024_cache_manifest(project_dataset_root, target_shape)
    if "d025" in requested:
        results["datasets"]["d025"] = build_d025_cache(
            archive_dataset_root,
            project_dataset_root,
            target_shape,
            force=force,
            limit=limit,
        )
    if "d036" in requested:
        results["datasets"]["d036"] = build_d036_cache(
            archive_dataset_root,
            project_dataset_root,
            target_shape,
            force=force,
            limit=limit,
        )
    results["reports"] = write_reports(results, report_dir)
    results["summary_json_path"] = write_json(report_dir / "public_cbct_local_training_cache_summary.json", results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build local CBCT NPZ caches that do not depend on raw archive mounts."
    )
    parser.add_argument("--datasets", default="d024,d025,d036", help="Comma-separated dataset IDs: d024,d025,d036")
    parser.add_argument("--archive-root", default=str(ARCHIVE_DATASET_ROOT))
    parser.add_argument("--project-dataset-root", default=str(PROJECT_DATASET_ROOT))
    parser.add_argument("--target-shape", default="64x64x64")
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument("--force", action="store_true", help="Regenerate existing NPZ caches.")
    parser.add_argument("--limit", type=int, default=None, help="Optional per-dataset case limit for debugging.")
    args = parser.parse_args()
    summary = build_local_training_cache(
        datasets=[item for item in args.datasets.split(",") if item.strip()],
        archive_dataset_root=Path(args.archive_root),
        project_dataset_root=Path(args.project_dataset_root),
        target_shape=parse_target_shape(args.target_shape),
        force=args.force,
        limit=args.limit,
        report_dir=Path(args.report_dir),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
