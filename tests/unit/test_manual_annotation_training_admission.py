from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from osteo_vision_core.datasets.registry import sha256_file
from osteo_vision_core.datasets.training_admission import (
    MANUAL_ANNOTATION_ROLE,
    TrainingAdmissionError,
    admit_manual_annotation_training_rows,
)


def test_manual_annotation_admission_keeps_audit_provenance_and_isolates_unsafe_rows(
    tmp_path: Path,
) -> None:
    accepted_a = _annotation_row(tmp_path, annotation_id="accepted-a", case_id="case-a", index=1)
    accepted_b = _annotation_row(tmp_path, annotation_id="accepted-b", case_id="case-b", index=2)
    engineering = {
        **_annotation_row(tmp_path, annotation_id="engineering", case_id="case-c", index=3),
        "actor_role": "engineering",
        "auth_source": "local_runtime",
    }
    draft = {
        **_annotation_row(tmp_path, annotation_id="draft", case_id="case-d", index=4),
        "review_state": "draft",
    }
    rejected = {
        **_annotation_row(tmp_path, annotation_id="rejected", case_id="case-e", index=5),
        "review_state": "rejected",
    }
    ineligible = {
        **_annotation_row(tmp_path, annotation_id="ineligible", case_id="case-f", index=6),
        "training_eligible": False,
        "sample_weight": 0.0,
        "sampling_weight": 0.0,
    }
    rights_pending = {
        **_annotation_row(tmp_path, annotation_id="rights-pending", case_id="case-g", index=7),
        "usage_policy": "annotation_review_complete_data_use_requires_verification",
        "license": "data use permission pending verification",
    }
    wrong_mask_type = {
        **_annotation_row(tmp_path, annotation_id="boundary-risk", case_id="case-h", index=8),
        "mask_type": "boundary_risk",
    }
    governance_pending = {
        **_annotation_row(tmp_path, annotation_id="governance-pending", case_id="case-i", index=9),
        "intake_usage_scope": "research_no_training",
        "intake_mapping_held_by_institution": False,
        "source_input_checksum_verified": False,
    }
    records = [
        accepted_a,
        accepted_b,
        engineering,
        draft,
        rejected,
        ineligible,
        rights_pending,
        wrong_mask_type,
        governance_pending,
    ]
    manifest = _write_manifest(tmp_path, records)

    result = admit_manual_annotation_training_rows(manifest)

    assert {row["annotation_id"] for row in result.rows} == {"accepted-a", "accepted-b"}
    assert {row["split"] for row in result.rows} == {"train", "val"}
    assert all(row["training_eligible"] == "true" for row in result.rows)
    assert all(row["label_source"] == "physician_manual_annotation" for row in result.rows)
    assert all(row["target_mask_type"] == "lesion" for row in result.rows)
    assert all(row["target_task"] == "lesion_segmentation" for row in result.rows)
    assert all(row["actor_role"] == "physician" for row in result.rows)
    assert all(row["reviewer_role"] == "physician" for row in result.rows)
    assert all(row["sample_weight"] == "4.0" for row in result.rows)
    assert all(row["review_manifest_checksum"] == sha256_file(manifest) for row in result.rows)
    assert all(row["source_snapshot_path"] == row["image_path"] for row in result.rows)
    assert all(row["source_checksum"] == row["image_checksum"] for row in result.rows)
    assert all(row["mask_checksum"] == row["label_checksum"] for row in result.rows)
    assert result.summary["admission_stage"] == "reviewed_finetune"
    assert result.summary["admitted_count"] == 2
    assert result.summary["isolated_count"] == 7
    reasons = result.summary["isolation_reason_counts"]
    assert reasons["untrusted_annotation_actor"] == 1
    assert reasons["review_not_accepted"] == 1
    assert reasons["rejected_review"] == 1
    assert reasons["training_ineligible"] == 1
    assert reasons["training_rights_not_verified"] == 1
    assert reasons["mask_type_not_selected"] == 1
    assert reasons["case_mapping_custody_unconfirmed"] == 1
    assert reasons["case_training_usage_not_authorized"] == 1
    assert reasons["source_input_checksum_unverified"] == 1
    rights_isolation = next(
        item for item in result.summary["isolation_records"] if item["annotation_id"] == "rights-pending"
    )
    assert rights_isolation["record"]["training_eligible"] is True
    assert "training_rights_not_verified" in rights_isolation["codes"]


def test_manual_annotation_admission_refuses_checksum_tampering(tmp_path: Path) -> None:
    row = _annotation_row(tmp_path, annotation_id="tampered", case_id="case-a", index=1)
    row["source_checksum"] = "0" * 64
    row["image_checksum"] = "0" * 64
    row["checksum"] = "0" * 64
    manifest = _write_manifest(tmp_path, [row])

    with pytest.raises(TrainingAdmissionError, match="source_checksum_mismatch"):
        admit_manual_annotation_training_rows(manifest)


def test_manual_annotation_admission_refuses_conflicting_checksum_aliases(tmp_path: Path) -> None:
    row = _annotation_row(tmp_path, annotation_id="aliases", case_id="case-a", index=1)
    row["image_checksum"] = "f" * 64
    manifest = _write_manifest(tmp_path, [row])

    with pytest.raises(TrainingAdmissionError, match="source_checksum_alias_mismatch"):
        admit_manual_annotation_training_rows(manifest)


def test_manual_annotation_admission_selects_one_explicit_video_signal_target(
    tmp_path: Path,
) -> None:
    row = _annotation_row(tmp_path, annotation_id="signal", case_id="case-a", index=1)
    row["mask_type"] = "fluorescence_signal"
    manifest = _write_manifest(tmp_path, [row])

    result = admit_manual_annotation_training_rows(
        manifest,
        target_mask_type="fluorescence_signal",
        target_task="video_signal_segmentation",
    )

    assert len(result.rows) == 1
    assert result.rows[0]["mask_type"] == "fluorescence_signal"
    assert result.rows[0]["target_mask_type"] == "fluorescence_signal"
    assert result.rows[0]["target_task"] == "video_signal_segmentation"
    assert result.summary["target_mask_type"] == "fluorescence_signal"
    assert result.summary["target_task"] == "video_signal_segmentation"


def test_manual_annotation_admission_isolates_non_independent_and_legacy_reviews(tmp_path: Path) -> None:
    valid = _annotation_row(tmp_path, annotation_id="valid-review", case_id="case-a", index=1)
    same_reviewer = _annotation_row(tmp_path, annotation_id="same-reviewer", case_id="case-b", index=2)
    same_reviewer["reviewer_actor_id"] = same_reviewer["actor_id"]
    legacy = _annotation_row(tmp_path, annotation_id="legacy-no-submitter", case_id="case-c", index=3)
    for key in (
        "submitted_by_actor_id",
        "submitted_by_role",
        "submitted_by_institution",
        "submitted_by_auth_source",
    ):
        legacy.pop(key)
    manifest = _write_manifest(tmp_path, [valid, same_reviewer, legacy])

    result = admit_manual_annotation_training_rows(manifest)

    assert [row["annotation_id"] for row in result.rows] == ["valid-review"]
    isolated = {item["annotation_id"]: item["codes"] for item in result.summary["isolation_records"]}
    assert "independent_physician_review_required" in isolated["same-reviewer"]
    assert "independent_physician_review_required" in isolated["legacy-no-submitter"]


def _annotation_row(
    root: Path,
    *,
    annotation_id: str,
    case_id: str,
    index: int,
) -> dict[str, object]:
    image_path = root / f"{annotation_id}_source.jpg"
    mask_path = root / f"{annotation_id}_mask.png"
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 12:36, 1] = 160 + index
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[8:24, 12:36] = 255
    Image.fromarray(image).save(image_path)
    Image.fromarray(mask).save(mask_path)
    return {
        "sample_id": f"manual_{annotation_id}_v2",
        "record_id": f"manual_{annotation_id}_v2",
        "annotation_id": annotation_id,
        "annotation_version": 2,
        "case_id": case_id,
        "patient_id": case_id,
        "group_id": case_id,
        "source_snapshot_path": str(image_path),
        "image_path": str(image_path),
        "local_path": str(image_path),
        "mask_path": str(mask_path),
        "label_path": str(mask_path),
        "source_checksum": sha256_file(image_path),
        "image_checksum": sha256_file(image_path),
        "checksum": sha256_file(image_path),
        "mask_checksum": sha256_file(mask_path),
        "label_checksum": sha256_file(mask_path),
        "label_type": "physician_mask",
        "mask_type": "lesion",
        "review_state": "accepted",
        "training_eligible": True,
        "sample_weight": 4.0,
        "sampling_weight": 4.0,
        "original_width": 48,
        "original_height": 32,
        "positive_pixel_count": 384,
        "positive_area_fraction": 0.25,
        "source_type": "case_jpeg",
        "source_id": f"case_jpeg:{case_id}",
        "source_url": "",
        "source_input_id": f"input-{index}",
        "source_run_id": "",
        "source_frame_index": "",
        "source_candidate_id": "",
        "source_video_path": "",
        "intake_authorization_status": "approved",
        "intake_usage_scope": "research_training",
        "intake_deidentification_confirmed": True,
        "intake_mapping_held_by_institution": True,
        "intake_admission_status": "target_registry_ready",
        "source_input_admission_status": "admitted",
        "source_input_batch_id": f"batch-{index}",
        "source_input_record_id": f"batch-{index}_0001",
        "source_input_checksum": sha256_file(image_path),
        "source_input_checksum_verified": True,
        "actor_id": f"doctor-{index}",
        "actor_role": "physician",
        "institution": "Example Stomatology Hospital",
        "auth_source": "verified_identity_token",
        "submitted_by_actor_id": f"doctor-{index}",
        "submitted_by_role": "physician",
        "submitted_by_institution": "Example Stomatology Hospital",
        "submitted_by_auth_source": "verified_identity_token",
        "reviewer_actor_id": f"reviewer-{index}",
        "reviewer_role": "physician",
        "reviewer_institution": "Example Stomatology Hospital",
        "reviewer_auth_source": "institution_sso",
        "reviewed_at": "2026-07-15T10:00:00+00:00",
        "input_domain": "physician_reviewed_case_annotation_domain_unconfirmed",
        "domain_tier": "case_annotation_domain_unconfirmed",
        "target_domain_flag": False,
        "artifact_role": MANUAL_ANNOTATION_ROLE,
        "usage_policy": "institution_authorized_training_use",
        "license": "authorized institutional research training",
        "medical_scene": "case annotation",
        "medical_boundary": "Physician-reviewed research-validation annotation.",
        "split": "",
        "exclusion_reason": "",
    }


def _write_manifest(root: Path, records: list[dict[str, object]]) -> Path:
    path = root / "manual_annotation_training_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-manual-annotation-training-manifest-v2",
                "created_at": "2026-07-15T10:00:00+00:00",
                "eligible_count": sum(bool(row.get("training_eligible")) for row in records),
                "excluded_count": sum(not bool(row.get("training_eligible")) for row in records),
                "records": records,
                "medical_boundary": "Physician review required.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
