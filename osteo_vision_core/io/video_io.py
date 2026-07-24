from __future__ import annotations

from pathlib import Path
from typing import Any

from osteo_vision_core.core.executables import find_runtime_executable
from osteo_vision_core.io.content_probe import probe_file_signature
from osteo_vision_core.io.official_device_quality import assess_official_video_profile

VIDEO_EXTENSIONS = {".mp4"}


def is_video_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def video_metadata(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    meta: dict[str, Any] = {
        "path": str(p),
        "extension": p.suffix.lower(),
        "content_probe": probe_file_signature(p),
    }
    capture = None
    try:
        import cv2

        capture = cv2.VideoCapture(str(p))
        if not capture.isOpened():
            return {**meta, "video_probe_error": "video capture could not be opened"}
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()
        duration_sec = frame_count / fps if fps > 0 and frame_count > 0 else None
        meta.update(
            {
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "duration_sec": duration_sec,
                "readable": bool(width > 0 and height > 0 and frame_count > 0),
                "validation_backend": "opencv",
                "ffprobe": _ffprobe_metadata(p),
            }
        )
        official_profile, quality_warnings = assess_official_video_profile(meta)
        meta.update(
            {
                "official_target_resolution": "3840x2160",
                "official_container": "mp4",
                "official_input_profile": official_profile,
                "official_resolution_match": official_profile["resolution_match"],
                "quality_warnings": quality_warnings,
            }
        )
    except Exception as exc:
        meta.update({"video_probe_error": str(exc)})
    finally:
        if capture is not None:
            capture.release()
    return meta


def _ffprobe_metadata(path: Path) -> dict[str, Any]:
    import json
    import subprocess

    executable = find_runtime_executable("ffprobe")
    if executable is None:
        return {"available": False}
    command = [
        executable,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return {"available": True, "error": str(exc)}
    if completed.returncode != 0:
        return {"available": True, "error": completed.stderr.strip() or "ffprobe failed"}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"available": True, "error": f"ffprobe JSON parse failed: {exc}"}
    streams = payload.get("streams") if isinstance(payload, dict) else None
    stream = _first_video_stream(streams)
    fmt = payload.get("format") if isinstance(payload, dict) else {}
    return {
        "available": True,
        "stream": stream if isinstance(stream, dict) else {},
        "format": fmt if isinstance(fmt, dict) else {},
    }


def _first_video_stream(streams: Any) -> dict[str, Any]:
    if not isinstance(streams, list):
        return {}
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream
    first = streams[0] if streams else {}
    return first if isinstance(first, dict) else {}
