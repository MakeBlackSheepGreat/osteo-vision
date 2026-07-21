from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np


def extract_keyframes(
    video_path: str | Path,
    output_dir: str | Path,
    *,
    max_frames: int = 5,
    sampling_strategy: str = "quality_peak",
    candidate_pool_size: int | None = None,
    min_frame_gap: int | None = None,
    requested_frame_indexes: Sequence[int] | None = None,
    requested_timestamps_sec: Sequence[float] | None = None,
    max_preview_side: int = 1280,
    max_timeline_entries: int = 5000,
    preview_jpeg_quality: int = 90,
    evidence_jpeg_quality: int = 96,
    deduplicate_similar_frames: bool = True,
    duplicate_similarity_threshold: float = 0.985,
    quality_evaluation_max_side: int | None = None,
) -> dict[str, Any]:
    """Extract deterministic preview and evidence keyframes from an MP4 file.

    The competition-facing path needs representative frame evidence without
    decoding long 4K videos end to end. The default strategy probes a bounded
    uniform candidate pool, scores frame quality plus fluorescence-like signal,
    then stores the best temporally separated frames.
    """

    import cv2

    source = Path(video_path)
    target_dir = Path(output_dir)
    preview_dir = target_dir / "preview"
    evidence_dir = target_dir / "evidence"
    preview_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        return {
            "source_path": str(source),
            "keyframes": [],
            "warnings": [{"code": "video_open_failed", "message": "Video file could not be opened.", "blocking": True}],
        }

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if frame_count <= 0:
        capture.release()
        return {
            "source_path": str(source),
            "keyframes": [],
            "warnings": [
                {"code": "video_empty_or_unindexed", "message": "Video has no readable frame count.", "blocking": True}
            ],
        }

    sample_count = max(1, min(max_frames, frame_count))
    requested_indexes = _requested_indexes(
        frame_count=frame_count,
        fps=fps,
        requested_frame_indexes=requested_frame_indexes,
        requested_timestamps_sec=requested_timestamps_sec,
    )
    strategy = "manual" if requested_indexes else sampling_strategy.lower().strip() or "quality_peak"
    if strategy not in {"quality_peak", "uniform", "manual"}:
        strategy = "quality_peak"
    if strategy == "manual":
        indexes = requested_indexes[:sample_count]
        selection_trace = {
            index: {"selection_score": None, "selection_rank": rank, "selection_source": "manual_request"}
            for rank, index in enumerate(indexes, 1)
        }
    else:
        indexes, selection_trace = _select_frame_indexes(
            capture,
            frame_count=frame_count,
            sample_count=sample_count,
            strategy=strategy,
            candidate_pool_size=candidate_pool_size,
            min_frame_gap=min_frame_gap,
            deduplicate_similar_frames=deduplicate_similar_frames,
            duplicate_similarity_threshold=duplicate_similarity_threshold,
            quality_evaluation_max_side=quality_evaluation_max_side,
        )

    keyframes: list[dict[str, Any]] = []
    for order, frame_index in enumerate(indexes, start=1):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        quality = _frame_quality(frame, max_evaluation_side=quality_evaluation_max_side)
        trace_item = selection_trace.get(int(frame_index), {})
        evidence_path = evidence_dir / f"keyframe_{order:02d}_f{int(frame_index):06d}_evidence.jpg"
        preview = _resize_for_preview(frame, max_preview_side=max_preview_side)
        preview_path = preview_dir / f"keyframe_{order:02d}_f{int(frame_index):06d}_preview.jpg"
        cv2.imwrite(str(evidence_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), evidence_jpeg_quality])
        cv2.imwrite(str(preview_path), preview, [int(cv2.IMWRITE_JPEG_QUALITY), preview_jpeg_quality])
        keyframes.append(
            {
                "order": order,
                "frame_index": int(frame_index),
                "timestamp_sec": float(frame_index / fps) if fps > 0 else None,
                "path": str(preview_path),
                "preview_path": str(preview_path),
                "evidence_path": str(evidence_path),
                "preview_width": int(preview.shape[1]),
                "preview_height": int(preview.shape[0]),
                "evidence_width": int(frame.shape[1]),
                "evidence_height": int(frame.shape[0]),
                "selection_score": trace_item.get("selection_score"),
                "selection_rank": trace_item.get("selection_rank"),
                "selection_source": trace_item.get("selection_source", strategy),
                "duplicate_group": trace_item.get("duplicate_group"),
                "duplicate_of_frame_index": trace_item.get("duplicate_of_frame_index"),
                "duplicate_similarity": trace_item.get("duplicate_similarity"),
                "quality": quality,
            }
        )

    capture.release()
    candidate_trace = _candidate_trace(selection_trace)
    report = {
        "source_path": str(source),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": float(frame_count / fps) if fps > 0 else None,
        "max_timeline_entries": max_timeline_entries,
        "sampling": strategy,
        "sampling_strategy": strategy,
        "quality_evaluation": _quality_evaluation_metadata(
            source_width=width,
            source_height=height,
            max_evaluation_side=quality_evaluation_max_side,
        ),
        "selection_trace": {
            "candidate_frame_count": len(selection_trace),
            "candidate_pool_size": candidate_pool_size,
            "min_frame_gap": min_frame_gap,
            "selected_indexes": indexes,
            "requested_frame_indexes": list(requested_frame_indexes or []),
            "requested_timestamps_sec": list(requested_timestamps_sec or []),
            "manual_selection_applied": strategy == "manual",
            "deduplication": {
                **_deduplication_summary(selection_trace, strategy=strategy),
                "enabled": strategy == "quality_peak" and deduplicate_similar_frames,
                "similarity_threshold": duplicate_similarity_threshold,
            },
            "candidates": candidate_trace,
        },
        "keyframes": keyframes,
        "quality_summary": _quality_summary(keyframes),
        "warnings": [],
    }
    return _write_keyframe_manifest(report, target_dir)


def _write_keyframe_manifest(report: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    manifest_path = target_dir / "keyframe_manifest.json"
    frame_index_manifest_path = target_dir / "frame_index_manifest.json"
    timeline_manifest_path = target_dir / "timeline_manifest.json"
    report = {
        **report,
        "schema_version": "osteo-vision-keyframe-manifest-v1",
        "keyframe_manifest_path": str(manifest_path),
        "frame_index_manifest_path": str(frame_index_manifest_path),
        "timeline_manifest_path": str(timeline_manifest_path),
    }
    frame_index_manifest_path.write_text(
        json.dumps(_frame_index_manifest(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    timeline_manifest_path.write_text(
        json.dumps(_timeline_manifest(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _requested_indexes(
    *,
    frame_count: int,
    fps: float,
    requested_frame_indexes: Sequence[int] | None,
    requested_timestamps_sec: Sequence[float] | None,
) -> list[int]:
    indexes: list[int] = []
    for value in requested_frame_indexes or []:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        indexes.append(index)
    if fps > 0:
        for timestamp in requested_timestamps_sec or []:
            try:
                seconds = float(timestamp)
            except (TypeError, ValueError):
                continue
            indexes.append(round(seconds * fps))
    clipped: list[int] = []
    seen: set[int] = set()
    for index in indexes:
        clipped_index = max(0, min(frame_count - 1, int(index)))
        if clipped_index in seen:
            continue
        seen.add(clipped_index)
        clipped.append(clipped_index)
    return clipped


def _frame_index_manifest(report: dict[str, Any]) -> dict[str, Any]:
    frames = []
    for frame in report.get("keyframes") or []:
        if not isinstance(frame, dict):
            continue
        frames.append(
            {
                "order": frame.get("order"),
                "frame_index": frame.get("frame_index"),
                "timestamp_sec": frame.get("timestamp_sec"),
                "path": frame.get("path"),
                "preview_path": frame.get("preview_path"),
                "evidence_path": frame.get("evidence_path"),
                "preview_width": frame.get("preview_width"),
                "preview_height": frame.get("preview_height"),
                "evidence_width": frame.get("evidence_width"),
                "evidence_height": frame.get("evidence_height"),
                "selection_score": frame.get("selection_score"),
                "selection_rank": frame.get("selection_rank"),
                "selection_source": frame.get("selection_source"),
                "duplicate_group": frame.get("duplicate_group"),
                "duplicate_of_frame_index": frame.get("duplicate_of_frame_index"),
                "duplicate_similarity": frame.get("duplicate_similarity"),
                "quality": frame.get("quality", {}),
            }
        )
    return {
        "schema_version": "osteo-vision-frame-index-manifest-v1",
        "frame_index_scope": "selected_keyframes_with_candidate_trace",
        "timeline_manifest_path": report.get("timeline_manifest_path"),
        "source_path": report.get("source_path"),
        "width": report.get("width"),
        "height": report.get("height"),
        "fps": report.get("fps"),
        "frame_count": report.get("frame_count"),
        "duration_sec": report.get("duration_sec"),
        "sampling": report.get("sampling"),
        "sampling_strategy": report.get("sampling_strategy"),
        "keyframe_manifest_path": report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": report.get("frame_index_manifest_path"),
        "selection_trace": report.get("selection_trace", {}),
        "quality_evaluation": report.get("quality_evaluation", {}),
        "deduplication": report.get("selection_trace", {}).get("deduplication", {}),
        "candidate_frame_count": len(report.get("selection_trace", {}).get("candidates", [])),
        "candidate_frames": report.get("selection_trace", {}).get("candidates", []),
        "quality_summary": report.get("quality_summary", {}),
        "selected_frame_count": len(frames),
        "frames": frames,
        "warnings": report.get("warnings", []),
    }


def _timeline_manifest(report: dict[str, Any]) -> dict[str, Any]:
    frame_count = max(0, int(report.get("frame_count") or 0))
    fps = float(report.get("fps") or 0.0)
    max_entries = max(1, int(report.get("max_timeline_entries") or 5000))
    stride = max(1, int(np.ceil(frame_count / max_entries))) if frame_count else 1
    candidate_by_index = {
        int(candidate["frame_index"]): candidate
        for candidate in report.get("selection_trace", {}).get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("frame_index") is not None
    }
    selected_by_index = {
        int(frame["frame_index"]): frame
        for frame in report.get("keyframes") or []
        if isinstance(frame, dict) and frame.get("frame_index") is not None
    }
    indexes: set[int] = set(range(0, frame_count, stride)) if frame_count else set()
    if frame_count:
        indexes.add(frame_count - 1)
    indexes.update(candidate_by_index)
    indexes.update(selected_by_index)
    timeline_frames = [
        _timeline_frame(
            index,
            fps=fps,
            candidate=candidate_by_index.get(index),
            selected=selected_by_index.get(index),
        )
        for index in sorted(indexes)
    ]
    return {
        "schema_version": "osteo-vision-video-timeline-manifest-v1",
        "timeline_scope": "full_duration_index_with_scored_candidates",
        "source_path": report.get("source_path"),
        "width": report.get("width"),
        "height": report.get("height"),
        "fps": fps,
        "frame_count": frame_count,
        "duration_sec": report.get("duration_sec"),
        "sampling_strategy": report.get("sampling_strategy"),
        "quality_evaluation": report.get("quality_evaluation", {}),
        "keyframe_manifest_path": report.get("keyframe_manifest_path"),
        "frame_index_manifest_path": report.get("frame_index_manifest_path"),
        "timeline_manifest_path": report.get("timeline_manifest_path"),
        "coverage": {
            "timeline_stride": stride,
            "timeline_frame_count": len(timeline_frames),
            "max_timeline_entries": max_entries,
            "includes_all_frames": stride == 1,
            "candidate_frame_count": len(candidate_by_index),
            "selected_frame_count": len(selected_by_index),
        },
        "deduplication": report.get("selection_trace", {}).get("deduplication", {}),
        "frames": timeline_frames,
        "warnings": report.get("warnings", []),
    }


def _timeline_frame(
    frame_index: int,
    *,
    fps: float,
    candidate: dict[str, Any] | None,
    selected: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "frame_index": frame_index,
        "timestamp_sec": float(frame_index / fps) if fps > 0 else None,
        "is_candidate": candidate is not None,
        "is_selected": selected is not None,
    }
    if candidate:
        payload.update(
            {
                "selection_score": candidate.get("selection_score"),
                "selection_rank": candidate.get("selection_rank"),
                "selection_source": candidate.get("selection_source"),
                "skipped_as_duplicate": candidate.get("skipped_as_duplicate", False),
                "duplicate_of_frame_index": candidate.get("duplicate_of_frame_index"),
                "duplicate_similarity": candidate.get("duplicate_similarity"),
                "duplicate_group": candidate.get("duplicate_group"),
                "visual_hash": candidate.get("visual_hash"),
                "quality": candidate.get("quality", {}),
            }
        )
    if selected:
        payload.update(
            {
                "order": selected.get("order"),
                "preview_path": selected.get("preview_path"),
                "evidence_path": selected.get("evidence_path"),
            }
        )
    return payload


def _resize_for_preview(frame: Any, *, max_preview_side: int) -> Any:
    import cv2

    height, width = frame.shape[:2]
    longest = max(width, height)
    if longest <= max_preview_side:
        return frame
    scale = max_preview_side / longest
    target_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)


def _select_frame_indexes(
    capture: Any,
    *,
    frame_count: int,
    sample_count: int,
    strategy: str,
    candidate_pool_size: int | None,
    min_frame_gap: int | None,
    deduplicate_similar_frames: bool,
    duplicate_similarity_threshold: float,
    quality_evaluation_max_side: int | None,
) -> tuple[list[int], dict[int, dict[str, Any]]]:
    if strategy == "uniform":
        indexes = _uniform_indexes(frame_count, sample_count)
        return indexes, {
            index: {"selection_score": None, "selection_rank": rank, "selection_source": "uniform"}
            for rank, index in enumerate(indexes, 1)
        }

    pool_size = candidate_pool_size or max(sample_count * 8, 24)
    candidate_count = max(sample_count, min(frame_count, pool_size))
    candidate_indexes = _uniform_indexes(frame_count, candidate_count)
    scored: list[dict[str, Any]] = []
    for index in candidate_indexes:
        capture.set(1, int(index))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        evaluation_frame, gray = _prepare_quality_frame(
            frame,
            max_evaluation_side=quality_evaluation_max_side,
        )
        quality = _frame_quality_from_prepared(
            evaluation_frame,
            gray,
            source_shape=frame.shape,
        )
        signature = _frame_signature(gray)
        scored.append(
            {
                "frame_index": int(index),
                "selection_score": _selection_score(quality),
                "quality": quality,
                "_signature": signature,
                "visual_hash": _visual_hash(signature),
            }
        )
    if not scored:
        indexes = _uniform_indexes(frame_count, sample_count)
        return indexes, {
            index: {"selection_score": None, "selection_rank": rank, "selection_source": "uniform_fallback"}
            for rank, index in enumerate(indexes, 1)
        }

    gap = min_frame_gap if min_frame_gap is not None else max(1, frame_count // max(sample_count * 4, 1))
    ranked = sorted(scored, key=lambda item: float(item["selection_score"]), reverse=True)
    selected: list[dict[str, Any]] = []
    for item in ranked:
        frame_index = int(item["frame_index"])
        duplicate = _duplicate_match(item, selected, threshold=duplicate_similarity_threshold)
        if deduplicate_similar_frames and duplicate:
            item["skipped_as_duplicate"] = True
            item["duplicate_of_frame_index"] = duplicate["frame_index"]
            item["duplicate_similarity"] = duplicate["similarity"]
            item["duplicate_group"] = f"dup_{duplicate['frame_index']}"
            continue
        if all(abs(frame_index - int(other["frame_index"])) >= gap for other in selected):
            item["selected_by_dedup"] = True
            selected.append(item)
        if len(selected) >= sample_count:
            break
    if len(selected) < sample_count:
        for item in ranked:
            if not any(int(item["frame_index"]) == int(other["frame_index"]) for other in selected):
                if item.get("skipped_as_duplicate"):
                    item["selected_after_duplicate_backfill"] = True
                selected.append(item)
            if len(selected) >= sample_count:
                break
    trace: dict[int, dict[str, Any]] = {}
    selected_indexes = {int(item["frame_index"]) for item in selected[:sample_count]}
    for rank, item in enumerate(ranked, start=1):
        trace[int(item["frame_index"])] = {
            "selection_score": round(float(item["selection_score"]), 6),
            "selection_rank": rank,
            "selection_source": "quality_peak",
            "selected": int(item["frame_index"]) in selected_indexes,
            "skipped_as_duplicate": bool(item.get("skipped_as_duplicate", False)),
            "selected_after_duplicate_backfill": bool(item.get("selected_after_duplicate_backfill", False)),
            "duplicate_of_frame_index": item.get("duplicate_of_frame_index"),
            "duplicate_similarity": item.get("duplicate_similarity"),
            "duplicate_group": item.get("duplicate_group"),
            "visual_hash": item.get("visual_hash"),
            "quality": item.get("quality", {}),
        }
    return sorted(int(item["frame_index"]) for item in selected[:sample_count]), trace


def _uniform_indexes(frame_count: int, sample_count: int) -> list[int]:
    if sample_count <= 1:
        return [frame_count // 2]
    return [round(i * (frame_count - 1) / (sample_count - 1)) for i in range(sample_count)]


def _frame_quality(frame: Any, *, max_evaluation_side: int | None = None) -> dict[str, Any]:
    evaluation_frame, gray = _prepare_quality_frame(frame, max_evaluation_side=max_evaluation_side)
    return _frame_quality_from_prepared(evaluation_frame, gray, source_shape=frame.shape)


def _prepare_quality_frame(frame: Any, *, max_evaluation_side: int | None) -> tuple[Any, np.ndarray]:
    import cv2

    evaluation_frame = frame
    if max_evaluation_side is not None:
        evaluation_frame = _resize_for_preview(frame, max_preview_side=max(64, int(max_evaluation_side)))
    gray = cv2.cvtColor(evaluation_frame, cv2.COLOR_BGR2GRAY)
    return evaluation_frame, gray


def _quality_evaluation_metadata(
    *,
    source_width: int,
    source_height: int,
    max_evaluation_side: int | None,
) -> dict[str, Any]:
    longest_side = max(source_width, source_height)
    bounded = max_evaluation_side is not None and longest_side > max(64, int(max_evaluation_side))
    return {
        "method": "bounded_thumbnail_v1" if bounded else "full_resolution_histogram_v1",
        "max_side_px": max(64, int(max_evaluation_side)) if max_evaluation_side is not None else None,
        "full_resolution_quality_metrics": not bounded,
        "full_resolution_evidence_preserved": True,
    }


def _frame_quality_from_prepared(
    evaluation_frame: Any,
    gray: np.ndarray,
    *,
    source_shape: Sequence[int],
) -> dict[str, Any]:
    import cv2

    # Only the green channel is needed independently. Avoid materializing all three 4K channels.
    green = cv2.extractChannel(evaluation_frame, 1)
    green_dominance = cv2.subtract(green, cv2.max(evaluation_frame[..., 2], evaluation_frame[..., 0]))
    gray_histogram = _uint8_histogram(gray)
    green_histogram = _uint8_histogram(green)
    dominance_histogram = _uint8_histogram(green_dominance)
    pixel_count = max(1, int(gray.size))
    _, high_intensity = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    _, high_green_dominance = cv2.threshold(green_dominance, 50, 255, cv2.THRESH_BINARY)
    high_signal = cv2.bitwise_or(high_intensity, high_green_dominance)
    source_height, source_width = int(source_shape[0]), int(source_shape[1])
    evaluation_height, evaluation_width = int(gray.shape[0]), int(gray.shape[1])
    return {
        "mean_intensity": float(cv2.mean(gray)[0]),
        "p95_intensity": _uint8_percentile(gray_histogram, 95.0, pixel_count),
        "p99_green": _uint8_percentile(green_histogram, 99.0, pixel_count),
        "green_dominance_p95": _uint8_percentile(dominance_histogram, 95.0, pixel_count),
        "high_signal_fraction": float(cv2.countNonZero(high_signal) / pixel_count),
        "blur_laplacian_var": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "underexposed_fraction": float(gray_histogram[:8].sum(dtype=np.int64) / pixel_count),
        "overexposed_fraction": float(gray_histogram[248:].sum(dtype=np.int64) / pixel_count),
        "source_width": source_width,
        "source_height": source_height,
        "evaluation_width": evaluation_width,
        "evaluation_height": evaluation_height,
        "evaluation_scale": float(evaluation_width / source_width) if source_width else 1.0,
        "evaluation_downsampled": evaluation_width != source_width or evaluation_height != source_height,
    }


def _uint8_histogram(image: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.calcHist([image], [0], None, [256], [0, 256]).reshape(-1).astype(np.int64, copy=False)


def _uint8_percentile(histogram: np.ndarray, percentile: float, pixel_count: int) -> float:
    if pixel_count <= 0:
        return 0.0
    rank = (pixel_count - 1) * percentile / 100.0
    lower_rank = int(np.floor(rank))
    upper_rank = int(np.ceil(rank))
    cumulative = np.cumsum(histogram, dtype=np.int64)
    lower_value = int(np.searchsorted(cumulative, lower_rank + 1, side="left"))
    upper_value = int(np.searchsorted(cumulative, upper_rank + 1, side="left"))
    return float(lower_value + (upper_value - lower_value) * (rank - lower_rank))


def _frame_signature(gray: np.ndarray, *, size: int = 16) -> np.ndarray:
    import cv2

    thumbnail = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA).astype("float32") / 255.0
    return thumbnail.reshape(-1)


def _visual_hash(signature: np.ndarray) -> str:
    if signature.size == 0:
        return ""
    bits = signature >= float(signature.mean())
    value = 0
    chunks: list[str] = []
    for index, bit in enumerate(bits, start=1):
        value = (value << 1) | int(bool(bit))
        if index % 4 == 0:
            chunks.append(f"{value:x}")
            value = 0
    if len(bits) % 4:
        chunks.append(f"{value:x}")
    return "".join(chunks)


def _duplicate_match(
    item: dict[str, Any], selected: list[dict[str, Any]], *, threshold: float
) -> dict[str, Any] | None:
    signature = item.get("_signature")
    if not isinstance(signature, np.ndarray):
        return None
    best: dict[str, Any] | None = None
    for selected_item in selected:
        selected_signature = selected_item.get("_signature")
        if not isinstance(selected_signature, np.ndarray):
            continue
        similarity = 1.0 - float(np.mean(np.abs(signature - selected_signature)))
        if similarity < threshold:
            continue
        if best is None or similarity > float(best["similarity"]):
            best = {
                "frame_index": int(selected_item["frame_index"]),
                "similarity": round(similarity, 6),
            }
    return best


def _candidate_trace(selection_trace: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for frame_index, trace in sorted(selection_trace.items()):
        candidate = {key: value for key, value in trace.items() if not key.startswith("_")}
        candidate["frame_index"] = int(frame_index)
        candidates.append(candidate)
    return candidates


def _deduplication_summary(selection_trace: dict[int, dict[str, Any]], *, strategy: str) -> dict[str, Any]:
    candidates = list(selection_trace.values())
    duplicate_candidates = [item for item in candidates if item.get("skipped_as_duplicate")]
    backfilled = [item for item in duplicate_candidates if item.get("selected_after_duplicate_backfill")]
    return {
        "enabled": strategy == "quality_peak",
        "strategy": "thumbnail_mean_absolute_similarity" if strategy == "quality_peak" else "not_applied",
        "duplicate_candidate_count": len(duplicate_candidates),
        "skipped_duplicate_count": max(0, len(duplicate_candidates) - len(backfilled)),
        "backfilled_duplicate_count": len(backfilled),
    }


def _selection_score(quality: dict[str, Any]) -> float:
    signal = max(
        float(quality.get("p95_intensity", 0.0)) / 255.0,
        float(quality.get("p99_green", 0.0)) / 255.0,
        float(quality.get("green_dominance_p95", 0.0)) / 255.0,
        min(float(quality.get("high_signal_fraction", 0.0)) * 4.0, 1.0),
    )
    blur = min(float(quality.get("blur_laplacian_var", 0.0)) / 200.0, 1.0)
    exposure_penalty = min(
        float(quality.get("underexposed_fraction", 0.0)) + float(quality.get("overexposed_fraction", 0.0)),
        1.0,
    )
    return 0.55 * signal + 0.35 * blur + 0.10 * (1.0 - exposure_penalty)


def _quality_summary(keyframes: list[dict[str, Any]]) -> dict[str, Any]:
    qualities = [frame.get("quality", {}) for frame in keyframes]
    means = [float(item["mean_intensity"]) for item in qualities if "mean_intensity" in item]
    blurs = [float(item["blur_laplacian_var"]) for item in qualities if "blur_laplacian_var" in item]
    scores = [float(frame["selection_score"]) for frame in keyframes if frame.get("selection_score") is not None]
    return {
        "frames_saved": len(keyframes),
        "mean_intensity_min": min(means) if means else None,
        "mean_intensity_max": max(means) if means else None,
        "blur_laplacian_var_min": min(blurs) if blurs else None,
        "selection_score_max": max(scores) if scores else None,
        "selection_score_min": min(scores) if scores else None,
    }
