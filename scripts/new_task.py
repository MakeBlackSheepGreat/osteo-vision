from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEMPLATES = {
    "classification": {
        "pipelines": ["classification"],
        "metrics": ["auc", "accuracy", "sensitivity", "specificity", "precision", "f1"],
        "demo_outputs": ["probability", "class_label", "risk_level", "warnings", "report_path"],
        "recommended_models": [{"model_id": "biomedclip_zero_shot", "family": "vlm_encoder"}, {"model_id": "fixture_default", "family": "fixture"}],
    },
    "segmentation": {
        "pipelines": ["segmentation", "quantification"],
        "metrics": ["dice", "iou", "hd95"],
        "demo_outputs": ["segmentation_mask", "lesion_evidence", "quantification", "warnings", "report_path"],
        "recommended_models": [{"model_id": "medsam2_promptable", "family": "medsam_like"}, {"model_id": "nnunet_v2_baseline", "family": "nnunet_v2"}],
    },
    "ct_roi": {
        "pipelines": ["classification", "segmentation", "detection", "quantification", "multitask"],
        "metrics": ["auc", "sensitivity", "specificity", "f1", "dice", "candidate_recall"],
        "demo_outputs": ["risk_level", "lesion_evidence", "quantification", "warnings", "report_path"],
        "recommended_models": [{"model_id": "vista3d_foundation", "family": "vista3d_like"}, {"model_id": "monai_bundle_baseline", "family": "monai_bundle"}],
    },
    "multitask": {
        "pipelines": ["classification", "segmentation", "detection", "quantification", "multitask"],
        "metrics": ["auc", "accuracy", "dice", "iou", "candidate_recall"],
        "demo_outputs": ["prediction", "lesion_evidence", "quantification", "warnings", "report_path"],
        "recommended_models": [{"model_id": "fixture_default", "family": "fixture"}],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--template", choices=sorted(TEMPLATES), default="classification")
    parser.add_argument("--output-dir", default="configs/tasks")
    args = parser.parse_args()
    outputs = create_task(args.task_id, args.template, args.output_dir)
    for path in outputs:
        print(path)
    return 0


def create_task(task_id: str, template: str, output_dir: str | Path) -> list[str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    slug = task_id.strip().replace(" ", "_").lower()
    task_path = root / f"{slug}.yml"
    manifest_path = root / f"{slug}_manifest.example.csv"
    runtime_path = root / f"{slug}_runtime.example.yml"
    readme_path = root / f"{slug}_README_SNIPPET.md"
    for path in [task_path, manifest_path, runtime_path, readme_path]:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    spec = TEMPLATES[template]
    task_payload = {
        "task_id": slug,
        "task_name": slug.replace("_", " ").title(),
        "modality": "generic",
        "input_contract": {
            "input_types": ["2d_image", "npz_roi", "dicom_series", "nifti_volume"],
            "required_manifest_columns": ["case_id", "input_path", "label", "task_type", "input_type"],
            "optional_manifest_columns": ["patient_id", "split", "fold", "label_source", "modality", "metadata_path", "mask_path", "bbox", "model_hint"],
        },
        "label_contract": {"type": "binary_or_missing"},
        "pipelines": spec["pipelines"],
        "metrics": spec["metrics"],
        "demo_outputs": spec["demo_outputs"],
        "benchmark_contract": {"manifest_version": "v2", "patient_level_split_recommended": True},
        "recommended_models": spec["recommended_models"],
        "safety": {"disclaimer_required": True, "clinical_claim_allowed": False, "user_upload_policy": "transient_inference_only"},
    }
    task_path.write_text(yaml.safe_dump(task_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "input_path", "label", "task_type", "input_type", "patient_id", "split", "fold", "label_source", "modality", "metadata_path", "mask_path", "bbox", "model_hint"])
        writer.writerow(["example_case", "tests/fixtures/sample_image.png", "", spec["pipelines"][0], "2d_image", "patient_001", "demo", "0", "example", "generic", "", "", "", "fixture_default"])
    runtime_payload = {
        "paths_config": "configs/paths.example.yml",
        "runtime": {
            "model_version": f"{slug}-fixture-v0",
            "task_package": str(task_path).replace("\\", "/"),
            "default_task_type": spec["pipelines"][0],
            "model_selection_policy": "fixture_fallback",
            "models": [{"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"], "enabled": True}],
        },
    }
    runtime_path.write_text(yaml.safe_dump(runtime_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    readme_path.write_text(
        f"## {task_payload['task_name']}\n\n"
        f"- Task package: `{task_path}`\n"
        f"- Example manifest: `{manifest_path}`\n"
        f"- Runtime config: `{runtime_path}`\n"
        "- Safety: research and competition prototype only.\n",
        encoding="utf-8",
    )
    return [str(task_path), str(manifest_path), str(runtime_path), str(readme_path)]


if __name__ == "__main__":
    raise SystemExit(main())

