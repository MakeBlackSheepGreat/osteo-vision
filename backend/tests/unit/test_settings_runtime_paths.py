from __future__ import annotations

from pathlib import Path

from backend.src.core.settings import load_settings


def test_inference_config_relative_path_is_resolved_from_project_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "runtime-artifacts"))
    monkeypatch.setenv(
        "OSTEO_INFERENCE_CONFIG",
        "configs/inference/osteo_vision_competition_strict.yml",
    )
    monkeypatch.setenv(
        "OSTEO_PROMOTION_TRUSTED_KEYS_PATH",
        "configs/security/promotion_trusted_keys.json",
    )

    settings = load_settings()

    expected = (settings.project_root / "configs" / "inference" / "osteo_vision_competition_strict.yml").resolve()
    assert settings.inference_config_path == expected
    assert settings.inference_config_path.is_file()
    assert settings.artifact_root == tmp_path / "runtime-artifacts"
    assert (
        settings.promotion_trusted_keys_path
        == (settings.project_root / "configs" / "security" / "promotion_trusted_keys.json").resolve()
    )
    assert settings.promotion_approval_store_path == (
        tmp_path / "runtime-artifacts" / "promotion_approvals" / "approvals.sqlite"
    )
