from __future__ import annotations

from pathlib import Path


def test_competition_disc_assets_define_a_portable_release_layout() -> None:
    root = Path(__file__).resolve().parents[2]
    assets = root / "packaging" / "competition_disc"

    assert (assets / "verify_release.ps1").is_file()
    assert (assets / "README.md").is_file()
    assert "release-manifest.json" in (assets / "verify_release.ps1").read_text(encoding="utf-8")
    assert '"Osteo Vision Platform.exe"' in (assets / "verify_release.ps1").read_text(encoding="utf-8")
    assert "Osteo_Vision_r28_使用说明.docx" in (assets / "verify_release.ps1").read_text(encoding="utf-8")
    assert "Osteo_Vision_r28_使用说明.pdf" in (assets / "verify_release.ps1").read_text(encoding="utf-8")
    assert "OFDVDNET_001.mp4" in (assets / "verify_release.ps1").read_text(encoding="utf-8")
    assert "mandible_d024_0001.stl" in (assets / "verify_release.ps1").read_text(encoding="utf-8")


def test_competition_disc_builder_checks_media_capacity_and_integrity() -> None:
    root = Path(__file__).resolve().parents[2]
    builder = (root / "scripts" / "build_competition_disc_package.ps1").read_text(encoding="utf-8")

    assert "MediaCapacityGB" in builder
    assert "Get-FileHash" in builder
    assert "release-manifest.json" in builder
    assert "Get-ChildItem -LiteralPath $sourceDesktopPackage -Force" in builder
    assert '"Osteo Vision Platform.exe"' in builder
    assert '"platform\\\\Osteo Vision Platform.exe"' not in builder
    assert "OFDVDNET_001.mp4" in builder
    assert "mandible_d024_0001.stl" in builder
    assert "$userGuideFiles" in builder
    assert "Osteo_Vision_r28_使用说明.docx" in builder
    assert "Osteo_Vision_r28_使用说明.pdf" in builder


def test_desktop_builder_removes_stale_backend_before_pyinstaller_runs() -> None:
    root = Path(__file__).resolve().parents[2]
    builder = (root / "scripts" / "build_desktop_package.ps1").read_text(encoding="utf-8")

    assert "foreach ($staleBackendPath in @($backendDist, $pyinstallerBackendDist))" in builder
    assert "Remove-Item -LiteralPath $staleBackendPath -Recurse -Force" in builder


def test_desktop_builder_rewrites_development_absolute_paths_in_runtime_metadata() -> None:
    root = Path(__file__).resolve().parents[2]
    builder = (root / "scripts" / "build_desktop_package.ps1").read_text(encoding="utf-8")

    assert "Rewrite-PackagedMetadataPaths" in builder
    assert "runtime_external_root" in builder
    assert '$DevelopmentRoot.Replace("\\", "\\\\")' in builder
