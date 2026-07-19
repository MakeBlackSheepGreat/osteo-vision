from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from src.models.promotion_approval import (
    PromotionApprovalError,
    PromotionTrustStore,
    SignedPromotionApproval,
    verify_signed_approval,
)

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "sign_promotion_approval.py"


@pytest.fixture
def offline_tmp_path() -> Path:
    with tempfile.TemporaryDirectory(prefix="osteo-vision-offline-approval-") as directory:
        path = Path(directory).resolve()
        assert ROOT not in path.parents
        yield path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _generate_key(tmp_path: Path) -> tuple[Path, Path, Path, subprocess.CompletedProcess[str]]:
    private_key = tmp_path / "offline" / "physician.private.pem"
    public_key = tmp_path / "exchange" / "physician.public.pem"
    trust_store = tmp_path / "exchange" / "promotion_trust_store.json"
    result = _run(
        "generate-key",
        "--private-key",
        str(private_key),
        "--public-key",
        str(public_key),
        "--trust-store",
        str(trust_store),
        "--key-id",
        "physician-key-001",
        "--actor-id",
        "doctor-chen-001",
        "--role",
        "physician",
        "--institution",
        "Mianyang Third People's Hospital",
        "--allowed-capability",
        "patient_conditioned_segmentation",
    )
    return private_key, public_key, trust_store, result


def _prepare_payload(
    tmp_path: Path,
    *,
    actor_id: str = "doctor-chen-001",
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    payload = tmp_path / f"payload-{actor_id}.json"
    result = _run(
        "prepare-payload",
        "--output",
        str(payload),
        "--approval-id",
        f"approval-{uuid.uuid4().hex}",
        "--capability",
        "patient_conditioned_segmentation",
        "--model-id",
        "patient-conditioned-v1",
        "--checkpoint-sha256",
        "1" * 64,
        "--policy-sha256",
        "2" * 64,
        "--evidence-bundle-sha256",
        "3" * 64,
        "--signer-actor-id",
        actor_id,
        "--signer-role",
        "physician",
        "--signer-institution",
        "Mianyang Third People's Hospital",
    )
    return payload, result


def test_cli_generates_protected_key_and_public_trust_material_without_leaking_private_key(
    offline_tmp_path: Path,
) -> None:
    private_key, public_key, trust_store_path, result = _generate_key(offline_tmp_path)

    assert result.returncode == 0, result.stderr
    assert private_key.exists()
    assert public_key.exists()
    assert trust_store_path.exists()
    private_pem = private_key.read_text(encoding="ascii")
    assert "BEGIN PRIVATE KEY" in private_pem
    assert "PRIVATE KEY" not in result.stdout
    assert private_pem not in result.stdout
    assert private_pem not in result.stderr

    trust_store = PromotionTrustStore.model_validate_json(trust_store_path.read_text(encoding="utf-8"))
    trusted_key = trust_store.key("physician-key-001")
    assert trusted_key is not None
    assert trusted_key.actor_id == "doctor-chen-001"
    assert trusted_key.allowed_capabilities == ["patient_conditioned_segmentation"]
    assert trusted_key.public_key_pem == public_key.read_text(encoding="ascii")

    second = _run(
        "generate-key",
        "--private-key",
        str(private_key),
        "--public-key",
        str(public_key),
        "--trust-store",
        str(trust_store_path),
        "--key-id",
        "physician-key-001",
        "--actor-id",
        "doctor-chen-001",
        "--role",
        "physician",
        "--institution",
        "Mianyang Third People's Hospital",
        "--allowed-capability",
        "patient_conditioned_segmentation",
    )
    assert second.returncode == 2
    assert json.loads(second.stderr)["error"]["code"] == "offline_approval_output_exists"
    assert private_key.read_text(encoding="ascii") == private_pem


def test_cli_merges_distinct_two_role_public_trust_stores(offline_tmp_path: Path) -> None:
    _, _, physician_store, physician_result = _generate_key(offline_tmp_path)
    assert physician_result.returncode == 0, physician_result.stderr
    reviewer_store = offline_tmp_path / "exchange" / "reviewer.trust-store.json"
    reviewer_result = _run(
        "generate-key",
        "--private-key",
        str(offline_tmp_path / "offline" / "reviewer.private.pem"),
        "--public-key",
        str(offline_tmp_path / "exchange" / "reviewer.public.pem"),
        "--trust-store",
        str(reviewer_store),
        "--key-id",
        "project-reviewer-key-001",
        "--actor-id",
        "project-safety-owner-001",
        "--role",
        "project_reviewer",
        "--institution",
        "Osteo Vision Project",
        "--allowed-capability",
        "patient_conditioned_segmentation",
    )
    assert reviewer_result.returncode == 0, reviewer_result.stderr
    merged_path = offline_tmp_path / "exchange" / "merged.trust-store.json"

    merged_result = _run(
        "merge-trust-stores",
        "--input",
        str(physician_store),
        "--input",
        str(reviewer_store),
        "--output",
        str(merged_path),
        "--required-capability",
        "patient_conditioned_segmentation",
    )

    assert merged_result.returncode == 0, merged_result.stderr
    merged = PromotionTrustStore.model_validate_json(merged_path.read_text(encoding="utf-8"))
    assert len(merged.keys) == 2
    assert {key.role for key in merged.keys} == {"physician", "project_reviewer"}

    incomplete_result = _run(
        "merge-trust-stores",
        "--input",
        str(physician_store),
        "--output",
        str(offline_tmp_path / "exchange" / "incomplete.trust-store.json"),
        "--required-capability",
        "patient_conditioned_segmentation",
    )
    assert incomplete_result.returncode == 2
    assert json.loads(incomplete_result.stderr)["error"]["code"] == "promotion_trust_store_two_role_coverage_missing"


def test_cli_prepares_signs_and_self_verifies_approval_while_tampering_fails(
    offline_tmp_path: Path,
) -> None:
    private_key, _, trust_store_path, key_result = _generate_key(offline_tmp_path)
    assert key_result.returncode == 0, key_result.stderr
    payload_path, payload_result = _prepare_payload(offline_tmp_path)
    assert payload_result.returncode == 0, payload_result.stderr
    signed_path = offline_tmp_path / "signed" / "promotion_approval.json"

    sign_result = _run(
        "sign",
        "--payload",
        str(payload_path),
        "--private-key",
        str(private_key),
        "--trust-store",
        str(trust_store_path),
        "--key-id",
        "physician-key-001",
        "--output",
        str(signed_path),
    )

    assert sign_result.returncode == 0, sign_result.stderr
    assert json.loads(sign_result.stdout)["self_verified"] is True
    submission = SignedPromotionApproval.model_validate_json(signed_path.read_text(encoding="utf-8"))
    trust_store = PromotionTrustStore.model_validate_json(trust_store_path.read_text(encoding="utf-8"))
    verify_signed_approval(submission, trust_store)
    assert "PRIVATE KEY" not in signed_path.read_text(encoding="utf-8")

    tampered = submission.model_copy(
        update={"payload": submission.payload.model_copy(update={"checkpoint_sha256": "4" * 64})}
    )
    with pytest.raises(PromotionApprovalError) as exc_info:
        verify_signed_approval(tampered, trust_store)
    assert exc_info.value.code == "promotion_approval_signature_invalid"


def test_cli_prepares_payload_from_exact_gate_target(offline_tmp_path: Path) -> None:
    target = {
        "capability": "patient_conditioned_segmentation",
        "model_id": "patient-conditioned-v1",
        "checkpoint_sha256": "1" * 64,
        "policy_sha256": "2" * 64,
        "evidence_bundle_sha256": "3" * 64,
    }
    target_path = offline_tmp_path / "exchange" / "approval-target.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(target), encoding="utf-8")
    payload_path = offline_tmp_path / "payload-from-target.json"

    result = _run(
        "prepare-payload",
        "--output",
        str(payload_path),
        "--approval-id",
        "approval-from-target-001",
        "--target",
        str(target_path),
        "--signer-actor-id",
        "doctor-chen-001",
        "--signer-role",
        "physician",
        "--signer-institution",
        "Mianyang Third People's Hospital",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert {name: payload[name] for name in target} == target


def test_cli_rejects_identity_mismatch_before_writing_signed_output(offline_tmp_path: Path) -> None:
    private_key, _, trust_store_path, key_result = _generate_key(offline_tmp_path)
    assert key_result.returncode == 0, key_result.stderr
    payload_path, payload_result = _prepare_payload(offline_tmp_path, actor_id="different-doctor")
    assert payload_result.returncode == 0, payload_result.stderr
    signed_path = offline_tmp_path / "signed" / "mismatched.json"

    result = _run(
        "sign",
        "--payload",
        str(payload_path),
        "--private-key",
        str(private_key),
        "--trust-store",
        str(trust_store_path),
        "--key-id",
        "physician-key-001",
        "--output",
        str(signed_path),
    )

    assert result.returncode == 2
    assert json.loads(result.stderr)["error"]["code"] == "promotion_approval_key_identity_mismatch"
    assert not signed_path.exists()


def test_cli_rejects_private_key_paths_inside_repository(tmp_path: Path) -> None:
    forbidden_private = ROOT / ".codex_tmp" / f"{uuid.uuid4().hex}.private.pem"
    result = _run(
        "generate-key",
        "--private-key",
        str(forbidden_private),
        "--public-key",
        str(tmp_path / "public.pem"),
        "--trust-store",
        str(tmp_path / "trust.json"),
        "--key-id",
        "physician-key-001",
        "--actor-id",
        "doctor-chen-001",
        "--role",
        "physician",
        "--institution",
        "Mianyang Third People's Hospital",
        "--allowed-capability",
        "patient_conditioned_segmentation",
    )

    assert result.returncode == 2
    assert json.loads(result.stderr)["error"]["code"] == "private_key_location_forbidden"
    assert not forbidden_private.exists()


def test_backend_service_has_no_private_key_loader_or_private_key_setting() -> None:
    backend_python = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "backend" / "src").rglob("*.py"))

    assert "load_pem_private_key" not in backend_python
    assert "Ed25519PrivateKey" not in backend_python
    assert "OSTEO_PROMOTION_PRIVATE_KEY" not in backend_python
