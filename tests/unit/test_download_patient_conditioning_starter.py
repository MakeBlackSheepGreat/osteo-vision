from __future__ import annotations

import csv
from pathlib import Path

from tools.download_patient_conditioning_starter import (
    KITS23_CASE_FILES,
    SOURCES,
    _source_page,
    write_manifest,
)


def test_patient_conditioning_starter_covers_image_mask_and_clinical_context() -> None:
    roles = {str(source["file_role"]) for source in SOURCES}

    assert {"clinical_context_table", "sample_ct_image", "sample_pixel_mask"} <= roles


def test_patient_conditioning_sources_are_non_target_domain_proxies() -> None:
    assert _source_page("D071").startswith("https://github.com/")
    assert _source_page("D072").startswith("https://www.cancerimagingarchive.net/")


def test_kits23_starter_has_five_complete_patient_pairs() -> None:
    case_sources = [source for source in SOURCES if source.get("case_id")]
    expected_cases = {case_id for case_id, _, _ in KITS23_CASE_FILES}

    assert expected_cases == {f"case_{index:05d}" for index in range(5)}
    assert len(case_sources) == 10
    assert {source["case_id"] for source in case_sources} == expected_cases
    for case_id in expected_cases:
        roles = {source["file_role"] for source in case_sources if source["case_id"] == case_id}
        assert roles == {"sample_ct_image", "sample_pixel_mask"}


def test_kits23_expected_sizes_are_positive_and_urls_are_unique() -> None:
    case_sources = [source for source in SOURCES if source.get("case_id")]

    assert all(int(source["expected_size"]) > 0 for source in case_sources)
    assert len({source["url"] for source in case_sources}) == len(case_sources)


def test_manifest_csv_supports_optional_case_id(tmp_path: Path) -> None:
    rows = [
        {"dataset_id": "D071", "size_bytes": 1},
        {"dataset_id": "D071", "case_id": "case_00000", "size_bytes": 2},
    ]

    write_manifest(tmp_path, rows)

    with (tmp_path / "patient_conditioning_starter_manifest.csv").open("r", encoding="utf-8", newline="") as handle:
        parsed = list(csv.DictReader(handle))
    assert parsed[1]["case_id"] == "case_00000"
