from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from osteo_vision_core.core.schemas import PromotionRecord
from osteo_vision_core.core.warnings import DISCLAIMER_TEXT, warning


def evaluate_promotion_gate(
    *,
    run_id: str,
    experiment_id: str,
    model_id: str,
    model_family: str = "fixture",
    metrics: dict[str, Any],
    leakage: dict[str, Any],
    gate: dict[str, Any],
    checkpoint_path: str,
) -> PromotionRecord:
    reasons: list[str] = []
    warnings: list[dict[str, Any]] = []
    minimum_metrics = dict(gate.get("minimum_metrics") or {})
    for metric, expected in minimum_metrics.items():
        actual = metrics.get(metric)
        if actual is None or float(actual) < float(expected):
            reasons.append(f"{metric} below gate: actual={actual}, required={expected}")
    if bool(gate.get("require_no_leakage", True)) and leakage.get("leakage_detected"):
        reasons.append("patient-level leakage detected")
    if bool(gate.get("require_patient_id", True)) and leakage.get("reason") == "patient_id column missing":
        reasons.append("patient_id missing; formal promotion is not allowed")
        warnings.append(warning("patient_id_missing", "patient_id is required for formal runtime promotion"))
    promoted = not reasons
    runtime_patch = {}
    if promoted:
        runtime_patch = {
            "runtime": {
                "model_version": f"{model_id}-{run_id}",
                "checkpoint_path": checkpoint_path,
                "models": [
                    {
                        "model_id": model_id,
                        "family": model_family,
                        "task_types": ["*"],
                        "input_types": ["*"],
                        "checkpoint_path": checkpoint_path,
                        "enabled": True,
                        "intended_use": "research_platform_validation",
                        "clinical_claim_allowed": False,
                    }
                ],
            }
        }
    return PromotionRecord(
        run_id=run_id,
        experiment_id=experiment_id,
        model_id=model_id,
        promoted=promoted,
        gate=gate,
        reasons=reasons,
        runtime_patch=runtime_patch,
        warnings=warnings,
    )


def load_promotion_record(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "promotion_record.json"
    if not path.exists():
        raise FileNotFoundError(f"Promotion record not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_promotion_draft(run_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    record = load_promotion_record(run_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    draft = {
        "source_run_dir": str(run_dir),
        "promoted": bool(record.get("promoted")),
        "runtime_patch": record.get("runtime_patch", {}),
        "reasons": record.get("reasons", []),
        "disclaimer": DISCLAIMER_TEXT,
    }
    output.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft | {"output_path": str(output)}
