from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.download_d094_clinrad_orn_context import (
    ARTICLE_ID,
    ARTICLE_VERSION,
    DATACITE_URL,
    DOWNLOAD_URL,
    EXPECTED_DOI,
    EXPECTED_FILENAME,
    EXPECTED_HEADERS,
    EXPECTED_LICENSE,
    EXPECTED_MD5,
    EXPECTED_PATIENT_COUNT,
    EXPECTED_SHA256,
    EXPECTED_SIZE,
    EXPECTED_STAGE_COUNTS,
    EXPECTED_TITLE,
    FILE_ID,
    _audit_workbook,
    _validate_article_metadata,
    _validate_datacite_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "research/datasets/public-candidates/d094_clinrad_orn_context_20260719"


def _article_metadata() -> dict[str, object]:
    return {
        "id": ARTICLE_ID,
        "version": ARTICLE_VERSION,
        "doi": EXPECTED_DOI,
        "title": EXPECTED_TITLE,
        "is_public": True,
        "is_confidential": False,
        "download_disabled": False,
        "license": {"name": EXPECTED_LICENSE},
        "files": [
            {
                "id": FILE_ID,
                "name": EXPECTED_FILENAME,
                "size": EXPECTED_SIZE,
                "computed_md5": EXPECTED_MD5,
                "download_url": DOWNLOAD_URL,
                "is_link_only": False,
            }
        ],
    }


def _datacite_metadata() -> dict[str, object]:
    return {
        "data": {
            "id": EXPECTED_DOI,
            "attributes": {
                "titles": [{"title": EXPECTED_TITLE}],
                "rightsList": [{"rightsIdentifier": "cc-by-4.0"}],
                "sizes": [f"{EXPECTED_SIZE} Bytes"],
            },
        }
    }


def test_metadata_contract_accepts_pinned_public_release() -> None:
    file_info = _validate_article_metadata(_article_metadata())
    _validate_datacite_metadata(_datacite_metadata())

    assert file_info["id"] == FILE_ID
    assert DATACITE_URL.endswith(EXPECTED_DOI)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ARTICLE_ID + 1),
        ("version", ARTICLE_VERSION + 1),
        ("doi", "10.6084/changed"),
        ("title", "changed"),
        ("is_public", False),
        ("is_confidential", True),
        ("download_disabled", True),
    ],
)
def test_article_metadata_changes_fail_closed(field: str, value: object) -> None:
    payload = _article_metadata()
    payload[field] = value

    with pytest.raises(RuntimeError):
        _validate_article_metadata(payload)


def test_local_workbook_and_manifest_are_integrity_bound() -> None:
    workbook = DATASET_DIR / "raw/clinrad_orn_anonymized_cohort_v2.xlsx"
    manifest_path = DATASET_DIR / "d094_clinrad_orn_context_manifest.json"
    assert workbook.stat().st_size == EXPECTED_SIZE
    assert EXPECTED_SHA256 == __import__("hashlib").sha256(workbook.read_bytes()).hexdigest()

    audit = _audit_workbook(workbook)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["records"][0]

    assert audit["patient_count"] == EXPECTED_PATIENT_COUNT
    assert audit["column_count"] == len(EXPECTED_HEADERS)
    assert audit["watson_stage_grade_counts"] == EXPECTED_STAGE_COUNTS
    assert record["content_audit"] == audit
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False
