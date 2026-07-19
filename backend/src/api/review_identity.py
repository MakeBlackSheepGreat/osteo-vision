from __future__ import annotations

import hmac
import json
import os
from typing import Annotated

from fastapi import Header, HTTPException, status
from pydantic import ValidationError

from backend.src.domains.cases.enums import ReviewerRole
from backend.src.domains.cases.schemas import ReviewActorIdentity, ReviewIdentityStatus
from src.core.clinical_context_verification import (
    TRUSTED_CLINICAL_REVIEW_ROLE_VALUES,
    TRUSTED_REVIEW_AUTH_SOURCES,
)

REVIEW_IDENTITIES_ENV = "OSTEO_REVIEW_IDENTITIES_JSON"
MIN_REVIEW_TOKEN_LENGTH = 16
TRUSTED_CLINICAL_REVIEW_ROLES = frozenset(ReviewerRole(value) for value in TRUSTED_CLINICAL_REVIEW_ROLE_VALUES)


def resolve_review_actor(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ReviewActorIdentity:
    if authorization is None:
        return engineering_review_actor()

    scheme, separator, token = authorization.strip().partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise _credential_error("Review credentials must use a Bearer token")

    identities = _configured_identities()
    actor = _constant_time_identity_lookup(identities, token.strip())
    if actor is None:
        raise _credential_error("Review credentials are invalid")
    return actor


def engineering_review_actor() -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id="engineering-local-session",
        role=ReviewerRole.ENGINEERING_REVIEWER,
        institution="Osteo Vision Engineering",
        auth_source="local_unverified_session",
    )


def identity_status(actor: ReviewActorIdentity) -> ReviewIdentityStatus:
    return ReviewIdentityStatus(
        **actor.model_dump(),
        authenticated=actor.auth_source != "local_unverified_session",
    )


def can_verify_clinical_context(actor: ReviewActorIdentity) -> bool:
    return actor.role in TRUSTED_CLINICAL_REVIEW_ROLES and actor.auth_source in TRUSTED_REVIEW_AUTH_SOURCES


def _configured_identities() -> dict[str, ReviewActorIdentity]:
    raw = os.environ.get(REVIEW_IDENTITIES_ENV, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _identity_configuration_error("Review identity configuration is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise _identity_configuration_error("Review identity configuration must be a token-to-identity object")

    identities: dict[str, ReviewActorIdentity] = {}
    for token, identity_payload in payload.items():
        if not isinstance(token, str) or len(token) < MIN_REVIEW_TOKEN_LENGTH:
            raise _identity_configuration_error(
                f"Configured review tokens must contain at least {MIN_REVIEW_TOKEN_LENGTH} characters"
            )
        if not isinstance(identity_payload, dict):
            raise _identity_configuration_error("Each review identity must be an object")
        try:
            identity = ReviewActorIdentity.model_validate(identity_payload)
        except ValidationError as exc:
            raise _identity_configuration_error("Configured review identity failed validation") from exc
        identities[token] = identity
    return identities


def _constant_time_identity_lookup(
    identities: dict[str, ReviewActorIdentity],
    supplied_token: str,
) -> ReviewActorIdentity | None:
    matched: ReviewActorIdentity | None = None
    for configured_token, identity in identities.items():
        if hmac.compare_digest(configured_token.encode("utf-8"), supplied_token.encode("utf-8")):
            matched = identity
    return matched


def _credential_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_review_credentials", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _identity_configuration_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "review_identity_configuration_invalid", "message": message},
    )
