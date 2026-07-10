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
