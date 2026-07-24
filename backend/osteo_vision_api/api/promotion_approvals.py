from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.osteo_vision_api.api.review_identity import resolve_review_actor
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.promotion_approval_service import PromotionApprovalService
from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalError,
    PromotionApprovalPayload,
    SignedPromotionApproval,
    StoredPromotionApproval,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"


def router(service: PromotionApprovalService) -> APIRouter:
    api = APIRouter()

    @api.post(
        "/model-promotion/approvals",
        response_model=StoredPromotionApproval,
        status_code=status.HTTP_201_CREATED,
    )
    def create_model_promotion_approval(
        submission: SignedPromotionApproval,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> StoredPromotionApproval:
        try:
            return service.submit(submission, actor)
        except PromotionApprovalError as exc:
            raise _approval_http_error(exc) from exc

    @api.get("/model-promotion/approvals/status")
    def get_model_promotion_approval_status(
        capability: Annotated[
            Literal["patient_conditioned_segmentation", "bone_activity_multitask"],
            Query(),
        ],
        model_id: Annotated[str, Query(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")],
        checkpoint_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
        policy_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
        evidence_bundle_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
    ) -> dict[str, object]:
        bundle = _readiness(
            service,
            capability=capability,
            model_id=model_id,
            checkpoint_sha256=checkpoint_sha256,
            policy_sha256=policy_sha256,
            evidence_bundle_sha256=evidence_bundle_sha256,
        )
        return {
            "schema_version": "osteo-vision-promotion-approval-status-v1",
            "target_fingerprint": bundle["target_fingerprint"],
            "target": bundle["target"],
            "approval_ready": bundle["approval_ready"],
            "active_approval_count": bundle["active_approval_count"],
            "active_approval_ids": bundle["active_approval_ids"],
            "required_roles": bundle["required_roles"],
            "missing_roles": bundle["missing_roles"],
            "blockers": bundle["blockers"],
            "chain_valid": bundle["chain_valid"],
            "chain_record_count": bundle["chain_record_count"],
            "chain_head_hash": bundle["chain_head_hash"],
            "trust_store_sha256": bundle["trust_store_sha256"],
            "bundle_sha256": bundle["bundle_sha256"],
            "runtime_replacement_allowed": False,
            "clinical_claim_allowed": False,
        }

    @api.get("/model-promotion/approvals/bundle")
    def get_model_promotion_approval_bundle(
        capability: Annotated[
            Literal["patient_conditioned_segmentation", "bone_activity_multitask"],
            Query(),
        ],
        model_id: Annotated[str, Query(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")],
        checkpoint_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
        policy_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
        evidence_bundle_sha256: Annotated[str, Query(pattern=SHA256_PATTERN)],
    ) -> dict[str, object]:
        return _readiness(
            service,
            capability=capability,
            model_id=model_id,
            checkpoint_sha256=checkpoint_sha256,
            policy_sha256=policy_sha256,
            evidence_bundle_sha256=evidence_bundle_sha256,
        )

    return api


def _readiness(
    service: PromotionApprovalService,
    *,
    capability: Literal["patient_conditioned_segmentation", "bone_activity_multitask"],
    model_id: str,
    checkpoint_sha256: str,
    policy_sha256: str,
    evidence_bundle_sha256: str,
) -> dict[str, object]:
    reference = PromotionApprovalPayload(
        approval_id="status-reference",
        capability=capability,
        model_id=model_id,
        checkpoint_sha256=checkpoint_sha256,
        policy_sha256=policy_sha256,
        evidence_bundle_sha256=evidence_bundle_sha256,
        decision="approve",
        signer_actor_id="status-query",
        signer_role="project_reviewer",
        signer_institution="Osteo Vision Status Query",
        signed_at_utc=datetime.now(timezone.utc),
        nonce="status-query-reference-000000000001",
    )
    try:
        return service.readiness(reference)
    except PromotionApprovalError as exc:
        raise _approval_http_error(exc) from exc


def _approval_http_error(exc: PromotionApprovalError) -> HTTPException:
    if exc.code in {
        "promotion_approval_replay_detected",
        "promotion_approval_active_role_conflict",
        "promotion_approval_revocation_target_inactive",
    }:
        status_code = status.HTTP_409_CONFLICT
    elif exc.code.startswith("promotion_approval_chain_") or exc.code == "promotion_approval_trust_store_invalid":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.code in {
        "promotion_approval_authenticated_identity_untrusted",
        "promotion_approval_authenticated_role_forbidden",
        "promotion_approval_authenticated_identity_mismatch",
        "promotion_approval_revocation_identity_mismatch",
        "promotion_approval_key_unknown",
        "promotion_approval_key_identity_mismatch",
        "promotion_approval_key_capability_forbidden",
        "promotion_approval_key_revoked",
        "promotion_approval_key_expired",
        "promotion_approval_key_not_yet_valid",
    }:
        status_code = status.HTTP_403_FORBIDDEN
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc)},
    )
