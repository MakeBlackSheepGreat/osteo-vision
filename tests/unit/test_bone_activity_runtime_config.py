from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from osteo_vision_core.models.adapters import build_adapters, select_adapter

ROOT = Path(__file__).resolve().parents[2]
DEVELOPMENT_CONFIG = ROOT / "configs" / "inference" / "osteo_vision.yml"
STRICT_CONFIG = ROOT / "configs" / "inference" / "osteo_vision_competition_strict.yml"
MODEL_ID = "bone_activity_multitask_d074_proxy_candidate"
MAINLINE_MODEL_ID = "keyframe_residual_attention_unet_s20260715_20260715"
MANIFEST_SHA256 = "50816b29384766fdc6b7dc23d7a04d523958343351b89ff6a1d2e7dc4f5d7a8f"


def test_development_config_registers_hash_bound_bone_activity_candidate() -> None:
    runtime = _runtime(DEVELOPMENT_CONFIG)
    models = {str(item["model_id"]): item for item in runtime["models"]}
    candidate = models[MODEL_ID]
    extra = candidate["extra"]
    checkpoint = ROOT / candidate["checkpoint_path"]
    manifest_path = ROOT / extra["checkpoint_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert candidate["family"] == "bone_activity_multitask"
    assert candidate["input_types"] == ["dual_channel_image"]
    assert candidate["clinical_claim_allowed"] is False
    assert candidate["source_url"] == "https://zenodo.org/records/15260349"
    assert candidate["license"] == "CC-BY-4.0"
    assert extra["runtime_allowed"] is True
    assert extra["candidate_only"] is True
    assert extra["engineering_candidate_execution_allowed"] is True
    assert extra["runtime_replacement_allowed"] is False
    assert extra["mainline_replacement_allowed"] is False
    assert extra["strict_promotion_authorized"] is False
    assert extra["target_domain"] is False
    assert extra["engineering_utility_ready"] is False
    assert extra["checkpoint_manifest_sha256"] == MANIFEST_SHA256
    assert runtime["tasks"]["segmentation"]["model_id"] == MAINLINE_MODEL_ID
    assert checkpoint.is_file()
    assert manifest_path.is_file()
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == MANIFEST_SHA256
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == manifest["checkpoint_sha256"]
    assert manifest["target_domain_promotion_ready"] is False
    assert manifest["runtime_replacement_allowed"] is False
    assert manifest["engineering_utility"]["ready"] is False


def test_registered_bone_activity_candidate_requires_explicit_selection() -> None:
    adapters = build_adapters(_runtime(DEVELOPMENT_CONFIG))
    candidate = next(adapter for adapter in adapters if adapter.describe().model_id == MODEL_ID)

    status = candidate.warmup()
    automatic, _ = select_adapter(
        adapters,
        task_type="segmentation",
        input_type="dual_channel_image",
        modality="white_light_fluorescence",
    )
    explicit, explicit_statuses = select_adapter(
        adapters,
        task_type="segmentation",
        input_type="dual_channel_image",
        modality="white_light_fluorescence",
        policy="explicit",
        explicit_model_id=MODEL_ID,
    )

    assert status.available is True
    assert automatic is not None
    assert automatic.describe().model_id != MODEL_ID
    assert explicit is candidate
    assert explicit_statuses[-1].available is True


def test_strict_runtime_keeps_unpromoted_bone_activity_candidate_out_of_mainline() -> None:
    strict_runtime = _runtime(STRICT_CONFIG)
    strict_model_ids = {str(item["model_id"]) for item in strict_runtime["models"]}

    assert MODEL_ID in strict_model_ids
    candidate = next(item for item in strict_runtime["models"] if item["model_id"] == MODEL_ID)
    assert MODEL_ID not in set(strict_runtime.get("required_model_ids") or [])
    assert candidate["clinical_claim_allowed"] is False
    assert candidate["extra"]["candidate_only"] is True
    assert candidate["extra"]["mainline_replacement_allowed"] is False
    assert candidate["extra"]["runtime_replacement_allowed"] is False
    assert MODEL_ID not in strict_runtime["required_model_ids"]
    assert strict_runtime["required_model_ids"] == [MAINLINE_MODEL_ID]
    assert strict_runtime["tasks"]["segmentation"]["model_id"] == MAINLINE_MODEL_ID


def _runtime(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runtime = payload.get("runtime")
    assert isinstance(runtime, dict)
    return runtime
