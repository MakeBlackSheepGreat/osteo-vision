from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.osteo_vision_api.domains.cases.enums import ReviewerRole
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.models.promotion_approval import (
    PromotionApprovalError,
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    StoredPromotionApproval,
    approval_record_hash,
    canonical_json_sha256,
    target_fingerprint,
    trust_store_fingerprint,
    verify_signed_approval,
)

EMPTY_CHAIN_HASH = "0" * 64
REQUIRED_APPROVAL_ROLES = ("physician", "project_reviewer")
TRUSTED_PROMOTION_AUTH_SOURCES = frozenset(
    {
        "institution_sso",
        "signed_session",
        "verified_identity_token",
    }
)


class PromotionApprovalRepository:
    """Append-only SQLite approval log with a transactionally maintained hash-chain anchor."""

    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        ensure_dir(self.store_path.parent)
        self._initialize()

    def append(
        self,
        submission: SignedPromotionApproval,
        *,
        recorded_at_utc: datetime,
        state_validator: Callable[[list[StoredPromotionApproval]], None] | None = None,
    ) -> StoredPromotionApproval:
        recorded_at = _utc_datetime(recorded_at_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            chain = self._verify_connection(connection)
            duplicate = connection.execute(
                "SELECT approval_id, nonce FROM promotion_approvals WHERE approval_id = ? OR nonce = ?",
                (submission.payload.approval_id, submission.payload.nonce),
            ).fetchone()
            if duplicate is not None:
                raise PromotionApprovalError(
                    "promotion_approval_replay_detected",
                    "Approval id or nonce has already been appended.",
                )
            if state_validator is not None:
                rows = connection.execute(
                    "SELECT record_json FROM promotion_approvals ORDER BY sequence ASC"
                ).fetchall()
                state_validator([_stored_record(str(row["record_json"])) for row in rows])

            sequence = int(chain["record_count"]) + 1
            previous_record_hash = str(chain["head_hash"])
            record_hash = approval_record_hash(
                sequence=sequence,
                recorded_at_utc=recorded_at,
                previous_record_hash=previous_record_hash,
                submission=submission,
            )
            record = StoredPromotionApproval(
                sequence=sequence,
                recorded_at_utc=recorded_at,
                previous_record_hash=previous_record_hash,
                record_hash=record_hash,
                submission=submission,
            )
            connection.execute(
                """
                INSERT INTO promotion_approvals(
                    sequence, approval_id, nonce, target_fingerprint, previous_record_hash,
                    record_hash, record_json, recorded_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence,
                    submission.payload.approval_id,
                    submission.payload.nonce,
                    target_fingerprint(submission.payload),
                    previous_record_hash,
                    record_hash,
                    _model_json(record),
                    recorded_at.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE promotion_approval_chain_state SET record_count = ?, head_hash = ? WHERE singleton_id = 1",
                (sequence, record_hash),
            )
        return record

    def list_records(self) -> list[StoredPromotionApproval]:
        with self._connect() as connection:
            self._verify_connection(connection)
            rows = connection.execute("SELECT record_json FROM promotion_approvals ORDER BY sequence ASC").fetchall()
        return [_stored_record(str(row["record_json"])) for row in rows]

    def get(self, approval_id: str) -> StoredPromotionApproval | None:
        with self._connect() as connection:
            self._verify_connection(connection)
            row = connection.execute(
                "SELECT record_json FROM promotion_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return None if row is None else _stored_record(str(row["record_json"]))

    def verify_chain(self) -> dict[str, Any]:
        with self._connect() as connection:
            return self._verify_connection(connection)

    def _verify_connection(self, connection: sqlite3.Connection) -> dict[str, Any]:
        rows = connection.execute("""
            SELECT sequence, approval_id, nonce, target_fingerprint, previous_record_hash,
                   record_hash, record_json, recorded_at_utc
            FROM promotion_approvals ORDER BY sequence ASC
            """).fetchall()
        previous_hash = EMPTY_CHAIN_HASH
        previous_recorded_at: datetime | None = None
        expected_sequence = 1
        for row in rows:
            record = _stored_record(str(row["record_json"]))
            if int(row["sequence"]) != expected_sequence or record.sequence != expected_sequence:
                raise PromotionApprovalError(
                    "promotion_approval_chain_sequence_invalid",
                    "Approval chain sequence is missing, duplicated, or reordered.",
                )
            if str(row["approval_id"]) != record.submission.payload.approval_id:
                raise PromotionApprovalError(
                    "promotion_approval_chain_index_mismatch",
                    "Approval chain indexed identity does not match its signed record.",
                )
            if str(row["nonce"]) != record.submission.payload.nonce:
                raise PromotionApprovalError(
                    "promotion_approval_chain_index_mismatch",
                    "Approval chain indexed nonce does not match its signed record.",
                )
            if str(row["target_fingerprint"]) != target_fingerprint(record.submission.payload):
                raise PromotionApprovalError(
                    "promotion_approval_chain_index_mismatch",
                    "Approval chain target fingerprint does not match its signed record.",
                )
            if str(row["recorded_at_utc"]) != record.recorded_at_utc.isoformat():
                raise PromotionApprovalError(
                    "promotion_approval_chain_index_mismatch",
                    "Approval chain indexed timestamp does not match its stored record.",
                )
            if previous_recorded_at is not None and record.recorded_at_utc < previous_recorded_at:
                raise PromotionApprovalError(
                    "promotion_approval_chain_timestamp_invalid",
                    "Approval chain recorded timestamps are not monotonic.",
                )
            if record.previous_record_hash != previous_hash or str(row["previous_record_hash"]) != previous_hash:
                raise PromotionApprovalError(
                    "promotion_approval_chain_link_mismatch",
                    "Approval chain previous-record hash is invalid.",
                )
            expected_hash = approval_record_hash(
                sequence=record.sequence,
                recorded_at_utc=record.recorded_at_utc,
                previous_record_hash=record.previous_record_hash,
                submission=record.submission,
            )
            if record.record_hash != expected_hash or str(row["record_hash"]) != expected_hash:
                raise PromotionApprovalError(
                    "promotion_approval_chain_hash_mismatch",
                    "Approval chain record hash does not match its stored content.",
                )
            previous_hash = expected_hash
            previous_recorded_at = record.recorded_at_utc
            expected_sequence += 1

        anchor = connection.execute(
            "SELECT record_count, head_hash FROM promotion_approval_chain_state WHERE singleton_id = 1"
        ).fetchone()
        if anchor is None:
            raise PromotionApprovalError(
                "promotion_approval_chain_anchor_missing",
                "Approval chain anchor is missing.",
            )
        if int(anchor["record_count"]) != len(rows) or str(anchor["head_hash"]) != previous_hash:
            raise PromotionApprovalError(
                "promotion_approval_chain_anchor_mismatch",
                "Approval chain anchor does not match the append-only log.",
            )
        return {
            "chain_valid": True,
            "record_count": len(rows),
            "head_hash": previous_hash,
        }

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS promotion_approvals (
                    sequence INTEGER PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    nonce TEXT NOT NULL UNIQUE,
                    target_fingerprint TEXT NOT NULL,
                    previous_record_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL UNIQUE,
                    record_json TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                )
                """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS promotion_approval_chain_state (
                    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
                    record_count INTEGER NOT NULL,
                    head_hash TEXT NOT NULL
                )
                """)
            connection.execute(
                """
                INSERT OR IGNORE INTO promotion_approval_chain_state(singleton_id, record_count, head_hash)
                VALUES (1, 0, ?)
                """,
                (EMPTY_CHAIN_HASH,),
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_promotion_approvals_target_sequence "
                "ON promotion_approvals(target_fingerprint, sequence ASC)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.store_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


class PromotionApprovalService:
    def __init__(
        self,
        repository: PromotionApprovalRepository,
        trust_store: PromotionTrustStore,
        *,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.trust_store = trust_store
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def submit(
        self,
        submission: SignedPromotionApproval,
        actor: ReviewActorIdentity,
    ) -> StoredPromotionApproval:
        now = _utc_datetime(self._now_factory())
        self._validate_authenticated_actor(actor, submission.payload)
        verify_signed_approval(submission, self.trust_store, now=now)
        return self.repository.append(
            submission,
            recorded_at_utc=now,
            state_validator=lambda records: self._validate_submission_state(
                submission.payload,
                records,
            ),
        )

    def readiness(self, reference: PromotionApprovalPayload) -> dict[str, Any]:
        now = _utc_datetime(self._now_factory())
        chain = self.repository.verify_chain()
        target_id = target_fingerprint(reference)
        target_records: list[StoredPromotionApproval] = []
        approvals: dict[str, StoredPromotionApproval] = {}
        revoked: set[str] = set()
        chain_records = self.repository.list_records()

        for record in chain_records:
            try:
                verify_signed_approval(
                    record.submission,
                    self.trust_store,
                    now=record.recorded_at_utc,
                    enforce_current_authorization=False,
                )
            except PromotionApprovalError as exc:
                raise PromotionApprovalError(
                    "promotion_approval_chain_signature_invalid",
                    f"Stored approval signature failed verification: {exc.code}",
                ) from exc
            payload = record.submission.payload
            if target_fingerprint(payload) != target_id:
                continue
            target_records.append(record)
            if payload.decision == "approve":
                approvals[payload.approval_id] = record
            elif payload.supersedes_approval_id in approvals:
                original = approvals[payload.supersedes_approval_id]
                if _same_signer(payload, original.submission.payload):
                    revoked.add(str(payload.supersedes_approval_id))

        blockers: list[dict[str, Any]] = []
        active_by_role: dict[str, StoredPromotionApproval] = {}
        for approval_id, record in approvals.items():
            if approval_id in revoked:
                continue
            try:
                verify_signed_approval(
                    record.submission,
                    self.trust_store,
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
        if missing_roles:
            blockers.append({"code": "promotion_approval_roles_incomplete", "missing_roles": missing_roles})
        active_records = [active_by_role[role] for role in REQUIRED_APPROVAL_ROLES if role in active_by_role]
        if len({record.submission.key_id for record in active_records}) != len(active_records):
            blockers.append({"code": "promotion_approval_signing_keys_not_distinct"})
        if len({record.submission.payload.signer_actor_id for record in active_records}) != len(active_records):
            blockers.append({"code": "promotion_approval_signers_not_distinct"})

        bundle = {
            "schema_version": "osteo-vision-promotion-approval-bundle-v1",
            "target_fingerprint": target_id,
            "target": _target_summary(reference),
            "trust_store_sha256": trust_store_fingerprint(self.trust_store),
            "chain_head_hash": chain["head_hash"],
            "chain_record_count": chain["record_count"],
            "chain_records": [record.model_dump(mode="json") for record in chain_records],
            "target_records": [record.model_dump(mode="json") for record in target_records],
            "active_approval_ids": [record.submission.payload.approval_id for record in active_records],
            "active_approval_count": len(active_records),
            "required_roles": list(REQUIRED_APPROVAL_ROLES),
            "missing_roles": missing_roles,
            "blockers": blockers,
            "approval_ready": not blockers and not missing_roles,
        }
        return {**bundle, "bundle_sha256": canonical_json_sha256(bundle), "chain_valid": True}

    def _validate_authenticated_actor(
        self,
        actor: ReviewActorIdentity,
        payload: PromotionApprovalPayload,
    ) -> None:
        if actor.auth_source not in TRUSTED_PROMOTION_AUTH_SOURCES:
            raise PromotionApprovalError(
                "promotion_approval_authenticated_identity_untrusted",
                "Promotion approval requires an authenticated trusted identity.",
            )
        if actor.role not in {ReviewerRole.PHYSICIAN, ReviewerRole.PROJECT_REVIEWER}:
            raise PromotionApprovalError(
                "promotion_approval_authenticated_role_forbidden",
                "Promotion approval requires physician or project reviewer authority.",
            )
        expected = (actor.actor_id, actor.role.value, actor.institution)
        actual = (payload.signer_actor_id, payload.signer_role, payload.signer_institution)
        if actual != expected:
            raise PromotionApprovalError(
                "promotion_approval_authenticated_identity_mismatch",
                "Authenticated identity does not match the signed approval payload.",
            )

    def _validate_submission_state(
        self,
        payload: PromotionApprovalPayload,
        records: list[StoredPromotionApproval],
    ) -> None:
        for record in records:
            try:
                verify_signed_approval(
                    record.submission,
                    self.trust_store,
                    now=record.recorded_at_utc,
                    enforce_current_authorization=False,
                )
            except PromotionApprovalError as exc:
                raise PromotionApprovalError(
                    "promotion_approval_chain_signature_invalid",
                    f"Stored approval signature failed verification: {exc.code}",
                ) from exc
        target_id = target_fingerprint(payload)
        target_records = [record for record in records if target_fingerprint(record.submission.payload) == target_id]
        approvals: dict[str, StoredPromotionApproval] = {}
        revoked: set[str] = set()
        for record in target_records:
            stored_payload = record.submission.payload
            if stored_payload.decision == "approve":
                approvals[stored_payload.approval_id] = record
                continue
            original = approvals.get(str(stored_payload.supersedes_approval_id))
            if original is not None and _same_signer(
                stored_payload,
                original.submission.payload,
            ):
                revoked.add(original.submission.payload.approval_id)

        if payload.decision == "approve":
            role_conflict = next(
                (
                    record
                    for approval_id, record in approvals.items()
                    if approval_id not in revoked and record.submission.payload.signer_role == payload.signer_role
                ),
                None,
            )
            if role_conflict is not None:
                raise PromotionApprovalError(
                    "promotion_approval_active_role_conflict",
                    "An active approval already exists for this target and signer role; revoke it before replacement.",
                )
            return

        original = approvals.get(str(payload.supersedes_approval_id))
        if original is None:
            raise PromotionApprovalError(
                "promotion_approval_revocation_target_missing",
                "Revocation target does not exist in the append-only approval log.",
            )
        original_payload = original.submission.payload
        if original_payload.decision != "approve" or target_fingerprint(original_payload) != target_fingerprint(
            payload
        ):
            raise PromotionApprovalError(
                "promotion_approval_revocation_target_invalid",
                "Revocation target is not an approval for the same model evidence.",
            )
        if not _same_signer(payload, original_payload):
            raise PromotionApprovalError(
                "promotion_approval_revocation_identity_mismatch",
                "Only the original signing identity may revoke an approval.",
            )
        if original_payload.approval_id in revoked:
            raise PromotionApprovalError(
                "promotion_approval_revocation_target_inactive",
                "Revocation target has already been revoked.",
            )


def load_promotion_trust_store(path: str | Path) -> PromotionTrustStore:
    trust_path = Path(path)
    if not trust_path.exists():
        return PromotionTrustStore(keys=[])
    try:
        payload = json.loads(trust_path.read_text(encoding="utf-8"))
        return PromotionTrustStore.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PromotionApprovalError(
            "promotion_approval_trust_store_invalid",
            "Promotion approval trust store is unreadable or invalid.",
        ) from exc


def _stored_record(payload: str) -> StoredPromotionApproval:
    try:
        return StoredPromotionApproval.model_validate_json(payload)
    except ValidationError as exc:
        raise PromotionApprovalError(
            "promotion_approval_chain_record_invalid",
            "Approval chain contains a malformed record.",
        ) from exc


def _model_json(model: StoredPromotionApproval) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


def _target_summary(payload: PromotionApprovalPayload) -> dict[str, str]:
    return {
        "capability": payload.capability,
        "model_id": payload.model_id,
        "checkpoint_sha256": payload.checkpoint_sha256,
        "policy_sha256": payload.policy_sha256,
        "evidence_bundle_sha256": payload.evidence_bundle_sha256,
    }


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("promotion approval timestamps must include a timezone")
    return value.astimezone(timezone.utc)
