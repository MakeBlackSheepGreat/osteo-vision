from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS = 24
CLINICAL_CONTEXT_VERIFICATION_FUTURE_TOLERANCE_SECONDS = 60

TRUSTED_CLINICAL_REVIEW_ROLE_VALUES = frozenset({"physician", "project_reviewer"})
TRUSTED_REVIEW_AUTH_SOURCES = frozenset(
    {
        "institution_sso",
        "signed_session",
        "verified_identity_token",
    }
)


def clinical_context_verification_issues(
    snapshot: Mapping[str, Any],
    *,
    reference_time: datetime | None = None,
) -> list[str]:
    actor = snapshot.get("verified_by")
    issues: list[str] = []
    if not isinstance(actor, Mapping):
        issues.append("clinical_context_verified_by_missing")
    else:
        if str(actor.get("role") or "").strip() not in TRUSTED_CLINICAL_REVIEW_ROLE_VALUES:
            issues.append("clinical_context_verified_actor_role_untrusted")
        if str(actor.get("auth_source") or "").strip() not in TRUSTED_REVIEW_AUTH_SOURCES:
            issues.append("clinical_context_verified_actor_auth_source_untrusted")
        if not str(actor.get("institution") or "").strip():
            issues.append("clinical_context_verified_actor_institution_missing")

    verified_at = _parse_utc_datetime(snapshot.get("verified_at"))
    if snapshot.get("verified_at") is None:
        issues.append("clinical_context_verified_at_missing")
    elif verified_at is None:
        issues.append("clinical_context_verified_at_invalid")
    else:
        now = _as_utc(reference_time or datetime.now(timezone.utc))
        age = now - verified_at
        if age < -timedelta(seconds=CLINICAL_CONTEXT_VERIFICATION_FUTURE_TOLERANCE_SECONDS):
            issues.append("clinical_context_verified_at_in_future")
        elif age > timedelta(hours=CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS):
            issues.append("clinical_context_verification_expired")
    return issues


def _parse_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
