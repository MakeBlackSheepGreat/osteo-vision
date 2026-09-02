from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from osteo_vision_core.preprocess.fluorescence import (
    register_fluorescence_to_reference,
    subtract_fluorescence_background,
)
from tools.run_platform_flow_demo_check import (
    bind_runtime_environment,
    configured_segmentation_model_id,
    create_proxy_jpeg,
    file_record,
    parse_args,
    paths_match,
    required_runtime_model_ids,
    run_record,
    upload_record,
    video_segmentation_execution,
)


def test_platform_flow_defaults_to_strict_runtime(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["run_platform_flow_demo_check.py"])

    args = parse_args()

    assert args.config == "configs/inference/osteo_vision_strict.yml"


def test_bind_runtime_environment_uses_requested_config(tmp_path: Path) -> None:
    config_path = tmp_path / "strict.yml"
    config_path.write_text("runtime: {}\n", encoding="utf-8")
    output_dir = tmp_path / "run"
    names = (
        "OSTEO_INFERENCE_CONFIG",
        "OSTEO_ARTIFACT_ROOT",
        "OSTEO_CASE_STORE_PATH",
        "OSTEO_JOB_STORE_PATH",
        "OSTEO_JOB_EXECUTION_MODE",
    )
    original_environment = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)

    try:
        resolved = bind_runtime_environment(config_path, output_dir)

        assert resolved == config_path.resolve()
        assert Path(os.environ["OSTEO_INFERENCE_CONFIG"]) == config_path.resolve()
        assert Path(os.environ["OSTEO_ARTIFACT_ROOT"]) == output_dir / "artifacts"
        assert os.environ["OSTEO_JOB_EXECUTION_MODE"] == "background"
        assert paths_match(os.environ["OSTEO_INFERENCE_CONFIG"], config_path)
    finally:
        for name, value in original_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_model_gate_is_derived_from_runtime_config() -> None:
    runtime = {
        "required_model_ids": ["keyframe_mainline"],
        "tasks": {"segmentation": {"pipeline": "segmentation", "model_id": "keyframe_mainline"}},
    }

    assert required_runtime_model_ids(runtime) == {"keyframe_mainline"}
    assert configured_segmentation_model_id(runtime) == "keyframe_mainline"


def test_generated_proxy_pair_passes_registration_gate(tmp_path: Path) -> None:
    white_path = create_proxy_jpeg(tmp_path / "white.jpg", channel="white", width=640, height=360)
    fluorescence_path = create_proxy_jpeg(
        tmp_path / "fluorescence.jpg",
        channel="fluorescence",
        width=640,
        height=360,
    )
    with Image.open(white_path) as white_image, Image.open(fluorescence_path) as fluorescence_image:
        white = np.asarray(white_image.convert("RGB"), dtype=np.float32)
        fluorescence = np.asarray(fluorescence_image.convert("L"), dtype=np.float32)
    corrected, _background = subtract_fluorescence_background(fluorescence, percentile=5.0)

    _registered, report = register_fluorescence_to_reference(white, corrected)

    assert report["applied"] is True
    assert report["response"] >= report["min_response"]


def test_file_and_run_records_keep_hash_registration_and_patient_safety_evidence(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jpg"
    input_path.write_bytes(b"traceable-input")
    record = file_record(input_path)
    run = run_record(
        {
            "run_id": "run_registered",
            "status": "completed",
            "candidate_regions": [],
            "quantitative_summary": {},
            "fused_outputs": {
                "fusion": {
                    "registration_details": {
                        "applied": True,
                        "response": 0.36,
                        "min_response": 0.08,
                    }
                },
                "patient_conditioning_evidence": {
                    "available": True,
                    "model_id": "patient_proxy",
                    "spatial_effect_applied": False,
                    "safe_fallback_applied": True,
                    "failure_reasons": ["non_target_domain_proxy"],
                },
            },
        }
    )

    assert record["size_bytes"] == len(b"traceable-input")
    assert len(record["sha256"]) == 64
    assert run["registration_evidence"]["applied"] is True
    assert run["patient_conditioning"] == {
        "available": True,
        "model_id": "patient_proxy",
        "spatial_effect_applied": False,
        "safe_fallback_applied": True,
        "failure_reasons": ["non_target_domain_proxy"],
    }


def test_upload_record_reads_official_input_profile() -> None:
    profile = {"status": "official_profile_match", "target_resolution": [3840, 2160]}

    record = upload_record({"metadata": {"official_input_profile": profile}})

    assert record["official_profile"] == profile


def test_video_execution_reads_models_and_methods_from_manifest(tmp_path: Path) -> None:
    probability_path = tmp_path / "probability.png"
    probability_path.write_bytes(b"probability")
    manifest = tmp_path / "video_segmentation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "summary": {
                    "model_ids": ["keyframe_mainline"],
                    "analysis_methods": ["trainable_keyframe_segmenter"],
                },
                "frames": [
                    {
                        "segmentation_result": {
                            "model_id": "keyframe_mainline",
                            "analysis_method": "trainable_keyframe_segmenter",
                            "probability_path": str(probability_path),
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run = {"fused_outputs": {"video_segmentation_manifest_path": str(manifest)}}

    execution = video_segmentation_execution(run)

    assert execution["available"] is True
    assert execution["model_ids"] == ["keyframe_mainline"]
    assert execution["analysis_methods"] == ["trainable_keyframe_segmenter"]
    assert execution["frame_evidence_valid"] is True
    assert execution["missing_probability_paths"] == []


def test_video_execution_rejects_missing_frame_probability_evidence(tmp_path: Path) -> None:
    manifest = tmp_path / "video_segmentation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "summary": {
                    "model_ids": ["keyframe_mainline"],
                    "analysis_methods": ["trainable_keyframe_segmenter"],
                },
                "frames": [
                    {
                        "segmentation_result": {
                            "model_id": "keyframe_mainline",
                            "analysis_method": "trainable_keyframe_segmenter",
                            "probability_path": str(tmp_path / "missing.png"),
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    execution = video_segmentation_execution({"fused_outputs": {"video_segmentation_manifest_path": str(manifest)}})

    assert execution["frame_evidence_valid"] is False
    assert execution["missing_probability_paths"] == ["frame_1"]
