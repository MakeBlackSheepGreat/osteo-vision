from __future__ import annotations

from typing import Any

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
