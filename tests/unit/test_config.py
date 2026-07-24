from __future__ import annotations

from osteo_vision_core.core.config import load_yaml, runtime_config


def test_demo_config_loads() -> None:
    config = load_yaml("configs/inference/demo.yml")
    runtime = runtime_config(config)
    assert runtime["model_version"] == "micf-fixture-v0"
    assert runtime["default_task_type"] == "classification"
    assert "classification" in runtime["tasks"]
