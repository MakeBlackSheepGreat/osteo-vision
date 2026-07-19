from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from tools.download_d090_breast_sentinel_icg_video import (
    _contained_path,
    _download_verified,
    _expected_md5,
    _select_archive,
    _video_members,
)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [self.payload[:3], self.payload[3:]]


class _FakeSession:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(self.payload)


def _md5(payload: bytes) -> str:
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def test_contained_path_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="escapes"):
        _contained_path(tmp_path, "../outside.bin")


def test_select_archive_rejects_duplicate_sanitized_names() -> None:
    files = [
        {
            "key": "sample?.zip",
            "size": 1,
            "checksum": "md5:" + "a" * 32,
            "links": {"self": "https://zenodo.org/a"},
        },
        {
            "key": "sample*.zip",
            "size": 1,
            "checksum": "md5:" + "b" * 32,
            "links": {"self": "https://zenodo.org/b"},
        },
    ]

    with pytest.raises(RuntimeError, match="duplicate"):
        _select_archive(files)


def test_download_verified_commits_only_after_size_and_md5_match(tmp_path: Path) -> None:
    payload = b"d090-icg-video"
    destination = tmp_path / "video.zip"

    receipt = _download_verified(
        _FakeSession(payload),
        "https://zenodo.org/video.zip",
        destination,
        expected_size=len(payload),
        expected_md5=_md5(payload),
    )

    assert destination.read_bytes() == payload
    assert not destination.with_name("video.zip.part").exists()
    assert receipt["md5"] == _md5(payload)
    assert receipt["sha256"] == hashlib.sha256(payload).hexdigest()


def test_download_verified_removes_partial_on_size_mismatch(tmp_path: Path) -> None:
    payload = b"short"
    destination = tmp_path / "video.zip"

    with pytest.raises(RuntimeError, match="size mismatch"):
        _download_verified(
            _FakeSession(payload),
            "https://zenodo.org/video.zip",
            destination,
            expected_size=len(payload) + 1,
            expected_md5=_md5(payload),
        )

    assert not destination.exists()
    assert not destination.with_name("video.zip.part").exists()


def test_download_verified_removes_partial_on_md5_mismatch(tmp_path: Path) -> None:
    payload = b"corrupt"
    destination = tmp_path / "video.zip"

    with pytest.raises(RuntimeError, match="MD5 mismatch"):
        _download_verified(
            _FakeSession(payload),
            "https://zenodo.org/video.zip",
            destination,
            expected_size=len(payload),
            expected_md5="0" * 32,
        )

    assert not destination.exists()
    assert not destination.with_name("video.zip.part").exists()


def test_download_verified_rejects_non_https_url(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="HTTPS"):
        _download_verified(
            _FakeSession(b"x"),
            "http://zenodo.org/video.zip",
            tmp_path / "video.zip",
            expected_size=1,
            expected_md5=_md5(b"x"),
        )


def test_video_members_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "videos.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../S1.mp4", b"one")
        archive.writestr("S2.mp4", b"two")
        archive.writestr("S3.mp4", b"three")

    with pytest.raises(RuntimeError, match="unsafe"):
        _video_members(archive_path)


def test_video_members_requires_three_videos(tmp_path: Path) -> None:
    archive_path = tmp_path / "videos.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("S1.mp4", b"one")
        archive.writestr("S2.mp4", b"two")

    with pytest.raises(RuntimeError, match="requires 3"):
        _video_members(archive_path)


def test_expected_md5_requires_zenodo_checksum_shape() -> None:
    assert _expected_md5("md5:" + "a" * 32) == "a" * 32
    with pytest.raises(RuntimeError, match="valid MD5"):
        _expected_md5("sha256:" + "b" * 64)
