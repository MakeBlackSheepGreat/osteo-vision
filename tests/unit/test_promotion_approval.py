from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalError,
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    TrustedPromotionKey,
    public_key_pem,
    sign_approval_payload,
    target_fingerprint,
    verify_signed_approval,
)


def _payload(*, actor_id: str = "doctor-chen-001", role: str = "physician") -> PromotionApprovalPayload:
    return PromotionApprovalPayload(
        approval_id="approval-00000001",
        capability="patient_conditioned_segmentation",
        model_id="patient-conditioned-v1",
        checkpoint_sha256="1" * 64,
        policy_sha256="2" * 64,
        evidence_bundle_sha256="3" * 64,
        decision="approve",
        signer_actor_id=actor_id,
        signer_role=role,
        signer_institution="Mianyang Third People's Hospital",
        signed_at_utc=datetime.now(timezone.utc),
        nonce="nonce-000000000000000000000001",
    )


def _trusted_key(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str = "physician-key-001",
    actor_id: str = "doctor-chen-001",
    role: str = "physician",
    status: str = "active",
) -> TrustedPromotionKey:
    now = datetime.now(timezone.utc)
    return TrustedPromotionKey(
        key_id=key_id,
        algorithm="ed25519",
        public_key_pem=public_key_pem(private_key.public_key()),
        actor_id=actor_id,
        role=role,
        institution="Mianyang Third People's Hospital",
        status=status,
        valid_from_utc=now - timedelta(days=1),
        valid_until_utc=now + timedelta(days=30),
        allowed_capabilities=["patient_conditioned_segmentation"],
    )


def test_ed25519_approval_signature_is_bound_to_target_and_identity() -> None:
    private_key = Ed25519PrivateKey.generate()
    payload = _payload()
    submission = SignedPromotionApproval(
        payload=payload,
        key_id="physician-key-001",
        signature_b64=sign_approval_payload(payload, private_key),
    )
    trust_store = PromotionTrustStore(keys=[_trusted_key(private_key)])

    verified = verify_signed_approval(submission, trust_store)

    assert verified.payload == payload
    assert target_fingerprint(payload) == target_fingerprint(verified.payload)

    tampered = submission.model_copy(update={"payload": payload.model_copy(update={"checkpoint_sha256": "4" * 64})})
    with pytest.raises(PromotionApprovalError, match="signature") as exc_info:
        verify_signed_approval(tampered, trust_store)
    assert exc_info.value.code == "promotion_approval_signature_invalid"


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("revoked", "promotion_approval_key_revoked"),
        ("expired", "promotion_approval_key_expired"),
    ],
)
def test_inactive_trusted_keys_fail_closed(status: str, expected_code: str) -> None:
    private_key = Ed25519PrivateKey.generate()
    payload = _payload()
    submission = SignedPromotionApproval(
        payload=payload,
        key_id="physician-key-001",
        signature_b64=sign_approval_payload(payload, private_key),
    )

    with pytest.raises(PromotionApprovalError) as exc_info:
        verify_signed_approval(
            submission,
            PromotionTrustStore(keys=[_trusted_key(private_key, status=status)]),
        )
    assert exc_info.value.code == expected_code


def test_unknown_key_and_identity_mismatch_fail_closed() -> None:
    private_key = Ed25519PrivateKey.generate()
    payload = _payload()
    submission = SignedPromotionApproval(
        payload=payload,
        key_id="unknown-key",
        signature_b64=sign_approval_payload(payload, private_key),
    )

    with pytest.raises(PromotionApprovalError) as exc_info:
        verify_signed_approval(submission, PromotionTrustStore(keys=[]))
    assert exc_info.value.code == "promotion_approval_key_unknown"

    mismatched_store = PromotionTrustStore(
        keys=[_trusted_key(private_key, key_id="unknown-key", actor_id="different-doctor")]
    )
    with pytest.raises(PromotionApprovalError) as exc_info:
        verify_signed_approval(submission, mismatched_store)
    assert exc_info.value.code == "promotion_approval_key_identity_mismatch"


def test_trust_store_rejects_aliases_of_the_same_public_key() -> None:
    private_key = Ed25519PrivateKey.generate()

    with pytest.raises(ValueError, match="cryptographically distinct"):
        PromotionTrustStore(
            keys=[
                _trusted_key(private_key, key_id="physician-key-001"),
                _trusted_key(
                    private_key,
                    key_id="project-key-001",
                    actor_id="project-reviewer-001",
                    role="project_reviewer",
                ),
            ]
        )


def test_signature_age_and_future_timestamp_are_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    now = datetime.now(timezone.utc)
    trust_store = PromotionTrustStore(keys=[_trusted_key(private_key)])

    for signed_at, expected_code in (
        (now - timedelta(hours=25), "promotion_approval_signature_stale"),
        (now + timedelta(minutes=6), "promotion_approval_signature_from_future"),
    ):
        payload = _payload().model_copy(update={"signed_at_utc": signed_at})
        submission = SignedPromotionApproval(
            payload=payload,
            key_id="physician-key-001",
            signature_b64=sign_approval_payload(payload, private_key),
        )
        with pytest.raises(PromotionApprovalError) as exc_info:
            verify_signed_approval(submission, trust_store, now=now)
        assert exc_info.value.code == expected_code
