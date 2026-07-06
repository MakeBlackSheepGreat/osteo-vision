from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.preprocess.video import extract_keyframes


def keyframe_report_for_analysis(
    source_path: Any,
    output_dir: Any,
    *,
    max_frames: int,
    sampling_strategy: str,
    requested_frame_indexes: list[int],
    requested_timestamps_sec: list[float],
) -> dict[str, Any]:
    if requested_frame_indexes or requested_timestamps_sec:
        return extract_keyframes(
            source_path,
            output_dir,
            max_frames=max_frames,
            sampling_strategy="manual",
            requested_frame_indexes=requested_frame_indexes,
            requested_timestamps_sec=requested_timestamps_sec,
        )
    reusable = _load_reusable_upload_keyframes(source_path, max_frames=max_frames, sampling_strategy=sampling_strategy)
    if reusable is not None:
        return reusable
    return extract_keyframes(
        source_path,
        output_dir,
        max_frames=max_frames,
        sampling_strategy=sampling_strategy,
    )


def numeric_sequence(value: Any, *, cast_type: type[int] | type[float]) -> list[Any]:
    raw_items = value if isinstance(value, list) else [value] if value is not None else []
    parsed: list[Any] = []
    for item in raw_items:
        try:
            parsed.append(cast_type(item))
        except (TypeError, ValueError):
            continue
    return parsed


def _load_reusable_upload_keyframes(
    source_path: Any,
    *,
    max_frames: int,
    sampling_strategy: str,
) -> dict[str, Any] | None:
    # 上传阶段已预抽帧时，分析阶段优先复用 manifest，避免同一 MP4 重复解码。
    source = Path(str(source_path))
    manifest_path = source.parent / "keyframes" / source.stem / "keyframe_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload_source = payload.get("source_path")
    if not payload_source or Path(str(payload_source)).resolve() != source.resolve():
        return None
    payload_strategy = str(payload.get("sampling_strategy") or payload.get("sampling") or "").lower()
    if payload_strategy != sampling_strategy.lower().strip():
        return None
    keyframes = [frame for frame in payload.get("keyframes") or [] if isinstance(frame, dict)]
    requested_count = max(1, int(max_frames))
    if len(keyframes) < requested_count:
        return None
    selected_keyframes = keyframes[:requested_count]
    if not _keyframe_paths_exist(selected_keyframes):
        return None
    selection_trace = dict(payload.get("selection_trace") or {})
    selection_trace.update(
        {
            "selected_indexes": [frame.get("frame_index") for frame in selected_keyframes],
            "reused_from_manifest": str(manifest_path),
        }
    )
    quality_summary = dict(payload.get("quality_summary") or {})
    quality_summary.update({"frames_saved": len(selected_keyframes), "reused_from_upload_preextract": True})
    frame_index_manifest_path = payload.get("frame_index_manifest_path")
    if not frame_index_manifest_path:
        sibling_frame_index_manifest = manifest_path.with_name("frame_index_manifest.json")
        if sibling_frame_index_manifest.exists():
            frame_index_manifest_path = str(sibling_frame_index_manifest)
    timeline_manifest_path = payload.get("timeline_manifest_path")
    if not timeline_manifest_path:
        sibling_timeline_manifest = manifest_path.with_name("timeline_manifest.json")
        if sibling_timeline_manifest.exists():
            timeline_manifest_path = str(sibling_timeline_manifest)
    return {
        **payload,
        "keyframes": selected_keyframes,
        "selection_trace": selection_trace,
        "quality_summary": quality_summary,
        "report_source": "reused_upload_preextract",
        "source_manifest_path": str(manifest_path),
        "keyframe_manifest_path": str(manifest_path),
        "frame_index_manifest_path": frame_index_manifest_path,
        "timeline_manifest_path": timeline_manifest_path,
    }


def _keyframe_paths_exist(keyframes: list[dict[str, Any]]) -> bool:
    for frame in keyframes:
        path = frame.get("evidence_path") or frame.get("path")
        if not path or not Path(str(path)).exists():
            return False
    return True
