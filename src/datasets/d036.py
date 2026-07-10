from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

D036_DATASET_ROOT = Path("research/datasets/public-candidates/d036_toothfairy2")
D036_RAW_DATASET_DIR = D036_DATASET_ROOT / "raw" / "Dataset112_ToothFairy2"
D036_MANIFEST_PATH = D036_DATASET_ROOT / "derived" / "manifests" / "d036_toothfairy2_manifest.csv"

D036_RAW_LABELS = {
    0: "background",
    1: "lower_jawbone",
    2: "upper_jawbone",
    3: "left_inferior_alveolar_canal",
    4: "right_inferior_alveolar_canal",
    5: "left_maxillary_sinus",
    6: "right_maxillary_sinus",
}

D036_NNUNET_LABELS = {
    "jawbone_binary": {
        0: "background",
        1: "maxilla_and_mandible_jawbones",
    },
    "jaw2": {
        0: "background",
        1: "maxilla_or_upper_jawbone",
        2: "mandible_or_lower_jawbone",
    },
    "mandible_binary": {
        0: "background",
        1: "mandible_or_lower_jawbone",
    },
    "anatomy4": {
        0: "background",
        1: "maxilla_or_upper_jawbone",
        2: "mandible_or_lower_jawbone",
        3: "mandibular_canal",
        4: "maxillary_sinus",
    },
    "coarse3": {
        0: "background",
        1: "jawbone",
        2: "mandibular_canal",
        3: "maxillary_sinus",
    },
}


@dataclass(frozen=True)
class D036Case:
    case_id: str
    image_path: Path
    label_path: Path
    label_source: str = "D036 ToothFairy2 maxillofacial CBCT segmentation"


def available_d036_cases(
    *,
    project_root: str | Path = ".",
    manifest_path: str | Path | None = None,
    case_ids: set[str] | None = None,
) -> list[D036Case]:
    root = Path(project_root)
    manifest = _resolve_path(root, manifest_path or D036_MANIFEST_PATH)
    if not manifest.exists():
        raw_dir = _resolve_path(root, D036_RAW_DATASET_DIR)
        return _scan_raw_cases(raw_dir, case_ids=case_ids)

    cases: list[D036Case] = []
    seen: set[str] = set()
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = str(row.get("case_id") or "").strip()
            if not case_id or case_id in seen:
                continue
            if case_ids and case_id not in case_ids:
                continue
            image_path = _resolve_path(root, str(row.get("input_path") or ""))
            label_path = _resolve_path(root, str(row.get("mask_path") or ""))
            if image_path.exists() and label_path.exists():
                cases.append(
                    D036Case(
                        case_id=case_id,
                        image_path=image_path,
                        label_path=label_path,
                        label_source=str(row.get("label_source") or "D036 ToothFairy2 maxillofacial CBCT segmentation"),
                    )
                )
                seen.add(case_id)
    return sorted(cases, key=lambda item: item.case_id)


def remap_d036_label(label: np.ndarray, *, label_mode: str) -> np.ndarray:
    data = np.asarray(label)
    output = np.zeros(data.shape, dtype=np.uint8)
    if label_mode == "jawbone_binary":
        output[np.isin(data, [1, 2])] = 1
        return output
    if label_mode == "jaw2":
        output[data == 2] = 1
        output[data == 1] = 2
        return output
    if label_mode == "mandible_binary":
        output[data == 1] = 1
        return output
    if label_mode == "anatomy4":
        output[data == 2] = 1
        output[data == 1] = 2
        output[np.isin(data, [3, 4])] = 3
        output[np.isin(data, [5, 6])] = 4
        return output
    if label_mode == "coarse3":
        output[np.isin(data, [1, 2])] = 1
        output[np.isin(data, [3, 4])] = 2
        output[np.isin(data, [5, 6])] = 3
        return output
    raise ValueError(f"Unsupported D036 label mode: {label_mode}")


def nnunet_label_mapping(label_mode: str) -> dict[str, int]:
    labels = D036_NNUNET_LABELS.get(label_mode)
    if labels is None:
        raise ValueError(f"Unsupported D036 label mode: {label_mode}")
    return {name: int(value) for value, name in labels.items()}


def build_nnunet_dataset_json(*, dataset_name: str, label_mode: str, num_training: int) -> dict[str, Any]:
    return {
        "channel_names": {"0": "CBCT"},
        "labels": nnunet_label_mapping(label_mode),
        "numTraining": int(num_training),
        "file_ending": ".nii.gz",
        "dataset_name": dataset_name,
        "reference": "https://ditto.ing.unimore.it/toothfairy2/",
        "license": "CC-BY-SA 4.0",
        "release": "D036 ToothFairy2 local conversion for Osteo Vision platform validation",
    }


def _scan_raw_cases(raw_dir: Path, *, case_ids: set[str] | None) -> list[D036Case]:
    images_dir = raw_dir / "imagesTr"
    labels_dir = raw_dir / "labelsTr"
    if not images_dir.exists() or not labels_dir.exists():
        return []
    cases: list[D036Case] = []
    for image_path in sorted(images_dir.glob("*_0000.mha")):
        case_id = image_path.name.removesuffix("_0000.mha")
        if case_ids and case_id not in case_ids:
            continue
        label_path = labels_dir / f"{case_id}.mha"
        if label_path.exists():
            cases.append(D036Case(case_id=case_id, image_path=image_path, label_path=label_path))
    return cases


def _resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path
