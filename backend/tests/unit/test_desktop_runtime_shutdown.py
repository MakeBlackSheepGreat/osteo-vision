from __future__ import annotations

from pathlib import Path

from backend.osteo_vision_api.core import settings


def test_packaged_project_root_uses_explicit_runtime_assets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OSTEO_PROJECT_ROOT", str(tmp_path))

    assert settings._repo_root() == tmp_path.resolve()


def test_default_project_root_ignores_blank_packaged_root(monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_PROJECT_ROOT", "   ")

    assert settings._repo_root().name == "osteo-vision"
