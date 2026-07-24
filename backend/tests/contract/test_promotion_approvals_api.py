from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app
from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    TrustedPromotionKey,
    public_key_pem,
    sign_approval_payload,
)

PHYSICIAN_TOKEN = "promotion-physician-token-0001"
PROJECT_REVIEWER_TOKEN = "promotion-project-review-token-0001"
PHYSICIAN_IDENTITY = {
    "actor_id": "doctor-promotion-001",
    "role": "physician",
    "institution": "Mianyang Third People's Hospital",
    "auth_source": "verified_identity_token",
}
PROJECT_REVIEWER_IDENTITY = {
    "actor_id": "safety-owner-001",
    "role": "project_reviewer",
    "institution": "Osteo Vision Project",
    "auth_source": "signed_session",
}
TARGET = {
    "capability": "patient_conditioned_segmentation",
    "model_id": "patient-conditioned-target-v1",
    "checkpoint_sha256": "1" * 64,
    "policy_sha256": "2" * 64,
    "evidence_bundle_sha256": "3" * 64,
}


def _client(
    tmp_path: Path,
    monkeypatch,
) -> tuple[TestClient, dict[str, Ed25519PrivateKey]]:
    now = datetime.now(timezone.utc)
    private_keys = {
        "physician-key-001": Ed25519PrivateKey.generate(),
        "project-reviewer-key-001": Ed25519PrivateKey.generate(),
    }
    trust_store = PromotionTrustStore(
        keys=[
            _trusted_key(
                private_keys["physician-key-001"],
                key_id="physician-key-001",
                identity=PHYSICIAN_IDENTITY,
                now=now,
            ),
            _trusted_key(
                private_keys["project-reviewer-key-001"],
                key_id="project-reviewer-key-001",
                identity=PROJECT_REVIEWER_IDENTITY,
                now=now,
            ),
        ]
    )
    trusted_keys_path = tmp_path / "promotion_trusted_keys.json"
    trusted_keys_path.write_text(
        json.dumps(trust_store.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.sqlite"))
    monkeypatch.setenv("OSTEO_ANNOTATION_STORE_PATH", str(tmp_path / "annotations.sqlite"))
    monkeypatch.setenv("OSTEO_JOB_STORE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("OSTEO_PROMOTION_APPROVAL_STORE_PATH", str(tmp_path / "promotion_approvals.sqlite"))
    monkeypatch.setenv("OSTEO_PROMOTION_TRUSTED_KEYS_PATH", str(trusted_keys_path))
    monkeypatch.setenv(
        "OSTEO_REVIEW_IDENTITIES_JSON",
        json.dumps(
            {
                PHYSICIAN_TOKEN: PHYSICIAN_IDENTITY,
                PROJECT_REVIEWER_TOKEN: PROJECT_REVIEWER_IDENTITY,
            }
        ),
    )
    return TestClient(create_app()), private_keys


def _trusted_key(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
    identity: dict[str, str],
    now: datetime,
) -> TrustedPromotionKey:
    return TrustedPromotionKey(
        key_id=key_id,
        public_key_pem=public_key_pem(private_key.public_key()),
        actor_id=identity["actor_id"],
        role=identity["role"],
        institution=identity["institution"],
        valid_from_utc=now - timedelta(days=1),
        valid_until_utc=now + timedelta(days=30),
        allowed_capabilities=["patient_conditioned_segmentation"],
    )


def _submission(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
    identity: dict[str, str],
    approval_id: str,
    nonce: str,
    decision: str = "approve",
    supersedes_approval_id: str | None = None,
) -> dict[str, Any]:
    payload = PromotionApprovalPayload(
        **TARGET,
        approval_id=approval_id,
        decision=decision,
        signer_actor_id=identity["actor_id"],
        signer_role=identity["role"],
        signer_institution=identity["institution"],
        signed_at_utc=datetime.now(timezone.utc),
        nonce=nonce,
        supersedes_approval_id=supersedes_approval_id,
    )
    submission = SignedPromotionApproval(
        payload=payload,
        key_id=key_id,
        signature_b64=sign_approval_payload(payload, private_key),
    )
    return submission.model_dump(mode="json")


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_model_promotion_approval_rejects_unauthenticated_session(tmp_path: Path, monkeypatch) -> None:
    client, private_keys = _client(tmp_path, monkeypatch)
    submission = _submission(
        private_keys["physician-key-001"],
        key_id="physician-key-001",
        identity=PHYSICIAN_IDENTITY,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )

    response = client.post("/model-promotion/approvals", json=submission)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "promotion_approval_authenticated_identity_untrusted"


def test_model_promotion_approval_rejects_authenticated_identity_mismatch(tmp_path: Path, monkeypatch) -> None:
    client, private_keys = _client(tmp_path, monkeypatch)
    submission = _submission(
        private_keys["physician-key-001"],
        key_id="physician-key-001",
        identity=PHYSICIAN_IDENTITY,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )

    response = client.post(
        "/model-promotion/approvals",
        json=submission,
        headers=_authorization(PROJECT_REVIEWER_TOKEN),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "promotion_approval_authenticated_identity_mismatch"


def test_model_promotion_approval_rejects_replayed_id_and_nonce(tmp_path: Path, monkeypatch) -> None:
    client, private_keys = _client(tmp_path, monkeypatch)
    submission = _submission(
        private_keys["physician-key-001"],
        key_id="physician-key-001",
        identity=PHYSICIAN_IDENTITY,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )

    accepted = client.post(
        "/model-promotion/approvals",
        json=submission,
        headers=_authorization(PHYSICIAN_TOKEN),
    )
    replayed = client.post(
        "/model-promotion/approvals",
        json=submission,
        headers=_authorization(PHYSICIAN_TOKEN),
    )
    role_conflict = client.post(
        "/model-promotion/approvals",
        json=_submission(
            private_keys["physician-key-001"],
            key_id="physician-key-001",
            identity=PHYSICIAN_IDENTITY,
            approval_id="approval-physician-0002",
            nonce="nonce-physician-000000000002",
        ),
        headers=_authorization(PHYSICIAN_TOKEN),
    )

    assert accepted.status_code == 201
    assert replayed.status_code == 409
    assert replayed.json()["detail"]["code"] == "promotion_approval_replay_detected"
    assert role_conflict.status_code == 409
    assert role_conflict.json()["detail"]["code"] == "promotion_approval_active_role_conflict"


def test_two_distinct_authenticated_signatures_make_bundle_ready(tmp_path: Path, monkeypatch) -> None:
    client, private_keys = _client(tmp_path, monkeypatch)
    physician = _submission(
        private_keys["physician-key-001"],
        key_id="physician-key-001",
        identity=PHYSICIAN_IDENTITY,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    project_reviewer = _submission(
        private_keys["project-reviewer-key-001"],
        key_id="project-reviewer-key-001",
        identity=PROJECT_REVIEWER_IDENTITY,
        approval_id="approval-project-reviewer-0001",
        nonce="nonce-project-reviewer-00000001",
    )

    assert (
        client.post(
            "/model-promotion/approvals",
            json=physician,
            headers=_authorization(PHYSICIAN_TOKEN),
        ).status_code
        == 201
    )
    pending = client.get("/model-promotion/approvals/status", params=TARGET)
    assert pending.status_code == 200
    assert pending.json()["approval_ready"] is False
    assert pending.json()["missing_roles"] == ["project_reviewer"]

    assert (
        client.post(
            "/model-promotion/approvals",
            json=project_reviewer,
            headers=_authorization(PROJECT_REVIEWER_TOKEN),
        ).status_code
        == 201
    )
    status_response = client.get("/model-promotion/approvals/status", params=TARGET)
    bundle_response = client.get("/model-promotion/approvals/bundle", params=TARGET)

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["approval_ready"] is True
    assert status_payload["active_approval_count"] == 2
    assert status_payload["runtime_replacement_allowed"] is False
    assert status_payload["clinical_claim_allowed"] is False
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()
    assert bundle["approval_ready"] is True
    assert bundle["chain_valid"] is True
    assert bundle["chain_record_count"] == 2
    assert len(bundle["chain_records"]) == 2
    assert len(bundle["target_records"]) == 2
    assert len(bundle["bundle_sha256"]) == 64


def test_signed_revocation_removes_physician_from_active_bundle(tmp_path: Path, monkeypatch) -> None:
    client, private_keys = _client(tmp_path, monkeypatch)
    physician_approval_id = "approval-physician-0001"
    approvals = [
        (
            _submission(
                private_keys["physician-key-001"],
                key_id="physician-key-001",
                identity=PHYSICIAN_IDENTITY,
                approval_id=physician_approval_id,
                nonce="nonce-physician-000000000001",
            ),
            PHYSICIAN_TOKEN,
        ),
        (
            _submission(
                private_keys["project-reviewer-key-001"],
                key_id="project-reviewer-key-001",
                identity=PROJECT_REVIEWER_IDENTITY,
                approval_id="approval-project-reviewer-0001",
                nonce="nonce-project-reviewer-00000001",
            ),
            PROJECT_REVIEWER_TOKEN,
        ),
    ]
    for submission, token in approvals:
        response = client.post(
            "/model-promotion/approvals",
            json=submission,
            headers=_authorization(token),
        )
        assert response.status_code == 201
    assert client.get("/model-promotion/approvals/status", params=TARGET).json()["approval_ready"] is True

    revocation = _submission(
        private_keys["physician-key-001"],
        key_id="physician-key-001",
        identity=PHYSICIAN_IDENTITY,
        approval_id="revocation-physician-0001",
        nonce="nonce-revocation-physician-00001",
        decision="revoke",
        supersedes_approval_id=physician_approval_id,
    )
    revoked = client.post(
        "/model-promotion/approvals",
        json=revocation,
        headers=_authorization(PHYSICIAN_TOKEN),
    )
    status_response = client.get("/model-promotion/approvals/status", params=TARGET)
    bundle_response = client.get("/model-promotion/approvals/bundle", params=TARGET)

    assert revoked.status_code == 201
    status_payload = status_response.json()
    assert status_payload["approval_ready"] is False
    assert status_payload["missing_roles"] == ["physician"]
    bundle = bundle_response.json()
    assert bundle["chain_record_count"] == 3
    assert bundle["active_approval_count"] == 1
    assert [row["submission"]["payload"]["decision"] for row in bundle["target_records"]] == [
        "approve",
        "approve",
        "revoke",
    ]
