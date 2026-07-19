from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from backend.src.core.settings import Settings
from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseInputAsset, CaseRecord
from backend.src.services.static_registration_service import sha256_for_path
from src.core.executables import find_runtime_executable
from src.navigation.coordinate_contract import (
    CoordinateContractError,
    validate_coordinate_transform,
    validate_frame_metadata,
)
from src.navigation.offline_pose_replay import (
    DYNAMIC_AR_MODE,
    POSE_ONLY_MODE,
    OfflinePoseReplayConfig,
    replay_offline_poses,
)

L2_MEASUREMENT_SCHEMA = "osteo-vision-l2-independent-measurements-v1"
L2_POSE_INPUT_SCHEMA = "osteo-vision-l2-pose-input-v3"
L2_THRESHOLD_POLICY_SCHEMA = "osteo-vision-l2-threshold-policy-v2"
L2_MEASUREMENT_METHOD = "independent_tracker_and_phantom_target_v1"
L2_DYNAMIC_CAMERA_SPACE = "camera_optical_dynamic"
TRUSTED_REVIEW_AUTH_SOURCES = {
    "institution_sso",
    "signed_session",
    "verified_identity_token",
}
PLATFORM_SAFETY_CEILINGS = {
    "max_time_offset_ms": 50.0,
    "drift_threshold_mm": 1.0,
    "tre_proxy_threshold_mm": 2.0,
    "dynamic_target_error_threshold_mm": 2.0,
    "max_magnification_rate_per_s": 25.0,
    "max_working_distance_rate_mm_per_s": 600.0,
    "max_intrinsics_switch_rate_hz": 10.0,
}
PLATFORM_SAFETY_FLOORS = {"calibration_ambiguity_margin": 0.05}


class OfflinePoseReplayRequestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OfflinePoseReplayService:
    def __init__(self, settings: Settings, repo: CaseRepository) -> None:
        self.settings = settings
        self.repo = repo

    def replay(self, payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        case = self.repo.get(case_id)
        if case is None:
            raise OfflinePoseReplayRequestError(
                "case_not_found",
                f"Case not found: {case_id}",
            )
        normalized, input_manifest_path, pose_manifest_sha256 = self._normalized_payload(payload)
        replay_mode = str(normalized.get("replay_mode") or POSE_ONLY_MODE).strip().lower()
        if replay_mode not in {POSE_ONLY_MODE, DYNAMIC_AR_MODE}:
            raise OfflinePoseReplayRequestError(
                "replay_mode_invalid",
                "Unsupported L2 replay mode.",
            )
        if replay_mode == DYNAMIC_AR_MODE:
            if normalized.get("schema_version") != L2_POSE_INPUT_SCHEMA:
                raise OfflinePoseReplayRequestError(
                    "dynamic_pose_manifest_schema_unsupported",
                    "Dynamic AR requires the versioned v3 pose manifest with temporal calibration safety policy.",
                )
            required_manifest_fields = {
                "case_id",
                "video_input_id",
                "video_sha256",
                "video_frame_count",
                "intrinsics_id",
                "calibration_table_id",
                "projection_point_space",
                "projection_point_frame",
                "projection_points_3d",
                "poses",
                "max_time_offset_ms",
                "drift_threshold_mm",
                "tre_proxy_threshold_mm",
                "dynamic_target_error_threshold_mm",
                "minimum_visible_projection_points",
                "max_magnification_rate_per_s",
                "max_working_distance_rate_mm_per_s",
                "max_intrinsics_switch_rate_hz",
                "calibration_ambiguity_margin",
                "l2_threshold_approval",
                "measurement_artifact_path",
                "measurement_artifact_sha256",
                "threshold_policy_artifact_path",
                "threshold_policy_artifact_sha256",
                "l1_registration_run_id",
                "l1_model_sha256",
                "l1_input_artifact_sha256",
                "l1_registration_output_sha256",
                "l1_transform_sha256",
                "doctor_review_status",
            }
            missing_manifest_fields = sorted(
                field
                for field in required_manifest_fields
                if field not in normalized or normalized[field] in (None, "", [], {})
            )
            if missing_manifest_fields:
                raise OfflinePoseReplayRequestError(
                    "dynamic_pose_manifest_fields_missing",
                    "Dynamic AR pose manifest fields missing: " + ", ".join(missing_manifest_fields),
                )

        l1_evidence = _l1_evidence_for_replay(dict(case.three_d_evidence))
        static_transform, transform_path, l1_coordinate_contract = self._validated_l1_transform(l1_evidence)
        l1_chain_binding = (
            self._validated_l1_chain_binding(normalized, l1_evidence, transform_path=transform_path)
            if replay_mode == DYNAMIC_AR_MODE
            else None
        )
        l1_tre_mm = _nonnegative_number(
            l1_evidence.get("tre_mm", l1_evidence.get("registration_error_mm")),
            "l1_tre_mm",
        )
        default_config = OfflinePoseReplayConfig()
        config = OfflinePoseReplayConfig(
            max_time_offset_ms=_positive_number(
                normalized.get("max_time_offset_ms", default_config.max_time_offset_ms),
                "max_time_offset_ms",
            ),
            drift_threshold_mm=_positive_number(
                normalized.get("drift_threshold_mm", default_config.drift_threshold_mm),
                "drift_threshold_mm",
            ),
            tre_proxy_threshold_mm=_positive_number(
                normalized.get("tre_proxy_threshold_mm", default_config.tre_proxy_threshold_mm),
                "tre_proxy_threshold_mm",
            ),
            dynamic_target_error_threshold_mm=_positive_number(
                normalized.get(
                    "dynamic_target_error_threshold_mm",
                    default_config.dynamic_target_error_threshold_mm,
                ),
                "dynamic_target_error_threshold_mm",
            ),
            minimum_visible_projection_points=_positive_int(
                normalized.get(
                    "minimum_visible_projection_points",
                    default_config.minimum_visible_projection_points,
                ),
                "minimum_visible_projection_points",
            ),
            max_magnification_rate_per_s=_positive_number(
                normalized.get(
                    "max_magnification_rate_per_s",
                    default_config.max_magnification_rate_per_s,
                ),
                "max_magnification_rate_per_s",
            ),
            max_working_distance_rate_mm_per_s=_positive_number(
                normalized.get(
                    "max_working_distance_rate_mm_per_s",
                    default_config.max_working_distance_rate_mm_per_s,
                ),
                "max_working_distance_rate_mm_per_s",
            ),
            max_intrinsics_switch_rate_hz=_positive_number(
                normalized.get(
                    "max_intrinsics_switch_rate_hz",
                    default_config.max_intrinsics_switch_rate_hz,
                ),
                "max_intrinsics_switch_rate_hz",
            ),
            calibration_ambiguity_margin=_bounded_nonnegative_number(
                normalized.get(
                    "calibration_ambiguity_margin",
                    default_config.calibration_ambiguity_margin,
                ),
                "calibration_ambiguity_margin",
                maximum=1.0,
            ),
        )
        if replay_mode == DYNAMIC_AR_MODE:
            _enforce_platform_safety_ceiling(config)
        output_dir = self.settings.artifact_root / "three_d_pose_replay" / _safe_name(case_id) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        video_evidence: dict[str, Any] | None = None
        overlay_source_path: Path | None = None
        preflight_failures: list[str] = []
        frame_timestamps_s = normalized.get("frame_timestamps_s") or []
        frame_indices: list[int] | None = None
        calibration_table = normalized.get("calibration_table") or []
        projection_points = normalized.get("projection_points_3d")
        poses = normalized.get("poses") or []
        source_space = l1_coordinate_contract["from_space"]
        reference_space = l1_coordinate_contract["to_space"]
        camera_space = L2_DYNAMIC_CAMERA_SPACE
        dynamic_camera_frame: dict[str, Any] | None = None
        actor = normalized.get("review_actor") if isinstance(normalized.get("review_actor"), dict) else None
        doctor_status = str(normalized.get("doctor_review_status") or "review_required")
        trusted_actor = bool(
            actor is not None
            and actor.get("role") == "physician"
            and actor.get("auth_source") in TRUSTED_REVIEW_AUTH_SOURCES
        )
        measurement_evidence: dict[str, Any] | None = None
        threshold_policy_evidence: dict[str, Any] | None = None
        approval: Any = normalized.get("l2_threshold_approval")

        if replay_mode == DYNAMIC_AR_MODE:
            if str(payload.get("input_mode") or "") != "offline_manifest":
                raise OfflinePoseReplayRequestError(
                    "dynamic_ar_requires_controlled_manifest",
                    "Dynamic AR validation requires a checksum-bound offline pose manifest.",
                )
            video_asset, video_path, video_sha256 = self._validated_admitted_video(
                case,
                normalized.get("video_input_id"),
            )
            overlay_source_path = video_path
            decoded = _decode_video(video_path)
            post_decode_sha256 = sha256_for_path(video_path)
            if post_decode_sha256 != video_sha256:
                raise OfflinePoseReplayRequestError(
                    "video_input_changed_during_decode",
                    "Admitted MP4 changed while frame and PTS evidence was being decoded.",
                )
            frame_timestamps_s = decoded["timestamps_s"]
            frame_indices = decoded["frame_indices"]
            video_evidence = {
                "input_id": video_asset.input_id,
                "path": str(video_path),
                "sha256": video_sha256,
                "post_decode_sha256": post_decode_sha256,
                "integrity_status": "verified_before_and_after_decode",
                "frame_count": decoded["frame_count"],
                "fps": decoded["fps"],
                "container_fps": decoded["container_fps"],
                "pts_derived_fps": decoded["pts_derived_fps"],
                "fps_consistent": decoded["fps_consistent"],
                "fps_consistency_error_ratio": decoded["fps_consistency_error_ratio"],
                "width": decoded["width"],
                "height": decoded["height"],
                "timestamp_source": decoded["timestamp_source"],
                "timestamps_verified": decoded["timestamps_verified"],
                "timestamp_verification_failure": decoded["timestamp_verification_failure"],
                "timing_mode": decoded["timing_mode"],
                "frame_interval_s": decoded["frame_interval_s"],
                "max_frame_interval_deviation_s": decoded["max_frame_interval_deviation_s"],
                "source_type": video_asset.metadata.get("source_type"),
            }
            if decoded["timestamps_verified"] is not True:
                preflight_failures.append("video_pts_unverified")
            elif decoded["timing_mode"] != "constant_frame_rate_verified":
                preflight_failures.append("video_variable_frame_rate_unsupported")
            elif decoded["fps_consistent"] is not True:
                preflight_failures.append("video_container_pts_fps_mismatch")
            self._validate_manifest_video_binding(
                normalized,
                case_id=case_id,
                video_evidence=video_evidence,
            )
            self._validate_pose_frame_binding(
                normalized,
                frame_count=decoded["frame_count"],
            )
            measurement_evidence, poses = self._validated_dynamic_measurements(
                normalized,
                actor=actor,
                case_id=case_id,
                video_evidence=video_evidence,
                poses=poses,
            )
            threshold_policy_evidence, approval = self._validated_threshold_policy(
                normalized,
                actor=actor,
                config=config,
            )
            calibration_table = self._validated_l1_calibration(
                l1_evidence,
                image_size=(decoded["width"], decoded["height"]),
                expected_intrinsics_id=str(normalized.get("intrinsics_id") or ""),
                expected_table_id=str(normalized.get("calibration_table_id") or ""),
            )
            projection_points = normalized.get("projection_points_3d")
            if str(normalized.get("projection_point_space") or "").strip() != source_space:
                raise OfflinePoseReplayRequestError(
                    "projection_coordinate_space_mismatch",
                    "Projection points must use the source space bound to the verified L1 transform artifact.",
                )
            dynamic_camera_frame = self._validated_dynamic_coordinate_contract(
                normalized,
                l1_coordinate_contract=l1_coordinate_contract,
            )

        result = replay_offline_poses(
            frame_timestamps_s,
            poses,
            calibration_table=calibration_table,
            static_l1_transform=static_transform,
            l1_tre_mm=l1_tre_mm,
            source_space=source_space,
            reference_space=reference_space,
            camera_space=camera_space,
            config=config,
            failure_injections=_failure_injections(normalized.get("failure_injections")),
            validation_mode=replay_mode,
            projection_points_3d=projection_points,
            frame_indices=frame_indices,
            source_frame_metadata=(l1_coordinate_contract["source_frame"] if replay_mode == DYNAMIC_AR_MODE else None),
            reference_frame_metadata=(
                l1_coordinate_contract["target_frame"] if replay_mode == DYNAMIC_AR_MODE else None
            ),
            camera_frame_metadata=dynamic_camera_frame,
            matrix_convention=(l1_coordinate_contract["matrix_convention"] if replay_mode == DYNAMIC_AR_MODE else None),
        )

        external_failures: list[str] = list(preflight_failures)
        if doctor_status != "accepted" or not trusted_actor:
            external_failures.append("doctor_review_not_accepted")

        if replay_mode == DYNAMIC_AR_MODE:
            external_failures.extend(
                _threshold_approval_failures(
                    approval if isinstance(approval, dict) else {},
                    config=config,
                )
            )

        overlay_evidence: dict[str, Any] | None = None
        if (
            replay_mode == DYNAMIC_AR_MODE
            and video_evidence is not None
            and result.navigation_ready
            and not external_failures
        ):
            overlay_path = output_dir / "dynamic_ar_overlay.mp4"
            overlay_input_path = cast(Path, overlay_source_path)
            try:
                if sha256_for_path(overlay_input_path) != str(video_evidence["sha256"]):
                    raise OfflinePoseReplayRequestError(
                        "video_input_changed_before_overlay",
                        "Admitted MP4 changed after replay validation and before overlay rendering.",
                    )
                overlay_evidence = _render_overlay_video(
                    overlay_input_path,
                    result.frames,
                    overlay_path,
                    fps=float(video_evidence["fps"]),
                )
                if sha256_for_path(overlay_input_path) != str(video_evidence["sha256"]):
                    raise OfflinePoseReplayRequestError(
                        "video_input_changed_during_overlay",
                        "Admitted MP4 changed while overlay evidence was being rendered.",
                    )
            except OfflinePoseReplayRequestError as exc:
                overlay_path.unlink(missing_ok=True)
                external_failures.append(exc.code)

        failure_reasons = list(dict.fromkeys([*result.failure_reasons, *external_failures]))
        navigation_ready = (
            replay_mode == DYNAMIC_AR_MODE
            and result.navigation_ready
            and not failure_reasons
            and overlay_evidence is not None
            and overlay_evidence.get("frame_count") == len(result.frames)
        )
        if (
            replay_mode == DYNAMIC_AR_MODE
            and overlay_evidence is not None
            and (overlay_evidence.get("frame_count") != len(result.frames))
        ):
            failure_reasons.append("overlay_frame_count_mismatch")
            Path(str(overlay_evidence.get("path") or "")).unlink(missing_ok=True)
            overlay_evidence = None
            navigation_ready = False
        failure_reasons = list(dict.fromkeys(failure_reasons))
        navigation_level = "L2" if navigation_ready else "L0"
        fallback_mode = None if navigation_ready else "unregistered_3d_reference"
        safe_frame_count = len(result.frames) if navigation_ready else 0
        degraded_frame_count = len(result.frames) - safe_frame_count

        frames_path = output_dir / "pose_replay_frames.csv"
        _write_frames_csv(frames_path, result.frames, global_navigation_ready=navigation_ready)
        frames_sha256 = sha256_for_path(frames_path)
        worst_frame = max(
            result.frames,
            key=lambda item: (
                abs(item.time_offset_ms),
                item.dynamic_target_error_mm if item.dynamic_target_error_mm is not None else math.inf,
            ),
            default=None,
        )
        pose_summary = {
            "calibration_status": (
                "verified" if replay_mode == DYNAMIC_AR_MODE and navigation_ready else "not_navigation_validated"
            ),
            "pose_tracking_status": "tracking" if navigation_ready else "degraded",
            "time_offset_ms": abs(worst_frame.time_offset_ms) if worst_frame else None,
            "tre_mm": max(
                (frame.dynamic_target_error_mm for frame in result.frames if frame.dynamic_target_error_mm is not None),
                default=None,
            ),
            "tre_threshold_mm": config.dynamic_target_error_threshold_mm,
            "drift_mm": max((frame.drift_proxy_mm for frame in result.frames), default=None),
            "drift_threshold_mm": config.drift_threshold_mm,
            "depth_source": "verified_l1_calibration_and_admitted_video" if replay_mode == DYNAMIC_AR_MODE else None,
            "depth_status": "verified" if navigation_ready else "not_navigation_validated",
            "magnification_rate_per_s": result.calibration_transition_summary.get("max_magnification_rate_per_s"),
            "magnification_rate_threshold_per_s": config.max_magnification_rate_per_s,
            "working_distance_rate_mm_per_s": result.calibration_transition_summary.get(
                "max_working_distance_rate_mm_per_s"
            ),
            "working_distance_rate_threshold_mm_per_s": config.max_working_distance_rate_mm_per_s,
            "intrinsics_switch_count": result.calibration_transition_summary.get("switch_count"),
            "intrinsics_switch_rate_hz": result.calibration_transition_summary.get(
                "max_intrinsics_switch_rate_hz_observed"
            ),
            "intrinsics_switch_rate_threshold_hz": config.max_intrinsics_switch_rate_hz,
        }
        calibration_selection = {
            "calibration_table_id": (
                str(normalized.get("calibration_table_id") or "") if replay_mode == DYNAMIC_AR_MODE else None
            ),
            "selection_method": ("nearest_validated_entry_v1" if replay_mode == DYNAMIC_AR_MODE else None),
            "artifact_sha256": (
                calibration_table[0].get("artifact_sha256")
                if replay_mode == DYNAMIC_AR_MODE and calibration_table
                else None
            ),
            "selected_intrinsics_ids": sorted(
                {str(frame.intrinsics_id) for frame in result.frames if frame.intrinsics_id}
            ),
            **result.calibration_transition_summary,
            "per_frame": [
                {
                    "frame_index": frame.frame_index,
                    "pose_index": frame.pose_index,
                    "intrinsics_id": frame.intrinsics_id,
                    "magnification": poses[frame.pose_index].get("magnification"),
                    "working_distance_mm": poses[frame.pose_index].get("working_distance_mm"),
                    "magnification_rate_per_s": frame.magnification_rate_per_s,
                    "working_distance_rate_mm_per_s": frame.working_distance_rate_mm_per_s,
                    "intrinsics_switched": frame.intrinsics_switched,
                    "intrinsics_switch_rate_hz": frame.intrinsics_switch_rate_hz,
                    "candidate_count": frame.calibration_candidate_count,
                    "selection_distance": frame.calibration_selection_distance,
                    "ambiguous": frame.calibration_selection_ambiguous,
                    "failure_reasons": frame.failure_reasons,
                }
                for frame in result.frames
            ],
        }
        manifest = {
            "schema_version": result.schema_version,
            "case_id": case_id,
            "job_id": job_id,
            "replay_mode": replay_mode,
            "input_mode": str(payload.get("input_mode") or "manual_metadata"),
            "input_manifest_path": input_manifest_path,
            "input_manifest_sha256": pose_manifest_sha256,
            "l1_transform_path": str(transform_path),
            "l1_transform_sha256": sha256_for_path(transform_path),
            "l1_chain_binding": l1_chain_binding,
            "l1_tre_mm": l1_tre_mm,
            "l1_coordinate_contract": l1_coordinate_contract,
            "dynamic_camera_frame": dynamic_camera_frame,
            "video_evidence": video_evidence,
            "overlay_evidence": overlay_evidence,
            "measurement_evidence": measurement_evidence,
            "threshold_policy_evidence": threshold_policy_evidence,
            "calibration_selection": calibration_selection,
            "projection_evidence": {
                "source_space": source_space,
                "source_frame": (l1_coordinate_contract["source_frame"] if replay_mode == DYNAMIC_AR_MODE else None),
                "point_count": len(projection_points or []),
                "minimum_visible_points": config.minimum_visible_projection_points,
                "minimum_visible_count_observed": min(
                    (frame.visible_projected_point_count for frame in result.frames),
                    default=0,
                ),
            },
            "thresholds": {
                "max_time_offset_ms": config.max_time_offset_ms,
                "drift_threshold_mm": config.drift_threshold_mm,
                "tre_proxy_threshold_mm": config.tre_proxy_threshold_mm,
                "dynamic_target_error_threshold_mm": config.dynamic_target_error_threshold_mm,
                "minimum_visible_projection_points": config.minimum_visible_projection_points,
                "max_magnification_rate_per_s": config.max_magnification_rate_per_s,
                "max_working_distance_rate_mm_per_s": config.max_working_distance_rate_mm_per_s,
                "max_intrinsics_switch_rate_hz": config.max_intrinsics_switch_rate_hz,
                "calibration_ambiguity_margin": config.calibration_ambiguity_margin,
                "approval": approval if isinstance(approval, dict) else None,
            },
            "safe_frame_count": safe_frame_count,
            "degraded_frame_count": degraded_frame_count,
            "navigation_ready": navigation_ready,
            "navigation_level": navigation_level,
            "fallback_mode": fallback_mode,
            "failure_reasons": failure_reasons,
            "frames_csv_path": str(frames_path),
            "frames_csv_sha256": frames_sha256,
            "doctor_review_status": doctor_status,
            "doctor_reviewed_by": actor if doctor_status == "accepted" else None,
        }
        manifest_path = output_dir / "pose_replay_manifest.json"
        _write_json(manifest_path, manifest)
        manifest_sha256 = sha256_for_path(manifest_path)
        reviewed_at = datetime.now(timezone.utc).isoformat() if doctor_status == "accepted" and actor else None
        evidence = {
            **l1_evidence,
            "schema_version": "osteo-vision-three-d-evidence-v2",
            "analysis_mode": "l2_offline_pose_replay",
            "run_id": job_id,
            "requested_navigation_level": "L2",
            "replay_mode": replay_mode,
            "navigation_ready": navigation_ready,
            "navigation_level": navigation_level,
            "degradation_state": "dynamic_ar_validated" if navigation_ready else "safety_gate_degraded",
            "fallback_mode": fallback_mode,
            "failure_reasons": failure_reasons,
            "doctor_review_status": doctor_status,
            "doctor_reviewed_by": actor if doctor_status == "accepted" else None,
            "doctor_reviewed_at": reviewed_at,
            "microscope_pose_evidence": pose_summary,
            "video_evidence": video_evidence,
            "pose_manifest_path": input_manifest_path,
            "pose_manifest_sha256": pose_manifest_sha256,
            "projection_evidence": manifest["projection_evidence"],
            "l2_coordinate_contracts": {
                "l1_transform": l1_coordinate_contract,
                "dynamic_camera_frame": dynamic_camera_frame,
                "matrix_convention": (
                    l1_coordinate_contract["matrix_convention"] if replay_mode == DYNAMIC_AR_MODE else None
                ),
            },
            "l1_chain_binding": l1_chain_binding,
            "calibration_selection": calibration_selection,
            "overlay_evidence": overlay_evidence,
            "l2_threshold_approval": approval if isinstance(approval, dict) else None,
            "l2_measurement_evidence": measurement_evidence,
            "l2_threshold_policy_evidence": threshold_policy_evidence,
            "l1_evidence_snapshot": l1_evidence,
            "pose_replay_manifest_path": str(manifest_path),
            "pose_replay_manifest_sha256": manifest_sha256,
            "pose_replay_frames_csv_path": str(frames_path),
            "pose_replay_frames_csv_sha256": frames_sha256,
            "artifact_lifecycle": {
                "status": "active" if navigation_ready else "failed_closed",
                "run_id": job_id,
                "artifact_kind": "l2_offline_pose_replay",
                "overlay_active": bool(navigation_ready and overlay_evidence),
            },
            "boundary_note": (
                "L2 is offline dynamic AR engineering validation. Target-domain performance and real-time "
                "intraoperative navigation remain outside this evidence boundary."
            ),
        }
        return {
            "case_id": case_id,
            "replay_status": "completed",
            "replay_mode": replay_mode,
            "navigation_ready": navigation_ready,
            "navigation_level": navigation_level,
            "safe_frame_count": safe_frame_count,
            "degraded_frame_count": degraded_frame_count,
            "failure_reasons": failure_reasons,
            "video_input_id": video_evidence.get("input_id") if video_evidence else None,
            "video_sha256": video_evidence.get("sha256") if video_evidence else None,
            "video_frame_count": video_evidence.get("frame_count") if video_evidence else None,
            "video_timestamp_source": video_evidence.get("timestamp_source") if video_evidence else None,
            "pose_manifest_path": input_manifest_path,
            "pose_manifest_sha256": pose_manifest_sha256,
            "calibration_selection": calibration_selection,
            "overlay_video_path": overlay_evidence.get("path") if overlay_evidence else None,
            "overlay_video_sha256": overlay_evidence.get("sha256") if overlay_evidence else None,
            "overlay_frame_count": overlay_evidence.get("frame_count") if overlay_evidence else None,
            "pose_replay_manifest_path": str(manifest_path),
            "pose_replay_manifest_sha256": manifest_sha256,
            "pose_replay_frames_csv_path": str(frames_path),
            "pose_replay_frames_csv_sha256": frames_sha256,
            "three_d_evidence": evidence,
        }

    def failure_result(
        self,
        payload: dict[str, Any],
        *,
        job_id: str,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        case = self.repo.get(case_id)
        prior = dict(case.three_d_evidence) if case is not None else {}
        l1_evidence = _l1_evidence_for_replay(prior)
        replay_mode = str(payload.get("replay_mode") or POSE_ONLY_MODE)
        superseded_run_id = (
            str(prior.get("run_id") or "").strip()
            if str(prior.get("analysis_mode") or "") == "l2_offline_pose_replay"
            else None
        )
        evidence = {
            **l1_evidence,
            "schema_version": "osteo-vision-three-d-evidence-v2",
            "analysis_mode": "l2_offline_pose_replay",
            "run_id": job_id,
            "requested_navigation_level": "L2",
            "replay_mode": replay_mode,
            "navigation_ready": False,
            "navigation_level": "L0",
            "degradation_state": "safety_gate_degraded",
            "fallback_mode": "unregistered_3d_reference",
            "failure_reasons": [code],
            "pose_replay_failure": {"code": code, "message": message},
            "doctor_review_status": str(payload.get("doctor_review_status") or "review_required"),
            "l1_evidence_snapshot": l1_evidence,
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
            "pose_replay_manifest_path": None,
            "pose_replay_manifest_sha256": None,
            "pose_replay_frames_csv_path": None,
            "pose_replay_frames_csv_sha256": None,
            "artifact_lifecycle": {
                "status": "failed_closed",
                "run_id": job_id,
                "artifact_kind": "l2_offline_pose_replay",
                "overlay_active": False,
                "superseded_run_id": superseded_run_id or None,
            },
        }
        return {
            "case_id": case_id,
            "replay_status": "failed",
            "replay_mode": replay_mode,
            "error_code": code,
            "error_message": message,
            "navigation_ready": False,
            "navigation_level": "L0",
            "safe_frame_count": 0,
            "degraded_frame_count": 0,
            "failure_reasons": [code],
            "three_d_evidence": evidence,
        }

    def _normalized_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None, str | None]:
        if payload.get("input_mode") != "offline_manifest":
            return dict(payload), None, None
        manifest_path = self._allowed_file(payload.get("pose_manifest_path"), "pose manifest")
        expected_sha256 = str(payload.get("pose_manifest_sha256") or "").strip().lower()
        if not _valid_sha256(expected_sha256):
            raise OfflinePoseReplayRequestError(
                "pose_manifest_sha256_invalid_or_missing",
                "Pose manifest SHA256 is required and must contain 64 hexadecimal characters.",
            )
        try:
            encoded = manifest_path.read_bytes()
        except OSError as exc:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_unreadable",
                "Pose manifest must be readable UTF-8 JSON.",
            ) from exc
        actual_sha256 = hashlib.sha256(encoded).hexdigest()
        if actual_sha256 != expected_sha256:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_sha256_mismatch",
                "Pose manifest checksum does not match the declared SHA256.",
            )
        try:
            manifest = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_unreadable",
                "Pose manifest must be readable UTF-8 JSON.",
            ) from exc
        if not isinstance(manifest, dict):
            raise OfflinePoseReplayRequestError(
                "pose_manifest_invalid",
                "Pose manifest must contain a JSON object.",
            )
        if sha256_for_path(manifest_path) != actual_sha256:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_changed_during_read",
                "Pose manifest changed while its checksum-bound content was being parsed.",
            )
        bound_fields = {
            "case_id",
            "replay_mode",
            "video_input_id",
            "video_sha256",
            "video_frame_count",
            "intrinsics_id",
            "calibration_table_id",
            "projection_point_space",
            "projection_points_3d",
            "frame_timestamps_s",
            "poses",
            "calibration_table",
            "failure_injections",
            "max_time_offset_ms",
            "drift_threshold_mm",
            "tre_proxy_threshold_mm",
            "dynamic_target_error_threshold_mm",
            "minimum_visible_projection_points",
            "max_magnification_rate_per_s",
            "max_working_distance_rate_mm_per_s",
            "max_intrinsics_switch_rate_hz",
            "calibration_ambiguity_margin",
            "l2_threshold_approval",
            "measurement_artifact_path",
            "measurement_artifact_sha256",
            "threshold_policy_artifact_path",
            "threshold_policy_artifact_sha256",
            "doctor_review_status",
        }
        for field in bound_fields:
            if field not in payload:
                continue
            if field not in manifest or manifest[field] != payload[field]:
                raise OfflinePoseReplayRequestError(
                    "pose_manifest_request_field_mismatch",
                    f"Request field {field} does not match the checksum-bound pose manifest.",
                )

        normalized = dict(manifest)
        for field in (
            "case_id",
            "input_mode",
            "pose_manifest_path",
            "pose_manifest_sha256",
            "doctor_review_status",
            "review_actor",
        ):
            if field in payload:
                normalized[field] = payload[field]
        return normalized, str(manifest_path), actual_sha256

    def _validated_dynamic_measurements(
        self,
        manifest: dict[str, Any],
        *,
        actor: dict[str, Any] | None,
        case_id: str,
        video_evidence: dict[str, Any],
        poses: list[Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        artifact_path = self._allowed_file(
            manifest.get("measurement_artifact_path"),
            "independent L2 measurement artifact",
        )
        artifact, artifact_sha256 = _read_checksum_bound_json(
            artifact_path,
            manifest.get("measurement_artifact_sha256"),
            code_prefix="l2_measurement_artifact",
            label="Independent L2 measurement artifact",
        )
        if artifact.get("schema_version") != L2_MEASUREMENT_SCHEMA:
            raise OfflinePoseReplayRequestError(
                "l2_measurement_artifact_schema_unsupported",
                "Independent L2 measurements require the supported versioned artifact schema.",
            )
        if artifact.get("measurement_method_id") != L2_MEASUREMENT_METHOD:
            raise OfflinePoseReplayRequestError(
                "l2_measurement_method_untrusted",
                "L2 measurement evidence must use the independent tracker and phantom target protocol.",
            )
        if artifact.get("source_type") != "independent_phantom_measurement":
            raise OfflinePoseReplayRequestError(
                "l2_measurement_source_untrusted",
                "L2 measurement evidence must declare an independent phantom measurement source.",
            )
        if artifact.get("review_status") != "accepted" or not _actor_contract_matches(
            artifact.get("reviewed_by"), actor
        ):
            raise OfflinePoseReplayRequestError(
                "l2_measurement_review_untrusted",
                "Independent L2 measurements require acceptance by the authenticated physician reviewer.",
            )
        reviewed_at = _parse_timestamp(artifact.get("reviewed_at"))
        if reviewed_at is None or reviewed_at > datetime.now(timezone.utc):
            raise OfflinePoseReplayRequestError(
                "l2_measurement_review_time_invalid",
                "Independent L2 measurement review time must be valid and non-future.",
            )
        bindings = (
            ("case_id", case_id),
            ("video_input_id", video_evidence["input_id"]),
            ("video_sha256", video_evidence["sha256"]),
        )
        for field, expected in bindings:
            if str(artifact.get(field) or "").strip() != str(expected):
                raise OfflinePoseReplayRequestError(
                    "l2_measurement_artifact_binding_mismatch",
                    f"Independent L2 measurement {field} does not match admitted replay evidence.",
                )
        records = artifact.get("records")
        if not isinstance(records, list) or len(records) != len(poses) or artifact.get("frame_count") != len(poses):
            raise OfflinePoseReplayRequestError(
                "l2_measurement_record_count_mismatch",
                "Independent L2 measurement records must match the pose and video frame count one-to-one.",
            )
        source_reference = f"{L2_MEASUREMENT_METHOD}:{artifact_sha256}"
        normalized_poses: list[dict[str, Any]] = []
        for expected_index, (pose, record) in enumerate(zip(poses, records)):
            if not isinstance(pose, dict) or not isinstance(record, dict):
                raise OfflinePoseReplayRequestError(
                    "l2_measurement_record_invalid",
                    "Every pose and independent measurement record must be an object.",
                )
            if pose.get("frame_index") != expected_index or record.get("frame_index") != expected_index:
                raise OfflinePoseReplayRequestError(
                    "l2_measurement_frame_binding_mismatch",
                    "Independent measurement frame indexes must match pose indexes exactly.",
                )
            pose_timestamp = _measurement_nonnegative(pose.get("timestamp_s"), "pose_timestamp_s")
            measurement_timestamp = _measurement_nonnegative(
                record.get("timestamp_s"),
                "measurement_timestamp_s",
            )
            if not math.isclose(pose_timestamp, measurement_timestamp, rel_tol=0.0, abs_tol=1e-9):
                raise OfflinePoseReplayRequestError(
                    "l2_measurement_timestamp_mismatch",
                    "Independent measurement timestamps must match their bound pose records.",
                )
            drift = _measurement_nonnegative(record.get("tracking_drift_mm"), "tracking_drift_mm")
            dynamic_error = _measurement_nonnegative(
                record.get("dynamic_target_error_mm"),
                "dynamic_target_error_mm",
            )
            for field, measured in (
                ("tracking_drift_mm", drift),
                ("dynamic_target_error_mm", dynamic_error),
            ):
                declared = _measurement_nonnegative(pose.get(field), field)
                if not math.isclose(declared, measured, rel_tol=0.0, abs_tol=1e-9):
                    raise OfflinePoseReplayRequestError(
                        "l2_measurement_pose_mismatch",
                        "Pose measurements do not match the checksum-bound independent artifact.",
                    )
            if (
                str(pose.get("tracking_drift_source") or "") != source_reference
                or str(pose.get("dynamic_target_error_source") or "") != source_reference
            ):
                raise OfflinePoseReplayRequestError(
                    "l2_measurement_source_binding_mismatch",
                    "Pose measurement sources must bind to the independent artifact SHA256.",
                )
            normalized_pose = dict(pose)
            normalized_pose.update(
                {
                    "tracking_drift_mm": drift,
                    "dynamic_target_error_mm": dynamic_error,
                    "tracking_drift_source": source_reference,
                    "dynamic_target_error_source": source_reference,
                }
            )
            normalized_poses.append(normalized_pose)
        return (
            {
                "schema_version": L2_MEASUREMENT_SCHEMA,
                "artifact_path": str(artifact_path),
                "artifact_sha256": artifact_sha256,
                "measurement_method_id": L2_MEASUREMENT_METHOD,
                "source_type": artifact["source_type"],
                "frame_count": len(records),
                "review_status": artifact["review_status"],
                "reviewed_by": artifact["reviewed_by"],
                "reviewed_at": reviewed_at.isoformat(),
            },
            normalized_poses,
        )

    def _validated_threshold_policy(
        self,
        manifest: dict[str, Any],
        *,
        actor: dict[str, Any] | None,
        config: OfflinePoseReplayConfig,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        artifact_path = self._allowed_file(
            manifest.get("threshold_policy_artifact_path"),
            "L2 threshold policy artifact",
        )
        artifact, artifact_sha256 = _read_checksum_bound_json(
            artifact_path,
            manifest.get("threshold_policy_artifact_sha256"),
            code_prefix="l2_threshold_policy_artifact",
            label="L2 threshold policy artifact",
        )
        if artifact.get("schema_version") != L2_THRESHOLD_POLICY_SCHEMA:
            raise OfflinePoseReplayRequestError(
                "l2_threshold_policy_schema_unsupported",
                "L2 threshold approval requires the supported versioned policy artifact schema.",
            )
        policy_id = str(artifact.get("policy_id") or "").strip()
        policy_version = str(artifact.get("policy_version") or "").strip()
        if not policy_id or not policy_version:
            raise OfflinePoseReplayRequestError(
                "l2_threshold_policy_identity_missing",
                "L2 threshold policy ID and version are required.",
            )
        if artifact.get("status") != "approved" or not _actor_contract_matches(artifact.get("approved_by"), actor):
            raise OfflinePoseReplayRequestError(
                "l2_threshold_policy_approval_untrusted",
                "L2 threshold policy requires approval by the authenticated physician reviewer.",
            )
        approved_at = _parse_timestamp(artifact.get("approved_at"))
        if approved_at is None or approved_at > datetime.now(timezone.utc):
            raise OfflinePoseReplayRequestError(
                "l2_threshold_policy_time_invalid",
                "L2 threshold policy approval time must be valid and non-future.",
            )
        protocol_version = str(artifact.get("protocol_version") or "").strip()
        data_version = str(artifact.get("data_version") or "").strip()
        thresholds = artifact.get("thresholds")
        if not protocol_version or not data_version or not isinstance(thresholds, dict):
            raise OfflinePoseReplayRequestError(
                "l2_threshold_policy_contract_incomplete",
                "L2 threshold policy protocol, data version, and thresholds are required.",
            )
        expected = _config_thresholds(config)
        for field, expected_value in expected.items():
            try:
                approved_value = float(str(thresholds.get(field)))
            except (TypeError, ValueError) as exc:
                raise OfflinePoseReplayRequestError(
                    "l2_threshold_policy_value_invalid",
                    f"L2 threshold policy {field} must be numeric.",
                ) from exc
            if not math.isfinite(approved_value) or not math.isclose(
                approved_value,
                expected_value,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                raise OfflinePoseReplayRequestError(
                    "l2_threshold_policy_value_mismatch",
                    "L2 threshold policy values must match the checksum-bound replay configuration.",
                )
        approval = manifest.get("l2_threshold_approval")
        if not isinstance(approval, dict):
            raise OfflinePoseReplayRequestError(
                "l2_threshold_approval_missing",
                "L2 pose manifest must reference the approved threshold policy artifact.",
            )
        expected_inline: dict[str, Any] = {
            "status": "approved",
            "policy_id": policy_id,
            "policy_version": policy_version,
            "artifact_sha256": artifact_sha256,
            "protocol_version": protocol_version,
            "data_version": data_version,
            "approved_by": str(actor.get("actor_id") or "") if actor else "",
            "approved_at": approved_at.isoformat(),
            **expected,
        }
        for field, expected_value in expected_inline.items():
            actual = approval.get(field)
            if isinstance(expected_value, float):
                try:
                    matches = math.isclose(
                        float(str(actual)),
                        expected_value,
                        rel_tol=1e-9,
                        abs_tol=1e-9,
                    )
                except (TypeError, ValueError):
                    matches = False
            else:
                matches = str(actual or "") == str(expected_value)
            if not matches:
                raise OfflinePoseReplayRequestError(
                    "l2_threshold_inline_policy_mismatch",
                    "Inline L2 threshold approval does not match its checksum-bound policy artifact.",
                )
        return (
            {
                "schema_version": L2_THRESHOLD_POLICY_SCHEMA,
                "artifact_path": str(artifact_path),
                "artifact_sha256": artifact_sha256,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "protocol_version": protocol_version,
                "data_version": data_version,
                "status": "approved",
                "approved_by": artifact["approved_by"],
                "approved_at": approved_at.isoformat(),
                "thresholds": expected,
            },
            dict(approval),
        )

    def _validated_l1_transform(
        self,
        evidence: dict[str, Any],
    ) -> tuple[list[list[float]], Path, dict[str, Any]]:
        if not (
            evidence.get("navigation_ready") is True
            and str(evidence.get("navigation_level") or "").upper() == "L1"
            and str(evidence.get("registration_status") or "").lower() == "registered"
        ):
            raise OfflinePoseReplayRequestError(
                "l1_navigation_evidence_not_ready",
                "L2 replay requires accepted, safety-gated L1 case evidence.",
            )
        transform_path = self._allowed_file(evidence.get("transform_path"), "L1 transform")
        expected_sha256 = str(evidence.get("transform_sha256") or "").lower()
        try:
            encoded = transform_path.read_bytes()
        except OSError as exc:
            raise OfflinePoseReplayRequestError(
                "l1_transform_unreadable",
                "Persisted L1 transform must be readable UTF-8 JSON.",
            ) from exc
        actual_sha256 = hashlib.sha256(encoded).hexdigest()
        if not expected_sha256 or actual_sha256 != expected_sha256:
            raise OfflinePoseReplayRequestError(
                "l1_transform_checksum_mismatch",
                "Persisted L1 transform checksum is missing or does not match.",
            )
        try:
            payload = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OfflinePoseReplayRequestError(
                "l1_transform_unreadable",
                "Persisted L1 transform must be readable UTF-8 JSON.",
            ) from exc
        matrix = payload.get("matrix") if isinstance(payload, dict) else None
        if matrix is None:
            raise OfflinePoseReplayRequestError(
                "l1_transform_matrix_missing",
                "Persisted L1 transform matrix is missing.",
            )
        coordinate = payload.get("coordinate_transform") if isinstance(payload, dict) else None
        try:
            contract = validate_coordinate_transform(coordinate)
        except CoordinateContractError as exc:
            raise OfflinePoseReplayRequestError(
                "l1_transform_coordinate_contract_invalid",
                f"Persisted L1 transform coordinate contract is invalid: {exc.code}.",
            ) from exc
        chain = evidence.get("transform_chain")
        if not isinstance(chain, list) or not chain or not all(isinstance(item, dict) for item in chain):
            raise OfflinePoseReplayRequestError(
                "l1_transform_coordinate_contract_invalid",
                "Persisted L1 evidence must contain a coordinate transform chain.",
            )
        try:
            chain_contracts = [validate_coordinate_transform(item) for item in chain]
        except CoordinateContractError as exc:
            raise OfflinePoseReplayRequestError(
                "l1_transform_coordinate_contract_invalid",
                f"Persisted L1 transform chain metadata is invalid: {exc.code}.",
            ) from exc
        if any(
            previous["target_frame"] != current["source_frame"]
            or previous["matrix_convention"] != current["matrix_convention"]
            for previous, current in zip(chain_contracts, chain_contracts[1:])
        ):
            raise OfflinePoseReplayRequestError(
                "l1_transform_coordinate_contract_invalid",
                "Persisted L1 transform chain frame metadata is discontinuous.",
            )
        if (
            chain_contracts[0]["source_frame"] != contract["source_frame"]
            or chain_contracts[-1]["target_frame"] != contract["target_frame"]
            or any(item["matrix_convention"] != contract["matrix_convention"] for item in chain_contracts)
        ):
            raise OfflinePoseReplayRequestError(
                "l1_transform_coordinate_contract_invalid",
                "Persisted L1 evidence chain does not match the checksum-bound transform artifact.",
            )
        provenance = evidence.get("registration_input_provenance")
        provenance_contract = provenance.get("coordinate_contract") if isinstance(provenance, dict) else None
        try:
            normalized_provenance_contract = validate_coordinate_transform(provenance_contract)
        except CoordinateContractError as exc:
            raise OfflinePoseReplayRequestError(
                "l1_input_coordinate_contract_invalid",
                f"Persisted L1 input frame metadata is invalid: {exc.code}.",
            ) from exc
        if not isinstance(provenance, dict) or provenance.get("valid") is not True:
            raise OfflinePoseReplayRequestError(
                "l1_input_coordinate_contract_invalid",
                "Persisted L1 input provenance must be checksum verified.",
            )
        if normalized_provenance_contract != chain_contracts[0]:
            raise OfflinePoseReplayRequestError(
                "l1_input_coordinate_contract_mismatch",
                "Persisted L1 input frame metadata conflicts with the exported rigid transform.",
            )
        frame_contracts = evidence.get("coordinate_frame_contracts")
        if not isinstance(frame_contracts, dict) or frame_contracts.get("rigid") != chain_contracts[0]:
            raise OfflinePoseReplayRequestError(
                "l1_evidence_coordinate_contract_mismatch",
                "Persisted L1 frame contracts conflict with the exported transform chain.",
            )
        if len(chain_contracts) > 1 and frame_contracts.get("camera") != chain_contracts[-1]:
            raise OfflinePoseReplayRequestError(
                "l1_evidence_coordinate_contract_mismatch",
                "Persisted L1 camera frame contract conflicts with the exported transform chain.",
            )
        return matrix, transform_path, contract

    def _validated_l1_chain_binding(
        self,
        manifest: dict[str, Any],
        evidence: dict[str, Any],
        *,
        transform_path: Path,
    ) -> dict[str, Any]:
        provenance = evidence.get("registration_input_provenance")
        if not isinstance(provenance, dict):
            raise OfflinePoseReplayRequestError(
                "l1_chain_binding_evidence_incomplete",
                "Persisted L1 evidence is missing checksum-bound input provenance.",
            )
        persisted = {
            "l1_registration_run_id": str(evidence.get("run_id") or "").strip(),
            "l1_model_sha256": str(evidence.get("model_sha256") or "").strip().lower(),
            "l1_input_artifact_sha256": str(provenance.get("artifact_sha256") or "").strip().lower(),
            "l1_registration_output_sha256": str(evidence.get("registration_output_manifest_sha256") or "")
            .strip()
            .lower(),
            "l1_transform_sha256": str(evidence.get("transform_sha256") or "").strip().lower(),
        }
        if not persisted["l1_registration_run_id"] or any(
            not _valid_sha256(value) for key, value in persisted.items() if key != "l1_registration_run_id"
        ):
            raise OfflinePoseReplayRequestError(
                "l1_chain_binding_evidence_incomplete",
                "Persisted L1 model, input, output-manifest, transform, and run bindings must be complete.",
            )
        mismatches = sorted(
            key
            for key, expected in persisted.items()
            if str(manifest.get(key) or "").strip().lower() != expected.lower()
        )
        if mismatches:
            raise OfflinePoseReplayRequestError(
                "l1_chain_binding_mismatch",
                "L2 pose manifest does not bind to the active L1 chain: " + ", ".join(mismatches),
            )

        artifacts = (
            (
                "model",
                evidence.get("model_path"),
                persisted["l1_model_sha256"],
                "l1_model_checksum_mismatch",
            ),
            (
                "registration input",
                provenance.get("artifact_path"),
                persisted["l1_input_artifact_sha256"],
                "l1_input_artifact_checksum_mismatch",
            ),
            (
                "registration output manifest",
                evidence.get("registration_output_manifest_path"),
                persisted["l1_registration_output_sha256"],
                "l1_registration_output_checksum_mismatch",
            ),
        )
        verified_paths: dict[str, str] = {}
        for label, path_value, expected_sha256, error_code in artifacts:
            artifact_path = self._allowed_file(path_value, f"L1 {label}")
            if sha256_for_path(artifact_path) != expected_sha256:
                raise OfflinePoseReplayRequestError(
                    error_code,
                    f"Persisted L1 {label} changed after the accepted L1 run.",
                )
            verified_paths[label.replace(" ", "_") + "_path"] = str(artifact_path)
        if sha256_for_path(transform_path) != persisted["l1_transform_sha256"]:
            raise OfflinePoseReplayRequestError(
                "l1_transform_checksum_mismatch",
                "Persisted L1 transform changed after the accepted L1 run.",
            )
        return {
            "schema_version": "osteo-vision-l1-to-l2-chain-binding-v1",
            "status": "verified_same_l1_chain",
            **persisted,
            **verified_paths,
            "transform_path": str(transform_path),
        }

    def _validated_dynamic_coordinate_contract(
        self,
        manifest: dict[str, Any],
        *,
        l1_coordinate_contract: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            projection_frame = validate_frame_metadata(
                manifest.get("projection_point_frame"),
                expected_name=l1_coordinate_contract["from_space"],
            )
        except CoordinateContractError as exc:
            raise OfflinePoseReplayRequestError(
                "projection_frame_contract_invalid",
                f"Projection point frame metadata is invalid: {exc.code}.",
            ) from exc
        if projection_frame != l1_coordinate_contract["source_frame"]:
            raise OfflinePoseReplayRequestError(
                "projection_frame_contract_mismatch",
                "Projection point frame metadata conflicts with persisted L1 source frame metadata.",
            )
        poses = manifest.get("poses")
        if not isinstance(poses, list) or not poses:
            raise OfflinePoseReplayRequestError(
                "pose_coordinate_contract_invalid",
                "Dynamic AR requires pose frame metadata.",
            )
        target_frame: dict[str, Any] | None = None
        for pose in poses:
            if not isinstance(pose, dict):
                raise OfflinePoseReplayRequestError(
                    "pose_coordinate_contract_invalid",
                    "Every pose must contain a coordinate contract.",
                )
            coordinate = {
                "from_space": pose.get("from_space"),
                "to_space": pose.get("to_space"),
                "direction": pose.get("direction"),
                "unit": pose.get("unit"),
                "source_frame": pose.get("source_frame"),
                "target_frame": pose.get("target_frame"),
                "matrix_convention": pose.get("matrix_convention"),
            }
            try:
                pose_contract = validate_coordinate_transform(coordinate)
            except CoordinateContractError as exc:
                raise OfflinePoseReplayRequestError(
                    "pose_coordinate_contract_invalid",
                    f"Pose frame metadata is invalid: {exc.code}.",
                ) from exc
            if (
                pose_contract["from_space"] != l1_coordinate_contract["to_space"]
                or pose_contract["to_space"] != L2_DYNAMIC_CAMERA_SPACE
                or pose_contract["source_frame"] != l1_coordinate_contract["target_frame"]
                or pose_contract["matrix_convention"] != l1_coordinate_contract["matrix_convention"]
            ):
                raise OfflinePoseReplayRequestError(
                    "pose_coordinate_contract_mismatch",
                    "Pose frame metadata conflicts with the persisted L1 target frame.",
                )
            if target_frame is None:
                target_frame = pose_contract["target_frame"]
            elif target_frame != pose_contract["target_frame"]:
                raise OfflinePoseReplayRequestError(
                    "pose_coordinate_contract_mismatch",
                    "Dynamic pose target frame metadata must remain constant across frames.",
                )
        if target_frame is None:
            raise OfflinePoseReplayRequestError(
                "pose_coordinate_contract_invalid",
                "Dynamic pose target frame metadata is missing.",
            )
        return target_frame

    def _validated_l1_calibration(
        self,
        evidence: dict[str, Any],
        *,
        image_size: tuple[int, int],
        expected_intrinsics_id: str,
        expected_table_id: str,
    ) -> list[dict[str, Any]]:
        calibration = evidence.get("camera_calibration_evidence")
        if not isinstance(calibration, dict):
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_missing",
                "Verified L1 camera calibration evidence is required.",
            )
        validation = calibration.get("artifact_validation")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_not_verified",
                "L1 camera calibration artifact validation did not pass.",
            )
        artifact_path = self._allowed_file(calibration.get("artifact_path"), "L1 camera calibration")
        expected_sha256 = str(calibration.get("artifact_sha256") or "").strip().lower()
        try:
            encoded = artifact_path.read_bytes()
        except OSError as exc:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_unreadable",
                "L1 camera calibration artifact must be readable UTF-8 JSON.",
            ) from exc
        actual_sha256 = hashlib.sha256(encoded).hexdigest()
        if not _valid_sha256(expected_sha256) or actual_sha256 != expected_sha256:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_checksum_mismatch",
                "L1 camera calibration checksum is missing or does not match.",
            )
        try:
            artifact = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_unreadable",
                "L1 camera calibration artifact must be readable UTF-8 JSON.",
            ) from exc
        if sha256_for_path(artifact_path) != actual_sha256:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_changed_during_read",
                "L1 camera calibration changed while its checksum-bound content was parsed.",
            )
        if not isinstance(artifact, dict):
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_invalid",
                "L1 camera calibration artifact must contain a JSON object.",
            )
        if artifact.get("schema_version") != "osteo-vision-camera-calibration-v2":
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_schema_unsupported",
                "Dynamic AR requires a versioned v2 camera calibration table.",
            )
        intrinsics_id = str(artifact.get("intrinsics_id") or "").strip()
        if not intrinsics_id or intrinsics_id != expected_intrinsics_id:
            raise OfflinePoseReplayRequestError(
                "l1_camera_intrinsics_mismatch",
                "Pose manifest intrinsics do not match verified L1 calibration.",
            )
        calibration_table_id = str(artifact.get("calibration_table_id") or "").strip()
        if not calibration_table_id or calibration_table_id != expected_table_id:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_table_mismatch",
                "Pose manifest calibration table does not match verified L1 calibration.",
            )
        selection_method = str(artifact.get("selection_method") or "").strip()
        if selection_method != "nearest_validated_entry_v1":
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_selection_method_unsupported",
                "Dynamic AR requires nearest_validated_entry_v1 calibration selection.",
            )
        artifact_image_size = artifact.get("image_size_px")
        if not isinstance(artifact_image_size, list) or len(artifact_image_size) != 2:
            raise OfflinePoseReplayRequestError(
                "l1_camera_image_size_invalid",
                "Verified L1 camera image size is invalid.",
            )
        if tuple(int(value) for value in artifact_image_size) != image_size:
            raise OfflinePoseReplayRequestError(
                "video_calibration_image_size_mismatch",
                "Admitted MP4 dimensions do not match verified L1 calibration.",
            )
        magnification_range = artifact.get("magnification_range")
        working_distance_range = artifact.get("working_distance_range_mm")
        if not _valid_range(magnification_range) or not _valid_range(working_distance_range):
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_range_invalid",
                "Verified L1 calibration ranges are missing or invalid.",
            )
        entries = artifact.get("calibration_entries")
        if not isinstance(entries, list) or not entries:
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_entries_missing",
                "Dynamic AR requires at least one validated zoom and working-distance calibration entry.",
            )
        validated_entries = [
            _validated_calibration_entry(
                entry,
                image_size=image_size,
                artifact_sha256=actual_sha256,
                calibration_table_id=calibration_table_id,
                selection_method=selection_method,
            )
            for entry in entries
        ]
        entry_ids = [item["intrinsics_id"] for item in validated_entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise OfflinePoseReplayRequestError(
                "l1_camera_calibration_entry_id_duplicate",
                "Calibration entry intrinsics identifiers must be unique.",
            )
        return validated_entries

    def _validated_admitted_video(
        self,
        case: CaseRecord,
        input_id_value: object,
    ) -> tuple[CaseInputAsset, Path, str]:
        input_id = str(input_id_value or "").strip()
        asset = next((item for item in case.inputs if item.input_id == input_id), None)
        if asset is None:
            raise OfflinePoseReplayRequestError(
                "video_input_not_found",
                "Selected video input is not attached to the case.",
            )
        if asset.channel != InputChannel.VIDEO or Path(asset.path).suffix.lower() != ".mp4":
            raise OfflinePoseReplayRequestError(
                "video_input_not_mp4",
                "Dynamic AR validation requires a case MP4 video input.",
            )
        metadata = asset.metadata
        intake = case.intake_metadata
        source_type = str(metadata.get("source_type") or "").strip().lower()
        admitted = metadata.get("admission_status") == "admitted"
        if source_type == "institutional_handover":
            source_governance_valid = bool(
                intake is not None
                and intake.deidentification_confirmed is True
                and intake.authorization_status == "approved"
                and metadata.get("deidentification_confirmed") is True
            )
        elif source_type in {"phantom_engineering", "synthetic_validation"}:
            source_governance_valid = bool(
                metadata.get("contains_patient_data") is False
                and metadata.get("governance_status") == "approved"
                and str(metadata.get("usage_scope") or "").strip()
                and str(metadata.get("purpose_boundary") or "").strip()
            )
        elif source_type == "public_proxy":
            source_governance_valid = bool(
                metadata.get("target_domain_flag") is False
                and metadata.get("deidentification_confirmed") is True
                and metadata.get("license_review_status") == "approved"
                and str(metadata.get("source_url") or "").strip()
                and str(metadata.get("usage_scope") or "").strip()
            )
        else:
            source_governance_valid = False
        if not admitted or not source_governance_valid:
            raise OfflinePoseReplayRequestError(
                "video_input_not_admitted",
                "Dynamic AR validation requires a governed, admitted MP4 input with an explicit source boundary.",
            )
        video_path = self._allowed_file(asset.path, "admitted MP4")
        expected_sha256 = str(metadata.get("sha256") or "").strip().lower()
        actual_sha256 = sha256_for_path(video_path)
        if not _valid_sha256(expected_sha256) or actual_sha256 != expected_sha256:
            raise OfflinePoseReplayRequestError(
                "video_input_checksum_mismatch",
                "Admitted MP4 checksum is missing or does not match.",
            )
        return asset, video_path, actual_sha256

    def _validate_manifest_video_binding(
        self,
        manifest: dict[str, Any],
        *,
        case_id: str,
        video_evidence: dict[str, Any],
    ) -> None:
        checks = (
            ("case_id", case_id, "pose_manifest_case_mismatch"),
            ("video_input_id", video_evidence["input_id"], "pose_manifest_video_input_mismatch"),
            ("video_sha256", video_evidence["sha256"], "pose_manifest_video_checksum_mismatch"),
        )
        for field, expected, code in checks:
            if str(manifest.get(field) or "").strip() != str(expected):
                raise OfflinePoseReplayRequestError(
                    code,
                    f"Pose manifest {field} does not match persisted case evidence.",
                )

    def _validate_pose_frame_binding(
        self,
        manifest: dict[str, Any],
        *,
        frame_count: int,
    ) -> None:
        if frame_count < 2:
            raise OfflinePoseReplayRequestError(
                "dynamic_video_sequence_too_short",
                "Dynamic AR validation requires at least two decoded video frames.",
            )
        try:
            declared_count = int(str(manifest.get("video_frame_count")))
        except (TypeError, ValueError) as exc:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_frame_count_missing",
                "Pose manifest must declare the bound video frame count.",
            ) from exc
        poses = manifest.get("poses")
        if declared_count != frame_count or not isinstance(poses, list) or len(poses) != frame_count:
            raise OfflinePoseReplayRequestError(
                "pose_manifest_frame_count_mismatch",
                "Pose manifest, decoded MP4, and pose record counts must match.",
            )
        for expected_index, pose in enumerate(poses):
            if not isinstance(pose, dict) or pose.get("frame_index") != expected_index:
                raise OfflinePoseReplayRequestError(
                    "pose_manifest_frame_index_mismatch",
                    "Pose manifest frame indexes must be contiguous and match decoded MP4 frames.",
                )

    def _allowed_file(self, value: object, label: str) -> Path:
        path = Path(str(value or "")).expanduser()
        path = (self.settings.project_root / path).resolve() if not path.is_absolute() else path.resolve()
        roots = [
            self.settings.project_root.resolve(),
            self.settings.artifact_root.resolve(),
        ]
        if not any(path == root or root in path.parents for root in roots):
            raise OfflinePoseReplayRequestError(
                "path_not_allowed",
                f"{label} path is outside allowed roots.",
            )
        if not path.is_file():
            raise OfflinePoseReplayRequestError(
                "file_not_found",
                f"{label} file does not exist.",
            )
        return path


def _decode_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise OfflinePoseReplayRequestError(
            "video_decode_failed",
            "Admitted MP4 could not be opened.",
        )
    declared_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    container_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if container_fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise OfflinePoseReplayRequestError(
            "video_metadata_invalid",
            "Admitted MP4 frame rate or dimensions are invalid.",
        )
    decoded_count = 0
    timestamps: list[float] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame.shape[:2] != (height, width):
            capture.release()
            raise OfflinePoseReplayRequestError(
                "video_decode_frame_dimension_mismatch",
                "Decoded MP4 frame dimensions do not match the declared video dimensions.",
            )
        decoded_count += 1
        timestamps.append(float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0)
    capture.release()
    if decoded_count == 0:
        raise OfflinePoseReplayRequestError(
            "video_decode_empty",
            "Admitted MP4 contains no decodable frames.",
        )
    if declared_count > 0 and declared_count != decoded_count:
        raise OfflinePoseReplayRequestError(
            "video_decode_frame_count_mismatch",
            "Decoded frame count does not match the MP4 container metadata.",
        )
    probed_timestamps, probe_failure = _ffprobe_frame_timestamps(path)
    timestamps_verified = bool(probed_timestamps is not None and len(probed_timestamps) == decoded_count)
    if timestamps_verified and probed_timestamps is not None:
        timestamps = probed_timestamps
        timestamp_source = "ffprobe_best_effort_timestamp_time"
    elif all(current > previous for previous, current in zip(timestamps, timestamps[1:])):
        timestamp_source = "opencv_pos_msec_unverified"
    else:
        timestamps = [index / container_fps for index in range(decoded_count)]
        timestamp_source = "decoded_index_over_fps_unverified"
    frame_interval_s: float | None = None
    max_frame_interval_deviation_s: float | None = None
    pts_derived_fps: float | None = None
    fps_consistency_error_ratio: float | None = None
    fps_consistent = False
    timing_mode = "unverified"
    if timestamps_verified and len(timestamps) >= 2:
        intervals = np.diff(np.asarray(timestamps, dtype=np.float64))
        frame_interval_s = float(np.median(intervals))
        max_frame_interval_deviation_s = float(np.max(np.abs(intervals - frame_interval_s)))
        tolerance = max(1e-6, frame_interval_s * 0.01)
        timing_mode = (
            "constant_frame_rate_verified"
            if max_frame_interval_deviation_s <= tolerance
            else "variable_frame_rate_verified"
        )
        if frame_interval_s > 0:
            pts_derived_fps = 1.0 / frame_interval_s
            fps_consistency_error_ratio = abs(container_fps - pts_derived_fps) / pts_derived_fps
            fps_consistent = fps_consistency_error_ratio <= 0.01
    effective_fps = pts_derived_fps if pts_derived_fps is not None else container_fps
    return {
        "timestamps_s": timestamps,
        "frame_indices": list(range(decoded_count)),
        "frame_count": decoded_count,
        "fps": effective_fps,
        "container_fps": container_fps,
        "pts_derived_fps": pts_derived_fps,
        "fps_consistent": fps_consistent,
        "fps_consistency_error_ratio": fps_consistency_error_ratio,
        "width": width,
        "height": height,
        "timestamp_source": timestamp_source,
        "timestamps_verified": timestamps_verified,
        "timestamp_verification_failure": None if timestamps_verified else probe_failure,
        "timing_mode": timing_mode,
        "frame_interval_s": frame_interval_s,
        "max_frame_interval_deviation_s": max_frame_interval_deviation_s,
    }


def _ffprobe_frame_timestamps(path: Path) -> tuple[list[float] | None, str | None]:
    executable = find_runtime_executable("ffprobe")
    if executable is None:
        return None, "ffprobe_unavailable"
    try:
        completed = subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "frame=best_effort_timestamp_time,pkt_pts_time",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "ffprobe_execution_failed"
    if completed.returncode != 0:
        return None, "ffprobe_execution_failed"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, "ffprobe_output_invalid"
    frames = payload.get("frames") if isinstance(payload, dict) else None
    if not isinstance(frames, list) or not frames:
        return None, "ffprobe_frame_timestamps_missing"
    timestamps: list[float] = []
    for frame in frames:
        if not isinstance(frame, dict):
            return None, "ffprobe_frame_timestamps_invalid"
        raw_value = frame.get("best_effort_timestamp_time", frame.get("pkt_pts_time"))
        try:
            timestamp = float(str(raw_value))
        except (TypeError, ValueError):
            return None, "ffprobe_frame_timestamps_invalid"
        if not math.isfinite(timestamp):
            return None, "ffprobe_frame_timestamps_invalid"
        timestamps.append(timestamp)
    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        return None, "ffprobe_frame_timestamps_not_strictly_increasing"
    return timestamps, None


def _render_overlay_video(
    video_path: Path | None,
    replay_frames: list[Any],
    output_path: Path,
    *,
    fps: float,
) -> dict[str, Any]:
    if video_path is None or not replay_frames:
        raise OfflinePoseReplayRequestError(
            "overlay_frame_count_mismatch",
            "Overlay source video and replay evidence are required.",
        )
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OfflinePoseReplayRequestError(
            "overlay_source_decode_failed",
            "Dynamic AR overlay source MP4 could not be opened.",
        )
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        raise OfflinePoseReplayRequestError(
            "overlay_source_metadata_invalid",
            "Dynamic AR overlay source dimensions are invalid.",
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise OfflinePoseReplayRequestError(
            "overlay_writer_unavailable",
            "Dynamic AR overlay MP4 writer could not be opened.",
        )
    written = 0
    try:
        for replay_frame in replay_frames:
            ok, frame = capture.read()
            if not ok:
                raise OfflinePoseReplayRequestError(
                    "overlay_source_ended_early",
                    "Overlay source MP4 ended before all replay frames were rendered.",
                )
            if frame.shape[:2] != (height, width):
                raise OfflinePoseReplayRequestError(
                    "overlay_frame_dimension_mismatch",
                    "Decoded video frames have inconsistent dimensions.",
                )
            rendered = frame.copy()
            points = replay_frame.projected_points_px
            for x, y in points:
                pixel = (int(round(x)), int(round(y)))
                if 0 <= pixel[0] < width and 0 <= pixel[1] < height:
                    cv2.circle(rendered, pixel, 5, (0, 255, 255), 2, lineType=cv2.LINE_AA)
            visible = [(int(round(x)), int(round(y))) for x, y in points if 0 <= x < width and 0 <= y < height]
            if len(visible) >= 2:
                cv2.polylines(
                    rendered,
                    [np.asarray(visible, dtype=np.int32).reshape(-1, 1, 2)],
                    isClosed=True,
                    color=(0, 220, 255),
                    thickness=2,
                    lineType=cv2.LINE_AA,
                )
            cv2.putText(
                rendered,
                f"frame {replay_frame.frame_index} | L2 engineering validation",
                (16, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            writer.write(rendered)
            written += 1
        extra_frame, _ = capture.read()
        if extra_frame:
            raise OfflinePoseReplayRequestError(
                "overlay_frame_count_mismatch",
                "Overlay source MP4 contains frames without replay evidence.",
            )
    finally:
        capture.release()
        writer.release()
    if written != len(replay_frames) or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise OfflinePoseReplayRequestError(
            "overlay_write_incomplete",
            "Dynamic AR overlay evidence was not written completely.",
        )
    verification = cv2.VideoCapture(str(output_path))
    decoded_count = 0
    while verification.isOpened():
        ok, _ = verification.read()
        if not ok:
            break
        decoded_count += 1
    verification.release()
    if decoded_count != written:
        raise OfflinePoseReplayRequestError(
            "overlay_decode_frame_count_mismatch",
            "Written overlay frame count failed decode verification.",
        )
    output_timestamps, output_probe_failure = _ffprobe_frame_timestamps(output_path)
    if output_timestamps is None or len(output_timestamps) != written:
        raise OfflinePoseReplayRequestError(
            "overlay_pts_unverified",
            "Written overlay frame timestamps could not be verified: "
            + str(output_probe_failure or "frame_count_mismatch"),
        )
    output_intervals = np.diff(np.asarray(output_timestamps, dtype=np.float64))
    if output_intervals.size == 0:
        raise OfflinePoseReplayRequestError(
            "overlay_pts_unverified",
            "Written overlay must contain at least two timestamped frames.",
        )
    output_interval_s = float(np.median(output_intervals))
    output_interval_deviation_s = float(np.max(np.abs(output_intervals - output_interval_s)))
    output_fps = 1.0 / output_interval_s if output_interval_s > 0 else float("inf")
    fps_error_ratio = abs(output_fps - fps) / fps
    output_duration_s = float(output_timestamps[-1] - output_timestamps[0] + output_interval_s)
    expected_duration_s = written / fps
    duration_tolerance_s = max(1e-3, expected_duration_s * 0.02)
    if (
        not math.isfinite(output_fps)
        or output_interval_deviation_s > max(1e-6, output_interval_s * 0.01)
        or fps_error_ratio > 0.01
        or abs(output_duration_s - expected_duration_s) > duration_tolerance_s
    ):
        raise OfflinePoseReplayRequestError(
            "overlay_timing_mismatch",
            "Written overlay PTS, frame rate, or duration does not match verified source timing.",
        )
    return {
        "path": str(output_path),
        "sha256": sha256_for_path(output_path),
        "frame_count": written,
        "width": width,
        "height": height,
        "fps": output_fps,
        "source_pts_derived_fps": fps,
        "timestamp_source": "ffprobe_best_effort_timestamp_time",
        "frame_interval_s": output_interval_s,
        "max_frame_interval_deviation_s": output_interval_deviation_s,
        "duration_s": output_duration_s,
        "expected_duration_s": expected_duration_s,
        "fps_error_ratio": fps_error_ratio,
        "render_method": "opencv_projected_landmark_overlay_v1",
        "memory_mode": "streaming_two_pass_v1",
    }


def _read_checksum_bound_json(
    path: Path,
    expected_sha256_value: object,
    *,
    code_prefix: str,
    label: str,
) -> tuple[dict[str, Any], str]:
    expected_sha256 = str(expected_sha256_value or "").strip().lower()
    if not _valid_sha256(expected_sha256):
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_sha256_invalid_or_missing",
            f"{label} SHA256 is required.",
        )
    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_unreadable",
            f"{label} must be readable UTF-8 JSON.",
        ) from exc
    actual_sha256 = hashlib.sha256(encoded).hexdigest()
    if actual_sha256 != expected_sha256:
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_sha256_mismatch",
            f"{label} checksum does not match the declared SHA256.",
        )
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_unreadable",
            f"{label} must be readable UTF-8 JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_invalid",
            f"{label} must contain a JSON object.",
        )
    if sha256_for_path(path) != actual_sha256:
        raise OfflinePoseReplayRequestError(
            f"{code_prefix}_changed_during_read",
            f"{label} changed while its checksum-bound content was parsed.",
        )
    return payload, actual_sha256


def _actor_contract_matches(value: object, actor: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict) or not isinstance(actor, dict):
        return False
    if actor.get("role") != "physician" or actor.get("auth_source") not in TRUSTED_REVIEW_AUTH_SOURCES:
        return False
    return all(
        str(value.get(field) or "").strip() == str(actor.get(field) or "").strip()
        for field in ("actor_id", "role", "institution", "auth_source")
    )


def _config_thresholds(config: OfflinePoseReplayConfig) -> dict[str, float]:
    return {
        "max_time_offset_ms": config.max_time_offset_ms,
        "drift_threshold_mm": config.drift_threshold_mm,
        "tre_proxy_threshold_mm": config.tre_proxy_threshold_mm,
        "dynamic_target_error_threshold_mm": config.dynamic_target_error_threshold_mm,
        "minimum_visible_projection_points": float(config.minimum_visible_projection_points),
        "max_magnification_rate_per_s": config.max_magnification_rate_per_s,
        "max_working_distance_rate_mm_per_s": config.max_working_distance_rate_mm_per_s,
        "max_intrinsics_switch_rate_hz": config.max_intrinsics_switch_rate_hz,
        "calibration_ambiguity_margin": config.calibration_ambiguity_margin,
    }


def _enforce_platform_safety_ceiling(config: OfflinePoseReplayConfig) -> None:
    thresholds = _config_thresholds(config)
    relaxed = (
        any(thresholds[field] > ceiling for field, ceiling in PLATFORM_SAFETY_CEILINGS.items())
        or config.minimum_visible_projection_points < 4
        or any(thresholds[field] < floor for field, floor in PLATFORM_SAFETY_FLOORS.items())
    )
    if relaxed:
        raise OfflinePoseReplayRequestError(
            "l2_threshold_exceeds_platform_safety_ceiling",
            "L2 replay thresholds may only preserve or tighten the platform safety ceiling.",
        )


def _threshold_approval_failures(
    approval: dict[str, Any],
    *,
    config: OfflinePoseReplayConfig,
) -> list[str]:
    reasons: list[str] = []
    if not approval:
        return ["l2_threshold_approval_missing"]
    if str(approval.get("status") or "").strip().lower() != "approved":
        reasons.append("l2_threshold_policy_not_approved")
    for field, reason in (
        ("protocol_version", "l2_threshold_protocol_version_missing"),
        ("data_version", "l2_threshold_data_version_missing"),
        ("approved_by", "l2_threshold_approver_missing"),
        ("approved_at", "l2_threshold_approval_time_missing"),
    ):
        if not str(approval.get(field) or "").strip():
            reasons.append(reason)
    approved_at = _parse_timestamp(approval.get("approved_at"))
    if approval.get("approved_at") and approved_at is None:
        reasons.append("l2_threshold_approval_time_invalid")
    elif approved_at is not None and approved_at > datetime.now(timezone.utc):
        reasons.append("l2_threshold_approval_time_in_future")
    expected = _config_thresholds(config)
    for field, value in expected.items():
        try:
            approved_value = float(str(approval.get(field)))
        except (TypeError, ValueError):
            reasons.append(f"approved_{field}_missing")
            continue
        if not math.isfinite(approved_value) or not math.isclose(
            approved_value,
            value,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            reasons.append(f"approved_{field}_mismatch")
    return list(dict.fromkeys(reasons))


def _l1_evidence_for_replay(evidence: dict[str, Any]) -> dict[str, Any]:
    snapshot = evidence.get("l1_evidence_snapshot")
    if (
        str(evidence.get("analysis_mode") or "") == "l2_offline_pose_replay"
        and isinstance(snapshot, dict)
        and snapshot
        and str(snapshot.get("analysis_mode") or "") == "l1_static_registration"
        and snapshot.get("navigation_ready") is True
        and str(snapshot.get("navigation_level") or "").upper() == "L1"
    ):
        return dict(snapshot)
    return dict(evidence)


def _failure_injections(value: object) -> dict[int, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise OfflinePoseReplayRequestError(
            "failure_injections_invalid",
            "failure_injections must be an object.",
        )
    normalized: dict[int, list[str]] = {}
    try:
        for index, reasons in value.items():
            frame_index = int(index)
            if frame_index < 0 or isinstance(reasons, (str, bytes)) or not isinstance(reasons, list):
                raise ValueError
            normalized[frame_index] = [str(item) for item in reasons]
        return normalized
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "failure_injections_invalid",
            "Failure injection keys must be frame indexes with string lists.",
        ) from exc


def _positive_number(value: Any, field: str) -> float:
    number = _nonnegative_number(value, field)
    if number <= 0:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must be positive.",
        )
    return number


def _positive_int(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must be a positive integer.",
        ) from exc
    if number <= 0:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must be a positive integer.",
        )
    return number


def _bounded_nonnegative_number(value: Any, field: str, *, maximum: float) -> float:
    number = _nonnegative_number(value, field)
    if number > maximum:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must not exceed {maximum}.",
        )
    return number


def _nonnegative_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must be numeric.",
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise OfflinePoseReplayRequestError(
            "threshold_invalid",
            f"{field} must be finite and non-negative.",
        )
    return number


def _measurement_nonnegative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "l2_measurement_value_invalid",
            f"Independent L2 measurement {field} must be numeric.",
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise OfflinePoseReplayRequestError(
            "l2_measurement_value_invalid",
            f"Independent L2 measurement {field} must be finite and non-negative.",
        )
    return number


def _validated_calibration_entry(
    value: object,
    *,
    image_size: tuple[int, int],
    artifact_sha256: str,
    calibration_table_id: str,
    selection_method: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_invalid",
            "Each calibration table entry must be an object.",
        )
    intrinsics_id = str(value.get("intrinsics_id") or "").strip()
    if not intrinsics_id:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_id_missing",
            "Each calibration entry requires an intrinsics identifier.",
        )
    magnification_range = value.get("magnification_range")
    working_distance_range = value.get("working_distance_range_mm")
    if not _valid_range(magnification_range) or not _valid_range(working_distance_range):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_range_invalid",
            "Calibration entry magnification and working-distance ranges must be valid.",
        )
    assert isinstance(magnification_range, list)
    assert isinstance(working_distance_range, list)
    magnification_min, magnification_max = (
        float(magnification_range[0]),
        float(magnification_range[1]),
    )
    working_distance_min, working_distance_max = (
        float(working_distance_range[0]),
        float(working_distance_range[1]),
    )
    try:
        magnification_reference = float(str(value.get("magnification_reference")))
        working_distance_reference = float(str(value.get("working_distance_reference_mm")))
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_reference_invalid",
            "Calibration entry reference magnification and working distance must be numeric.",
        ) from exc
    if not (
        math.isfinite(magnification_reference)
        and math.isfinite(working_distance_reference)
        and magnification_min <= magnification_reference <= magnification_max
        and working_distance_min <= working_distance_reference <= working_distance_max
    ):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_reference_invalid",
            "Calibration entry reference values must lie inside their validated ranges.",
        )
    entry_image_size = value.get("image_size_px")
    try:
        parsed_entry_image_size = (
            tuple(int(item) for item in entry_image_size)
            if isinstance(entry_image_size, list) and len(entry_image_size) == 2
            else None
        )
    except (TypeError, ValueError):
        parsed_entry_image_size = None
    if parsed_entry_image_size != image_size:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_image_size_mismatch",
            "Calibration entry image dimensions must match the admitted MP4.",
        )
    try:
        camera_matrix = np.asarray(value.get("camera_matrix"), dtype=np.float64)
        distortion = np.asarray(value.get("distortion_coefficients"), dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_intrinsics_invalid",
            "Calibration entry intrinsics must be numeric.",
        ) from exc
    width, height = image_size
    if (
        camera_matrix.shape != (3, 3)
        or not np.isfinite(camera_matrix).all()
        or camera_matrix[0, 0] <= 0
        or camera_matrix[1, 1] <= 0
        or not 0 <= camera_matrix[0, 2] < width
        or not 0 <= camera_matrix[1, 2] < height
        or distortion.size not in {4, 5, 8, 12, 14}
        or not np.isfinite(distortion).all()
    ):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_intrinsics_invalid",
            "Calibration entry matrix, distortion, or principal point is invalid.",
        )
    calibrated_at = _parse_timestamp(value.get("calibrated_at"))
    if calibrated_at is None or calibrated_at > datetime.now(timezone.utc):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_time_invalid",
            "Calibration entry requires a valid, non-future calibration time.",
        )
    calibration_method = str(value.get("calibration_method") or "").strip()
    if not calibration_method:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_method_missing",
            "Calibration entry requires a documented calibration method.",
        )
    try:
        reprojection_error = float(str(value.get("calibration_reprojection_error_px")))
        reprojection_threshold = float(str(value.get("calibration_reprojection_threshold_px")))
    except (TypeError, ValueError) as exc:
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_reprojection_invalid",
            "Calibration entry reprojection evidence must be numeric.",
        ) from exc
    if (
        not math.isfinite(reprojection_error)
        or not math.isfinite(reprojection_threshold)
        or reprojection_error < 0
        or reprojection_threshold <= 0
        or reprojection_error > reprojection_threshold
    ):
        raise OfflinePoseReplayRequestError(
            "l1_camera_calibration_entry_reprojection_invalid",
            "Calibration entry reprojection evidence does not pass its threshold.",
        )
    return {
        "intrinsics_id": intrinsics_id,
        "calibration_table_id": calibration_table_id,
        "selection_method": selection_method,
        "magnification_reference": magnification_reference,
        "magnification_min": magnification_min,
        "magnification_max": magnification_max,
        "working_distance_reference_mm": working_distance_reference,
        "working_distance_min_mm": working_distance_min,
        "working_distance_max_mm": working_distance_max,
        "camera_matrix": camera_matrix.tolist(),
        "distortion_coefficients": distortion.tolist(),
        "image_size_px": list(image_size),
        "calibrated_at": calibrated_at.isoformat(),
        "calibration_method": calibration_method,
        "calibration_reprojection_error_px": reprojection_error,
        "calibration_reprojection_threshold_px": reprojection_threshold,
        "artifact_sha256": artifact_sha256,
        "verification_status": "verified",
    }


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _valid_range(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    try:
        minimum, maximum = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return False
    return math.isfinite(minimum) and math.isfinite(maximum) and 0 < minimum <= maximum


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _write_frames_csv(
    path: Path,
    frames: list[Any],
    *,
    global_navigation_ready: bool,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "frame_index",
                "frame_timestamp_s",
                "pose_index",
                "pose_timestamp_s",
                "time_offset_ms",
                "intrinsics_id",
                "magnification",
                "working_distance_mm",
                "magnification_rate_per_s",
                "working_distance_rate_mm_per_s",
                "intrinsics_switched",
                "intrinsics_switch_rate_hz",
                "calibration_candidate_count",
                "calibration_selection_distance",
                "calibration_selection_ambiguous",
                "drift_proxy_mm",
                "tre_proxy_mm",
                "dynamic_target_error_mm",
                "projected_point_count",
                "visible_projected_point_count",
                "navigation_ready",
                "navigation_level",
                "fallback_mode",
                "failure_reasons",
                "projected_points_json",
                "composed_transform_json",
            ],
        )
        writer.writeheader()
        for frame in frames:
            frame_ready = bool(frame.navigation_ready and global_navigation_ready)
            writer.writerow(
                {
                    "frame_index": frame.frame_index,
                    "frame_timestamp_s": frame.frame_timestamp_s,
                    "pose_index": frame.pose_index,
                    "pose_timestamp_s": frame.pose_timestamp_s,
                    "time_offset_ms": frame.time_offset_ms,
                    "intrinsics_id": frame.intrinsics_id,
                    "magnification": frame.magnification,
                    "working_distance_mm": frame.working_distance_mm,
                    "magnification_rate_per_s": frame.magnification_rate_per_s,
                    "working_distance_rate_mm_per_s": frame.working_distance_rate_mm_per_s,
                    "intrinsics_switched": frame.intrinsics_switched,
                    "intrinsics_switch_rate_hz": frame.intrinsics_switch_rate_hz,
                    "calibration_candidate_count": frame.calibration_candidate_count,
                    "calibration_selection_distance": frame.calibration_selection_distance,
                    "calibration_selection_ambiguous": frame.calibration_selection_ambiguous,
                    "drift_proxy_mm": frame.drift_proxy_mm,
                    "tre_proxy_mm": frame.tre_proxy_mm,
                    "dynamic_target_error_mm": frame.dynamic_target_error_mm,
                    "projected_point_count": frame.projected_point_count,
                    "visible_projected_point_count": frame.visible_projected_point_count,
                    "navigation_ready": frame_ready,
                    "navigation_level": "L2" if frame_ready else "L0",
                    "fallback_mode": None if frame_ready else "unregistered_3d_reference",
                    "failure_reasons": "|".join(frame.failure_reasons),
                    "projected_points_json": json.dumps(frame.projected_points_px),
                    "composed_transform_json": json.dumps(frame.composed_transform),
                }
            )


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value) or "case"
