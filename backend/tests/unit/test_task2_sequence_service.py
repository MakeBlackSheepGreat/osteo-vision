from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from backend.osteo_vision_api.domains.cases.enums import InputChannel
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    CaseRecord,
    InputCreateRequest,
    Task2PairedSequenceManifest,
)
from backend.osteo_vision_api.services.analysis_service import AnalysisService
from backend.osteo_vision_api.services.input_service import InputService
from backend.osteo_vision_api.services.task2_sequence_service import analyze_task2_paired_sequence


def test_paired_sequence_tracks_sync_latency_and_optical_context_resets(tmp_path: Path) -> None:
    case, frame_ids = _paired_case(tmp_path, frame_count=3)
    manifest = Task2PairedSequenceManifest.model_validate(
        {
            "schema_version": "osteo-vision-task2-paired-sequence-v1",
            "sequence_id": "sequence-optical-extremes",
            "prefer_gpu": False,
            "frames": [
                _frame_reference(frame_ids[0], frame_index=0, timestamp_ms=0.0, magnification=1.3, distance=200),
                _frame_reference(frame_ids[1], frame_index=1, timestamp_ms=40.0, magnification=17.0, distance=200),
                _frame_reference(frame_ids[2], frame_index=2, timestamp_ms=80.0, magnification=17.0, distance=630),
            ],
        }
    )

    outputs, quantification, artifacts, warnings = analyze_task2_paired_sequence(
        case,
        manifest,
        run_id="run_sequence",
        output_dir=tmp_path / "output",
    )

    sequence = outputs["task2_paired_sequence"]
    assert sequence["frame_count"] == 3
    assert sequence["checks"]["all_pairs_synchronized"] is True
    assert sequence["checks"]["all_frames_registered"] is True
    assert sequence["checks"]["optical_context_complete"] is True
    assert sequence["checks"]["continuous_display_artifacts_complete"] is True
    assert sequence["summary"]["continuous_display"]["processed_frame_count"] == 3
    assert sequence["summary"]["continuous_display"]["unique_overlay_path_count"] == 3
    assert sequence["summary"]["context_reset_counts"] == {
        "magnification_change": 1,
        "working_distance_change": 1,
    }
    assert sequence["spatial_interpretation_allowed"] is True
    assert Path(sequence["manifest_path"]).is_file()
    assert len(artifacts) == 4
    assert quantification["frame_count"] == 3
    assert quantification["registration_fusion_p95_ms"] > 0
    assert quantification["continuous_display_p95_ms"] > 0
    assert any(warning["code"] == "task2_sequence_gpu_fallback_observed" for warning in warnings)
    context = outputs["latest_fusion_report"]["task2_sequence_context"]
    assert context["spatial_interpretation_allowed"] is True
    assert context["manifest_sha256"] == sequence["manifest_sha256"]


def test_paired_sequence_closes_spatial_interpretation_when_timestamps_are_unverified(tmp_path: Path) -> None:
    case, frame_ids = _paired_case(tmp_path, frame_count=2)
    manifest = Task2PairedSequenceManifest.model_validate(
        {
            "schema_version": "osteo-vision-task2-paired-sequence-v1",
            "sequence_id": "sequence-unsynchronized",
            "prefer_gpu": False,
            "frames": [
                {
                    **_frame_reference(frame_ids[0], frame_index=0, timestamp_ms=0.0, magnification=2.0, distance=300),
                    "fluorescence_timestamp_ms": 80.0,
                },
                {
                    "frame_index": 1,
                    "white_input_id": frame_ids[1][0],
                    "fluorescence_input_id": frame_ids[1][1],
                    "magnification": 2.0,
                    "working_distance_mm": 300.0,
                },
            ],
        }
    )

    outputs, _quantification, _artifacts, warnings = analyze_task2_paired_sequence(
        case,
        manifest,
        run_id="run_unsynchronized",
        output_dir=tmp_path / "output",
    )

    sequence = outputs["task2_paired_sequence"]
    assert sequence["checks"]["all_pairs_synchronized"] is False
    assert sequence["spatial_interpretation_allowed"] is False
    assert sequence["summary"]["synchronization"]["verified_pair_count"] == 0
    assert any(warning["code"] == "task2_sequence_synchronization_unverified" for warning in warnings)


def test_analysis_service_dispatches_paired_sequence_and_persists_task3_handoff(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    case, frame_ids = _paired_case(tmp_path, frame_count=2)
    repo = JsonCaseRepository(tmp_path / "cases.json")
    repo.create(case)
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models: []",
                "reports:",
                f"  output_dir: {tmp_path / 'reports'}",
                f"  visual_dir: {tmp_path / 'visual'}",
            ]
        ),
        encoding="utf-8",
    )
    service = AnalysisService(repo, config_path=str(config_path))
    monkeypatch.setattr(
        service,
        "_fused_image_ai",
        lambda **_kwargs: (
            {
                "available": False,
                "execution_state": "skipped",
                "input_contract": {},
                "boundary_assessment": {"candidate_count": 0, "candidates": []},
                "spatial_interpretation_allowed": False,
                "clinical_claim_allowed": False,
            },
            [],
        ),
    )
    manifest = {
        "schema_version": "osteo-vision-task2-paired-sequence-v1",
        "sequence_id": "sequence-platform-run",
        "prefer_gpu": False,
        "frames": [
            _frame_reference(frame_ids[0], frame_index=0, timestamp_ms=0.0, magnification=2.0, distance=300),
            _frame_reference(frame_ids[1], frame_index=1, timestamp_ms=40.0, magnification=2.0, distance=300),
        ],
    }

    updated = service.start_analysis(
        case,
        [],
        {"mode": "task2_paired_sequence", "paired_sequence_manifest": manifest},
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "task2_paired_sequence"
    assert run.fused_outputs["fused_image_ai"]["execution_state"] == "skipped"
    assert run.quantitative_summary["frame_count"] == 2
    assert run.quantitative_summary["task3_review_candidate_count"] == 0
    assert any(artifact.kind.value == "task2_sequence_manifest" for artifact in updated.artifacts)
    persisted = repo.get(case.case_id)
    assert persisted is not None
    assert persisted.analysis_runs[-1].run_id == run.run_id


def _paired_case(tmp_path: Path, *, frame_count: int) -> tuple[CaseRecord, list[tuple[str, str]]]:
    rng = np.random.default_rng(20260724)
    texture = cv2.GaussianBlur(rng.integers(0, 256, size=(160, 224), dtype=np.uint8), (5, 5), 0)
    requests: list[InputCreateRequest] = []
    for index in range(frame_count):
        white_path = tmp_path / f"white_{index}.png"
        fluorescence_path = tmp_path / f"fluorescence_{index}.png"
        Image.fromarray(np.repeat(texture[..., None], 3, axis=2)).save(white_path)
        matrix = np.asarray([[1.0, 0.0, 5.0], [0.0, 1.0, -3.0]], dtype=np.float32)
        shifted = cv2.warpAffine(texture, matrix, (texture.shape[1], texture.shape[0]), borderMode=cv2.BORDER_REFLECT)
        Image.fromarray(shifted).save(fluorescence_path)
        requests.extend(
            [
                InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(white_path)),
                InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(fluorescence_path)),
            ]
        )
    case = InputService().add_inputs(
        CaseRecord(case_id="case_task2_sequence", title="Task 2 sequence"),
        requests,
        replace_existing_channels=False,
    )
    white_ids = [asset.input_id for asset in case.inputs if asset.channel == InputChannel.WHITE_LIGHT]
    fluorescence_ids = [asset.input_id for asset in case.inputs if asset.channel == InputChannel.FLUORESCENCE]
    return case, list(zip(white_ids, fluorescence_ids, strict=True))


def _frame_reference(
    ids: tuple[str, str],
    *,
    frame_index: int,
    timestamp_ms: float,
    magnification: float,
    distance: float,
) -> dict[str, object]:
    return {
        "frame_index": frame_index,
        "white_input_id": ids[0],
        "fluorescence_input_id": ids[1],
        "white_timestamp_ms": timestamp_ms,
        "fluorescence_timestamp_ms": timestamp_ms + 3.0,
        "magnification": magnification,
        "working_distance_mm": distance,
    }
