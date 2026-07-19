from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.src.domains.cases.enums import ReviewerRole
from backend.src.domains.cases.schemas import ReviewActorIdentity
from backend.src.services.promotion_approval_service import (
    PromotionApprovalRepository,
    PromotionApprovalService,
)
from src.models.promotion_approval import (
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    TrustedPromotionKey,
    public_key_pem,
    sign_approval_payload,
)
from src.models.promotion_approval_gate import validate_promotion_approval_bundle

NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)


def _actor(actor_id: str, role: ReviewerRole, institution: str) -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id=actor_id,
        role=role,
        institution=institution,
        auth_source="verified_identity_token",
    )


def _trusted_key(
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
        model_id="patient-conditioned-target-v1",
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


def _signed(
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


def _ready_bundle(tmp_path: Path) -> tuple[
    dict,
    PromotionTrustStore,
    PromotionApprovalPayload,
    PromotionApprovalService,
    ReviewActorIdentity,
    Ed25519PrivateKey,
]:
    physician = _actor("physician-001", ReviewerRole.PHYSICIAN, "Target Hospital")
    reviewer = _actor("project-reviewer-001", ReviewerRole.PROJECT_REVIEWER, "Osteo Vision Project")
    physician_key = Ed25519PrivateKey.generate()
    reviewer_key = Ed25519PrivateKey.generate()
    trust_store = PromotionTrustStore(
        keys=[
            _trusted_key(physician_key, key_id="physician-key-001", actor=physician),
            _trusted_key(reviewer_key, key_id="reviewer-key-001", actor=reviewer),
        ]
    )
    service = PromotionApprovalService(
        PromotionApprovalRepository(tmp_path / "approvals.sqlite"),
        trust_store,
        now_factory=lambda: NOW,
    )
    physician_payload = _payload(
        physician,
        approval_id="approval-physician-001",
        nonce="nonce-physician-000000000001",
    )
    reviewer_payload = _payload(
        reviewer,
        approval_id="approval-reviewer-001",
        nonce="nonce-reviewer-0000000000001",
    )
    service.submit(
        _signed(physician_payload, key_id="physician-key-001", private_key=physician_key),
        physician,
    )
    service.submit(
        _signed(reviewer_payload, key_id="reviewer-key-001", private_key=reviewer_key),
        reviewer,
    )
    return (
        service.readiness(physician_payload),
        trust_store,
        physician_payload,
        service,
        physician,
        physician_key,
    )


def test_signed_bundle_replays_to_two_role_approval(tmp_path: Path) -> None:
    bundle, trust_store, reference, _, _, _ = _ready_bundle(tmp_path)
    transported_bundle = json.loads(json.dumps(bundle, ensure_ascii=False))

    result = validate_promotion_approval_bundle(
        transported_bundle,
        trust_store=trust_store,
        reference=reference,
        now=NOW,
    )

    assert result["valid"] is True
    assert result["blockers"] == []
    assert result["active_approval_count"] == 2
    assert result["bundle_sha256"] == bundle["bundle_sha256"]


def test_bundle_target_tampering_fails_closed(tmp_path: Path) -> None:
    bundle, trust_store, reference, _, _, _ = _ready_bundle(tmp_path)
    bundle["target"]["checkpoint_sha256"] = "f" * 64

    result = validate_promotion_approval_bundle(
        bundle,
        trust_store=trust_store,
        reference=reference,
        now=NOW,
    )

    codes = {item["code"] for item in result["blockers"]}
    assert "promotion_approval_bundle_sha_mismatch" in codes
    assert "promotion_approval_bundle_target_mismatch" in codes
    assert result["valid"] is False


def test_bundle_chain_record_tampering_fails_closed(tmp_path: Path) -> None:
    bundle, trust_store, reference, _, _, _ = _ready_bundle(tmp_path)
    bundle["chain_records"][0]["record_hash"] = "f" * 64

    result = validate_promotion_approval_bundle(
        bundle,
        trust_store=trust_store,
        reference=reference,
        now=NOW,
    )

    codes = {item["code"] for item in result["blockers"]}
    assert "promotion_approval_bundle_sha_mismatch" in codes
    assert "promotion_approval_bundle_chain_hash_mismatch" in codes


def test_revocation_bundle_cannot_remain_ready(tmp_path: Path) -> None:
    _, trust_store, reference, service, physician, physician_key = _ready_bundle(tmp_path)
    revocation = _payload(
        physician,
        approval_id="revocation-physician-001",
        nonce="nonce-revocation-000000000001",
        decision="revoke",
        supersedes_approval_id=reference.approval_id,
    )
    service.submit(
        _signed(revocation, key_id="physician-key-001", private_key=physician_key),
        physician,
    )
    bundle = service.readiness(reference)

    result = validate_promotion_approval_bundle(
        bundle,
        trust_store=trust_store,
        reference=reference,
        now=NOW,
    )

    codes = {item["code"] for item in result["blockers"]}
    assert "promotion_approval_bundle_not_ready" in codes
    assert "promotion_approval_roles_incomplete" in codes
    assert result["valid"] is False


def test_empty_bundle_fails_closed() -> None:
    actor = _actor("physician-001", ReviewerRole.PHYSICIAN, "Target Hospital")
    reference = _payload(
        actor,
        approval_id="approval-physician-001",
        nonce="nonce-physician-000000000001",
    )

    result = validate_promotion_approval_bundle(
        None,
        trust_store=PromotionTrustStore(keys=[]),
        reference=reference,
        now=NOW,
    )

    assert result["valid"] is False
    assert result["blockers"] == [{"code": "promotion_approval_bundle_missing"}]
