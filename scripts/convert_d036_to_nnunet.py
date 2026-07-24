from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osteo_vision_core.datasets.d036 import (
    D036_MANIFEST_PATH,
    available_d036_cases,
    build_nnunet_dataset_json,
    remap_d036_label,
)

DEFAULT_OUTPUT_ROOT = Path("research/datasets/public-candidates/d036_toothfairy2/derived/nnunet")
DEFAULT_DATASET_ID = 136
DEFAULT_DATASET_NAME = "D036Jawbones"
SUPPORTED_LABEL_MODES = ("jawbone_binary", "jaw2", "mandible_binary", "anatomy4", "coarse3")


def main() -> None:
    args = parse_args()
    summary = convert_d036_to_nnunet(
        project_root=args.project_root,
        manifest_path=args.manifest,
        output_root=args.output_root,
        dataset_id=args.dataset_id,
        dataset_name=args.dataset_name,
        label_mode=args.label_mode,
        max_cases=args.max_cases,
        case_ids=set(args.case_id or []),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert locally available D036 ToothFairy2 CBCT labels into an nnU-Net v2 training dataset."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root.")
    parser.add_argument("--manifest", type=Path, default=D036_MANIFEST_PATH, help="D036 manifest CSV.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="nnU-Net workspace root.")
    parser.add_argument("--dataset-id", type=int, default=DEFAULT_DATASET_ID, help="nnU-Net dataset numeric ID.")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME, help="nnU-Net dataset name suffix.")
    parser.add_argument("--label-mode", default="jaw2", choices=SUPPORTED_LABEL_MODES)
    parser.add_argument("--max-cases", type=int, default=None, help="Limit converted cases. Omit for all local pairs.")
    parser.add_argument("--case-id", action="append", help="Convert only this case id; can be repeated.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing converted files.")
    parser.add_argument("--dry-run", action="store_true", help="Only audit available cases and write no volumes.")
    return parser.parse_args()


def convert_d036_to_nnunet(
    *,
    project_root: Path,
    manifest_path: Path,
    output_root: Path,
    dataset_id: int,
    dataset_name: str,
    label_mode: str,
    max_cases: int | None = None,
    case_ids: set[str] | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if label_mode not in SUPPORTED_LABEL_MODES:
        raise ValueError(f"Unsupported label mode: {label_mode}")

    root = project_root.resolve()
    cases = available_d036_cases(project_root=root, manifest_path=manifest_path, case_ids=case_ids or None)
    selected_cases = cases[:max_cases] if max_cases is not None else cases
    dataset_folder_name = f"Dataset{dataset_id:03d}_{dataset_name}"
    nnunet_root = _resolve_output(root, output_root)
    raw_dataset_dir = nnunet_root / "nnUNet_raw" / dataset_folder_name
    images_dir = raw_dataset_dir / "imagesTr"
    labels_dir = raw_dataset_dir / "labelsTr"
    manifest_dir = nnunet_root / "manifests"
    conversion_manifest = manifest_dir / f"{dataset_folder_name}_{label_mode}_conversion_manifest.csv"
    summary_path = manifest_dir / f"{dataset_folder_name}_{label_mode}_conversion_summary.json"

    rows: list[dict[str, Any]] = []
    converted = 0
    skipped_existing = 0
    if not dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        manifest_dir.mkdir(parents=True, exist_ok=True)

    for case in selected_cases:
        image_output = images_dir / f"{case.case_id}_0000.nii.gz"
        label_output = labels_dir / f"{case.case_id}.nii.gz"
        should_write = overwrite or not (image_output.exists() and label_output.exists())
        if dry_run:
            status = "available"
        elif should_write:
            _convert_case(case.image_path, case.label_path, image_output, label_output, label_mode=label_mode)
            converted += 1
            status = "converted"
        else:
            skipped_existing += 1
            status = "skipped_existing"
        rows.append(
            {
                "case_id": case.case_id,
                "source_image_path": str(case.image_path),
                "source_label_path": str(case.label_path),
                "image_output_path": str(image_output),
                "label_output_path": str(label_output),
                "label_mode": label_mode,
                "status": status,
                "label_source": case.label_source,
            }
        )

    dataset_json = build_nnunet_dataset_json(
        dataset_name=dataset_folder_name,
        label_mode=label_mode,
        num_training=len(selected_cases),
    )
    if not dry_run:
        (raw_dataset_dir / "dataset.json").write_text(
            json.dumps(dataset_json, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_csv(conversion_manifest, rows)

    summary = {
        "schema_version": "osteo-vision-d036-nnunet-conversion-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "dataset_id": dataset_id,
        "dataset_name": dataset_folder_name,
        "label_mode": label_mode,
        "available_local_pairs": len(cases),
        "selected_cases": len(selected_cases),
        "converted_cases": converted,
        "skipped_existing": skipped_existing,
        "raw_dataset_dir": str(raw_dataset_dir),
        "dataset_json_path": str(raw_dataset_dir / "dataset.json"),
        "conversion_manifest_path": str(conversion_manifest),
        "nnunet_env": nnunet_env(nnunet_root),
        "commands": nnunet_commands(dataset_id=dataset_id, nnunet_root=nnunet_root),
        "data_boundary": (
            "D036 ToothFairy2 is public CBCT anatomical segmentation data. It can train upper/lower jawbone anatomy priors, "
            "but it is not jaw osteomyelitis target-domain ICG video data and is not navigation-ready."
        ),
    }
    if not dry_run:
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def nnunet_env(nnunet_root: Path) -> dict[str, str]:
    return {
        "nnUNet_raw": str(nnunet_root / "nnUNet_raw"),
        "nnUNet_preprocessed": str(nnunet_root / "nnUNet_preprocessed"),
        "nnUNet_results": str(nnunet_root / "nnUNet_results"),
    }


def nnunet_commands(*, dataset_id: int, nnunet_root: Path) -> dict[str, str]:
    python = str(Path(sys.executable).resolve())
    env_prefix = (
        f"$env:nnUNet_raw='{nnunet_root / 'nnUNet_raw'}'; "
        f"$env:nnUNet_preprocessed='{nnunet_root / 'nnUNet_preprocessed'}'; "
        f"$env:nnUNet_results='{nnunet_root / 'nnUNet_results'}'; "
    )
    return {
        "plan_and_preprocess": (
            f"{env_prefix}& '{python}' -m nnunetv2.experiment_planning.plan_and_preprocess_entrypoints "
            f"-d {dataset_id} -c 3d_fullres --verify_dataset_integrity -np 4"
        ),
        "train_fold0": (
            f"{env_prefix}& '{python}' -m nnunetv2.run.run_training {dataset_id} 3d_fullres 0 "
            "-tr nnUNetTrainerNoMirroring -device cuda"
        ),
        "predict_fold0": (
            f"{env_prefix}& '{python}' -m nnunetv2.inference.predict_from_raw_data "
            f"-i <images_folder> -o <prediction_folder> -d {dataset_id} -c 3d_fullres "
            "-f 0 -tr nnUNetTrainerNoMirroring -device cuda --disable_tta"
        ),
    }


def _convert_case(
    image_path: Path,
    label_path: Path,
    image_output: Path,
    label_output: Path,
    *,
    label_mode: str,
) -> None:
    try:
        import SimpleITK as sitk
    except ImportError as exc:  # pragma: no cover - project environment includes SimpleITK
        raise RuntimeError("SimpleITK is required for D036 nnU-Net conversion") from exc

    image = sitk.ReadImage(str(image_path))
    label = sitk.ReadImage(str(label_path))
    label_array = sitk.GetArrayFromImage(label)
    remapped = remap_d036_label(label_array, label_mode=label_mode)
    label_out = sitk.GetImageFromArray(remapped)
    label_out.CopyInformation(label)
    image_output.parent.mkdir(parents=True, exist_ok=True)
    label_output.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(sitk.Cast(image, sitk.sitkFloat32), str(image_output))
    sitk.WriteImage(sitk.Cast(label_out, sitk.sitkUInt8), str(label_output))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id",
        "source_image_path",
        "source_label_path",
        "image_output_path",
        "label_output_path",
        "label_mode",
        "status",
        "label_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_output(project_root: Path, output_root: Path) -> Path:
    return output_root if output_root.is_absolute() else project_root / output_root


if __name__ == "__main__":
    main()
