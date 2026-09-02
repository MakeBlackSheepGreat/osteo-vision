from pathlib import Path

from osteo_vision_core.core.paths import project_root, resolve_path


def test_project_root_honors_packaged_runtime_root(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_assets"
    runtime_root.mkdir()
    monkeypatch.setenv("OSTEO_PROJECT_ROOT", str(runtime_root))

    assert project_root() == runtime_root.resolve()
    assert resolve_path("artifacts/checkpoints/model.pt") == (
        runtime_root / "artifacts" / "checkpoints" / "model.pt"
    ).resolve()


def test_project_root_falls_back_to_source_root(monkeypatch) -> None:
    monkeypatch.delenv("OSTEO_PROJECT_ROOT", raising=False)

    root = project_root()
    assert root.name == "osteo-vision"
    assert resolve_path("configs") == root / "configs"


def test_packaged_visual_and_report_outputs_use_writable_artifact_root(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime_assets"
    artifact_root = tmp_path / "user-data" / "artifacts"
    runtime_root.mkdir()
    monkeypatch.setenv("OSTEO_PROJECT_ROOT", str(runtime_root))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))

    assert resolve_path("artifacts/visual_evidence/osteo_vision/mask.png") == (
        artifact_root / "visual_evidence" / "osteo_vision" / "mask.png"
    ).resolve()
    assert resolve_path("artifacts/reports/case.json") == (artifact_root / "reports" / "case.json").resolve()
    assert resolve_path("artifacts/checkpoints/model.pt") == (
        runtime_root / "artifacts" / "checkpoints" / "model.pt"
    ).resolve()
    assert resolve_path("artifacts/platform/three_d_runtime/references/d024/model.stl") == (
        runtime_root / "artifacts" / "platform" / "three_d_runtime" / "references" / "d024" / "model.stl"
    ).resolve()
