from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pydicom

from backend.src.domains.cases.enums import RegionSource, ReviewState
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import (
    AnalysisRun,
    CandidateRegion,
    CaseRecord,
    ExportRequest,
    RegionOfInterest,
    ReviewEvent,
)
from backend.src.services.export_service import ExportService


def test_export_service_writes_reports(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_export", title="export"))
    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())

    assert Path(response.report_path).exists()
    assert Path(response.manifest_path).exists()
    assert response.dicom_path is not None
    assert Path(response.dicom_path).exists()
    assert Path(response.bundle_path).suffix == ".zip"
    assert response.summary["total_artifact_count"] >= 6
    assert response.summary["dicom_included"] is True
    assert response.summary["review_manifest_row_count"] == 0
    assert response.summary["annotation_audit_version_count"] == 0
    assert any(entry["kind"] == "review_manifest_json" for entry in response.artifact_entries)
    assert any(entry["kind"] == "review_manifest_csv" for entry in response.artifact_entries)
    assert any(entry["kind"] == "evidence_bundle" for entry in response.artifact_entries)
    with ZipFile(response.bundle_path) as archive:
        assert f"reports/{case.case_id}_report.json" in archive.namelist()
        assert f"reports/{case.case_id}_secondary_capture.dcm" in archive.namelist()
        assert f"reports/{case.case_id}_quantification.csv" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.json" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.csv" in archive.namelist()
        assert f"reports/{case.case_id}_three_d_scene_manifest.json" in archive.namelist()
        assert f"reports/{case.case_id}_annotation_audit.json" in archive.namelist()
        assert f"reports/{case.case_id}_annotation_audit.csv" in archive.namelist()
        assert f"reports/{case.case_id}_annotation_manifest_registry.json" in archive.namelist()
    dicom = pydicom.dcmread(response.dicom_path)
    assert dicom.SOPClassUID == pydicom.uid.SecondaryCaptureImageStorage
    assert dicom.PatientIdentityRemoved == "YES"
    assert dicom.Rows > 0
    assert dicom.Columns > 0
    assert "Platform software for research and competition validation" in Path(response.report_path).read_text(
        encoding="utf-8"
    )


def test_export_service_writes_three_d_scene_manifest_from_latest_run(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    scene_manifest_v2 = {
        "schema_version": "osteo-vision-three-d-scene-v2",
        "scene": {
            "coordinate_space": "cbct_label_voxel_spacing_mm",
            "registration_status": "unregistered",
            "navigation_ready": False,
        },
        "nodes": [
            {"id": "volume", "type": "volume", "name": "CBCT label volume"},
            {"id": "seg", "type": "segmentation", "name": "mandible label"},
            {"id": "model", "type": "model", "name": "mandible.stl"},
        ],
        "markups": [{"id": "curve", "type": "curve", "name": "mandibular curve"}],
        "geometry_jobs": [{"id": "surface_export", "type": "surface_export", "status": "completed"}],
        "data_boundary": "public CBCT reference; not navigation",
    }
    case = repo.create(
        CaseRecord(
            case_id="case_three_d_export",
            title="three d export",
            analysis_runs=[
                AnalysisRun(
                    run_id="run_three_d",
                    case_id="case_three_d_export",
                    method_id="cbct_stl_review",
                    status="completed",
                    fused_outputs={
                        "three_d_evidence": {
                            "schema_version": "osteo-vision-three-d-evidence-v1",
                            "model_path": "artifacts/models/mandible.stl",
                            "model_file_name": "mandible.stl",
                            "model_source": "CBCT label surface",
                            "registration_status": "unregistered",
                            "navigation_ready": False,
                            "scene_manifest_v2": scene_manifest_v2,
                            "boundary_note": "未配准，非导航。",
                        }
                    },
                )
            ],
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())
    scene_entry = next(entry for entry in response.artifact_entries if entry["kind"] == "three_d_scene_manifest")
    scene_payload = json.loads(Path(scene_entry["path"]).read_text(encoding="utf-8"))
    report_payload = json.loads(Path(response.report_path).read_text(encoding="utf-8"))

    assert scene_payload["available"] is True
    assert scene_payload["scene_manifest_v2"]["schema_version"] == "osteo-vision-three-d-scene-v2"
    assert scene_payload["scene_manifest_v2"]["nodes"][2]["type"] == "model"
    assert report_payload["three_d_evidence"]["scene_node_count"] == 3
    assert report_payload["three_d_evidence"]["geometry_job_count"] == 1
    assert "Slicer-like scene" in Path(response.report_path.replace("_report.json", "_report.md")).read_text(
        encoding="utf-8"
    )


def test_export_service_preserves_l2_temporal_failure_evidence_in_report_and_bundle(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(
        CaseRecord(
            case_id="case_l2_temporal_export",
            title="L2 temporal failure export",
            three_d_evidence={
                "schema_version": "osteo-vision-three-d-evidence-v2",
                "analysis_mode": "l2_offline_pose_replay",
                "replay_mode": "dynamic_ar_validation",
                "requested_navigation_level": "L2",
                "navigation_level": "L0",
                "navigation_ready": False,
                "fallback_mode": "unregistered_3d_reference",
                "degradation_state": "failed_closed",
                "failure_reasons": [
                    "calibration_selection_ambiguous",
                    "calibration_selection_oscillation",
                ],
                "calibration_selection": {
                    "status": "failed_closed",
                    "switch_count": 2,
                    "ambiguous_frame_count": 1,
                    "oscillation_count": 1,
                    "max_magnification_rate_per_s": 40.0,
                    "max_working_distance_rate_mm_per_s": 1500.0,
                    "max_intrinsics_switch_rate_hz_observed": 20.0,
                    "approved_thresholds": {
                        "max_magnification_rate_per_s": 25.0,
                        "max_working_distance_rate_mm_per_s": 600.0,
                        "max_intrinsics_switch_rate_hz": 10.0,
                        "calibration_ambiguity_margin": 0.05,
                    },
                },
                "l2_threshold_policy_evidence": {
                    "schema_version": "osteo-vision-l2-threshold-policy-v2",
                    "policy_id": "l2-platform-safety-ceiling",
                    "policy_version": "1.0.0",
                    "artifact_sha256": "a" * 64,
                },
                "pose_replay_manifest_path": "artifacts/navigation/pose_replay_manifest.json",
                "pose_replay_manifest_sha256": "b" * 64,
                "pose_replay_frames_csv_path": "artifacts/navigation/pose_replay_frames.csv",
                "pose_replay_frames_csv_sha256": "c" * 64,
                "overlay_video_path": None,
                "overlay_video_sha256": None,
                "doctor_review_status": "accepted",
                "boundary_note": "L2 temporal gate failed; keep L0 reference only.",
            },
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())
    report = json.loads(Path(response.report_path).read_text(encoding="utf-8"))
    navigation = report["three_d_evidence"]["navigation_evidence"]
    assert navigation["navigation_level"] == "L0"
    assert navigation["navigation_ready"] is False
    assert navigation["calibration_transition_summary"]["oscillation_count"] == 1
    assert navigation["failure_reason_labels"] == ["标定选择存在歧义", "出现 A/B/A 内参振荡"]
    markdown = Path(response.report_path.replace("_report.json", "_report.md")).read_text(encoding="utf-8")
    assert "Calibration continuity" in markdown
    assert "calibration_selection_oscillation (出现 A/B/A 内参振荡)" in markdown
    assert "l2-platform-safety-ceiling" in markdown

    scene_entry = next(entry for entry in response.artifact_entries if entry["kind"] == "three_d_scene_manifest")
    scene_payload = json.loads(Path(scene_entry["path"]).read_text(encoding="utf-8"))
    assert scene_payload["schema_version"] == "osteo-vision-exported-three-d-evidence-manifest-v2"
    assert scene_payload["scene_available"] is False
    assert scene_payload["navigation_evidence_available"] is True
    assert scene_payload["navigation_evidence"]["calibration_selection"]["ambiguous_frame_count"] == 1
    with ZipFile(response.bundle_path) as archive:
        archived = json.loads(archive.read(f"reports/{case.case_id}_three_d_scene_manifest.json").decode("utf-8"))
    assert archived["navigation_evidence"]["l2_threshold_policy_evidence"]["policy_version"] == "1.0.0"


def test_export_service_writes_review_manifest_for_training_feedback(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    candidate = CandidateRegion(
        candidate_id="cand_001",
        run_id="run_video",
        score=0.72,
        confidence=0.81,
        risk_type="video_keyframe_model_segmentation",
        status=ReviewState.ACCEPTED,
        explanation="Trainable proxy segmentation model on MP4 keyframe; physician review required.",
        metadata={
            "model_id": "convnext2d_keyframe_proxy_segmenter",
            "model_family": "convnext2d_keyframe_segmenter",
            "analysis_method": "trainable_keyframe_segmenter",
            "frame_index": 12,
            "timestamp_sec": 2.0,
            "bbox_xyxy": [20, 10, 80, 64],
            "bbox_normalized": {"type": "rect", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4},
            "mask_path": "artifacts/example_mask.png",
            "overlay_path": "artifacts/example_overlay.png",
            "source_path": "artifacts/example_keyframe.jpg",
            "image_width": 200,
            "image_height": 160,
        },
    )
    case = repo.create(
        CaseRecord(
            case_id="case_review_export",
            title="review export",
            analysis_runs=[
                AnalysisRun(
                    run_id="run_video",
                    case_id="case_review_export",
                    method_id="mp4_keyframe_segmentation",
                    status="completed",
                    candidate_regions=[candidate],
                )
            ],
            rois=[
                RegionOfInterest(
                    roi_id="roi_cand_001",
                    case_id="case_review_export",
                    source=RegionSource.AI,
                    candidate_id="cand_001",
                    review_state=ReviewState.ACCEPTED,
                    label="suspected_osteomyelitis_boundary",
                    geometry={"type": "rect", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.4},
                    metrics={"frame_index": 12, "timestamp_sec": 2.0},
                )
            ],
            review_events=[
                ReviewEvent(
                    event_id="event_001",
                    case_id="case_review_export",
                    actor="doctor",
                    action="accept_candidate_and_create_roi",
                    target_id="cand_001",
                    before_state="review_required",
                    after_state="accepted",
                    notes="accepted for platform feedback",
                )
            ],
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())
    manifest_path = Path(response.manifest_path)
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert "review_manifest_json_path" in manifest_text
    assert "review_manifest_csv_path" in manifest_text
    assert response.summary["review_manifest_row_count"] == 3
    assert response.summary["roi_count"] == 1
    assert response.summary["review_event_count"] == 1

    review_json_entry = next(entry for entry in response.artifact_entries if entry["kind"] == "review_manifest_json")
    review_csv_entry = next(entry for entry in response.artifact_entries if entry["kind"] == "review_manifest_csv")
    review_json_text = Path(review_json_entry["path"]).read_text(encoding="utf-8")
    review_csv_text = Path(review_csv_entry["path"]).read_text(encoding="utf-8")
    assert "convnext2d_keyframe_proxy_segmenter" in review_json_text
    assert "platform_feedback_training_or_error_analysis_after_deidentification" in review_json_text
    assert "candidate_region" in review_csv_text
    assert "roi_cand_001" in review_csv_text
    assert "accept_candidate_and_create_roi" in review_csv_text

    with ZipFile(response.bundle_path) as archive:
        assert f"reports/{case.case_id}_review_manifest.json" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.csv" in archive.namelist()


def test_export_service_reports_bone_activity_spectrum_and_quantification(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    spectrum = {
        "available": True,
        "status": "available_for_physician_review",
        "low_activity_candidate": {
            "available": True,
            "label": "低活性候选",
            "positive_area_px": 12,
            "bone_gate_fraction": 0.2,
        },
        "transition_candidate": {
            "available": True,
            "label": "过渡复核区",
            "positive_area_px": 18,
            "bone_gate_fraction": 0.3,
        },
        "high_activity_candidate": {
            "available": True,
            "label": "高活性参考",
            "positive_area_px": 24,
            "bone_gate_fraction": 0.4,
        },
        "ignore_region": {
            "available": True,
            "label": "无法判断区",
            "positive_area_px": 6,
            "bone_gate_fraction": 0.1,
            "path": "ignore.png",
            "sha256": "a" * 64,
            "sources": [
                {
                    "source_type": "model_uncertainty",
                    "path": "uncertain.png",
                    "sha256": "b" * 64,
                }
            ],
        },
        "calibration_status": "pending_target_domain_validation",
        "spatial_effect_applied": True,
        "review_required": True,
        "confidence_statement": "0.80 仅表示信号候选置信度。",
        "medical_boundary": "空间活性候选需基于已复核骨面门控，并由医生确认。",
    }
    case = repo.create(
        CaseRecord(
            case_id="case_activity_export",
            title="activity export",
            analysis_runs=[
                AnalysisRun(
                    run_id="run_activity",
                    case_id="case_activity_export",
                    method_id="mp4_keyframe_segmentation",
                    status="completed",
                    fused_outputs={
                        "video_segmentation_summary": {"analysis_scope": "video_signal_segmentation"},
                        "frame_details": [
                            {
                                "frame_index": 7,
                                "timestamp_sec": 1.4,
                                "video_signal_segmentation": {"bone_activity_spectrum": spectrum},
                            }
                        ],
                    },
                )
            ],
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())
    report_payload = json.loads(Path(response.report_path).read_text(encoding="utf-8"))
    frame_spectrum = report_payload["video_signal_segmentation"]["frame_examples"][0]["bone_activity_spectrum"]
    assert frame_spectrum["candidates"]["low_activity_candidate"]["positive_area_px"] == 12
    assert frame_spectrum["candidates"]["ignore_region"]["sha256"] == "a" * 64
    assert frame_spectrum["calibration_status"] == "pending_target_domain_validation"
    markdown = Path(response.report_path.replace("_report.json", "_report.md")).read_text(encoding="utf-8")
    assert "低活性候选" in markdown
    assert "无法判断区" in markdown
    assert "信号候选置信度" in markdown
    assert "model_uncertainty:uncertain.png" in markdown
    assert "b" * 64 in markdown
    csv_path = next(entry["path"] for entry in response.artifact_entries if entry["kind"] == "quantification_csv")
    csv_text = Path(csv_path).read_text(encoding="utf-8")
    assert "bone_activity_candidate" in csv_text
    assert "high_activity_candidate" in csv_text
    assert "ignore_region" in csv_text
    assert "model_uncertainty" in csv_text
    assert "pending_target_domain_validation" in csv_text


def test_export_service_reports_patient_conditioning_evidence_and_safe_fallback(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    clinical_feature_vector = {
        "schema_version": "osteo-vision-clinical-feature-vector-v1",
        "feature_version": "clinical-feature-vector-v1",
        "feature_names": [
            "age_years",
            "sex_at_birth_female",
            "diabetes",
            "renal_disease",
            "egfr_ml_min_1_73m2",
        ],
        "present_mask": [True, True, True, False, False],
        "missing_mask": [False, False, False, True, False],
        "ood_mask": [False, False, False, False, True],
        "checkpoint_consumed_mask": [True, True, True, False, False],
        "spatial_effect_applied_mask": [False, False, False, False, False],
        "recorded_input_summary": {
            "age_recorded": True,
            "sex_recorded": True,
            "comorbidity_record_count": 2,
            "comorbidities_reviewed": True,
            "medication_record_count": 1,
            "medications_reviewed": True,
            "lab_record_count": 3,
            "eligible_lab_record_count": 1,
        },
        "checkpoint_consumed_feature_names": ["age_years", "sex_at_birth_female", "diabetes"],
        "spatially_applied_feature_names": [],
        "missing_feature_names": ["renal_disease"],
        "ood_feature_names": ["egfr_ml_min_1_73m2"],
        "unconsumed_recorded_inputs": [
            {
                "input_domain": "medications",
                "record_count": 1,
                "reason_codes": ["checkpoint_declares_no_medication_features"],
            },
            {
                "input_domain": "laboratory_results",
                "record_count": 2,
                "reason_codes": ["recorded_lab_not_consumed_by_checkpoint"],
            },
        ],
        "vector_checksum": "v" * 64,
        "runtime_vector_checksum": "r" * 64,
    }
    evidence = {
        "schema_version": "osteo-vision-patient-conditioned-runtime-v1",
        "model_id": "patient_conditioned_kits23_proxy",
        "model_family": "patient_conditioned_segmenter",
        "available": True,
        "proxy_checkpoint": True,
        "spatial_effect_applied": False,
        "safe_fallback_applied": True,
        "failure_reasons": ["non_target_domain_proxy"],
        "target_domain_promotion_ready": False,
        "runtime_replacement_allowed": False,
        "clinical_context_checksum": "c" * 64,
        "clinical_present_fraction": 0.8,
        "clinical_feature_vector": clinical_feature_vector,
        "reviewed_bone_gate": {"path": "bone.png", "sha256": "b" * 64},
        "image_only_probability_path": "image_only.png",
        "conditioned_probability_path": "conditioned.png",
        "difference_mask_path": "difference.png",
        "evidence_manifest_path": "patient_conditioning.json",
        "quantification": {
            "positive_area_px": 42,
            "positive_area_fraction": 0.25,
            "difference_area_px": 0,
            "spatial_effect_area_px": 0,
            "delta_abs_mean": 0.0,
            "uncertainty_mean": 0.2,
        },
        "medical_boundary": "Non-target-domain proxy evidence requiring physician review.",
    }
    case = repo.create(
        CaseRecord(
            case_id="case_patient_conditioning_export",
            title="patient conditioning export",
            analysis_runs=[
                AnalysisRun(
                    run_id="run_patient_conditioning",
                    case_id="case_patient_conditioning_export",
                    method_id="dual_channel_fusion",
                    status="completed",
                    fused_outputs={"patient_conditioning_evidence": evidence},
                )
            ],
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())

    report = json.loads(Path(response.report_path).read_text(encoding="utf-8"))
    section = report["patient_conditioning_evidence"]
    assert section["available"] is True
    assert section["proxy_checkpoint"] is True
    assert section["spatial_effect_applied"] is False
    assert section["runtime_replacement_allowed"] is False
    assert section["quantification"]["difference_area_px"] == 0
    assert section["clinical_feature_vector"] == clinical_feature_vector
    assert section["clinical_feature_vector"]["spatial_effect_applied_mask"] == [False, False, False, False, False]
    markdown = Path(response.report_path.replace("_report.json", "_report.md")).read_text(encoding="utf-8")
    assert "Patient-Conditioned Segmentation Comparison" in markdown
    assert "non_target_domain_proxy" in markdown
    assert "Clinical feature vector schema: `osteo-vision-clinical-feature-vector-v1`" in markdown
    assert "Final spatially applied feature count: `0`" in markdown
    assert "checkpoint_declares_no_medication_features" in markdown
    assert "recorded_lab_not_consumed_by_checkpoint" in markdown
    assert "v" * 64 in markdown
    csv_path = next(entry["path"] for entry in response.artifact_entries if entry["kind"] == "quantification_csv")
    csv_text = Path(csv_path).read_text(encoding="utf-8")
    assert "patient_conditioning_summary" in csv_text
    assert "patient_conditioned_kits23_proxy" in csv_text
    assert "non_target_domain_proxy" in csv_text
    csv_rows = list(csv.DictReader(StringIO(csv_text)))
    conditioning_row = next(row for row in csv_rows if row["record_type"] == "patient_conditioning_summary")
    assert conditioning_row["clinical_feature_vector_schema_version"] == ("osteo-vision-clinical-feature-vector-v1")
    assert (
        json.loads(conditioning_row["clinical_feature_vector_feature_names"])
        == clinical_feature_vector["feature_names"]
    )
    assert json.loads(conditioning_row["clinical_feature_vector_spatial_effect_applied_mask"]) == [
        False,
        False,
        False,
        False,
        False,
    ]
    assert json.loads(conditioning_row["clinical_feature_vector_unconsumed_recorded_inputs"]) == (
        clinical_feature_vector["unconsumed_recorded_inputs"]
    )
    assert conditioning_row["clinical_feature_vector_vector_checksum"] == "v" * 64
    assert conditioning_row["clinical_feature_vector_runtime_vector_checksum"] == "r" * 64

    with ZipFile(response.bundle_path) as archive:
        bundled_report = json.loads(archive.read(f"reports/{case.case_id}_report.json").decode("utf-8"))
        bundled_csv = archive.read(f"reports/{case.case_id}_quantification.csv").decode("utf-8")
    assert bundled_report["patient_conditioning_evidence"]["clinical_feature_vector"] == clinical_feature_vector
    assert "clinical_feature_vector_spatial_effect_applied_mask" in bundled_csv
    assert "checkpoint_declares_no_medication_features" in bundled_csv
