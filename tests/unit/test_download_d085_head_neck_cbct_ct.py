from __future__ import annotations

import pytest

from tools.download_d085_head_neck_cbct_ct import (
    EXPECTED_FILE_NAME,
    EXPECTED_MD5,
    EXPECTED_SIZE,
    _update_manifest_record,
    _validated_download_spec,
)


def _zenodo_record() -> dict[str, object]:
    return {
        "id": 13231287,
        "metadata": {
            "license": {"id": "cc-by-4.0"},
            "access_right": "open",
        },
        "files": [
            {
                "key": EXPECTED_FILE_NAME,
                "size": EXPECTED_SIZE,
                "checksum": f"md5:{EXPECTED_MD5}",
                "links": {"self": ("https://zenodo.org/api/records/13231287/files/" "Head-Neck-CBCT-CT.rar/content")},
            }
        ],
    }


def test_validated_download_spec_requires_pinned_open_cc_by_archive() -> None:
    spec = _validated_download_spec(_zenodo_record())

    assert spec["size_bytes"] == EXPECTED_SIZE
    assert spec["md5"] == EXPECTED_MD5
    assert spec["license_id"] == "cc-by-4.0"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("license", {"id": "cc-by-nc-4.0"}),
        ("access_right", "restricted"),
    ],
)
def test_validated_download_spec_fails_closed_on_governance_change(field: str, value: object) -> None:
    record = _zenodo_record()
    metadata = record["metadata"]
    assert isinstance(metadata, dict)
    metadata[field] = value

    with pytest.raises(RuntimeError):
        _validated_download_spec(record)


def test_update_manifest_record_preserves_non_target_safety_boundary() -> None:
    record = {
        "candidate_id": "D085",
        "metadata_urls": ["https://api.datacite.org/dois/10.5281/zenodo.13231287"],
        "local_files": [{"path": "head_neck_cbct_ct/metadata/datacite.json"}],
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
    }
    updated = _update_manifest_record(
        record,
        spec={
            "download_url": "https://zenodo.org/file/content",
            "size_bytes": EXPECTED_SIZE,
            "md5": EXPECTED_MD5,
            "license_id": "cc-by-4.0",
        },
        archive_entry={"path": "head_neck_cbct_ct/raw/Head-Neck-CBCT-CT.rar"},
        metadata_entry={"path": "head_neck_cbct_ct/metadata/zenodo_record_13231287.json"},
        downloaded_at_utc="2026-07-19T00:00:00+00:00",
    )

    assert updated["download_status"] == "verified_archive_downloaded"
    assert updated["target_domain_flag"] is False
    assert updated["training_eligible"] is False
    assert updated["navigation_claim_allowed"] is False
    assert len(updated["local_files"]) == 3
