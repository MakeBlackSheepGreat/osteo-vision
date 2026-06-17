from __future__ import annotations

from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapters, inventory_from_adapters, select_adapter


def test_adapter_inventory_reports_fixture_and_unavailable_models() -> None:
    runtime = {
        "models": [
            {
                "model_id": "missing_biomedclip",
                "family": "vlm_encoder",
                "task_types": ["classification"],
                "input_types": ["2d_image"],
                "checkpoint_path": "artifacts/checkpoints/missing_biomedclip.pt",
                "dependency_group": "vlm",
            },
            {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]},
        ]
    }
    adapters = build_adapters(runtime)
    inventory = inventory_from_adapters(adapters)
    assert any(row["spec"]["family"] == "fixture" and row["status"]["available"] for row in inventory)
    assert any(row["spec"]["family"] == "vlm_encoder" and not row["status"]["available"] for row in inventory)


def test_select_adapter_falls_back_to_fixture() -> None:
    adapters = build_adapters(
        {
            "models": [
                {
                    "model_id": "missing_biomedclip",
                    "family": "vlm_encoder",
                    "task_types": ["classification"],
                    "input_types": ["2d_image"],
                    "checkpoint_path": "artifacts/checkpoints/missing_biomedclip.pt",
                    "dependency_group": "vlm",
                },
                {"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]},
            ]
        }
    )
    adapter, statuses = select_adapter(adapters, task_type="classification", input_type="2d_image", modality="generic")
    assert adapter is not None
    assert adapter.describe().family == "fixture"
    assert len(statuses) >= 2


def test_fixture_adapter_predicts() -> None:
    adapters = build_adapters({"models": [{"model_id": "fixture_default", "family": "fixture", "task_types": ["*"], "input_types": ["*"]}]})
    result = adapters[0].predict(
        AdapterRequest(
            case_id="case",
            input_path="tests/fixtures/sample_image.png",
            input_type="2d_image",
            task_type="classification",
            modality="generic",
        )
    )
    assert result.probability is not None
    assert result.model_family == "fixture"

