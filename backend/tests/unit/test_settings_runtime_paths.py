from __future__ import annotations

from pathlib import Path

from backend.osteo_vision_api.core.settings import _default_video_manifest_path, load_settings


def test_default_video_manifest_selects_latest_versioned_inventory(tmp_path: Path) -> None:
    inventory = tmp_path / "research" / "literature" / "inventory"
    inventory.mkdir(parents=True)
    older = inventory / "video_library_manifest_20260704.csv"
    latest = inventory / "video_library_manifest_20260719.csv"
    older.write_text("older\n", encoding="utf-8")
    latest.write_text("latest\n", encoding="utf-8")

    assert _default_video_manifest_path(tmp_path) == latest


def test_default_video_manifest_falls_back_to_download_inventory(tmp_path: Path) -> None:
    inventory = tmp_path / "research" / "literature" / "inventory"
    inventory.mkdir(parents=True)
    fallback = inventory / "video_download_manifest_20260719.csv"
    fallback.write_text("fallback\n", encoding="utf-8")

    assert _default_video_manifest_path(tmp_path) == fallback


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


def test_default_allowed_origins_include_the_independent_renderer(monkeypatch) -> None:
    monkeypatch.delenv("OSTEO_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("OSTEO_FRONTEND_PORT", "5274")
    monkeypatch.setenv("OSTEO_THREE_D_RUNTIME_PORT", "5275")

    settings = load_settings()

    assert settings.allowed_origins == (
        "http://localhost:5274",
        "http://127.0.0.1:5274",
        "http://localhost:5275",
        "http://127.0.0.1:5275",
    )
