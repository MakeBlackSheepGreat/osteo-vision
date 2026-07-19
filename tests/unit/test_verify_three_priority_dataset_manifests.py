from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.verify_three_priority_dataset_manifests import (
    DEFAULT_MANIFESTS,
    verify_manifest,
    verify_manifests,
)


def test_default_manifests_include_d051_balanced_starter() -> None:
    assert any(
        path.name == "manifest.json" and path.parent.name == "d051_mronj_imaging_mass_cytometry_starter_20260718"
        for path in DEFAULT_MANIFESTS
    )


def test_default_manifests_include_verified_c3vd_l2_proxy() -> None:
    assert len(DEFAULT_MANIFESTS) == 15
    manifest_path = next(path for path in DEFAULT_MANIFESTS if path.name == "c3vd_l2_proxy_manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D087"
    assert record["size_bytes"] == 1_515_094_074
    assert record["sha256"] == ("ce6b285c578d9ebe42d9013bc21eb244d6df93ca0de63333b5ab38a80acc16ff")
    assert record["zip_crc_verified"] is True
    assert record["paired_frame_count"] == 766
    assert record["duplicate_pose_timestamp_count"] == 2
    assert record["runtime_pose_use_requires_deduplication"] is True
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False
    assert record["navigation_claim_allowed"] is False


def test_default_manifests_include_d094_clinrad_orn_context() -> None:
    manifest_path = next(path for path in DEFAULT_MANIFESTS if path.name == "d094_clinrad_orn_context_manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D094"
    assert record["patient_count"] == 53
    assert record["content_audit"]["column_count"] == 12
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def test_default_manifests_include_d095_mdacc_orn_context() -> None:
    manifest_path = next(
        path for path in DEFAULT_MANIFESTS if path.name == "d095_mdacc_orn_time_to_event_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D095"
    assert record["patient_count"] == 1_129
    assert record["content_audit"]["column_count"] == 61
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def test_default_manifests_include_d090_non_target_icg_video() -> None:
    manifest_path = next(
        path for path in DEFAULT_MANIFESTS if path.name == "d090_breast_sentinel_icg_video_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D090"
    assert payload["video_count"] == 3
    assert record["license_identifier"] == "cc-by-4.0"
    assert record["non_jaw"] is True
    assert record["non_bone"] is True
    assert record["non_target_domain"] is True
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def test_default_manifests_include_d091_three_panel_icg_video() -> None:
    manifest_path = next(
        path for path in DEFAULT_MANIFESTS if path.name == "d091_icg_hepatic_dynamic_proxy_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D091"
    assert payload["video_count"] == 2
    assert record["license_identifier"] == "cc-by-4.0"
    assert "white-light" in record["channel_availability"]
    assert "independently synchronized channels" in record["channel_availability"]
    assert record["non_jaw"] is True
    assert record["non_bone"] is True
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def test_default_manifests_include_pmcanalseg_navigation_starter() -> None:
    manifest_path = next(
        path for path in DEFAULT_MANIFESTS if path.name == "pmcanalseg_navigation_starter_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["dataset_id"] == "D092"
    assert record["patient_count"] == 5
    assert payload["file_count"] == 22
    assert payload["total_size_bytes"] == 75_757_662
    assert len(record["geometry_checks"]) == 10
    assert all(item["shape_matches"] is True for item in record["geometry_checks"])
    assert all(item["affine_matches"] is True for item in record["geometry_checks"])
    assert record["orientation_review_required"] is True
    assert record["navigation_claim_allowed"] is False
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def test_default_manifests_include_d093_mronj_spect_ct_figures() -> None:
    manifest_path = next(path for path in DEFAULT_MANIFESTS if path.name == "d093_mronj_spect_ct_figures_manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["candidate_id"] == "D093"
    assert record["license_identifier"] == "cc-by-4.0"
    assert payload["file_count"] == 4
    assert payload["total_size_bytes"] == 524_188
    assert len(record["image_checks"]) == 2
    assert record["visual_review"]["status"] == "completed"
    assert [item["visual_classification"] for item in record["visual_review"]["findings"]] == [
        "diagnostic_roc_curve_without_anatomical_imaging",
        "mronj_spect_ct_multiplanar_composite_with_roi_table",
    ]
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False
    assert record["review_state"] == "review_required"


def test_default_manifests_include_selectively_extracted_mmdental_context() -> None:
    manifest_path = next(
        path for path in DEFAULT_MANIFESTS if path.name == "mmdental_patient_context_starter_manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]

    assert record["dataset_id"] == "D069"
    assert payload["remote_zip"]["size_bytes"] == 68_087_010_723
    assert payload["remote_zip"]["central_directory"]["zip64"] is True
    assert payload["extracted_member"]["name"].endswith("medical_records.csv")
    assert payload["extracted_member"]["structural_summary"]["unique_filename_count"] == 660
    cbct = payload["extracted_cbct_members"][0]
    assert cbct["name"] == "MMDental/492/492.nii.gz"
    assert cbct["nifti_header"]["shape"] == [640, 640, 400]
    assert cbct["paired_context"]["medical_history_present"] is True
    modeling = payload["derived_modeling_artifact"]
    assert modeling["surface_sha256"] == ("37304a2c54d14378bdfe1ddf5bd8eeffb6828d64a168f1cc8c59e8d2d1af6e9c")
    assert modeling["vertex_count"] == 118_452
    assert modeling["navigation_ready"] is False
    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False


def _manifest(tmp_path: Path) -> Path:
    data_path = tmp_path / "sample.bin"
    data_path.write_bytes(b"osteo-vision")
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "test-v1",
                "record_count": 1,
                "total_size_bytes": data_path.stat().st_size,
                "records": [
                    {
                        "source_page_url": "https://example.org/source",
                        "direct_download_url": "https://example.org/file",
                        "local_path": str(data_path),
                        "size_bytes": data_path.stat().st_size,
                        "sha256": digest,
                        "license": "CC BY 4.0",
                        "license_review_status": "verified_from_source",
                        "domain_tier": "non_target_proxy",
                        "modality": "binary engineering sample",
                        "labels": "deterministic test payload",
                        "sample_count": 1,
                        "clinical_variables_unavailable_reason": "No patient data are present.",
                        "recommended_use": "Manifest validator unit test.",
                        "target_domain_flag": False,
                        "training_eligible": False,
                        "review_state": "review_required",
                        "download_status": "verified",
                        "downloaded_at_utc": "2026-07-18T00:00:00+00:00",
                        "data_boundary": "Public proxy data for engineering validation only.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_verify_manifest_accepts_complete_verified_proxy_record(tmp_path: Path) -> None:
    result = verify_manifest(_manifest(tmp_path))

    assert result["status"] == "passed"
    assert result["verified_record_count"] == 1
    assert all(value == 1 for value in result["provenance_coverage"].values())
    assert result["errors"] == []


def test_verify_manifest_detects_tampered_file(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    (tmp_path / "sample.bin").write_bytes(b"tampered-data")

    result = verify_manifest(manifest_path)

    assert result["status"] == "failed"
    assert {error["code"] for error in result["errors"]} >= {"size_mismatch", "total_size_mismatch"}


def test_verify_manifests_aggregates_counts(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)

    result = verify_manifests([manifest_path])

    assert result["status"] == "passed"
    assert result["manifest_count"] == 1
    assert result["record_count"] == 1
    assert result["file_count"] == 1


def test_verify_manifest_accepts_nested_dataset_artifacts(tmp_path: Path) -> None:
    data_path = tmp_path / "metadata.csv"
    data_path.write_text("age,sex\n61,F\n", encoding="utf-8")
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "nested_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "nested-test-v1",
                "dataset_count": 1,
                "artifact_count": 1,
                "total_size_bytes": data_path.stat().st_size,
                "downloaded_at_utc": "2026-07-18T00:00:00+00:00",
                "datasets": [
                    {
                        "dataset_id": "D999",
                        "source_page_url": "https://example.org/source",
                        "license": "CC BY 4.0",
                        "governance_state": "public_open_access",
                        "priority_target": "patient_conditioning_proxy",
                        "modalities": ["structured table"],
                        "segmentation_labels": ["candidate region"],
                        "patient_count": 1,
                        "clinical_variables": ["age", "sex"],
                        "recommended_use": "Contract normalization test.",
                        "target_domain_flag": False,
                        "training_eligible": False,
                        "review_state": "review_required",
                        "data_boundary": "Proxy metadata only.",
                        "local_artifacts": [
                            {
                                "direct_download_url": "https://example.org/metadata.csv",
                                "relative_path": data_path.name,
                                "size_bytes": data_path.stat().st_size,
                                "sha256": digest,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = verify_manifest(manifest_path)

    assert result["status"] == "passed"
    assert result["verified_record_count"] == 1
    assert result["verified_file_count"] == 1
    assert result["provenance_source_aliases"]["domain_tier"] == {"priority_target": 1}
    assert result["provenance_source_aliases"]["modality"] == {"modalities": 1}
    assert result["provenance_source_aliases"]["labels"] == {"segmentation_labels": 1}


def test_verify_manifest_accepts_explicit_count_and_clinical_unavailability(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record.pop("sample_count")
    record["sample_count_unavailable_reason"] = "The source reports no cohort count."
    record.pop("clinical_variables_unavailable_reason")
    record["clinical_variables_status"] = "No patient-level variables are published."
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_manifest(manifest_path)

    assert result["status"] == "passed"
    assert result["provenance_source_aliases"]["sample_or_patient_count"] == {"sample_count_unavailable_reason": 1}
    assert result["provenance_source_aliases"]["clinical_variables"] == {"clinical_variables_status": 1}


def test_verify_manifest_accepts_metadata_only_access_and_download_audit(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record.pop("direct_download_url")
    record.pop("downloaded_at_utc")
    record["download_status"] = "metadata_only_controlled_access"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_manifest(manifest_path)

    assert result["status"] == "passed"
    assert result["provenance_source_aliases"]["download_access"] == {"download_status": 1}
    assert result["provenance_source_aliases"]["download_audit"] == {"download_status": 1}


def test_verify_manifest_rejects_missing_provenance_fields(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record.pop("direct_download_url")
    record.pop("modality")
    record.pop("labels")
    record.pop("clinical_variables_unavailable_reason")
    record["data_boundary"] = "Engineering proxy boundary."
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_manifest(manifest_path)

    assert result["status"] == "failed"
    provenance_error = next(error for error in result["errors"] if error["code"] == "provenance_fields_missing")
    assert set(provenance_error["fields"]) >= {
        "download_access",
        "modality",
        "labels",
        "clinical_variables",
    }


def test_verify_manifest_rejects_invalid_boolean_boundary_fields(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["records"][0]["target_domain_flag"] = "false"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_manifest(manifest_path)

    assert result["status"] == "failed"
    provenance_error = next(error for error in result["errors"] if error["code"] == "provenance_fields_missing")
    assert "target_domain_flag" in provenance_error["fields"]
    assert any(error["code"] == "proxy_training_boundary_invalid" for error in result["errors"])
