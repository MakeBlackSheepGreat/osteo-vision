from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.core.artifacts import checksum_for_file
from backend.src.domains.cases.enums import ArtifactKind
from backend.src.domains.cases.repository import CaseRepository, CaseVersionConflictError
from backend.src.domains.cases.schemas import CaseRecord, EvidenceArtifact


def persist_three_d_modeling_result(
    repo: CaseRepository | None,
    *,
    case_id: str,
    job_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Attach a completed 3D modeling result to its case when the case exists."""

    persistence = {"status": "not_requested", "case_id": case_id}
    if repo is None:
        return {**result, "case_persistence": persistence}

    case = repo.get(case_id)
    if case is None:
        return {
            **result,
            "case_persistence": {
                "status": "case_not_found",
                "case_id": case_id,
                "message": "The modeling result remains available in the job registry but was not attached to a case.",
            },
        }

    evidence = result.get("three_d_evidence")
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    modeling = {
        "schema_version": "osteo-vision-case-three-d-modeling-v1",
        "job_id": job_id,
        "modeling_status": result.get("modeling_status"),
        "input_type": result.get("input_type"),
        "source_path": result.get("source_path"),
        "source_paths": list(result.get("source_paths") or []),
        "model_path": result.get("model_path"),
        "manifest_path": result.get("manifest_path"),
        "case_persistence_status": "persisted",
    }

    for _attempt in range(3):
        updated = _case_with_three_d_result(case, evidence=evidence, modeling=modeling)
        try:
            saved = repo.save(updated)
        except CaseVersionConflictError:
            refreshed = repo.get(case_id)
            if refreshed is None:
                break
            case = refreshed
            continue
        return {
            **result,
            "case_persistence": {
                "status": "persisted",
                "case_id": case_id,
                "case_version": saved.version,
            },
        }

    raise RuntimeError(f"Unable to persist 3D modeling evidence for case {case_id} after concurrent updates")


def persist_l1_registration_result(
    repo: CaseRepository,
    *,
    case_id: str,
    job_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    case = repo.get(case_id)
    if case is None:
        return {**result, "case_persistence": {"status": "case_not_found", "case_id": case_id}}
    evidence = result.get("three_d_evidence")
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    for _attempt in range(3):
        artifacts = list(case.artifacts)
        artifacts = _append_artifact(
            artifacts,
            case_id=case_id,
            kind=ArtifactKind.THREE_D_REGISTRATION_TRANSFORM,
            path=result.get("transform_path"),
        )
        artifacts = _append_artifact(
            artifacts,
            case_id=case_id,
            kind=ArtifactKind.THREE_D_REGISTRATION_MANIFEST,
            path=result.get("registration_manifest_path"),
        )
        registration_summary = {
            "schema_version": "osteo-vision-case-l1-registration-v1",
            "job_id": job_id,
            "status": result.get("registration_status"),
            "transform_path": result.get("transform_path"),
            "transform_sha256": result.get("transform_sha256"),
            "manifest_path": result.get("registration_manifest_path"),
            "manifest_sha256": result.get("registration_manifest_sha256"),
            "error_code": result.get("error_code"),
        }
        updated = case.model_copy(
            update={
                "three_d_evidence": evidence,
                "three_d_modeling": {**case.three_d_modeling, "l1_registration": registration_summary},
                "artifacts": artifacts,
                "review_summary": {
                    **case.review_summary,
                    "three_d_registration_status": result.get("registration_status"),
                    "three_d_navigation_ready": bool(evidence.get("navigation_ready")),
                    "three_d_navigation_level": evidence.get("navigation_level") or "L0",
                },
            }
        )
        try:
            saved = repo.save(updated)
        except CaseVersionConflictError:
            refreshed = repo.get(case_id)
            if refreshed is None:
                break
            case = refreshed
            continue
        return {
            **result,
            "case_persistence": {"status": "persisted", "case_id": case_id, "case_version": saved.version},
        }
    raise RuntimeError(f"Unable to persist L1 registration evidence for case {case_id} after concurrent updates")


def persist_l2_pose_replay_result(
    repo: CaseRepository,
    *,
    case_id: str,
    job_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    case = repo.get(case_id)
    if case is None:
        return {**result, "case_persistence": {"status": "case_not_found", "case_id": case_id}}
    evidence = result.get("three_d_evidence")
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    for _attempt in range(3):
        artifacts = list(case.artifacts)
        artifacts = _append_artifact(
            artifacts,
            case_id=case_id,
            kind=ArtifactKind.THREE_D_POSE_REPLAY_MANIFEST,
            path=result.get("pose_replay_manifest_path"),
        )
        artifacts = _append_artifact(
            artifacts,
            case_id=case_id,
            kind=ArtifactKind.THREE_D_POSE_REPLAY_FRAMES,
            path=result.get("pose_replay_frames_csv_path"),
        )
        artifacts = _append_artifact(
            artifacts,
            case_id=case_id,
            kind=ArtifactKind.THREE_D_AR_OVERLAY,
            path=result.get("overlay_video_path"),
        )
        replay_summary = {
            "schema_version": "osteo-vision-case-l2-pose-replay-v1",
            "job_id": job_id,
            "status": result.get("replay_status"),
            "navigation_ready": bool(evidence.get("navigation_ready")),
            "navigation_level": evidence.get("navigation_level") or "L0",
            "manifest_path": result.get("pose_replay_manifest_path"),
            "manifest_sha256": result.get("pose_replay_manifest_sha256"),
            "frames_csv_path": result.get("pose_replay_frames_csv_path"),
            "frames_csv_sha256": result.get("pose_replay_frames_csv_sha256"),
            "overlay_video_path": result.get("overlay_video_path"),
            "overlay_video_sha256": result.get("overlay_video_sha256"),
            "error_code": result.get("error_code"),
        }
        updated = case.model_copy(
            update={
                "three_d_evidence": evidence,
                "three_d_modeling": {**case.three_d_modeling, "l2_pose_replay": replay_summary},
                "artifacts": artifacts,
                "review_summary": {
                    **case.review_summary,
                    "three_d_pose_replay_status": result.get("replay_status"),
                    "three_d_navigation_ready": bool(evidence.get("navigation_ready")),
                    "three_d_navigation_level": evidence.get("navigation_level") or "L0",
                },
            }
        )
        try:
            saved = repo.save(updated)
        except CaseVersionConflictError:
            refreshed = repo.get(case_id)
            if refreshed is None:
                break
            case = refreshed
            continue
        return {
            **result,
            "case_persistence": {"status": "persisted", "case_id": case_id, "case_version": saved.version},
        }
    raise RuntimeError(f"Unable to persist L2 pose replay evidence for case {case_id} after concurrent updates")


def _case_with_three_d_result(
    case: CaseRecord,
    *,
    evidence: dict[str, Any],
    modeling: dict[str, Any],
) -> CaseRecord:
    artifacts = list(case.artifacts)
    artifacts = _append_artifact(
        artifacts,
        case_id=case.case_id,
        kind=ArtifactKind.THREE_D_MODEL,
        path=evidence.get("model_path") or modeling.get("model_path"),
    )
    artifacts = _append_artifact(
        artifacts,
        case_id=case.case_id,
        kind=ArtifactKind.THREE_D_MODELING_MANIFEST,
        path=modeling.get("manifest_path"),
    )
    review_summary = {
        **case.review_summary,
        "three_d_evidence_available": bool(evidence),
        "three_d_model_available": bool(evidence.get("model_path")),
        "three_d_modeling_status": modeling.get("modeling_status"),
        "three_d_navigation_ready": bool(evidence.get("navigation_ready")),
    }
    return case.model_copy(
        update={
            "three_d_evidence": evidence or case.three_d_evidence,
            "three_d_modeling": modeling,
            "artifacts": artifacts,
            "review_summary": review_summary,
        }
    )


def _append_artifact(
    artifacts: list[EvidenceArtifact],
    *,
    case_id: str,
    kind: ArtifactKind,
    path: object,
) -> list[EvidenceArtifact]:
    path_text = str(path or "").strip()
    if not path_text or any(item.kind == kind and item.path == path_text for item in artifacts):
        return artifacts
    artifact_path = Path(path_text)
    checksum = checksum_for_file(artifact_path) if artifact_path.exists() and artifact_path.is_file() else None
    return [
        *artifacts,
        EvidenceArtifact(
            artifact_id=f"artifact_{uuid4().hex[:10]}",
            case_id=case_id,
            kind=kind,
            path=path_text,
            checksum=checksum,
        ),
    ]
