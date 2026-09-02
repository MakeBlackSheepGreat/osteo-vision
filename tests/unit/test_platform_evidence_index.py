from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.build_evidence_index import (
    DEFAULT_MANIFEST,
    ROOT,
    build_payload,
    repository_path,
    sha256,
)


def test_sha256_streams_file_content(tmp_path: Path) -> None:
    path = tmp_path / "evidence.bin"
    payload = b"osteo-vision-evidence" * 1024
    path.write_bytes(payload)

    assert sha256(path, chunk_size=31) == hashlib.sha256(payload).hexdigest()


def test_repository_path_rejects_parent_escape() -> None:
    with pytest.raises(ValueError, match="escapes the repository"):
        repository_path(ROOT.parent / "outside-evidence.json")


def test_current_evidence_manifest_has_consistent_versions_and_required_files() -> None:
    payload = build_payload(DEFAULT_MANIFEST)

    assert payload["project_versions"]["consistent"] is True
    assert payload["project_versions"]["manifest"] == "0.3.0-rc.2"
    assert payload["summary"]["missing_required"] == []
    assert payload["summary"]["ready_for_release"] is True
    assert payload["config"]["path"] == "configs/inference/osteo_vision_strict.yml"
    assert any(
        model["model_id"] == "keyframe_residual_attention_unet_s20260715_20260715" for model in payload["models"]
    )
