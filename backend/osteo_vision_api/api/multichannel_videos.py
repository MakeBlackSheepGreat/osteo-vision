from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


class RealtimeMultichannelFrameRequest(BaseModel):
    timestamp_sec: float = Field(ge=0.0, le=86_400.0)
    alpha: float = Field(default=0.45, ge=0.0, le=1.0)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    colormap: str = Field(default="green", pattern="^(green|amber|magenta)$")
    white_frame_base64: str | None = Field(default=None, max_length=3_000_000)
    fluorescence_frame_base64: str | None = Field(default=None, max_length=3_000_000)

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

    @api.post("/cases/{case_id}/multichannel-video-sessions/{session_id}/realtime-frame")
    def analyze_realtime_multichannel_frame(
        case_id: str,
        session_id: str,
        request: RealtimeMultichannelFrameRequest,
    ) -> dict:
        case = require_case(repo, case_id)
        try:
            return service.analyze_realtime_frame(
                case,
                session_id,
                request.timestamp_sec,
                alpha=request.alpha,
                threshold=request.threshold,
                colormap=request.colormap,
                white_frame_base64=request.white_frame_base64,
                fluorescence_frame_base64=request.fluorescence_frame_base64,
            )
        except MultichannelVideoError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, "message": str(exc), "details": exc.details},
            ) from exc

    return api
