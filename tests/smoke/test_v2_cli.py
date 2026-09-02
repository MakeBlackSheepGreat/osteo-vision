from __future__ import annotations

import json
import subprocess
import sys


def test_new_task_generates_scaffold(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/new_task.py",
            "--task-id",
            "demo_task",
            "--template",
            "classification",
            "--output-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "demo_task.yml").exists()
    assert (tmp_path / "demo_task_manifest.example.csv").exists()
    assert (tmp_path / "demo_task_runtime.example.yml").exists()


def test_model_inventory_cli_reports_fixture() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/model_inventory.py", "--config", "configs/inference/demo.yml"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "osteo-vision-runtime-model-inventory-v1"
    assert payload["config_sha256"]
    assert payload["runtime_profile"] == "development"
    assert payload["task_package"]["task_id"] == "medical_demo"
    assert any(row["spec"]["family"] == "fixture" and row["status"]["available"] for row in payload["models"])
    assert any(row["spec"]["family"] != "fixture" and not row["status"]["available"] for row in payload["models"])
    model_ids = [row["spec"]["model_id"] for row in payload["models"]]
    assert model_ids == sorted(model_ids)


def test_compare_models_cli_uses_fixture(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/compare_models.py",
            "--config",
            "configs/inference/demo.yml",
            "--manifest",
            "tests/fixtures/benchmark_manifest_v2.csv",
            "--output",
            str(tmp_path),
            "--models",
            "fixture_default",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "model_comparison.json").exists()
    assert (tmp_path / "model_comparison.csv").exists()
