from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.osteo_vision_api.domains.cases.enums import InputChannel
from backend.osteo_vision_api.domains.cases.schemas import CaseInputAsset, CaseRecord
from backend.osteo_vision_api.services.input_service import InputService
from backend.osteo_vision_api.services.standard_demo_case import (
    STANDARD_DEMO_VIDEO_RECORD_ID,
    StandardDemoCaseService,
)


class _VideoLibrary:
    def __init__(self, preferred: dict[str, Any] | None, fallback: list[dict[str, Any]]) -> None:
        self.preferred = preferred
        self.fallback = fallback
        self.get_calls: list[str] = []
        self.list_calls: list[dict[str, Any]] = []

    def get_candidate(self, record_id: str) -> dict[str, Any] | None:
        self.get_calls.append(record_id)
        return self.preferred

    def list_candidates(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return {"items": self.fallback}


class _CaseRepository:
    def __init__(self, record: CaseRecord) -> None:
        self.record = record

    def get(self, case_id: str) -> CaseRecord | None:
        return self.record if self.record.case_id == case_id else None

    def save(self, record: CaseRecord) -> CaseRecord:
        self.record = record
        return record

    def create(self, record: CaseRecord) -> CaseRecord:
        self.record = record
        return record


def test_selected_video_candidate_uses_indexed_preferred_record() -> None:
    preferred = {"record_id": STANDARD_DEMO_VIDEO_RECORD_ID, "system_readable": True}
    library = _VideoLibrary(preferred, [])
    service = StandardDemoCaseService(None, None, library)  # type: ignore[arg-type]

    assert service._selected_video_candidate() is preferred
    assert library.get_calls == [STANDARD_DEMO_VIDEO_RECORD_ID]
    assert library.list_calls == []


def test_selected_video_candidate_falls_back_to_first_readable_candidate() -> None:
    fallback = [{"record_id": "fallback", "system_readable": True}]
    library = _VideoLibrary(None, fallback)
    service = StandardDemoCaseService(None, None, library)  # type: ignore[arg-type]

    assert service._selected_video_candidate() is fallback[0]
    assert library.list_calls == [{"accepted_only": True, "limit": 1}]


def test_existing_demo_refreshes_a_video_path_from_an_older_desktop_release(tmp_path: Path) -> None:
    current_video = tmp_path / "current-release" / "OFDVDNET_001.mp4"
    current_video.parent.mkdir()
    current_video.write_bytes(b"current release placeholder")
    stale_video = tmp_path / "old-release" / "OFDVDNET_001.mp4"
    existing = CaseRecord(
        case_id="case_standard_demo",
        title="stale demo",
        version=4,
        inputs=[
            CaseInputAsset(
                input_id="stale-input",
                channel=InputChannel.VIDEO,
                path=str(stale_video),
                mime_type="video/mp4",
                metadata={"standard_demo": True, "record_id": STANDARD_DEMO_VIDEO_RECORD_ID},
            )
        ],
        review_summary={
            "standard_demo_version": 9,
            "multichannel_session_status": "blocked",
        },
    )
    repository = _CaseRepository(existing)
    library = _VideoLibrary(
        {
            "record_id": STANDARD_DEMO_VIDEO_RECORD_ID,
            "system_readable": True,
            "local_path": str(current_video),
            "composite_layout_available": False,
        },
        [],
    )
    service = StandardDemoCaseService(
        repository,
        InputService([tmp_path]),
        library,
        artifact_root=tmp_path / "artifacts",
    )

    refreshed = service.ensure_case()

    assert len(refreshed.inputs) == 1
    assert refreshed.inputs[0].path == str(current_video.resolve())
    assert refreshed.inputs[0].metadata["record_id"] == STANDARD_DEMO_VIDEO_RECORD_ID
    assert refreshed.inputs[0].metadata["standard_demo"] is True
