from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nibabel as nib
import numpy as np

from scripts.preprocess_d024_dentvoxel import (
    DATASET_ROOT_IN_ZIP,
    DEFAULT_DATASET_DIR,
    build_case_pairs,
    load_dataset_metadata,
)
from src.datasets.d024 import build_fold_splits, build_nnunet_dataset_json, d024_task_spec, remap_label_array

DEFAULT_NNUNET_ROOT = DEFAULT_DATASET_DIR / "derived" / "nnunet"
DEFAULT_REPORT_DIR = Path("research/reports/modeling")


def convert_d024_to_nnunet(
    *,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_root: Path = DEFAULT_NNUNET_ROOT,
    task: str = "jaw-roi",
    folds: int = 5,
    overwrite: bool = False,
) -> dict[str, Any]:
    raw_dataset_dir = dataset_dir / "raw" / DATASET_ROOT_IN_ZIP
    if not raw_dataset_dir.exists():
        raise FileNotFoundError(f"D024 raw dataset directory not found: {raw_dataset_dir}")

    metadata = load_dataset_metadata(raw_dataset_dir)
    spec = d024_task_spec(task, metadata)
    dataset_output = output_root / "nnUNet_raw" / spec.folder_name
    images_tr = dataset_output / "imagesTr"
    labels_tr = dataset_output / "labelsTr"
    images_tr.mkdir(parents=True, exist_ok=True)
    labels_tr.mkdir(parents=True, exist_ok=True)

    cases, pairing = build_case_pairs(raw_dataset_dir)
    converted_cases: list[dict[str, Any]] = []
    skipped_existing = 0
    for case in cases:
        numeric_id = str(case["numeric_id"])
        nnunet_case_id = f"d024_{numeric_id}"
        image_target = images_tr / f"{nnunet_case_id}_0000.nii.gz"
        label_target = labels_tr / f"{nnunet_case_id}.nii.gz"

        if overwrite or not image_target.exists():
            shutil.copy2(case["image_path"], image_target)
        else:
            skipped_existing += 1

        if overwrite or not label_target.exists():
            _write_converted_label(Path(case["label_path"]), label_target, spec.original_to_target)
        else:
            skipped_existing += 1

        converted_cases.append(
            {
                "case_id": nnunet_case_id,
                "source_image": str(case["image_path"]),
                "source_label": str(case["label_path"]),
                "nnunet_image": str(image_target),
                "nnunet_label": str(label_target),
            }
        )

    dataset_json = build_nnunet_dataset_json(spec, len(converted_cases), metadata)
    dataset_json_path = dataset_output / "dataset.json"
    dataset_json_path.write_text(json.dumps(dataset_json, ensure_ascii=False, indent=2), encoding="utf-8")

    splits = build_fold_splits([case["case_id"] for case in converted_cases], folds=folds)
    splits_path = dataset_output / "splits_final.json"
    splits_path.write_text(json.dumps(splits, ensure_ascii=False, indent=2), encoding="utf-8")

    commands = build_nnunet_command_plan(output_root, spec.dataset_id)
    commands_path = dataset_output / "command_plan.json"
    commands_path.write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "dataset_id": "D024",
        "task": spec.task_name,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_raw_dataset_dir": str(raw_dataset_dir),
        "output_root": str(output_root),
        "dataset_output": str(dataset_output),
        "nnunet_raw_dir": str(output_root / "nnUNet_raw"),
        "nnunet_preprocessed_dir": str(output_root / "nnUNet_preprocessed"),
        "nnunet_results_dir": str(output_root / "nnUNet_results"),
        "folder_name": spec.folder_name,
        "dataset_number": spec.dataset_id,
        "case_count": len(converted_cases),
        "pairing": pairing,
        "labels": spec.labels,
        "label_groups": spec.label_groups,
        "tubular_labels": spec.tubular_labels,
        "dataset_json_path": str(dataset_json_path),
        "splits_path": str(splits_path),
        "command_plan_path": str(commands_path),
        "skipped_existing_files": skipped_existing,
        "converted_cases_sample": converted_cases[:5],
        "commands": commands,
        "notes": [
            "CBCT is written as channel name CT so nnU-Net uses CT normalization instead of generic z-score fallback.",
            "Jaw ROI remaps selected anatomical structures to sequential labels and drops teeth to background.",
            "Full-39 keeps DentVoxel labels 0-38 unchanged.",
            "Use the NoMirroring trainer for dental laterality-sensitive classes unless an ablation explicitly enables mirroring.",
        ],
    }
    summary_path = dataset_output / "conversion_summary.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_nnunet_command_plan(output_root: Path, dataset_id: int) -> dict[str, Any]:
    env = {
        "nnUNet_raw": str(output_root / "nnUNet_raw"),
        "nnUNet_preprocessed": str(output_root / "nnUNet_preprocessed"),
        "nnUNet_results": str(output_root / "nnUNet_results"),
    }
    return {
        "environment": env,
        "m0_default_fullres": [
            f"nnUNetv2_plan_and_preprocess -d {dataset_id} -c 3d_fullres --verify_dataset_integrity",
            f"nnUNetv2_train {dataset_id} 3d_fullres 0 -tr nnUNetTrainerNoMirroring",
            f"nnUNetv2_predict -d {dataset_id} -c 3d_fullres -f 0 -tr nnUNetTrainerNoMirroring --save_probabilities",
        ],
        "m1_resenc_candidate": [
            f"nnUNetv2_plan_and_preprocess -d {dataset_id} -pl nnUNetPlannerResEncM -c 3d_fullres --verify_dataset_integrity",
            f"nnUNetv2_train {dataset_id} 3d_fullres 0 -p nnUNetResEncUNetMPlans -tr nnUNetTrainerNoMirroring",
        ],
        "five_fold_template": [
            f"nnUNetv2_train {dataset_id} 3d_fullres <fold 0..4> -tr nnUNetTrainerNoMirroring",
            f"nnUNetv2_find_best_configuration {dataset_id} -c 3d_fullres -tr nnUNetTrainerNoMirroring",
        ],
        "powershell_env_example": [
            f"$env:nnUNet_raw='{env['nnUNet_raw']}'",
            f"$env:nnUNet_preprocessed='{env['nnUNet_preprocessed']}'",
            f"$env:nnUNet_results='{env['nnUNet_results']}'",
        ],
    }


def _write_converted_label(source_path: Path, target_path: Path, original_to_target: dict[int, int] | None) -> None:
    source = nib.load(str(source_path))
    data = np.asanyarray(source.dataobj)
    remapped = remap_label_array(data, original_to_target)
    converted = nib.Nifti1Image(remapped, source.affine, source.header)
    converted.set_data_dtype(np.int16)
    nib.save(converted, str(target_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert D024 DentVoxel into nnU-Net raw dataset format.")
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--output-root", default=str(DEFAULT_NNUNET_ROOT))
    parser.add_argument("--task", choices=["jaw-roi", "full-39"], default="jaw-roi")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    summary = convert_d024_to_nnunet(
        dataset_dir=Path(args.dataset_dir),
        output_root=Path(args.output_root),
        task=args.task,
        folds=args.folds,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
