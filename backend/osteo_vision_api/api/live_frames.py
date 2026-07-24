from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timezone
from threading import Event
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.requests import ClientDisconnect

from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.services.live_frame_service import (
    LiveFrameAdmission,
    LiveFrameAnalysisService,
    LiveFrameCancelledError,
    LiveFrameCapacityError,
    LiveFrameInputError,
)

MAX_LIVE_FRAME_BYTES = 20 * 1024 * 1024
MAX_WARMUP_BODY_BYTES = 4096
MAX_LIVE_FRAME_UPLOAD_SECONDS = 30.0


def router(repo: CaseRepository, service: LiveFrameAnalysisService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/live-frames")
    async def analyze_live_frame(case_id: str, request: Request) -> dict[str, Any]:
        if repo.get(case_id) is None:
            raise HTTPException(status_code=404, detail="Case not found")
        content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if content_type not in {"image/jpeg", "image/jpg", "image/png", "application/octet-stream"}:
            raise HTTPException(status_code=415, detail="Live frame must be JPEG or PNG")
        content_length = _content_length(request)
        if content_length is not None and content_length > MAX_LIVE_FRAME_BYTES:
            raise HTTPException(status_code=413, detail="Live frame exceeds 20 MB")
        admission: LiveFrameAdmission | None = None
        worker_submitted = False
        request_cancelled = False
        cancel_event = Event()
        try:
            # Reserve capacity before accepting the potentially large request body.
            admission = service.acquire_admission(wait=False)
            try:
                async with asyncio.timeout(MAX_LIVE_FRAME_UPLOAD_SECONDS):
                    frame_bytes = await _read_bounded_body(request, MAX_LIVE_FRAME_BYTES)
            except TimeoutError as exc:
                raise HTTPException(status_code=408, detail="Live frame upload timed out") from exc
            if not frame_bytes:
                raise HTTPException(status_code=400, detail="Live frame is empty")
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="Live frame request was cancelled")
            parameters = {
                "captured_at": request.headers.get("x-captured-at") or datetime.now(timezone.utc).isoformat(),
                "sequence": request.headers.get("x-frame-sequence"),
                "timestamp_sec": request.headers.get("x-source-timestamp-sec"),
                "segmentation_model_id": request.headers.get("x-segmentation-model-id"),
                "threshold": request.headers.get("x-hotspot-threshold"),
                "colormap": request.headers.get("x-colormap"),
            }
            filename = request.headers.get("x-filename") or "live_frame.jpg"
            analysis_task = asyncio.create_task(
                asyncio.to_thread(
                    service.analyze,
                    case_id=case_id,
                    frame_bytes=frame_bytes,
                    filename=filename,
                    parameters=parameters,
                    cancel_event=cancel_event,
                    admission=admission,
                )
            )
            analysis_task.add_done_callback(_consume_task_exception)
            worker_submitted = True
            return await _await_analysis_or_disconnect(request, analysis_task, cancel_event)
        except HTTPException:
            raise
        except ClientDisconnect as exc:
            request_cancelled = worker_submitted
            cancel_event.set()
            raise HTTPException(status_code=499, detail="Live frame request was cancelled") from exc
        except asyncio.CancelledError:
            request_cancelled = worker_submitted
            cancel_event.set()
            raise
        except LiveFrameCapacityError as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "live_frame_capacity_exceeded",
                    "message": "Live frame inference is busy; retry after the active frame completes.",
                    "max_concurrent": exc.max_concurrent,
                    "waited_ms": exc.waited_ms,
                },
                headers={"Retry-After": "1"},
            ) from exc
        except LiveFrameCancelledError as exc:
            raise HTTPException(status_code=499, detail="Live frame analysis was cancelled") from exc
        except LiveFrameInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=503, detail="Live frame configuration is unavailable; check server logs."
            ) from exc
        except Exception as exc:
            # Keep model/config paths and dependency details out of the HTTP response.
            raise HTTPException(status_code=500, detail="Live frame analysis failed; check server logs.") from exc
        finally:
            if admission is not None and not request_cancelled:
                admission.release()

    @api.post("/live-frames/warmup")
    async def warmup_live_frame_model(request: Request) -> dict[str, Any]:
        content_length = _content_length(request)
        if content_length is not None and content_length > MAX_WARMUP_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Warmup request exceeds 4096 bytes")
        try:
            body = await _read_bounded_body(request, MAX_WARMUP_BODY_BYTES)
        except ClientDisconnect as exc:
            raise HTTPException(status_code=499, detail="Warmup request was cancelled") from exc
        if not body:
            payload: Any = {}
        elif request.headers.get("content-type", "").lower().startswith("application/json"):
            try:
                payload = json.loads(body)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="Warmup request JSON is invalid") from exc
        else:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        model_id = str(payload.get("model_id") or "").strip() or None
        try:
            return await asyncio.to_thread(service.warmup, model_id)
        except LiveFrameCapacityError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "live_frame_warmup_capacity_exceeded",
                    "message": "Live frame model is currently serving inference; retry warmup later.",
                    "max_concurrent": exc.max_concurrent,
                    "waited_ms": exc.waited_ms,
                },
                headers={"Retry-After": "1"},
            ) from exc
        except LiveFrameInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=503, detail="Live frame model configuration is unavailable; check server logs."
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Live frame model warmup unavailable; check server logs."
            ) from exc

    return api


def _content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header") from None
    if parsed < 0:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header")
    return parsed


async def _read_bounded_body(request: Request, limit: int) -> bytes:
    buffer = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(buffer) + len(chunk) > limit:
            raise HTTPException(status_code=413, detail=f"Request body exceeds {limit} bytes")
        buffer.extend(chunk)
    return bytes(buffer)


async def _await_analysis_or_disconnect(
    request: Request,
    analysis_task: asyncio.Task[dict[str, Any]],
    cancel_event: Event,
) -> dict[str, Any]:
    disconnect_task = asyncio.create_task(_wait_for_disconnect(request))
    try:
        completed, _pending = await asyncio.wait(
            {analysis_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if analysis_task in completed:
            return await analysis_task
        cancel_event.set()
        raise ClientDisconnect()
    finally:
        if not disconnect_task.done():
            disconnect_task.cancel()
        with suppress(asyncio.CancelledError):
            await disconnect_task


async def _wait_for_disconnect(request: Request) -> None:
    while True:
        message = await request.receive()
        if message.get("type") == "http.disconnect":
            return
        await asyncio.sleep(0)


def _consume_task_exception(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        return
