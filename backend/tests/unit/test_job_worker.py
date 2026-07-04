from __future__ import annotations

from pathlib import Path

import cv2
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


def _write_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (80, 60))
    for index in range(6):
        frame = np.full((60, 80, 3), 20 + index * 20, dtype=np.uint8)
        frame[20:38, 26:52, 1] = 255
        writer.write(frame)
    writer.release()
