from __future__ import annotations

import json

import numpy as np
from PIL import Image

from backend.src.services.video_segmentation_manifest import write_video_segmentation_outputs
from src.models.video_signal_masks import (
    VIDEO_SIGNAL_MASK_TAXONOMY,
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
