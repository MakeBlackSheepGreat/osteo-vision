from __future__ import annotations

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
    assert any(entry["kind"] == "review_manifest_json" for entry in response.artifact_entries)
    assert any(entry["kind"] == "review_manifest_csv" for entry in response.artifact_entries)
    assert any(entry["kind"] == "evidence_bundle" for entry in response.artifact_entries)
    with ZipFile(response.bundle_path) as archive:
        assert f"reports/{case.case_id}_report.json" in archive.namelist()
        assert f"reports/{case.case_id}_secondary_capture.dcm" in archive.namelist()
        assert f"reports/{case.case_id}_quantification.csv" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.json" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.csv" in archive.namelist()
    dicom = pydicom.dcmread(response.dicom_path)
    assert dicom.SOPClassUID == pydicom.uid.SecondaryCaptureImageStorage
    assert dicom.PatientIdentityRemoved == "YES"
    assert dicom.Rows > 0
    assert dicom.Columns > 0
    assert "Research prototype only" in Path(response.report_path).read_text(encoding="utf-8")


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
                    notes="accepted for prototype feedback",
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
    assert "prototype_retraining_or_error_analysis_after_deidentification" in review_json_text
    assert "candidate_region" in review_csv_text
    assert "roi_cand_001" in review_csv_text
    assert "accept_candidate_and_create_roi" in review_csv_text

    with ZipFile(response.bundle_path) as archive:
        assert f"reports/{case.case_id}_review_manifest.json" in archive.namelist()
        assert f"reports/{case.case_id}_review_manifest.csv" in archive.namelist()
