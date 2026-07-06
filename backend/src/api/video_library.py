from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.src.api.helpers import require_case
from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.input_service import InputService
from backend.src.services.video_library_service import VideoLibraryService


def router(repo: CaseRepository, input_service: InputService, video_library: VideoLibraryService) -> APIRouter:
    api = APIRouter()

    @api.get("/video-library/candidates")
    def list_video_candidates(
        accepted_only: bool = Query(default=True),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, object]:
        return video_library.list_candidates(accepted_only=accepted_only, limit=limit)

    @api.post("/video-library/candidates/{record_id}/preview")
    def create_video_candidate_preview(record_id: str) -> dict[str, object]:
        try:
            candidate = video_library.ensure_preview(record_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Video candidate not found") from exc
        if candidate.get("preview_status") == "unsupported_or_missing":
            raise HTTPException(status_code=422, detail=candidate)
        return candidate

    @api.post("/cases/{case_id}/video-library/{record_id}/inputs", response_model=CaseRecord)
    def import_video_candidate(case_id: str, record_id: str) -> CaseRecord:
        case = require_case(repo, case_id)
        candidate = video_library.get_candidate(record_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Video candidate not found")
        if not candidate.get("system_readable"):
            raise HTTPException(status_code=422, detail="Video candidate is missing or unsupported by the MP4 pipeline")
        existing = [
            asset
            for asset in case.inputs
            if asset.path == candidate["local_path"] and asset.channel == InputChannel.VIDEO
        ]
        if existing:
            return case
        request = InputCreateRequest(
            channel=InputChannel.VIDEO,
            path=str(candidate["local_path"]),
            mime_type="video/mp4",
            metadata={
                "source": "public_video_library",
                "record_id": candidate["record_id"],
                "source_page_original_link": candidate["source_page_original_link"],
                "direct_download_link": candidate["direct_download_link"],
                "fluorescence": candidate["fluorescence"],
                "medical_scene": candidate["medical_scene"],
                "domain_boundary": candidate["domain_boundary"],
            },
        )
        return repo.save(input_service.add_inputs(case, [request]))

    return api
