from __future__ import annotations

from pathlib import Path

import cv2
import nibabel as nib
import numpy as np

from backend.src.core.settings import Settings
from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import build_case_repository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.input_service import InputService
from backend.src.services.job_service import JobRegistry
from backend.src.services.job_worker import LocalJobWorker


def test_local_job_worker_processes_queued_case_analysis(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    settings = Settings(
        artifact_root=tmp_path / "artifacts",
        case_store_path=tmp_path / "cases.sqlite",
        job_store_path=tmp_path / "jobs.json",
        video_manifest_path=tmp_path / "videos.csv",
    )
    repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
    case = CaseRecord(case_id="case_worker_analysis", title="worker analysis")
    case = InputService().add_inputs(
        case,
        [
            InputCreateRequest(
                channel=InputChannel.WHITE_LIGHT,
                path=str(Path("tests/fixtures/platform/white.png").resolve()),
            ),
            InputCreateRequest(
                channel=InputChannel.FLUORESCENCE,
                path=str(Path("tests/fixtures/platform/fluorescence.png").resolve()),
            ),
        ],
    )
    repo.create(case)
    registry = JobRegistry(settings.job_store_path)
    job = registry.create(
        kind="case_analysis",
        payload={
            "case_id": case.case_id,
            "selected_input_ids": [],
            "parameters": {"threshold": 0.6},
            "roi_hints": [],
        },
    )

    result = LocalJobWorker(settings).run_once(limit=1)

    completed = JobRegistry(settings.job_store_path).get(job["job_id"])
    updated = repo.get(case.case_id)
    assert result["processed_count"] == 1
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result"]["run_status"] == "completed"
    assert updated is not None
    assert updated.analysis_runs[-1].status == "completed"


def test_local_job_worker_processes_queued_upload_keyframes(tmp_path: Path) -> None:
    settings = Settings(
        artifact_root=tmp_path / "artifacts",
        case_store_path=tmp_path / "cases.sqlite",
        job_store_path=tmp_path / "jobs.json",
        video_manifest_path=tmp_path / "videos.csv",
    )
    video_path = tmp_path / "worker_video.mp4"
    _write_video(video_path)
    output_dir = tmp_path / "keyframes"
    registry = JobRegistry(settings.job_store_path)
    job = registry.create(
        kind="upload_keyframe_extraction",
        payload={"source_path": str(video_path), "output_dir": str(output_dir), "max_frames": 3},
    )

    result = LocalJobWorker(settings).run_once(limit=1)

    completed = JobRegistry(settings.job_store_path).get(job["job_id"])
    assert result["processed_count"] == 1
    assert completed is not None
    assert completed["status"] == "completed"
    assert len(completed["result"]["keyframes"]) == 3
    assert Path(completed["result"]["keyframe_manifest_path"]).exists()
    assert Path(completed["result"]["frame_index_manifest_path"]).exists()
    assert Path(completed["result"]["timeline_manifest_path"]).exists()


def test_local_job_worker_processes_queued_cbct_surface_modeling(tmp_path: Path) -> None:
    settings = Settings(
        artifact_root=tmp_path / "artifacts",
        case_store_path=tmp_path / "cases.sqlite",
        job_store_path=tmp_path / "jobs.json",
        video_manifest_path=tmp_path / "videos.csv",
    )
    source_dir = settings.artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "worker_cbct_label.nii.gz"
    data = np.zeros((8, 8, 8), dtype=np.uint8)
    data[2:6, 2:6, 2:6] = 1
    nib.save(nib.Nifti1Image(data, affine=np.eye(4)), str(source))
    registry = JobRegistry(settings.job_store_path)
    job = registry.create(
        kind="cbct_surface_modeling",
        payload={
            "source_path": str(source),
            "source_role": "label",
            "label_value": 1,
            "case_id": "case_worker_cbct",
            "dataset_id": "worker",
            "decimation_step": 1,
        },
    )

    result = LocalJobWorker(settings).run_once(limit=1, kinds=["cbct_surface_modeling"])

    completed = JobRegistry(settings.job_store_path).get(job["job_id"])
    assert result["processed_count"] == 1
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result"]["modeling_status"] == "completed"
    assert Path(completed["result"]["model_path"]).exists()
    assert completed["result"]["three_d_evidence"]["navigation_ready"] is False


def test_local_job_worker_processes_queued_l1_static_registration(tmp_path: Path) -> None:
    settings = Settings(
        artifact_root=tmp_path / "artifacts",
        case_store_path=tmp_path / "cases.sqlite",
        job_store_path=tmp_path / "jobs.json",
        video_manifest_path=tmp_path / "videos.csv",
    )
    repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
    case = repo.create(CaseRecord(case_id="case_worker_l1", title="worker L1"))
    model = settings.artifact_root / "models" / "mandible.stl"
    model.parent.mkdir(parents=True)
    model.write_text("solid mandible\nendsolid mandible\n", encoding="utf-8")
    source = [[0, 0, 0], [20, 0, 0], [0, 20, 0], [0, 0, 20]]
    target = [[5, -3, 2], [25, -3, 2], [5, 17, 2], [5, -3, 22]]
    job = JobRegistry(settings.job_store_path).create(
        kind="l1_static_registration",
        payload={
            "case_id": case.case_id,
            "input_mode": "manual_metadata",
            "model_path": str(model),
            "source_points": source,
            "target_points": target,
            "validation_source_points": [[10, 10, 10]],
            "validation_target_points": [[15, 7, 12]],
            "source_space": "cbct_lps_mm",
            "target_space": "phantom_reference_mm",
            "unit": "mm",
            "fre_threshold_mm": 1.0,
            "tre_threshold_mm": 1.0,
            "threshold_source": "phantom_protocol_v1",
            "doctor_review_status": "review_required",
            "microscope_pose_evidence": {
                "calibration_status": "valid",
                "magnification": 4,
                "calibration_magnification_min": 2,
                "calibration_magnification_max": 8,
                "working_distance_mm": 250,
                "calibration_working_distance_min_mm": 200,
                "calibration_working_distance_max_mm": 300,
                "depth_status": "valid",
            },
        },
    )

    result = LocalJobWorker(settings).run_once(limit=1, kinds=["l1_static_registration"])

    completed = JobRegistry(settings.job_store_path).get(job["job_id"])
    updated = repo.get(case.case_id)
    assert result["processed_count"] == 1
    assert completed is not None and completed["status"] == "completed"
    assert updated is not None
    assert updated.three_d_evidence["registration_status"] == "registered"
    assert updated.three_d_evidence["navigation_level"] == "L0"


def _write_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        frame = np.full((60, 80, 3), 20 + index * 20, dtype=np.uint8)
        frame[20:38, 26:52, 1] = 255
        writer.write(frame)
    writer.release()
