from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "keyframe_residual_attention_unet_s20260715_20260715"


def _runtime(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runtime = payload.get("runtime")
    assert isinstance(runtime, dict)
    return runtime


def test_competition_strict_config_selects_promoted_residual_attention_mainline() -> None:
    runtime = _runtime(ROOT / "configs" / "inference" / "osteo_vision_competition_strict.yml")
    models = {str(item["model_id"]): item for item in runtime["models"]}
    selected = models[MODEL_ID]

    assert runtime["required_model_ids"] == [MODEL_ID]
    assert runtime["tasks"]["segmentation"]["model_id"] == MODEL_ID
    assert runtime["allow_heuristic_keyframe_fallback"] is False
    assert selected["family"] == "residual_attention_unet_keyframe_segmenter"
    assert selected["clinical_claim_allowed"] is False
    assert selected["extra"]["runtime_allowed"] is True
    assert selected["extra"]["threshold"] == 0.4
    assert selected["extra"]["checkpoint_model_id"] == MODEL_ID
    assert selected["extra"]["live_stream"]["fast_output"] is True


def test_development_config_uses_same_keyframe_mainline_and_keeps_convnext_comparator() -> None:
    runtime = _runtime(ROOT / "configs" / "inference" / "osteo_vision.yml")
    models = {str(item["model_id"]): item for item in runtime["models"]}

    assert runtime["tasks"]["segmentation"]["model_id"] == MODEL_ID
    assert models[MODEL_ID]["family"] == "residual_attention_unet_keyframe_segmenter"
    assert models[MODEL_ID]["extra"]["threshold"] == 0.4
    assert "convnext2d_keyframe_proxy_segmenter" in models
