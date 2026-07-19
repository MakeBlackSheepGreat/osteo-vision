from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.src.domains.cases.repository import CaseRepository
from backend.src.services.live_frame_service import LiveFrameAnalysisService


def router(repo: CaseRepository, service: LiveFrameAnalysisService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/live-frames")
    async def analyze_live_frame(case_id: str, request: Request) -> dict[str, Any]:
        if repo.get(case_id) is None:
            raise HTTPException(status_code=404, detail="Case not found")
        content_type = (request.headers.get("content-type") or "").lower()
        if content_type not in {"image/jpeg", "image/jpg", "image/png", "application/octet-stream"}:
            raise HTTPException(status_code=415, detail="Live frame must be JPEG or PNG")
        max_frame_bytes = 20 * 1024 * 1024
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            if not chunk:
                continue
            total += len(chunk)
            if total > max_frame_bytes:
                raise HTTPException(status_code=413, detail="Live frame exceeds 20 MB")
            chunks.append(chunk)
        frame_bytes = b"".join(chunks)
        if not frame_bytes:
            raise HTTPException(status_code=400, detail="Live frame is empty")
        parameters = {
            "captured_at": request.headers.get("x-captured-at") or datetime.now(timezone.utc).isoformat(),
            "sequence": request.headers.get("x-frame-sequence"),
            "timestamp_sec": request.headers.get("x-source-timestamp-sec"),
            "segmentation_model_id": request.headers.get("x-segmentation-model-id"),
            "threshold": request.headers.get("x-hotspot-threshold"),
            "colormap": request.headers.get("x-colormap"),
        }
        filename = request.headers.get("x-filename") or "live_frame.jpg"
        try:
            return await asyncio.to_thread(
                service.analyze,
                case_id=case_id,
                frame_bytes=frame_bytes,
                filename=filename,
                parameters=parameters,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            # Keep model/config paths and dependency details out of the HTTP response.
            raise HTTPException(status_code=500, detail="Live frame analysis failed; check server logs.") from exc

    @api.post("/live-frames/warmup")
    async def warmup_live_frame_model(request: Request) -> dict[str, Any]:
        payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(payload, dict):
            payload = {}
        model_id = str(payload.get("model_id") or "").strip() or None
        try:
            return await asyncio.to_thread(service.warmup, model_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Live frame model warmup unavailable; check server logs."
            ) from exc

    return api
