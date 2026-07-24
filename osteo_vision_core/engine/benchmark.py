from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from osteo_vision_core.core.config import config_hash
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.core.schemas import BenchmarkReport
from osteo_vision_core.datasets.manifests import read_manifest
from osteo_vision_core.datasets.splits import patient_leakage_report
from osteo_vision_core.engine.inference import MedicalImagingInferenceService
from osteo_vision_core.metrics.classification import classification_metrics, threshold_sweep
from osteo_vision_core.reports.benchmark import write_benchmark_report
from osteo_vision_core.reports.writers import write_csv, write_json


def evaluate_manifest(config_path: str | Path, manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    rows, info = read_manifest(manifest_path)
    service = MedicalImagingInferenceService.from_config(config_path)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = _run_output_dir(output_dir, run_id)
    _write_snapshots(config_path, manifest_path, service, out)
    prediction_rows: list[dict[str, Any]] = []
    y_true: list[int] = []
    y_score: list[float] = []
    failures: dict[str, int] = {}
    for row in rows:
        result = service.diagnose(
            row["input_path"],
            task_type=row.get("task_type") or None,
            case_id=row.get("case_id") or None,
            model_id=row.get("model_hint") or None,
        )
        payload = result.to_dict()
        status = payload.get("status", "")
        if status != "completed":
            failures[status] = failures.get(status, 0) + 1
        label_text = str(row.get("label", "")).strip()
        probability = payload.get("probability")
        if label_text in {"0", "1"} and probability is not None:
            y_true.append(int(label_text))
            y_score.append(float(probability))
        prediction_rows.append(
            {
                "run_id": run_id,
                "case_id": row.get("case_id"),
                "input_path": row.get("input_path"),
                "label": row.get("label"),
                "task_type": row.get("task_type"),
                "status": status,
                "probability": probability,
                "class_label": payload.get("class_label"),
                "risk_level": payload.get("risk_level"),
                "model_id": payload.get("model_id"),
                "model_family": payload.get("model_family"),
                "report_path": payload.get("report_path"),
            }
        )
    prediction_csv = out / "predictions.csv"
    write_csv(
        prediction_csv,
        prediction_rows,
        [
            "run_id",
            "case_id",
            "input_path",
            "label",
            "task_type",
            "status",
            "probability",
            "class_label",
            "risk_level",
            "model_id",
            "model_family",
            "report_path",
        ],
    )
    metrics = classification_metrics(y_true, y_score, threshold=0.5) if y_true else {}
    threshold = threshold_sweep(y_true, y_score)
    leakage = (
        patient_leakage_report(rows)
        if "patient_id" in info.get("optional_columns_present", [])
        else {"leakage_detected": False, "reason": "patient_id column missing"}
    )
    metrics_path = out / "metrics.json"
    write_json(
        metrics_path, {"metrics": metrics, "threshold_analysis": threshold, "manifest": info, "leakage": leakage}
    )
    report = BenchmarkReport(
        run_id=run_id,
        config_path=str(config_path),
        manifest_path=str(manifest_path),
        output_dir=str(out),
        model_version=service.model_version,
        prediction_csv=str(prediction_csv),
        metrics_path=str(metrics_path),
        metrics=metrics,
        failure_summary=failures | {"leakage": leakage},
        threshold_analysis_path=str(out / "threshold_analysis.md"),
    )
    report_path = write_benchmark_report(report, out, threshold)
    payload = report.to_dict()
    payload["report_path"] = report_path
    payload["config_hash"] = config_hash(config_path)
    payload["run_dir"] = str(out)
    return payload


def _run_output_dir(output_dir: str | Path, run_id: str) -> Path:
    root = ensure_dir(output_dir)
    if root.name.startswith("run_") or root.name == run_id:
        return root
    return ensure_dir(root / run_id)


def _write_snapshots(
    config_path: str | Path, manifest_path: str | Path, service: MedicalImagingInferenceService, output_dir: Path
) -> None:
    config_source = Path(config_path)
    manifest_source = Path(manifest_path)
    if config_source.exists():
        (output_dir / "config_snapshot.yml").write_text(config_source.read_text(encoding="utf-8"), encoding="utf-8")
    if manifest_source.exists():
        (output_dir / "manifest_snapshot.csv").write_text(manifest_source.read_text(encoding="utf-8"), encoding="utf-8")
    if service.task_package.source_path:
        task_source = Path(service.task_package.source_path)
        if task_source.exists():
            (output_dir / "task_package_snapshot.yml").write_text(
                task_source.read_text(encoding="utf-8"), encoding="utf-8"
            )
    write_json(output_dir / "model_specs.json", {"models": service.model_inventory()})
