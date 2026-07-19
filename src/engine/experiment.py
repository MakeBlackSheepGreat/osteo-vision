from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.paths import ensure_dir, resolve_path
from src.core.schemas import CheckpointManifest, EvaluationRun, ModelCard, TrainingRun
from src.core.task_package import load_task_package
from src.core.warnings import DISCLAIMER_TEXT, warning
from src.datasets.manifests import read_manifest
from src.datasets.splits import patient_leakage_report
from src.experiments.promotion import evaluate_promotion_gate
from src.experiments.spec import load_experiment_spec
from src.experiments.splits import assign_splits
from src.experiments.thresholds import choose_threshold
from src.metrics.classification import classification_metrics
from src.models.adapters import model_spec_from_mapping
from src.models.classifier import DeterministicClassifier
from src.reports.writers import write_csv, write_json


def run_experiment(spec_path: str | Path) -> dict[str, Any]:
    spec = load_experiment_spec(spec_path)
    task_package = load_task_package(spec.task_package)
    manifest_path = resolve_path(spec.manifest_path)
    rows, manifest_info = read_manifest(manifest_path)
    model_spec = model_spec_from_mapping(spec.model_spec)
    assigned_rows, split_info = assign_splits(rows, spec.split_strategy)

    run_id = _new_run_id(spec.experiment_id)
    run_dir = _make_run_dir(spec.output_dir, run_id)
    _write_snapshots(spec, task_package.source_path, manifest_path, run_dir)

    classifier = DeterministicClassifier(threshold=float(spec.threshold_strategy.get("threshold", 0.5)))
    scored_rows = _score_fixture_rows(assigned_rows, classifier, model_spec.model_id, model_spec.family)
    y_true, y_score = _labeled_vectors(scored_rows)
    threshold_result = choose_threshold(y_true, y_score, spec.threshold_strategy)
    selected_threshold = float(threshold_result.get("threshold", 0.5))
    prediction_rows = _finalize_oof_rows(scored_rows, selected_threshold, run_id, spec.experiment_id)
    metrics = classification_metrics(y_true, y_score, selected_threshold) if y_true else {}
    fold_reports = _fold_reports(prediction_rows, selected_threshold)
    fold_summary = _fold_summary(fold_reports)
    leakage = _leakage_report(prediction_rows, split_info)
    warnings = _experiment_warnings(leakage, y_true, manifest_info)

    checkpoint_path = _write_fixture_checkpoint(run_dir, run_id, spec.experiment_id, model_spec.to_dict())
    checkpoint_hash = _file_sha256(checkpoint_path)

    oof_path = run_dir / "oof_predictions.csv"
    write_csv(
        oof_path,
        prediction_rows,
        [
            "run_id",
            "experiment_id",
            "case_id",
            "input_path",
            "label",
            "task_type",
            "input_type",
            "patient_id",
            "split",
            "fold",
            "probability",
            "score",
            "predicted_label",
            "class_label",
            "model_id",
            "model_family",
        ],
    )

    training_run = TrainingRun(
        run_id=run_id,
        experiment_id=spec.experiment_id,
        task_package=spec.task_package,
        manifest_path=str(manifest_path),
        model_spec=model_spec.to_dict(),
        split_strategy=split_info,
        training_config=spec.training_config,
        output_checkpoint=str(checkpoint_path),
        fold_reports=fold_reports,
        metrics={"overall": metrics, "fold_summary": fold_summary, "selected_threshold": selected_threshold},
        warnings=warnings,
    )
    training_report_path = write_json(run_dir / "training_report.json", training_run.to_dict())

    evaluation_run = EvaluationRun(
        run_id=run_id,
        experiment_id=spec.experiment_id,
        evaluation_config=spec.evaluation_config,
        threshold_strategy=spec.threshold_strategy,
        metrics=metrics,
        threshold_analysis=threshold_result,
        failure_summary=_failure_summary(prediction_rows, manifest_info, leakage),
        evidence_paths=[str(oof_path)],
        warnings=warnings,
    )
    evaluation_report_path = write_json(run_dir / "evaluation_report.json", evaluation_run.to_dict())

    promotion_record = evaluate_promotion_gate(
        run_id=run_id,
        experiment_id=spec.experiment_id,
        model_id=model_spec.model_id,
        model_family=model_spec.family,
        metrics=metrics,
        leakage=leakage,
        gate=spec.promotion_gate,
        checkpoint_path=str(checkpoint_path),
    )
    promotion_record_path = write_json(run_dir / "promotion_record.json", promotion_record.to_dict())

    model_card = ModelCard(
        model_id=model_spec.model_id,
        model_family=model_spec.family,
        intended_use=model_spec.intended_use,
        task_package=task_package.task_id,
        training_data={
            "manifest": manifest_info,
            "split_strategy": split_info,
            "row_count": len(rows),
            "fixture_training": True,
            "leakage": leakage,
        },
        metrics=metrics,
        limitations=[
            "Fixture flow only; no real model weights were trained.",
            "Metrics are generated from deterministic fallback scores.",
            "A clinician review boundary is required before any real-world use.",
        ],
        clinical_claim_allowed=False,
    )
    model_card_path = write_json(run_dir / "model_card.json", model_card.to_dict())

    checkpoint_manifest = CheckpointManifest(
        checkpoint_path=str(checkpoint_path),
        checkpoint_hash=checkpoint_hash,
        source_run_id=run_id,
        model_id=model_spec.model_id,
        task_package=task_package.task_id,
        metrics=metrics,
        runtime_allowed=promotion_record.promoted,
        clinical_claim_allowed=False,
        warnings=warnings,
    )
    checkpoint_manifest_path = write_json(run_dir / "checkpoint_manifest.json", checkpoint_manifest.to_dict())

    return {
        "run_id": run_id,
        "experiment_id": spec.experiment_id,
        "run_dir": str(run_dir),
        "training_report": training_report_path,
        "evaluation_report": evaluation_report_path,
        "oof_predictions": str(oof_path),
        "model_card": model_card_path,
        "checkpoint_manifest": checkpoint_manifest_path,
        "promotion_record": promotion_record_path,
        "metrics": metrics,
        "threshold_analysis": threshold_result,
        "promotion": promotion_record.to_dict(),
        "disclaimer": DISCLAIMER_TEXT,
    }


def _new_run_id(experiment_id: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in experiment_id).strip("_") or "experiment"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{slug}_{stamp}"


def _make_run_dir(output_dir: str | Path, run_id: str) -> Path:
    root = ensure_dir(resolve_path(output_dir))
    candidate = root / run_id
    counter = 1
    while candidate.exists():
        candidate = root / f"{run_id}_{counter}"
        counter += 1
    return ensure_dir(candidate)


def _write_snapshots(spec: Any, task_package_path: str | None, manifest_path: Path, run_dir: Path) -> None:
    if spec.source_path:
        source = Path(spec.source_path)
        if source.exists():
            (run_dir / "experiment_snapshot.yml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    if task_package_path:
        task_source = Path(task_package_path)
        if task_source.exists():
            (run_dir / "task_package_snapshot.yml").write_text(
                task_source.read_text(encoding="utf-8"), encoding="utf-8"
            )
    if manifest_path.exists():
        (run_dir / "manifest_snapshot.csv").write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    write_json(run_dir / "model_spec_snapshot.json", {"model_spec": spec.model_spec})


def _score_fixture_rows(
    rows: list[dict[str, Any]], classifier: DeterministicClassifier, model_id: str, model_family: str
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        metadata = {
            "case_id": row.get("case_id"),
            "task_type": row.get("task_type"),
            "input_type": row.get("input_type"),
            "modality": row.get("modality"),
            "fold": row.get("_fold"),
        }
        probability = classifier.predict_probability(str(row.get("input_path", "")), metadata)
        item = dict(row)
        item["_probability"] = probability
        item["_model_id"] = model_id
        item["_model_family"] = model_family
        scored.append(item)
    return scored


def _labeled_vectors(rows: list[dict[str, Any]]) -> tuple[list[int], list[float]]:
    y_true: list[int] = []
    y_score: list[float] = []
    for row in rows:
        label = str(row.get("label", "")).strip()
        if label not in {"0", "1"}:
            continue
        y_true.append(int(label))
        y_score.append(float(row["_probability"]))
    return y_true, y_score


def _finalize_oof_rows(
    rows: list[dict[str, Any]], threshold: float, run_id: str, experiment_id: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        probability = float(row["_probability"])
        predicted_label = 1 if probability >= threshold else 0
        output.append(
            {
                "run_id": run_id,
                "experiment_id": experiment_id,
                "case_id": row.get("case_id"),
                "input_path": row.get("input_path"),
                "label": row.get("label"),
                "task_type": row.get("task_type"),
                "input_type": row.get("input_type"),
                "patient_id": row.get("patient_id"),
                "split": row.get("_split"),
                "fold": row.get("_fold"),
                "probability": probability,
                "score": probability,
                "predicted_label": predicted_label,
                "class_label": "positive" if predicted_label else "negative",
                "model_id": row.get("_model_id"),
                "model_family": row.get("_model_family"),
            }
        )
    return output


def _fold_reports(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("fold") or "0")].append(row)
    reports: list[dict[str, Any]] = []
    for fold, fold_rows in sorted(grouped.items()):
        y_true: list[int] = []
        y_score: list[float] = []
        for row in fold_rows:
            label = str(row.get("label", "")).strip()
            if label in {"0", "1"}:
                y_true.append(int(label))
                y_score.append(float(row.get("probability", 0.0)))
        reports.append(
            {
                "fold": fold,
                "row_count": len(fold_rows),
                "labeled_count": len(y_true),
                "metrics": classification_metrics(y_true, y_score, threshold) if y_true else {},
            }
        )
    return reports


def _fold_summary(fold_reports: list[dict[str, Any]]) -> dict[str, Any]:
    numeric: dict[str, list[float]] = defaultdict(list)
    for report in fold_reports:
        for key, value in dict(report.get("metrics") or {}).items():
            if isinstance(value, (int, float)):
                numeric[key].append(float(value))
    summary: dict[str, Any] = {}
    for key, values in sorted(numeric.items()):
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        summary[key] = {"mean": mean, "std": variance**0.5, "folds": len(values)}
    return summary


def _leakage_report(rows: list[dict[str, Any]], split_info: dict[str, Any]) -> dict[str, Any]:
    patient_values = [str(row.get("patient_id") or "").strip() for row in rows]
    if not any(patient_values):
        return {"leakage_detected": False, "reason": "patient_id column missing"}
    split_key = "fold" if split_info.get("type") == "kfold" else "split"
    report = patient_leakage_report(rows, patient_key="patient_id", split_key=split_key)
    report["checked_split_key"] = split_key
    return report


def _experiment_warnings(
    leakage: dict[str, Any], y_true: list[int], manifest_info: dict[str, Any]
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if leakage.get("reason") == "patient_id column missing":
        warnings.append(warning("patient_id_missing", "patient_id is required for formal training promotion"))
    if leakage.get("leakage_detected"):
        warnings.append(warning("patient_leakage_detected", "Patient-level leakage was detected", True))
    if not y_true:
        warnings.append(warning("labels_missing", "No binary labels were available for metric calculation"))
    if manifest_info.get("manifest_version") == "v1":
        warnings.append(warning("manifest_v1", "V1 manifest is supported, but V2 metadata is recommended"))
    return warnings


def _failure_summary(
    rows: list[dict[str, Any]], manifest_info: dict[str, Any], leakage: dict[str, Any]
) -> dict[str, Any]:
    labeled = sum(1 for row in rows if str(row.get("label", "")).strip() in {"0", "1"})
    task_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        task_counts[str(row.get("task_type") or "")] += 1
    return {
        "row_count": len(rows),
        "labeled_count": labeled,
        "unlabeled_count": len(rows) - labeled,
        "task_counts": dict(task_counts),
        "manifest": manifest_info,
        "leakage": leakage,
    }


def _write_fixture_checkpoint(run_dir: Path, run_id: str, experiment_id: str, model_spec: dict[str, Any]) -> Path:
    checkpoint_path = run_dir / "fixture_checkpoint.json"
    write_json(
        checkpoint_path,
        {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "model_spec": model_spec,
            "checkpoint_kind": "fixture_contract",
            "trained_real_weights": False,
            "clinical_claim_allowed": False,
            "disclaimer": DISCLAIMER_TEXT,
        },
    )
    return checkpoint_path


def _file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
