from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

JAW_ROI_LABELS: dict[int, str] = {
    1: "maxilla",
    2: "mandible",
    35: "r_mandibular_canal",
    36: "l_mandibular_canal",
    37: "r_maxillary_sinus",
    38: "l_maxillary_sinus",
}

LABEL_GROUPS: dict[str, list[int]] = {
    "jaw": [1, 2],
    "teeth": list(range(3, 35)),
    "canal": [35, 36],
    "sinus": [37, 38],
}

TUBULAR_LABELS = [35, 36]


@dataclass(frozen=True)
class NnUNetTaskSpec:
    task_name: str
    dataset_id: int
    dataset_name: str
    description: str
    labels: dict[str, int]
    original_to_target: dict[int, int] | None
    label_groups: dict[str, list[int]]
    tubular_labels: list[int]

    @property
    def folder_name(self) -> str:
        return f"Dataset{self.dataset_id:03d}_{self.dataset_name}"


def d024_task_spec(task_name: str, metadata: dict[str, Any] | None = None) -> NnUNetTaskSpec:
    normalized = task_name.lower().replace("_", "-")
    if normalized == "jaw-roi":
        return NnUNetTaskSpec(
            task_name="jaw-roi",
            dataset_id=124,
            dataset_name="DentVoxelJawROI",
            description=(
                "D024 DentVoxel reduced jaw ROI task: maxilla, mandible, mandibular canals, "
                "and maxillary sinuses remapped to sequential labels."
            ),
            labels={
                "background": 0,
                "maxilla": 1,
                "mandible": 2,
                "r_mandibular_canal": 3,
                "l_mandibular_canal": 4,
                "r_maxillary_sinus": 5,
                "l_maxillary_sinus": 6,
            },
            original_to_target={0: 0, 1: 1, 2: 2, 35: 3, 36: 4, 37: 5, 38: 6},
            label_groups={"jaw": [1, 2], "canal": [3, 4], "sinus": [5, 6]},
            tubular_labels=[3, 4],
        )
    if normalized == "full-39":
        labels = _metadata_labels_to_nnunet_labels(metadata or {})
        return NnUNetTaskSpec(
            task_name="full-39",
            dataset_id=125,
            dataset_name="DentVoxelFull39",
            description="D024 DentVoxel full 39-class anatomical instance segmentation task.",
            labels=labels,
            original_to_target=None,
            label_groups=dict(LABEL_GROUPS),
            tubular_labels=list(TUBULAR_LABELS),
        )
    raise ValueError(f"Unsupported D024 task: {task_name}")


def remap_label_array(label_array: np.ndarray, original_to_target: dict[int, int] | None) -> np.ndarray:
    data = np.asarray(label_array)
    if original_to_target is None:
        return data.astype(np.int16, copy=False)
    output = np.zeros(data.shape, dtype=np.int16)
    for source_label, target_label in original_to_target.items():
        if source_label == 0:
            continue
        output[data == source_label] = target_label
    return output


def build_nnunet_dataset_json(
    spec: NnUNetTaskSpec, num_training: int, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    source = metadata or {}
    return {
        "name": spec.dataset_name,
        "description": spec.description,
        "reference": source.get("reference", {}),
        "licence": source.get("license") or source.get("licence") or "CC BY",
        "release": source.get("version", "1.0"),
        "channel_names": {"0": "CT"},
        "labels": spec.labels,
        "numTraining": int(num_training),
        "file_ending": ".nii.gz",
        "source_dataset": {
            "dataset_id": "D024",
            "dataset_name": source.get("name", "DentVoxel"),
            "modality": "CBCT",
            "spacing_mm": source.get("acquisition_protocol", {}).get("spacing_mm"),
        },
    }


def build_fold_splits(case_ids: list[str], folds: int = 5) -> list[dict[str, list[str]]]:
    if folds < 2:
        raise ValueError("folds must be at least 2")
    sorted_cases = sorted(case_ids)
    splits: list[dict[str, list[str]]] = []
    for fold in range(folds):
        val = [case_id for index, case_id in enumerate(sorted_cases) if index % folds == fold]
        train = [case_id for case_id in sorted_cases if case_id not in set(val)]
        splits.append({"train": train, "val": val})
    return splits


def _metadata_labels_to_nnunet_labels(metadata: dict[str, Any]) -> dict[str, int]:
    labels = metadata.get("labels") or {}
    if not labels:
        raise ValueError("D024 metadata is missing labels.")
    converted = {str(name): int(value) for value, name in labels.items()}
    if converted.get("background") != 0:
        raise ValueError("D024 metadata must contain background label 0.")
    return dict(sorted(converted.items(), key=lambda item: item[1]))
