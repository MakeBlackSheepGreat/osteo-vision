from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app


def test_ready_exposes_runtime_profile_and_config_hash(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "development.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "development_test",
                    "strict_startup": False,
                    "use_fixture_model": False,
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_INFERENCE_CONFIG", str(config))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["runtime_readiness"]["runtime_profile"] == "development_test"
    assert payload["runtime_readiness"]["config_sha256"]
    assert payload["accelerator"]["selected_device"] in {"cpu", "cuda"}
    assert isinstance(payload["accelerator"]["fallback_active"], bool)
    assert payload["task2_fusion_warmup"]["requested"] is False
    assert payload["inference_config"] == str(config.resolve())
    assert payload["promotion_approval_store"] == str(
        tmp_path / "artifacts" / "promotion_approvals" / "approvals.sqlite"
    )
    assert Path(payload["promotion_trusted_keys"]).name == "promotion_trusted_keys.json"


def test_strict_runtime_failure_prevents_backend_construction(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "strict.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "competition_strict",
                    "strict_startup": True,
                    "use_fixture_model": True,
                    "allow_fixture_on_missing_checkpoint": False,
                    "model_selection_policy": "explicit",
                    "required_model_ids": ["missing_model"],
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_INFERENCE_CONFIG", str(config))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    with pytest.raises(RuntimeError, match="Strict runtime readiness failed"):
        create_app()
