from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.download_d095_mdacc_orn_time_to_event import (
    ARTICLE_ID,
    ARTICLE_VERSION,
    DOWNLOAD_URL,
    EXPECTED_DOI,
    EXPECTED_FILENAME,
    EXPECTED_GRADE_COUNTS,
    EXPECTED_HEADERS,
    EXPECTED_LICENSE,
    EXPECTED_MD5,
    EXPECTED_PATIENT_COUNT,
    EXPECTED_SHA256,
    EXPECTED_SIZE,
    EXPECTED_TITLE,
    FILE_ID,
    _audit_csv,
    _validate_article_metadata,
    _validate_datacite_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "research/datasets/public-candidates/d095_mdacc_orn_time_to_event_20260719"


def test_metadata_contract_accepts_pinned_public_release() -> None:
    article = {
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
    datacite = {
        "data": {
            "id": EXPECTED_DOI,
            "attributes": {
                "titles": [{"title": EXPECTED_TITLE}],
                "rightsList": [{"rightsIdentifier": "cc-by-4.0"}],
                "sizes": [f"{EXPECTED_SIZE} Bytes"],
            },
        }
    }

    assert _validate_article_metadata(article)["id"] == FILE_ID
    _validate_datacite_metadata(datacite)


def test_local_csv_and_manifest_are_integrity_bound() -> None:
    csv_path = DATASET_DIR / "raw/mdacc_orn_time_to_event_v1.csv"
    manifest_path = DATASET_DIR / "d095_mdacc_orn_time_to_event_manifest.json"
    assert csv_path.stat().st_size == EXPECTED_SIZE
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == EXPECTED_SHA256

    audit = _audit_csv(csv_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["records"][0]

    assert audit["patient_count"] == EXPECTED_PATIENT_COUNT
    assert audit["column_count"] == len(EXPECTED_HEADERS)
    assert audit["tsai_grade_counts"] == EXPECTED_GRADE_COUNTS
    assert audit["missing_cell_count"] == 0
    assert record["content_audit"] == audit
    assert record["training_eligible"] is False
