from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.download_d051_mronj_imc_starter import (
    REQUIRED_SUBJECTS,
    select_all_roi_files,
    select_balanced_roi_files,
    subject_id,
    verify_downloaded_file,
    write_download_receipt,
)


def _files() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, subject in enumerate(REQUIRED_SUBJECTS):
        rows.extend(
            [
                {"name": f"{subject}_01.txt", "size": 200 + index},
                {"name": f"{subject}_02.txt", "size": 100 + index},
            ]
        )
    rows.extend(
        [
            {"name": "Tonsil01.txt", "size": 50},
            {"name": "panel.csv", "size": 10},
        ]
    )
    return rows


def test_balanced_selection_has_one_smallest_roi_per_required_subject() -> None:
    selected = select_balanced_roi_files(_files())

    assert len(selected) == 14
    assert [subject_id(str(row["name"])) for row in selected] == list(REQUIRED_SUBJECTS)
    assert all(str(row["name"]).endswith("_02.txt") for row in selected)


def test_balanced_selection_rejects_missing_subject() -> None:
    rows = [row for row in _files() if not str(row["name"]).startswith("Patient06_")]

    with pytest.raises(RuntimeError, match="Patient06"):
        select_balanced_roi_files(rows)


def test_all_roi_selection_includes_tonsil_and_excludes_metadata() -> None:
    selected = select_all_roi_files(_files())

    assert len(selected) == 29
    assert any(row["name"] == "Tonsil01.txt" for row in selected)
    assert not any(row["name"] == "panel.csv" for row in selected)


def test_download_integrity_verifies_official_md5_and_sha256(tmp_path: Path) -> None:
    path = tmp_path / "Patient01_02.txt"
    path.write_bytes(b"d051-imc")
    item = {
        "name": path.name,
        "size": path.stat().st_size,
        "download_url": "https://example.org/Patient01_02.txt",
        "computed_md5": hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest(),
    }

    receipt = verify_downloaded_file(path, item)

    assert receipt["official_md5"] == receipt["local_md5"]
    assert receipt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_download_receipt_preserves_records(tmp_path: Path) -> None:
    rows = [
        {
            "dataset_id": "D051",
            "size_bytes": 8,
            "sha256": "a" * 64,
        }
    ]

    write_download_receipt(tmp_path, rows)

    payload = json.loads((tmp_path / "d051_download_receipt.json").read_text(encoding="utf-8"))
    assert payload["record_count"] == 1
    assert payload["total_size_bytes"] == 8
    assert (tmp_path / "d051_download_receipt.csv").is_file()
