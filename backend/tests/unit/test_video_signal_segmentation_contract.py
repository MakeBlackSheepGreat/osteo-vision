from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.osteo_vision_api.services.video_segmentation_manifest import write_video_segmentation_outputs
from osteo_vision_core.models.video_signal_masks import (
    VIDEO_SIGNAL_MASK_TAXONOMY,
    derive_bone_activity_candidates,
    save_bone_activity_candidate_maps,
    save_video_signal_maps,
    video_signal_mask_contract,
)


def test_video_signal_mask_contract_keeps_bone_gate_pending(tmp_path) -> None:
    probability = np.array([[0.1, 0.7], [0.55, 0.95]], dtype=np.float32)
    mask = (probability >= 0.6).astype(np.uint8)

    paths = save_video_signal_maps(
        probability=probability,
        mask=mask,
        uncertainty=None,
        output_dir=tmp_path,
        safe_case="case_001",
        model_id="signal",
        threshold=0.6,
    )
    contract = video_signal_mask_contract(
        mask_path="mask.png",
        risk_mask_path=paths["risk_mask_path"],
        uncertain_mask_path=paths["uncertain_mask_path"],
        width=2,
        height=2,
        positive_area_px=int(mask.sum()),
        threshold=0.6,
        source="unit_test",
        risk_summary=paths["risk_summary"],
    )

    assert set(VIDEO_SIGNAL_MASK_TAXONOMY) >= {"exposed_bone", "fluorescence_hotspot", "boundary_risk", "uncertain"}
    assert contract["bone_gate_mask"]["available"] is False
    assert contract["bone_gate_mask"]["status"] == "not_available_pending_review"
    assert contract["fluorescence_signal_mask"]["available"] is True
    assert contract["risk_mask"]["available"] is True
    assert contract["uncertain_mask"]["available"] is True
    spectrum = contract["bone_activity_spectrum"]
    assert spectrum["available"] is False
    assert spectrum["status"] == "pending_reviewed_bone_gate"
    assert spectrum["calibration_status"] == "pending_target_domain_validation"
    assert spectrum["spatial_effect_applied"] is False
    assert "切除成功率" in spectrum["confidence_statement"]


def test_activity_candidates_require_reviewed_bone_gate() -> None:
    probability = np.array([[0.1, 0.4], [0.7, 0.9]], dtype=np.float32)
    gate = np.ones((2, 2), dtype=np.uint8)

    pending = derive_bone_activity_candidates(
        probability=probability,
        threshold=0.6,
        bone_gate=gate,
        bone_gate_status="prompt_assisted_review",
    )
    assert pending["available"] is False
    assert pending["low_activity_candidate"]["available"] is False

    reviewed = derive_bone_activity_candidates(
        probability=probability,
        threshold=0.6,
        bone_gate=gate,
        bone_gate_status="physician_accepted",
    )
    assert reviewed["available"] is True
    assert reviewed["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert reviewed["spatial_effect_applied"] is True
    assert reviewed["low_activity_candidate"]["positive_area_px"] == 1
    assert reviewed["transition_candidate"]["positive_area_px"] == 1
    assert reviewed["high_activity_candidate"]["positive_area_px"] == 2
    assert reviewed["ignore_region"]["positive_area_px"] == 0
    assert reviewed["partition_check"]["valid"] is True


def test_activity_candidates_partition_reviewed_bone_with_explicit_ignore(tmp_path) -> None:
    probability = np.array([[0.1, 0.4, 0.7], [0.9, 0.2, 0.8]], dtype=np.float32)
    gate = np.array([[1, 1, 1], [1, 1, 0]], dtype=np.uint8)
    ignored = np.array([[0, 1, 0], [0, 0, 1]], dtype=np.uint8)

    spectrum = save_bone_activity_candidate_maps(
        probability=probability,
        bone_gate=gate,
        threshold=0.6,
        ignore_mask=ignored,
        ignore_sources=[{"source_type": "unit_test", "path": "ignore.png", "sha256": "a" * 64}],
        output_dir=tmp_path,
        safe_case="partition",
    )

    assert spectrum["ignore_region"]["available"] is True
    assert spectrum["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert spectrum["ignore_region"]["positive_area_px"] == 1
    assert spectrum["ignore_region"]["bone_gate_fraction"] == 0.2
    assert spectrum["ignore_region"]["sources"][0]["source_type"] == "unit_test"
    assert Path(spectrum["ignore_region"]["path"]).is_file()
    assert len(spectrum["ignore_region"]["sha256"]) == 64
    assert spectrum["class_map_encoding"] == {
        "0": "outside_reviewed_bone_gate",
        "1": "low_activity_candidate",
        "2": "transition_candidate",
        "3": "high_activity_candidate",
        "4": "ignore_region",
    }
    assert spectrum["partition_check"] == {
        "valid": True,
        "reviewed_bone_px": 5,
        "classified_px": 4,
        "ignore_px": 1,
        "union_px": 5,
        "overlap_px": 0,
        "outside_gate_px": 0,
        "uncovered_gate_px": 0,
    }
    with Image.open(spectrum["activity_class_map_path"]) as image:
        class_map = np.asarray(image, dtype=np.uint8)
    assert class_map[0, 1] == 4
    assert class_map[1, 2] == 0


def test_activity_candidates_reject_ignore_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="ignore_mask shape"):
        derive_bone_activity_candidates(
            probability=np.ones((2, 2), dtype=np.float32),
            threshold=0.5,
            bone_gate=np.ones((2, 2), dtype=np.uint8),
            bone_gate_status="physician_accepted",
            ignore_mask=np.ones((1, 2), dtype=np.uint8),
        )


def test_video_segmentation_manifest_writes_signal_masks_and_risk_summary(tmp_path) -> None:
    overlay_path = tmp_path / "overlay.png"
    mask_path = tmp_path / "mask.png"
    risk_path = tmp_path / "risk.png"
    uncertain_path = tmp_path / "uncertain.png"
    for path in (overlay_path, mask_path, risk_path, uncertain_path):
        Image.fromarray(np.full((8, 8), 128, dtype=np.uint8)).save(path)
    signal_masks = video_signal_mask_contract(
        mask_path=str(mask_path),
        risk_mask_path=str(risk_path),
        uncertain_mask_path=str(uncertain_path),
        width=8,
        height=8,
        positive_area_px=16,
        threshold=0.6,
        source="unit_test",
        overlay_path=str(overlay_path),
    )
    frame_details = [
        {
            "frame_key": "1-0",
            "frame_order": 1,
            "frame_index": 10,
            "timestamp_sec": 2.5,
            "evidence_path": str(overlay_path),
            "overlay_path": str(overlay_path),
            "mask_path": str(mask_path),
            "risk_mask_path": str(risk_path),
            "uncertain_mask_path": str(uncertain_path),
            "positive_area_fraction": 0.25,
            "component_count": 1,
            "signal_masks": signal_masks,
            "video_signal_segmentation": signal_masks,
            "review_required": True,
            "review_priority": "high",
        }
    ]
    hotspot_outputs = [
        {
            "frame_order": 1,
            "frame_index": 10,
            "timestamp_sec": 2.5,
            "model_id": "video_keyframe_hotspot_segmenter",
            "analysis_method": "heuristic_hotspot_fallback",
            "segmentation_mask": {"path": str(mask_path), "risk_mask_path": str(risk_path), "width": 8, "height": 8},
            "lesion_evidence": {"overlay_path": str(overlay_path), "uncertain_mask_path": str(uncertain_path)},
            "quantification": {"positive_area_fraction": 0.25, "component_count": 1},
            "signal_masks": signal_masks,
        }
    ]

    outputs = write_video_segmentation_outputs(
        tmp_path / "out",
        case_id="case_video_signal",
        run_id="run_001",
        source_path="source.mp4",
        keyframe_report={"fps": 2.0, "width": 3840, "height": 2160, "frame_count": 30, "duration_sec": 15},
        frame_details=frame_details,
        hotspot_outputs=hotspot_outputs,
        three_d_evidence={
            "model_path": "artifacts/models/case_001_mandible.glb",
            "registration_status": "unregistered",
            "navigation_ready": False,
        },
    )
    manifest = json.loads((tmp_path / "out" / "video_segmentation_manifest.json").read_text(encoding="utf-8"))

    assert outputs["summary"]["risk_frame_count"] == 1
    assert outputs["summary"]["analysis_scope"] == "selected_mp4_keyframes_video_signal_segmentation"
    assert outputs["summary"]["three_d_evidence_available"] is True
    assert outputs["summary"]["three_d_registration_status"] == "unregistered"
    assert manifest["three_d_evidence"]["model_path"] == "artifacts/models/case_001_mandible.glb"
    assert manifest["frames"][0]["video_signal_segmentation"]["bone_gate_mask"]["status"] == (
        "not_available_pending_review"
    )
    assert manifest["frames"][0]["video_signal_segmentation"]["risk_mask"]["path"] == str(risk_path)
    spectrum = manifest["frames"][0]["video_signal_segmentation"]["bone_activity_spectrum"]
    assert spectrum["schema_version"] == "osteo-vision-bone-activity-spectrum-v2"
    assert spectrum["ignore_region"]["sources"][0]["source_type"] == "compatibility_default_empty"
    assert spectrum["class_map_encoding"]["4"] == "ignore_region"
    assert manifest["summary"]["video_signal_outputs"][-1] == "bone_activity_spectrum"


def test_realtime_manifest_requires_explicit_display_permission(tmp_path) -> None:
    image_path = tmp_path / "frame.png"
    Image.fromarray(np.full((8, 8), 128, dtype=np.uint8)).save(image_path)

    outputs = write_video_segmentation_outputs(
        tmp_path / "live",
        case_id="case_live",
        run_id="run_live",
        source_path="rtsp://example.test/live",
        keyframe_report={"fps": 2.0, "width": 8, "height": 8},
        frame_details=[
            {
                "frame_key": "1-0",
                "frame_order": 1,
                "frame_index": 0,
                "evidence_path": str(image_path),
                "overlay_path": str(image_path),
                "mask_path": str(image_path),
                "risk_mask_path": str(image_path),
            }
        ],
        hotspot_outputs=[{"frame_order": 1, "frame_index": 0}],
        analysis_mode="realtime_stream_keyframes",
    )

    assert outputs["summary"]["captured_frame_count"] == 1
    assert outputs["summary"]["selected_frame_count"] == 0
    assert outputs["summary"]["analysis_available"] is False
    assert outputs["segmentation_review_video_path"] is None
