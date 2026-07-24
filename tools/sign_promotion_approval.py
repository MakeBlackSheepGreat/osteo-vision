from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from osteo_vision_core.models.promotion_approval import (  # noqa: E402
    PromotionApprovalError,
    PromotionApprovalPayload,
    PromotionTrustStore,
    SignedPromotionApproval,
    TrustedPromotionKey,
    public_key_pem,
    sign_approval_payload,
    target_fingerprint,
    trust_store_fingerprint,
    verify_signed_approval,
)

PRIVATE_KEY_ENV_PATHS = (
    "OSTEO_ARTIFACT_ROOT",
    "OSTEO_CASE_STORE_PATH",
    "OSTEO_ANNOTATION_STORE_PATH",
    "OSTEO_PROMOTION_APPROVAL_STORE_PATH",
    "OSTEO_JOB_STORE_PATH",
)
ALLOWED_CAPABILITIES = (
    "patient_conditioned_segmentation",
    "bone_activity_multitask",
)
ALLOWED_ROLES = ("physician", "project_reviewer")


class OfflineApprovalCliError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and sign target-domain promotion approvals with an offline Ed25519 key."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    key_parser = subparsers.add_parser(
        "generate-key",
        help="Generate an offline PKCS8 private key, public key, and one-key trust store.",
    )
    key_parser.add_argument("--private-key", type=Path, required=True)
    key_parser.add_argument("--public-key", type=Path, required=True)
    key_parser.add_argument("--trust-store", type=Path, required=True)
    key_parser.add_argument("--key-id", required=True)
    key_parser.add_argument("--actor-id", required=True)
    key_parser.add_argument("--role", choices=ALLOWED_ROLES, required=True)
    key_parser.add_argument("--institution", required=True)
    key_parser.add_argument(
        "--allowed-capability",
        choices=ALLOWED_CAPABILITIES,
        action="append",
        required=True,
    )
    key_parser.add_argument("--valid-days", type=int, default=365)

    export_parser = subparsers.add_parser(
        "export-public-key",
        help="Derive a public PEM from an existing protected offline private key.",
    )
    export_parser.add_argument("--private-key", type=Path, required=True)
    export_parser.add_argument("--public-key", type=Path, required=True)

    merge_parser = subparsers.add_parser(
        "merge-trust-stores",
        help="Merge independently exported public-key stores and verify two-role capability coverage.",
    )
    merge_parser.add_argument("--input", type=Path, action="append", required=True)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.add_argument(
        "--required-capability",
        choices=ALLOWED_CAPABILITIES,
        action="append",
        required=True,
    )

    payload_parser = subparsers.add_parser(
        "prepare-payload",
        help="Create a validated unsigned promotion approval payload for human review.",
    )
    payload_parser.add_argument("--output", type=Path, required=True)
    payload_parser.add_argument("--approval-id", required=True)
    payload_parser.add_argument(
        "--target",
        type=Path,
        help="Exact target JSON emitted by check_three_priority_model_promotion.py.",
    )
    payload_parser.add_argument("--capability", choices=ALLOWED_CAPABILITIES)
    payload_parser.add_argument("--model-id")
    payload_parser.add_argument("--checkpoint-sha256")
    payload_parser.add_argument("--policy-sha256")
    payload_parser.add_argument("--evidence-bundle-sha256")
    payload_parser.add_argument("--decision", choices=("approve", "revoke"), default="approve")
    payload_parser.add_argument("--signer-actor-id", required=True)
    payload_parser.add_argument("--signer-role", choices=ALLOWED_ROLES, required=True)
    payload_parser.add_argument("--signer-institution", required=True)
    payload_parser.add_argument("--signed-at-utc", type=_parse_utc_datetime)
    payload_parser.add_argument("--nonce")
    payload_parser.add_argument("--supersedes-approval-id")

    sign_parser = subparsers.add_parser(
        "sign",
        help="Sign a reviewed payload and verify it against a local public trust store.",
    )
    sign_parser.add_argument("--payload", type=Path, required=True)
    sign_parser.add_argument("--private-key", type=Path, required=True)
    sign_parser.add_argument("--trust-store", type=Path, required=True)
    sign_parser.add_argument("--key-id", required=True)
    sign_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        if args.command == "generate-key":
            result = _generate_key(args)
        elif args.command == "export-public-key":
            result = _export_public_key(args)
        elif args.command == "merge-trust-stores":
            result = _merge_trust_stores(args)
        elif args.command == "prepare-payload":
            result = _prepare_payload(args)
        elif args.command == "sign":
            result = _sign_payload(args)
        else:  # pragma: no cover - argparse enforces the subcommand
            raise OfflineApprovalCliError("command_invalid", "Unsupported command.")
    except (OfflineApprovalCliError, PromotionApprovalError) as exc:
        _print_error(exc.code, str(exc))
        return 2
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as exc:
        _print_error("offline_approval_input_invalid", str(exc))
        return 2

    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


def _generate_key(args: argparse.Namespace) -> dict[str, Any]:
    if args.valid_days < 1 or args.valid_days > 3650:
        raise OfflineApprovalCliError(
            "private_key_validity_invalid",
            "valid-days must be between 1 and 3650.",
        )

    private_path = _validated_private_key_output_path(args.private_key)
    public_path = _resolved_output_path(args.public_key)
    trust_store_path = _resolved_output_path(args.trust_store)
    _require_distinct_paths(private_path, public_path, trust_store_path)
    _require_outputs_absent(private_path, public_path, trust_store_path)

    now = datetime.now(timezone.utc)
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key_pem(private_key.public_key())
    trust_store = PromotionTrustStore(
        keys=[
            TrustedPromotionKey(
                key_id=args.key_id,
                public_key_pem=public_pem,
                actor_id=args.actor_id,
                role=args.role,
                institution=args.institution,
                valid_from_utc=now - timedelta(minutes=5),
                valid_until_utc=now + timedelta(days=args.valid_days),
                allowed_capabilities=list(dict.fromkeys(args.allowed_capability)),
            )
        ]
    )

    _write_bytes_exclusive(private_path, private_bytes, mode=0o600)
    try:
        _harden_private_key_permissions(private_path)
        _validate_private_key_permissions(private_path)
    except Exception:
        private_path.unlink(missing_ok=True)
        raise
    _write_text_exclusive(public_path, public_pem, mode=0o644)
    _write_json_model_exclusive(trust_store_path, trust_store, mode=0o644)
    return {
        "command": "generate-key",
        "private_key_created": True,
        "private_key_encrypted": False,
        "public_key": str(public_path),
        "trust_store": str(trust_store_path),
        "key_id": args.key_id,
        "public_key_sha256": hashlib.sha256(public_pem.encode("ascii")).hexdigest(),
        "trust_store_sha256": trust_store_fingerprint(trust_store),
    }


def _export_public_key(args: argparse.Namespace) -> dict[str, Any]:
    private_path = _validated_existing_private_key_path(args.private_key)
    public_path = _resolved_output_path(args.public_key)
    _require_distinct_paths(private_path, public_path)
    _require_outputs_absent(public_path)
    private_key = _read_private_key(private_path)
    public_pem = public_key_pem(private_key.public_key())
    _write_text_exclusive(public_path, public_pem, mode=0o644)
    return {
        "command": "export-public-key",
        "public_key": str(public_path),
        "public_key_sha256": hashlib.sha256(public_pem.encode("ascii")).hexdigest(),
    }


def _merge_trust_stores(args: argparse.Namespace) -> dict[str, Any]:
    output_path = _resolved_output_path(args.output)
    input_paths = [_resolved_existing_path(path, "promotion trust store") for path in args.input]
    _require_distinct_paths(*input_paths, output_path)
    _require_outputs_absent(output_path)
    stores = [PromotionTrustStore.model_validate(_read_json_object(path)) for path in input_paths]
    merged = PromotionTrustStore(keys=[key for store in stores for key in store.keys])
    required_capabilities = list(dict.fromkeys(args.required_capability))
    missing: list[str] = []
    now = datetime.now(timezone.utc)
    for capability in required_capabilities:
        authorized = [
            key
            for key in merged.keys
            if key.status == "active"
            and key.valid_from_utc <= now <= key.valid_until_utc
            and capability in key.allowed_capabilities
        ]
        roles = {key.role for key in authorized}
        actor_ids = {key.actor_id for key in authorized}
        key_ids = {key.key_id for key in authorized}
        if not set(ALLOWED_ROLES).issubset(roles) or len(actor_ids) < 2 or len(key_ids) < 2:
            missing.append(capability)
    if missing:
        raise OfflineApprovalCliError(
            "promotion_trust_store_two_role_coverage_missing",
            "Merged trust store lacks distinct physician and project-reviewer keys for: " + ", ".join(missing),
        )
    _write_json_model_exclusive(output_path, merged, mode=0o644)
    return {
        "command": "merge-trust-stores",
        "trust_store": str(output_path),
        "key_count": len(merged.keys),
        "required_capabilities": required_capabilities,
        "trust_store_sha256": trust_store_fingerprint(merged),
    }


def _prepare_payload(args: argparse.Namespace) -> dict[str, Any]:
    output_path = _resolved_output_path(args.output)
    _require_outputs_absent(output_path)
    target = _approval_target(args)
    payload = PromotionApprovalPayload.model_validate(
        {
            "approval_id": args.approval_id,
            **target,
            "decision": args.decision,
            "signer_actor_id": args.signer_actor_id,
            "signer_role": args.signer_role,
            "signer_institution": args.signer_institution,
            "signed_at_utc": args.signed_at_utc or datetime.now(timezone.utc),
            "nonce": args.nonce or f"nonce-{secrets.token_hex(24)}",
            "supersedes_approval_id": args.supersedes_approval_id,
        }
    )
    _write_json_model_exclusive(output_path, payload, mode=0o600)
    return {
        "command": "prepare-payload",
        "payload": str(output_path),
        "approval_id": payload.approval_id,
        "target_fingerprint": target_fingerprint(payload),
        "requires_human_review": True,
    }


def _approval_target(args: argparse.Namespace) -> dict[str, str]:
    direct = {
        "capability": args.capability,
        "model_id": args.model_id,
        "checkpoint_sha256": args.checkpoint_sha256,
        "policy_sha256": args.policy_sha256,
        "evidence_bundle_sha256": args.evidence_bundle_sha256,
    }
    if args.target is not None:
        if any(value is not None for value in direct.values()):
            raise OfflineApprovalCliError(
                "promotion_approval_target_input_conflict",
                "Use --target alone or provide all five target fields directly.",
            )
        target_path = _resolved_existing_path(args.target, "promotion approval target")
        target = _read_json_object(target_path)
    else:
        missing = [name for name, value in direct.items() if value is None]
        if missing:
            raise OfflineApprovalCliError(
                "promotion_approval_target_incomplete",
                "Missing target fields: " + ", ".join(missing),
            )
        target = direct
    expected_fields = {
        "capability",
        "model_id",
        "checkpoint_sha256",
        "policy_sha256",
        "evidence_bundle_sha256",
    }
    if set(target) != expected_fields:
        raise OfflineApprovalCliError(
            "promotion_approval_target_schema_invalid",
            "Promotion approval target must contain exactly five bound target fields.",
        )
    return {name: str(target[name]) for name in sorted(expected_fields)}


def _sign_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload_path = _resolved_existing_path(args.payload, "approval payload")
    trust_store_path = _resolved_existing_path(args.trust_store, "promotion trust store")
    output_path = _resolved_output_path(args.output)
    private_path = _validated_existing_private_key_path(args.private_key)
    _require_distinct_paths(payload_path, trust_store_path, output_path, private_path)
    _require_outputs_absent(output_path)

    payload = PromotionApprovalPayload.model_validate(_read_json_object(payload_path))
    trust_store = PromotionTrustStore.model_validate(_read_json_object(trust_store_path))
    trusted_key = trust_store.key(args.key_id)
    if trusted_key is None:
        raise OfflineApprovalCliError(
            "promotion_approval_key_unknown",
            "The requested key id is absent from the local public trust store.",
        )

    private_key = _read_private_key(private_path)
    _require_matching_public_key(private_key.public_key(), trusted_key)
    submission = SignedPromotionApproval(
        payload=payload,
        key_id=args.key_id,
        signature_b64=sign_approval_payload(payload, private_key),
    )
    local_trust_store = PromotionTrustStore(keys=[trusted_key])
    verify_signed_approval(submission, local_trust_store, now=datetime.now(timezone.utc))
    _write_json_model_exclusive(output_path, submission, mode=0o600)
    return {
        "command": "sign",
        "signed_approval": str(output_path),
        "approval_id": payload.approval_id,
        "key_id": args.key_id,
        "target_fingerprint": target_fingerprint(payload),
        "self_verified": True,
        "trust_store_sha256": trust_store_fingerprint(trust_store),
    }


def _validated_private_key_output_path(path: Path) -> Path:
    resolved = _resolved_output_path(path)
    _reject_forbidden_private_key_location(resolved)
    return resolved


def _validated_existing_private_key_path(path: Path) -> Path:
    if path.is_symlink():
        raise OfflineApprovalCliError(
            "private_key_symlink_forbidden",
            "Private key paths may not be symbolic links.",
        )
    resolved = _resolved_existing_path(path, "private key")
    _reject_forbidden_private_key_location(resolved)
    _validate_private_key_permissions(resolved)
    return resolved


def _reject_forbidden_private_key_location(path: Path) -> None:
    for root in _forbidden_private_key_roots():
        if _is_within(path, root):
            raise OfflineApprovalCliError(
                "private_key_location_forbidden",
                f"Private keys must remain outside the repository and backend artifact roots: {root}",
            )


def _forbidden_private_key_roots() -> list[Path]:
    roots = [ROOT, ROOT / "backend", ROOT / "artifacts"]
    for name in PRIVATE_KEY_ENV_PATHS:
        raw_value = os.environ.get(name)
        if not raw_value:
            continue
        candidate = Path(raw_value).expanduser().resolve(strict=False)
        roots.append(candidate if name == "OSTEO_ARTIFACT_ROOT" else candidate.parent)
    unique: dict[str, Path] = {}
    for root in roots:
        unique[os.path.normcase(str(root.resolve(strict=False)))] = root.resolve(strict=False)
    return list(unique.values())


def _validate_private_key_permissions(path: Path) -> None:
    file_stat = path.stat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise OfflineApprovalCliError(
            "private_key_file_invalid",
            "Private key input must be a regular file.",
        )
    if file_stat.st_nlink != 1:
        raise OfflineApprovalCliError(
            "private_key_hardlink_forbidden",
            "Private key files with multiple hard links are rejected.",
        )
    if os.name == "nt":
        _validate_windows_private_key_acl(path)
        return
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise OfflineApprovalCliError(
            "private_key_permissions_too_broad",
            "Private key permissions must deny all group and other access.",
        )


def _harden_private_key_permissions(path: Path) -> None:
    os.chmod(path, 0o600)
    if os.name != "nt":
        return
    principal = _windows_current_principal()
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:(F)"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise OfflineApprovalCliError(
            "private_key_acl_hardening_failed",
            "Windows ACL hardening failed; the generated key must not be used.",
        )


def _validate_windows_private_key_acl(path: Path) -> None:
    result = subprocess.run(
        ["icacls", str(path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise OfflineApprovalCliError(
            "private_key_acl_unverifiable",
            "Windows private-key ACL could not be verified.",
        )
    principals = _windows_acl_principals(result.stdout, path)
    if not principals:
        raise OfflineApprovalCliError(
            "private_key_acl_unverifiable",
            "Windows private-key ACL contains no parseable access entries.",
        )
    allowed = {
        _normalize_principal(_windows_current_principal()),
        _normalize_principal(getpass.getuser()),
        "nt authority\\system",
        "builtin\\administrators",
        "s-1-5-18",
        "s-1-5-32-544",
    }
    unexpected = sorted(principal for principal in principals if _normalize_principal(principal) not in allowed)
    if unexpected:
        raise OfflineApprovalCliError(
            "private_key_permissions_too_broad",
            "Windows private-key ACL grants access to an unapproved principal.",
        )


def _windows_acl_principals(output: str, path: Path) -> list[str]:
    principals: list[str] = []
    path_text = str(path)
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.casefold().startswith(path_text.casefold()):
            line = line[len(path_text) :].strip()
        marker = line.find(":(")
        if marker <= 0:
            continue
        principal = line[:marker].strip()
        if principal:
            principals.append(principal)
    return principals


def _windows_current_principal() -> str:
    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    return f"{domain}\\{username}" if domain else username


def _normalize_principal(value: str) -> str:
    return value.strip().casefold()


def _read_private_key(path: Path) -> Ed25519PrivateKey:
    try:
        loaded = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (TypeError, ValueError) as exc:
        raise OfflineApprovalCliError(
            "promotion_approval_private_key_invalid",
            "Private key is not an unencrypted Ed25519 PKCS8 PEM key.",
        ) from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise OfflineApprovalCliError(
            "promotion_approval_private_key_invalid",
            "Private key algorithm must be Ed25519.",
        )
    return loaded


def _require_matching_public_key(public_key: Ed25519PublicKey, trusted_key: TrustedPromotionKey) -> None:
    try:
        trusted_public = serialization.load_pem_public_key(trusted_key.public_key_pem.encode("ascii"))
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise OfflineApprovalCliError(
            "promotion_approval_public_key_invalid",
            "Trusted public key is not valid PEM.",
        ) from exc
    if not isinstance(trusted_public, Ed25519PublicKey):
        raise OfflineApprovalCliError(
            "promotion_approval_public_key_invalid",
            "Trusted public key algorithm must be Ed25519.",
        )
    derived_raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    trusted_raw = trusted_public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if not secrets.compare_digest(derived_raw, trusted_raw):
        raise OfflineApprovalCliError(
            "promotion_approval_private_key_mismatch",
            "Offline private key does not match the selected trusted public key.",
        )


def _resolved_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _resolved_existing_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise OfflineApprovalCliError(
            "offline_approval_input_invalid",
            f"The {label} path must point to a regular file.",
        )
    return resolved


def _require_outputs_absent(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise OfflineApprovalCliError(
            "offline_approval_output_exists",
            "Refusing to overwrite an existing output file.",
        )


def _require_distinct_paths(*paths: Path) -> None:
    normalized = [os.path.normcase(str(path.resolve(strict=False))) for path in paths]
    if len(normalized) != len(set(normalized)):
        raise OfflineApprovalCliError(
            "offline_approval_paths_collide",
            "Input and output paths must be distinct.",
        )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _write_bytes_exclusive(path: Path, payload: bytes, *, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_text_exclusive(path: Path, payload: str, *, mode: int) -> None:
    _write_bytes_exclusive(path, payload.encode("utf-8"), mode=mode)


def _write_json_model_exclusive(path: Path, model: Any, *, mode: int) -> None:
    encoded = json.dumps(model.model_dump(mode="json", exclude_none=False), ensure_ascii=False, indent=2) + "\n"
    _write_text_exclusive(path, encoded, mode=mode)


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OfflineApprovalCliError(
            "offline_approval_input_invalid",
            "Approval JSON inputs must contain one object.",
        )
    return value


def _parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _print_error(code: str, message: str) -> None:
    print(
        json.dumps(
            {"ok": False, "error": {"code": code, "message": message}},
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
