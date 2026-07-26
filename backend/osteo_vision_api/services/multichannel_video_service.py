from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from math import isfinite
from pathlib import Path
from typing import Any, Literal

from backend.osteo_vision_api.domains.cases.enums import InputChannel
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    CaseInputAsset,
    CaseRecord,
    InputCreateRequest,
    MultichannelVideoChannel,
    MultichannelVideoSession,
    MultichannelVideoSessionCreateRequest,
    Task2PairedFrameReference,
    Task2PairedSequenceManifest,
)
from backend.osteo_vision_api.services.input_service import InputService
from backend.osteo_vision_api.services.video_library_service import VideoLibraryService
from osteo_vision_core.core.executables import find_runtime_executable
from osteo_vision_core.core.paths import ensure_dir
from osteo_vision_core.io.video_io import video_metadata

SOURCE_BOUNDARY = "多通道视频结果用于公开/代理数据的软件工程验证与医生复核，不代表真实术中 ICG " "颌骨骨髓炎临床性能。"


class MultichannelVideoError(ValueError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class MultichannelVideoService:
    def __init__(
        self,
        repo: CaseRepository,
        input_service: InputService,
        video_library: VideoLibraryService,
        artifact_root: str | Path,
    ) -> None:
        self.repo = repo
        self.input_service = input_service
        self.video_library = video_library
        self.root = Path(artifact_root) / "multichannel_video"

    def create_session(
        self,
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
    ) -> MultichannelVideoSession:
        identity = self._session_identity(case, request)
        session_id = f"mcv_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"
        session_dir = ensure_dir(self.root / case.case_id / session_id)
        session_path = session_dir / "session.json"
        cached = self._load_cached_session(session_path, case)
        if cached is not None:
            updated_case = self._case_with_session_summary(case, cached)
            if updated_case.review_summary != case.review_summary:
                self.repo.save(updated_case)
            return cached

        try:
            if request.mode == "single_video":
                session, updated_case = self._single_session(case, request, session_id)
            else:
                session, updated_case = self._paired_session(case, request, session_id, session_dir)
        except MultichannelVideoError as exc:
            if request.mode == "composite_layout":
                try:
                    session, updated_case = self._degraded_composite_session(
                        case,
                        request,
                        session_id,
                        exc,
                    )
                except MultichannelVideoError:
                    session, updated_case = self._blocked_session(case, request, session_id, exc)
            else:
                session, updated_case = self._blocked_session(case, request, session_id, exc)
        except ValueError as exc:
            wrapped = MultichannelVideoError(
                "multichannel_input_invalid",
                f"多通道视频输入校验失败：{exc}",
            )
            session, updated_case = self._blocked_session(case, request, session_id, wrapped)

        updated_case = self._case_with_session_summary(updated_case, session)
        if updated_case.model_dump(mode="json") != case.model_dump(mode="json"):
            self.repo.save(updated_case)
        self._write_session(session_path, session)
        return session

    @staticmethod
    def _case_with_session_summary(
        case: CaseRecord,
        session: MultichannelVideoSession,
    ) -> CaseRecord:
        review_summary = {
            **case.review_summary,
            "multichannel_session_id": session.session_id,
            "multichannel_session_status": session.status,
            "multichannel_video_mode": session.mode,
            "multichannel_synchronization_status": session.synchronization_status,
        }
        return case.model_copy(update={"review_summary": review_summary})

    @staticmethod
    def _blocked_session(
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
        session_id: str,
        error: MultichannelVideoError,
    ) -> tuple[MultichannelVideoSession, CaseRecord]:
        return (
            MultichannelVideoSession(
                schema_version="osteo-vision-multichannel-video-session-v1",
                session_id=session_id,
                case_id=case.case_id,
                mode=request.mode,
                status="blocked",
                analysis_allowed=False,
                synchronization_tolerance_ms=request.synchronization_tolerance_ms,
                synchronization_status="unavailable",
                failure_reasons=[error.code],
                warnings=[
                    {
                        "code": error.code,
                        "message": str(error),
                        "blocking": True,
                        "details": error.details,
                    }
                ],
                source_boundary=SOURCE_BOUNDARY,
            ),
            case,
        )

    def _degraded_composite_session(
        self,
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
        session_id: str,
        error: MultichannelVideoError,
    ) -> tuple[MultichannelVideoSession, CaseRecord]:
        candidate = self.video_library.get_candidate(str(request.composite_record_id))
        if candidate is None or not candidate.get("system_readable"):
            raise error
        case, asset = self._resolve_video_asset(
            case,
            None,
            str(candidate["local_path"]),
            role="composite_source",
            metadata={
                "record_id": candidate.get("record_id"),
                "view_layout": candidate.get("view_layout"),
                "domain_boundary": candidate.get("domain_boundary"),
            },
        )
        probe = self._required_video_probe(asset.path, "composite_source")
        return (
            MultichannelVideoSession(
                schema_version="osteo-vision-multichannel-video-session-v1",
                session_id=session_id,
                case_id=case.case_id,
                mode=request.mode,
                status="degraded",
                analysis_allowed=False,
                channels=[
                    MultichannelVideoChannel(
                        role="video",
                        input_id=asset.input_id,
                        path=asset.path,
                        probe=probe,
                        source_boundary=SOURCE_BOUNDARY,
                    )
                ],
                synchronization_tolerance_ms=request.synchronization_tolerance_ms,
                synchronization_status="unavailable",
                failure_reasons=[error.code],
                warnings=[
                    {
                        "code": error.code,
                        "message": f"{error} 已保留原始合成 MP4 播放。",
                        "blocking": False,
                        "details": error.details,
                    }
                ],
                source_boundary=SOURCE_BOUNDARY,
            ),
            case,
        )

    def get_session(self, case: CaseRecord, session_id: str) -> MultichannelVideoSession:
        suffix = session_id[4:] if session_id.startswith("mcv_") else ""
        if len(suffix) != 16 or any(char not in "0123456789abcdef" for char in suffix):
            raise MultichannelVideoError("multichannel_session_id_invalid", "多通道会话 ID 无效。")
        path = self.root / case.case_id / session_id / "session.json"
        session = self._load_cached_session(path, case, require_case_assets=False)
        if session is None:
            raise MultichannelVideoError("multichannel_session_not_found", "未找到多通道视频会话。")
        return session

    def _single_session(
        self,
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
        session_id: str,
    ) -> tuple[MultichannelVideoSession, CaseRecord]:
        case, asset = self._resolve_video_asset(
            case,
            request.video_input_id,
            request.video_path,
            role="video",
        )
        probe = self._required_video_probe(asset.path, "video")
        session = MultichannelVideoSession(
            schema_version="osteo-vision-multichannel-video-session-v1",
            session_id=session_id,
            case_id=case.case_id,
            mode=request.mode,
            status="ready",
            analysis_allowed=False,
            channels=[
                MultichannelVideoChannel(
                    role="video",
                    input_id=asset.input_id,
                    path=asset.path,
                    probe=probe,
                    source_boundary=SOURCE_BOUNDARY,
                )
            ],
            synchronization_tolerance_ms=request.synchronization_tolerance_ms,
            synchronization_status="unavailable",
            warnings=[
                {
                    "code": "single_video_uses_existing_analysis_path",
                    "message": "单路 MP4 继续使用现有关键帧分析和连续分割流程。",
                    "blocking": False,
                }
            ],
            source_boundary=SOURCE_BOUNDARY,
        )
        return session, case

    def _paired_session(
        self,
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
        session_id: str,
        session_dir: Path,
    ) -> tuple[MultichannelVideoSession, CaseRecord]:
        warnings: list[dict[str, Any]] = []
        if request.mode == "composite_layout":
            case, assets = self._prepare_composite_assets(case, request, session_id, session_dir)
        else:
            case, white = self._resolve_video_asset(
                case,
                request.white_light_input_id,
                request.white_light_path,
                role="white_light",
            )
            case, fluorescence = self._resolve_video_asset(
                case,
                request.fluorescence_input_id,
                request.fluorescence_path,
                role="fluorescence",
            )
            device: CaseInputAsset | None = None
            if request.device_overlay_input_id or request.device_overlay_path:
                case, device = self._resolve_video_asset(
                    case,
                    request.device_overlay_input_id,
                    request.device_overlay_path,
                    role="device_overlay",
                )
            assets = {"white_light": white, "fluorescence": fluorescence, "device_overlay": device}

        probes = {
            role: self._required_video_probe(asset.path, role) for role, asset in assets.items() if asset is not None
        }
        auto_fluorescence = _automatic_offset_ms(probes["white_light"], probes["fluorescence"])
        effective_fluorescence = (
            auto_fluorescence if request.fluorescence_offset_ms is None else float(request.fluorescence_offset_ms)
        )
        auto_device = 0.0
        effective_device = 0.0
        if assets.get("device_overlay") is not None:
            auto_device = _automatic_offset_ms(probes["white_light"], probes["device_overlay"])
            effective_device = (
                auto_device if request.device_overlay_offset_ms is None else float(request.device_overlay_offset_ms)
            )
        offsets = {
            "white_light": 0.0,
            "fluorescence": effective_fluorescence,
            "device_overlay": effective_device,
        }
        common_start, common_end = _common_interval(probes, offsets)
        if common_end <= common_start:
            raise MultichannelVideoError(
                "multichannel_no_common_interval",
                "多通道视频没有共同有效时间区间，无法准备配对关键帧。",
                details={"common_start_sec": common_start, "common_end_sec": common_end, "offsets_ms": offsets},
            )

        initial_delta = abs(auto_fluorescence)
        if assets.get("device_overlay") is not None:
            initial_delta = max(initial_delta, abs(auto_device))
        synchronization_status: Literal["aligned", "review_required"] = (
            "aligned" if initial_delta <= request.synchronization_tolerance_ms else "review_required"
        )
        if synchronization_status == "review_required":
            warnings.append(
                {
                    "code": "multichannel_start_time_review_required",
                    "message": "通道容器起始时间差超过同步容差，已应用偏移并保留人工复核标记。",
                    "blocking": False,
                    "details": {
                        "initial_time_delta_ms": initial_delta,
                        "tolerance_ms": request.synchronization_tolerance_ms,
                    },
                }
            )

        frame_times = _sample_times(
            common_start,
            common_end,
            request.keyframe_count,
            request.focus_timepoints_sec,
        )
        case, manifest, frame_pairs, extraction_warnings = self._extract_pairs(
            case,
            assets,
            probes,
            offsets,
            session_id,
            session_dir,
            frame_times,
            request.synchronization_tolerance_ms,
        )
        warnings.extend(extraction_warnings)
        channels = [
            MultichannelVideoChannel(
                role=role,  # type: ignore[arg-type]
                input_id=asset.input_id,
                path=asset.path,
                probe=probes[role],
                automatic_offset_ms=(
                    auto_fluorescence if role == "fluorescence" else auto_device if role == "device_overlay" else 0.0
                ),
                effective_offset_ms=offsets[role],
                source_boundary=SOURCE_BOUNDARY,
            )
            for role, asset in assets.items()
            if asset is not None
        ]
        status: Literal["ready", "degraded"] = "ready" if len(manifest.frames) == len(frame_times) else "degraded"
        return (
            MultichannelVideoSession(
                schema_version="osteo-vision-multichannel-video-session-v1",
                session_id=session_id,
                case_id=case.case_id,
                mode=request.mode,
                status=status,
                analysis_allowed=len(manifest.frames) >= 2,
                channels=channels,
                synchronization_tolerance_ms=request.synchronization_tolerance_ms,
                synchronization_status=synchronization_status,
                initial_time_delta_ms=round(initial_delta, 3),
                common_start_sec=round(common_start, 6),
                common_end_sec=round(common_end, 6),
                common_duration_sec=round(common_end - common_start, 6),
                paired_sequence_manifest=manifest,
                frame_pairs=frame_pairs,
                warnings=warnings,
                source_boundary=SOURCE_BOUNDARY,
            ),
            case,
        )

    def _prepare_composite_assets(
        self,
        case: CaseRecord,
        request: MultichannelVideoSessionCreateRequest,
        session_id: str,
        session_dir: Path,
    ) -> tuple[CaseRecord, dict[str, CaseInputAsset | None]]:
        candidate = self.video_library.get_candidate(str(request.composite_record_id))
        if candidate is None:
            raise MultichannelVideoError("composite_video_not_found", "未找到指定的合成三视图视频。")
        if not candidate.get("system_readable"):
            raise MultichannelVideoError("composite_video_unreadable", "合成三视图视频缺失或无法解码。")
        crop_regions = candidate.get("crop_regions")
        if not isinstance(crop_regions, dict) or not all(
            isinstance(crop_regions.get(role), list) for role in ("white_light", "fluorescence", "device_overlay")
        ):
            raise MultichannelVideoError("composite_layout_missing", "视频清单缺少可用的三视图裁切坐标。")
        case, _ = self._resolve_video_asset(
            case,
            None,
            str(candidate["local_path"]),
            role="composite_source",
            metadata={
                "record_id": candidate.get("record_id"),
                "view_layout": candidate.get("view_layout"),
                "domain_boundary": candidate.get("domain_boundary"),
            },
        )
        output_paths = self._split_composite(
            Path(str(candidate["local_path"])),
            crop_regions,
            session_dir / "channels",
        )
        result: dict[str, CaseInputAsset | None] = {}
        for role in ("white_light", "fluorescence", "device_overlay"):
            case, result[role] = self._resolve_video_asset(
                case,
                None,
                str(output_paths[role]),
                role=role,
                metadata={
                    "source": "ofdvdnet_composite_split",
                    "source_record_id": candidate.get("record_id"),
                    "multichannel_session_id": session_id,
                    "crop_xyxy": crop_regions[role],
                    "domain_boundary": candidate.get("domain_boundary"),
                },
            )
        return case, result

    def _split_composite(
        self,
        source: Path,
        crop_regions: dict[str, Any],
        output_dir: Path,
    ) -> dict[str, Path]:
        probe = self._required_video_probe(str(source), "composite_source")
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)
        regions: dict[str, tuple[int, int, int, int]] = {}
        for role in ("white_light", "fluorescence", "device_overlay"):
            raw = crop_regions.get(role)
            if not isinstance(raw, list) or len(raw) != 4:
                raise MultichannelVideoError("composite_crop_invalid", f"{role} 裁切坐标无效。")
            x1, y1, x2, y2 = (int(value) for value in raw)
            if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > width or y2 > height:
                raise MultichannelVideoError(
                    "composite_crop_out_of_bounds",
                    f"{role} 裁切坐标超出视频范围。",
                    details={"crop": raw, "video_size": [width, height]},
                )
            regions[role] = (x1, y1, x2, y2)

        executable = find_runtime_executable("ffmpeg")
        if executable is None:
            raise MultichannelVideoError(
                "ffmpeg_unavailable",
                "FFmpeg 不可用，已保留原始合成 MP4 播放，暂无法拆分通道。",
            )
        ensure_dir(output_dir)
        outputs = {role: output_dir / f"{role}.mp4" for role in regions}
        pending = [role for role, output in outputs.items() if not output.is_file() or output.stat().st_size <= 0]
        if not pending:
            return outputs

        filter_parts: list[str] = []
        source_labels: list[str]
        if len(pending) == 1:
            source_labels = ["0:v"]
        else:
            source_labels = [f"source_{index}" for index in range(len(pending))]
            split_outputs = "".join(f"[{label}]" for label in source_labels)
            filter_parts.append(f"[0:v]split={len(pending)}{split_outputs}")
        output_labels: list[str] = []
        for index, role in enumerate(pending):
            x1, y1, x2, y2 = regions[role]
            output_label = f"crop_{index}"
            output_labels.append(output_label)
            filter_parts.append(f"[{source_labels[index]}]crop={x2 - x1}:{y2 - y1}:{x1}:{y1}[{output_label}]")

        command = [executable, "-y", "-v", "error", "-i", str(source), "-filter_complex", ";".join(filter_parts)]
        for role, output_label in zip(pending, output_labels, strict=True):
            command.extend(
                [
                    "-map",
                    f"[{output_label}]",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-movflags",
                    "+faststart",
                    str(outputs[role]),
                ]
            )
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MultichannelVideoError(
                "composite_split_failed",
                "合成视频通道拆分失败。",
                details={"error": str(exc), "pending_roles": pending},
            ) from exc
        missing = [role for role in pending if not outputs[role].is_file() or outputs[role].stat().st_size <= 0]
        if completed.returncode != 0 or missing:
            raise MultichannelVideoError(
                "composite_split_failed",
                "合成视频通道拆分失败。",
                details={
                    "stderr": completed.stderr.strip()[-1000:],
                    "pending_roles": pending,
                    "missing_roles": missing,
                },
            )
        return outputs

    def _extract_pairs(
        self,
        case: CaseRecord,
        assets: dict[str, CaseInputAsset | None],
        probes: dict[str, dict[str, Any]],
        offsets: dict[str, float],
        session_id: str,
        session_dir: Path,
        times: list[float],
        tolerance_ms: float,
    ) -> tuple[CaseRecord, Task2PairedSequenceManifest, list[dict[str, Any]], list[dict[str, Any]]]:
        frame_dir = ensure_dir(session_dir / "paired_frames")
        input_requests: list[InputCreateRequest] = []
        extracted: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for pair_index, master_time in enumerate(times):
            local_times = {
                role: master_time + offsets.get(role, 0.0) / 1000.0
                for role in ("white_light", "fluorescence", "device_overlay")
            }
            paths: dict[str, str] = {}
            failed = False
            for role in ("white_light", "fluorescence"):
                asset = assets.get(role)
                if asset is None:
                    failed = True
                    break
                output = frame_dir / f"{pair_index:03d}_{role}.jpg"
                if not _extract_video_frame(Path(asset.path), local_times[role], output):
                    warnings.append(
                        {
                            "code": "multichannel_keyframe_extract_failed",
                            "message": f"时间点 {master_time:.3f}s 的 {role} 帧抽取失败，已跳过该配对。",
                            "blocking": False,
                        }
                    )
                    failed = True
                    break
                paths[role] = str(output)
            if failed:
                continue
            device = assets.get("device_overlay")
            if device is not None:
                output = frame_dir / f"{pair_index:03d}_device_overlay.jpg"
                if _extract_video_frame(Path(device.path), local_times["device_overlay"], output):
                    paths["device_overlay"] = str(output)
                else:
                    warnings.append(
                        {
                            "code": "device_overlay_keyframe_extract_failed",
                            "message": f"时间点 {master_time:.3f}s 的设备叠加帧抽取失败，融合分析继续运行。",
                            "blocking": False,
                        }
                    )
            extracted.append(
                {
                    "pair_index": len(extracted),
                    "master_time_sec": round(master_time, 6),
                    "local_times_sec": {key: round(value, 6) for key, value in local_times.items()},
                    "paths": paths,
                }
            )
            for role, channel in (
                ("white_light", InputChannel.WHITE_LIGHT),
                ("fluorescence", InputChannel.FLUORESCENCE),
            ):
                source_asset = assets.get(role)
                if source_asset is None:
                    raise MultichannelVideoError(
                        "multichannel_source_asset_missing",
                        f"{role} 源视频在关键帧写入前丢失。",
                    )
                input_requests.append(
                    InputCreateRequest(
                        channel=channel,
                        path=paths[role],
                        mime_type="image/jpeg",
                        metadata={
                            "source": "multichannel_video_keyframe",
                            "channel_role": role,
                            "multichannel_session_id": session_id,
                            "pair_index": len(extracted) - 1,
                            "master_time_sec": master_time,
                            "source_local_time_sec": local_times[role],
                            "source_video_input_id": source_asset.input_id,
                            "source_video_probe": probes[role],
                        },
                    )
                )
            if "device_overlay" in paths:
                source_asset = assets.get("device_overlay")
                if source_asset is not None:
                    input_requests.append(
                        InputCreateRequest(
                            channel=InputChannel.DEVICE_OVERLAY,
                            path=paths["device_overlay"],
                            mime_type="image/jpeg",
                            metadata={
                                "source": "multichannel_video_keyframe",
                                "channel_role": "device_overlay",
                                "multichannel_session_id": session_id,
                                "pair_index": len(extracted) - 1,
                                "master_time_sec": master_time,
                                "source_local_time_sec": local_times["device_overlay"],
                                "source_video_input_id": source_asset.input_id,
                                "source_video_probe": probes["device_overlay"],
                            },
                        )
                    )

        if len(extracted) < 2:
            raise MultichannelVideoError(
                "multichannel_keyframes_insufficient",
                "成功抽取的成对关键帧少于 2 对，无法运行任务2融合分析。",
                details={"requested": len(times), "extracted": len(extracted)},
            )
        prior_count = len(case.inputs)
        case = self.input_service.add_inputs(case, input_requests, replace_existing_channels=False)
        new_assets = case.inputs[prior_count:]
        indexed_assets: dict[tuple[int, str], CaseInputAsset] = {}
        for asset in new_assets:
            metadata_pair_index = asset.metadata.get("pair_index")
            metadata_role = asset.metadata.get("channel_role")
            if isinstance(metadata_pair_index, int) and isinstance(metadata_role, str):
                indexed_assets[(metadata_pair_index, metadata_role)] = asset
        references: list[Task2PairedFrameReference] = []
        for index, pair in enumerate(extracted):
            white = indexed_assets[(index, "white_light")]
            fluorescence = indexed_assets[(index, "fluorescence")]
            device = indexed_assets.get((index, "device_overlay"))
            pair["white_input_id"] = white.input_id
            pair["fluorescence_input_id"] = fluorescence.input_id
            pair["device_overlay_input_id"] = device.input_id if device else None
            references.append(
                Task2PairedFrameReference(
                    frame_index=index,
                    white_input_id=white.input_id,
                    fluorescence_input_id=fluorescence.input_id,
                    device_overlay_input_id=device.input_id if device else None,
                    captured_at=datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=float(pair["master_time_sec"])),
                    white_timestamp_ms=float(pair["master_time_sec"]) * 1000.0,
                    fluorescence_timestamp_ms=float(pair["master_time_sec"]) * 1000.0,
                )
            )
        manifest = Task2PairedSequenceManifest(
            schema_version="osteo-vision-task2-paired-sequence-v1",
            sequence_id=session_id,
            frames=references,
            synchronization_tolerance_ms=tolerance_ms,
        )
        return case, manifest, extracted, warnings

    def _resolve_video_asset(
        self,
        case: CaseRecord,
        input_id: str | None,
        path: str | None,
        *,
        role: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[CaseRecord, CaseInputAsset]:
        if input_id:
            asset = next((item for item in case.inputs if item.input_id == input_id), None)
            if asset is None:
                raise MultichannelVideoError(
                    "multichannel_input_not_found",
                    f"病例中未找到 {role} 视频输入。",
                    details={"input_id": input_id},
                )
            if asset.channel != InputChannel.VIDEO:
                raise MultichannelVideoError("multichannel_input_channel_invalid", f"{role} 输入不是 MP4 视频。")
            return case, asset
        if not path:
            raise MultichannelVideoError("multichannel_input_missing", f"缺少 {role} 视频路径。")
        resolved = str(Path(path).expanduser().resolve())
        existing = next(
            (
                item
                for item in case.inputs
                if item.channel == InputChannel.VIDEO and str(Path(item.path).expanduser().resolve()) == resolved
            ),
            None,
        )
        if existing is not None:
            return case, existing
        case = self.input_service.add_inputs(
            case,
            [
                InputCreateRequest(
                    channel=InputChannel.VIDEO,
                    path=path,
                    mime_type="video/mp4",
                    metadata={
                        "source": "multichannel_video_session",
                        "channel_role": role,
                        "domain_boundary": SOURCE_BOUNDARY,
                        **(metadata or {}),
                    },
                )
            ],
            replace_existing_channels=False,
        )
        return case, case.inputs[-1]

    @staticmethod
    def _required_video_probe(path: str, role: str) -> dict[str, Any]:
        probe = video_metadata(path)
        if not probe.get("readable") or not probe.get("duration_sec"):
            raise MultichannelVideoError(
                "multichannel_video_unreadable",
                f"{role} 视频无法解码或缺少有效时长。",
                details={"path": path, "probe_error": probe.get("video_probe_error")},
            )
        return probe

    def _session_identity(self, case: CaseRecord, request: MultichannelVideoSessionCreateRequest) -> str:
        payload = {"case_id": case.case_id, **request.model_dump(mode="json")}
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _load_cached_session(
        path: Path,
        case: CaseRecord,
        *,
        require_case_assets: bool = True,
    ) -> MultichannelVideoSession | None:
        try:
            session = MultichannelVideoSession.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if require_case_assets and session.paired_sequence_manifest:
            known = {asset.input_id for asset in case.inputs}
            referenced = {
                input_id
                for frame in session.paired_sequence_manifest.frames
                for input_id in (frame.white_input_id, frame.fluorescence_input_id)
            }
            if not referenced.issubset(known):
                return None
        return session

    @staticmethod
    def _write_session(path: Path, session: MultichannelVideoSession) -> None:
        ensure_dir(path.parent)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)


def _probe_start_time_sec(probe: dict[str, Any]) -> float:
    ffprobe = probe.get("ffprobe")
    if not isinstance(ffprobe, dict):
        return 0.0
    for container in (ffprobe.get("format"), ffprobe.get("stream")):
        if not isinstance(container, dict):
            continue
        try:
            parsed = float(container.get("start_time") or 0.0)
        except (TypeError, ValueError):
            continue
        if isfinite(parsed):
            return parsed
    return 0.0


def _automatic_offset_ms(white_probe: dict[str, Any], other_probe: dict[str, Any]) -> float:
    return round((_probe_start_time_sec(white_probe) - _probe_start_time_sec(other_probe)) * 1000.0, 3)


def _common_interval(
    probes: dict[str, dict[str, Any]],
    offsets_ms: dict[str, float],
) -> tuple[float, float]:
    starts = [0.0]
    ends = [float(probes["white_light"]["duration_sec"])]
    for role in ("fluorescence", "device_overlay"):
        if role not in probes:
            continue
        offset_sec = offsets_ms.get(role, 0.0) / 1000.0
        starts.append(-offset_sec)
        ends.append(float(probes[role]["duration_sec"]) - offset_sec)
    return max(starts), min(ends)


def _sample_times(start: float, end: float, count: int, focus: list[Any]) -> list[float]:
    epsilon = min(0.1, max(0.001, (end - start) / 10.0))
    upper = max(start, end - epsilon)
    parsed_focus: set[float] = set()
    for value in focus:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(parsed) and start <= parsed <= upper:
            parsed_focus.add(round(parsed, 6))
    focus_values = sorted(parsed_focus)
    remaining = max(0, count - len(focus_values))
    if remaining <= 0:
        uniform: list[float] = []
    elif remaining == 1:
        uniform = [start]
    else:
        step = (upper - start) / (remaining - 1)
        uniform = [start + step * index for index in range(remaining)]
    combined = sorted({round(value, 6) for value in [*focus_values, *uniform]})
    if len(combined) > count:
        focus_set = set(focus_values)
        prioritized = [value for value in combined if value in focus_set]
        prioritized.extend(value for value in combined if value not in focus_set)
        combined = sorted(prioritized[:count])
    return combined


def _extract_video_frame(source: Path, time_sec: float, output: Path) -> bool:
    import cv2

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        return False
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(time_sec)) * 1000.0)
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        return False
    ensure_dir(output.parent)
    return bool(cv2.imwrite(str(output), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92]))
