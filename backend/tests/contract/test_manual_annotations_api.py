from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.src.api.app import create_app
from backend.src.domains.cases.enums import ReviewState
from backend.src.domains.cases.repository import SQLiteCaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseRecord


def _client(tmp_path: Path, monkeypatch, *, identities: dict | None = None) -> TestClient:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_ANNOTATION_STORE_PATH", str(tmp_path / "annotations.sqlite"))
    if identities is None:
        monkeypatch.delenv("OSTEO_REVIEW_IDENTITIES_JSON", raising=False)
    else:
        monkeypatch.setenv("OSTEO_REVIEW_IDENTITIES_JSON", json.dumps(identities))
    return TestClient(create_app())


def _case_with_jpeg(client: TestClient, tmp_path: Path, *, title: str = "manual annotation") -> tuple[str, str]:
    image_path = tmp_path / "source.jpg"
    image = np.full((60, 80, 3), 35, dtype=np.uint8)
    image[12:48, 20:65, 1] = 210
    Image.fromarray(image).save(image_path, quality=96)
    case_id = client.post("/cases", json={"title": title}).json()["case_id"]
    input_response = client.post(
        f"/cases/{case_id}/inputs",
        json=[{"channel": "white_light", "path": str(image_path), "mime_type": "image/jpeg"}],
    )
    assert input_response.status_code == 200
    return case_id, input_response.json()["inputs"][0]["input_id"]


def _training_admitted_case_with_jpeg(client: TestClient, tmp_path: Path) -> tuple[str, str]:
    image_path = tmp_path / "training_source.jpg"
    image = np.full((60, 80, 3), 35, dtype=np.uint8)
    image[12:48, 20:65, 1] = 210
    Image.fromarray(image).save(image_path, quality=96)
    uploaded = client.post(
        "/uploads/raw?keyframe_mode=none",
        content=image_path.read_bytes(),
        headers={"content-type": "image/jpeg", "x-filename": image_path.name},
    )
    assert uploaded.status_code == 200, uploaded.text
    upload_payload = uploaded.json()
    admitted = client.post(
        "/hospital-intake/batches",
        json={
            "batch_id": "batch-manual-training",
            "handover_id": "handover-manual-training",
            "source_organization": "Example Stomatology Hospital",
            "received_by": "project_receiver",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "authorization_status": "approved",
            "usage_scope": "research_training",
            "deidentification_confirmed": True,
            "deidentification_method": "institutional export review",
            "mapping_held_by_institution": True,
            "target_condition_confirmed": True,
            "files": [
                {
                    "external_case_id": "HOSP_CASE_MANUAL_TRAINING",
                    "path": upload_payload["path"],
                    "channel": "white_light",
                    "acquisition_mode": "white_light",
                    "channel_relationship": "single_channel",
                    "original_filename": upload_payload["original_filename"],
                }
            ],
        },
    )
    assert admitted.status_code == 200, admitted.text
    admission_payload = admitted.json()
    assert admission_payload["summary"]["admitted_count"] == 1
    case_id = admission_payload["records"][0]["platform_case_id"]
    case = client.get(f"/cases/{case_id}").json()
    return case_id, case["inputs"][0]["input_id"]


def _geometry(offset: int = 0) -> dict:
    return {
        "coordinate_space": "image_pixels",
        "operations": [
            {
                "tool": "polygon",
                "mode": "add",
                "points": [
                    {"x": 10 + offset, "y": 10},
                    {"x": 60, "y": 10},
                    {"x": 60, "y": 45},
                    {"x": 10 + offset, "y": 45},
                ],
            },
            {
                "tool": "eraser",
                "radius": 3,
                "points": [{"x": 30, "y": 24}, {"x": 40, "y": 24}],
            },
            {
                "tool": "brush",
                "radius": 2,
                "points": [{"x": 22, "y": 20}, {"x": 27, "y": 20}],
            },
        ],
    }


def _seed_ignore_candidate_case(tmp_path: Path) -> tuple[str, Path]:
    case_id = "case-ignore-api"
    source_path = tmp_path / "ignore_candidate.png"
    gate_path = tmp_path / "ignore_gate.png"
    probability_path = tmp_path / "ignore_probability.png"
    Image.fromarray(np.full((60, 80, 3), 120, dtype=np.uint8)).save(source_path)
    Image.fromarray(np.full((60, 80), 255, dtype=np.uint8)).save(gate_path)
    Image.fromarray(np.tile(np.arange(80, dtype=np.uint8), (60, 1)) * 3).save(probability_path)
    signal_masks = {
        "schema_version": "osteo-vision-video-signal-masks-v2",
        "bone_gate_mask": {
            "available": True,
            "path": str(gate_path),
            "review_state": "accepted",
            "status": "physician_accepted",
        },
        "fluorescence_signal_mask": {
            "available": True,
            "probability_path": str(probability_path),
            "threshold": 0.5,
        },
    }
    manifest_path = tmp_path / "ignore_video_segmentation_manifest.json"
    manifest_path.write_text(
        json.dumps({"frames": [{"frame_index": 5, "video_signal_segmentation": signal_masks}], "summary": {}}),
        encoding="utf-8",
    )
    candidate = CandidateRegion(
        candidate_id="candidate-ignore-api",
        run_id="run-ignore-api",
        risk_type="boundary_risk",
        status=ReviewState.ACCEPTED,
        metadata={
            "source_path": str(source_path),
            "frame_index": 5,
            "frame_order": 1,
            "image_width": 80,
            "image_height": 60,
            "video_signal_segmentation": signal_masks,
            "signal_masks": signal_masks,
        },
    )
    run = AnalysisRun(
        run_id="run-ignore-api",
        case_id=case_id,
        status="completed",
        candidate_regions=[candidate],
        fused_outputs={
            "frame_details": [
                {
                    "frame_index": 5,
                    "frame_order": 1,
                    "evidence_path": str(source_path),
                    "video_signal_segmentation": signal_masks,
                }
            ],
            "video_segmentation_manifest_path": str(manifest_path),
        },
    )
    now = datetime.now(timezone.utc)
    SQLiteCaseRepository(tmp_path / "cases.sqlite").create(
        CaseRecord(
            case_id=case_id,
            title="API physician ignore synchronization",
            created_at=now,
            updated_at=now,
            analysis_runs=[run],
        )
    )
    return case_id, manifest_path


def _create_annotation(
    client: TestClient,
    case_id: str,
    input_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(
        f"/cases/{case_id}/annotations",
        headers=headers,
        json={
            "source": {"source_type": "case_jpeg", "input_id": input_id},
            "label": "lesion",
            "geometry": _geometry(),
            "notes": "initial physician contour",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_manual_annotation_source_create_version_history_and_delete(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id, input_id = _case_with_jpeg(client, tmp_path)

    sources = client.get(f"/cases/{case_id}/annotation-sources")
    assert sources.status_code == 200
    source = sources.json()["sources"][0]
    assert source["source_type"] == "case_jpeg"
    assert source["original_width"] == 80
    assert source["original_height"] == 60
    preview = client.get("/files/preview", params={"path": source["preview_path"]})
    assert preview.status_code == 200

    created = _create_annotation(client, case_id, input_id)
    assert [item["tool"] for item in created["geometry"]["operations"]] == ["polygon", "eraser", "brush"]
    assert created["geometry"]["operations"][0]["points"][0] == {"x": 10.0, "y": 10.0}
    assert created["status"] == "draft"
    assert created["current_version"] == 1
    assert created["training_eligible"] is False
    with Image.open(created["mask_path"]) as mask:
        assert mask.size == (80, 60)
        assert np.count_nonzero(np.asarray(mask)) == created["positive_pixel_count"]
    assert client.get("/files/preview", params={"path": created["source_snapshot_path"]}).status_code == 200
    assert client.get("/files/preview", params={"path": created["mask_path"]}).status_code == 200

    saved = client.put(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/versions",
        json={"expected_version": 1, "geometry": _geometry(offset=5), "notes": "boundary refined"},
    )
    assert saved.status_code == 200
    updated = saved.json()
    assert updated["current_version"] == 2
    assert updated["geometry"]["operations"][0]["points"][0] == {"x": 15.0, "y": 10.0}
    assert updated["mask_path"] != created["mask_path"]

    history = client.get(f"/cases/{case_id}/annotations/{created['annotation_id']}/versions")
    assert history.status_code == 200
    assert [item["version"] for item in history.json()["versions"]] == [1, 2]
    assert history.json()["versions"][0]["geometry"]["operations"][0]["points"][0]["x"] == 10.0
    assert history.json()["versions"][1]["geometry"]["operations"][0]["points"][0]["x"] == 15.0

    stale = client.put(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/versions",
        json={"expected_version": 1, "geometry": _geometry()},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "annotation_version_conflict"

    deleted = client.delete(f"/cases/{case_id}/annotations/{created['annotation_id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "annotation_id": created["annotation_id"]}
    assert client.get(f"/cases/{case_id}/annotations/{created['annotation_id']}").status_code == 404


def test_trusted_physician_annotation_review_and_training_manifest(tmp_path, monkeypatch) -> None:
    author_token = "physician-annotation-token-001"
    reviewer_token = "physician-review-token-001"
    identities = {
        author_token: {
            "actor_id": "doctor-li-001",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        },
        reviewer_token: {
            "actor_id": "doctor-chen-002",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "institution_sso",
        },
    }
    client = _client(tmp_path, monkeypatch, identities=identities)
    author_headers = {"Authorization": f"Bearer {author_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
    case_id, input_id = _training_admitted_case_with_jpeg(client, tmp_path)
    created = _create_annotation(client, case_id, input_id, headers=author_headers)

    submitted = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/submit",
        headers=author_headers,
        json={"expected_version": 1, "notes": "ready for physician review"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_by"]["actor_id"] == "doctor-li-001"

    reviewed = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/review",
        headers=reviewer_headers,
        json={"expected_version": 1, "decision": "accepted", "notes": "contour accepted"},
    )
    assert reviewed.status_code == 200
    accepted = reviewed.json()
    assert accepted["status"] == "accepted"
    assert accepted["training_eligible"] is True
    assert accepted["sample_weight"] == 4.0
    assert accepted["reviewed_by"]["actor_id"] == "doctor-chen-002"
    assert accepted["training_exclusion_reason"] is None

    manifest = client.post(
        "/annotation-training-manifests",
        headers=reviewer_headers,
        json={"case_ids": [case_id], "include_ineligible": False},
    )
    assert manifest.status_code == 201
    payload = manifest.json()
    assert payload["eligible_count"] == 1
    assert payload["excluded_count"] == 0
    assert Path(payload["json_path"]).is_file()
    assert Path(payload["csv_path"]).is_file()
    row = payload["records"][0]
    assert row["annotation_id"] == created["annotation_id"]
    assert row["label_type"] == "physician_mask"
    assert row["training_eligible"] is True
    assert row["sample_weight"] == 4.0
    assert Path(row["image_path"]).is_file()
    assert Path(row["mask_path"]).is_file()
    assert row["source_snapshot_path"] == row["image_path"]
    assert row["source_checksum"] == row["image_checksum"]
    assert row["mask_checksum"] == row["label_checksum"]
    assert row["reviewer_role"] == "physician"
    assert row["reviewer_auth_source"] == "institution_sso"
    assert row["submitted_by_actor_id"] == "doctor-li-001"
    assert row["reviewer_actor_id"] == "doctor-chen-002"


def test_same_physician_review_is_retained_but_excluded_from_training(tmp_path, monkeypatch) -> None:
    token = "same-physician-review-token"
    identities = {
        token: {
            "actor_id": "doctor-same-001",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        }
    }
    client = _client(tmp_path, monkeypatch, identities=identities)
    headers = {"Authorization": f"Bearer {token}"}
    case_id, input_id = _case_with_jpeg(client, tmp_path, title="same physician review gate")
    created = _create_annotation(client, case_id, input_id, headers=headers)
    submitted = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/submit",
        headers=headers,
        json={"expected_version": 1},
    )
    assert submitted.status_code == 200

    reviewed = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/review",
        headers=headers,
        json={"expected_version": 1, "decision": "accepted", "notes": "engineering review record"},
    )
    assert reviewed.status_code == 200
    record = reviewed.json()
    assert record["status"] == "accepted"
    assert record["reviewed_by"]["actor_id"] == "doctor-same-001"
    assert record["training_eligible"] is False
    assert record["sample_weight"] == 0.0
    assert record["training_exclusion_reason"] == "independent_physician_review_required"

    manifest = client.post(
        "/annotation-training-manifests",
        headers=headers,
        json={"case_ids": [case_id], "include_ineligible": True},
    )
    assert manifest.status_code == 201
    payload = manifest.json()
    assert payload["eligible_count"] == 0
    assert payload["excluded_count"] == 1
    row = payload["records"][0]
    assert row["training_eligible"] is False
    assert row["sample_weight"] == 0.0
    assert "independent_physician_review_required" in row["exclusion_reason"]


def test_engineering_annotation_cannot_enter_training_after_physician_acceptance(tmp_path, monkeypatch) -> None:
    token = "physician-review-token-002"
    identities = {
        token: {
            "actor_id": "doctor-wang-002",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "institution_sso",
        }
    }
    client = _client(tmp_path, monkeypatch, identities=identities)
    case_id, input_id = _case_with_jpeg(client, tmp_path, title="engineering annotation boundary")
    created = _create_annotation(client, case_id, input_id)
    submitted = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/submit",
        json={"expected_version": 1},
    )
    assert submitted.status_code == 200

    denied = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/review",
        json={"expected_version": 1, "decision": "accepted"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "annotation_permission_denied"

    accepted = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"expected_version": 1, "decision": "accepted"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["training_eligible"] is False
    assert accepted.json()["sample_weight"] == 0.0

    audit_manifest = client.post(
        "/annotation-training-manifests",
        headers={"Authorization": f"Bearer {token}"},
        json={"case_ids": [case_id], "include_ineligible": True},
    ).json()
    assert audit_manifest["eligible_count"] == 0
    assert audit_manifest["excluded_count"] == 1
    assert audit_manifest["records"][0]["training_eligible"] is False
    assert "annotation_not_training_eligible" in audit_manifest["records"][0]["exclusion_reason"]


def test_reviewed_model_candidate_ignore_annotation_immediately_updates_case_and_manifest(
    tmp_path, monkeypatch
) -> None:
    author_token = "physician-ignore-token-003"
    reviewer_token = "physician-ignore-review-token-004"
    identities = {
        author_token: {
            "actor_id": "doctor-ignore-003",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        },
        reviewer_token: {
            "actor_id": "doctor-ignore-reviewer-004",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "institution_sso",
        },
    }
    client = _client(tmp_path, monkeypatch, identities=identities)
    author_headers = {"Authorization": f"Bearer {author_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
    case_id, manifest_path = _seed_ignore_candidate_case(tmp_path)

    created_response = client.post(
        f"/cases/{case_id}/annotations",
        headers=author_headers,
        json={
            "source": {
                "source_type": "model_candidate",
                "run_id": "run-ignore-api",
                "candidate_id": "candidate-ignore-api",
            },
            "label": "ignore",
            "geometry": _geometry(),
            "notes": "unable to assess due to occlusion",
        },
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    submitted = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/submit",
        headers=author_headers,
        json={"expected_version": 1},
    )
    assert submitted.status_code == 200
    before_review = client.get(f"/cases/{case_id}").json()
    before_signal = before_review["analysis_runs"][0]["candidate_regions"][0]["metadata"]["video_signal_segmentation"]
    assert "physician_ignore_mask" not in before_signal

    reviewed = client.post(
        f"/cases/{case_id}/annotations/{created['annotation_id']}/review",
        headers=reviewer_headers,
        json={"expected_version": 1, "decision": "modified", "notes": "ignore region verified"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "modified"
    assert reviewed.json()["training_eligible"] is False
    assert reviewed.json()["training_exclusion_reason"] == "case_intake_metadata_missing"

    case = client.get(f"/cases/{case_id}").json()
    candidate = case["analysis_runs"][0]["candidate_regions"][0]
    signal_masks = candidate["metadata"]["video_signal_segmentation"]
    assert candidate["metadata"]["physician_ignore_sync_status"] == "applied"
    assert signal_masks["schema_version"] == "osteo-vision-video-signal-masks-v2"
    assert signal_masks["physician_ignore_mask"]["annotation_count"] == 1
    provenance = signal_masks["physician_ignore_mask"]["annotations"][0]
    assert provenance["annotation_id"] == created["annotation_id"]
    assert provenance["version"] == 1
    assert provenance["path"] == created["mask_path"]
    assert provenance["sha256"] == created["mask_checksum"]
    assert provenance["reviewer"]["actor_id"] == "doctor-ignore-reviewer-004"
    spectrum = signal_masks["bone_activity_spectrum"]
    assert spectrum["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert spectrum["available"] is True
    assert spectrum["partition_check"]["valid"] is True
    assert spectrum["partition_check"]["classified_px"] + spectrum["partition_check"]["ignore_px"] == 4800
    assert case["review_events"][-1]["action"] == "physician_ignore_annotations_synchronized"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_signal = manifest["frames"][0]["video_signal_segmentation"]
    assert manifest_signal["physician_ignore_mask"]["sha256"] == signal_masks["physician_ignore_mask"]["sha256"]
    artifact_paths = {str(Path(item["path"]).resolve()) for item in case["artifacts"]}
    assert str(Path(created["mask_path"]).resolve()) in artifact_paths
    assert str(Path(spectrum["ignore_region"]["path"]).resolve()) in artifact_paths
