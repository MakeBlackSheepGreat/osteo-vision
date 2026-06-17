from __future__ import annotations

from src.core.schemas import ModelSpec
from src.core.task_package import load_task_package


def test_task_package_loads() -> None:
    package = load_task_package("configs/tasks/medical_competition_demo.yml")
    assert package.task_id == "medical_competition_demo"
    assert "classification" in package.pipelines
    assert package.safety["clinical_claim_allowed"] is False


def test_model_spec_defaults() -> None:
    spec = ModelSpec(model_id="fixture_default", family="fixture")
    payload = spec.to_dict()
    assert payload["enabled"] is True
    assert payload["clinical_claim_allowed"] is False

