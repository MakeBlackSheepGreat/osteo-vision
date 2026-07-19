from __future__ import annotations

from pathlib import Path

import pytest

from backend.src.services.job_service import (
    JobCapacityError,
    JobConflictError,
    JobRegistry,
)


def test_job_registry_persists_completed_jobs(tmp_path: Path) -> None:
    store = tmp_path / "jobs.json"
    registry = JobRegistry(store)
    job = registry.create(kind="case_analysis", payload={"case_id": "case_1"})
    registry.mark_completed(job["job_id"], {"run_id": "run_1"})

    loaded = JobRegistry(store).get(job["job_id"])

    assert loaded is not None
    assert loaded["status"] == "completed"
    assert loaded["progress"]["percent"] == 100
    assert loaded["progress"]["phase"] == "completed"
    assert loaded["payload"]["case_id"] == "case_1"
    assert loaded["result"]["run_id"] == "run_1"


def test_job_registry_retries_transient_windows_replace_lock(tmp_path: Path, monkeypatch) -> None:
    original_replace = Path.replace
    calls = {"count": 0}

    def flaky_replace(path: Path, target: Path) -> Path:
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError(5, "transient file lock")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr("backend.src.services.job_service.time.sleep", lambda _seconds: None)

    registry = JobRegistry(tmp_path / "jobs.json")
    job = registry.create(kind="case_analysis", payload={"case_id": "case_retry"})

    assert calls["count"] >= 2
    assert registry.get(job["job_id"])["status"] == "queued"  # type: ignore[index]


def test_job_registry_marks_unfinished_jobs_failed_after_restart(
    tmp_path: Path,
) -> None:
    store = tmp_path / "jobs.json"
    registry = JobRegistry(store)
    job = registry.create(kind="upload_keyframe_extraction", payload={"source_path": "sample.mp4"})
    registry.mark_running(job["job_id"])

    loaded = JobRegistry(store).get(job["job_id"])

    assert loaded is not None
    assert loaded["status"] == "failed"
    assert loaded["error"] == "Job did not complete before process restart."
    assert loaded["progress"]["phase"] == "failed"


def test_job_registry_keeps_queued_jobs_after_restart(tmp_path: Path) -> None:
    store = tmp_path / "jobs.json"
    registry = JobRegistry(store)
    job = registry.create(kind="case_analysis", payload={"case_id": "case_queued"})

    loaded = JobRegistry(store).get(job["job_id"])

    assert loaded is not None
    assert loaded["status"] == "queued"


def test_job_registry_claims_oldest_queued_job(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "jobs.json")
    first = registry.create(kind="case_analysis", payload={"case_id": "case_1"})
    registry.create(kind="case_analysis", payload={"case_id": "case_2"})

    claimed = registry.claim_next_queued(kind="case_analysis")

    assert claimed is not None
    assert claimed["job_id"] == first["job_id"]
    assert claimed["status"] == "running"
    assert registry.get(first["job_id"])["status"] == "running"  # type: ignore[index]


def test_job_registry_cancel_preserves_canceled_status(tmp_path: Path) -> None:
    store = tmp_path / "jobs.json"
    registry = JobRegistry(store)
    job = registry.create(kind="case_analysis", payload={"case_id": "case_cancel"})
    registry.update_progress(job["job_id"], phase="running", percent=42, message="Halfway")
    canceled = registry.cancel(job["job_id"])

    registry.mark_running(job["job_id"])
    registry.mark_completed(job["job_id"], {"run_id": "run_should_not_win"})
    loaded = JobRegistry(store).get(job["job_id"])

    assert canceled is not None
    assert canceled["status"] == "canceled"
    assert canceled["progress"]["percent"] == 42
    assert loaded is not None
    assert loaded["status"] == "canceled"
    assert "run_should_not_win" not in loaded.get("result", {})


def test_job_registry_enforces_active_capacity(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "jobs.json")
    registry.create(kind="case_analysis", payload={"case_id": "case_1"}, max_active=1)

    with pytest.raises(JobCapacityError) as exc_info:
        registry.create(kind="case_analysis", payload={"case_id": "case_2"}, max_active=1)

    assert exc_info.value.kind == "case_analysis"
    assert exc_info.value.active_count == 1
    assert exc_info.value.max_active == 1


def test_job_registry_enforces_singleton_payload_keys(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "jobs.json")
    first = registry.create(
        kind="case_analysis",
        payload={"case_id": "case_lock"},
        singleton_keys=["case_id"],
    )

    with pytest.raises(JobConflictError) as exc_info:
        registry.create(
            kind="case_analysis",
            payload={"case_id": "case_lock"},
            singleton_keys=["case_id"],
        )

    assert exc_info.value.active_job["job_id"] == first["job_id"]
    registry.mark_completed(first["job_id"], {"run_id": "run_done"})
    second = registry.create(
        kind="case_analysis",
        payload={"case_id": "case_lock"},
        singleton_keys=["case_id"],
    )
    assert second["job_id"] != first["job_id"]


@pytest.mark.parametrize(
    ("first_kind", "second_kind"),
    [
        ("l1_static_registration", "l2_offline_pose_replay"),
        ("l2_offline_pose_replay", "l1_static_registration"),
    ],
)
def test_job_registry_serializes_navigation_pipeline_jobs_across_kinds(
    tmp_path: Path,
    first_kind: str,
    second_kind: str,
) -> None:
    registry = JobRegistry(tmp_path / "jobs.json")
    first = registry.create(
        kind=first_kind,
        payload={"case_id": "case_navigation_lock"},
        singleton_keys=["case_id"],
    )

    with pytest.raises(JobConflictError) as exc_info:
        registry.create(
            kind=second_kind,
            payload={"case_id": "case_navigation_lock"},
            singleton_keys=["case_id"],
        )

    assert first["family"] == "navigation_pipeline"
    assert exc_info.value.active_job["job_id"] == first["job_id"]
    assert exc_info.value.active_job["kind"] == first_kind

    registry.mark_completed(first["job_id"], {"navigation_level": "L0"})
    second = registry.create(
        kind=second_kind,
        payload={"case_id": "case_navigation_lock"},
        singleton_keys=["case_id"],
    )
    assert second["family"] == "navigation_pipeline"
