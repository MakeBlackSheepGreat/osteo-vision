from __future__ import annotations

import hashlib
from pathlib import Path

from backend.osteo_vision_api.domains.cases.enums import ArtifactKind
from backend.osteo_vision_api.services.analysis_outputs import (
    fusion_ai_artifacts,
    fusion_ai_candidate_regions,
    patient_conditioning_artifacts,
    three_channel_quality_artifacts,
)


def test_task3_candidates_fail_closed_for_invalid_numeric_metadata() -> None:
    evidence = {
        "boundary_assessment": {
            "candidates": [
                {
                    "candidate_id": "candidate-1",
                    "score": "NaN",
                    "confidence": "invalid",
                    "boundary_type": "uncertain_boundary",
                }
            ]
        },
        "input_contract": {"model_input": {"dimensions": "invalid"}},
    }

    candidates = fusion_ai_candidate_regions("run-1", evidence, max_per_boundary_type="invalid")  # type: ignore[arg-type]

    assert len(candidates) == 1
    assert candidates[0].score == 0.0
    assert candidates[0].confidence == 0.0
    assert candidates[0].metadata["image_width"] is None
    assert candidates[0].metadata["image_height"] is None


def test_verified_artifact_builders_deduplicate_and_ignore_stale_paths(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"evidence": true}\n', encoding="utf-8")
    expected_checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()

    fusion_artifacts = fusion_ai_artifacts(
        "case-1",
        "run-1",
        {
            "input_contract": {"contract_path": artifact},
            "boundary_assessment": {"summary_path": artifact},
            "lesion_evidence": {"mask_path": tmp_path / "missing.png"},
        },
    )
    patient_artifacts = patient_conditioning_artifacts(
        "case-1",
        "run-1",
        {
            "image_only_probability_path": artifact,
            "conditioned_probability_path": artifact,
            "uncertainty_path": tmp_path / "missing.png",
        },
    )
    quality_artifacts = three_channel_quality_artifacts(
        "case-1",
        "run-1",
        {"report_path": artifact, "overlay_comparison": "invalid"},
    )

    assert len(fusion_artifacts) == 1
    assert fusion_artifacts[0].kind is ArtifactKind.REPORT_JSON
    assert fusion_artifacts[0].checksum == expected_checksum
    assert len(patient_artifacts) == 1
    assert patient_artifacts[0].kind is ArtifactKind.PROBABILITY_MAP
    assert len(quality_artifacts) == 1
    assert quality_artifacts[0].kind is ArtifactKind.THREE_CHANNEL_QC_REPORT
