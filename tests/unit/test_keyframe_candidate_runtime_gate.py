from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from tools.build_keyframe_candidate_runtime_gate import build_candidate_runtime_gate


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_candidate_runtime_gate_requires_4k_preflight_and_keeps_production_config_unselected(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "candidate.pt"
    checkpoint.write_bytes(b"candidate")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    model_id = "candidate_residual"
    selection = _write_json(
        tmp_path / "selection.json",
        {
            "recommendation": {
                "selected_family": "residual_attention_unet_keyframe_segmenter",
                "selected_model_id": model_id,
                "selected_checkpoint": str(checkpoint),
            },
            "candidate_families": [
                {
                    "model_family": "residual_attention_unet_keyframe_segmenter",
                    "gates": {
                        "minimum_seed_count_passed": True,
                        "all_seeds_above_baseline_dice_and_iou": True,
                    },
                }
            ],
        },
    )
    promotion = _write_json(
        tmp_path / "promotion.json",
        {
            "checkpoint_sha256": digest,
            "model_id": model_id,
            "model_family": "residual_attention_unet_keyframe_segmenter",
            "threshold": 0.4,
            "runtime_allowed": True,
            "clinical_claim_allowed": False,
        },
    )
    smoke = _write_json(
        tmp_path / "smoke.json",
        {
            "checkpoint": {"sha256": digest},
            "input": {"width": 3840, "height": 2160, "is_official_4k_resolution": True},
            "inference": {
                "mode": "tiled",
                "tile_size": 512,
                "tile_overlap": 64,
                "tile_count": 45,
                "tile_batch_size": 4,
                "tta_enabled": False,
                "use_amp": False,
                "output_profile": "full_evidence",
                "benchmark_runs": 3,
                "end_to_end_latency_ms_p95": 5500.0,
            },
            "checks": {"pass": True},
            "gate_policy": {},
        },
    )
    comparator = _write_json(
        tmp_path / "comparator.json",
        {
            "model_id": "mainline",
            "input": {"width": 3840, "height": 2160, "is_official_4k_resolution": True},
            "inference": {
                "mode": "tiled",
                "tile_size": 512,
                "tile_overlap": 64,
                "tile_count": 45,
                "tile_batch_size": 4,
                "tta_enabled": False,
                "use_amp": False,
                "output_profile": "full_evidence",
                "benchmark_runs": 3,
            },
            "checks": {"pass": True},
        },
    )
    preflight = _write_json(
        tmp_path / "preflight.json",
        {
            "passed": True,
            "strict_startup": True,
            "runtime_profile": "competition_strict",
            "config_sha256": "candidate-config-sha",
            "verified_models": [{"model_id": model_id, "checkpoint_sha256": digest, "runtime_allowed": True}],
        },
    )
    competition_flow = _write_json(
        tmp_path / "competition_flow.json",
        {
            "case_id": "case_candidate_gate",
            "runtime": {
                "config_bound": True,
                "readiness_passed": True,
                "strict_startup": True,
                "runtime_profile": "competition_strict",
                "config_sha256": "candidate-config-sha",
            },
            "models": {
                "configured_segmentation_model_id": model_id,
                "video_execution": {
                    "manifest_path": str(tmp_path / "video_segmentation_manifest.json"),
                    "model_ids": [model_id],
                    "analysis_methods": ["trainable_keyframe_segmenter"],
                },
            },
            "demo_check": {
                "pass": True,
                "keyframe_mainline_model_exercised": True,
                "keyframe_fallback_used": False,
                "required_formats_present": ["probability_map", "video_mask", "video_overlay"],
                "missing_required_formats": [],
                "clinical_claim_allowed": False,
                "non_target_domain_disclosed": True,
            },
        },
    )
    probability = tmp_path / "frame_probability.png"
    probability.write_bytes(b"probability")
    _write_json(
        tmp_path / "video_segmentation_manifest.json",
        {
            "frames": [
                {
                    "frame_order": 1,
                    "frame_index": 0,
                    "segmentation_result": {
                        "model_id": model_id,
                        "analysis_method": "trainable_keyframe_segmenter",
                        "probability_path": str(probability),
                    },
                }
            ]
        },
    )
    production = tmp_path / "strict.yml"
    production.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "required_model_ids": ["mainline"],
                    "models": [{"model_id": "mainline"}],
                    "tasks": {"segmentation": {"model_id": "mainline"}},
                }
            }
        ),
        encoding="utf-8",
    )
    production_digest = hashlib.sha256(production.read_bytes()).hexdigest()
    production_preflight = _write_json(
        tmp_path / "production_preflight.json",
        {
            "passed": True,
            "strict_startup": True,
            "runtime_profile": "competition_strict",
            "config_sha256": production_digest,
        },
    )

    report = build_candidate_runtime_gate(
        checkpoint_path=checkpoint,
        model_id=model_id,
        selection_summary_path=selection,
        runtime_promotion_sidecar_path=promotion,
        tiling_smoke_path=smoke,
        mainline_comparator_path=comparator,
        runtime_preflight_path=preflight,
        competition_flow_path=competition_flow,
        production_preflight_path=production_preflight,
        production_config_path=production,
    )

    assert report["technical_gate_passed"] is True
    assert report["competition_runtime_selected"] is False
    assert report["automatic_replacement_performed"] is False
    assert report["checks"]["production_config_candidate_not_selected"] is True
    assert report["mainline_comparison"]["strictly_comparable"] is True
    assert report["runtime_risks"]["continuous_playback_full_evidence_latency"] is True
    assert report["checks"]["production_strict_runtime_remains_ready"] is True
    assert report["checks"]["competition_flow_candidate_exercised"] is True
    assert report["checks"]["competition_flow_no_heuristic_fallback"] is True
    assert report["checks"]["competition_flow_frame_models_verified"] is True
    assert report["checks"]["competition_flow_frame_probability_files_verified"] is True
    assert report["competition_flow"]["executed_model_ids"] == [model_id]
    assert report["competition_flow"]["frame_evidence"]["frame_count"] == 1


def test_candidate_runtime_gate_rejects_competition_flow_fallback(tmp_path: Path) -> None:
    checkpoint = tmp_path / "candidate.pt"
    checkpoint.write_bytes(b"candidate")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    model_id = "candidate_residual"
    selection = _write_json(
        tmp_path / "selection.json",
        {
            "recommendation": {
                "selected_family": "residual_attention_unet_keyframe_segmenter",
                "selected_model_id": model_id,
                "selected_checkpoint": str(checkpoint),
            },
            "candidate_families": [
                {
                    "model_family": "residual_attention_unet_keyframe_segmenter",
                    "gates": {"selection_passed": True},
                }
            ],
        },
    )
    promotion = _write_json(
        tmp_path / "promotion.json",
        {
            "checkpoint_sha256": digest,
            "model_id": model_id,
            "model_family": "residual_attention_unet_keyframe_segmenter",
            "threshold": 0.4,
            "runtime_allowed": True,
            "clinical_claim_allowed": False,
        },
    )
    tiled_payload = {
        "model_id": "mainline",
        "checkpoint": {"sha256": digest},
        "input": {"width": 3840, "height": 2160, "is_official_4k_resolution": True},
        "inference": {
            "mode": "tiled",
            "tile_size": 512,
            "tile_overlap": 64,
            "tile_count": 45,
            "tile_batch_size": 4,
            "tta_enabled": False,
            "use_amp": False,
            "output_profile": "full_evidence",
            "benchmark_runs": 3,
        },
        "checks": {"pass": True},
    }
    smoke = _write_json(tmp_path / "smoke.json", tiled_payload)
    comparator_payload = json.loads(json.dumps(tiled_payload))
    comparator_payload.pop("checkpoint")
    comparator = _write_json(tmp_path / "comparator.json", comparator_payload)
    preflight = _write_json(
        tmp_path / "preflight.json",
        {
            "passed": True,
            "strict_startup": True,
            "runtime_profile": "competition_strict",
            "config_sha256": "candidate-config-sha",
            "verified_models": [{"model_id": model_id, "checkpoint_sha256": digest, "runtime_allowed": True}],
        },
    )
    flow = _write_json(
        tmp_path / "flow.json",
        {
            "runtime": {
                "config_bound": True,
                "readiness_passed": True,
                "strict_startup": True,
                "runtime_profile": "competition_strict",
                "config_sha256": "candidate-config-sha",
            },
            "models": {
                "configured_segmentation_model_id": model_id,
                "video_execution": {
                    "model_ids": ["video_keyframe_hotspot_segmenter"],
                    "analysis_methods": ["heuristic_hotspot_fallback"],
                },
            },
            "demo_check": {
                "pass": False,
                "keyframe_mainline_model_exercised": False,
                "keyframe_fallback_used": True,
                "required_formats_present": [],
                "missing_required_formats": ["probability_map"],
                "clinical_claim_allowed": False,
                "non_target_domain_disclosed": True,
            },
        },
    )
    production = tmp_path / "strict.yml"
    production.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "required_model_ids": ["mainline"],
                    "models": [{"model_id": "mainline"}],
                    "tasks": {"segmentation": {"model_id": "mainline"}},
                }
            }
        ),
        encoding="utf-8",
    )
    production_preflight = _write_json(
        tmp_path / "production_preflight.json",
        {
            "passed": True,
            "strict_startup": True,
            "runtime_profile": "competition_strict",
            "config_sha256": hashlib.sha256(production.read_bytes()).hexdigest(),
        },
    )

    report = build_candidate_runtime_gate(
        checkpoint_path=checkpoint,
        model_id=model_id,
        selection_summary_path=selection,
        runtime_promotion_sidecar_path=promotion,
        tiling_smoke_path=smoke,
        mainline_comparator_path=comparator,
        runtime_preflight_path=preflight,
        competition_flow_path=flow,
        production_preflight_path=production_preflight,
        production_config_path=production,
    )

    assert report["technical_gate_passed"] is False
    assert report["checks"]["competition_flow_passed"] is False
    assert report["checks"]["competition_flow_candidate_exercised"] is False
    assert report["checks"]["competition_flow_no_heuristic_fallback"] is False
    assert report["checks"]["competition_flow_probability_map_exported"] is False
    assert report["checks"]["competition_flow_frame_models_verified"] is False
    assert report["checks"]["competition_flow_frame_probability_files_verified"] is False
