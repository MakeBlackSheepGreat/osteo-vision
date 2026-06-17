from __future__ import annotations

import json
from pathlib import Path

from src.core.schemas import ExperimentSpec
from src.engine.experiment import run_experiment
from src.experiments.spec import write_experiment_spec


def test_v2_task_package_drives_v3_experiment_flow(tmp_path) -> None:
    spec = ExperimentSpec(
        experiment_id="integration_v3",
        task_package="configs/tasks/medical_competition_demo.yml",
        manifest_path="tests/fixtures/benchmark_manifest_v2.csv",
        model_spec={
            "model_id": "fixture_default",
            "family": "fixture",
            "task_types": ["*"],
            "input_types": ["*"],
            "enabled": True,
            "clinical_claim_allowed": False,
        },
        split_strategy={"type": "fixed", "split_column": "split", "default_split": "validation"},
        training_config={"mode": "fixture"},
        evaluation_config={"mode": "fixture_oof"},
        threshold_strategy={"type": "fixed", "threshold": 0.5},
        promotion_gate={"require_no_leakage": True, "require_patient_id": True, "minimum_metrics": {"accuracy": 0.0}},
        output_dir=str(tmp_path / "runs"),
    )
    spec_path = tmp_path / "experiment.yml"
    write_experiment_spec(spec, spec_path)

    result = run_experiment(spec_path)
    run_dir = Path(result["run_dir"])
    expected = [
        "experiment_snapshot.yml",
        "task_package_snapshot.yml",
        "manifest_snapshot.csv",
        "model_spec_snapshot.json",
        "training_report.json",
        "evaluation_report.json",
        "oof_predictions.csv",
        "model_card.json",
        "checkpoint_manifest.json",
        "promotion_record.json",
    ]
    for name in expected:
        assert (run_dir / name).exists(), name

    model_card = json.loads((run_dir / "model_card.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((run_dir / "checkpoint_manifest.json").read_text(encoding="utf-8"))
    promotion = json.loads((run_dir / "promotion_record.json").read_text(encoding="utf-8"))
    assert model_card["clinical_claim_allowed"] is False
    assert checkpoint["clinical_claim_allowed"] is False
    assert promotion["clinical_claim_allowed"] is False
    assert promotion["promoted"] is True
    assert "Research prototype" in model_card["disclaimer"]
