from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.files import (
    _artifact_roots,
    _manifest_parent,
    _resolve_local_path,
    _video_roots,
    router,
)
from backend.osteo_vision_api.core.settings import Settings


def _client(tmp_path: Path) -> tuple[TestClient, Settings, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    settings = Settings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        video_manifest_path=tmp_path / "manifests" / "videos.csv",
        ofdvd_manifest_path=tmp_path / "manifests" / "ofdvd.csv",
    )
    app = FastAPI()
    app.include_router(router(settings))
    return TestClient(app), settings, artifact_root


def test_file_routes_preserve_percent_literal_and_reject_directories(tmp_path: Path) -> None:
    client, _, artifact_root = _client(tmp_path)
    image = artifact_root / "100%20_signal.jpg"
    image.write_bytes(b"image")
    directory = artifact_root / "directory.jpg"
    directory.mkdir()

    response = client.get("/files/preview", params={"path": str(image)})

    assert response.status_code == 200
    assert response.content == b"image"
    assert client.get("/files/preview", params={"path": str(directory)}).status_code == 404


def test_file_routes_keep_root_and_suffix_guards(tmp_path: Path) -> None:
    client, _, artifact_root = _client(tmp_path)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    unsupported = artifact_root / "report.txt"
    unsupported.write_text("report", encoding="utf-8")

    assert client.get("/files/preview", params={"path": str(outside)}).status_code == 403
    assert client.get("/files/preview", params={"path": str(unsupported)}).status_code == 415
    assert client.get("/files/preview", params={"path": str(artifact_root / "missing.jpg")}).status_code == 404


def test_local_path_resolution_fails_closed_for_invalid_and_non_file_paths(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, artifact_root=tmp_path / "artifacts")
    roots = _artifact_roots(settings)
    directory = tmp_path / "artifacts"
    directory.mkdir()

    with pytest.raises(HTTPException) as invalid_path:
        _resolve_local_path(
            settings,
            "\x00",
            not_found_detail="missing",
            allowed_roots=roots,
            outside_detail="outside",
        )
    assert invalid_path.value.status_code == 404

    with pytest.raises(HTTPException) as directory_path:
        _resolve_local_path(
            settings,
            str(directory),
            not_found_detail="missing",
            allowed_roots=roots,
            outside_detail="outside",
        )
    assert directory_path.value.status_code == 404


def test_root_resolution_deduplicates_artifact_and_manifest_roots(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    settings = Settings(
        project_root=tmp_path,
        artifact_root=artifact_root,
        video_manifest_path=artifact_root / "videos.csv",
        ofdvd_manifest_path=artifact_root / "ofdvd.csv",
    )

    artifact_roots = _artifact_roots(settings)
    video_roots = _video_roots(settings, artifact_roots=artifact_roots)

    assert len(artifact_roots) == len(set(artifact_roots))
    assert len(video_roots) == len(set(video_roots))
    assert _manifest_parent(settings.video_manifest_path) == artifact_root.resolve()
