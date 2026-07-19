from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROMOTION_APPROVAL_SCHEMA_VERSION: Literal["osteo-vision-promotion-approval-v1"] = "osteo-vision-promotion-approval-v1"
PROMOTION_APPROVAL_SCOPE: Literal["osteo-vision-target-domain-promotion"] = "osteo-vision-target-domain-promotion"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
ALLOWED_SIGNER_ROLES = frozenset({"physician", "project_reviewer"})
MAX_SIGNATURE_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)


class PromotionApprovalError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PromotionApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["osteo-vision-promotion-approval-v1"] = PROMOTION_APPROVAL_SCHEMA_VERSION
    scope: Literal["osteo-vision-target-domain-promotion"] = PROMOTION_APPROVAL_SCOPE
    approval_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    capability: Literal["patient_conditioned_segmentation", "bone_activity_multitask"]
    model_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
    checkpoint_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    decision: Literal["approve", "revoke"]
    signer_actor_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
    signer_role: Literal["physician", "project_reviewer"]
    signer_institution: str = Field(min_length=2, max_length=160)
    signed_at_utc: datetime
    nonce: str = Field(min_length=24, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    supersedes_approval_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @field_validator("model_id", "signer_actor_id", "signer_institution", "nonce", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("signed_at_utc")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signed_at_utc must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_decision_reference(self) -> PromotionApprovalPayload:
        if self.decision == "approve" and self.supersedes_approval_id is not None:
            raise ValueError("approve decisions cannot supersede another approval")
        if self.decision == "revoke" and self.supersedes_approval_id is None:
            raise ValueError("revoke decisions require supersedes_approval_id")
        if self.supersedes_approval_id == self.approval_id:
            raise ValueError("an approval cannot supersede itself")
        return self


class SignedPromotionApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: PromotionApprovalPayload
    key_id: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    signature_b64: str = Field(min_length=80, max_length=128)


class StoredPromotionApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    recorded_at_utc: datetime
    previous_record_hash: str = Field(pattern=SHA256_PATTERN)
    record_hash: str = Field(pattern=SHA256_PATTERN)
    submission: SignedPromotionApproval

    @field_validator("recorded_at_utc")
    @classmethod
    def require_recorded_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at_utc must include a timezone")
        return value.astimezone(timezone.utc)


class TrustedPromotionKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    algorithm: Literal["ed25519"] = "ed25519"
    public_key_pem: str = Field(min_length=80, max_length=1000)
    actor_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
    role: Literal["physician", "project_reviewer"]
    institution: str = Field(min_length=2, max_length=160)
    status: Literal["active", "revoked", "expired"] = "active"
    valid_from_utc: datetime
    valid_until_utc: datetime
    allowed_capabilities: list[Literal["patient_conditioned_segmentation", "bone_activity_multitask"]] = Field(
        min_length=1
    )

    @field_validator("valid_from_utc", "valid_until_utc")
    @classmethod
    def require_key_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trusted key timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_validity_window(self) -> TrustedPromotionKey:
        if self.valid_until_utc <= self.valid_from_utc:
            raise ValueError("trusted key validity window is empty")
        if len(set(self.allowed_capabilities)) != len(self.allowed_capabilities):
            raise ValueError("trusted key capabilities must be unique")
        _load_public_key(self.public_key_pem)
        return self


class PromotionTrustStore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["osteo-vision-promotion-trust-store-v1"] = "osteo-vision-promotion-trust-store-v1"
    keys: list[TrustedPromotionKey] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> PromotionTrustStore:
        key_ids = [key.key_id for key in self.keys]
        if len(set(key_ids)) != len(key_ids):
            raise ValueError("promotion trust-store key ids must be unique")
        public_keys = [_public_key_raw(key.public_key_pem) for key in self.keys]
        if len(set(public_keys)) != len(public_keys):
            raise ValueError("promotion trust-store public keys must be cryptographically distinct")
        return self

    def key(self, key_id: str) -> TrustedPromotionKey | None:
        return next((key for key in self.keys if key.key_id == key_id), None)


def canonical_approval_payload_bytes(payload: PromotionApprovalPayload) -> bytes:
    normalized = payload.model_dump(mode="json", exclude_none=False)
    return _canonical_json_bytes(normalized)


def sign_approval_payload(
    payload: PromotionApprovalPayload,
    private_key: Ed25519PrivateKey | bytes | str,
) -> str:
    key = _load_private_key(private_key)
    signature = key.sign(canonical_approval_payload_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def verify_signed_approval(
    submission: SignedPromotionApproval,
    trust_store: PromotionTrustStore,
    *,
    now: datetime | None = None,
    enforce_current_authorization: bool = True,
    enforce_submission_window: bool = True,
) -> SignedPromotionApproval:
    current = _normalized_now(now)
    key = trust_store.key(submission.key_id)
    if key is None:
        raise PromotionApprovalError("promotion_approval_key_unknown", "Approval signing key is not trusted.")
    if enforce_current_authorization:
        _validate_current_key_authorization(key, current)
    _validate_key_identity_and_scope(key, submission.payload)
    if enforce_submission_window:
        _validate_signature_time(submission.payload.signed_at_utc, current)

    try:
        signature = base64.b64decode(submission.signature_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise PromotionApprovalError(
            "promotion_approval_signature_encoding_invalid",
            "Approval signature is not valid base64.",
        ) from exc
    if len(signature) != 64:
        raise PromotionApprovalError(
            "promotion_approval_signature_encoding_invalid",
            "Ed25519 approval signatures must contain 64 bytes.",
        )
    public_key = _load_public_key(key.public_key_pem)
    try:
        public_key.verify(signature, canonical_approval_payload_bytes(submission.payload))
    except InvalidSignature as exc:
        raise PromotionApprovalError(
            "promotion_approval_signature_invalid",
            "Approval signature does not match the signed target and identity.",
        ) from exc
    return submission


def target_fingerprint(payload: PromotionApprovalPayload) -> str:
    target = {
        "scope": payload.scope,
        "capability": payload.capability,
        "model_id": payload.model_id,
        "checkpoint_sha256": payload.checkpoint_sha256,
        "policy_sha256": payload.policy_sha256,
        "evidence_bundle_sha256": payload.evidence_bundle_sha256,
    }
    return hashlib.sha256(_canonical_json_bytes(target)).hexdigest()


def approval_record_hash(
    *,
    sequence: int,
    recorded_at_utc: datetime,
    previous_record_hash: str,
    submission: SignedPromotionApproval,
) -> str:
    material = {
        "sequence": sequence,
        "recorded_at_utc": _utc_iso(recorded_at_utc),
        "previous_record_hash": previous_record_hash,
        "submission": submission.model_dump(mode="json", exclude_none=False),
    }
    return hashlib.sha256(_canonical_json_bytes(material)).hexdigest()


def trust_store_fingerprint(trust_store: PromotionTrustStore) -> str:
    return hashlib.sha256(_canonical_json_bytes(trust_store.model_dump(mode="json", exclude_none=False))).hexdigest()


def canonical_json_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def public_key_pem(public_key: Ed25519PublicKey) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _validate_current_key_authorization(key: TrustedPromotionKey, now: datetime) -> None:
    if key.status == "revoked":
        raise PromotionApprovalError("promotion_approval_key_revoked", "Approval signing key has been revoked.")
    if key.status == "expired":
        raise PromotionApprovalError("promotion_approval_key_expired", "Approval signing key is marked expired.")
    if now < key.valid_from_utc:
        raise PromotionApprovalError(
            "promotion_approval_key_not_yet_valid",
            "Approval signing key is outside its validity window.",
        )
    if now > key.valid_until_utc:
        raise PromotionApprovalError("promotion_approval_key_expired", "Approval signing key has expired.")


def _validate_key_identity_and_scope(key: TrustedPromotionKey, payload: PromotionApprovalPayload) -> None:
    expected_identity = (key.actor_id, key.role, key.institution)
    actual_identity = (payload.signer_actor_id, payload.signer_role, payload.signer_institution)
    if actual_identity != expected_identity:
        raise PromotionApprovalError(
            "promotion_approval_key_identity_mismatch",
            "Approval signer identity does not match the trusted public key record.",
        )
    if payload.capability not in key.allowed_capabilities:
        raise PromotionApprovalError(
            "promotion_approval_key_capability_forbidden",
            "Approval signing key is not authorized for this capability.",
        )


def _validate_signature_time(signed_at: datetime, now: datetime) -> None:
    if signed_at > now + MAX_FUTURE_SKEW:
        raise PromotionApprovalError(
            "promotion_approval_signature_from_future",
            "Approval signature timestamp is too far in the future.",
        )
    if now - signed_at > MAX_SIGNATURE_AGE:
        raise PromotionApprovalError(
            "promotion_approval_signature_stale",
            "Approval signature is older than the submission window.",
        )


def _load_private_key(private_key: Ed25519PrivateKey | bytes | str) -> Ed25519PrivateKey:
    if isinstance(private_key, Ed25519PrivateKey):
        return private_key
    payload = private_key.encode("ascii") if isinstance(private_key, str) else private_key
    try:
        loaded = serialization.load_pem_private_key(payload, password=None)
    except (TypeError, ValueError) as exc:
        raise PromotionApprovalError(
            "promotion_approval_private_key_invalid",
            "Private key is not an unencrypted Ed25519 PEM key.",
        ) from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise PromotionApprovalError(
            "promotion_approval_private_key_invalid",
            "Private key algorithm must be Ed25519.",
        )
    return loaded


def _load_public_key(public_key_pem_value: str) -> Ed25519PublicKey:
    try:
        loaded = serialization.load_pem_public_key(public_key_pem_value.encode("ascii"))
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("trusted public key is not valid PEM") from exc
    if not isinstance(loaded, Ed25519PublicKey):
        raise ValueError("trusted public key algorithm must be Ed25519")
    return loaded


def _public_key_raw(public_key_pem_value: str) -> bytes:
    return _load_public_key(public_key_pem_value).public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _normalized_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("verification time must include a timezone")
    return current.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")
