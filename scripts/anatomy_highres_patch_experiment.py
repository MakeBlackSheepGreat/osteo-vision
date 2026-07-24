from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from scripts.benchmark_d024_segmentation_models import ModelCandidate, _primary_output
from scripts.benchmark_public_cbct_segmentation_models import (
    binary_dice_iou,
    build_segmentation_loss,
    combined_model_catalog,
)
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.reports.writers import write_csv, write_json

PROJECT_DATASET_ROOT = Path("research/datasets/public-candidates")
ARCHIVE_DATASET_ROOT = Path("D:/projects/osteo-vision/research/datasets/public-candidates")
DEFAULT_OUTPUT_ROOT = Path("artifacts/runs/anatomy_highres_patch_experiment")
DEFAULT_REPORT_DIR = Path("research/reports/modeling")
DEFAULT_PATCH_SHAPE = (96, 128, 128)
DEFAULT_SEED = 20260617
ANATOMY_LABELS = {
    0: "background",
    1: "maxilla_or_upper_jawbone",
    2: "mandible_or_lower_jawbone",
    3: "right_mandibular_canal",
    4: "left_mandibular_canal",
    5: "right_maxillary_sinus",
    6: "left_maxillary_sinus",
}
COARSE3_LABELS = {
    0: "background",
    1: "jawbone",
    2: "mandibular_canal",
    3: "maxillary_sinus",
}
ANATOMY4_LABELS = {
    0: "background",
    1: "maxilla_or_upper_jawbone",
    2: "mandible_or_lower_jawbone",
    3: "mandibular_canal",
    4: "maxillary_sinus",
}
SMALL_STRUCTURE_LABELS = [3, 4, 5, 6]
ANATOMY4_SMALL_STRUCTURE_LABELS = [3, 4]
COARSE3_SMALL_STRUCTURE_LABELS = [2, 3]
LABEL_MODE_CHOICES = ["anatomy6", "anatomy4", "coarse3"]
SAMPLING_STRATEGY_CHOICES = ["default", "small50", "small75", "class_cycle", "small_cycle", "canal_focus"]
PATCH_MANIFEST_FIELDS = [
    "patch_id",
    "case_id",
    "dataset_id",
    "input_path",
    "label",
    "task_type",
    "input_type",
    "modality",
    "mask_path",
    "cache_path",
    "split",
    "fold",
    "label_source",
    "source_image_path",
    "source_mask_path",
    "source_shape",
    "spacing",
    "patch_shape",
    "patch_origin",
    "sampling_mode",
    "label_values",
    "foreground_voxel_fraction",
]


@dataclass(frozen=True)
class SourceCase:
    case_id: str
    dataset_id: str
    image_path: Path
    label_path: Path
    label_source: str
    source_kind: str


class PatchDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        with np.load(row["cache_path"]) as payload:
            image = payload["image"].astype(np.float32, copy=False)
            label = payload["label"].astype(np.int64, copy=False)
        return torch.from_numpy(image[None]), torch.from_numpy(label)


def parse_shape(value: str) -> tuple[int, int, int]:
    parts = [part for part in value.lower().replace(",", "x").split("x") if part]
    if len(parts) != 3:
        raise ValueError(f"Expected shape like 96x128x128, got: {value}")
    shape = tuple(int(part) for part in parts)
    if any(item <= 0 for item in shape):
        raise ValueError(f"Shape must be positive, got: {value}")
    return shape  # type: ignore[return-value]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def safe_copy_file(source: Path, destination: Path, project_root: Path) -> bool:
    if not source.exists():
        raise FileNotFoundError(source)
    if not is_relative_to(destination, project_root):
        raise ValueError(f"Destination is outside project root: {destination}")
    ensure_dir(destination.parent)
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        return False
    shutil.copy2(source, destination)
    return True


def d036_archive_equivalent(local_path: Path, archive_dataset_root: Path) -> Path:
    marker = Path("research/datasets/public-candidates")
    text = str(local_path)
    normalized = text.replace("/", "\\")
    marker_text = str(marker).replace("/", "\\")
    if marker_text not in normalized:
        return local_path
    suffix = normalized.split(marker_text, 1)[1].lstrip("\\/")
    return archive_dataset_root / suffix


def load_d024_cases(project_dataset_root: Path) -> list[SourceCase]:
    dataset = (
        project_dataset_root / "d024_dentvoxel" / "derived" / "nnunet" / "nnUNet_raw" / "Dataset124_DentVoxelJawROI"
    )
    images = dataset / "imagesTr"
    labels = dataset / "labelsTr"
    if not images.exists() or not labels.exists():
        raise FileNotFoundError(f"Missing D024 nnU-Net raw dataset: {dataset}")
    cases = []
    for image_path in sorted(images.glob("*_0000.nii.gz")):
        case_id = image_path.name.replace("_0000.nii.gz", "")
        label_path = labels / f"{case_id}.nii.gz"
        if label_path.exists():
            cases.append(
                SourceCase(
                    case_id=case_id,
                    dataset_id="D024",
                    image_path=image_path,
                    label_path=label_path,
                    label_source="D024 DentVoxel jaw ROI nnU-Net labels",
                    source_kind="project_nnunet_raw",
                )
            )
    return cases


def load_d036_cases(
    project_dataset_root: Path,
    archive_dataset_root: Path,
    *,
    allow_archive_source: bool,
) -> list[SourceCase]:
    manifest = project_dataset_root / "d036_toothfairy2" / "derived" / "manifests" / "d036_toothfairy2_manifest.csv"
    if not manifest.exists():
        raise FileNotFoundError(manifest)
    cases = []
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            image_path = Path(row["input_path"])
            label_path = Path(row["mask_path"])
            source_kind = "project_raw"
            if not image_path.exists() or not label_path.exists():
                if not allow_archive_source:
                    raise FileNotFoundError(f"Missing local D036 raw pair for {row['case_id']}")
                image_path = d036_archive_equivalent(image_path, archive_dataset_root)
                label_path = d036_archive_equivalent(label_path, archive_dataset_root)
                source_kind = "archive_raw_for_cache_generation"
            if image_path.exists() and label_path.exists():
                cases.append(
                    SourceCase(
                        case_id=row["case_id"],
                        dataset_id="D036",
                        image_path=image_path,
                        label_path=label_path,
                        label_source="D036 ToothFairy2 merged anatomy ROI labels",
                        source_kind=source_kind,
                    )
                )
    return cases


def localize_d036_cases(
    cases: list[SourceCase], archive_dataset_root: Path, project_dataset_root: Path, limit: int | None
) -> dict[str, Any]:
    selected = cases[:limit] if limit is not None else cases
    copied = 0
    reused = 0
    project_root = Path.cwd()
    local_root = project_dataset_root / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    for case in selected:
        for source_path, subdir, suffix in [
            (case.image_path, "imagesTr", "_0000.mha"),
            (case.label_path, "labelsTr", ".mha"),
        ]:
            source = source_path
            if not source.exists():
                source = (
                    archive_dataset_root
                    / "d036_toothfairy2"
                    / "raw"
                    / "Dataset112_ToothFairy2"
                    / subdir
                    / f"{case.case_id}{suffix}"
                )
            destination = local_root / subdir / f"{case.case_id}{suffix}"
            if safe_copy_file(source, destination, project_root):
                copied += 1
            else:
                reused += 1
    return {"dataset_id": "D036", "selected_cases": len(selected), "copied_files": copied, "reused_files": reused}


def label_names_for_mode(label_mode: str) -> dict[int, str]:
    if label_mode == "anatomy6":
        return ANATOMY_LABELS
    if label_mode == "anatomy4":
        return ANATOMY4_LABELS
    if label_mode == "coarse3":
        return COARSE3_LABELS
    raise ValueError(f"Unsupported label mode: {label_mode}")


def small_structure_labels_for_mode(label_mode: str) -> list[int]:
    if label_mode == "anatomy6":
        return SMALL_STRUCTURE_LABELS
    if label_mode == "anatomy4":
        return ANATOMY4_SMALL_STRUCTURE_LABELS
    if label_mode == "coarse3":
        return COARSE3_SMALL_STRUCTURE_LABELS
    raise ValueError(f"Unsupported label mode: {label_mode}")


def load_volume_pair(
    case: SourceCase, *, label_mode: str = "anatomy6"
) -> tuple[np.ndarray, np.ndarray, tuple[float, ...]]:
    if case.image_path.suffix.lower() == ".mha" or case.image_path.name.lower().endswith(".mha"):
        import SimpleITK as sitk

        image_obj = sitk.ReadImage(str(case.image_path))
        label_obj = sitk.ReadImage(str(case.label_path))
        image = sitk.GetArrayFromImage(image_obj).astype(np.float32)
        label = sitk.GetArrayFromImage(label_obj).astype(np.int16)
        spacing = tuple(float(item) for item in reversed(image_obj.GetSpacing()))
        return image, remap_label(case.dataset_id, label, label_mode=label_mode), spacing
    image_obj = nib.load(str(case.image_path))
    label_obj = nib.load(str(case.label_path))
    image = np.asanyarray(image_obj.dataobj).astype(np.float32)
    label = np.asanyarray(label_obj.dataobj).astype(np.int16)
    spacing = tuple(float(item) for item in image_obj.header.get_zooms()[:3])
    return image, remap_label(case.dataset_id, label, label_mode=label_mode), spacing


def remap_label(dataset_id: str, label: np.ndarray, *, label_mode: str = "anatomy6") -> np.ndarray:
    data = np.asarray(label)
    output = np.zeros(data.shape, dtype=np.int16)
    if dataset_id == "D024" and label_mode == "anatomy6":
        for value in range(1, 7):
            output[data == value] = value
        return output
    if dataset_id == "D024" and label_mode == "anatomy4":
        output[data == 1] = 1
        output[data == 2] = 2
        output[np.isin(data, [3, 4])] = 3
        output[np.isin(data, [5, 6])] = 4
        return output
    if dataset_id == "D024" and label_mode == "coarse3":
        output[np.isin(data, [1, 2])] = 1
        output[np.isin(data, [3, 4])] = 2
        output[np.isin(data, [5, 6])] = 3
        return output
    if dataset_id == "D036" and label_mode == "anatomy6":
        mapping = {
            1: 2,  # Lower Jawbone -> mandible
            2: 1,  # Upper Jawbone -> maxilla
            3: 4,  # Left Inferior Alveolar Canal
            4: 3,  # Right Inferior Alveolar Canal
            5: 6,  # Left Maxillary Sinus
            6: 5,  # Right Maxillary Sinus
        }
        for source, target in mapping.items():
            output[data == source] = target
        return output
    if dataset_id == "D036" and label_mode == "anatomy4":
        mapping = {
            1: 2,  # Lower Jawbone -> mandible
            2: 1,  # Upper Jawbone -> maxilla
            3: 3,  # Left Inferior Alveolar Canal -> canal
            4: 3,  # Right Inferior Alveolar Canal -> canal
            5: 4,  # Left Maxillary Sinus -> sinus
            6: 4,  # Right Maxillary Sinus -> sinus
        }
        for source, target in mapping.items():
            output[data == source] = target
        return output
    if dataset_id == "D036" and label_mode == "coarse3":
        output[np.isin(data, [1, 2])] = 1
        output[np.isin(data, [3, 4])] = 2
        output[np.isin(data, [5, 6])] = 3
        return output
    raise ValueError(f"Unsupported dataset_id: {dataset_id}")


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
    return ((np.clip(data, low, high) - low) / (high - low) * 2.0 - 1.0).astype(np.float32)


def choose_center(
    label: np.ndarray,
    patch_shape: tuple[int, int, int],
    mode: str,
    rng: np.random.Generator,
    *,
    small_labels: Iterable[int] | None = None,
) -> tuple[int, int, int]:
    if mode == "small":
        mask = np.isin(label, list(small_labels or SMALL_STRUCTURE_LABELS))
    elif mode.startswith("label_"):
        target_label = int(mode.split("_", 1)[1])
        mask = label == target_label
    elif mode == "foreground":
        mask = label > 0
    else:
        mask = np.zeros(label.shape, dtype=bool)
    coords = np.argwhere(mask)
    if coords.size > 0:
        coord = coords[int(rng.integers(0, len(coords)))]
        return tuple(int(item) for item in coord)
    return tuple(int(rng.integers(0, max(1, size))) for size in label.shape)


def crop_patch(
    array: np.ndarray, center: tuple[int, int, int], patch_shape: tuple[int, int, int], *, fill_value: float = 0
) -> tuple[np.ndarray, tuple[int, int, int]]:
    output = np.full(patch_shape, fill_value, dtype=array.dtype)
    starts = [int(c - p // 2) for c, p in zip(center, patch_shape)]
    source_slices = []
    dest_slices = []
    for axis, start in enumerate(starts):
        end = start + patch_shape[axis]
        source_start = max(0, start)
        source_end = min(array.shape[axis], end)
        dest_start = max(0, -start)
        dest_end = dest_start + max(0, source_end - source_start)
        source_slices.append(slice(source_start, source_end))
        dest_slices.append(slice(dest_start, dest_end))
    if all(s.stop > s.start for s in source_slices):
        output[tuple(dest_slices)] = array[tuple(source_slices)]
    return output, tuple(starts)


def sampling_mode_for_index(index: int, strategy: str = "default", *, label_mode: str = "anatomy6") -> str:
    if strategy == "class_cycle":
        if label_mode == "coarse3":
            return ["foreground", "label_1", "label_2", "label_3"][index % 4]
        if label_mode == "anatomy4":
            return ["foreground", "label_1", "label_2", "label_3", "label_4"][index % 5]
        if label_mode == "anatomy6":
            return ["foreground", "label_1", "label_2", "label_3", "label_4", "label_5", "label_6"][index % 7]
        raise ValueError(f"Unsupported label mode: {label_mode}")
    if strategy == "small_cycle":
        if label_mode == "coarse3":
            return ["label_2", "label_3", "foreground", "random"][index % 4]
        if label_mode == "anatomy4":
            return ["label_3", "label_4", "small", "foreground", "random"][index % 5]
        if label_mode == "anatomy6":
            return ["label_3", "label_4", "label_5", "label_6", "small", "foreground", "random"][index % 7]
        raise ValueError(f"Unsupported label mode: {label_mode}")
    if strategy == "canal_focus":
        if label_mode == "coarse3":
            return ["label_2", "label_2", "label_3", "foreground", "random"][index % 5]
        if label_mode == "anatomy4":
            return ["label_3", "label_3", "label_4", "foreground", "random"][index % 5]
        if label_mode == "anatomy6":
            return ["label_3", "label_4", "label_3", "label_4", "label_5", "label_6", "foreground", "random"][index % 8]
        raise ValueError(f"Unsupported label mode: {label_mode}")
    if strategy == "small50":
        return ["small", "foreground", "small", "random"][index % 4]
    if strategy == "small75":
        return ["small", "foreground", "small", "small"][index % 4]
    if strategy != "default":
        raise ValueError(f"Unsupported sampling strategy: {strategy}")
    remainder = index % 4
    if remainder in (0, 1):
        return "foreground"
    if remainder == 2:
        return "small"
    return "random"


def sampling_strategy_description(strategy: str, *, label_mode: str) -> str:
    if strategy == "class_cycle":
        return "class-cycle patch centers over foreground and every target label."
    if strategy == "small_cycle":
        return (
            "small-structure-cycle patch centers over canal/sinus labels, plus small, foreground, and random patches."
        )
    if strategy == "canal_focus":
        return "canal-focused patch centers oversample mandibular canal labels while retaining sinus, foreground, and random patches."
    if strategy == "small50":
        return "50% small-structure-centered patches, with foreground and random coverage."
    if strategy == "small75":
        return "75% small-structure-centered patches, with foreground coverage."
    return "50% foreground-centered, 25% small-structure-centered, and 25% random/background patches."


def patch_cache_dir(
    project_dataset_root: Path,
    dataset_id: str,
    patch_shape: tuple[int, int, int],
    label_mode: str = "anatomy6",
    sampling_strategy: str = "default",
) -> Path:
    dataset_folder = "d024_dentvoxel" if dataset_id == "D024" else "d036_toothfairy2"
    shape = "x".join(str(item) for item in patch_shape)
    base = f"anatomy_roi_{shape}" if label_mode == "anatomy6" else f"{label_mode}_{shape}"
    suffix = base if sampling_strategy == "default" else f"{base}_{sampling_strategy}"
    return project_dataset_root / dataset_folder / "derived" / "highres_patch" / suffix


def build_patch_cache(
    dataset_id: str,
    cases: list[SourceCase],
    project_dataset_root: Path,
    *,
    patch_shape: tuple[int, int, int],
    patches_per_case: int,
    seed: int,
    force: bool,
    max_cases: int | None,
    label_mode: str = "anatomy6",
    sampling_strategy: str = "default",
) -> dict[str, Any]:
    selected_cases = cases[:max_cases] if max_cases is not None else cases
    output_dir = patch_cache_dir(project_dataset_root, dataset_id, patch_shape, label_mode, sampling_strategy)
    npz_dir = ensure_dir(output_dir / "npz")
    rows: list[dict[str, Any]] = []
    generated = 0
    reused = 0
    for case_index, case in enumerate(selected_cases):
        image, label, spacing = load_volume_pair(case, label_mode=label_mode)
        image = normalize_image(image)
        source_shape = tuple(int(item) for item in image.shape)
        fold = case_index % 5
        split = "val" if fold == 0 else "train"
        small_labels = small_structure_labels_for_mode(label_mode)
        for patch_index in range(patches_per_case):
            rng = np.random.default_rng(seed + case_index * 1009 + patch_index)
            mode = sampling_mode_for_index(patch_index, sampling_strategy, label_mode=label_mode)
            center = choose_center(label, patch_shape, mode, rng, small_labels=small_labels)
            image_patch, origin = crop_patch(image, center, patch_shape, fill_value=0)
            label_patch, _ = crop_patch(label, center, patch_shape, fill_value=0)
            label_values = np.unique(label_patch).astype(int).tolist()
            patch_id = f"{case.case_id}_p{patch_index:03d}"
            cache_path = npz_dir / f"{patch_id}.npz"
            if force or not cache_path.exists():
                np.savez_compressed(
                    cache_path,
                    image=image_patch.astype(np.float16),
                    label=label_patch.astype(np.int16),
                    case_id=np.asarray(case.case_id),
                    source_shape=np.asarray(source_shape, dtype=np.int32),
                    spacing=np.asarray(spacing, dtype=np.float32),
                    patch_origin=np.asarray(origin, dtype=np.int32),
                    patch_shape=np.asarray(patch_shape, dtype=np.int32),
                    label_values=np.asarray(label_values, dtype=np.int16),
                    sampling_mode=np.asarray(mode),
                )
                generated += 1
            else:
                reused += 1
            fg_fraction = float((label_patch > 0).sum() / max(1, label_patch.size))
            rows.append(
                {
                    "patch_id": patch_id,
                    "case_id": case.case_id,
                    "dataset_id": dataset_id,
                    "input_path": str(cache_path),
                    "label": "available",
                    "task_type": "segmentation",
                    "input_type": "npz_patch",
                    "modality": "cbct",
                    "mask_path": str(cache_path),
                    "cache_path": str(cache_path),
                    "split": split,
                    "fold": fold,
                    "label_source": case.label_source,
                    "source_image_path": str(case.image_path),
                    "source_mask_path": str(case.label_path),
                    "source_shape": "x".join(str(item) for item in source_shape),
                    "spacing": "x".join(f"{item:.6g}" for item in spacing),
                    "patch_shape": "x".join(str(item) for item in patch_shape),
                    "patch_origin": "x".join(str(item) for item in origin),
                    "sampling_mode": mode,
                    "label_values": "|".join(str(item) for item in label_values),
                    "foreground_voxel_fraction": fg_fraction,
                }
            )
        del image, label
    manifest_path = output_dir / f"{dataset_id.lower()}_anatomy_highres_patch_manifest.csv"
    write_csv(manifest_path, rows, PATCH_MANIFEST_FIELDS)
    return {
        "dataset_id": dataset_id,
        "cache_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "case_count": len(selected_cases),
        "patch_count": len(rows),
        "generated_patch_count": generated,
        "reused_patch_count": reused,
        "patch_shape": list(patch_shape),
        "patches_per_case": patches_per_case,
        "label_mode": label_mode,
        "label_names": label_names_for_mode(label_mode),
        "sampling_strategy": sampling_strategy,
        "source_kinds": sorted({case.source_kind for case in selected_cases}),
    }


def read_patch_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def patch_data_info(rows: list[dict[str, Any]], *, label_mode: str = "anatomy6") -> dict[str, Any]:
    label_names = label_names_for_mode(label_mode)
    counts = np.zeros(len(label_names), dtype=np.float64)
    foreground_voxels = 0
    total_voxels = 0
    shape = None
    for row in rows:
        with np.load(row["cache_path"]) as payload:
            label = payload["label"]
            shape = label.shape
            values, value_counts = np.unique(label, return_counts=True)
        total_voxels += int(label.size)
        for value, count in zip(values, value_counts):
            if 0 <= int(value) < len(counts):
                counts[int(value)] += float(count)
            if int(value) > 0:
                foreground_voxels += int(count)
    return {
        "target_shape": list(shape or DEFAULT_PATCH_SHAPE),
        "n_classes": len(label_names),
        "foreground_labels": [label for label in sorted(label_names) if label > 0],
        "label_voxel_counts": counts.tolist(),
        "foreground_voxel_fraction": foreground_voxels / max(1, total_voxels),
        "label_names": label_names,
    }


def split_rows(rows: list[dict[str, Any]], overfit_cases: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if overfit_cases > 0:
        selected_case_ids = []
        for row in rows:
            if row["case_id"] not in selected_case_ids:
                selected_case_ids.append(row["case_id"])
            if len(selected_case_ids) >= overfit_cases:
                break
        selected = [row for row in rows if row["case_id"] in set(selected_case_ids)]
        return selected, selected
    train = [row for row in rows if row.get("split") == "train"]
    val = [row for row in rows if row.get("split") == "val"]
    return train, val


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate_patch_model(
    model: torch.nn.Module,
    rows: list[dict[str, Any]],
    *,
    labels: Iterable[int],
    device: torch.device,
    max_val_patches: int,
    use_amp: bool,
    label_names: dict[int, str],
) -> dict[str, Any]:
    model.eval()
    rows = rows[:max_val_patches]
    per_label: dict[int, list[dict[str, Any]]] = {int(label): [] for label in labels}
    prediction_positive = 0
    target_positive = 0
    total = 0
    with torch.no_grad():
        for row in rows:
            with np.load(row["cache_path"]) as payload:
                image_np = payload["image"].astype(np.float32, copy=False)
                target = payload["label"].astype(np.int16, copy=False)
            image = torch.from_numpy(image_np[None, None]).to(device)
            with torch.amp.autocast("cuda", enabled=use_amp and device.type == "cuda"):
                logits = _primary_output(model(image))
            prediction = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy().astype(np.int16)
            total += int(target.size)
            prediction_positive += int((prediction > 0).sum())
            target_positive += int((target > 0).sum())
            for label in labels:
                score = binary_dice_iou(prediction == int(label), target == int(label))
                if score["target_present"] or score["prediction_present"]:
                    per_label[int(label)].append(score)
    per_label_summary = {}
    all_dice = []
    all_iou = []
    for label, scores in per_label.items():
        dice_values = [float(item["dice"]) for item in scores if item["dice"] is not None]
        iou_values = [float(item["iou"]) for item in scores if item["iou"] is not None]
        per_label_summary[str(label)] = {
            "label_name": label_names[label],
            "dice": float(np.mean(dice_values)) if dice_values else None,
            "iou": float(np.mean(iou_values)) if iou_values else None,
            "evaluated_patches": len(scores),
        }
        all_dice.extend(dice_values)
        all_iou.extend(iou_values)
    return {
        "patch_count": len(rows),
        "foreground_mean_dice": float(np.mean(all_dice)) if all_dice else None,
        "foreground_mean_iou": float(np.mean(all_iou)) if all_iou else None,
        "prediction_positive_fraction": prediction_positive / max(1, total),
        "target_positive_fraction": target_positive / max(1, total),
        "per_label": per_label_summary,
    }


def train_patch_model(
    candidate: ModelCandidate,
    dataset_id: str,
    rows: list[dict[str, Any]],
    *,
    device: torch.device,
    max_train_batches: int,
    max_val_patches: int,
    learning_rate: float,
    seed: int,
    overfit_cases: int,
    use_amp: bool,
    label_mode: str,
    loss_name: str,
    class_weighting: str,
) -> dict[str, Any]:
    set_seed(seed)
    train_rows, val_rows = split_rows(rows, overfit_cases)
    data_info = patch_data_info(train_rows, label_mode=label_mode)
    started = time.perf_counter()
    status = "completed"
    error = ""
    peak_memory_mb = None
    train_loss = None
    train_batches = 0
    epochs_seen = 0
    samples_seen = 0
    metrics: dict[str, Any] = {}
    model = None
    try:
        if not train_rows:
            raise ValueError(f"No train rows for {dataset_id}")
        if not val_rows:
            raise ValueError(f"No val rows for {dataset_id}")
        model = candidate.constructor(tuple(data_info["target_shape"]), data_info["n_classes"]).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        loss_fn = build_segmentation_loss(
            loss_name=loss_name,
            data_info=data_info,
            target_labels="foreground",
            class_weighting=class_weighting,
            device=device,
        )
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp and device.type == "cuda")
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        losses = []
        while train_batches < max_train_batches:
            loader = DataLoader(PatchDataset(train_rows), batch_size=1, shuffle=True, num_workers=0)
            epochs_seen += 1
            for image, label in loader:
                if train_batches >= max_train_batches:
                    break
                image = image.to(device, non_blocking=True)
                label = label.to(device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                with torch.amp.autocast("cuda", enabled=use_amp and device.type == "cuda"):
                    logits = _primary_output(model(image))
                    loss = loss_fn(logits, label)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                train_batches += 1
                samples_seen += int(image.shape[0])
                losses.append(float(loss.detach().cpu()))
        train_loss = float(np.mean(losses)) if losses else None
        metrics = evaluate_patch_model(
            model,
            val_rows,
            labels=data_info["foreground_labels"],
            device=device,
            max_val_patches=max_val_patches,
            use_amp=use_amp,
            label_names=data_info["label_names"],
        )
        if device.type == "cuda":
            peak_memory_mb = float(torch.cuda.max_memory_allocated(device) / (1024**2))
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            status = "failed_oom"
            error = str(exc)
            if device.type == "cuda":
                torch.cuda.empty_cache()
        else:
            status = "failed_runtime"
            error = str(exc)
    except Exception as exc:  # noqa: BLE001
        status = "failed_runtime"
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if model is not None:
            del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return {
        "dataset_id": dataset_id,
        "model_id": candidate.model_id,
        "display_name": candidate.display_name,
        "status": status,
        "error": error,
        "train_batches": train_batches,
        "epochs_seen": epochs_seen,
        "samples_seen": samples_seen,
        "train_loss": train_loss,
        "loss_name": loss_name,
        "class_weighting": class_weighting,
        "label_mode": label_mode,
        "val_patches": metrics.get("patch_count", 0),
        "foreground_mean_dice": metrics.get("foreground_mean_dice"),
        "foreground_mean_iou": metrics.get("foreground_mean_iou"),
        "prediction_positive_fraction": metrics.get("prediction_positive_fraction"),
        "target_positive_fraction": metrics.get("target_positive_fraction"),
        "per_label": metrics.get("per_label", {}),
        "peak_memory_mb": peak_memory_mb,
        "elapsed_seconds": time.perf_counter() - started,
    }


def selected_models(model_ids: str) -> list[ModelCandidate]:
    catalog = combined_model_catalog()
    requested = [item.strip() for item in model_ids.split(",") if item.strip()]
    output = []
    for model_id in requested:
        if model_id not in catalog:
            raise ValueError(f"Unknown model: {model_id}")
        output.append(catalog[model_id])
    return output


def nnunet_command(
    project_dataset_root: Path, configuration: str = "3d_fullres", trainer: str = "nnUNetTrainerNoMirroring"
) -> dict[str, Any]:
    nnunet_root = project_dataset_root / "d024_dentvoxel" / "derived" / "nnunet"
    return {
        "dataset_id": 124,
        "configuration": configuration,
        "fold": 0,
        "trainer": trainer,
        "env": {
            "nnUNet_raw": str(nnunet_root / "nnUNet_raw"),
            "nnUNet_preprocessed": str(nnunet_root / "nnUNet_preprocessed"),
            "nnUNet_results": str(nnunet_root / "nnUNet_results"),
        },
        "command": f"nnUNetv2_train 124 {configuration} 0 -tr {trainer}",
    }


def run_nnunet(command_info: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    env = {**command_info["env"]}
    command = command_info["command"]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env={**os.environ, **env},
        )
        return {
            "status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "returncode": None,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "elapsed_seconds": time.perf_counter() - started,
        }


def compact_per_label(row: dict[str, Any]) -> str:
    keep_names = {
        "jawbone",
        "mandibular_canal",
        "maxillary_sinus",
        "maxilla_or_upper_jawbone",
        "mandible_or_lower_jawbone",
        "right_mandibular_canal",
        "left_mandibular_canal",
        "right_maxillary_sinus",
        "left_maxillary_sinus",
    }
    parts = []
    for label_id, item in row.get("per_label", {}).items():
        name = str(item.get("label_name", label_id))
        if name in keep_names:
            parts.append(f"{name} {format_metric(item.get('dice'))}")
    return ", ".join(parts[:6])


def history_rows_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    config = summary.get("config", {})
    for result in summary.get("results", []):
        if result.get("status") != "completed":
            continue
        rows.append(
            {
                "run_id": summary.get("run_id", ""),
                "dataset_id": result.get("dataset_id", ""),
                "model_id": result.get("model_id", ""),
                "patch_shape": config.get("patch_shape", ""),
                "label_mode": config.get("label_mode", result.get("label_mode", "")),
                "sampling_strategy": config.get("sampling_strategy", ""),
                "loss": result.get("loss_name", config.get("loss", "")),
                "train_batches": result.get("train_batches", 0),
                "foreground_mean_dice": result.get("foreground_mean_dice"),
                "foreground_mean_iou": result.get("foreground_mean_iou"),
                "peak_memory_mb": result.get("peak_memory_mb"),
                "key_classes": compact_per_label(result),
            }
        )
    return rows


def collect_comparison_history(output_root: Path, current_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in output_root.glob("*/anatomy_highres_patch_experiment_summary.json"):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.extend(history_rows_from_summary(payload))
    rows.extend(history_rows_from_summary(current_summary))
    deduped = {}
    for row in rows:
        key = (
            row["run_id"],
            row["dataset_id"],
            row["model_id"],
            row["patch_shape"],
            row["label_mode"],
            row["sampling_strategy"],
            row["loss"],
        )
        deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda item: (
            str(item.get("label_mode", "")),
            str(item.get("dataset_id", "")),
            -(float(item.get("foreground_mean_dice") or 0.0)),
        ),
    )


def render_history_table(rows: list[dict[str, Any]]) -> str:
    table_rows = []
    for row in rows:
        table_rows.append(
            f"| `{row['run_id']}` | {row['label_mode']} | {row['dataset_id']} | {row['patch_shape']} | "
            f"{row['loss']} | {row['sampling_strategy']} | {format_metric(row.get('foreground_mean_dice'))} | "
            f"{format_metric(row.get('foreground_mean_iou'))} | {row.get('train_batches', 0)} | "
            f"{format_metric(row.get('peak_memory_mb'))} | {row.get('key_classes', '')} |"
        )
    return "\n".join(table_rows)


def render_report(summary: dict[str, Any], *, language: str) -> str:
    result_rows = []
    for row in summary["results"]:
        result_rows.append(
            f"| {row['dataset_id']} | {row['model_id']} | {row['status']} | "
            f"{format_metric(row.get('foreground_mean_dice'))} | {format_metric(row.get('foreground_mean_iou'))} | "
            f"{format_metric(row.get('target_positive_fraction'))} | {format_metric(row.get('prediction_positive_fraction'))} | "
            f"{row.get('train_batches', 0)} | {format_metric(row.get('peak_memory_mb'))} | {format_metric(row.get('elapsed_seconds'))} |"
        )
    cache_rows = []
    for dataset_id, item in summary["patch_caches"].items():
        cache_rows.append(
            f"| {dataset_id} | {item['case_count']} | {item['patch_count']} | {item['generated_patch_count']} | "
            f"`{item['manifest_path']}` | {', '.join(item.get('source_kinds', []))} |"
        )
    history_rows = render_history_table(summary.get("comparison_history", []))
    sampling_description = sampling_strategy_description(
        summary["config"].get("sampling_strategy", "default"),
        label_mode=summary["config"].get("label_mode", "anatomy6"),
    )
    if language == "zh":
        return f"""# 解剖高分辨率 Patch 分割实验报告（中文）

## 目标

本轮实验用于验证低 Dice 是否主要来自 `64x64x64` 全体积压缩。实验改用 `{summary['config']['patch_shape']}` 高分辨率 patch cache，并将运行输入固定在项目本地 `derived/highres_patch/`。

医学边界：D024/D036 均为 CBCT 解剖结构分割数据，不包含术中 ICG 或颌骨骨髓炎临床结局标签。

## 数据缓存

| 数据集 | 病例数 | Patch 数 | 新生成 Patch | Manifest | 来源 |
| --- | ---: | ---: | ---: | --- | --- |
{chr(10).join(cache_rows)}

## 实验设置

- 设备：`{summary['environment']['device']}`；GPU：`{summary['environment'].get('cuda_device_name')}`
- 模型：`{', '.join(summary['config']['models'])}`
- 标签模式：`{summary['config'].get('label_mode', 'anatomy6')}`；采样策略：`{summary['config'].get('sampling_strategy', 'default')}`
- Loss：`{summary['config'].get('loss', 'dice_ce')}`；类别权重：`{summary['config'].get('class_weighting', 'sqrt_inverse')}`；AMP：`{summary['config']['amp']}`
- 训练 batch：`{summary['config']['max_train_batches']}`；验证 patch：`{summary['config']['max_val_patches']}`
- 采样说明：{sampling_description}

## 结果

| 数据集 | 模型 | 状态 | Dice | IoU | Target FG | Pred FG | Train batches | Peak MB | Seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(result_rows)}

## 历史对照

| Run | 标签模式 | 数据集 | Patch | Loss | 采样 | Dice | IoU | Train batches | Peak MB | 关键类别 Dice |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
{history_rows}

## nnU-Net 入口

`{summary['nnunet']['command']}`

环境变量：

```json
{json.dumps(summary['nnunet']['env'], ensure_ascii=False, indent=2)}
```

## 判断

本报告应与 `public_cbct_3dataset_segmentation_benchmark_zh.md` 分开解读：64³ 结果只代表 smoke，当前结果代表高分辨率 patch 训练链路。历史对照显示，`coarse3 + 160x224x224 + class_cycle` 已在 D024/D036 达到 0.3 以上 Dice，可作为当前可用的粗粒度解剖先验；新增 `anatomy4` 中间粒度任务后，D024 达到 `0.2989`，D036 达到 `0.3860`，说明合并左右下颌管和左右上颌窦后，模型已经能稳定学到接近或超过 0.3 Dice 的可用解剖结构表示。

本轮 loss 对照显示，`tversky_focal` 将 D024 anatomy6 从 `0.1394` 提升到 `0.1986`，`dice_focal` 将 D036 anatomy6 从 `0.1004` 提升到 `0.1200`。新增 `small_cycle` 采样后，D036 在 `160x224x224 + dice_focal` 下进一步提升到 `0.1813`，但 D024 在同类小结构强化下下降到 `0.1649`，说明 D024 更依赖大结构稳定监督，D036 更受益于小结构采样。延长到 800 batch 后，D024 anatomy6 达到 `0.2090`，D036 anatomy6 达到 `0.2096`，两者都确认了训练预算仍然带来增益。

`192x256x256` 已通过 8 batch 显存 sanity，峰值约 `6652 MB`，但短训练结果不能和 300 batch 对照直接比较。`128x160x160 + small_cycle` 在当前独立 cache 下未复现旧的高 Dice，提示旧结果可能受 cache、采样或验证切分差异影响。`canal_focus` 在 D036 上下降到 `0.0446`，说明单纯过采样下颌管会破坏 jaw/sinus 的共同表示。下一步应将 `anatomy4` 作为第一阶段结构先验，再做局部左右细分 refinement；完整 `anatomy6` 暂不直接承诺 0.3。
"""
    return f"""# Anatomy High-Resolution Patch Segmentation Experiment Report

## Objective

This experiment tests whether the low Dice scores are mainly caused by `64x64x64` full-volume compression. The run uses `{summary['config']['patch_shape']}` high-resolution patch caches, with runtime inputs fixed under local project `derived/highres_patch/` directories.

Medical boundary: D024/D036 are CBCT anatomical segmentation datasets. They do not contain intraoperative ICG labels or clinical jaw osteomyelitis outcome labels.

## Patch Caches

| Dataset | Cases | Patches | Generated Patches | Manifest | Source |
| --- | ---: | ---: | ---: | --- | --- |
{chr(10).join(cache_rows)}

## Settings

- Device: `{summary['environment']['device']}`; GPU: `{summary['environment'].get('cuda_device_name')}`
- Models: `{', '.join(summary['config']['models'])}`
- Label mode: `{summary['config'].get('label_mode', 'anatomy6')}`; sampling strategy: `{summary['config'].get('sampling_strategy', 'default')}`
- Loss: `{summary['config'].get('loss', 'dice_ce')}`; class weighting: `{summary['config'].get('class_weighting', 'sqrt_inverse')}`; AMP: `{summary['config']['amp']}`
- Train batches: `{summary['config']['max_train_batches']}`; validation patches: `{summary['config']['max_val_patches']}`
- Sampling: {sampling_description}

## Results

| Dataset | Model | Status | Dice | IoU | Target FG | Pred FG | Train batches | Peak MB | Seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(result_rows)}

## Historical Comparison

| Run | Label mode | Dataset | Patch | Loss | Sampling | Dice | IoU | Train batches | Peak MB | Key class Dice |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
{history_rows}

## nnU-Net Entry

`{summary['nnunet']['command']}`

Environment:

```json
{json.dumps(summary['nnunet']['env'], ensure_ascii=False, indent=2)}
```

## Interpretation

This report must be read separately from `public_cbct_3dataset_segmentation_benchmark_en.md`: the 64-cube result is smoke evidence, while this run validates the high-resolution patch training path. The historical comparison shows that `coarse3 + 160x224x224 + class_cycle` already reaches Dice above 0.3 on D024/D036, making it usable as the current coarse anatomical-prior task. With the new intermediate `anatomy4` task, D024 reaches `0.2989` and D036 reaches `0.3860`; after merging left/right mandibular canal and left/right maxillary sinus labels, the model now learns a usable anatomical representation around or above 0.3 Dice.

The loss comparison shows that `tversky_focal` improves D024 anatomy6 from `0.1394` to `0.1986`, while `dice_focal` improves D036 anatomy6 from `0.1004` to `0.1200`. With the new `small_cycle` sampler, D036 further improves to `0.1813` under `160x224x224 + dice_focal`, while D024 drops to `0.1649` under a similar small-structure-heavy setting. This suggests that D024 still needs stable large-structure supervision, while D036 benefits more from small-structure sampling. Extending training to 800 batches raises D024 anatomy6 to `0.2090` and D036 anatomy6 to `0.2096`, confirming that training budget still provides measurable gains.

The `192x256x256` setting passed an 8-batch memory sanity check with about `6652 MB` peak usage, but the short-run Dice is not comparable to 300-batch experiments. `128x160x160 + small_cycle` did not reproduce the older high Dice after using an isolated cache, which suggests that the older result may have depended on cache, sampling, or validation split differences. `canal_focus` drops D036 to `0.0446`, showing that simply oversampling mandibular-canal centers damages the shared jaw/sinus representation. Next work should use `anatomy4` as the first-stage structural prior and then train local laterality-aware refinement; full `anatomy6` should not be claimed as 0.3-ready yet.
"""


def format_metric(value: Any) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.4f}"


def write_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    ensure_dir(report_dir)
    zh = report_dir / "anatomy_highres_patch_experiment_zh.md"
    en = report_dir / "anatomy_highres_patch_experiment_en.md"
    zh.write_text(render_report(summary, language="zh"), encoding="utf-8")
    en.write_text(render_report(summary, language="en"), encoding="utf-8")
    return {"zh_report": str(zh), "en_report": str(en)}


def build_cases_for_dataset(
    dataset_id: str,
    project_dataset_root: Path,
    archive_dataset_root: Path,
    *,
    allow_archive_source: bool,
) -> list[SourceCase]:
    if dataset_id == "D024":
        return load_d024_cases(project_dataset_root)
    if dataset_id == "D036":
        return load_d036_cases(project_dataset_root, archive_dataset_root, allow_archive_source=allow_archive_source)
    raise ValueError(f"Unsupported dataset: {dataset_id}")


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = ensure_dir(Path(args.output_root) / run_id)
    project_dataset_root = Path(args.project_dataset_root)
    archive_dataset_root = Path(args.archive_dataset_root)
    patch_shape = parse_shape(args.patch_shape)
    dataset_ids = [item.strip().upper() for item in args.datasets.split(",") if item.strip()]
    model_ids = [item.strip() for item in args.models.split(",") if item.strip()]
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else args.device)
    if device.type == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    environment = {
        "device": str(device),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    patch_caches: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    localization: list[dict[str, Any]] = []
    selected = selected_models(args.models)
    for dataset_id in dataset_ids:
        cases = build_cases_for_dataset(
            dataset_id,
            project_dataset_root,
            archive_dataset_root,
            allow_archive_source=args.allow_archive_source,
        )
        if args.localize_raw and dataset_id == "D036":
            localization.append(
                localize_d036_cases(cases, archive_dataset_root, project_dataset_root, args.max_source_cases)
            )
            cases = build_cases_for_dataset(
                dataset_id,
                project_dataset_root,
                archive_dataset_root,
                allow_archive_source=args.allow_archive_source,
            )
        cache_summary = build_patch_cache(
            dataset_id,
            cases,
            project_dataset_root,
            patch_shape=patch_shape,
            patches_per_case=args.patches_per_case,
            seed=args.seed,
            force=args.force_cache,
            max_cases=args.max_source_cases,
            label_mode=args.label_mode,
            sampling_strategy=args.sampling_strategy,
        )
        patch_caches[dataset_id] = cache_summary
        rows = read_patch_manifest(Path(cache_summary["manifest_path"]))
        if not args.build_cache_only:
            for candidate in selected:
                if dataset_id == "D036" and candidate.model_id == "monai_swinunetr_tiny" and args.skip_d036_swin:
                    continue
                print(f"[start] {dataset_id} {candidate.model_id}", flush=True)
                result = train_patch_model(
                    candidate,
                    dataset_id,
                    rows,
                    device=device,
                    max_train_batches=args.max_train_batches,
                    max_val_patches=args.max_val_patches,
                    learning_rate=args.learning_rate,
                    seed=args.seed,
                    overfit_cases=args.overfit_cases,
                    use_amp=args.amp,
                    label_mode=args.label_mode,
                    loss_name=args.loss,
                    class_weighting=args.class_weighting,
                )
                results.append(result)
                print(f"[done] {dataset_id} {candidate.model_id} {result['status']}", flush=True)
    nnunet = nnunet_command(project_dataset_root)
    if args.run_nnunet:
        nnunet["run_result"] = run_nnunet(nnunet, args.nnunet_timeout_seconds)
    summary = {
        "run_id": run_id,
        "created_utc": datetime.now(UTC).isoformat(),
        "config": {
            "datasets": dataset_ids,
            "models": model_ids,
            "patch_shape": "x".join(str(item) for item in patch_shape),
            "patches_per_case": args.patches_per_case,
            "max_source_cases": args.max_source_cases,
            "max_train_batches": args.max_train_batches,
            "max_val_patches": args.max_val_patches,
            "overfit_cases": args.overfit_cases,
            "amp": args.amp,
            "label_mode": args.label_mode,
            "sampling_strategy": args.sampling_strategy,
            "loss": args.loss,
            "class_weighting": args.class_weighting,
            "allow_archive_source": args.allow_archive_source,
            "localize_raw": args.localize_raw,
        },
        "environment": environment,
        "localization": localization,
        "patch_caches": patch_caches,
        "results": results,
        "nnunet": nnunet,
        "medical_boundary": "Research and competition validation platform; D024/D036 are anatomy segmentation datasets.",
    }
    summary["paths"] = {
        "summary_json": str(write_json(output_dir / "anatomy_highres_patch_experiment_summary.json", summary)),
        "results_csv": str(
            write_csv(
                output_dir / "anatomy_highres_patch_experiment_results.csv",
                results,
                list(results[0].keys()) if results else ["status"],
            )
        ),
    }
    summary["comparison_history"] = collect_comparison_history(Path(args.output_root), summary)
    summary["reports"] = write_reports(summary, Path(args.report_dir))
    write_json(output_dir / "anatomy_highres_patch_experiment_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run high-resolution patch experiments for public CBCT anatomy segmentation."
    )
    parser.add_argument("--datasets", default="D024,D036")
    parser.add_argument("--models", default="monai_segresnetds,monai_swinunetr_tiny")
    parser.add_argument("--project-dataset-root", default=str(PROJECT_DATASET_ROOT))
    parser.add_argument("--archive-dataset-root", default=str(ARCHIVE_DATASET_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--patch-shape", default="96x128x128")
    parser.add_argument("--patches-per-case", type=int, default=8)
    parser.add_argument("--max-source-cases", type=int, default=None)
    parser.add_argument("--max-train-batches", type=int, default=800)
    parser.add_argument("--max-val-patches", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--overfit-cases", type=int, default=0)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--label-mode", default="anatomy6", choices=LABEL_MODE_CHOICES)
    parser.add_argument("--sampling-strategy", default="default", choices=SAMPLING_STRATEGY_CHOICES)
    parser.add_argument("--loss", default="dice_ce", choices=["ce", "dice_ce", "dice_focal", "tversky_focal"])
    parser.add_argument("--class-weighting", default="sqrt_inverse", choices=["none", "inverse", "sqrt_inverse"])
    parser.add_argument("--allow-archive-source", action="store_true")
    parser.add_argument("--localize-raw", action="store_true")
    parser.add_argument("--force-cache", action="store_true")
    parser.add_argument("--build-cache-only", action="store_true")
    parser.add_argument("--skip-d036-swin", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-nnunet", action="store_true")
    parser.add_argument("--nnunet-timeout-seconds", type=int, default=3600)
    args = parser.parse_args()
    summary = run_experiment(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
