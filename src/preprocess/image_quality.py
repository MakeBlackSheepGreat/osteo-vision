from __future__ import annotations

from pathlib import Path


def assess_basic_quality(path: str | Path, input_type: str) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, "path does not exist"
    if p.is_file() and p.stat().st_size == 0:
        return False, "file is empty"
    if input_type == "unknown":
        return False, "unsupported input type"
    if input_type == "video_file":
        return _assess_video_quality(p)
    return True, ""


def _assess_video_quality(path: Path) -> tuple[bool, str]:
    try:
        import cv2
    except Exception as exc:
        return False, f"OpenCV is unavailable for video validation: {exc}"

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return False, "video capture could not be opened"
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        ok, frame = capture.read()
        if width <= 0 or height <= 0:
            return False, "video has invalid dimensions"
        if frame_count <= 0:
            return False, "video has no readable frame count"
        if not ok or frame is None:
            return False, "video has no decodable frames"
    finally:
        capture.release()
    return True, ""
