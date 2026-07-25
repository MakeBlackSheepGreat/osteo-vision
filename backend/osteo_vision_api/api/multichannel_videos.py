from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.osteo_vision_api.api.helpers import require_case
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    MultichannelVideoSession,
    MultichannelVideoSessionCreateRequest,
)
from backend.osteo_vision_api.services.multichannel_video_service import (
    MultichannelVideoError,
    MultichannelVideoService,
)


def router(repo: CaseRepository, service: MultichannelVideoService) -> APIRouter:
    api = APIRouter()

    @api.post(
        "/cases/{case_id}/multichannel-video-sessions",
        response_model=MultichannelVideoSession,
    )
    def create_multichannel_video_session(
        case_id: str,
        request: MultichannelVideoSessionCreateRequest,
    ) -> MultichannelVideoSession:
        case = require_case(repo, case_id)
        try:
            return service.create_session(case, request)
        except MultichannelVideoError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": str(exc), "details": exc.details},
            ) from exc

    @api.get(
        "/cases/{case_id}/multichannel-video-sessions/{session_id}",
        response_model=MultichannelVideoSession,
    )
    def get_multichannel_video_session(case_id: str, session_id: str) -> MultichannelVideoSession:
        case = require_case(repo, case_id)
        try:
            return service.get_session(case, session_id)
        except MultichannelVideoError as exc:
            status_code = 404 if exc.code == "multichannel_session_not_found" else 422
            raise HTTPException(
                status_code=status_code,
                detail={"code": exc.code, "message": str(exc), "details": exc.details},
            ) from exc

    return api
