from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import ValidationError

from osteo_vision_core.models.promotion_approval import (
    PROMOTION_APPROVAL_SCOPE,
    PromotionApprovalError,
    PromotionApprovalPayload,
    PromotionTrustStore,
    StoredPromotionApproval,
    approval_record_hash,
    canonical_json_sha256,
    target_fingerprint,
    trust_store_fingerprint,
    verify_signed_approval,
)

APPROVAL_BUNDLE_SCHEMA_VERSION = "osteo-vision-promotion-approval-bundle-v1"
EMPTY_CHAIN_HASH = "0" * 64
REQUIRED_APPROVAL_ROLES = ("physician", "project_reviewer")


def validate_promotion_approval_bundle(
    bundle: Mapping[str, Any] | None,
    *,
    trust_store: PromotionTrustStore,
    reference: PromotionApprovalPayload | Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Independently replay a signed approval bundle before model promotion."""

    blockers: list[dict[str, Any]] = []
    data = dict(bundle) if isinstance(bundle, Mapping) else {}
    current = _utc_now(now)
    expected_target = _normalized_target(reference)
    expected_target_fingerprint = _target_summary_fingerprint(expected_target)

    if not data:
        blockers.append({"code": "promotion_approval_bundle_missing"})
        return _result(blockers, expected_target_fingerprint, None, 0)
    if data.get("schema_version") != APPROVAL_BUNDLE_SCHEMA_VERSION:
        blockers.append({"code": "promotion_approval_bundle_schema_invalid"})

    declared_bundle_sha256 = str(data.get("bundle_sha256") or "").lower()
    bundle_material = {key: value for key, value in data.items() if key not in {"bundle_sha256", "chain_valid"}}
    recomputed_bundle_sha256 = canonical_json_sha256(bundle_material)
    if declared_bundle_sha256 != recomputed_bundle_sha256:
        blockers.append({"code": "promotion_approval_bundle_sha_mismatch"})
    if data.get("chain_valid") is not True:
        blockers.append({"code": "promotion_approval_bundle_chain_not_valid"})
    if str(data.get("trust_store_sha256") or "").lower() != trust_store_fingerprint(trust_store):
        blockers.append({"code": "promotion_approval_bundle_trust_store_mismatch"})
    if str(data.get("target_fingerprint") or "").lower() != expected_target_fingerprint:
        blockers.append({"code": "promotion_approval_bundle_target_fingerprint_mismatch"})
    if _mapping(data.get("target")) != expected_target:
        blockers.append({"code": "promotion_approval_bundle_target_mismatch"})

    records = _parse_records(data.get("chain_records"), blockers)
    chain = _validate_chain(records, trust_store, blockers)
    if _strict_integer(data.get("chain_record_count")) != chain["record_count"]:
        blockers.append({"code": "promotion_approval_bundle_chain_count_mismatch"})
    if str(data.get("chain_head_hash") or "").lower() != chain["head_hash"]:
        blockers.append({"code": "promotion_approval_bundle_chain_head_mismatch"})

    target_records = [
        record for record in records if target_fingerprint(record.submission.payload) == expected_target_fingerprint
    ]
    declared_target_records = data.get("target_records")
    expected_target_records = [record.model_dump(mode="json") for record in target_records]
    if declared_target_records != expected_target_records:
        blockers.append({"code": "promotion_approval_bundle_target_records_mismatch"})

    active_records, missing_roles = _active_approvals(
        target_records,
        trust_store=trust_store,
        now=current,
        blockers=blockers,
    )
    active_ids = [record.submission.payload.approval_id for record in active_records]
    if data.get("required_roles") != list(REQUIRED_APPROVAL_ROLES):
        blockers.append({"code": "promotion_approval_bundle_required_roles_mismatch"})
    if data.get("missing_roles") != missing_roles:
        blockers.append({"code": "promotion_approval_bundle_missing_roles_mismatch"})
    if data.get("active_approval_ids") != active_ids:
        blockers.append({"code": "promotion_approval_bundle_active_ids_mismatch"})
    if _strict_integer(data.get("active_approval_count")) != len(active_records):
        blockers.append({"code": "promotion_approval_bundle_active_count_mismatch"})
    if data.get("blockers") not in ([], None):
        blockers.append({"code": "promotion_approval_bundle_reported_blockers"})
    if data.get("approval_ready") is not True:
        blockers.append({"code": "promotion_approval_bundle_not_ready"})
    if missing_roles:
        blockers.append({"code": "promotion_approval_roles_incomplete", "missing_roles": missing_roles})

    unique_blockers = _unique_blockers(blockers)
    return _result(
        unique_blockers,
        expected_target_fingerprint,
        declared_bundle_sha256 or None,
        len(active_records),
    )


def _parse_records(value: Any, blockers: list[dict[str, Any]]) -> list[StoredPromotionApproval]:
    if not isinstance(value, list):
        blockers.append({"code": "promotion_approval_bundle_chain_records_missing"})
        return []
    records: list[StoredPromotionApproval] = []
    for index, item in enumerate(value):
        try:
            records.append(StoredPromotionApproval.model_validate(item))
        except ValidationError:
            blockers.append({"code": "promotion_approval_bundle_chain_record_invalid", "index": index})
    return records


def _validate_chain(
    records: list[StoredPromotionApproval],
    trust_store: PromotionTrustStore,
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_hash = EMPTY_CHAIN_HASH
    previous_recorded_at: datetime | None = None
    seen_approval_ids: set[str] = set()
    seen_nonces: set[str] = set()
    for expected_sequence, record in enumerate(records, start=1):
        payload = record.submission.payload
        if record.sequence != expected_sequence:
            blockers.append({"code": "promotion_approval_bundle_chain_sequence_invalid"})
        if payload.approval_id in seen_approval_ids or payload.nonce in seen_nonces:
            blockers.append({"code": "promotion_approval_bundle_chain_replay_detected"})
        seen_approval_ids.add(payload.approval_id)
        seen_nonces.add(payload.nonce)
        if record.previous_record_hash != previous_hash:
            blockers.append({"code": "promotion_approval_bundle_chain_link_mismatch"})
        if previous_recorded_at is not None and record.recorded_at_utc < previous_recorded_at:
            blockers.append({"code": "promotion_approval_bundle_chain_timestamp_invalid"})
        expected_hash = approval_record_hash(
            sequence=record.sequence,
            recorded_at_utc=record.recorded_at_utc,
            previous_record_hash=record.previous_record_hash,
            submission=record.submission,
        )
        if record.record_hash != expected_hash:
            blockers.append({"code": "promotion_approval_bundle_chain_hash_mismatch"})
        try:
            verify_signed_approval(
                record.submission,
                trust_store,
                now=record.recorded_at_utc,
                enforce_current_authorization=False,
            )
        except PromotionApprovalError as exc:
            blockers.append(
                {
                    "code": "promotion_approval_bundle_historical_signature_invalid",
                    "approval_id": payload.approval_id,
                    "reason": exc.code,
                }
            )
        previous_hash = expected_hash
        previous_recorded_at = record.recorded_at_utc
    return {"record_count": len(records), "head_hash": previous_hash}


def _active_approvals(
    records: list[StoredPromotionApproval],
    *,
    trust_store: PromotionTrustStore,
    now: datetime,
    blockers: list[dict[str, Any]],
) -> tuple[list[StoredPromotionApproval], list[str]]:
    approvals: dict[str, StoredPromotionApproval] = {}
    revoked: set[str] = set()
    for record in records:
        payload = record.submission.payload
        if payload.decision == "approve":
            approvals[payload.approval_id] = record
            continue
        original = approvals.get(str(payload.supersedes_approval_id))
        if original is None or not _same_signer(payload, original.submission.payload):
            blockers.append(
                {
                    "code": "promotion_approval_bundle_revocation_invalid",
                    "approval_id": payload.approval_id,
                }
            )
            continue
        original_id = original.submission.payload.approval_id
        if original_id in revoked:
            blockers.append(
                {
                    "code": "promotion_approval_revocation_target_inactive",
                    "approval_id": payload.approval_id,
                }
            )
            continue
        revoked.add(original_id)

    active_by_role: dict[str, StoredPromotionApproval] = {}
    for approval_id, record in approvals.items():
        if approval_id in revoked:
            continue
        try:
            verify_signed_approval(
                record.submission,
                trust_store,
                now=now,
                enforce_submission_window=False,
            )
        except PromotionApprovalError as exc:
            blockers.append(
                {
                    "code": exc.code,
                    "approval_id": approval_id,
                    "signer_role": record.submission.payload.signer_role,
                }
            )
            continue
        role = record.submission.payload.signer_role
        if role in active_by_role:
            blockers.append(
                {
                    "code": "promotion_approval_multiple_active_role_approvals",
                    "signer_role": role,
                }
            )
        active_by_role[role] = record

    missing_roles = [role for role in REQUIRED_APPROVAL_ROLES if role not in active_by_role]
    active_records = [active_by_role[role] for role in REQUIRED_APPROVAL_ROLES if role in active_by_role]
    if len({record.submission.key_id for record in active_records}) != len(active_records):
        blockers.append({"code": "promotion_approval_signing_keys_not_distinct"})
    if len({record.submission.payload.signer_actor_id for record in active_records}) != len(active_records):
        blockers.append({"code": "promotion_approval_signers_not_distinct"})
    return active_records, missing_roles


def _target_summary(payload: PromotionApprovalPayload) -> dict[str, str]:
    return {
        "capability": payload.capability,
        "model_id": payload.model_id,
        "checkpoint_sha256": payload.checkpoint_sha256,
        "policy_sha256": payload.policy_sha256,
        "evidence_bundle_sha256": payload.evidence_bundle_sha256,
    }


def _normalized_target(reference: PromotionApprovalPayload | Mapping[str, Any]) -> dict[str, str]:
    if isinstance(reference, PromotionApprovalPayload):
        return _target_summary(reference)
    value = dict(reference)
    return {
        "capability": str(value.get("capability") or ""),
        "model_id": str(value.get("model_id") or ""),
        "checkpoint_sha256": str(value.get("checkpoint_sha256") or "").lower(),
        "policy_sha256": str(value.get("policy_sha256") or "").lower(),
        "evidence_bundle_sha256": str(value.get("evidence_bundle_sha256") or "").lower(),
    }


def _target_summary_fingerprint(target: Mapping[str, str]) -> str:
    return canonical_json_sha256(
        {
            "scope": PROMOTION_APPROVAL_SCOPE,
            "capability": target["capability"],
            "model_id": target["model_id"],
            "checkpoint_sha256": target["checkpoint_sha256"],
            "policy_sha256": target["policy_sha256"],
            "evidence_bundle_sha256": target["evidence_bundle_sha256"],
        }
    )


def _same_signer(left: PromotionApprovalPayload, right: PromotionApprovalPayload) -> bool:
    return (
        left.signer_actor_id,
        left.signer_role,
        left.signer_institution,
    ) == (
        right.signer_actor_id,
        right.signer_role,
        right.signer_institution,
    )


def _result(
    blockers: list[dict[str, Any]],
    target_id: str,
    bundle_sha256: str | None,
    active_approval_count: int,
) -> dict[str, Any]:
    return {
        "valid": not blockers,
        "target_fingerprint": target_id,
        "bundle_sha256": bundle_sha256,
        "active_approval_count": active_approval_count,
        "blockers": blockers,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("promotion approval verification time must include a timezone")
    return current.astimezone(timezone.utc)


def _strict_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _unique_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for blocker in blockers:
        key = canonical_json_sha256(blocker)
        if key in seen:
            continue
        seen.add(key)
        result.append(blocker)
    return result
