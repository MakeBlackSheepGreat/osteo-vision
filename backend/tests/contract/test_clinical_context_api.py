from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app


def _client(tmp_path: Path, monkeypatch, *, identities: dict | None = None) -> TestClient:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    if identities is None:
        monkeypatch.delenv("OSTEO_REVIEW_IDENTITIES_JSON", raising=False)
    else:
        monkeypatch.setenv("OSTEO_REVIEW_IDENTITIES_JSON", json.dumps(identities))
    return TestClient(create_app())


def _context_payload(*, review_status: str = "review_required", age_years: int = 68) -> dict:
    return {
        "age_years": age_years,
        "age_group": "young_adult",
        "sex_at_birth": "female",
        "comorbidities": ["type_2_diabetes"],
        "comorbidities_reviewed": True,
        "medications": [],
        "medications_reviewed": True,
        "labs": [
            {
                "name": "CRP",
                "value": 18.2,
                "unit": "mg/L",
                "abnormal_flag": "high",
            }
        ],
        "source_organization": "deidentified_test_hospital",
        "recorded_by": "reviewer-1",
        "review_status": review_status,
        "deidentified": True,
    }


def test_clinical_context_is_derived_persisted_and_snapshotted(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "clinical context"}).json()["case_id"]

    response = client.put(
        f"/cases/{case_id}/clinical-context",
        json=_context_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["clinical_context"]["age_group"] == "older_adult"
    assert payload["clinical_context"]["verified_by"] is None
    assert payload["clinical_context"]["verified_at"] is None
    assert payload["clinical_context"]["comorbidities_reviewed"] is True
    assert payload["clinical_context"]["medications_reviewed"] is True
    assert (
        payload["clinical_context"]["clinical_use_boundary"]
        == "risk_prior_and_calibration_only_no_spatial_boundary_effect"
    )
    assert client.get(f"/cases/{case_id}").json()["clinical_context"] == payload["clinical_context"]

    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()
    client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )
    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6}, "roi_hints": []},
    )

    assert analyzed.status_code == 200
    parameters = analyzed.json()["analysis_runs"][-1]["parameters"]
    assert parameters["clinical_context_snapshot"]["age_group"] == "older_adult"
    assert parameters["contextual_risk_prior"]["recorded_factor_count"] == 1
    assert parameters["contextual_risk_prior"]["probability"] is None
    assert parameters["clinical_context_quality"]["issues"] == ["lab_timestamp_missing"]
    assert parameters["clinical_feature_vector"]["feature_version"] == "clinical-feature-vector-v1"
    assert len(parameters["clinical_context_checksum"]) == 64
    assert parameters["calibration_evidence"]["applied"] is False
    assert parameters["calibration_status"] == "pending_target_domain_validation"
    assert parameters["spatial_effect_applied"] is False


def test_clinical_context_rejects_unrecognized_fields(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "invalid context"}).json()["case_id"]

    response = client.put(
        f"/cases/{case_id}/clinical-context",
        json={"age_years": 42, "patient_name": "must-not-be-stored"},
    )

    assert response.status_code == 422


def test_unverified_session_cannot_mark_clinical_context_verified(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "verification gate"}).json()["case_id"]
    saved = client.put(
        f"/cases/{case_id}/clinical-context",
        json=_context_payload(review_status="review_required", age_years=68),
    )
    assert saved.status_code == 200

    denied = client.put(
        f"/cases/{case_id}/clinical-context",
        json=_context_payload(review_status="verified", age_years=41),
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "clinical_context_verification_forbidden"
    persisted = client.get(f"/cases/{case_id}").json()["clinical_context"]
    assert persisted["review_status"] == "review_required"
    assert persisted["age_years"] == 68
    assert persisted["verified_by"] is None
    assert persisted["verified_at"] is None


def test_trusted_review_token_can_verify_clinical_context_with_audit_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    token = "clinical-context-physician-token-001"
    identities = {
        token: {
            "actor_id": "doctor-chen-001",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        }
    }
    client = _client(tmp_path, monkeypatch, identities=identities)
    case_id = client.post("/cases", json={"title": "verified context"}).json()["case_id"]

    response = client.put(
        f"/cases/{case_id}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json=_context_payload(review_status="verified"),
    )

    assert response.status_code == 200
    context = response.json()["clinical_context"]
    assert context["review_status"] == "verified"
    assert context["verified_by"] == identities[token]
    assert datetime.fromisoformat(context["verified_at"]).tzinfo is not None
    assert client.get(f"/cases/{case_id}").json()["clinical_context"] == context


def test_authenticated_engineering_identity_cannot_verify_clinical_context(tmp_path: Path, monkeypatch) -> None:
    token = "clinical-context-engineer-token-001"
    client = _client(
        tmp_path,
        monkeypatch,
        identities={
            token: {
                "actor_id": "engineer-001",
                "role": "engineering_reviewer",
                "institution": "Osteo Vision Engineering",
                "auth_source": "signed_session",
            }
        },
    )
    case_id = client.post("/cases", json={"title": "engineering verification denied"}).json()["case_id"]

    response = client.put(
        f"/cases/{case_id}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json=_context_payload(review_status="verified"),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "clinical_context_verification_forbidden"


def test_trusted_project_reviewer_can_verify_and_later_edit_requires_review_again(tmp_path: Path, monkeypatch) -> None:
    token = "clinical-context-project-review-token-001"
    reviewer = {
        "actor_id": "project-reviewer-001",
        "role": "project_reviewer",
        "institution": "Osteo Vision Review Board",
        "auth_source": "signed_session",
    }
    client = _client(tmp_path, monkeypatch, identities={token: reviewer})
    case_id = client.post("/cases", json={"title": "project reviewer verification"}).json()["case_id"]
    verified = client.put(
        f"/cases/{case_id}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json=_context_payload(review_status="verified"),
    )
    assert verified.status_code == 200
    assert verified.json()["clinical_context"]["verified_by"] == reviewer

    edited = client.put(
        f"/cases/{case_id}/clinical-context",
        json=_context_payload(review_status="review_required", age_years=69),
    )

    assert edited.status_code == 200
    context = edited.json()["clinical_context"]
    assert context["review_status"] == "review_required"
    assert context["verified_by"] is None
    assert context["verified_at"] is None


def test_client_cannot_spoof_clinical_context_verification_audit(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    case_id = client.post("/cases", json={"title": "audit spoof denied"}).json()["case_id"]
    payload = _context_payload()
    payload["verified_by"] = {
        "actor_id": "spoofed-doctor",
        "role": "physician",
        "institution": "Spoofed Hospital",
        "auth_source": "verified_identity_token",
    }
    payload["verified_at"] = "2026-07-18T08:00:00Z"

    response = client.put(f"/cases/{case_id}/clinical-context", json=payload)

    assert response.status_code == 200
    context = response.json()["clinical_context"]
    assert context["review_status"] == "review_required"
    assert context["verified_by"] is None
    assert context["verified_at"] is None
