from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np
from PIL import Image

from scripts.preprocess_d024_dentvoxel import preprocess_d024
from src.core.paths import ensure_dir
from src.datasets.manifests import read_manifest
from src.reports.writers import write_csv, write_json

DATASET_ROOT = Path("research/datasets/public-candidates")
REPORT_DIR = Path("research/reports/preprocessing")
MANIFEST_FIELDS = [
    "case_id",
    "input_path",
    "label",
    "task_type",
    "input_type",
    "modality",
    "mask_path",
    "label_source",
    "hist_image_path",
    "hist_mask_path",
    "diagnosis_group",
]
DOLCHID_QUALITY_FIELDS = [
    "case_id",
    "diagnosis_group",
    "image_shape",
    "label_shape",
    "image_spacing",
    "label_spacing",
    "image_dtype",
    "label_dtype",
    "cbct_label_values",
    "hist_image_size",
    "hist_image_mode",
    "hist_label_size",
    "hist_label_mode",
    "hist_label_values",
    "status",
    "message",
]
TOOTHFAIRY2_QUALITY_FIELDS = [
    "case_id",
    "image_dim_size",
    "label_dim_size",
    "image_spacing",
    "label_spacing",
    "image_element_type",
    "label_element_type",
    "status",
    "message",
]


def is_resource_entry(name: str) -> bool:
    parts = name.replace("\\", "/").split("/")
    return any(part == "__MACOSX" or part.startswith("._") for part in parts)


def safe_extract_zip(zip_path: Path, raw_dir: Path) -> dict[str, Any]:
    raw_dir = ensure_dir(raw_dir)
    raw_root = raw_dir.resolve()
    extracted_count = 0
    skipped_existing_count = 0
    skipped_resource_count = 0
    skipped_directory_count = 0
    unsafe_entries: list[str] = []
    started = datetime.now(UTC)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir():
                skipped_directory_count += 1
                continue
            if is_resource_entry(name):
                skipped_resource_count += 1
                continue
            target = raw_dir / name
            resolved_target = target.resolve()
            try:
                resolved_target.relative_to(raw_root)
            except ValueError:
                unsafe_entries.append(name)
                continue
            ensure_dir(target.parent)
            if target.exists() and target.stat().st_size == info.file_size:
                skipped_existing_count += 1
                continue
            with zf.open(info) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle, length=1024 * 1024)
            extracted_count += 1
    finished = datetime.now(UTC)
    return {
        "zip_path": str(zip_path),
        "raw_dir": str(raw_dir),
        "zip_size_gb": round(zip_path.stat().st_size / 1024**3, 3),
        "extracted_count": extracted_count,
        "skipped_existing_count": skipped_existing_count,
        "skipped_resource_count": skipped_resource_count,
        "skipped_directory_count": skipped_directory_count,
        "unsafe_entries": unsafe_entries,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
    }


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_prefix(case_id: str) -> str:
    match = re.match(r"^[A-Za-z]+", case_id)
    return match.group(0) if match else "unknown"


def dolchid_case_id(path: Path) -> str:
    return re.sub(r"_(CBCT|HIST)_(Image|Label)\.(nii\.gz|png)$", "", path.name, flags=re.IGNORECASE)


def toothfairy_case_id(path: Path) -> str:
    name = path.name
    name = re.sub(r"_0000\.mha$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.mha$", "", name, flags=re.IGNORECASE)
    return name


def write_manifest(rows: list[dict[str, Any]], path: Path) -> tuple[str, dict[str, Any]]:
    write_csv(path, rows, MANIFEST_FIELDS)
    _, info = read_manifest(path)
    return str(path), info


def preprocess_dolchid(dataset_dir: Path, *, preview_count: int, skip_extract: bool) -> dict[str, Any]:
    zip_path = dataset_dir / "DOLCHID.zip"
    raw_dir = dataset_dir / "raw"
    raw_dataset_dir = raw_dir / "DOLCHID"
    derived_dir = dataset_dir / "derived"
    manifests_dir = ensure_dir(derived_dir / "manifests")
    previews_dir = ensure_dir(derived_dir / "previews")
    if not zip_path.exists() and not raw_dataset_dir.exists():
        raise FileNotFoundError(f"Missing DOLCHID ZIP or raw dataset: {zip_path}")
    extraction = {"skipped": True, "reason": "skip_extract"}
    if not skip_extract and zip_path.exists():
        extraction = safe_extract_zip(zip_path, raw_dir)
    cases, pairing = build_dolchid_cases(raw_dataset_dir)
    manifest_rows = [
        {
            "case_id": case["case_id"],
            "input_path": str(case["cbct_image_path"]),
            "label": case["diagnosis_group"],
            "task_type": "segmentation",
            "input_type": "nifti_volume",
            "modality": "cbct",
            "mask_path": str(case["cbct_label_path"]),
            "label_source": "DOLCHID CBCT lesion mask",
            "hist_image_path": str(case["hist_image_path"]),
            "hist_mask_path": str(case["hist_label_path"]),
            "diagnosis_group": case["diagnosis_group"],
        }
        for case in cases
    ]
    manifest_path, manifest_info = write_manifest(manifest_rows, manifests_dir / "d025_dolchid_manifest.csv")
    quality_rows, quality_summary = analyze_dolchid_cases(cases)
    quality_csv_path = write_csv(manifests_dir / "d025_dolchid_quality_check.csv", quality_rows, DOLCHID_QUALITY_FIELDS)
    diagnosis_rows = [
        {"diagnosis_group": key, "case_count": value}
        for key, value in sorted(Counter(case["diagnosis_group"] for case in cases).items())
    ]
    diagnosis_csv_path = write_csv(
        manifests_dir / "d025_dolchid_diagnosis_inventory.csv", diagnosis_rows, ["diagnosis_group", "case_count"]
    )
    previews = generate_dolchid_previews(cases[:preview_count], previews_dir)
    summary = {
        "dataset_id": "D025",
        "dataset_name": "DOLCHID",
        "source_zip": str(zip_path),
        "raw_dataset_dir": str(raw_dataset_dir),
        "derived_dir": str(derived_dir),
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "metadata_policy": "No original metadata file was found in the archive; generated metadata is written only under derived/.",
        "source_zip_sha256": hash_file(zip_path) if zip_path.exists() else None,
        "extraction": extraction,
        "pairing": pairing,
        "manifest": {"path": manifest_path, "info": manifest_info, "row_count": len(manifest_rows)},
        "quality": quality_summary,
        "quality_csv_path": quality_csv_path,
        "diagnosis_inventory_path": diagnosis_csv_path,
        "previews": previews,
        "preview_count_generated": len(previews),
        "project_use": [
            "CBCT lesion segmentation baseline",
            "Lesion ROI prior for jaw osteomyelitis software platform",
            "Cross-modal CBCT and histology evidence exploration",
        ],
        "limitations": [
            "The archive does not include a separate metadata or license file.",
            "The diagnosis groups are inferred from case ID prefixes and need source documentation confirmation.",
            "The dataset is not intraoperative ICG fluorescence data.",
        ],
    }
    summary_path = write_json(manifests_dir / "d025_dolchid_preprocessing_summary.json", summary)
    summary["summary_json_path"] = summary_path
    report_paths = write_dolchid_reports(summary, REPORT_DIR)
    summary["reports"] = report_paths
    write_json(summary_path, summary)
    return summary


def build_dolchid_cases(raw_dataset_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups = {
        "cbct_image": {
            dolchid_case_id(path): path for path in sorted((raw_dataset_dir / "cbct_image").glob("*_CBCT_Image.nii.gz"))
        },
        "cbct_label": {
            dolchid_case_id(path): path for path in sorted((raw_dataset_dir / "cbct_label").glob("*_CBCT_Label.nii.gz"))
        },
        "hist_image": {
            dolchid_case_id(path): path for path in sorted((raw_dataset_dir / "hist_image").glob("*_HIST_Image.png"))
        },
        "hist_label": {
            dolchid_case_id(path): path for path in sorted((raw_dataset_dir / "hist_label").glob("*_HIST_Label.png"))
        },
    }
    all_ids = sorted(set().union(*(set(values) for values in groups.values())))
    paired_ids = [case_id for case_id in all_ids if all(case_id in group for group in groups.values())]
    cases = [
        {
            "case_id": case_id,
            "diagnosis_group": case_prefix(case_id),
            "cbct_image_path": groups["cbct_image"][case_id],
            "cbct_label_path": groups["cbct_label"][case_id],
            "hist_image_path": groups["hist_image"][case_id],
            "hist_label_path": groups["hist_label"][case_id],
        }
        for case_id in paired_ids
    ]
    pairing = {
        "case_count_union": len(all_ids),
        "paired_count": len(cases),
        "counts_by_group": {key: len(value) for key, value in groups.items()},
        "missing_by_group_first20": {key: sorted(set(all_ids) - set(value))[:20] for key, value in groups.items()},
        "diagnosis_prefix_counts": dict(sorted(Counter(case_prefix(case_id) for case_id in paired_ids).items())),
    }
    return cases, pairing


def analyze_dolchid_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    status_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    spacing_counts: Counter[str] = Counter()
    cbct_label_presence: Counter[str] = Counter()
    hist_label_presence: Counter[str] = Counter()
    for case in cases:
        row = analyze_dolchid_case(case)
        rows.append(row)
        status_counts[row["status"]] += 1
        if row["status"] == "ok":
            shape_counts[row["image_shape"]] += 1
            spacing_counts[row["image_spacing"]] += 1
            for value in row["cbct_label_values"].split("|"):
                if value:
                    cbct_label_presence[value] += 1
            for value in row["hist_label_values"].split("|"):
                if value:
                    hist_label_presence[value] += 1
    return rows, {
        "row_count": len(rows),
        "status_counts": dict(status_counts),
        "shape_distribution": dict(shape_counts),
        "spacing_distribution": dict(spacing_counts),
        "cbct_label_presence_counts": dict(sorted(cbct_label_presence.items(), key=lambda item: int(item[0]))),
        "hist_label_presence_counts": dict(sorted(hist_label_presence.items(), key=lambda item: int(item[0]))),
    }


def analyze_dolchid_case(case: dict[str, Any]) -> dict[str, Any]:
    try:
        image = nib.load(str(case["cbct_image_path"]))
        label = nib.load(str(case["cbct_label_path"]))
        label_values = np.unique(np.asanyarray(label.dataobj)).astype(int).tolist()
        with Image.open(case["hist_image_path"]) as hist_image:
            hist_image_size = f"{hist_image.size[0]}x{hist_image.size[1]}"
            hist_image_mode = hist_image.mode
        with Image.open(case["hist_label_path"]) as hist_label:
            hist_label_size = f"{hist_label.size[0]}x{hist_label.size[1]}"
            hist_label_mode = hist_label.mode
            hist_label_values = np.unique(np.asarray(hist_label)).astype(int).tolist()
        status = "ok"
        message = ""
        if image.shape != label.shape:
            status = "shape_mismatch"
            message = "CBCT image and label shapes differ."
        return {
            "case_id": case["case_id"],
            "diagnosis_group": case["diagnosis_group"],
            "image_shape": format_tuple(image.shape),
            "label_shape": format_tuple(label.shape),
            "image_spacing": format_tuple(round_items(image.header.get_zooms()[:3])),
            "label_spacing": format_tuple(round_items(label.header.get_zooms()[:3])),
            "image_dtype": str(image.get_data_dtype()),
            "label_dtype": str(label.get_data_dtype()),
            "cbct_label_values": "|".join(str(value) for value in label_values),
            "hist_image_size": hist_image_size,
            "hist_image_mode": hist_image_mode,
            "hist_label_size": hist_label_size,
            "hist_label_mode": hist_label_mode,
            "hist_label_values": "|".join(str(value) for value in hist_label_values),
            "status": status,
            "message": message,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "case_id": case["case_id"],
            "diagnosis_group": case.get("diagnosis_group", ""),
            "image_shape": "",
            "label_shape": "",
            "image_spacing": "",
            "label_spacing": "",
            "image_dtype": "",
            "label_dtype": "",
            "cbct_label_values": "",
            "hist_image_size": "",
            "hist_image_mode": "",
            "hist_label_size": "",
            "hist_label_mode": "",
            "hist_label_values": "",
            "status": "read_error",
            "message": f"{type(exc).__name__}: {exc}",
        }


def generate_dolchid_previews(cases: list[dict[str, Any]], preview_dir: Path) -> list[dict[str, str]]:
    rows = []
    for case in cases:
        case_dir = ensure_dir(preview_dir / case["case_id"])
        image = np.asanyarray(nib.load(str(case["cbct_image_path"])).dataobj)
        label = np.asanyarray(nib.load(str(case["cbct_label_path"])).dataobj)
        axial = case_dir / "cbct_axial_overlay.png"
        coronal = case_dir / "cbct_coronal_overlay.png"
        sagittal = case_dir / "cbct_sagittal_overlay.png"
        save_overlay_slice(image[:, :, image.shape[2] // 2], label[:, :, label.shape[2] // 2], axial)
        save_overlay_slice(image[:, image.shape[1] // 2, :], label[:, label.shape[1] // 2, :], coronal)
        save_overlay_slice(image[image.shape[0] // 2, :, :], label[label.shape[0] // 2, :, :], sagittal)
        hist_overlay = case_dir / "histology_overlay.png"
        save_histology_overlay(case["hist_image_path"], case["hist_label_path"], hist_overlay)
        rows.append(
            {
                "case_id": case["case_id"],
                "cbct_axial": str(axial),
                "cbct_coronal": str(coronal),
                "cbct_sagittal": str(sagittal),
                "histology_overlay": str(hist_overlay),
            }
        )
        del image, label
    return rows


def preprocess_toothfairy2(dataset_dir: Path, *, preview_count: int, skip_extract: bool) -> dict[str, Any]:
    zip_path = dataset_dir / "ToothFairy2_Dataset.zip"
    raw_dir = dataset_dir / "raw"
    raw_dataset_dir = raw_dir / "Dataset112_ToothFairy2"
    derived_dir = dataset_dir / "derived"
    manifests_dir = ensure_dir(derived_dir / "manifests")
    previews_dir = ensure_dir(derived_dir / "previews")
    if not zip_path.exists() and not raw_dataset_dir.exists():
        raise FileNotFoundError(f"Missing ToothFairy2 ZIP or raw dataset: {zip_path}")
    extraction = {"skipped": True, "reason": "skip_extract"}
    if not skip_extract and zip_path.exists():
        extraction = safe_extract_zip(zip_path, raw_dir)
    metadata_path = raw_dataset_dir / "dataset.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    cases, pairing = build_toothfairy2_cases(raw_dataset_dir)
    manifest_rows = [
        {
            "case_id": case["case_id"],
            "input_path": str(case["image_path"]),
            "label": "available",
            "task_type": "segmentation",
            "input_type": "mha_volume",
            "modality": "cbct",
            "mask_path": str(case["label_path"]),
            "label_source": "ToothFairy2 maxillofacial CBCT segmentation",
            "hist_image_path": "",
            "hist_mask_path": "",
            "diagnosis_group": "",
        }
        for case in cases
    ]
    manifest_path, manifest_info = write_manifest(manifest_rows, manifests_dir / "d036_toothfairy2_manifest.csv")
    label_inventory_rows = [
        {"label_name": name, "label_value": value}
        for name, value in sorted(metadata.get("labels", {}).items(), key=lambda item: int(item[1]))
    ]
    label_inventory_path = write_csv(
        manifests_dir / "d036_toothfairy2_label_inventory.csv", label_inventory_rows, ["label_value", "label_name"]
    )
    quality_rows, quality_summary = analyze_toothfairy2_cases(cases)
    quality_csv_path = write_csv(
        manifests_dir / "d036_toothfairy2_quality_check.csv", quality_rows, TOOTHFAIRY2_QUALITY_FIELDS
    )
    previews = generate_toothfairy2_previews(cases[:preview_count], previews_dir)
    summary = {
        "dataset_id": "D036",
        "dataset_name": "ToothFairy2",
        "source_zip": str(zip_path),
        "raw_dataset_dir": str(raw_dataset_dir),
        "derived_dir": str(derived_dir),
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "metadata_policy": "Original dataset.json is kept unchanged in raw/; generated summaries are written under derived/.",
        "metadata_path": str(metadata_path),
        "metadata_sha256": hash_file(metadata_path),
        "source_zip_sha256": hash_file(zip_path) if zip_path.exists() else None,
        "license": metadata.get("license"),
        "reference": metadata.get("reference"),
        "metadata": {
            "release": metadata.get("release"),
            "latest_update": metadata.get("latestUpdate"),
            "file_ending": metadata.get("file_ending"),
            "label_count": len(metadata.get("labels", {})),
        },
        "extraction": extraction,
        "pairing": pairing,
        "manifest": {"path": manifest_path, "info": manifest_info, "row_count": len(manifest_rows)},
        "label_inventory_path": label_inventory_path,
        "quality": quality_summary,
        "quality_csv_path": quality_csv_path,
        "previews": previews,
        "preview_count_generated": len(previews),
        "project_use": [
            "Maxillofacial CBCT anatomical segmentation baseline",
            "Jawbone, mandibular canal, sinus, and tooth structure pretraining",
            "External validation source for D024-style structure segmentation",
        ],
        "limitations": [
            "This is anatomical segmentation data and does not contain jaw osteomyelitis lesion labels.",
            "The raw .mha volumes are large; full label-value scans are deferred to task-specific preprocessing.",
        ],
    }
    summary_path = write_json(manifests_dir / "d036_toothfairy2_preprocessing_summary.json", summary)
    summary["summary_json_path"] = summary_path
    report_paths = write_toothfairy2_reports(summary, REPORT_DIR)
    summary["reports"] = report_paths
    write_json(summary_path, summary)
    return summary


def build_toothfairy2_cases(raw_dataset_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    images = {toothfairy_case_id(path): path for path in sorted((raw_dataset_dir / "imagesTr").glob("*_0000.mha"))}
    labels = {toothfairy_case_id(path): path for path in sorted((raw_dataset_dir / "labelsTr").glob("*.mha"))}
    paired_ids = sorted(set(images) & set(labels))
    cases = [
        {"case_id": case_id, "image_path": images[case_id], "label_path": labels[case_id]} for case_id in paired_ids
    ]
    return cases, {
        "image_count": len(images),
        "label_count": len(labels),
        "paired_count": len(cases),
        "missing_labels_for_images": sorted(set(images) - set(labels))[:20],
        "missing_images_for_labels": sorted(set(labels) - set(images))[:20],
    }


def read_mha_header(path: Path) -> dict[str, str]:
    header: dict[str, str] = {}
    with path.open("rb") as handle:
        for raw_line in handle:
            line = raw_line.decode("latin-1", errors="ignore").strip()
            if "=" in line:
                key, value = line.split("=", 1)
                header[key.strip()] = value.strip()
            if line.startswith("ElementDataFile"):
                break
    return header


def analyze_toothfairy2_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    status_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    spacing_counts: Counter[str] = Counter()
    for case in cases:
        row = analyze_toothfairy2_case(case)
        rows.append(row)
        status_counts[row["status"]] += 1
        if row["status"] == "ok":
            shape_counts[row["image_dim_size"]] += 1
            spacing_counts[row["image_spacing"]] += 1
    return rows, {
        "row_count": len(rows),
        "status_counts": dict(status_counts),
        "dim_size_distribution": dict(shape_counts),
        "spacing_distribution": dict(spacing_counts),
    }


def analyze_toothfairy2_case(case: dict[str, Any]) -> dict[str, Any]:
    try:
        image_header = read_mha_header(case["image_path"])
        label_header = read_mha_header(case["label_path"])
        status = "ok"
        message = ""
        if image_header.get("DimSize") != label_header.get("DimSize"):
            status = "shape_mismatch"
            message = "Image and label DimSize differ."
        return {
            "case_id": case["case_id"],
            "image_dim_size": image_header.get("DimSize", ""),
            "label_dim_size": label_header.get("DimSize", ""),
            "image_spacing": image_header.get("ElementSpacing", ""),
            "label_spacing": label_header.get("ElementSpacing", ""),
            "image_element_type": image_header.get("ElementType", ""),
            "label_element_type": label_header.get("ElementType", ""),
            "status": status,
            "message": message,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "case_id": case["case_id"],
            "image_dim_size": "",
            "label_dim_size": "",
            "image_spacing": "",
            "label_spacing": "",
            "image_element_type": "",
            "label_element_type": "",
            "status": "read_error",
            "message": f"{type(exc).__name__}: {exc}",
        }


def generate_toothfairy2_previews(cases: list[dict[str, Any]], preview_dir: Path) -> list[dict[str, str]]:
    try:
        import SimpleITK as sitk
    except ImportError:
        return []
    rows = []
    for case in cases:
        case_dir = ensure_dir(preview_dir / case["case_id"])
        image = sitk.GetArrayFromImage(sitk.ReadImage(str(case["image_path"]))).astype(np.float32)
        label = sitk.GetArrayFromImage(sitk.ReadImage(str(case["label_path"])))
        axial = case_dir / "axial_overlay.png"
        coronal = case_dir / "coronal_overlay.png"
        sagittal = case_dir / "sagittal_overlay.png"
        save_overlay_slice(image[image.shape[0] // 2, :, :], label[label.shape[0] // 2, :, :], axial)
        save_overlay_slice(image[:, image.shape[1] // 2, :], label[:, label.shape[1] // 2, :], coronal)
        save_overlay_slice(image[:, :, image.shape[2] // 2], label[:, :, label.shape[2] // 2], sagittal)
        rows.append(
            {"case_id": case["case_id"], "axial": str(axial), "coronal": str(coronal), "sagittal": str(sagittal)}
        )
        del image, label
    return rows


def save_overlay_slice(image_slice: np.ndarray, label_slice: np.ndarray, output_path: Path) -> None:
    image_norm = normalize_slice(image_slice)
    rgb = np.stack([image_norm, image_norm, image_norm], axis=-1)
    mask = np.asarray(label_slice) > 0
    rgb[mask, 0] = 235
    rgb[mask, 1] = (rgb[mask, 1] * 0.45).astype(np.uint8)
    rgb[mask, 2] = (rgb[mask, 2] * 0.45).astype(np.uint8)
    Image.fromarray(np.rot90(rgb)).save(output_path)


def save_histology_overlay(image_path: Path, label_path: Path, output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    label = Image.open(label_path).convert("L")
    max_width = 1024
    if image.width > max_width:
        scale = max_width / image.width
        new_size = (max_width, max(1, int(image.height * scale)))
        image = image.resize(new_size, Image.Resampling.BILINEAR)
        label = label.resize(new_size, Image.Resampling.NEAREST)
    rgb = np.asarray(image).copy()
    mask = np.asarray(label) > 0
    rgb[mask, 0] = 235
    rgb[mask, 1] = (rgb[mask, 1] * 0.35).astype(np.uint8)
    rgb[mask, 2] = (rgb[mask, 2] * 0.35).astype(np.uint8)
    Image.fromarray(rgb).save(output_path)


def normalize_slice(image_slice: np.ndarray) -> np.ndarray:
    data = np.asarray(image_slice, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros(data.shape, dtype=np.uint8)
    low = float(np.percentile(finite, 1))
    high = float(np.percentile(finite, 99))
    if high <= low:
        low, high = float(np.min(finite)), float(np.max(finite))
    if high <= low:
        return np.zeros(data.shape, dtype=np.uint8)
    return np.clip((data - low) / (high - low) * 255.0, 0, 255).astype(np.uint8)


def write_dolchid_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    zh = report_dir / "d025_dolchid_preprocessing_zh.md"
    en = report_dir / "d025_dolchid_preprocessing_en.md"
    ensure_dir(report_dir)
    zh.write_text(render_dolchid_report(summary, language="zh"), encoding="utf-8")
    en.write_text(render_dolchid_report(summary, language="en"), encoding="utf-8")
    return {"zh_report": str(zh), "en_report": str(en)}


def write_toothfairy2_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    zh = report_dir / "d036_toothfairy2_preprocessing_zh.md"
    en = report_dir / "d036_toothfairy2_preprocessing_en.md"
    ensure_dir(report_dir)
    zh.write_text(render_toothfairy2_report(summary, language="zh"), encoding="utf-8")
    en.write_text(render_toothfairy2_report(summary, language="en"), encoding="utf-8")
    return {"zh_report": str(zh), "en_report": str(en)}


def render_dolchid_report(summary: dict[str, Any], *, language: str) -> str:
    pairing = summary["pairing"]
    quality = summary["quality"]
    manifest = summary["manifest"]
    if language == "zh":
        return f"""# D025 DOLCHID 数据预处理报告（中文）

## 数据来源与目录

- 数据集：DOLCHID
- 来源 ZIP：`{summary['source_zip']}`
- 原始解压目录：`{summary['raw_dataset_dir']}`
- 派生产物目录：`{summary['derived_dir']}`
- 元数据策略：{summary['metadata_policy']}

## 解压结果

- 新解压文件数：{summary['extraction'].get('extracted_count')}
- 已存在跳过文件数：{summary['extraction'].get('skipped_existing_count')}
- 不安全路径条目数：{len(summary['extraction'].get('unsafe_entries', []))}

## 配对检查

- 病例总数：{pairing['case_count_union']}
- 完整配对病例：{pairing['paired_count']}
- 子目录文件数：`{pairing['counts_by_group']}`
- 诊断前缀分布：`{pairing['diagnosis_prefix_counts']}`

## 质量检查

- 质检行数：{quality['row_count']}
- 状态分布：`{quality['status_counts']}`
- CBCT shape 分布：`{quality['shape_distribution']}`
- CBCT spacing 分布：`{quality['spacing_distribution']}`
- CBCT 标签值出现统计：`{quality['cbct_label_presence_counts']}`
- 病理标签值出现统计：`{quality['hist_label_presence_counts']}`

## 预处理产物

- manifest：`{manifest['path']}`
- 质检 CSV：`{summary['quality_csv_path']}`
- 诊断组清单：`{summary['diagnosis_inventory_path']}`
- 统计 JSON：`{summary['summary_json_path']}`
- 预览图病例数：{summary['preview_count_generated']}

## 项目用途与限制

DOLCHID 可用于 CBCT 病灶区域分割和 ROI 先验探索，属于 AI 辅助判读的非目标域代理数据。其数据不含术中 ICG 荧光，诊断组含义仍需核对来源文档，禁止包装成颌骨骨髓炎临床诊断性能。
"""
    return f"""# D025 DOLCHID Preprocessing Report

## Source and Layout

- Dataset: DOLCHID
- Source ZIP: `{summary['source_zip']}`
- Raw directory: `{summary['raw_dataset_dir']}`
- Derived directory: `{summary['derived_dir']}`
- Metadata policy: {summary['metadata_policy']}

## Extraction

- Newly extracted files: {summary['extraction'].get('extracted_count')}
- Existing files skipped: {summary['extraction'].get('skipped_existing_count')}
- Unsafe path entries: {len(summary['extraction'].get('unsafe_entries', []))}

## Pairing Check

- Total case IDs: {pairing['case_count_union']}
- Fully paired cases: {pairing['paired_count']}
- Directory counts: `{pairing['counts_by_group']}`
- Diagnosis prefix distribution: `{pairing['diagnosis_prefix_counts']}`

## Quality Check

- Quality rows: {quality['row_count']}
- Status counts: `{quality['status_counts']}`
- CBCT shape distribution: `{quality['shape_distribution']}`
- CBCT spacing distribution: `{quality['spacing_distribution']}`
- CBCT label-value presence: `{quality['cbct_label_presence_counts']}`
- Histology label-value presence: `{quality['hist_label_presence_counts']}`

## Artifacts

- Manifest: `{manifest['path']}`
- Quality CSV: `{summary['quality_csv_path']}`
- Diagnosis inventory: `{summary['diagnosis_inventory_path']}`
- Summary JSON: `{summary['summary_json_path']}`
- Preview cases: {summary['preview_count_generated']}

## Project Use and Boundary

DOLCHID is the closest current dataset for competition point 2 because it contains CBCT lesion masks and paired histology images. It is still not intraoperative ICG fluorescence data. Diagnosis-group meanings must be verified from source documentation before any clinical wording is used.
"""


def render_toothfairy2_report(summary: dict[str, Any], *, language: str) -> str:
    pairing = summary["pairing"]
    quality = summary["quality"]
    manifest = summary["manifest"]
    if language == "zh":
        return f"""# D036 ToothFairy2 数据预处理报告（中文）

## 数据来源与许可

- 数据集：ToothFairy2
- 来源 ZIP：`{summary['source_zip']}`
- 原始解压目录：`{summary['raw_dataset_dir']}`
- 许可：{summary.get('license')}
- 参考链接：{summary.get('reference')}
- 元数据路径：`{summary.get('metadata_path')}`
- 元数据策略：{summary['metadata_policy']}

## 解压结果

- 新解压文件数：{summary['extraction'].get('extracted_count')}
- 已存在跳过文件数：{summary['extraction'].get('skipped_existing_count')}
- 不安全路径条目数：{len(summary['extraction'].get('unsafe_entries', []))}

## 配对检查

- image 数：{pairing['image_count']}
- label 数：{pairing['label_count']}
- 完整配对病例：{pairing['paired_count']}
- 缺失 label 的 image：{pairing['missing_labels_for_images']}
- 缺失 image 的 label：{pairing['missing_images_for_labels']}

## 质量检查

- 质检行数：{quality['row_count']}
- 状态分布：`{quality['status_counts']}`
- DimSize 分布：`{quality['dim_size_distribution']}`
- spacing 分布：`{quality['spacing_distribution']}`

## 预处理产物

- manifest：`{manifest['path']}`
- 标签清单：`{summary['label_inventory_path']}`
- 质检 CSV：`{summary['quality_csv_path']}`
- 统计 JSON：`{summary['summary_json_path']}`
- 预览图病例数：{summary['preview_count_generated']}

## 项目用途与限制

ToothFairy2 可作为 D024 的增强版解剖结构分割数据，用于颌骨、牙齿、下牙槽神经管和上颌窦结构先验。它不包含颌骨骨髓炎、坏死骨或 ICG 荧光标注。
"""
    return f"""# D036 ToothFairy2 Preprocessing Report

## Source and License

- Dataset: ToothFairy2
- Source ZIP: `{summary['source_zip']}`
- Raw directory: `{summary['raw_dataset_dir']}`
- License: {summary.get('license')}
- Reference: {summary.get('reference')}
- Metadata path: `{summary.get('metadata_path')}`
- Metadata policy: {summary['metadata_policy']}

## Extraction

- Newly extracted files: {summary['extraction'].get('extracted_count')}
- Existing files skipped: {summary['extraction'].get('skipped_existing_count')}
- Unsafe path entries: {len(summary['extraction'].get('unsafe_entries', []))}

## Pairing Check

- Image count: {pairing['image_count']}
- Label count: {pairing['label_count']}
- Fully paired cases: {pairing['paired_count']}
- Images missing labels: {pairing['missing_labels_for_images']}
- Labels missing images: {pairing['missing_images_for_labels']}

## Quality Check

- Quality rows: {quality['row_count']}
- Status counts: `{quality['status_counts']}`
- DimSize distribution: `{quality['dim_size_distribution']}`
- Spacing distribution: `{quality['spacing_distribution']}`

## Artifacts

- Manifest: `{manifest['path']}`
- Label inventory: `{summary['label_inventory_path']}`
- Quality CSV: `{summary['quality_csv_path']}`
- Summary JSON: `{summary['summary_json_path']}`
- Preview cases: {summary['preview_count_generated']}

## Project Use and Boundary

ToothFairy2 can extend D024 anatomical segmentation for jawbone, teeth, inferior alveolar canals, and maxillary sinuses. It does not contain jaw osteomyelitis, necrotic bone, or ICG fluorescence annotations.
"""


def write_combined_reports(results: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh = report_dir / "public_cbct_datasets_preprocessing_summary_zh.md"
    en = report_dir / "public_cbct_datasets_preprocessing_summary_en.md"
    zh.write_text(render_combined_report(results, language="zh"), encoding="utf-8")
    en.write_text(render_combined_report(results, language="en"), encoding="utf-8")
    return {"zh_report": str(zh), "en_report": str(en)}


def render_combined_report(results: dict[str, Any], *, language: str) -> str:
    if language == "zh":
        lines = [
            "# 公开 CBCT 数据集解压与预处理汇总（中文）",
            "",
            "## 处理范围",
            "",
            "本次处理 D024 DentVoxel、D025 DOLCHID、D036 ToothFairy2 三个本地数据集。原始 ZIP 与原始元数据文件只读取和解压，不在 raw/ 中做改写；所有派生清单、质检、预览和报告写入 derived/ 与 research/reports/preprocessing/。",
            "",
            "## 汇总",
            "",
            "| Dataset | Status | Cases | Manifest | Report |",
            "|---|---|---:|---|---|",
        ]
        for key, item in results["datasets"].items():
            if not item.get("available"):
                lines.append(f"| {key} | skipped | 0 |  |  |")
                continue
            case_count = item.get("pairing", {}).get("paired_count") or item.get("manifest", {}).get("row_count") or ""
            lines.append(
                f"| {key} | processed | {case_count} | `{item.get('manifest', {}).get('path', '')}` | `{item.get('reports', {}).get('zh_report', '')}` |"
            )
        lines.extend(
            [
                "",
                "## 下一步",
                "",
                "1. D025 优先转换为二值病灶分割任务，先做 64³/128³ 低分辨率 smoke。",
                "2. D036 与 D024 合并设计 jaw-roi 结构分割标签映射，服务术前 ROI。",
                "3. 所有训练产物继续放本地 ignored 目录，长期证据只保留报告和必要预览图。",
            ]
        )
        return "\n".join(lines) + "\n"
    lines = [
        "# Public CBCT Dataset Extraction and Preprocessing Summary",
        "",
        "## Scope",
        "",
        "This run processes D024 DentVoxel, D025 DOLCHID, and D036 ToothFairy2. Source ZIP files and raw metadata files are only read/extracted and are not rewritten under raw/. Derived manifests, quality checks, previews, and reports are written under derived/ and research/reports/preprocessing/.",
        "",
        "## Summary",
        "",
        "| Dataset | Status | Cases | Manifest | Report |",
        "|---|---|---:|---|---|",
    ]
    for key, item in results["datasets"].items():
        if not item.get("available"):
            lines.append(f"| {key} | skipped | 0 |  |  |")
            continue
        case_count = item.get("pairing", {}).get("paired_count") or item.get("manifest", {}).get("row_count") or ""
        lines.append(
            f"| {key} | processed | {case_count} | `{item.get('manifest', {}).get('path', '')}` | `{item.get('reports', {}).get('en_report', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Steps",
            "",
            "1. Convert D025 into a binary lesion segmentation task and start with 64³/128³ smoke runs.",
            "2. Align D036 and D024 jaw-roi label mappings for preoperative ROI structure segmentation.",
            "3. Keep training outputs in ignored local directories; retain only reports and essential previews as long-term evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_tuple(values: Iterable[Any]) -> str:
    return "x".join(str(value) for value in values)


def round_items(values: Iterable[Any]) -> list[float]:
    return [round(float(value), 6) for value in values]


def run(args: argparse.Namespace) -> dict[str, Any]:
    requested = {item.strip().lower() for item in args.datasets.split(",") if item.strip()}
    results: dict[str, Any] = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "datasets_requested": sorted(requested),
        "datasets": {},
    }
    if "d024" in requested:
        d024 = preprocess_d024(
            dataset_dir=DATASET_ROOT / "d024_dentvoxel",
            report_dir=REPORT_DIR,
            preview_count=args.preview_count,
            skip_extract=args.skip_extract,
        )
        d024["available"] = True
        results["datasets"]["d024"] = d024
    if "d025" in requested:
        d025 = preprocess_dolchid(
            DATASET_ROOT / "d025_lesion_cbct", preview_count=args.preview_count, skip_extract=args.skip_extract
        )
        d025["available"] = True
        results["datasets"]["d025"] = d025
    if "d036" in requested:
        d036 = preprocess_toothfairy2(
            DATASET_ROOT / "d036_toothfairy2", preview_count=args.preview_count, skip_extract=args.skip_extract
        )
        d036["available"] = True
        results["datasets"]["d036"] = d036
    combined_reports = write_combined_reports(results, REPORT_DIR)
    results["reports"] = combined_reports
    results["summary_json_path"] = write_json(REPORT_DIR / "public_cbct_datasets_preprocessing_summary.json", results)
    write_json(results["summary_json_path"], results)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract and preprocess local public CBCT candidate datasets.")
    parser.add_argument("--datasets", default="d024,d025,d036", help="Comma-separated dataset IDs: d024,d025,d036")
    parser.add_argument("--preview-count", type=int, default=5)
    parser.add_argument("--skip-extract", action="store_true")
    return parser.parse_args()


def main() -> int:
    results = run(parse_args())
    print(
        json.dumps(
            {"summary_json_path": results["summary_json_path"], "reports": results["reports"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
