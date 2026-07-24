from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from backend.osteo_vision_api.domains.cases.enums import ReviewerRole
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.review_service import (
    _activity_spectrum_artifacts,
    _derive_reviewed_activity_spectrum,
)


def _actor(role: ReviewerRole) -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id=f"test-{role.value}",
        role=role,
        institution="Test Hospital",
        auth_source="institution_sso" if role == ReviewerRole.PHYSICIAN else "signed_session",
    )


def _signal_masks(
    tmp_path: Path,
    *,
    empty_gate: bool = False,
    uncertain: np.ndarray | None = None,
) -> dict[str, object]:
    probability = np.array([[0, 60, 150, 255], [0, 60, 150, 255]], dtype=np.uint8)
    gate = np.zeros((2, 4), dtype=np.uint8) if empty_gate else np.full((2, 4), 255, dtype=np.uint8)
    probability_path = tmp_path / "probability.png"
    gate_path = tmp_path / "bone_gate.png"
    Image.fromarray(probability).save(probability_path)
    Image.fromarray(gate).save(gate_path)
    result: dict[str, object] = {
        "bone_gate_mask": {"available": True, "path": str(gate_path)},
        "fluorescence_signal_mask": {
            "available": True,
            "probability_path": str(probability_path),
            "threshold": 0.5,
        },
    }
    if uncertain is not None:
        uncertain_path = tmp_path / "uncertain.png"
        Image.fromarray(np.asarray(uncertain, dtype=np.uint8)).save(uncertain_path)
        result["uncertain_mask"] = {
            "available": True,
            "path": str(uncertain_path),
            "sha256": hashlib.sha256(uncertain_path.read_bytes()).hexdigest(),
        }
    return result


def test_physician_modified_gate_materializes_activity_masks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    result = _derive_reviewed_activity_spectrum(
        signal_masks=_signal_masks(tmp_path),
        actor=_actor(ReviewerRole.PHYSICIAN),
        review_state="modified",
        case_id="case-1",
        candidate_id="candidate-1",
    )
    spectrum = result["bone_activity_spectrum"]
    assert spectrum["available"] is True
    assert spectrum["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert spectrum["spatial_effect_applied"] is True
    assert Path(spectrum["activity_class_map_path"]).exists()
    assert spectrum["low_activity_candidate"]["positive_area_px"] == 4
    assert spectrum["transition_candidate"]["positive_area_px"] == 0
    assert spectrum["high_activity_candidate"]["positive_area_px"] == 4
    assert spectrum["ignore_region"]["positive_area_px"] == 0
    assert spectrum["ignore_region"]["bone_gate_fraction"] == 0.0
    assert spectrum["ignore_region"]["sources"][0]["source_type"] == "compatibility_default_empty"
    assert Path(spectrum["ignore_region"]["path"]).is_file()
    assert len(spectrum["ignore_region"]["sha256"]) == 64
    assert spectrum["partition_check"] == {
        "valid": True,
        "reviewed_bone_px": 8,
        "classified_px": 8,
        "ignore_px": 0,
        "union_px": 8,
        "overlap_px": 0,
        "outside_gate_px": 0,
        "uncovered_gate_px": 0,
    }
    artifacts = _activity_spectrum_artifacts("case-1", "run-1", result)
    artifact_paths = {Path(item.path) for item in artifacts}
    assert Path(spectrum["ignore_region"]["path"]) in artifact_paths
    ignore_artifact = next(item for item in artifacts if Path(item.path) == Path(spectrum["ignore_region"]["path"]))
    assert ignore_artifact.checksum == spectrum["ignore_region"]["sha256"]
    for key in ("low_activity_candidate", "transition_candidate", "high_activity_candidate"):
        assert Path(spectrum[key]["path"]).exists()


def test_project_and_engineering_reviewers_cannot_unlock_activity_masks(tmp_path: Path) -> None:
    for role in (ReviewerRole.PROJECT_REVIEWER, ReviewerRole.ENGINEERING_REVIEWER):
        result = _derive_reviewed_activity_spectrum(
            signal_masks=_signal_masks(tmp_path),
            actor=_actor(role),
            review_state="accepted",
            case_id="case-1",
            candidate_id=role.value,
        )
        assert result["bone_activity_spectrum"]["available"] is False
        assert result["bone_activity_spectrum"]["status"] == "pending_trusted_reviewed_bone_gate"


def test_empty_gate_and_missing_probability_remain_unavailable(tmp_path: Path) -> None:
    empty = _derive_reviewed_activity_spectrum(
        signal_masks=_signal_masks(tmp_path, empty_gate=True),
        actor=_actor(ReviewerRole.PHYSICIAN),
        review_state="accepted",
        case_id="case-1",
        candidate_id="empty",
    )
    assert empty["bone_activity_spectrum"]["status"] == "empty_reviewed_bone_gate"
    missing = _signal_masks(tmp_path)
    missing["fluorescence_signal_mask"]["probability_path"] = str(tmp_path / "missing.png")
    result = _derive_reviewed_activity_spectrum(
        signal_masks=missing,
        actor=_actor(ReviewerRole.PHYSICIAN),
        review_state="accepted",
        case_id="case-1",
        candidate_id="missing",
    )
    assert result["bone_activity_spectrum"]["status"] == "pending_probability_map"


def test_uncertain_and_physician_ignore_masks_are_unioned_and_excluded_from_three_classes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    signal_masks = _signal_masks(
        tmp_path,
        uncertain=np.array([[0, 255, 0, 0], [0, 0, 255, 0]], dtype=np.uint8),
    )
    physician_ignore_path = tmp_path / "physician_ignore.png"
    Image.fromarray(np.array([[0, 0, 0, 255], [0, 0, 0, 0]], dtype=np.uint8)).save(physician_ignore_path)
    signal_masks["physician_ignore_mask"] = {
        "available": True,
        "path": str(physician_ignore_path),
        "review_state": "accepted",
        "label_source": "physician",
    }

    result = _derive_reviewed_activity_spectrum(
        signal_masks=signal_masks,
        actor=_actor(ReviewerRole.PHYSICIAN),
        review_state="accepted",
        case_id="case-ignore",
        candidate_id="candidate-ignore",
    )

    spectrum = result["bone_activity_spectrum"]
    assert spectrum["available"] is True
    assert spectrum["ignore_region"]["positive_area_px"] == 3
    assert spectrum["ignore_region"]["bone_gate_fraction"] == 3 / 8
    assert {item["source_type"] for item in spectrum["ignore_region"]["sources"]} == {
        "physician_ignore_mask",
        "uncertain_mask",
    }
    assert spectrum["low_activity_candidate"]["positive_area_px"] == 3
    assert spectrum["transition_candidate"]["positive_area_px"] == 0
    assert spectrum["high_activity_candidate"]["positive_area_px"] == 2
    assert spectrum["partition_check"]["valid"] is True
    assert spectrum["partition_check"]["classified_px"] + spectrum["partition_check"]["ignore_px"] == 8
    with Image.open(spectrum["activity_class_map_path"]) as image:
        values = set(np.unique(np.asarray(image, dtype=np.uint8)))
    assert values == {1, 3, 4}


def test_invalid_ignore_evidence_fails_closed_without_stale_spatial_outputs(tmp_path: Path) -> None:
    cases = (
        ("ignore_mask_source_missing", {"available": True, "path": str(tmp_path / "missing.png")}),
        ("ignore_mask_size_mismatch", None),
        ("ignore_mask_invalid", None),
        ("ignore_mask_checksum_mismatch", None),
    )
    size_mismatch = tmp_path / "size_mismatch.png"
    Image.fromarray(np.zeros((1, 1), dtype=np.uint8)).save(size_mismatch)
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not-an-image")
    checksum_mismatch = tmp_path / "checksum_mismatch.png"
    Image.fromarray(np.zeros((2, 4), dtype=np.uint8)).save(checksum_mismatch)
    records = {
        "ignore_mask_size_mismatch": {"available": True, "path": str(size_mismatch)},
        "ignore_mask_invalid": {"available": True, "path": str(invalid)},
        "ignore_mask_checksum_mismatch": {
            "available": True,
            "path": str(checksum_mismatch),
            "sha256": "0" * 64,
        },
    }

    for expected_status, record in cases:
        signal_masks = _signal_masks(tmp_path)
        signal_masks["uncertain_mask"] = record or records[expected_status]
        signal_masks["bone_activity_spectrum"] = {
            "available": True,
            "activity_class_map_path": "stale.png",
            "low_activity_candidate": {"available": True, "path": "stale-low.png"},
            "ignore_region": {"available": True, "path": "stale-ignore.png", "sha256": "stale"},
        }
        result = _derive_reviewed_activity_spectrum(
            signal_masks=signal_masks,
            actor=_actor(ReviewerRole.PHYSICIAN),
            review_state="accepted",
            case_id="case-invalid",
            candidate_id=expected_status,
        )
        spectrum = result["bone_activity_spectrum"]
        assert spectrum["available"] is False
        assert spectrum["status"] == expected_status
        assert spectrum["spatial_effect_applied"] is False
        assert spectrum["activity_class_map_path"] is None
        assert spectrum["low_activity_candidate"]["path"] is None
        assert spectrum["ignore_region"]["path"] is None
        assert spectrum["ignore_region"]["sha256"] is None
        assert spectrum["partition_check"]["valid"] is False
