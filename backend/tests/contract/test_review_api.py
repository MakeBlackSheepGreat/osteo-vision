from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from backend.osteo_vision_api.api.app import create_app
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import AnalysisRun, CandidateRegion, CaseRecord


def test_review_identity_defaults_to_engineering_reviewer(monkeypatch) -> None:
    monkeypatch.delenv("OSTEO_REVIEW_IDENTITIES_JSON", raising=False)
    response = TestClient(create_app()).get("/review-identity")

    assert response.status_code == 200
    assert response.json() == {
        "actor_id": "engineering-local-session",
        "role": "engineering_reviewer",
        "institution": "Osteo Vision Engineering",
        "auth_source": "local_unverified_session",
        "authenticated": False,
    }


def test_review_identity_uses_server_configured_bearer_token(monkeypatch) -> None:
    token = "physician-review-token-001"
    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps(
            {
                token: {
                    "actor_id": "doctor-zhang-001",
                    "role": "physician",
                    "institution": "Example Stomatology Hospital",
                    "auth_source": "verified_identity_token",
                }
            }
        ),
    )

    response = TestClient(create_app()).get(
        "/review-identity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["actor_id"] == "doctor-zhang-001"
    assert response.json()["role"] == "physician"
    assert response.json()["institution"] == "Example Stomatology Hospital"
    assert response.json()["auth_source"] == "verified_identity_token"
    assert response.json()["authenticated"] is True


def test_review_identity_rejects_unknown_or_untrusted_credentials(monkeypatch) -> None:
    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps(
            {
                "configured-token-0001": {
                    "actor_id": "project-reviewer-001",
                    "role": "project_reviewer",
                    "institution": "Osteo Vision Engineering",
                    "auth_source": "verified_identity_token",
                }
            }
        ),
    )
    client = TestClient(create_app())

    unknown = client.get("/review-identity", headers={"Authorization": "Bearer unknown-token-000000"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"]["code"] == "invalid_review_credentials"

    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps(
            {
                "unsafe-physician-token": {
                    "actor_id": "doctor-unverified",
                    "role": "physician",
                    "institution": "Unverified Hospital",
                    "auth_source": "local_unverified_session",
                }
            }
        ),
    )
    unsafe = client.get(
        "/review-identity",
        headers={"Authorization": "Bearer unsafe-physician-token"},
    )
    assert unsafe.status_code == 503
    assert unsafe.json()["detail"]["code"] == "review_identity_configuration_invalid"


def test_review_api_records_region_and_event(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "review"}).json()["case_id"]

    region = client.patch(
        f"/cases/{case_id}/regions/roi_1", json={"review_state": "accepted", "geometry": {"type": "box"}}
    )
    assert region.status_code == 200
    assert region.json()["rois"][0]["review_state"] == "accepted"

    event = client.post(
        f"/cases/{case_id}/review-events",
        json={"action": "accept", "target_id": "roi_1", "after_state": "accepted"},
    )
    assert event.status_code == 200
    recorded = event.json()["review_events"][-1]
    assert recorded["target_id"] == "roi_1"
    assert recorded["actor"] == "engineering-local-session"
    assert recorded["actor_id"] == "engineering-local-session"
    assert recorded["role"] == "engineering_reviewer"
    assert recorded["institution"] == "Osteo Vision Engineering"
    assert recorded["auth_source"] == "local_unverified_session"


def test_review_api_rejects_client_supplied_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    monkeypatch.delenv("OSTEO_REVIEW_IDENTITIES_JSON", raising=False)
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "review identity boundary"}).json()["case_id"]

    response = client.post(
        f"/cases/{case_id}/review-events",
        json={
            "action": "accept",
            "target_id": "roi_1",
            "actor_id": "self-claimed-doctor",
            "role": "physician",
            "institution": "Self Claimed Hospital",
            "auth_source": "verified_identity_token",
        },
    )

    assert response.status_code == 422


def test_review_api_returns_reason_code_when_prompt_fallback_is_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = tmp_path / "runtime.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "runtime_profile": "competition_safety_test",
                    "strict_startup": False,
                    "allow_prompt_fallback": False,
                    "use_fixture_model": False,
                    "models": [],
                }
            }
        ),
        encoding="utf-8",
    )
    case_store = tmp_path / "cases.json"
    monkeypatch.setenv("OSTEO_INFERENCE_CONFIG", str(config))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(case_store))
    source = tmp_path / "source.png"
    source.write_bytes(b"prompt adapter must remain closed")
    case = CaseRecord(
        case_id="case_prompt_disabled",
        title="prompt disabled",
        analysis_runs=[
            AnalysisRun(
                run_id="run_prompt_disabled",
                case_id="case_prompt_disabled",
                candidate_regions=[
                    CandidateRegion(
                        candidate_id="candidate_prompt_disabled",
                        run_id="run_prompt_disabled",
                        metadata={
                            "source_path": str(source),
                            "bbox_normalized": {
                                "type": "rect",
                                "coordinate_space": "normalized",
                                "x": 0.1,
                                "y": 0.1,
                                "width": 0.5,
                                "height": 0.5,
                            },
                        },
                    )
                ],
            )
        ],
    )
    JsonCaseRepository(case_store).create(case)
    client = TestClient(create_app())

    response = client.post(
        "/cases/case_prompt_disabled/candidate-regions/candidate_prompt_disabled/bone-gate-mask",
        json={"review_state": "review_required"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "prompt_fallback_disabled_by_runtime_policy"
    assert response.json()["detail"]["runtime_profile"] == "competition_safety_test"


def test_review_api_generates_prompt_assisted_bone_gate_mask(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "bone_gate_video.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (80, 60))
    for index in range(5):
        frame = np.full((60, 80, 3), 30 + index * 10, dtype=np.uint8)
        frame[18:42, 25:55, 1] = 255
        writer.write(frame)
    writer.release()
    case_id = client.post("/cases", json={"title": "bone gate"}).json()["case_id"]
    client.post(f"/cases/{case_id}/inputs", json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}])
    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 2}, "roi_hints": []},
    )
    assert analyzed.status_code == 200
    candidate = analyzed.json()["analysis_runs"][-1]["candidate_regions"][0]

    response = client.post(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask",
        json={"geometry": candidate["metadata"]["bbox_normalized"], "review_state": "review_required"},
    )

    assert response.status_code == 200
    payload = response.json()
    updated_candidate = payload["analysis_runs"][-1]["candidate_regions"][0]
    metadata = updated_candidate["metadata"]
    assert metadata["mask_type"] == "exposed_bone"
    assert metadata["label_source"] == "prompt_assisted_review"
    assert metadata["prompt_contract_fallback"] is True
    assert Path(metadata["bone_gate_mask_path"]).exists()
    assert Path(metadata["bone_gate_overlay_path"]).exists()
    assert metadata["video_signal_segmentation"]["bone_gate_mask"]["available"] is True
    assert metadata["video_signal_segmentation"]["bone_gate_mask"]["status"] == "prompt_assisted_review"
    assert payload["analysis_runs"][-1]["fused_outputs"]["video_segmentation_summary"]["bone_gate_frame_count"] == 1
    assert payload["review_events"][-1]["action"] == "bone_gate_mask_generated"
    assert payload["review_events"][-1]["role"] == "engineering_reviewer"

    repeated = client.post(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask",
        json={"geometry": candidate["metadata"]["bbox_normalized"], "review_state": "review_required"},
    )

    assert repeated.status_code == 200
    assert (
        repeated.json()["analysis_runs"][-1]["fused_outputs"]["video_segmentation_summary"]["bone_gate_frame_count"]
        == 1
    )


def test_review_api_saves_edited_bone_gate_mask_for_training_feedback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = tmp_path / "bone_gate_edit_video.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (80, 60))
    for index in range(5):
        frame = np.full((60, 80, 3), 25 + index * 15, dtype=np.uint8)
        frame[16:44, 20:58, 1] = 255
        writer.write(frame)
    writer.release()
    case_id = client.post("/cases", json={"title": "bone gate edit"}).json()["case_id"]
    client.post(f"/cases/{case_id}/inputs", json=[{"channel": "video", "path": str(source), "mime_type": "video/mp4"}])
    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"mode": "video_file", "keyframe_count": 2}, "roi_hints": []},
    )
    candidate = analyzed.json()["analysis_runs"][-1]["candidate_regions"][0]
    mask_array = np.zeros((24, 32), dtype=np.uint8)
    mask_array[4:18, 7:25] = 255
    buffer = BytesIO()
    Image.fromarray(mask_array).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    response = client.post(
        f"/cases/{case_id}/candidate-regions/{candidate['candidate_id']}/bone-gate-mask/edits",
        json={"mask_png_base64": encoded, "review_state": "modified", "reviewer_notes": "edited in mask editor"},
    )

    assert response.status_code == 200
    payload = response.json()
    metadata = payload["analysis_runs"][-1]["candidate_regions"][0]["metadata"]
    assert metadata["mask_type"] == "exposed_bone"
    assert metadata["label_source"] == "engineering_reviewer_modified_mask"
    assert metadata["prompt_source"] == "frontend_mask_editor"
    assert metadata["sample_weight"] == 4.0
    assert Path(metadata["bone_gate_mask_path"]).exists()
    assert Path(metadata["bone_gate_overlay_path"]).exists()
    assert metadata["video_signal_segmentation"]["bone_gate_mask"]["status"] == "engineering_reviewer_modified_mask"
    assert payload["review_events"][-1]["action"] == "bone_gate_mask_edited"
    assert payload["review_events"][-1]["role"] == "engineering_reviewer"
