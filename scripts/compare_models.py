from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.paths import ensure_dir
from src.datasets.manifests import read_manifest
from src.engine.inference import MedicalImagingInferenceService
from src.reports.writers import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/inference/osteo_vision.yml")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/runs/model_comparison")
    parser.add_argument("--models", default="", help="Comma-separated model ids; empty means all configured models.")
    args = parser.parse_args()
    report = compare_models(args.config, args.manifest, args.output, [m for m in args.models.split(",") if m])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def compare_models(config_path: str, manifest_path: str, output_dir: str, model_ids: list[str]) -> dict[str, object]:
    service = MedicalImagingInferenceService.from_config(config_path)
    rows, manifest_info = read_manifest(manifest_path)
    selected = model_ids or [item["spec"]["model_id"] for item in service.model_inventory()]
    output = ensure_dir(output_dir)
    comparison_rows: list[dict[str, object]] = []
    for model_id in selected:
        for row in rows:
            result = service.diagnose(
                row["input_path"],
                task_type=row.get("task_type") or None,
                case_id=row.get("case_id") or None,
                model_id=model_id,
            ).to_dict()
            comparison_rows.append(
                {
                    "model_id": model_id,
                    "case_id": row.get("case_id"),
                    "status": result.get("status"),
                    "probability": result.get("probability"),
                    "class_label": result.get("class_label"),
                    "risk_level": result.get("risk_level"),
                    "selected_model_id": result.get("model_id"),
                    "selected_model_family": result.get("model_family"),
                    "warning_codes": "|".join(str(item.get("code")) for item in result.get("warnings", [])),
                }
            )
    csv_path = output / "model_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "model_id",
            "case_id",
            "status",
            "probability",
            "class_label",
            "risk_level",
            "selected_model_id",
            "selected_model_family",
            "warning_codes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_rows)
    payload = {
        "config": config_path,
        "manifest": manifest_info,
        "models_requested": selected,
        "row_count": len(comparison_rows),
        "comparison_csv": str(csv_path),
        "model_inventory": service.model_inventory(),
    }
    write_json(output / "model_comparison.json", payload)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
