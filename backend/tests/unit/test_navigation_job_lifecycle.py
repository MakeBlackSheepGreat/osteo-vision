from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

import backend.src.services.job_tasks as job_tasks
from backend.src.services.job_service import JobRegistry
from backend.src.services.offline_pose_replay_service import (
    OfflinePoseReplayRequestError,
)
from backend.src.services.static_registration_service import (
    StaticRegistrationRequestError,
)

NavigationRunner = Callable[..., dict[str, Any]]


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
