from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

import backend.osteo_vision_api.services.job_tasks as job_tasks
from backend.osteo_vision_api.services.job_service import JobRegistry
from backend.osteo_vision_api.services.offline_pose_replay_service import (
    OfflinePoseReplayRequestError,
)
from backend.osteo_vision_api.services.static_registration_service import (
    StaticRegistrationRequestError,
)

NavigationRunner = Callable[..., dict[str, Any]]


def test_cbct_modeling_job_exposes_detailed_progress_before_case_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs = JobRegistry(tmp_path / "jobs.json")
    job = jobs.create(kind="cbct_surface_modeling", payload={"case_id": "case_progress"})
    observed_progress: list[dict[str, Any]] = []

    def build_with_progress(**kwargs: Any) -> dict[str, Any]:
        reporter = kwargs["progress_reporter"]
        reporter(
            "extract_surface",
            62,
            "正在从标签体提取三维表面网格。",
            {"current_file": "case_progress_label.nii.gz"},
        )
        observed_progress.append((jobs.get(job["job_id"]) or {})["progress"])
        return {
            "modeling_status": "completed",
            "model_path": "case_progress.stl",
            "three_d_evidence": {"model_path": "case_progress.stl"},
        }

    monkeypatch.setattr(job_tasks, "build_cbct_surface_model", build_with_progress)
    monkeypatch.setattr(
        job_tasks,
        "persist_three_d_modeling_result",
        lambda _repo, *, case_id, job_id, result: {
            **result,
            "case_persistence": {"status": "persisted", "case_id": case_id, "job_id": job_id},
        },
    )

    result = job_tasks.run_cbct_surface_modeling_job(
        jobs,
        job["job_id"],
        object(),
        Path("case_progress.nii.gz"),
        label_value=1,
        case_id="case_progress",
        dataset_id="unit",
        decimation_step=1,
        source_original_filename="case_progress.nii.gz",
    )

    assert observed_progress == [
        {
            "phase": "extract_surface",
            "percent": 62,
            "message": "正在从标签体提取三维表面网格。",
            "details": {"current_file": "case_progress_label.nii.gz"},
        }
    ]
    assert result["status"] == "completed"
    assert jobs.get(job["job_id"])["progress"]["percent"] == 100  # type: ignore[index]


@pytest.mark.parametrize(
    (
        "kind",
        "service_attribute",
        "persist_attribute",
        "runner",
    ),
    [
        (
            "l1_static_registration",
            "StaticRegistrationService",
            "persist_l1_registration_result",
            job_tasks.run_l1_static_registration_job,
        ),
        (
            "l2_offline_pose_replay",
            "OfflinePoseReplayService",
            "persist_l2_pose_replay_result",
            job_tasks.run_l2_offline_pose_replay_job,
        ),
    ],
)
def test_navigation_job_cancel_after_service_return_skips_case_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    service_attribute: str,
    persist_attribute: str,
    runner: NavigationRunner,
) -> None:
    jobs = JobRegistry(tmp_path / "jobs.json")
    job = jobs.create(kind=kind, payload={"case_id": "case_cancel_success"})
    persistence_calls: list[dict[str, Any]] = []

    class CancelingService:
        def __init__(self, _settings: object, _repo: object) -> None:
            pass

        def register(self, _payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
            jobs.cancel(job_id)
            return {"case_id": "case_cancel_success", "three_d_evidence": {}}

        def replay(self, _payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
            jobs.cancel(job_id)
            return {"case_id": "case_cancel_success", "three_d_evidence": {}}

    def record_persistence(*_args: object, **kwargs: Any) -> dict[str, Any]:
        persistence_calls.append(kwargs)
        return kwargs["result"]

    monkeypatch.setattr(job_tasks, service_attribute, CancelingService)
    monkeypatch.setattr(job_tasks, persist_attribute, record_persistence)

    result = runner(
        jobs,
        job["job_id"],
        object(),
        object(),
        {"case_id": "case_cancel_success"},
    )

    assert result["status"] == "canceled"
    assert persistence_calls == []
    assert jobs.get(job["job_id"])["status"] == "canceled"  # type: ignore[index]


@pytest.mark.parametrize(
    (
        "kind",
        "service_attribute",
        "persist_attribute",
        "runner",
        "error_type",
    ),
    [
        (
            "l1_static_registration",
            "StaticRegistrationService",
            "persist_l1_registration_result",
            job_tasks.run_l1_static_registration_job,
            StaticRegistrationRequestError,
        ),
        (
            "l2_offline_pose_replay",
            "OfflinePoseReplayService",
            "persist_l2_pose_replay_result",
            job_tasks.run_l2_offline_pose_replay_job,
            OfflinePoseReplayRequestError,
        ),
    ],
)
def test_navigation_job_cancel_during_failure_evidence_skips_case_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    service_attribute: str,
    persist_attribute: str,
    runner: NavigationRunner,
    error_type: type[ValueError],
) -> None:
    jobs = JobRegistry(tmp_path / "jobs.json")
    job = jobs.create(kind=kind, payload={"case_id": "case_cancel_failure"})
    persistence_calls: list[dict[str, Any]] = []

    class FailingService:
        def __init__(self, _settings: object, _repo: object) -> None:
            pass

        def register(self, _payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
            raise error_type("controlled_failure", f"failure for {job_id}")

        def replay(self, _payload: dict[str, Any], *, job_id: str) -> dict[str, Any]:
            raise error_type("controlled_failure", f"failure for {job_id}")

        def failure_result(
            self,
            _payload: dict[str, Any],
            *,
            job_id: str,
            code: str,
            message: str,
        ) -> dict[str, Any]:
            jobs.cancel(job_id)
            return {
                "case_id": "case_cancel_failure",
                "error_code": code,
                "error_message": message,
                "three_d_evidence": {},
            }

    def record_persistence(*_args: object, **kwargs: Any) -> dict[str, Any]:
        persistence_calls.append(kwargs)
        return kwargs["result"]

    monkeypatch.setattr(job_tasks, service_attribute, FailingService)
    monkeypatch.setattr(job_tasks, persist_attribute, record_persistence)

    result = runner(
        jobs,
        job["job_id"],
        object(),
        object(),
        {"case_id": "case_cancel_failure"},
    )

    assert result["status"] == "canceled"
    assert persistence_calls == []
    assert jobs.get(job["job_id"])["status"] == "canceled"  # type: ignore[index]
