from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import cv2

from src.core.warnings import warning


@dataclass(frozen=True)
class LiveStreamCaptureConfig:
    """Bounded capture settings for camera, network and local video sources."""

    max_keyframes: int = 5
    keyframe_stride: int = 1
    queue_size: int = 8
    open_timeout_sec: float = 5.0
    read_timeout_sec: float = 2.0
    capture_timeout_sec: float = 15.0
    jpeg_quality: int = 92

    def validated(self) -> LiveStreamCaptureConfig:
        if self.max_keyframes <= 0:
            raise ValueError("max_keyframes must be positive")
        if self.keyframe_stride <= 0:
            raise ValueError("keyframe_stride must be positive")
        if self.queue_size <= 0:
            raise ValueError("queue_size must be positive")
        if self.open_timeout_sec <= 0:
            raise ValueError("open_timeout_sec must be positive")
        if self.read_timeout_sec <= 0:
            raise ValueError("read_timeout_sec must be positive")
        if self.capture_timeout_sec <= 0:
            raise ValueError("capture_timeout_sec must be positive")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        return self


@dataclass(frozen=True)
class _ResolvedSource:
    value: int | str
    kind: str
    display_uri: str


@dataclass(frozen=True)
class _FramePacket:
    frame_index: int
    capture_timestamp: str
    captured_monotonic: float
    frame: Any


@dataclass
class _ReaderState:
    frames_read: int = 0
    frames_dropped: int = 0
    ended: bool = False
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_read(self) -> int:
        with self.lock:
            frame_index = self.frames_read
            self.frames_read += 1
            return frame_index

    def record_drop(self) -> None:
        with self.lock:
            self.frames_dropped += 1

    def finish(self, error: str | None = None) -> None:
        with self.lock:
            self.ended = True
            self.error = error

    def snapshot(self) -> tuple[int, int, bool, str | None]:
        with self.lock:
            return self.frames_read, self.frames_dropped, self.ended, self.error


def capture_live_keyframes(
    source_uri: str,
    output_dir: str | Path,
    *,
    config: LiveStreamCaptureConfig | None = None,
) -> dict[str, Any]:
    """Capture a finite JPEG keyframe set through a bounded background reader."""

    settings = (config or LiveStreamCaptureConfig()).validated()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    frame_index_manifest_path = target_dir / "frame_index_manifest.json"
    started_at = _utc_timestamp()
    base_report: dict[str, Any] = {
        "schema_version": "osteo-vision-live-stream-capture-v1",
        "source_uri": source_uri,
        "capture_backend": "opencv",
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "frames_read": 0,
        "frames_dropped": 0,
        "started_at": started_at,
        "ended_at": started_at,
        "keyframes": [],
        "quality_summary": _quality_summary([], queue_delay_limit_sec=settings.read_timeout_sec),
        "frame_index_manifest_path": str(frame_index_manifest_path),
        "warnings": [],
    }

    try:
        resolved = _resolve_source(source_uri)
    except ValueError as exc:
        code = (
            "browser_camera_source_rejected" if source_uri.startswith("camera://browser") else "capture_source_invalid"
        )
        base_report["warnings"] = [warning(code, str(exc), True, source_uri=source_uri)]
        base_report["ended_at"] = _utc_timestamp()
        return _finalize_report(base_report)

    capture: Any | None = None
    stop_event = threading.Event()
    reader: threading.Thread | None = None
    try:
        capture, open_timed_out = _open_capture(resolved.value, settings=settings)
        if capture is None:
            code = "capture_open_timeout" if open_timed_out else "capture_open_failed"
            message = (
                "OpenCV did not finish opening the configured video source within the timeout."
                if open_timed_out
                else "OpenCV could not open the configured video source."
            )
            base_report["warnings"] = [
                warning(
                    code,
                    message,
                    True,
                    source_uri=source_uri,
                    source_kind=resolved.kind,
                    open_timeout_sec=settings.open_timeout_sec,
                )
            ]
            return _finalize_report(base_report)

        base_report.update(
            {
                "capture_backend": _capture_backend_name(capture),
                "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
                "fps": float(capture.get(cv2.CAP_PROP_FPS) or 0.0),
                "source_kind": resolved.kind,
            }
        )
        frame_queue: queue.Queue[_FramePacket] = queue.Queue(maxsize=settings.queue_size)
        state = _ReaderState()
        reader = threading.Thread(
            target=_capture_reader,
            args=(capture, frame_queue, state, stop_event),
            name="osteo-vision-live-capture",
            daemon=True,
        )
        reader.start()

        capture_started_monotonic = time.monotonic()
        deadline = capture_started_monotonic + settings.capture_timeout_sec
        last_frame_at = capture_started_monotonic
        selected: list[dict[str, Any]] = []
        while len(selected) < settings.max_keyframes:
            now = time.monotonic()
            if now >= deadline:
                base_report["warnings"].append(
                    warning(
                        "capture_timeout",
                        "Live capture reached its configured duration limit.",
                        False,
                        capture_timeout_sec=settings.capture_timeout_sec,
                    )
                )
                break
            wait_for = min(settings.read_timeout_sec, max(0.001, deadline - now))
            try:
                packet = frame_queue.get(timeout=wait_for)
            except queue.Empty:
                frames_read, _, ended, reader_error = state.snapshot()
                if ended:
                    _append_end_warning(
                        base_report["warnings"],
                        source_kind=resolved.kind,
                        frames_read=frames_read,
                        reader_error=reader_error,
                    )
                    break
                if time.monotonic() - last_frame_at >= settings.read_timeout_sec:
                    base_report["warnings"].append(
                        warning(
                            "capture_read_timeout",
                            "No frame arrived within the configured read timeout.",
                            True,
                            read_timeout_sec=settings.read_timeout_sec,
                        )
                    )
                    break
                continue

            last_frame_at = time.monotonic()
            if packet.frame_index % settings.keyframe_stride != 0:
                continue
            selected.append(
                _write_keyframe(
                    packet,
                    target_dir=target_dir,
                    order=len(selected) + 1,
                    jpeg_quality=settings.jpeg_quality,
                    capture_started_monotonic=capture_started_monotonic,
                    fps=float(base_report["fps"]),
                )
            )

        stop_event.set()
        capture.release()
        reader.join(timeout=max(0.05, min(settings.read_timeout_sec, 1.0)))
        if reader.is_alive():
            base_report["warnings"].append(
                warning(
                    "capture_reader_shutdown_timeout",
                    "The background capture reader did not stop within the shutdown timeout.",
                    True,
                )
            )
        frames_read, frames_dropped, _, reader_error = state.snapshot()
        if reader_error:
            base_report["warnings"].append(
                warning(
                    "capture_reader_failed",
                    "The background capture reader stopped after an exception.",
                    True,
                    error=reader_error,
                )
            )
        base_report.update(
            {
                "frames_read": frames_read,
                "frames_dropped": frames_dropped,
                "keyframes": selected,
                "quality_summary": _quality_summary(selected, queue_delay_limit_sec=settings.read_timeout_sec),
            }
        )
        return _finalize_report(base_report)
    finally:
        stop_event.set()
        if capture is not None:
            capture.release()
        if reader is not None:
            reader.join(timeout=max(0.05, min(settings.read_timeout_sec, 1.0)))


def _open_capture(
    source: int | str,
    *,
    settings: LiveStreamCaptureConfig,
) -> tuple[Any | None, bool]:
    result_queue: queue.Queue[tuple[Any | None, bool]] = queue.Queue(maxsize=1)
    cancelled = threading.Event()

    def worker() -> None:
        candidate = cv2.VideoCapture()
        _set_capture_timeout(candidate, "CAP_PROP_OPEN_TIMEOUT_MSEC", settings.open_timeout_sec)
        _set_capture_timeout(candidate, "CAP_PROP_READ_TIMEOUT_MSEC", settings.read_timeout_sec)
        opened = False
        try:
            opened = bool(candidate.open(source)) and bool(candidate.isOpened())
        except Exception:
            opened = False
        if cancelled.is_set():
            candidate.release()
            return
        try:
            result_queue.put_nowait((candidate if opened else None, opened))
        except queue.Full:  # pragma: no cover - defensive ownership handoff
            candidate.release()
            return
        if not opened:
            candidate.release()

    opener = threading.Thread(target=worker, name="osteo-vision-capture-open", daemon=True)
    opener.start()
    try:
        capture, opened = result_queue.get(timeout=settings.open_timeout_sec)
    except queue.Empty:
        cancelled.set()
        return None, True
    return (capture if opened else None), False


def _capture_reader(
    capture: Any,
    frame_queue: queue.Queue[_FramePacket],
    state: _ReaderState,
    stop_event: threading.Event,
) -> None:
    error: str | None = None
    try:
        while not stop_event.is_set():
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            frame_index = state.record_read()
            packet = _FramePacket(
                frame_index=frame_index,
                capture_timestamp=_utc_timestamp(),
                captured_monotonic=time.monotonic(),
                frame=frame,
            )
            try:
                frame_queue.put_nowait(packet)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
                else:
                    state.record_drop()
                try:
                    frame_queue.put_nowait(packet)
                except queue.Full:
                    state.record_drop()
    except Exception as exc:  # pragma: no cover - backend-specific failures
        error = str(exc)
    finally:
        state.finish(error)


def _resolve_source(source_uri: str) -> _ResolvedSource:
    value = source_uri.strip()
    if not value:
        raise ValueError("Video source URI is empty.")
    if value.startswith("camera://browser"):
        raise ValueError(
            "Browser camera URIs require browser-to-backend frame transport and cannot be opened by OpenCV."
        )
    if value.startswith("camera://opencv/"):
        index_text = value.removeprefix("camera://opencv/")
        if not index_text.isdigit():
            raise ValueError("OpenCV camera URI must end with a non-negative integer index.")
        return _ResolvedSource(value=int(index_text), kind="opencv_camera", display_uri=value)

    parsed = urlparse(value)
    if parsed.scheme.lower() in {"rtsp", "http", "https"}:
        return _ResolvedSource(value=value, kind="network_stream", display_uri=value)
    if parsed.scheme.lower() == "file":
        file_path = Path(unquote(parsed.path.lstrip("/"))) if parsed.netloc else Path(unquote(parsed.path))
        if parsed.netloc:
            file_path = Path(f"//{parsed.netloc}/{file_path}")
        return _resolve_local_path(file_path, value)

    return _resolve_local_path(Path(value).expanduser(), value)


def _resolve_local_path(path: Path, display_uri: str) -> _ResolvedSource:
    if not path.is_file():
        raise ValueError("Local video source does not exist or is not a readable file.")
    return _ResolvedSource(value=str(path.resolve()), kind="local_video", display_uri=display_uri)


def _set_capture_timeout(capture: Any, property_name: str, seconds: float) -> None:
    property_id = getattr(cv2, property_name, None)
    if property_id is None:
        return
    try:
        capture.set(property_id, int(seconds * 1000))
    except Exception:
        return


def _capture_backend_name(capture: Any) -> str:
    try:
        backend = str(capture.getBackendName()).strip()
    except Exception:
        backend = ""
    return f"opencv:{backend.lower()}" if backend else "opencv:auto"


def _write_keyframe(
    packet: _FramePacket,
    *,
    target_dir: Path,
    order: int,
    jpeg_quality: int,
    capture_started_monotonic: float,
    fps: float,
) -> dict[str, Any]:
    output_path = target_dir / f"live_keyframe_{order:03d}_f{packet.frame_index:08d}.jpg"
    saved = cv2.imwrite(str(output_path), packet.frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not saved:
        raise OSError(f"OpenCV failed to write keyframe: {output_path}")
    frame_age_ms = max(0.0, (time.monotonic() - packet.captured_monotonic) * 1000.0)
    relative_timestamp_sec = max(0.0, packet.captured_monotonic - capture_started_monotonic)
    if relative_timestamp_sec == 0.0 and fps > 0:
        relative_timestamp_sec = packet.frame_index / fps
    return {
        "order": order,
        "path": str(output_path),
        "evidence_path": str(output_path),
        "frame_index": packet.frame_index,
        "timestamp_sec": round(relative_timestamp_sec, 6),
        "capture_timestamp": packet.capture_timestamp,
        "frame_age_ms": round(frame_age_ms, 3),
        "selection_reason": "live_stream_stride",
        "width": int(packet.frame.shape[1]),
        "height": int(packet.frame.shape[0]),
    }


def _append_end_warning(
    warnings: list[dict[str, Any]],
    *,
    source_kind: str,
    frames_read: int,
    reader_error: str | None,
) -> None:
    if reader_error:
        warnings.append(
            warning(
                "capture_reader_failed",
                "The background capture reader stopped after an exception.",
                True,
                error=reader_error,
            )
        )
        return
    if source_kind == "local_video" and frames_read > 0:
        warnings.append(
            warning(
                "capture_end_of_stream",
                "The local video source reached its final readable frame.",
                False,
            )
        )
        return
    warnings.append(
        warning(
            "capture_stream_disconnected",
            "The camera or network stream stopped returning frames.",
            True,
        )
    )


def _quality_summary(keyframes: list[dict[str, Any]], *, queue_delay_limit_sec: float) -> dict[str, Any]:
    ages = [float(item["frame_age_ms"]) for item in keyframes if item.get("frame_age_ms") is not None]
    queue_delay_limit_ms = queue_delay_limit_sec * 1000.0
    return {
        "frames_saved": len(keyframes),
        "frame_age_ms_mean": round(sum(ages) / len(ages), 3) if ages else None,
        "frame_age_ms_max": round(max(ages), 3) if ages else None,
        "capture_queue_delay_limit_ms": round(queue_delay_limit_ms, 3),
        "capture_queue_delayed_frame_count": sum(age > queue_delay_limit_ms for age in ages),
        "source_pts_available": False,
        "source_buffer_age_verified": False,
    }


def _finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    report["ended_at"] = _utc_timestamp()
    report["keyframe_count"] = len(report.get("keyframes") or [])
    manifest_path = Path(str(report["frame_index_manifest_path"]))
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
