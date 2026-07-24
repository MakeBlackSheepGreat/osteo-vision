from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.osteo_vision_api.domains.cases.enums import ReviewerRole
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.promotion_approval_service import (
    PromotionApprovalRepository,
    PromotionApprovalService,
)
from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalError,
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    StoredPromotionApproval,
    TrustedPromotionKey,
    approval_record_hash,
    public_key_pem,
    sign_approval_payload,
)

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)


def _actor(actor_id: str, role: ReviewerRole, institution: str) -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id=actor_id,
        role=role,
        institution=institution,
        auth_source="verified_identity_token",
    )


def _key(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
    actor: ReviewActorIdentity,
) -> TrustedPromotionKey:
    return TrustedPromotionKey(
        key_id=key_id,
        public_key_pem=public_key_pem(private_key.public_key()),
        actor_id=actor.actor_id,
        role=actor.role.value,
        institution=actor.institution,
        valid_from_utc=NOW - timedelta(days=1),
        valid_until_utc=NOW + timedelta(days=30),
        allowed_capabilities=["patient_conditioned_segmentation"],
    )


def _payload(
    actor: ReviewActorIdentity,
    *,
    approval_id: str,
    nonce: str,
    decision: str = "approve",
    supersedes_approval_id: str | None = None,
) -> PromotionApprovalPayload:
    return PromotionApprovalPayload(
        approval_id=approval_id,
        capability="patient_conditioned_segmentation",
        model_id="patient-conditioned-v1",
        checkpoint_sha256="1" * 64,
        policy_sha256="2" * 64,
        evidence_bundle_sha256="3" * 64,
        decision=decision,
        signer_actor_id=actor.actor_id,
        signer_role=actor.role.value,
        signer_institution=actor.institution,
        signed_at_utc=NOW,
        nonce=nonce,
        supersedes_approval_id=supersedes_approval_id,
    )


def _submission(
    payload: PromotionApprovalPayload,
    *,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedPromotionApproval:
    return SignedPromotionApproval(
        payload=payload,
        key_id=key_id,
        signature_b64=sign_approval_payload(payload, private_key),
    )


def _service(tmp_path: Path) -> tuple[
    PromotionApprovalService,
    PromotionApprovalRepository,
    ReviewActorIdentity,
    ReviewActorIdentity,
    Ed25519PrivateKey,
    Ed25519PrivateKey,
]:
    physician = _actor("doctor-chen-001", ReviewerRole.PHYSICIAN, "Mianyang Third People's Hospital")
    safety = _actor("safety-owner-001", ReviewerRole.PROJECT_REVIEWER, "Osteo Vision Project")
    physician_private = Ed25519PrivateKey.generate()
    safety_private = Ed25519PrivateKey.generate()
    trust_store = PromotionTrustStore(
        keys=[
            _key(physician_private, key_id="physician-key-001", actor=physician),
            _key(safety_private, key_id="safety-key-001", actor=safety),
        ]
    )
    repository = PromotionApprovalRepository(tmp_path / "promotion_approvals.sqlite")
    return (
        PromotionApprovalService(repository, trust_store, now_factory=lambda: NOW),
        repository,
        physician,
        safety,
        physician_private,
        safety_private,
    )


def test_two_distinct_signed_roles_are_required_for_promotion_readiness(tmp_path: Path) -> None:
    service, repository, physician, safety, physician_private, safety_private = _service(tmp_path)
    physician_payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    service.submit(
        _submission(physician_payload, key_id="physician-key-001", private_key=physician_private),
        physician,
    )

    pending = service.readiness(physician_payload)

    assert pending["approval_ready"] is False
    assert pending["chain_valid"] is True
    assert pending["missing_roles"] == ["project_reviewer"]
    assert repository.verify_chain()["record_count"] == 1

    safety_payload = _payload(
        safety,
        approval_id="approval-safety-0001",
        nonce="nonce-safety-000000000000001",
    )
    service.submit(
        _submission(safety_payload, key_id="safety-key-001", private_key=safety_private),
        safety,
    )

    ready = service.readiness(physician_payload)

    assert ready["approval_ready"] is True
    assert ready["missing_roles"] == []
    assert ready["active_approval_count"] == 2
    assert len(ready["bundle_sha256"]) == 64


def test_nonce_and_approval_id_replay_are_rejected(tmp_path: Path) -> None:
    service, _, physician, _, physician_private, _ = _service(tmp_path)
    payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    submission = _submission(payload, key_id="physician-key-001", private_key=physician_private)
    service.submit(submission, physician)

    with pytest.raises(PromotionApprovalError) as exc_info:
        service.submit(submission, physician)
    assert exc_info.value.code == "promotion_approval_replay_detected"


def test_active_role_must_be_revoked_before_replacement(tmp_path: Path) -> None:
    service, repository, physician, _, physician_private, _ = _service(tmp_path)
    first = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    second = _payload(
        physician,
        approval_id="approval-physician-0002",
        nonce="nonce-physician-000000000002",
    )
    service.submit(
        _submission(first, key_id="physician-key-001", private_key=physician_private),
        physician,
    )

    with pytest.raises(PromotionApprovalError) as exc_info:
        service.submit(
            _submission(second, key_id="physician-key-001", private_key=physician_private),
            physician,
        )

    assert exc_info.value.code == "promotion_approval_active_role_conflict"
    assert repository.verify_chain()["record_count"] == 1


def test_authenticated_actor_must_match_signed_key_identity(tmp_path: Path) -> None:
    service, _, physician, safety, physician_private, _ = _service(tmp_path)
    payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )

    with pytest.raises(PromotionApprovalError) as exc_info:
        service.submit(
            _submission(payload, key_id="physician-key-001", private_key=physician_private),
            safety,
        )
    assert exc_info.value.code == "promotion_approval_authenticated_identity_mismatch"


def test_append_only_chain_detects_database_tampering(tmp_path: Path) -> None:
    service, repository, physician, _, physician_private, _ = _service(tmp_path)
    payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    service.submit(
        _submission(payload, key_id="physician-key-001", private_key=physician_private),
        physician,
    )

    with sqlite3.connect(repository.store_path) as connection:
        record_json = json.loads(
            connection.execute("SELECT record_json FROM promotion_approvals WHERE sequence = 1").fetchone()[0]
        )
        signature = record_json["submission"]["signature_b64"]
        record_json["submission"]["signature_b64"] = ("A" if signature[0] != "A" else "B") + signature[1:]
        connection.execute(
            "UPDATE promotion_approvals SET record_json = ? WHERE sequence = 1",
            (json.dumps(record_json, separators=(",", ":")),),
        )

    with pytest.raises(PromotionApprovalError) as exc_info:
        repository.verify_chain()
    assert exc_info.value.code == "promotion_approval_chain_hash_mismatch"


def test_rehashed_invalid_signature_chain_rejects_new_append(tmp_path: Path) -> None:
    service, repository, physician, safety, physician_private, safety_private = _service(tmp_path)
    physician_payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    service.submit(
        _submission(physician_payload, key_id="physician-key-001", private_key=physician_private),
        physician,
    )

    with sqlite3.connect(repository.store_path) as connection:
        record_json = json.loads(
            connection.execute("SELECT record_json FROM promotion_approvals WHERE sequence = 1").fetchone()[0]
        )
        signature = record_json["submission"]["signature_b64"]
        record_json["submission"]["signature_b64"] = ("A" if signature[0] != "A" else "B") + signature[1:]
        tampered = StoredPromotionApproval.model_validate(record_json)
        record_hash = approval_record_hash(
            sequence=tampered.sequence,
            recorded_at_utc=tampered.recorded_at_utc,
            previous_record_hash=tampered.previous_record_hash,
            submission=tampered.submission,
        )
        record_json["record_hash"] = record_hash
        connection.execute(
            "UPDATE promotion_approvals SET record_hash = ?, record_json = ? WHERE sequence = 1",
            (record_hash, json.dumps(record_json, separators=(",", ":"))),
        )
        connection.execute(
            "UPDATE promotion_approval_chain_state SET head_hash = ? WHERE singleton_id = 1",
            (record_hash,),
        )
    assert repository.verify_chain()["chain_valid"] is True

    safety_payload = _payload(
        safety,
        approval_id="approval-safety-0001",
        nonce="nonce-safety-000000000000001",
    )
    with pytest.raises(PromotionApprovalError) as exc_info:
        service.submit(
            _submission(safety_payload, key_id="safety-key-001", private_key=safety_private),
            safety,
        )
    assert exc_info.value.code == "promotion_approval_chain_signature_invalid"


def test_signed_revocation_removes_the_original_role_approval(tmp_path: Path) -> None:
    service, _, physician, safety, physician_private, safety_private = _service(tmp_path)
    physician_payload = _payload(
        physician,
        approval_id="approval-physician-0001",
        nonce="nonce-physician-000000000001",
    )
    safety_payload = _payload(
        safety,
        approval_id="approval-safety-0001",
        nonce="nonce-safety-000000000000001",
    )
    service.submit(
        _submission(physician_payload, key_id="physician-key-001", private_key=physician_private),
        physician,
    )
    service.submit(
        _submission(safety_payload, key_id="safety-key-001", private_key=safety_private),
        safety,
    )
    revocation = _payload(
        physician,
        approval_id="revoke-physician-0001",
        nonce="nonce-revoke-physician-00000001",
        decision="revoke",
        supersedes_approval_id=physician_payload.approval_id,
    )

    service.submit(
        _submission(revocation, key_id="physician-key-001", private_key=physician_private),
        physician,
    )

    status = service.readiness(physician_payload)
    assert status["approval_ready"] is False
    assert status["missing_roles"] == ["physician"]

    duplicate_revocation = _payload(
        physician,
        approval_id="revoke-physician-0002",
        nonce="nonce-revoke-physician-00000002",
        decision="revoke",
        supersedes_approval_id=physician_payload.approval_id,
    )
    with pytest.raises(PromotionApprovalError) as exc_info:
        service.submit(
            _submission(
                duplicate_revocation,
                key_id="physician-key-001",
                private_key=physician_private,
            ),
            physician,
        )
    assert exc_info.value.code == "promotion_approval_revocation_target_inactive"

    replacement = _payload(
        physician,
        approval_id="approval-physician-0002",
        nonce="nonce-physician-000000000002",
    )
    service.submit(
        _submission(replacement, key_id="physician-key-001", private_key=physician_private),
        physician,
    )
    replacement_status = service.readiness(replacement)
    assert replacement_status["approval_ready"] is True
    assert replacement_status["active_approval_count"] == 2
