from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

from tools.download_d051_mronj_imc_starter import REQUIRED_SUBJECTS
from tools.verify_d051_mronj_imc_starter import inspect_imc_table, write_outputs


def test_inspect_imc_table_checks_columns_coordinates_and_rows(tmp_path: Path) -> None:
    table = tmp_path / "Patient01_02.txt"
    table.write_text("X\tY\tZ\tMarker\n0\t1\t2\t3.5\n4\t5\t6\t7.5\n", encoding="utf-8")

    result = inspect_imc_table(table)

    assert result["status"] == "passed"
    assert result["column_count"] == 4
    assert result["row_count"] == 2
    assert result["coordinate_ranges"]["X"] == {"min": 0.0, "max": 4.0}


def test_inspect_imc_table_rejects_malformed_rows(tmp_path: Path) -> None:
    table = tmp_path / "Patient01_02.txt"
    table.write_text("X\tY\tZ\tMarker\n0\t1\t2\n", encoding="utf-8")

    result = inspect_imc_table(table)

    assert result["status"] == "failed"
    assert result["malformed_row_examples"] == [2]


def test_write_outputs_emits_manifest_csv_and_verification(tmp_path: Path) -> None:
    artifact = {
        "subject_id": REQUIRED_SUBJECTS[0],
        "cohort": "mronj",
        "file_role": "imaging_mass_cytometry_roi_table",
        "original_file_name": "Patient01_02.txt",
        "relative_path": "raw/Patient01_02.txt",
        "direct_download_url": "https://example.org/file",
        "size_bytes": 4,
        "expected_size_bytes": 4,
        "size_matches": True,
        "official_md5": hashlib.md5(b"data", usedforsecurity=False).hexdigest(),
        "local_md5": hashlib.md5(b"data", usedforsecurity=False).hexdigest(),
        "md5_matches": True,
        "sha256": hashlib.sha256(b"data").hexdigest(),
        "verification_status": "passed",
    }
    manifest = {"datasets": [{"local_artifacts": [artifact]}]}
    verification = {"status": "passed"}

    write_outputs(tmp_path, manifest, verification)

    assert json.loads((tmp_path / "verification_20260718.json").read_text(encoding="utf-8")) == {"status": "passed"}
    with (tmp_path / "manifest.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["dataset_id"] == "D051"


def test_docx_fixture_is_a_valid_zip(tmp_path: Path) -> None:
    path = tmp_path / "supplement.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")

    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
