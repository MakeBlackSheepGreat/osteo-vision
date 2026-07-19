from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapter, build_adapters, model_spec_from_mapping, select_adapter
from src.models.runtime_preflight import check_runtime_readiness

ROOT = Path(__file__).resolve().parents[2]
DEVELOPMENT_CONFIG = ROOT / "configs" / "inference" / "osteo_vision.yml"
STRICT_CONFIG = ROOT / "configs" / "inference" / "osteo_vision_competition_strict.yml"
PATIENT_MODEL_ID = "patient_conditioned_kits23_proxy_candidate"
MAINLINE_MODEL_ID = "keyframe_residual_attention_unet_s20260715_20260715"
MANIFEST_SHA256 = "27f1fe208cea184e0ee069ae16165b1d63cc766dcf8d291ebb3602d4cff4e1e3"


def test_development_config_registers_hash_bound_patient_conditioned_candidate() -> None:
    runtime = _runtime(DEVELOPMENT_CONFIG)
    models = {str(item["model_id"]): item for item in runtime["models"]}
    candidate = models[PATIENT_MODEL_ID]
    extra = candidate["extra"]
    checkpoint = ROOT / candidate["checkpoint_path"]
    manifest = ROOT / extra["checkpoint_manifest_path"]

    assert candidate["family"] == "patient_conditioned_segmenter"
    assert candidate["input_types"] == ["dual_channel_image"]
    assert candidate["clinical_claim_allowed"] is False
    assert extra["runtime_allowed"] is True
    assert extra["candidate_only"] is True
    assert extra["engineering_candidate_execution_allowed"] is True
    assert extra["runtime_replacement_allowed"] is False
    assert extra["mainline_replacement_allowed"] is False
    assert extra["strict_promotion_authorized"] is False
    assert extra["target_domain"] is False
    assert extra["checkpoint_manifest_sha256"] == MANIFEST_SHA256
    assert runtime["tasks"]["segmentation"]["model_id"] == MAINLINE_MODEL_ID
    assert checkpoint.is_file()
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == MANIFEST_SHA256


def test_registered_patient_candidate_warms_up_and_requires_explicit_selection() -> None:
    runtime = _runtime(DEVELOPMENT_CONFIG)
    adapters = build_adapters(runtime)
    patient_adapter = next(adapter for adapter in adapters if adapter.describe().model_id == PATIENT_MODEL_ID)

    status = patient_adapter.warmup()
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
        explicit_model_id=PATIENT_MODEL_ID,
    )

    assert status.available is True
    assert automatic is not None
    assert automatic.describe().model_id != PATIENT_MODEL_ID
    assert explicit is patient_adapter
    assert explicit_statuses[-1].available is True


def test_registered_patient_candidate_runs_hash_bound_image_only_fallback(tmp_path: Path) -> None:
    runtime = _runtime(DEVELOPMENT_CONFIG)
    candidate = dict(next(item for item in runtime["models"] if item["model_id"] == PATIENT_MODEL_ID))
    candidate["extra"] = {**candidate["extra"], "output_dir": str(tmp_path / "evidence")}
    adapter = build_adapter(model_spec_from_mapping(candidate))
    white_path, fluorescence_path, bone_gate_path = _write_registered_inputs(tmp_path)
    context_snapshot = {
        "age_years": 68,
        "sex_at_birth": "female",
        "comorbidities": ["type_2_diabetes"],
        "medications": [],
        "labs": [],
        "deidentified": True,
        "review_status": "verified",
        "verified_by": {
            "actor_id": "doctor-runtime-config",
            "role": "physician",
            "institution": "Example Stomatology Hospital",
            "auth_source": "verified_identity_token",
        },
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    context_checksum = hashlib.sha256(
        json.dumps(context_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    result = adapter.predict(
        AdapterRequest(
            case_id="registered-patient-proxy",
            input_path=str(white_path),
            input_type="dual_channel_image",
            task_type="segmentation",
            modality="white_light_fluorescence",
            metadata={
                "fluorescence_path": str(fluorescence_path),
                "dual_channel_registration_verified": True,
                "clinical_context_assessment": {
                    "schema_version": "osteo-vision-clinical-context-assessment-v1",
                    "clinical_context_snapshot": context_snapshot,
                    "clinical_context_checksum": context_checksum,
                    "clinical_context_quality": {
                        "status": "ready_for_rule_summary",
                        "review_status": "verified",
                        "deidentified": True,
                        "issues": [],
                    },
                    "model_features": {
                        "age_years": 68.0,
                        "sex_at_birth_female": 1.0,
                        "diabetes": 1.0,
                        "renal_disease": 0.0,
                        "egfr_ml_min_1_73m2": 76.0,
                    },
                    "model_feature_present": {
                        "age_years": True,
                        "sex_at_birth_female": True,
                        "diabetes": True,
                        "renal_disease": True,
                        "egfr_ml_min_1_73m2": True,
                    },
                    "spatial_conditioning_authorized": True,
                },
                "reviewed_bone_gate": {
                    "path": str(bone_gate_path),
                    "sha256": hashlib.sha256(bone_gate_path.read_bytes()).hexdigest(),
                    "physician_reviewed": True,
                    "trusted_review": True,
                    "review_status": "physician_accepted",
                },
                "target_domain_input_verified": True,
            },
        )
    )

    image_only = np.load(result.prediction["image_only_probability_array_path"])
    conditioned = np.load(result.prediction["conditioned_probability_array_path"])
    delta = np.load(result.prediction["delta_map_array_path"])
    assert result.prediction["available"] is True
    assert result.prediction["proxy_checkpoint"] is True
    assert result.prediction["spatial_effect_applied"] is False
    assert result.prediction["safe_fallback_applied"] is True
    assert result.prediction["runtime_replacement_allowed"] is False
    assert "non_target_domain_proxy" in result.prediction["failure_reasons"]
    assert np.array_equal(conditioned, image_only)
    assert np.count_nonzero(delta) == 0
    assert result.quantification["difference_area_px"] == 0
    assert Path(result.prediction["evidence_manifest_path"]).is_file()


def test_competition_strict_inventory_excludes_unpromoted_patient_candidate(monkeypatch) -> None:
    strict_runtime = _runtime(STRICT_CONFIG)
    strict_model_ids = {str(item["model_id"]) for item in strict_runtime["models"]}
    monkeypatch.setattr("src.models.runtime_preflight.find_runtime_executable", lambda name: f"C:/tools/{name}.exe")

    report = check_runtime_readiness(STRICT_CONFIG, require_strict=True)

    assert PATIENT_MODEL_ID not in strict_model_ids
    assert PATIENT_MODEL_ID not in strict_runtime["required_model_ids"]
    assert strict_runtime["required_model_ids"] == [MAINLINE_MODEL_ID]
    assert strict_runtime["tasks"]["segmentation"]["model_id"] == MAINLINE_MODEL_ID
    assert report["passed"] is True
    assert [item["model_id"] for item in report["verified_models"]] == [MAINLINE_MODEL_ID]


def test_development_runtime_readiness_keeps_candidate_out_of_required_models(monkeypatch) -> None:
    monkeypatch.setattr("src.models.runtime_preflight.find_runtime_executable", lambda name: f"C:/tools/{name}.exe")

    report = check_runtime_readiness(DEVELOPMENT_CONFIG)

    assert report["passed"] is True
    assert PATIENT_MODEL_ID not in report["required_model_ids"]
    assert all(item["model_id"] != PATIENT_MODEL_ID for item in report["verified_models"])


def _runtime(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    runtime = payload.get("runtime")
    assert isinstance(runtime, dict)
    return runtime


def _write_registered_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    white_path = tmp_path / "white.png"
    fluorescence_path = tmp_path / "fluorescence.png"
    bone_gate_path = tmp_path / "reviewed_bone_gate.png"
    white = np.full((32, 40, 3), 92, dtype=np.uint8)
    white[8:26, 10:32, 1] = 176
    fluorescence = np.zeros((32, 40), dtype=np.uint8)
    fluorescence[9:27, 11:33] = 220
    bone_gate = np.zeros((32, 40), dtype=np.uint8)
    bone_gate[6:29, 8:35] = 255
    Image.fromarray(white).save(white_path)
    Image.fromarray(fluorescence).save(fluorescence_path)
    Image.fromarray(bone_gate).save(bone_gate_path)
    return white_path, fluorescence_path, bone_gate_path
