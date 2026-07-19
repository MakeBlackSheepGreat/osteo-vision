from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from tools import download_d093_mronj_spect_ct_figures as d093
from tools.download_d093_mronj_spect_ct_figures import (
    EXPECTED_DOI,
    EXPECTED_LICENSE,
    EXPECTED_TITLE,
    MENDELEY_ID,
    PINNED_FILES,
    VERSION,
    _download_pinned,
    _validate_files,
    _validate_snapshot,
    download_d093,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class _FakeSession:
    def __init__(self, snapshot: dict[str, object], files: list[dict[str, object]]) -> None:
        self.snapshot = snapshot
        self.files = files

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(self.snapshot if "/snapshot/" in url else self.files)


def _snapshot() -> dict[str, object]:
    return {
        "id": MENDELEY_ID,
        "version": VERSION,
        "name": EXPECTED_TITLE,
        "doi": EXPECTED_DOI,
        "is_confidential": False,
        "is_metadata_only": False,
        "licence": {"short_name": EXPECTED_LICENSE},
    }


def _files(specs: tuple[dict[str, object], ...] | list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    return [
        {
            "filename": spec["filename"],
            "id": spec["id"],
            "content_details": {
                "size": spec["size"],
                "sha256_hash": spec["sha256"],
                "content_type": spec["content_type"],
                "download_url": (
                    f"https://data.mendeley.com/public-files/datasets/{MENDELEY_ID}/files/"
                    f"{spec['id']}/file_downloaded"
                ),
            },
        }
        for spec in (PINNED_FILES if specs is None else specs)
    ]


def test_snapshot_and_file_inventory_are_pinned() -> None:
    _validate_snapshot(_snapshot())
    validated = _validate_files(_files())

    assert len(validated) == 2
    assert all(item["download_url"].endswith("/file_downloaded") for item in validated)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "changed"),
        ("version", VERSION + 1),
        ("doi", "10.17632/changed.1"),
        ("name", "changed"),
        ("is_confidential", True),
        ("is_metadata_only", True),
    ],
)
def test_snapshot_validation_fails_closed(field: str, value: object) -> None:
    snapshot = _snapshot()
    snapshot[field] = value

    with pytest.raises(RuntimeError):
        _validate_snapshot(snapshot)


def test_snapshot_validation_fails_closed_on_license_change() -> None:
    snapshot = _snapshot()
    snapshot["licence"] = {"short_name": "Custom"}

    with pytest.raises(RuntimeError, match="license"):
        _validate_snapshot(snapshot)


@pytest.mark.parametrize("mutation", ["missing", "extra", "filename", "size", "sha256", "content_type", "url"])
def test_file_inventory_validation_fails_closed(mutation: str) -> None:
    files = deepcopy(_files())
    if mutation == "missing":
        files.pop()
    elif mutation == "extra":
        files.append(deepcopy(files[0]))
        files[-1]["id"] = "extra"
    elif mutation == "filename":
        files[0]["filename"] = "changed.jpg"
    elif mutation == "size":
        files[0]["content_details"]["size"] += 1  # type: ignore[index]
    elif mutation == "sha256":
        files[0]["content_details"]["sha256_hash"] = "0" * 64  # type: ignore[index]
    elif mutation == "content_type":
        files[0]["content_details"]["content_type"] = "application/octet-stream"  # type: ignore[index]
    else:
        files[0]["content_details"]["download_url"] = "https://example.invalid/file"  # type: ignore[index]

    with pytest.raises(RuntimeError):
        _validate_files(files)


def test_download_pinned_replaces_same_size_corruption(tmp_path: Path, monkeypatch) -> None:
    payload = b"verified-d093"
    destination = tmp_path / "figure.bin"
    destination.write_bytes(b"x" * len(payload))
    calls = 0

    def fake_download(_session: object, _url: str, path: Path, _expected_size: int) -> None:
        nonlocal calls
        calls += 1
        path.write_bytes(payload)

    monkeypatch.setattr(d093, "_download", fake_download)

    _download_pinned(
        object(),
        "https://example.org/figure.bin",
        destination,
        expected_size=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )

    assert calls == 1
    assert destination.read_bytes() == payload


def test_download_writes_visually_reviewed_safe_boundary_manifest(tmp_path: Path, monkeypatch) -> None:
    payloads: dict[str, bytes] = {}
    test_specs: list[dict[str, object]] = []
    for index, source_spec in enumerate(PINNED_FILES):
        buffer = BytesIO()
        image_format = "JPEG" if Path(str(source_spec["local_name"])).suffix == ".jpg" else "TIFF"
        Image.new("RGB", (12 + index, 8 + index), color=(30, 60, 90)).save(buffer, format=image_format)
        payload = buffer.getvalue()
        payloads[str(source_spec["id"])] = payload
        test_specs.append(
            {
                **source_spec,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    monkeypatch.setattr(d093, "PINNED_FILES", tuple(test_specs))
    files = _files(test_specs)
    monkeypatch.setattr(d093, "_session", lambda: _FakeSession(_snapshot(), files))

    def fake_download(_session: object, url: str, destination: Path, _expected_size: int) -> None:
        file_id = next(file_id for file_id in payloads if file_id in url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payloads[file_id])

    monkeypatch.setattr(d093, "_download", fake_download)

    manifest = download_d093(tmp_path)
    record = manifest["records"][0]
    persisted = json.loads((tmp_path / "d093_mronj_spect_ct_figures_manifest.json").read_text(encoding="utf-8"))

    assert persisted == manifest
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False
    assert record["review_state"] == "review_required"
    assert record["visual_review"]["status"] == "completed"
    assert [item["visual_classification"] for item in record["visual_review"]["findings"]] == [
        "diagnostic_roc_curve_without_anatomical_imaging",
        "mronj_spect_ct_multiplanar_composite_with_roi_table",
    ]
    assert [item["file_role"] for item in record["local_files"][:2]] == [
        "published_roc_curve_figure",
        "published_spect_ct_composite_figure",
    ]
