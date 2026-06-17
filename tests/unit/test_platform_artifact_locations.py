from __future__ import annotations

from pathlib import Path

from backend.src.core.settings import load_settings


def test_platform_artifact_defaults_are_under_artifacts() -> None:
    settings = load_settings()
    assert "artifacts" in settings.artifact_root.parts
    assert settings.case_store_path.name == "cases.json"
