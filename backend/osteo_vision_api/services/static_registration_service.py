from __future__ import annotations

import hashlib
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import ArrayLike

from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.services.three_d_evidence import build_three_d_evidence
from osteo_vision_core.navigation.camera_registration import (
    CameraRegistrationResult,
    compose_transforms,
    export_camera_transform,
    register_camera_pnp,
)
from osteo_vision_core.navigation.coordinate_contract import CoordinateContractError, validate_coordinate_transform
from osteo_vision_core.navigation.rigid_registration import (
    RigidRegistrationError,
    export_rigid_transform,
    register_rigid_points,
)

L1_INPUT_MANIFEST_SCHEMA = "osteo-vision-l1-registration-input-v1"
L1_POINT_ARTIFACT_SCHEMA = "osteo-vision-l1-point-correspondence-v1"
SUPPORTED_MODEL_FORMATS = {"stl", "glb", "gltf"}
MIN_REGISTRATION_POINTS = 4
MIN_VALIDATION_POINTS = 3
_STL_VALIDATION_CHUNK_TRIANGLES = 65_536
_BINARY_STL_TRIANGLE_DTYPE = np.dtype(
    [
        ("normal", "<f4", (3,)),
        ("vertices", "<f4", (3, 3)),
        ("attribute_byte_count", "<u2"),
    ]
)


class StaticRegistrationRequestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class StaticRegistrationService:
    def __init__(self, settings: Settings, repo: CaseRepository) -> None:
        self.settings = settings
        self.repo = repo

    def register(self, payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        case = self.repo.get(case_id)
        if case is None:
            raise StaticRegistrationRequestError("case_not_found", f"Case not found: {case_id}")
        normalized, input_manifest_path, input_provenance = self._normalized_payload(payload)
        rigid_coordinate_contract = (
            normalized.get("coordinate_contract") if isinstance(normalized.get("coordinate_contract"), dict) else None
        )
        camera_coordinate_contract = (
            normalized.get("camera_coordinate_contract")
            if isinstance(normalized.get("camera_coordinate_contract"), dict)
            else None
        )
        model_path = self._allowed_file(
            normalized.get("model_path") or case.three_d_evidence.get("model_path"), "model"
        )
        model_provenance = self._model_provenance(
            model_path,
            expected_sha256=normalized.get("model_sha256"),
            declared_format=normalized.get("model_format"),
        )
        source_points = normalized.get("source_points")
        target_points = normalized.get("target_points")
        validation_source = normalized.get("validation_source_points")
        validation_target = normalized.get("validation_target_points")
        if validation_source is None or validation_target is None:
            raise StaticRegistrationRequestError(
                "tre_validation_missing",
                "L1 static registration requires independent validation points for TRE.",
            )
        fre_threshold = _positive_number(normalized.get("fre_threshold_mm"), "fre_threshold_mm")
        tre_threshold = _positive_number(normalized.get("tre_threshold_mm"), "tre_threshold_mm")
        threshold_source = str(normalized.get("threshold_source") or "").strip()
        if not threshold_source:
            raise StaticRegistrationRequestError(
                "threshold_source_missing", "Registration threshold source is required."
            )
        registration_mode = str(normalized.get("registration_method") or "rigid_points").strip()
        if registration_mode not in {"rigid_points", "rigid_points_with_pnp"}:
            raise StaticRegistrationRequestError(
                "registration_method_unsupported",
                f"Unsupported L1 registration method: {registration_mode}",
            )

        try:
            registration = register_rigid_points(
                cast(ArrayLike, source_points),
                cast(ArrayLike, target_points),
                source_space=str(normalized.get("source_space") or ""),
                target_space=str(normalized.get("target_space") or ""),
                unit=str(normalized.get("unit") or "mm"),
                validation_source_points=validation_source,
                validation_target_points=validation_target,
                source_frame_metadata=(
                    None if rigid_coordinate_contract is None else rigid_coordinate_contract["source_frame"]
                ),
                target_frame_metadata=(
                    None if rigid_coordinate_contract is None else rigid_coordinate_contract["target_frame"]
                ),
                matrix_convention=(
                    None if rigid_coordinate_contract is None else rigid_coordinate_contract["matrix_convention"]
                ),
            )
        except RigidRegistrationError:
            raise

        output_dir = self.settings.artifact_root / "three_d_registration" / _safe_name(case_id) / job_id
        rigid_transform_export = export_rigid_transform(registration, output_dir / "rigid_transform.json")
        transform_export = rigid_transform_export
        camera_registration: CameraRegistrationResult | None = None
        camera_pose_export: dict[str, Any] | None = None
        composed_camera_export: dict[str, Any] | None = None
        reprojection_threshold: float | None = None
        camera_calibration_evidence: dict[str, Any] = {}
        threshold_approval_source = normalized.get("threshold_approval")
        threshold_approval = threshold_approval_source if isinstance(threshold_approval_source, dict) else {}
        microscope_pose_value = normalized.get("microscope_pose_evidence")
        microscope_pose = microscope_pose_value if isinstance(microscope_pose_value, dict) else {}
        actor = normalized.get("review_actor") if isinstance(normalized.get("review_actor"), dict) else None
        doctor_status = str(normalized.get("doctor_review_status") or "review_required")
        transform_chain = [
            {
                "name": "CBCT model to L1 static reference",
                "from_space": registration.source_space,
                "to_space": registration.target_space,
                "direction": "forward",
                "unit": registration.unit,
                "source_frame": registration.source_frame,
                "target_frame": registration.target_frame,
                "matrix_convention": registration.matrix_convention,
                "path": rigid_transform_export["path"],
                "status": "ready",
            }
        ]
        if registration_mode == "rigid_points_with_pnp":
            if (
                normalized.get("validation_camera_object_points") is None
                or normalized.get("validation_camera_image_points") is None
            ):
                raise StaticRegistrationRequestError(
                    "camera_reprojection_validation_missing",
                    "Calibrated PnP requires independent 3D-to-2D validation points.",
                )
            reprojection_threshold = _positive_number(
                normalized.get("reprojection_threshold_px"),
                "reprojection_threshold_px",
            )
            camera_registration = register_camera_pnp(
                cast(ArrayLike, normalized.get("camera_object_points")),
                cast(ArrayLike, normalized.get("camera_image_points")),
                camera_matrix=cast(ArrayLike, normalized.get("camera_matrix")),
                distortion_coefficients=normalized.get("distortion_coefficients"),
                image_size_px=cast(tuple[int, int] | list[int], normalized.get("image_size_px")),
                object_space=registration.target_space,
                camera_space=str(normalized.get("camera_space") or "camera_optical"),
                intrinsics_id=str(normalized.get("intrinsics_id") or ""),
                magnification=cast(float, microscope_pose.get("magnification")),
                working_distance_mm=cast(float, microscope_pose.get("working_distance_mm")),
                validation_object_points=normalized.get("validation_camera_object_points"),
                validation_image_points=normalized.get("validation_camera_image_points"),
                object_frame_metadata=(
                    None if camera_coordinate_contract is None else camera_coordinate_contract["source_frame"]
                ),
                camera_frame_metadata=(
                    None if camera_coordinate_contract is None else camera_coordinate_contract["target_frame"]
                ),
                matrix_convention=(
                    None if camera_coordinate_contract is None else camera_coordinate_contract["matrix_convention"]
                ),
            )
            composed_matrix = compose_transforms(
                camera_registration.matrix,
                registration.matrix,
            )
            camera_pose_export = export_camera_transform(
                camera_registration,
                output_dir / "reference_to_camera_transform.json",
            )
            composed_camera_export = export_camera_transform(
                camera_registration,
                output_dir / "cbct_to_camera_transform.json",
                composed_matrix=composed_matrix,
                composed_source_space=registration.source_space,
                composed_source_frame_metadata=(
                    registration.source_frame if rigid_coordinate_contract is not None else None
                ),
            )
            transform_export = composed_camera_export
            transform_chain.append(
                {
                    "name": "L1 static reference to calibrated microscope camera",
                    "from_space": registration.target_space,
                    "to_space": camera_registration.camera_space,
                    "direction": "forward",
                    "unit": "mm",
                    "source_frame": camera_registration.object_frame,
                    "target_frame": camera_registration.camera_frame,
                    "matrix_convention": camera_registration.matrix_convention,
                    "path": camera_pose_export["path"],
                    "status": "ready",
                }
            )
            microscope_pose["intrinsics_id"] = camera_registration.intrinsics_id
            camera_calibration_evidence = self._camera_calibration_evidence(
                normalized,
                camera_registration=camera_registration,
            )
            microscope_pose.update(
                {
                    "calibration_status": (
                        "verified" if camera_calibration_evidence["artifact_validation"]["valid"] else "invalid"
                    ),
                    "calibrated_at": camera_calibration_evidence.get("calibrated_at"),
                    "calibration_method": camera_calibration_evidence.get("calibration_method"),
                    "calibration_reprojection_error_px": camera_calibration_evidence.get(
                        "calibration_reprojection_error_px"
                    ),
                    "calibration_reprojection_threshold_px": camera_calibration_evidence.get(
                        "calibration_reprojection_threshold_px"
                    ),
                    "calibration_magnification_min": camera_calibration_evidence.get("calibration_magnification_min"),
                    "calibration_magnification_max": camera_calibration_evidence.get("calibration_magnification_max"),
                    "calibration_working_distance_min_mm": camera_calibration_evidence.get(
                        "calibration_working_distance_min_mm"
                    ),
                    "calibration_working_distance_max_mm": camera_calibration_evidence.get(
                        "calibration_working_distance_max_mm"
                    ),
                }
            )
        explicit = {
            **case.three_d_evidence,
            "model_path": str(model_path),
            "model_format": model_path.suffix.lstrip(".").lower(),
            "model_sha256": model_provenance.get("sha256"),
            "model_expected_sha256": model_provenance.get("expected_sha256"),
            "model_provenance": model_provenance,
            "registration_input_provenance": input_provenance,
            "registration_status": "registered",
            "registration_method": (
                registration.method
                if camera_registration is None
                else f"{registration.method}+{camera_registration.method}"
            ),
            "registration_error_mm": registration.tre_mm,
            "registration_error_threshold_mm": tre_threshold,
            "registration_error_source": "independent_target_points",
            "fre_threshold_mm": fre_threshold,
            "tre_threshold_mm": tre_threshold,
            "fiducial_count": registration.registration_count,
            "model_coordinate_space": (
                case.three_d_evidence.get("model_coordinate_space")
                or case.three_d_evidence.get("coordinate_space")
                or registration.source_space
            ),
            "coordinate_space": (
                registration.target_space if camera_registration is None else camera_registration.camera_space
            ),
            "transform_path": transform_export["path"],
            "transform_sha256": transform_export["sha256"],
            "transform_format": transform_export["format"],
            "transform_chain": transform_chain,
            "coordinate_frame_contracts": {
                "rigid": rigid_coordinate_contract,
                "camera": camera_coordinate_contract,
            },
            "doctor_review_status": doctor_status,
            "requested_navigation_level": "L1",
            "microscope_pose_evidence": microscope_pose,
            "camera_registration_status": ("not_requested" if camera_registration is None else "estimated"),
            "camera_intrinsics_id": (None if camera_registration is None else camera_registration.intrinsics_id),
            "reprojection_error_px": (
                None if camera_registration is None else camera_registration.validation_reprojection_rmse_px
            ),
            "reprojection_fit_error_px": (
                None if camera_registration is None else camera_registration.reprojection_rmse_px
            ),
            "reprojection_error_threshold_px": reprojection_threshold,
            "reprojection_error_source": (
                None if camera_registration is None else "independent_camera_validation_points"
            ),
            "camera_calibration_evidence": camera_calibration_evidence,
            "threshold_approval": threshold_approval,
            "boundary_note": (
                "L1 static/phantom registration engineering evidence. It requires physician review and cannot be "
                "used as a real-time intraoperative resection boundary."
            ),
        }
        evidence = build_three_d_evidence(
            parameters={"three_d_evidence": explicit},
            source_inputs=case.inputs,
            analysis_mode="l1_static_registration",
            run_id=job_id,
        )
        threshold_failures: list[str] = []
        threshold_failures.extend(str(item) for item in model_provenance.get("failure_reasons", []))
        threshold_failures.extend(str(item) for item in input_provenance.get("failure_reasons", []))
        if registration.fre_mm > fre_threshold:
            threshold_failures.append("fre_threshold_exceeded")
        if registration.tre_mm is None or registration.tre_mm > tre_threshold:
            threshold_failures.append("tre_threshold_exceeded")
        if camera_registration is not None:
            validation_error = camera_registration.validation_reprojection_rmse_px
            if validation_error is None:
                threshold_failures.append("camera_reprojection_validation_missing")
            elif reprojection_threshold is not None and validation_error > reprojection_threshold:
                threshold_failures.append("reprojection_error_threshold_exceeded")
            if reprojection_threshold is not None and camera_registration.reprojection_rmse_px > reprojection_threshold:
                threshold_failures.append("reprojection_fit_error_threshold_exceeded")
        if threshold_failures:
            evidence = _degrade_evidence(evidence, threshold_failures)
        reviewed_at = datetime.now(timezone.utc).isoformat() if doctor_status == "accepted" and actor else None
        evidence.update(
            {
                "model_sha256": model_provenance.get("sha256"),
                "model_expected_sha256": model_provenance.get("expected_sha256"),
                "model_provenance": model_provenance,
                "registration_input_provenance": input_provenance,
                "coordinate_frame_contracts": {
                    "rigid": rigid_coordinate_contract,
                    "camera": camera_coordinate_contract,
                },
                "fre_mm": registration.fre_mm,
                "fre_threshold_mm": fre_threshold,
                "tre_mm": registration.tre_mm,
                "tre_threshold_mm": tre_threshold,
                "registration_threshold_source": threshold_source,
                "registration_input_mode": str(payload.get("input_mode") or "manual_metadata"),
                "registration_input_manifest_path": input_manifest_path,
                "camera_registration_status": ("not_requested" if camera_registration is None else "estimated"),
                "camera_intrinsics_id": (None if camera_registration is None else camera_registration.intrinsics_id),
                "reprojection_error_px": (
                    None if camera_registration is None else camera_registration.validation_reprojection_rmse_px
                ),
                "reprojection_fit_error_px": (
                    None if camera_registration is None else camera_registration.reprojection_rmse_px
                ),
                "reprojection_error_threshold_px": reprojection_threshold,
                "reprojection_error_source": (
                    None if camera_registration is None else "independent_camera_validation_points"
                ),
                "doctor_reviewed_by": actor if doctor_status == "accepted" else None,
                "doctor_reviewed_at": reviewed_at,
            }
        )
        registration_manifest = {
            "schema_version": "osteo-vision-l1-static-registration-v2",
            "case_id": case_id,
            "job_id": job_id,
            "input_mode": str(payload.get("input_mode") or "manual_metadata"),
            "input_manifest_path": input_manifest_path,
            "input_provenance": input_provenance,
            "model_path": str(model_path),
            "model_provenance": model_provenance,
            "registration": registration.to_manifest(),
            "registration_mode": registration_mode,
            "rigid_transform": rigid_transform_export,
            "camera_registration": (None if camera_registration is None else camera_registration.to_manifest()),
            "camera_pose_transform": camera_pose_export,
            "transform": transform_export,
            "thresholds": {
                "fre_threshold_mm": fre_threshold,
                "tre_threshold_mm": tre_threshold,
                "reprojection_threshold_px": reprojection_threshold,
                "source": threshold_source,
                "approval": threshold_approval or None,
            },
            "camera_calibration_evidence": camera_calibration_evidence or None,
            "doctor_review_status": doctor_status,
            "doctor_reviewed_by": actor if doctor_status == "accepted" else None,
            "doctor_reviewed_at": reviewed_at,
            "navigation_safety": {
                "navigation_ready": evidence.get("navigation_ready"),
                "navigation_level": evidence.get("navigation_level"),
                "failure_reasons": evidence.get("failure_reasons"),
                "fallback_mode": evidence.get("fallback_mode"),
            },
        }
        manifest_path = output_dir / "registration_manifest.json"
        _write_json(manifest_path, registration_manifest)
        registration_manifest_sha256 = sha256_for_path(manifest_path)
        evidence.update(
            {
                "registration_output_manifest_path": str(manifest_path),
                "registration_output_manifest_sha256": registration_manifest_sha256,
            }
        )
        return {
            "case_id": case_id,
            "input_mode": str(payload.get("input_mode") or "manual_metadata"),
            "input_manifest_path": input_manifest_path,
            "input_provenance": input_provenance,
            "model_sha256": model_provenance.get("sha256"),
            "model_provenance": model_provenance,
            "registration_status": "registered",
            "fre_mm": registration.fre_mm,
            "tre_mm": registration.tre_mm,
            "camera_registration_status": ("not_requested" if camera_registration is None else "estimated"),
            "reprojection_error_px": (
                None if camera_registration is None else camera_registration.validation_reprojection_rmse_px
            ),
            "reprojection_fit_error_px": (
                None if camera_registration is None else camera_registration.reprojection_rmse_px
            ),
            "transform_path": transform_export["path"],
            "transform_sha256": transform_export["sha256"],
            "registration_manifest_path": str(manifest_path),
            "registration_manifest_sha256": registration_manifest_sha256,
            "three_d_evidence": evidence,
        }

    def failure_result(self, payload: dict[str, Any], *, job_id: str, code: str, message: str) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        case = self.repo.get(case_id)
        prior = dict(case.three_d_evidence) if case is not None else {}
        evidence = {
            **prior,
            "schema_version": "osteo-vision-three-d-evidence-v2",
            "analysis_mode": "l1_static_registration",
            "run_id": job_id,
            "registration_status": "failed",
            "requested_navigation_level": "L1",
            "navigation_ready": False,
            "navigation_level": "L0",
            "degradation_state": "safety_gate_degraded",
            "fallback_mode": "unregistered_3d_reference",
            "failure_reasons": [code],
            "registration_failure": {"code": code, "message": message},
            "doctor_review_status": str(payload.get("doctor_review_status") or "review_required"),
            "doctor_reviewed_by": None,
            "doctor_reviewed_at": None,
            "replay_mode": None,
            "video_evidence": None,
            "pose_manifest_path": None,
            "pose_manifest_sha256": None,
            "projection_evidence": None,
            "l2_coordinate_contracts": None,
            "calibration_selection": None,
            "overlay_evidence": None,
            "l2_threshold_approval": None,
            "l2_measurement_evidence": None,
            "l2_threshold_policy_evidence": None,
            "l1_evidence_snapshot": None,
            "pose_replay_manifest_path": None,
            "pose_replay_manifest_sha256": None,
            "pose_replay_frames_csv_path": None,
            "pose_replay_frames_csv_sha256": None,
            "artifact_lifecycle": {
                "status": "failed_closed",
                "run_id": job_id,
                "artifact_kind": "l1_static_registration",
                "overlay_active": False,
                "prior_l2_active_references_revoked": True,
            },
        }
        return {
            "case_id": case_id,
            "registration_status": "failed",
            "error_code": code,
            "error_message": message,
            "fallback_mode": "unregistered_3d_reference",
            "three_d_evidence": evidence,
            "job_id": job_id,
        }

    def _normalized_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
        case_id = str(payload.get("case_id") or "").strip()
        if payload.get("input_mode") == "offline_manifest":
            manifest_path = self._allowed_file(payload.get("registration_manifest_path"), "registration manifest")
            manifest, actual_sha256, size_bytes = self._read_checksum_json_artifact(
                manifest_path,
                expected_sha256=payload.get("registration_manifest_sha256"),
                code_prefix="registration_manifest",
            )
            normalized = self._flatten_registration_input_manifest(manifest, case_id=case_id)
            normalized.update(
                {
                    "case_id": case_id,
                    "input_mode": "offline_manifest",
                    "registration_manifest_path": str(manifest_path),
                    "registration_manifest_sha256": actual_sha256,
                    "doctor_review_status": payload.get("doctor_review_status", "review_required"),
                    "review_actor": payload.get("review_actor"),
                }
            )
            provenance = {
                "schema_version": "osteo-vision-l1-input-provenance-v1",
                "input_kind": "registration_input_manifest",
                "artifact_path": str(manifest_path),
                "artifact_expected_sha256": str(payload.get("registration_manifest_sha256") or "").lower(),
                "artifact_sha256": actual_sha256,
                "artifact_size_bytes": size_bytes,
                "artifact_schema_version": manifest.get("schema_version"),
                "checksum_match": True,
                "coordinate_contract": normalized["coordinate_contract"],
                "point_set_counts": normalized["point_set_counts"],
                "valid": True,
                "failure_reasons": [],
            }
            return normalized, str(manifest_path), provenance

        normalized = dict(payload)
        artifact_path_value = payload.get("point_correspondence_artifact_path")
        if not str(artifact_path_value or "").strip():
            return (
                normalized,
                None,
                {
                    "schema_version": "osteo-vision-l1-input-provenance-v1",
                    "input_kind": "legacy_unbound_manual_metadata",
                    "artifact_path": None,
                    "artifact_expected_sha256": None,
                    "artifact_sha256": None,
                    "checksum_match": False,
                    "coordinate_contract": None,
                    "point_set_counts": None,
                    "valid": False,
                    "failure_reasons": ["point_correspondence_artifact_missing"],
                },
            )

        artifact_path = self._allowed_file(artifact_path_value, "point correspondence artifact")
        artifact, actual_sha256, size_bytes = self._read_checksum_json_artifact(
            artifact_path,
            expected_sha256=payload.get("point_correspondence_artifact_sha256"),
            code_prefix="point_correspondence_artifact",
        )
        artifact_inputs = self._flatten_point_correspondence_artifact(artifact, case_id=case_id)
        bound_fields = {
            "registration_method",
            "source_points",
            "target_points",
            "validation_source_points",
            "validation_target_points",
            "source_space",
            "target_space",
            "unit",
            "camera_object_points",
            "camera_image_points",
            "validation_camera_object_points",
            "validation_camera_image_points",
            "camera_space",
        }
        mismatches = sorted(
            field
            for field in bound_fields
            if field in payload
            and field in artifact_inputs
            and not _structures_equal(payload.get(field), artifact_inputs.get(field))
        )
        if mismatches:
            raise StaticRegistrationRequestError(
                "point_correspondence_request_mismatch",
                "Manual point fields conflict with the checksum-bound point artifact: " + ", ".join(mismatches),
            )
        normalized.update(artifact_inputs)
        normalized["point_correspondence_artifact_path"] = str(artifact_path)
        normalized["point_correspondence_artifact_sha256"] = actual_sha256
        provenance = {
            "schema_version": "osteo-vision-l1-input-provenance-v1",
            "input_kind": "point_correspondence_artifact",
            "artifact_path": str(artifact_path),
            "artifact_expected_sha256": str(payload.get("point_correspondence_artifact_sha256") or "").lower(),
            "artifact_sha256": actual_sha256,
            "artifact_size_bytes": size_bytes,
            "artifact_schema_version": artifact.get("schema_version"),
            "checksum_match": True,
            "coordinate_contract": artifact_inputs["coordinate_contract"],
            "point_set_counts": artifact_inputs["point_set_counts"],
            "valid": True,
            "failure_reasons": [],
        }
        return normalized, None, provenance

    def _read_checksum_json_artifact(
        self,
        path: Path,
        *,
        expected_sha256: object,
        code_prefix: str,
    ) -> tuple[dict[str, Any], str, int]:
        expected = str(expected_sha256 or "").strip().lower()
        if not _is_sha256(expected):
            raise StaticRegistrationRequestError(
                f"{code_prefix}_sha256_invalid_or_missing",
                f"{code_prefix} requires an explicit 64-character SHA256 checksum.",
            )
        try:
            encoded = path.read_bytes()
        except OSError as exc:
            raise StaticRegistrationRequestError(
                f"{code_prefix}_unreadable",
                f"{code_prefix} could not be read.",
            ) from exc
        actual = hashlib.sha256(encoded).hexdigest()
        if actual != expected:
            raise StaticRegistrationRequestError(
                f"{code_prefix}_sha256_mismatch",
                f"{code_prefix} checksum does not match the supplied SHA256.",
            )
        try:
            artifact = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StaticRegistrationRequestError(
                f"{code_prefix}_unreadable",
                f"{code_prefix} must be UTF-8 JSON.",
            ) from exc
        if not isinstance(artifact, dict):
            raise StaticRegistrationRequestError(
                f"{code_prefix}_invalid",
                f"{code_prefix} must contain a JSON object.",
            )
        return artifact, actual, len(encoded)

    def _flatten_registration_input_manifest(
        self,
        manifest: dict[str, Any],
        *,
        case_id: str,
    ) -> dict[str, Any]:
        if manifest.get("schema_version") != L1_INPUT_MANIFEST_SCHEMA:
            raise StaticRegistrationRequestError(
                "registration_manifest_schema_unsupported",
                f"Registration input manifest must use {L1_INPUT_MANIFEST_SCHEMA}.",
            )
        if str(manifest.get("case_id") or "").strip() != case_id:
            raise StaticRegistrationRequestError(
                "registration_manifest_case_mismatch",
                "Registration input manifest case_id does not match the requested case.",
            )
        model = manifest.get("model")
        if not isinstance(model, dict):
            raise StaticRegistrationRequestError(
                "registration_manifest_model_missing",
                "Registration input manifest requires a model object.",
            )
        model_path = str(model.get("path") or "").strip()
        model_sha256 = str(model.get("sha256") or "").strip().lower()
        model_format = str(model.get("format") or "").strip().lower()
        if not model_path or not _is_sha256(model_sha256) or model_format not in SUPPORTED_MODEL_FORMATS:
            raise StaticRegistrationRequestError(
                "registration_manifest_model_contract_invalid",
                "Manifest model requires path, SHA256, and a supported format.",
            )
        normalized = self._flatten_point_contract(manifest, case_id=case_id)
        thresholds = manifest.get("thresholds")
        if not isinstance(thresholds, dict):
            raise StaticRegistrationRequestError(
                "registration_manifest_thresholds_missing",
                "Registration input manifest requires a thresholds object.",
            )
        normalized.update(
            {
                "model_path": model_path,
                "model_sha256": model_sha256,
                "model_format": model_format,
                "fre_threshold_mm": thresholds.get("fre_threshold_mm"),
                "tre_threshold_mm": thresholds.get("tre_threshold_mm"),
                "threshold_source": thresholds.get("source"),
            }
        )
        optional_fields = {
            "camera_matrix",
            "distortion_coefficients",
            "image_size_px",
            "intrinsics_id",
            "reprojection_threshold_px",
            "camera_calibration_evidence",
            "threshold_approval",
            "microscope_pose_evidence",
        }
        for field in optional_fields:
            if field in manifest:
                normalized[field] = manifest[field]
        return normalized

    def _flatten_point_correspondence_artifact(
        self,
        artifact: dict[str, Any],
        *,
        case_id: str,
    ) -> dict[str, Any]:
        if artifact.get("schema_version") != L1_POINT_ARTIFACT_SCHEMA:
            raise StaticRegistrationRequestError(
                "point_correspondence_artifact_schema_unsupported",
                f"Point correspondence artifact must use {L1_POINT_ARTIFACT_SCHEMA}.",
            )
        if str(artifact.get("case_id") or "").strip() != case_id:
            raise StaticRegistrationRequestError(
                "point_correspondence_artifact_case_mismatch",
                "Point correspondence artifact case_id does not match the requested case.",
            )
        return self._flatten_point_contract(artifact, case_id=case_id)

    def _flatten_point_contract(
        self,
        artifact: dict[str, Any],
        *,
        case_id: str,
    ) -> dict[str, Any]:
        del case_id
        registration_method = str(artifact.get("registration_method") or "rigid_points").strip()
        if registration_method not in {"rigid_points", "rigid_points_with_pnp"}:
            raise StaticRegistrationRequestError(
                "point_correspondence_registration_method_invalid",
                "Point correspondence artifact uses an unsupported registration method.",
            )
        contract = _coordinate_contract(artifact.get("coordinate_transform"), label="rigid")
        point_sets = artifact.get("point_sets")
        if not isinstance(point_sets, dict):
            raise StaticRegistrationRequestError(
                "point_sets_missing",
                "Point correspondence artifact requires point_sets.",
            )
        registration_points = point_sets.get("registration")
        validation_points = point_sets.get("validation")
        if not isinstance(registration_points, dict) or not isinstance(validation_points, dict):
            raise StaticRegistrationRequestError(
                "point_sets_invalid",
                "point_sets requires registration and validation objects.",
            )
        source = _validated_points(
            registration_points.get("source"),
            label="registration_source",
            dimensions=3,
            minimum_count=MIN_REGISTRATION_POINTS,
            minimum_rank=2,
        )
        target = _validated_points(
            registration_points.get("target"),
            label="registration_target",
            dimensions=3,
            minimum_count=MIN_REGISTRATION_POINTS,
            minimum_rank=2,
        )
        validation_source = _validated_points(
            validation_points.get("source"),
            label="validation_source",
            dimensions=3,
            minimum_count=MIN_VALIDATION_POINTS,
            minimum_rank=2,
        )
        validation_target = _validated_points(
            validation_points.get("target"),
            label="validation_target",
            dimensions=3,
            minimum_count=MIN_VALIDATION_POINTS,
            minimum_rank=2,
        )
        _paired_point_count(source, target, label="registration")
        _paired_point_count(validation_source, validation_target, label="validation")
        _independent_point_sets(source, validation_source, label="source")
        _independent_point_sets(target, validation_target, label="target")
        normalized: dict[str, Any] = {
            "registration_method": registration_method,
            "source_points": source.tolist(),
            "target_points": target.tolist(),
            "validation_source_points": validation_source.tolist(),
            "validation_target_points": validation_target.tolist(),
            "source_space": contract["from_space"],
            "target_space": contract["to_space"],
            "unit": contract["unit"],
            "coordinate_contract": contract,
            "point_set_counts": {
                "registration": int(source.shape[0]),
                "validation": int(validation_source.shape[0]),
            },
        }
        if registration_method == "rigid_points_with_pnp":
            normalized.update(_camera_point_contract(artifact, rigid_target_space=contract["to_space"]))
        return normalized

    def _model_provenance(
        self,
        path: Path,
        *,
        expected_sha256: object,
        declared_format: object,
    ) -> dict[str, Any]:
        try:
            encoded = path.read_bytes()
        except OSError as exc:
            raise StaticRegistrationRequestError("model_unreadable", "Model file could not be read.") from exc
        actual_sha256 = hashlib.sha256(encoded).hexdigest()
        expected = str(expected_sha256 or "").strip().lower()
        suffix_format = path.suffix.lstrip(".").lower()
        declared = str(declared_format or suffix_format).strip().lower()
        failure_reasons: list[str] = []
        if not _is_sha256(expected):
            failure_reasons.append("model_sha256_invalid_or_missing")
        elif expected != actual_sha256:
            failure_reasons.append("model_sha256_mismatch")
        if declared not in SUPPORTED_MODEL_FORMATS:
            failure_reasons.append("model_format_unsupported")
        if declared != suffix_format:
            failure_reasons.append("model_format_extension_mismatch")
        parse_summary: dict[str, Any] = {}
        if declared in SUPPORTED_MODEL_FORMATS and declared == suffix_format:
            try:
                parse_summary = _parse_model_bytes(encoded, declared)
            except ValueError as exc:
                failure_reasons.append(str(exc))
        return {
            "schema_version": "osteo-vision-l1-model-provenance-v1",
            "path": str(path),
            "format": declared or None,
            "size_bytes": len(encoded),
            "expected_sha256": expected or None,
            "sha256": actual_sha256,
            "checksum_match": bool(_is_sha256(expected) and expected == actual_sha256),
            "parse_valid": not any(reason.startswith("model_parse_") for reason in failure_reasons),
            "parse_summary": parse_summary,
            "valid": not failure_reasons,
            "failure_reasons": list(dict.fromkeys(failure_reasons)),
        }

    def _camera_calibration_evidence(
        self,
        payload: dict[str, Any],
        *,
        camera_registration: CameraRegistrationResult,
    ) -> dict[str, Any]:
        declared_source = payload.get("camera_calibration_evidence")
        declared = dict(declared_source) if isinstance(declared_source, dict) else {}
        artifact_path_value = declared.get("artifact_path")
        expected_sha256 = str(declared.get("artifact_sha256") or "").strip().lower()
        failure_reasons: list[str] = []
        artifact_path: Path | None = None
        artifact: dict[str, Any] = {}

        if not str(artifact_path_value or "").strip():
            failure_reasons.append("camera_calibration_artifact_path_missing")
        else:
            try:
                artifact_path = self._allowed_file(
                    artifact_path_value,
                    "camera calibration artifact",
                )
            except StaticRegistrationRequestError as exc:
                failure_reasons.append(f"camera_calibration_artifact_{exc.code}")

        if len(expected_sha256) != 64 or any(character not in "0123456789abcdef" for character in expected_sha256):
            failure_reasons.append("camera_calibration_artifact_sha256_invalid_or_missing")

        actual_sha256: str | None = None
        if artifact_path is not None:
            actual_sha256 = sha256_for_path(artifact_path)
            if expected_sha256 and actual_sha256 != expected_sha256:
                failure_reasons.append("camera_calibration_artifact_sha256_mismatch")
            try:
                raw_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                failure_reasons.append("camera_calibration_artifact_unreadable")
            else:
                if isinstance(raw_artifact, dict):
                    artifact = raw_artifact
                else:
                    failure_reasons.append("camera_calibration_artifact_invalid")

        required_text = {
            "schema_version": "camera_calibration_schema_version_missing",
            "intrinsics_id": "camera_calibration_intrinsics_id_missing",
            "calibrated_at": "camera_calibration_date_missing",
            "calibration_method": "camera_calibration_method_missing",
        }
        for field, reason in required_text.items():
            if not str(artifact.get(field) or "").strip():
                failure_reasons.append(reason)

        calibrated_at = _parse_timestamp(artifact.get("calibrated_at"))
        if artifact.get("calibrated_at") and calibrated_at is None:
            failure_reasons.append("camera_calibration_date_invalid")
        elif calibrated_at is not None and calibrated_at > datetime.now(timezone.utc):
            failure_reasons.append("camera_calibration_date_in_future")

        if str(artifact.get("intrinsics_id") or "").strip() != camera_registration.intrinsics_id:
            failure_reasons.append("camera_calibration_intrinsics_id_mismatch")
        if not _numeric_structure_close(artifact.get("camera_matrix"), camera_registration.camera_matrix):
            failure_reasons.append("camera_calibration_matrix_mismatch")
        if not _numeric_structure_close(
            artifact.get("distortion_coefficients"),
            camera_registration.distortion_coefficients,
        ):
            failure_reasons.append("camera_calibration_distortion_mismatch")
        if not _numeric_structure_close(artifact.get("image_size_px"), list(camera_registration.image_size_px)):
            failure_reasons.append("camera_calibration_image_size_mismatch")

        calibration_error = _finite_nonnegative(artifact.get("calibration_reprojection_error_px"))
        calibration_threshold = _finite_positive(artifact.get("calibration_reprojection_threshold_px"))
        if calibration_error is None:
            failure_reasons.append("camera_calibration_reprojection_error_invalid_or_missing")
        if calibration_threshold is None:
            failure_reasons.append("camera_calibration_reprojection_threshold_invalid_or_missing")
        if (
            calibration_error is not None
            and calibration_threshold is not None
            and calibration_error > calibration_threshold
        ):
            failure_reasons.append("camera_calibration_reprojection_threshold_exceeded")

        magnification_range = _numeric_range(artifact.get("magnification_range"))
        if magnification_range is None:
            failure_reasons.append("camera_calibration_magnification_range_invalid_or_missing")
        working_distance_range = _numeric_range(artifact.get("working_distance_range_mm"))
        if working_distance_range is None:
            failure_reasons.append("camera_calibration_working_distance_range_invalid_or_missing")

        failure_reasons = list(dict.fromkeys(failure_reasons))
        return {
            "schema_version": "osteo-vision-camera-calibration-evidence-v1",
            "artifact_path": str(artifact_path) if artifact_path is not None else None,
            "artifact_expected_sha256": expected_sha256 or None,
            "artifact_sha256": actual_sha256,
            "intrinsics_id": camera_registration.intrinsics_id,
            "camera_matrix": camera_registration.camera_matrix,
            "distortion_coefficients": camera_registration.distortion_coefficients,
            "image_size_px": list(camera_registration.image_size_px),
            "calibrated_at": artifact.get("calibrated_at"),
            "calibration_method": artifact.get("calibration_method"),
            "calibration_reprojection_error_px": calibration_error,
            "calibration_reprojection_threshold_px": calibration_threshold,
            "calibration_magnification_min": (None if magnification_range is None else magnification_range[0]),
            "calibration_magnification_max": (None if magnification_range is None else magnification_range[1]),
            "calibration_working_distance_min_mm": (
                None if working_distance_range is None else working_distance_range[0]
            ),
            "calibration_working_distance_max_mm": (
                None if working_distance_range is None else working_distance_range[1]
            ),
            "artifact_validation": {
                "valid": not failure_reasons,
                "failure_reasons": failure_reasons,
            },
        }

    def _allowed_file(self, value: object, label: str) -> Path:
        path = Path(str(value or "")).expanduser()
        if not path.is_absolute():
            path = (self.settings.project_root / path).resolve()
        else:
            path = path.resolve()
        roots = [self.settings.project_root.resolve(), self.settings.artifact_root.resolve()]
        if not any(path == root or root in path.parents for root in roots):
            raise StaticRegistrationRequestError("path_not_allowed", f"{label} path is outside allowed roots.")
        if not path.is_file():
            raise StaticRegistrationRequestError("file_not_found", f"{label} file does not exist.")
        return path


def _coordinate_contract(value: object, *, label: str) -> dict[str, Any]:
    try:
        return validate_coordinate_transform(value)
    except CoordinateContractError as exc:
        raise StaticRegistrationRequestError(f"{label}_{exc.code}", str(exc)) from exc


def _validated_points(
    value: object,
    *,
    label: str,
    dimensions: int,
    minimum_count: int,
    minimum_rank: int,
) -> np.ndarray:
    try:
        points = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise StaticRegistrationRequestError(
            f"{label}_invalid",
            f"{label} must be a numeric Nx{dimensions} point array.",
        ) from exc
    if points.ndim != 2 or points.shape[1] != dimensions or points.shape[0] < minimum_count:
        raise StaticRegistrationRequestError(
            f"{label}_count_or_shape_invalid",
            f"{label} requires at least {minimum_count} Nx{dimensions} points.",
        )
    if not np.isfinite(points).all():
        raise StaticRegistrationRequestError(f"{label}_non_finite", f"{label} contains non-finite coordinates.")
    if np.unique(points, axis=0).shape[0] != points.shape[0]:
        raise StaticRegistrationRequestError(f"{label}_duplicate", f"{label} contains duplicate points.")
    if np.linalg.matrix_rank(points - points.mean(axis=0)) < minimum_rank:
        raise StaticRegistrationRequestError(f"{label}_degenerate", f"{label} has degenerate spatial geometry.")
    return points


def _paired_point_count(source: np.ndarray, target: np.ndarray, *, label: str) -> None:
    if source.shape[0] != target.shape[0]:
        raise StaticRegistrationRequestError(
            f"{label}_point_count_mismatch",
            f"{label} source and target correspondence counts must match.",
        )


def _independent_point_sets(registration: np.ndarray, validation: np.ndarray, *, label: str) -> None:
    registration_rows = {tuple(float(item) for item in row) for row in registration}
    validation_rows = {tuple(float(item) for item in row) for row in validation}
    if registration_rows.intersection(validation_rows):
        raise StaticRegistrationRequestError(
            f"validation_{label}_overlaps_registration",
            f"Independent validation {label} points must not reuse registration points.",
        )


def _camera_point_contract(artifact: dict[str, Any], *, rigid_target_space: str) -> dict[str, Any]:
    contract = _coordinate_contract(artifact.get("camera_coordinate_transform"), label="camera")
    if contract["from_space"] != rigid_target_space:
        raise StaticRegistrationRequestError(
            "camera_coordinate_chain_discontinuous",
            "Camera object space must equal the rigid registration target space.",
        )
    point_sets = artifact.get("camera_point_sets")
    if not isinstance(point_sets, dict):
        raise StaticRegistrationRequestError(
            "camera_point_sets_missing",
            "Calibrated PnP requires checksum-bound camera_point_sets.",
        )
    registration = point_sets.get("registration")
    validation = point_sets.get("validation")
    if not isinstance(registration, dict) or not isinstance(validation, dict):
        raise StaticRegistrationRequestError(
            "camera_point_sets_invalid",
            "camera_point_sets requires registration and validation objects.",
        )
    reg_object = _validated_points(
        registration.get("object"),
        label="camera_registration_object",
        dimensions=3,
        minimum_count=4,
        minimum_rank=2,
    )
    reg_image = _validated_points(
        registration.get("image"),
        label="camera_registration_image",
        dimensions=2,
        minimum_count=4,
        minimum_rank=2,
    )
    val_object = _validated_points(
        validation.get("object"),
        label="camera_validation_object",
        dimensions=3,
        minimum_count=3,
        minimum_rank=2,
    )
    val_image = _validated_points(
        validation.get("image"),
        label="camera_validation_image",
        dimensions=2,
        minimum_count=3,
        minimum_rank=2,
    )
    _paired_point_count(reg_object, reg_image, label="camera_registration")
    _paired_point_count(val_object, val_image, label="camera_validation")
    _independent_point_sets(reg_object, val_object, label="camera_object")
    return {
        "camera_object_points": reg_object.tolist(),
        "camera_image_points": reg_image.tolist(),
        "validation_camera_object_points": val_object.tolist(),
        "validation_camera_image_points": val_image.tolist(),
        "camera_space": contract["to_space"],
        "camera_coordinate_contract": contract,
        "camera_point_set_counts": {
            "registration": int(reg_object.shape[0]),
            "validation": int(val_object.shape[0]),
        },
    }


def _parse_model_bytes(encoded: bytes, model_format: str) -> dict[str, Any]:
    if model_format == "stl":
        return _parse_stl(encoded)
    if model_format == "gltf":
        try:
            payload = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("model_parse_gltf_invalid_json") from exc
        return _validate_gltf_payload(payload)
    if len(encoded) < 20 or encoded[:4] != b"glTF":
        raise ValueError("model_parse_glb_header_invalid")
    version, declared_length = struct.unpack_from("<II", encoded, 4)
    if version != 2 or declared_length != len(encoded):
        raise ValueError("model_parse_glb_header_invalid")
    chunk_length, chunk_type = struct.unpack_from("<II", encoded, 12)
    if chunk_type != 0x4E4F534A or 20 + chunk_length > len(encoded):
        raise ValueError("model_parse_glb_json_chunk_invalid")
    try:
        payload = json.loads(encoded[20 : 20 + chunk_length].rstrip(b"\x00 \t\r\n").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("model_parse_glb_json_chunk_invalid") from exc
    summary = _validate_gltf_payload(payload)
    summary["container"] = "glb"
    return summary


def _validate_gltf_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("model_parse_gltf_root_invalid")
    asset = payload.get("asset")
    meshes = payload.get("meshes")
    if not isinstance(asset, dict) or not str(asset.get("version") or "").startswith("2"):
        raise ValueError("model_parse_gltf_asset_invalid")
    if not isinstance(meshes, list) or not meshes:
        raise ValueError("model_parse_gltf_mesh_missing")
    primitive_count = sum(len(mesh.get("primitives") or []) for mesh in meshes if isinstance(mesh, dict))
    if primitive_count <= 0:
        raise ValueError("model_parse_gltf_primitive_missing")
    return {"container": "gltf", "mesh_count": len(meshes), "primitive_count": primitive_count}


def _parse_stl(encoded: bytes) -> dict[str, Any]:
    if len(encoded) >= 84:
        triangle_count = struct.unpack_from("<I", encoded, 80)[0]
        expected_length = 84 + triangle_count * 50
        if triangle_count > 0 and expected_length == len(encoded):
            triangles = np.frombuffer(
                encoded,
                dtype=_BINARY_STL_TRIANGLE_DTYPE,
                count=triangle_count,
                offset=84,
            )
            return _validate_stl_vertices(triangles["vertices"], triangle_count=triangle_count, encoding="binary")
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("model_parse_stl_encoding_invalid") from exc
    ascii_vertices: list[float] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            try:
                ascii_vertices.extend(float(value) for value in parts[1:])
            except ValueError as exc:
                raise ValueError("model_parse_stl_vertex_invalid") from exc
    if not ascii_vertices or len(ascii_vertices) % 9:
        raise ValueError("model_parse_stl_empty_or_incomplete")
    return _validate_stl_vertices(
        ascii_vertices,
        triangle_count=len(ascii_vertices) // 9,
        encoding="ascii",
    )


def _validate_stl_vertices(vertices: ArrayLike, *, triangle_count: int, encoding: str) -> dict[str, Any]:
    points = np.asarray(vertices).reshape(triangle_count, 3, 3)
    for start in range(0, triangle_count, _STL_VALIDATION_CHUNK_TRIANGLES):
        chunk = points[start : start + _STL_VALIDATION_CHUNK_TRIANGLES]
        if not np.isfinite(chunk).all():
            raise ValueError("model_parse_stl_non_finite")
        # Keep the prior float64 area calculation while bounding temporary arrays for large STL models.
        numeric_chunk = np.asarray(chunk, dtype=np.float64)
        areas = np.linalg.norm(
            np.cross(numeric_chunk[:, 1] - numeric_chunk[:, 0], numeric_chunk[:, 2] - numeric_chunk[:, 0]),
            axis=1,
        )
        if np.any(areas <= 1e-12):
            raise ValueError("model_parse_stl_degenerate_triangle")
    return {
        "container": "stl",
        "encoding": encoding,
        "triangle_count": triangle_count,
        "unique_vertex_count": int(np.unique(points.reshape(-1, 3), axis=0).shape[0]),
    }


def _structures_equal(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_structures_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(_structures_equal(a, b) for a, b in zip(left, right))
    try:
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return str(left) == str(right)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _positive_number(value: object, field: str) -> float:
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise StaticRegistrationRequestError("threshold_invalid", f"{field} must be a positive number.") from exc
    if not math.isfinite(number) or number <= 0:
        raise StaticRegistrationRequestError("threshold_invalid", f"{field} must be a positive number.")
    return number


def _degrade_evidence(evidence: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        **evidence,
        "navigation_ready": False,
        "navigation_level": "L0",
        "degradation_state": "safety_gate_degraded",
        "fallback_mode": "unregistered_3d_reference",
        "failure_reasons": list(dict.fromkeys([*(evidence.get("failure_reasons") or []), *reasons])),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _numeric_structure_close(left: Any, right: Any) -> bool:
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _numeric_structure_close(left_item, right_item) for left_item, right_item in zip(left, right)
        )
    try:
        left_number = float(left)
        right_number = float(right)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(left_number)
        and math.isfinite(right_number)
        and math.isclose(
            left_number,
            right_number,
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
    )


def _finite_nonnegative(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _finite_positive(value: Any) -> float | None:
    parsed = _finite_nonnegative(value)
    return parsed if parsed is not None and parsed > 0 else None


def _numeric_range(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    minimum = _finite_positive(value[0])
    maximum = _finite_positive(value[1])
    if minimum is None or maximum is None or minimum > maximum:
        return None
    return minimum, maximum


def sha256_for_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
