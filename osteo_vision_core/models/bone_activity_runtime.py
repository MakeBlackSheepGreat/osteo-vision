from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.models.bone_activity_multitask import (
    BONE_ACTIVITY_CLASSES,
    BoneActivityMultiTask2D,
    apply_bone_activity_safety_gate,
    load_bone_activity_multitask_checkpoint,
)

BONE_ACTIVITY_METADATA_CONTRACT: dict[str, Any] = {
    "fluorescence_path": "required_registered_grayscale_or_rgb_image_path",
    "dual_channel_registration_verified": "required_true_for_spatial_candidates",
    "reviewed_bone_gate": {
        "path": "required_for_spatial_candidates",
        "sha256": "required_for_spatial_candidates",
        "physician_reviewed": True,
        "trusted_review": True,
        "review_status": ["physician_accepted", "physician_modified", "reviewed_bone_gate"],
        "annotation_id": "required",
        "annotation_version": "required_positive_integer",
        "source_input_id": "required",
        "source_checksum": "required_white_light_sha256",
        "positive_pixel_count": "required_mask_area_binding",
        "reviewed_at": "required",
        "reviewed_by": "required_trusted_physician_identity",
    },
    "target_domain_input_verified": "required_true_for_spatial_candidates",
}

_MANIFEST_SCHEMA = "osteo-vision-bone-activity-multitask-checkpoint-v1"
_CAPABILITY = "bone_activity_multitask"
_MODEL_FAMILY = "dual_channel_bone_activity_multitask"
_REVIEWED_GATE_STATES = {"physician_accepted", "physician_modified", "reviewed_bone_gate"}
_REQUIRED_OUTPUTS = {
    "bone_gate",
    "activity_score",
    "class_logits",
    "class_probabilities",
    "uncertainty",
    "abstention",
}


@dataclass(frozen=True)
class BoneActivityRuntimeEvidence:
    checkpoint_path: Path
    checkpoint_sha256: str
    manifest_path: Path
    manifest_sha256: str
    engineering_ready: bool
    engineering_utility_ready: bool
    proxy_checkpoint: bool
    target_domain_promotion_ready: bool
    runtime_replacement_allowed: bool
    bone_gate_threshold: float
    abstention_threshold: float
    medical_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_path": str(self.checkpoint_path),
            "checkpoint_sha256": self.checkpoint_sha256,
            "manifest_path": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "engineering_ready": self.engineering_ready,
            "engineering_utility_ready": self.engineering_utility_ready,
            "proxy_checkpoint": self.proxy_checkpoint,
            "target_domain_promotion_ready": self.target_domain_promotion_ready,
            "runtime_replacement_allowed": self.runtime_replacement_allowed,
            "bone_gate_threshold": self.bone_gate_threshold,
            "abstention_threshold": self.abstention_threshold,
            "medical_boundary": self.medical_boundary,
        }


def load_validated_bone_activity_runtime(
    checkpoint_path: str | Path,
    manifest_path: str | Path,
    *,
    device: torch.device,
    expected_manifest_sha256: str | None = None,
    strict_promotion_authorized: bool = False,
) -> tuple[BoneActivityMultiTask2D, dict[str, Any], BoneActivityRuntimeEvidence]:
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not checkpoint.is_file():
        raise ValueError(f"Bone-activity checkpoint is missing: {checkpoint}")
    if not manifest_file.is_file():
        raise ValueError(f"Bone-activity manifest is missing: {manifest_file}")

    checkpoint_sha256 = _sha256_file(checkpoint)
    manifest_sha256 = _sha256_file(manifest_file)
    if expected_manifest_sha256 and manifest_sha256 != _normalized_sha256(expected_manifest_sha256):
        raise ValueError("Bone-activity manifest SHA256 mismatch")
    try:
        manifest_value = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Bone-activity manifest is unreadable: {exc}") from exc
    if not isinstance(manifest_value, dict):
        raise ValueError("Bone-activity manifest root must be a mapping")
    manifest = dict(manifest_value)
    if manifest.get("schema_version") != _MANIFEST_SCHEMA:
        raise ValueError("Bone-activity manifest schema_version is unsupported")
    if manifest.get("capability") != _CAPABILITY:
        raise ValueError("Bone-activity manifest capability mismatch")
    if _normalized_sha256(manifest.get("checkpoint_sha256")) != checkpoint_sha256:
        raise ValueError("Bone-activity checkpoint SHA256 mismatch")

    model, checkpoint_metadata = load_bone_activity_multitask_checkpoint(checkpoint, device=device)
    _validate_checkpoint_metadata(checkpoint_metadata, manifest, checkpoint_sha256)
    training_domain = _mapping(manifest.get("training_domain"))
    target_domain_training = training_domain.get("target_domain") is True
    proxy_checkpoint = not target_domain_training
    engineering_ready = manifest.get("engineering_ready") is True
    engineering_utility = _mapping(manifest.get("engineering_utility"))
    engineering_utility_ready = engineering_utility.get("ready") is True
    manifest_target_ready = manifest.get("target_domain_promotion_ready") is True
    manifest_runtime_allowed = manifest.get("runtime_allowed") is True
    manifest_replacement_allowed = manifest.get("runtime_replacement_allowed") is True
    thresholds = _mapping(manifest.get("inference_thresholds"))
    thresholds_runtime_authorized = thresholds.get("runtime_authorized") is True
    promotion = _mapping(manifest.get("promotion"))
    promotion_ready = bool(
        promotion.get("target_domain_promotion_ready") is True
        and promotion.get("runtime_replacement_allowed") is True
        and _normalized_sha256(promotion.get("checkpoint_sha256")) == checkpoint_sha256
        and not list(promotion.get("promotion_blockers") or [])
        and not list(promotion.get("errors") or [])
    )
    if proxy_checkpoint and (manifest_target_ready or manifest_runtime_allowed or manifest_replacement_allowed):
        raise ValueError("Non-target-domain bone-activity checkpoint contains forbidden runtime flags")
    target_domain_promotion_ready = bool(
        target_domain_training
        and manifest_target_ready
        and manifest_runtime_allowed
        and thresholds_runtime_authorized
        and promotion_ready
    )
    runtime_replacement_allowed = bool(
        target_domain_promotion_ready and manifest_replacement_allowed and strict_promotion_authorized
    )
    bone_gate_threshold = _probability_threshold(thresholds.get("bone_gate_threshold"), "bone_gate_threshold")
    abstention_threshold = _probability_threshold(thresholds.get("abstention_threshold"), "abstention_threshold")
    medical_boundary = str(
        manifest.get("medical_boundary")
        or "Bone-activity outputs remain research validation evidence requiring physician review."
    )
    return (
        model,
        checkpoint_metadata,
        BoneActivityRuntimeEvidence(
            checkpoint_path=checkpoint,
            checkpoint_sha256=checkpoint_sha256,
            manifest_path=manifest_file,
            manifest_sha256=manifest_sha256,
            engineering_ready=engineering_ready,
            engineering_utility_ready=engineering_utility_ready,
            proxy_checkpoint=proxy_checkpoint,
            target_domain_promotion_ready=target_domain_promotion_ready,
            runtime_replacement_allowed=runtime_replacement_allowed,
            bone_gate_threshold=bone_gate_threshold,
            abstention_threshold=abstention_threshold,
            medical_boundary=medical_boundary,
        ),
    )


def predict_bone_activity_image(
    model: BoneActivityMultiTask2D,
    runtime: BoneActivityRuntimeEvidence,
    *,
    white_path: str | Path,
    fluorescence_path: str | Path,
    metadata: Mapping[str, Any],
    device: torch.device,
    output_dir: str | Path,
    case_id: str,
    input_shape: tuple[int, int],
) -> dict[str, Any]:
    white, fluorescence, source = _load_registered_images(
        white_path,
        fluorescence_path,
        device=device,
        input_shape=input_shape,
    )
    source.update(
        {
            "white_light_path": str(Path(white_path).expanduser().resolve()),
            "white_light_sha256": _sha256_file(Path(white_path).expanduser().resolve()),
            "fluorescence_path": str(Path(fluorescence_path).expanduser().resolve()),
            "fluorescence_sha256": _sha256_file(Path(fluorescence_path).expanduser().resolve()),
        }
    )
    reviewed_gate, physician_reviewed, gate_reasons, gate_evidence = _reviewed_gate(
        metadata.get("reviewed_bone_gate"),
        width=source["width"],
        height=source["height"],
        model_shape=input_shape,
        source_sha256=str(source["white_light_sha256"]),
        device=device,
    )
    registration_verified = metadata.get("dual_channel_registration_verified") is True
    target_domain_input_verified = metadata.get("target_domain_input_verified") is True
    preflight_reasons: list[str] = []
    if not registration_verified:
        preflight_reasons.append("dual_channel_registration_not_verified")
    if not target_domain_input_verified:
        preflight_reasons.append("target_domain_input_not_verified")
    if runtime.proxy_checkpoint:
        preflight_reasons.append("non_target_domain_proxy")
    if not runtime.engineering_utility_ready:
        preflight_reasons.append("engineering_utility_gate_failed")

    model.eval()
    with torch.no_grad():
        outputs = model(white, fluorescence)
        safe = apply_bone_activity_safety_gate(
            outputs,
            reviewed_bone_gate=reviewed_gate,
            physician_reviewed_bone_gate=physician_reviewed and registration_verified,
            target_domain=target_domain_input_verified and not runtime.proxy_checkpoint,
            model_promotion_ready=runtime.runtime_replacement_allowed and registration_verified,
            abstention_threshold=runtime.abstention_threshold,
        )

    failure_reasons = list(dict.fromkeys([*preflight_reasons, *gate_reasons, *list(safe["failure_reasons"])]))
    raw_outputs = _raw_engineering_arrays(safe["raw_engineering_outputs"])
    output_root = ensure_dir(Path(output_dir).expanduser().resolve())
    evidence_id = _evidence_id(case_id, runtime.checkpoint_sha256, source)
    prefix = output_root / f"{_safe_name(case_id)}_{evidence_id}_bone_activity"
    raw_archive_path = Path(f"{prefix}_raw_engineering_outputs.npz")
    cast(Any, np.savez_compressed)(raw_archive_path, **raw_outputs)
    raw_summary = _raw_engineering_summary(raw_outputs)
    assets: dict[str, str] = {"raw_engineering_outputs_path": str(raw_archive_path)}

    spatial_candidates_available = bool(safe["spatial_candidates_available"])
    spectrum = _unavailable_spectrum(
        runtime=runtime,
        raw_archive_path=raw_archive_path,
        raw_summary=raw_summary,
        failure_reasons=failure_reasons,
    )
    if spatial_candidates_available:
        if reviewed_gate is None:
            raise RuntimeError("Bone-activity safety gate returned spatial candidates without a reviewed bone gate")
        safe_arrays = _safe_arrays(safe, reviewed_gate, output_shape=(source["height"], source["width"]))
        saved_assets, spectrum = _write_safe_candidate_assets(
            prefix=prefix,
            arrays=safe_arrays,
            runtime=runtime,
            raw_archive_path=raw_archive_path,
            raw_summary=raw_summary,
        )
        assets.update(saved_assets)

    asset_sha256 = {name: _sha256_file(Path(path)) for name, path in assets.items()}
    payload: dict[str, Any] = {
        "schema_version": "osteo-vision-bone-activity-runtime-evidence-v1",
        "available": spatial_candidates_available,
        "engineering_inference_executed": True,
        "spatial_candidates_available": spatial_candidates_available,
        "spatial_effect_applied": spatial_candidates_available,
        "safe_fallback_applied": not spatial_candidates_available,
        "failure_reasons": failure_reasons,
        "proxy_checkpoint": runtime.proxy_checkpoint,
        "engineering_ready": runtime.engineering_ready,
        "engineering_utility_ready": runtime.engineering_utility_ready,
        "target_domain_promotion_ready": runtime.target_domain_promotion_ready,
        "runtime_replacement_allowed": runtime.runtime_replacement_allowed,
        "checkpoint_sha256": runtime.checkpoint_sha256,
        "manifest_sha256": runtime.manifest_sha256,
        "source_inputs": source,
        "dual_channel_registration_verified": registration_verified,
        "target_domain_input_verified": target_domain_input_verified,
        "reviewed_bone_gate": gate_evidence,
        "thresholds": {
            "bone_gate_threshold": runtime.bone_gate_threshold,
            "abstention_threshold": runtime.abstention_threshold,
            "selection_source": "checkpoint_bound_manifest",
        },
        "raw_engineering_outputs": {
            "available": True,
            "spatial_use_allowed": False,
            "path": str(raw_archive_path),
            "sha256": asset_sha256["raw_engineering_outputs_path"],
            "summary": raw_summary,
        },
        "bone_activity_spectrum": spectrum,
        "asset_sha256": asset_sha256,
        "medical_boundary": runtime.medical_boundary,
    }
    evidence_path = Path(f"{prefix}_evidence.json")
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["evidence_manifest_path"] = str(evidence_path)
    payload["evidence_manifest_sha256"] = _sha256_file(evidence_path)
    return payload


def _validate_checkpoint_metadata(
    metadata: Mapping[str, Any], manifest: Mapping[str, Any], checkpoint_sha256: str
) -> None:
    if metadata.get("model_id") != manifest.get("model_id"):
        raise ValueError("Bone-activity checkpoint model_id mismatch")
    if metadata.get("model_family") != _MODEL_FAMILY or manifest.get("model_family") != _MODEL_FAMILY:
        raise ValueError("Bone-activity checkpoint model_family mismatch")
    if _mapping(metadata.get("model_config")) != _mapping(manifest.get("model_config")):
        raise ValueError("Bone-activity checkpoint model_config mismatch")
    if _mapping(metadata.get("training_domain")) != _mapping(manifest.get("training_domain")):
        raise ValueError("Bone-activity checkpoint training_domain mismatch")
    if (
        set(metadata.get("outputs") or []) != _REQUIRED_OUTPUTS
        or set(manifest.get("outputs") or []) != _REQUIRED_OUTPUTS
    ):
        raise ValueError("Bone-activity checkpoint outputs contract mismatch")
    if _mapping(metadata.get("inference_thresholds")) != _mapping(manifest.get("inference_thresholds")):
        raise ValueError("Bone-activity checkpoint inference thresholds mismatch")
    for field in ("runtime_allowed", "clinical_claim_allowed"):
        if metadata.get(field) is not manifest.get(field):
            raise ValueError(f"Bone-activity checkpoint and manifest {field} flags disagree")
    if metadata.get("clinical_claim_allowed") is not False or manifest.get("clinical_claim_allowed") is not False:
        raise ValueError("Bone-activity runtime cannot allow clinical claims")
    promotion = _mapping(manifest.get("promotion"))
    promotion_checkpoint_sha256 = _normalized_sha256(promotion.get("checkpoint_sha256"))
    if promotion_checkpoint_sha256 and promotion_checkpoint_sha256 != checkpoint_sha256:
        raise ValueError("Bone-activity promotion checkpoint SHA256 mismatch")


def _load_registered_images(
    white_path: str | Path,
    fluorescence_path: str | Path,
    *,
    device: torch.device,
    input_shape: tuple[int, int],
) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
    height, width = _validated_shape(input_shape)
    with Image.open(white_path) as white_image:
        rgb = np.asarray(white_image.convert("RGB"), dtype=np.uint8).copy()
    with Image.open(fluorescence_path) as fluorescence_image:
        fluorescence = np.asarray(fluorescence_image.convert("L"), dtype=np.uint8).copy()
    if rgb.shape[:2] != fluorescence.shape:
        raise ValueError("White-light and fluorescence image dimensions must match")
    resized_white = np.asarray(
        Image.fromarray(rgb).resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32
    )
    resized_fluorescence = np.asarray(
        Image.fromarray(fluorescence).resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32
    )
    white_tensor = torch.from_numpy(resized_white.transpose(2, 0, 1)[None].copy() / 255.0).to(device)
    fluorescence_tensor = torch.from_numpy(resized_fluorescence[None, None].copy() / 255.0).to(device)
    return white_tensor, fluorescence_tensor, {"width": int(rgb.shape[1]), "height": int(rgb.shape[0])}


def _reviewed_gate(
    value: Any,
    *,
    width: int,
    height: int,
    model_shape: tuple[int, int],
    source_sha256: str,
    device: torch.device,
) -> tuple[torch.Tensor | None, bool, list[str], dict[str, Any]]:
    record = _mapping(value)
    path_value = str(record.get("path") or "").strip()
    expected_sha = _normalized_sha256(record.get("sha256"))
    evidence = {
        "path": path_value or None,
        "sha256": expected_sha or None,
        "physician_reviewed": record.get("physician_reviewed") is True,
        "trusted_review": record.get("trusted_review") is True,
        "review_status": record.get("review_status"),
        "annotation_id": record.get("annotation_id"),
        "annotation_version": record.get("annotation_version"),
        "source_input_id": record.get("source_input_id"),
        "source_checksum": record.get("source_checksum"),
        "positive_pixel_count": record.get("positive_pixel_count"),
        "reviewed_at": record.get("reviewed_at"),
        "reviewed_by": record.get("reviewed_by"),
    }
    identity_trusted = _trusted_physician_review(record.get("reviewed_by"))
    annotation_version = record.get("annotation_version")
    binding_complete = bool(
        str(record.get("annotation_id") or "").strip()
        and isinstance(annotation_version, int)
        and not isinstance(annotation_version, bool)
        and annotation_version >= 1
        and str(record.get("source_input_id") or "").strip()
        and str(record.get("reviewed_at") or "").strip()
    )
    source_bound = _normalized_sha256(record.get("source_checksum")) == source_sha256
    trusted = bool(
        record.get("physician_reviewed") is True
        and record.get("trusted_review") is True
        and str(record.get("review_status") or "") in _REVIEWED_GATE_STATES
        and identity_trusted
        and binding_complete
        and source_bound
    )
    reasons: list[str] = []
    if record.get("physician_reviewed") is not True or record.get("trusted_review") is not True:
        reasons.append("physician_reviewed_bone_gate_untrusted")
    if str(record.get("review_status") or "") not in _REVIEWED_GATE_STATES:
        reasons.append("physician_reviewed_bone_gate_status_invalid")
    if not identity_trusted:
        reasons.append("physician_reviewed_bone_gate_reviewer_identity_untrusted")
    if not binding_complete:
        reasons.append("physician_reviewed_bone_gate_annotation_binding_missing")
    if not source_bound:
        reasons.append("physician_reviewed_bone_gate_source_checksum_mismatch")
    if not path_value or not expected_sha:
        reasons.append("physician_reviewed_bone_gate_evidence_missing")
        return None, False, reasons, evidence
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        reasons.append("physician_reviewed_bone_gate_file_missing")
        return None, False, reasons, evidence
    actual_sha = _sha256_file(path)
    evidence["actual_sha256"] = actual_sha
    if actual_sha != expected_sha:
        reasons.append("physician_reviewed_bone_gate_sha256_mismatch")
        return None, False, reasons, evidence
    try:
        with Image.open(path) as image:
            gate = np.asarray(image.convert("L"), dtype=np.uint8).copy()
    except (OSError, ValueError) as exc:
        reasons.append("physician_reviewed_bone_gate_unreadable")
        evidence["read_error"] = str(exc)
        return None, False, reasons, evidence
    if gate.shape != (height, width):
        reasons.append("physician_reviewed_bone_gate_dimension_mismatch")
        return None, False, reasons, evidence
    if not bool((gate > 127).any()):
        reasons.append("physician_reviewed_bone_gate_empty")
        return None, False, reasons, evidence
    positive_pixel_count = int((gate > 127).sum())
    evidence["actual_positive_pixel_count"] = positive_pixel_count
    recorded_positive_pixel_count = record.get("positive_pixel_count")
    if (
        not isinstance(recorded_positive_pixel_count, int)
        or isinstance(recorded_positive_pixel_count, bool)
        or recorded_positive_pixel_count != positive_pixel_count
    ):
        reasons.append("physician_reviewed_bone_gate_positive_pixel_count_mismatch")
        trusted = False
    model_height, model_width = _validated_shape(model_shape)
    resized = np.asarray(
        Image.fromarray(gate).resize((model_width, model_height), Image.Resampling.NEAREST), dtype=np.uint8
    )
    tensor = torch.from_numpy((resized > 127)[None, None]).to(device=device)
    return tensor, trusted, reasons, evidence


def _trusted_physician_review(value: Any) -> bool:
    actor = _mapping(value)
    return bool(
        str(actor.get("role") or "") == "physician"
        and str(actor.get("auth_source") or "") in {"institution_sso", "signed_session", "verified_identity_token"}
        and str(actor.get("actor_id") or "").strip()
        and str(actor.get("institution") or "").strip()
    )


def _raw_engineering_arrays(value: Mapping[str, torch.Tensor]) -> dict[str, np.ndarray]:
    return {
        "bone_gate_probability": _single_array(value["bone_gate_probability"]),
        "activity_score": _single_array(value["activity_score"]),
        "class_probabilities": value["class_probabilities"].detach().to(device="cpu", dtype=torch.float32).numpy()[0],
        "uncertainty": _single_array(value["uncertainty"]),
    }


def _raw_engineering_summary(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    class_probabilities = arrays["class_probabilities"]
    predicted = np.argmax(np.nan_to_num(class_probabilities, nan=-1.0), axis=0)
    return {
        "finite": bool(all(np.isfinite(value).all() for value in arrays.values())),
        "bone_gate_probability_mean": _finite_mean(arrays["bone_gate_probability"]),
        "activity_score_mean": _finite_mean(arrays["activity_score"]),
        "uncertainty_mean": _finite_mean(arrays["uncertainty"]),
        "predicted_class_pixel_counts": {
            class_name: int((predicted == index).sum()) for index, class_name in enumerate(BONE_ACTIVITY_CLASSES)
        },
    }


def _safe_arrays(
    safe: Mapping[str, Any],
    reviewed_gate: torch.Tensor,
    *,
    output_shape: tuple[int, int],
) -> dict[str, np.ndarray]:
    height, width = output_shape
    score = _resize_tensor(safe["activity_score"], (height, width), mode="bilinear")[0, 0]
    probabilities = _resize_tensor(safe["class_probabilities"], (height, width), mode="bilinear")[0]
    available = (
        _resize_tensor(safe["activity_score_available_mask"].to(dtype=torch.float32), (height, width), mode="nearest")[
            0, 0
        ]
        > 0.5
    )
    gate = _resize_tensor(reviewed_gate.to(dtype=torch.float32), (height, width), mode="nearest")[0, 0] > 0.5
    classes = torch.argmax(probabilities, dim=0).to(dtype=torch.uint8) + 1
    class_map = torch.zeros((height, width), dtype=torch.uint8, device=classes.device)
    class_map[gate & ~available] = 4
    class_map[gate & available] = classes[gate & available]
    score = score * available.to(dtype=score.dtype)
    return {
        "activity_score": score.detach().cpu().numpy().astype(np.float32),
        "class_map": class_map.detach().cpu().numpy().astype(np.uint8),
        "bone_gate": gate.detach().cpu().numpy().astype(np.bool_),
    }


def _write_safe_candidate_assets(
    *,
    prefix: Path,
    arrays: Mapping[str, np.ndarray],
    runtime: BoneActivityRuntimeEvidence,
    raw_archive_path: Path,
    raw_summary: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    score_path = Path(f"{prefix}_activity_score.png")
    class_map_path = Path(f"{prefix}_activity_classes.png")
    Image.fromarray(_unit_preview(arrays["activity_score"])).save(score_path)
    Image.fromarray(_class_map_preview(arrays["class_map"])).save(class_map_path)
    assets = {
        "activity_score_path": str(score_path),
        "activity_class_map_path": str(class_map_path),
    }
    gate_pixels = int(arrays["bone_gate"].sum())
    candidates: dict[str, dict[str, Any]] = {}
    for class_value, (key, label) in enumerate(
        (
            ("low_activity_candidate", "Low-activity candidate"),
            ("transition_candidate", "Transition review region"),
            ("high_activity_candidate", "High-activity reference"),
            ("ignore_region", "Unavailable region"),
        ),
        start=1,
    ):
        mask = arrays["class_map"] == class_value
        path = Path(f"{prefix}_{key}.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(path)
        assets[f"{key}_path"] = str(path)
        area = int(mask.sum())
        candidates[key] = {
            "available": True,
            "label": label,
            "positive_area_px": area,
            "bone_gate_fraction": float(area / gate_pixels) if gate_pixels else 0.0,
            "path": str(path),
            "sources": ["promoted_bone_activity_multitask_checkpoint"],
        }
    spectrum = {
        "schema_version": "osteo-vision-bone-activity-spectrum-v2",
        "available": True,
        "status": "available_for_physician_review",
        "activity_score": {
            "available": True,
            "path": str(score_path),
            "scale": [0.0, 1.0],
        },
        "activity_class_map_path": str(class_map_path),
        **candidates,
        "class_map_encoding": {
            "0": "outside_reviewed_bone_gate",
            "1": "low_activity_candidate",
            "2": "transition_candidate",
            "3": "high_activity_candidate",
            "4": "ignore_region",
        },
        "thresholds": {
            "bone_gate": runtime.bone_gate_threshold,
            "abstention": runtime.abstention_threshold,
        },
        "calibration_status": "target_domain_promotion_evidence_bound",
        "spatial_effect_applied": True,
        "review_required": True,
        "raw_engineering_outputs_path": str(raw_archive_path),
        "raw_engineering_summary": dict(raw_summary),
        "confidence_statement": "Model probabilities require physician review and do not express resection success.",
    }
    return assets, spectrum


def _unavailable_spectrum(
    *,
    runtime: BoneActivityRuntimeEvidence,
    raw_archive_path: Path,
    raw_summary: Mapping[str, Any],
    failure_reasons: list[str],
) -> dict[str, Any]:
    unavailable = {"available": False, "positive_area_px": None, "bone_gate_fraction": None, "path": None}
    return {
        "schema_version": "osteo-vision-bone-activity-spectrum-v2",
        "available": False,
        "status": "safe_fallback_engineering_evidence_only",
        "failure_reasons": failure_reasons,
        "activity_score": {
            "available": False,
            "path": None,
            "scale": [0.0, 1.0],
        },
        "activity_class_map_path": None,
        "low_activity_candidate": {**unavailable, "label": "Low-activity candidate"},
        "transition_candidate": {**unavailable, "label": "Transition review region"},
        "high_activity_candidate": {**unavailable, "label": "High-activity reference"},
        "ignore_region": {**unavailable, "label": "Unavailable region", "sources": ["safety_gate"]},
        "class_map_encoding": {
            "0": "outside_reviewed_bone_gate",
            "1": "low_activity_candidate",
            "2": "transition_candidate",
            "3": "high_activity_candidate",
            "4": "ignore_region",
        },
        "thresholds": {
            "bone_gate": runtime.bone_gate_threshold,
            "abstention": runtime.abstention_threshold,
        },
        "calibration_status": "pending_target_domain_validation",
        "spatial_effect_applied": False,
        "review_required": True,
        "raw_engineering_outputs_path": str(raw_archive_path),
        "raw_engineering_summary": dict(raw_summary),
        "confidence_statement": "Engineering outputs remain unavailable for spatial clinical use.",
    }


def _resize_tensor(value: torch.Tensor, output_shape: tuple[int, int], *, mode: str) -> torch.Tensor:
    if mode == "nearest":
        return F.interpolate(value.to(dtype=torch.float32), size=output_shape, mode=mode)
    return F.interpolate(value.to(dtype=torch.float32), size=output_shape, mode=mode, align_corners=False)


def _single_array(value: torch.Tensor) -> np.ndarray:
    return value.detach().to(device="cpu", dtype=torch.float32).numpy()[0, 0].copy()


def _finite_mean(value: np.ndarray) -> float | None:
    return float(value.mean()) if np.isfinite(value).all() else None


def _unit_preview(value: np.ndarray) -> np.ndarray:
    return np.clip(value * 255.0, 0.0, 255.0).astype(np.uint8)


def _class_map_preview(value: np.ndarray) -> np.ndarray:
    palette = np.asarray(
        [
            [0, 0, 0],
            [187, 56, 56],
            [194, 139, 39],
            [38, 143, 109],
            [104, 113, 124],
        ],
        dtype=np.uint8,
    )
    return palette[np.clip(value, 0, 4)]


def _probability_threshold(value: Any, field: str) -> float:
    threshold = float(value)
    if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
        raise ValueError(f"Bone-activity {field} must be finite and within (0, 1)")
    return threshold


def _validated_shape(value: tuple[int, int]) -> tuple[int, int]:
    if len(value) != 2:
        raise ValueError("Bone-activity input_shape must contain height and width")
    height, width = (int(value[0]), int(value[1]))
    if height < 24 or width < 24:
        raise ValueError("Bone-activity input_shape dimensions must be at least 24 pixels")
    return height, width


def _evidence_id(case_id: str, checkpoint_sha256: str, source: Mapping[str, Any]) -> str:
    value = "|".join(
        (
            case_id,
            checkpoint_sha256,
            str(source.get("white_light_sha256") or ""),
            str(source.get("fluorescence_sha256") or ""),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalized_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if len(text) == 64 and all(character in "0123456789abcdef" for character in text) else ""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    result = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    return result or "case"
