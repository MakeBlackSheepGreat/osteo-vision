from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np
from PIL import Image

from src.datasets.manifests import read_manifest

DATASET_ROOT_IN_ZIP = "DentVoxel_Dataset"
DEFAULT_DATASET_DIR = Path("research/datasets/public-candidates/d024_dentvoxel")
DEFAULT_ZIP_PATH = DEFAULT_DATASET_DIR / "DentVoxel_Dataset.zip"
DEFAULT_REPORT_DIR = Path("research/reports/preprocessing")
MANIFEST_FIELDS = [
    "case_id",
    "input_path",
    "label",
    "task_type",
    "input_type",
    "modality",
    "mask_path",
    "label_source",
]
QUALITY_FIELDS = [
    "case_id",
    "image_shape",
    "label_shape",
    "image_spacing",
    "label_spacing",
    "image_dtype",
    "label_dtype",
    "label_values",
    "label_count",
    "status",
    "message",
]


def is_macos_resource_entry(name: str) -> bool:
    parts = name.replace("\\", "/").split("/")
    return any(part == "__MACOSX" or part.startswith("._") for part in parts)


def is_real_nifti_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    return normalized.endswith(".nii.gz") and not is_macos_resource_entry(normalized)


def case_id_from_entry(name: str, prefix: str) -> str | None:
    pattern = rf"/{re.escape(prefix)}(\d{{4}})\.nii\.gz$"
    match = re.search(pattern, name.replace("\\", "/"))
    if not match:
        return None
    return match.group(1)


def pair_image_label_entries(entries: Iterable[str]) -> tuple[dict[str, str], dict[str, str], list[str], list[str]]:
    images: dict[str, str] = {}
    labels: dict[str, str] = {}
    for entry in entries:
        normalized = entry.replace("\\", "/")
        if not is_real_nifti_entry(normalized):
            continue
        image_id = case_id_from_entry(normalized, "img")
        label_id = case_id_from_entry(normalized, "label")
        if image_id and "/image/" in normalized:
            images[image_id] = normalized
        if label_id and "/label/" in normalized:
            labels[label_id] = normalized
    missing_labels = sorted(case_id for case_id in images if case_id not in labels)
    missing_images = sorted(case_id for case_id in labels if case_id not in images)
    return images, labels, missing_labels, missing_images


def extract_dataset(zip_path: Path, raw_dir: Path) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_count = 0
    skipped_resource_count = 0
    skipped_existing_count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if is_macos_resource_entry(info.filename):
                skipped_resource_count += 1
                continue
            target = raw_dir / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == info.file_size:
                skipped_existing_count += 1
                continue
            with zf.open(info) as source, target.open("wb") as handle:
                handle.write(source.read())
            extracted_count += 1
    return {
        "zip_path": str(zip_path),
        "raw_dir": str(raw_dir),
        "extracted_count": extracted_count,
        "skipped_resource_count": skipped_resource_count,
        "skipped_existing_count": skipped_existing_count,
    }


def load_dataset_metadata(raw_dataset_dir: Path) -> dict[str, Any]:
    metadata_path = raw_dataset_dir / "dataset_DentVoxel.json"
    with metadata_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_case_pairs(raw_dataset_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries = [str(path.relative_to(raw_dataset_dir)).replace("\\", "/") for path in raw_dataset_dir.rglob("*.nii.gz")]
    rooted_entries = [f"{DATASET_ROOT_IN_ZIP}/{entry}" for entry in entries]
    images, labels, missing_labels, missing_images = pair_image_label_entries(rooted_entries)
    cases = []
    for case_id in sorted(set(images) & set(labels)):
        cases.append(
            {
                "case_id": f"d024_{case_id}",
                "numeric_id": case_id,
                "image_path": raw_dataset_dir / "image" / f"img{case_id}.nii.gz",
                "label_path": raw_dataset_dir / "label" / f"label{case_id}.nii.gz",
            }
        )
    summary = {
        "image_count": len(images),
        "label_count": len(labels),
        "paired_count": len(cases),
        "missing_labels_for_images": missing_labels,
        "missing_images_for_labels": missing_images,
    }
    return cases, summary


def analyze_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    global_label_counter: Counter[int] = Counter()
    shape_counter: Counter[str] = Counter()
    spacing_counter: Counter[str] = Counter()
    error_rows = []
    for case in cases:
        row = analyze_case(case)
        rows.append(row)
        if row["status"] != "ok":
            error_rows.append(row)
            continue
        for label_value in row["_label_values"]:
            global_label_counter[int(label_value)] += 1
        shape_counter[row["image_shape"]] += 1
        spacing_counter[row["image_spacing"]] += 1
    public_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]
    summary = {
        "quality_row_count": len(public_rows),
        "error_count": len(error_rows),
        "error_cases": [row["case_id"] for row in error_rows],
        "shape_distribution": dict(shape_counter),
        "spacing_distribution": dict(spacing_counter),
        "label_presence_counts": {str(key): value for key, value in sorted(global_label_counter.items())},
    }
    return public_rows, summary


def analyze_case(case: dict[str, Any]) -> dict[str, Any]:
    try:
        image = nib.load(str(case["image_path"]))
        label = nib.load(str(case["label_path"]))
        label_values = np.unique(np.asanyarray(label.dataobj)).astype(int).tolist()
        status = "ok"
        message = ""
        if image.shape != label.shape:
            status = "shape_mismatch"
            message = "Image and label shapes differ."
        return {
            "case_id": case["case_id"],
            "image_shape": _format_tuple(image.shape),
            "label_shape": _format_tuple(label.shape),
            "image_spacing": _format_tuple(_round_items(image.header.get_zooms()[:3])),
            "label_spacing": _format_tuple(_round_items(label.header.get_zooms()[:3])),
            "image_dtype": str(image.get_data_dtype()),
            "label_dtype": str(label.get_data_dtype()),
            "label_values": "|".join(str(item) for item in label_values),
            "label_count": len(label_values),
            "status": status,
            "message": message,
            "_label_values": label_values,
        }
    except Exception as exc:
        return {
            "case_id": case["case_id"],
            "image_shape": "",
            "label_shape": "",
            "image_spacing": "",
            "label_spacing": "",
            "image_dtype": "",
            "label_dtype": "",
            "label_values": "",
            "label_count": 0,
            "status": "read_error",
            "message": str(exc),
            "_label_values": [],
        }


def write_manifest(cases: list[dict[str, Any]], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "input_path": str(case["image_path"]),
                    "label": "available",
                    "task_type": "segmentation",
                    "input_type": "nifti_volume",
                    "modality": "cbct",
                    "mask_path": str(case["label_path"]),
                    "label_source": "DentVoxel anatomical instance annotation",
                }
            )


def write_label_inventory(metadata: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = metadata.get("labels", {})
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label_value", "label_name"])
        writer.writeheader()
        for value, name in sorted(labels.items(), key=lambda item: int(item[0])):
            writer.writerow({"label_value": value, "label_name": name})


def write_quality_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUALITY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in QUALITY_FIELDS})


def generate_previews(cases: list[dict[str, Any]], preview_dir: Path, *, count: int = 5) -> list[dict[str, str]]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for case in cases[:count]:
        image = nib.load(str(case["image_path"]))
        label = nib.load(str(case["label_path"]))
        image_data = np.asanyarray(image.dataobj)
        label_data = np.asanyarray(label.dataobj)
        case_dir = preview_dir / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "case_id": case["case_id"],
            "axial": str(case_dir / "axial.png"),
            "coronal": str(case_dir / "coronal.png"),
            "sagittal": str(case_dir / "sagittal.png"),
        }
        _save_preview(image_data[:, :, image_data.shape[2] // 2], label_data[:, :, label_data.shape[2] // 2], case_dir / "axial.png")
        _save_preview(image_data[:, image_data.shape[1] // 2, :], label_data[:, label_data.shape[1] // 2, :], case_dir / "coronal.png")
        _save_preview(image_data[image_data.shape[0] // 2, :, :], label_data[label_data.shape[0] // 2, :, :], case_dir / "sagittal.png")
        generated.append(paths)
    return generated


def write_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    zh_path = report_dir / "d024_dentvoxel_preprocessing_zh.md"
    en_path = report_dir / "d024_dentvoxel_preprocessing_en.md"
    zh_path.write_text(_render_zh_report(summary), encoding="utf-8")
    en_path.write_text(_render_en_report(summary), encoding="utf-8")
    return {"zh_report": str(zh_path), "en_report": str(en_path)}


def preprocess_d024(
    zip_path: Path = DEFAULT_ZIP_PATH,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
    *,
    preview_count: int = 5,
    skip_extract: bool = False,
) -> dict[str, Any]:
    raw_dir = dataset_dir / "raw"
    raw_dataset_dir = raw_dir / DATASET_ROOT_IN_ZIP
    derived_dir = dataset_dir / "derived"
    manifests_dir = derived_dir / "manifests"
    preview_dir = derived_dir / "previews"
    if not zip_path.exists() and not raw_dataset_dir.exists():
        raise FileNotFoundError(f"Dataset ZIP not found: {zip_path}")

    extraction = {"skipped": True, "reason": "skip_extract or existing raw dataset"}
    if not skip_extract and zip_path.exists():
        extraction = extract_dataset(zip_path, raw_dir)

    metadata = load_dataset_metadata(raw_dataset_dir)
    cases, pairing_summary = build_case_pairs(raw_dataset_dir)
    quality_rows, quality_summary = analyze_cases(cases)
    manifest_path = manifests_dir / "d024_dentvoxel_manifest.csv"
    label_inventory_path = manifests_dir / "d024_dentvoxel_label_inventory.csv"
    quality_csv_path = manifests_dir / "d024_dentvoxel_quality_check.csv"
    summary_json_path = manifests_dir / "d024_dentvoxel_preprocessing_summary.json"
    write_manifest(cases, manifest_path)
    write_label_inventory(metadata, label_inventory_path)
    write_quality_csv(quality_rows, quality_csv_path)
    manifest_rows, manifest_info = read_manifest(manifest_path)
    previews = generate_previews(cases, preview_dir, count=preview_count)

    summary = {
        "dataset_id": "D024",
        "dataset_name": metadata.get("name", "DentVoxel"),
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_zip": str(zip_path),
        "license": metadata.get("license"),
        "raw_dataset_dir": str(raw_dataset_dir),
        "derived_dir": str(derived_dir),
        "report_dir": str(report_dir),
        "metadata": {
            "description": metadata.get("description"),
            "modality": metadata.get("modality"),
            "tensor_image_size": metadata.get("tensorImageSize"),
            "label_count": len(metadata.get("labels", {})),
            "acquisition_protocol": metadata.get("acquisition_protocol"),
        },
        "extraction": extraction,
        "pairing": pairing_summary,
        "quality": quality_summary,
        "manifest": {
            "path": str(manifest_path),
            "row_count": len(manifest_rows),
            "info": manifest_info,
        },
        "label_inventory_path": str(label_inventory_path),
        "quality_csv_path": str(quality_csv_path),
        "summary_json_path": str(summary_json_path),
        "preview_count_requested": preview_count,
        "preview_count_generated": len(previews),
        "previews": previews,
        "project_use": [
            "CBCT jaw structure segmentation pretraining",
            "nnU-Net baseline data preparation",
            "Jaw ROI extraction for downstream osteomyelitis experiments",
        ],
        "limitations": [
            "DentVoxel is an anatomical CBCT segmentation dataset, not an intraoperative ICG fluorescence dataset.",
            "Labels describe dental and jaw structures, not osteomyelitis or necrotic bone lesions.",
            "MacOS resource files in the archive are ignored during extraction and validation.",
        ],
    }
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_paths = write_reports(summary, report_dir)
    summary["reports"] = report_paths
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _save_preview(image_slice: np.ndarray, label_slice: np.ndarray, output_path: Path) -> None:
    image_norm = _normalize_slice(image_slice)
    rgb = np.stack([image_norm, image_norm, image_norm], axis=-1)
    label_mask = np.asarray(label_slice) > 0
    rgb[label_mask, 0] = np.maximum(rgb[label_mask, 0], 220)
    rgb[label_mask, 1] = (rgb[label_mask, 1] * 0.45).astype(np.uint8)
    rgb[label_mask, 2] = (rgb[label_mask, 2] * 0.45).astype(np.uint8)
    Image.fromarray(np.rot90(rgb)).save(output_path)


def _normalize_slice(image_slice: np.ndarray) -> np.ndarray:
    data = np.asarray(image_slice, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros_like(data, dtype=np.uint8)
    low = float(np.percentile(finite, 1))
    high = float(np.percentile(finite, 99))
    if high <= low:
        high = float(np.max(finite))
        low = float(np.min(finite))
    if high <= low:
        return np.zeros_like(data, dtype=np.uint8)
    return np.clip((data - low) / (high - low) * 255.0, 0, 255).astype(np.uint8)


def _render_zh_report(summary: dict[str, Any]) -> str:
    pairing = summary["pairing"]
    quality = summary["quality"]
    manifest = summary["manifest"]
    return f"""# D024 DentVoxel 数据集预处理报告（中文）

## 数据来源与许可

- 数据集：{summary['dataset_name']}（D024）
- 模态：CBCT，3D NIfTI
- 来源文件：`{summary['source_zip']}`
- 许可：{summary.get('license') or '未声明'}
- 运行时间（UTC）：{summary['run_timestamp_utc']}

## 目录结构

- 原始数据目录：`{summary['raw_dataset_dir']}`
- 派生产物目录：`{summary['derived_dir']}`
- 统一报告目录：`{summary['report_dir']}`
- manifest：`{manifest['path']}`
- 标签清单：`{summary['label_inventory_path']}`
- 质量检查表：`{summary['quality_csv_path']}`
- 统计 JSON：`{summary['summary_json_path']}`

## 预处理方法

1. 从 ZIP 解压 `DentVoxel_Dataset/` 到 `raw/`，跳过 `._*` 与 `__MACOSX` 资源文件。
2. 按 `imgXXXX.nii.gz` 与 `labelXXXX.nii.gz` 编号进行配对。
3. 使用 `nibabel` 读取每个病例的 shape、spacing、dtype 与标签值。
4. 生成框架可读 manifest，任务类型设为 `segmentation`，输入类型设为 `nifti_volume`。
5. 生成前 {summary['preview_count_generated']} 个病例的轴位、冠状位、矢状位预览图，红色叠加表示非背景标签。

## 全量检查结果

- image 数量：{pairing['image_count']}
- label 数量：{pairing['label_count']}
- 成功配对病例：{pairing['paired_count']}
- 缺失 label 的 image：{pairing['missing_labels_for_images']}
- 缺失 image 的 label：{pairing['missing_images_for_labels']}
- manifest 行数：{manifest['row_count']}
- 读取异常病例数：{quality['error_count']}
- shape 分布：`{quality['shape_distribution']}`
- spacing 分布：`{quality['spacing_distribution']}`

## 标签体系说明

标签值来自 `dataset_DentVoxel.json`，共 {summary['metadata']['label_count']} 类，包含背景、上颌骨、下颌骨、FDI 牙位、左右下颌管与左右上颌窦。完整标签表已写入 `d024_dentvoxel_label_inventory.csv`。

## 可用于本项目的任务方向

- 术前 CBCT 颌骨/牙齿结构分割预训练。
- nnU-Net 或 MONAI 3D 分割基线数据准备。
- 为颌骨骨髓炎病灶定位提供颌骨 ROI 与解剖结构先验。

## 局限性与下一步计划

- D024 是解剖结构分割数据集，不是术中 ICG 荧光数据。
- 当前标签不包含颌骨骨髓炎、坏死骨或炎症边界。
- 下一步建议转换为 nnU-Net 数据格式，并优先抽取上颌骨/下颌骨/下颌管等结构做 baseline。
"""


def _render_en_report(summary: dict[str, Any]) -> str:
    pairing = summary["pairing"]
    quality = summary["quality"]
    manifest = summary["manifest"]
    return f"""# D024 DentVoxel Dataset Preprocessing Report

## Source and License

- Dataset: {summary['dataset_name']} (D024)
- Modality: CBCT, 3D NIfTI
- Source archive: `{summary['source_zip']}`
- License: {summary.get('license') or 'Not specified'}
- Run timestamp (UTC): {summary['run_timestamp_utc']}

## Directory Layout

- Raw dataset directory: `{summary['raw_dataset_dir']}`
- Derived artifact directory: `{summary['derived_dir']}`
- Central report directory: `{summary['report_dir']}`
- Manifest: `{manifest['path']}`
- Label inventory: `{summary['label_inventory_path']}`
- Quality check table: `{summary['quality_csv_path']}`
- Summary JSON: `{summary['summary_json_path']}`

## Preprocessing Method

1. Extract `DentVoxel_Dataset/` from the ZIP archive into `raw/`, skipping `._*` and `__MACOSX` resource files.
2. Pair volumes by `imgXXXX.nii.gz` and `labelXXXX.nii.gz`.
3. Read shape, spacing, dtype, and label values with `nibabel`.
4. Generate a framework-compatible manifest with `segmentation` as the task type and `nifti_volume` as the input type.
5. Generate axial, coronal, and sagittal previews for the first {summary['preview_count_generated']} cases; red overlay indicates non-background labels.

## Full-Dataset Check Results

- Image count: {pairing['image_count']}
- Label count: {pairing['label_count']}
- Paired cases: {pairing['paired_count']}
- Images missing labels: {pairing['missing_labels_for_images']}
- Labels missing images: {pairing['missing_images_for_labels']}
- Manifest rows: {manifest['row_count']}
- Read-error cases: {quality['error_count']}
- Shape distribution: `{quality['shape_distribution']}`
- Spacing distribution: `{quality['spacing_distribution']}`

## Label System

Labels are defined in `dataset_DentVoxel.json`. The dataset contains {summary['metadata']['label_count']} classes, including background, maxilla, mandible, FDI tooth instances, bilateral mandibular canals, and bilateral maxillary sinuses. The full label table is written to `d024_dentvoxel_label_inventory.csv`.

## Project Use

- Pretraining for preoperative CBCT jaw and dental structure segmentation.
- Data preparation for nnU-Net or MONAI 3D segmentation baselines.
- Anatomical ROI priors for downstream jaw osteomyelitis lesion localization.

## Limitations and Next Steps

- D024 is an anatomical CBCT segmentation dataset, not an intraoperative ICG fluorescence dataset.
- Current labels do not include jaw osteomyelitis, necrotic bone, or inflammatory boundaries.
- The next step is to convert this dataset into nnU-Net format and start with maxilla, mandible, and mandibular canal segmentation baselines.
"""


def _format_tuple(values: Iterable[Any]) -> str:
    return "x".join(str(value) for value in values)


def _round_items(values: Iterable[Any]) -> list[float]:
    return [round(float(value), 6) for value in values]


def main() -> int:
    parser = argparse.ArgumentParser(description="Preprocess the D024 DentVoxel dataset.")
    parser.add_argument("--zip-path", default=str(DEFAULT_ZIP_PATH))
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--preview-count", type=int, default=5)
    parser.add_argument("--skip-extract", action="store_true")
    args = parser.parse_args()
    summary = preprocess_d024(
        zip_path=Path(args.zip_path),
        dataset_dir=Path(args.dataset_dir),
        report_dir=Path(args.report_dir),
        preview_count=args.preview_count,
        skip_extract=args.skip_extract,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
