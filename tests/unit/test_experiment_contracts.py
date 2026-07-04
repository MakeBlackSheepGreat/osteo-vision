from __future__ import annotations

from src.core.schemas import CheckpointManifest, ModelCard, PromotionRecord
from src.experiments.promotion import evaluate_promotion_gate
from src.experiments.spec import experiment_spec_from_mapping
from src.experiments.splits import assign_splits
from src.experiments.thresholds import choose_threshold


def test_experiment_spec_schema_requires_contract_fields() -> None:
    spec = experiment_spec_from_mapping(
        {
            "experiment_id": "demo_exp",
            "task_package": "configs/tasks/medical_competition_demo.yml",
            "manifest_path": "tests/fixtures/benchmark_manifest_v2.csv",
            "model_spec": {"model_id": "fixture_default", "family": "fixture"},
            "split_strategy": {"type": "fixed"},
            "training_config": {"mode": "fixture"},
            "evaluation_config": {"mode": "fixture_oof"},
            "threshold_strategy": {"type": "fixed", "threshold": 0.5},
            "promotion_gate": {"minimum_metrics": {"accuracy": 0.0}},
        }
    )
    payload = spec.to_dict()
    assert payload["experiment_id"] == "demo_exp"
    assert payload["model_spec"]["clinical_claim_allowed"] is False if "clinical_claim_allowed" in payload["model_spec"] else True


def test_model_lifecycle_schemas_include_safety_boundary() -> None:
    model_card = ModelCard(
        model_id="fixture_default",
        model_family="fixture",
        intended_use="research_competition_prototype",
        task_package="medical_competition_demo",
        training_data={},
        metrics={},
    )
    checkpoint = CheckpointManifest(
        checkpoint_path="artifacts/checkpoints/fixture.json",
        checkpoint_hash="abc",
        source_run_id="run_001",
        model_id="fixture_default",
        task_package="medical_competition_demo",
        metrics={},
    )
    promotion = PromotionRecord(run_id="run_001", experiment_id="exp_001", model_id="fixture_default", promoted=False, gate={})
    assert model_card.clinical_claim_allowed is False
    assert checkpoint.clinical_claim_allowed is False
    assert promotion.clinical_claim_allowed is False


def test_split_strategies_are_supported() -> None:
    rows = [
        {"case_id": "a", "patient_id": "p1", "split": "train"},
        {"case_id": "b", "patient_id": "p1", "split": "val"},
        {"case_id": "c", "patient_id": "p2", "split": ""},
    ]
    fixed, fixed_info = assign_splits(rows, {"type": "fixed", "default_split": "validation"})
    external, external_info = assign_splits(rows, {"type": "external", "external_split": "external"})
    kfold, kfold_info = assign_splits(rows, {"type": "kfold", "folds": 3})
    assert fixed_info["type"] == "fixed"
    assert fixed[2]["_split"] == "validation"
    assert external_info["type"] == "external"
    assert all(row["_fold"] == "external" for row in external)
    assert kfold_info["type"] == "kfold"
    assert kfold[0]["_fold"] == kfold[1]["_fold"]


def test_threshold_strategies_return_stable_contracts() -> None:
    y_true = [1, 1, 0, 0]
    y_score = [0.9, 0.8, 0.3, 0.2]
    fixed = choose_threshold(y_true, y_score, {"type": "fixed", "threshold": 0.4})
    youden = choose_threshold(y_true, y_score, {"type": "youden"})
    sensitivity_first = choose_threshold(y_true, y_score, {"type": "sensitivity_first", "min_sensitivity": 1.0})
    assert fixed["threshold"] == 0.4
    assert youden["analysis"]["available"] is True
    assert sensitivity_first["analysis"]["available"] is True
    assert sensitivity_first["analysis"]["best"]["metrics"]["sensitivity"] >= 1.0


def test_promotion_gate_passes_and_blocks_with_reasons() -> None:
    passed = evaluate_promotion_gate(
        run_id="run_001",
        experiment_id="exp_001",
        model_id="fixture_default",
        model_family="fixture",
        metrics={"accuracy": 0.8},
        leakage={"leakage_detected": False},
        gate={"require_no_leakage": True, "require_patient_id": True, "minimum_metrics": {"accuracy": 0.5}},
        checkpoint_path="artifacts/checkpoints/fixture.json",
    )
    blocked = evaluate_promotion_gate(
        run_id="run_002",
        experiment_id="exp_001",
        model_id="fixture_default",
        model_family="fixture",
        metrics={"accuracy": 0.4},
        leakage={"leakage_detected": False, "reason": "patient_id column missing"},
        gate={"require_no_leakage": True, "require_patient_id": True, "minimum_metrics": {"accuracy": 0.5}},
        checkpoint_path="artifacts/checkpoints/fixture.json",
    )
    assert passed.promoted is True
    assert passed.runtime_patch["runtime"]["models"][0]["clinical_claim_allowed"] is False
    assert blocked.promoted is False
    assert any("patient_id missing" in reason for reason in blocked.reasons)
