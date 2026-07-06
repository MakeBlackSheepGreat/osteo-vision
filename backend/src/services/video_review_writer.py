from __future__ import annotations

from pathlib import Path
from typing import Any


def review_video_fps(value: Any) -> float:
    try:
        fps = float(value)
    except (TypeError, ValueError):
        return 2.0
    if fps <= 0:
        return 2.0
    return min(8.0, max(1.0, fps))


def write_image_sequence_video(paths: list[str], output_path: Path, *, fps: float, max_side: int = 1280) -> str | None:
    """把关键帧 overlay/mask 串成复核 MP4，便于前端按视频流方式演示分割结果。"""

    existing = [Path(path) for path in paths if path and Path(path).exists()]
    if not existing:
        return None
    try:
        import cv2
    except Exception:
        return None
    first = cv2.imread(str(existing[0]), cv2.IMREAD_COLOR)
    if first is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_width, target_height = _review_video_size(first.shape[1], first.shape[0], max_side=max_side)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        max(0.5, float(fps)),
        (target_width, target_height),
    )
    if not writer.isOpened():
        return None
    try:
        for path in existing:
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            writer.write(frame)
    finally:
        writer.release()
    return str(output_path) if output_path.exists() else None


def _review_video_size(width: int, height: int, *, max_side: int) -> tuple[int, int]:
    width = max(2, int(width))
    height = max(2, int(height))
    longest = max(width, height)
    if longest <= max_side:
        return _even(width), _even(height)
    scale = float(max_side) / float(longest)
    return _even(max(2, round(width * scale))), _even(max(2, round(height * scale)))


def _even(value: int) -> int:
    return int(value) if int(value) % 2 == 0 else int(value) - 1
