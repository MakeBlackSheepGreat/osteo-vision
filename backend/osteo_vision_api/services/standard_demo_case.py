from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from threading import RLock
from typing import Any

import cv2

from backend.osteo_vision_api.domains.cases.enums import InputChannel
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    AnalysisRun,
    CaseRecord,
    InputCreateRequest,
    MultichannelVideoSessionCreateRequest,
)
from backend.osteo_vision_api.services.input_service import InputService
from backend.osteo_vision_api.services.multichannel_video_service import MultichannelVideoService
from backend.osteo_vision_api.services.three_d_evidence import build_three_d_evidence
from backend.osteo_vision_api.services.video_library_service import VideoLibraryService

STANDARD_DEMO_CASE_ID = "case_standard_demo"
STANDARD_DEMO_VIDEO_RECORD_ID = "OFDVDNET_001"
STANDARD_DEMO_VERSION = 9
STANDARD_DEMO_ANNOTATION_RUN_ID = "standard_demo_ofdvdnet_annotation_frames"
STANDARD_DEMO_ANNOTATION_FRAME_FRACTIONS = (0.16, 0.5, 0.84)
STANDARD_DEMO_ANNOTATION_BOUNDARY = (
    "OFDVDnet public non-target-domain fluorescence-guided surgery proxy keyframe; "
    "not real intraoperative ICG jaw osteomyelitis data."
)
DEMO_CASE_CATALOG_VERSION = 1
_STANDARD_DEMO_LOCK = RLock()
DEMO_CASE_CATALOG = (
    (STANDARD_DEMO_CASE_ID, "张三 · OFDVDnet 三视图荧光代理示例"),
    ("case_demo_li_si", "李四 · 荧光融合工程示例"),
    ("case_demo_wang_wu", "王五 · 视频关键帧复核示例"),
    ("case_demo_zhao_liu", "赵六 · CBCT 三维参考示例"),
    ("case_demo_chen_qi", "陈七 · 病例证据回顾示例"),
)


class StandardDemoCaseService:
    """Creates one deterministic, non-target-domain case for local demonstrations."""

    def __init__(
        self,
        repo: CaseRepository,
        input_service: InputService,
        video_library: VideoLibraryService,
        multichannel_video: MultichannelVideoService | None = None,
        artifact_root: str | Path | None = None,
    ) -> None:
        self.repo = repo
        self.input_service = input_service
        self.video_library = video_library
        self.multichannel_video = multichannel_video
        self.annotation_frame_root = Path(artifact_root or "artifacts/platform") / "standard_demo_annotation_frames"

    def ensure_case(self) -> CaseRecord:
        # The desktop shell can request the standard case from the route watcher and
        # the automation harness at the same time. Keep the read/prepare/save cycle atomic.
        with _STANDARD_DEMO_LOCK:
            return self._ensure_case()

    def _ensure_case(self) -> CaseRecord:
        existing = self.repo.get(STANDARD_DEMO_CASE_ID)
        candidate = self._selected_video_candidate()
        if (
            existing is not None
            and existing.review_summary.get("standard_demo_version") == STANDARD_DEMO_VERSION
            and existing.review_summary.get("multichannel_session_status") in {"ready", "degraded", "blocked"}
            and self._existing_demo_matches_candidate(existing, candidate)
        ):
            return existing

        if existing is None:
            now = datetime.now(timezone.utc)
            case = CaseRecord(
                case_id=STANDARD_DEMO_CASE_ID,
                title=DEMO_CASE_CATALOG[0][1],
                created_at=now,
                updated_at=now,
                review_summary={
                    "case_kind": "standard_demo",
                    "standard_demo_version": STANDARD_DEMO_VERSION,
                    "video_source_policy": "ofdvdnet_public_composite_proxy",
                    "three_d_source_policy": "d024_public_mandible_reference",
                    "doctor_review_status": "review_required",
                },
                warnings=[
                    {
                        "code": "standard_demo_non_target_domain",
                        "message": "标准示例使用 OFDVDnet 公开代理视频和 D024 下颌表面参考，不代表真实术中 ICG 颌骨骨髓炎病例。",
                        "blocking": False,
                    }
                ],
            )
        else:
            retained_inputs = [
                asset
                for asset in existing.inputs
                if not (
                    asset.metadata.get("standard_demo")
                    or asset.metadata.get("multichannel_session_id")
                    or asset.metadata.get("source") == "multichannel_video_keyframe"
                )
            ]
            retained_runs = [run for run in existing.analysis_runs if run.run_id != STANDARD_DEMO_ANNOTATION_RUN_ID]
            case = existing.model_copy(
                update={
                    "title": DEMO_CASE_CATALOG[0][1],
                    "inputs": retained_inputs,
                    "analysis_runs": retained_runs,
                    "review_summary": {
                        **existing.review_summary,
                        "standard_demo_version": STANDARD_DEMO_VERSION,
                        "video_source_policy": "ofdvdnet_public_composite_proxy",
                    },
                }
            )
        if candidate is not None:
            try:
                case = self.input_service.add_inputs(case, [self._video_input(candidate)])
            except ValueError as exc:
                case.warnings.append(
                    {
                        "code": "standard_demo_video_unavailable",
                        "message": f"标准示例视频未载入：{exc}",
                        "blocking": False,
                    }
                )
        else:
            case.warnings.append(
                {
                    "code": "standard_demo_video_unavailable",
                    "message": "本机未找到可读的公开视频代理，标准病例保留空视频输入。",
                    "blocking": False,
                }
            )

        case = self._attach_annotation_keyframes(case, candidate)

        evidence = build_three_d_evidence(
            parameters={"three_d_evidence_demo": "d024"},
            source_inputs=case.inputs,
            analysis_mode="standard_demo",
            run_id="standard_demo_seed",
        )
        evidence.update(
            {
                "input_domain": "public_non_target_domain_demo",
                "registration_status": "unregistered",
                "navigation_level": "L0",
                "navigation_ready": False,
                "doctor_review_status": "review_required",
                "fallback_mode": "unregistered_3d_reference",
                "failure_reasons": ["standard_demo_l0_only"],
                "data_boundary": "标准示例使用项目选定的公开视频代理和 D024 公开下颌表面，仅用于软件演示与工程复核。",
                "boundary_note": "标准示例保持 L0 未配准参考，医生复核后方可形成病例级工程结论。",
            }
        )
        case = case.model_copy(update={"three_d_evidence": evidence})
        case = self.repo.create(case) if existing is None else self.repo.save(case)
        return self._prepare_multichannel_demo(case, candidate)

    def ensure_demo_catalog(self) -> list[CaseRecord]:
        """Create the fixed, clearly synthetic case list shown in the archive by default."""
        standard_demo = self.ensure_case()
        catalog: list[CaseRecord] = [standard_demo]
        for case_id, title in DEMO_CASE_CATALOG[1:]:
            existing = self.repo.get(case_id)
            if existing is None:
                now = datetime.now(timezone.utc)
                catalog.append(
                    self.repo.create(
                        CaseRecord(
                            case_id=case_id,
                            title=title,
                            created_at=now,
                            updated_at=now,
                            review_summary={
                                "case_kind": "named_engineering_demo",
                                "demo_catalog_version": DEMO_CASE_CATALOG_VERSION,
                                "display_name_is_synthetic": True,
                            },
                            warnings=[
                                {
                                    "code": "synthetic_named_demo_case",
                                    "message": "姓名仅用于平台界面演示，未指向真实患者或临床结论。",
                                    "blocking": False,
                                }
                            ],
                        )
                    )
                )
                continue
            if (
                existing.review_summary.get("demo_catalog_version") != DEMO_CASE_CATALOG_VERSION
                or existing.title != title
            ):
                existing = self.repo.save(
                    existing.model_copy(
                        update={
                            "title": title,
                            "review_summary": {
                                **existing.review_summary,
                                "case_kind": "named_engineering_demo",
                                "demo_catalog_version": DEMO_CASE_CATALOG_VERSION,
                                "display_name_is_synthetic": True,
                            },
                        }
                    )
                )
            catalog.append(existing)
        return catalog

    def _attach_annotation_keyframes(
        self,
        case: CaseRecord,
        candidate: dict[str, Any] | None,
    ) -> CaseRecord:
        if candidate is None or candidate.get("record_id") != STANDARD_DEMO_VIDEO_RECORD_ID:
            return case
        video = next(
            (
                asset
                for asset in case.inputs
                if asset.channel == InputChannel.VIDEO
                and asset.metadata.get("standard_demo")
                and asset.metadata.get("record_id") == STANDARD_DEMO_VIDEO_RECORD_ID
            ),
            None,
        )
        if video is None:
            return case

        frames = self._extract_annotation_keyframes(Path(video.path), case.case_id)
        if not frames:
            warnings = [
                item for item in case.warnings if item.get("code") != "standard_demo_annotation_frames_unavailable"
            ]
            warnings.append(
                {
                    "code": "standard_demo_annotation_frames_unavailable",
                    "message": "OFDVDnet 示例视频无法生成可标注关键帧。",
                    "blocking": False,
                }
            )
            return case.model_copy(update={"warnings": warnings})

        run = AnalysisRun(
            run_id=STANDARD_DEMO_ANNOTATION_RUN_ID,
            case_id=case.case_id,
            method_id="ofdvdnet_annotation_keyframe_sampler",
            status="completed",
            parameters={
                "source_record_id": STANDARD_DEMO_VIDEO_RECORD_ID,
                "sampling_fractions": list(STANDARD_DEMO_ANNOTATION_FRAME_FRACTIONS),
                "annotation_demo": True,
            },
            fused_outputs={
                "mode": "standard_demo_ofdvdnet_annotation_keyframes",
                "source_path": video.path,
                "frame_details": frames,
                "keyframes": frames,
                "source_record_id": STANDARD_DEMO_VIDEO_RECORD_ID,
                "data_boundary": STANDARD_DEMO_ANNOTATION_BOUNDARY,
            },
            quantitative_summary={"keyframe_count": len(frames)},
            warnings=[
                {
                    "code": "standard_demo_annotation_non_target_domain",
                    "message": STANDARD_DEMO_ANNOTATION_BOUNDARY,
                    "blocking": False,
                }
            ],
            notes="OFDVDnet public proxy keyframes prepared for manual annotation workflow demonstration.",
        )
        warnings = [item for item in case.warnings if item.get("code") != "standard_demo_annotation_frames_unavailable"]
        return case.model_copy(update={"analysis_runs": [*case.analysis_runs, run], "warnings": warnings})

    def _extract_annotation_keyframes(self, video_path: Path, case_id: str) -> list[dict[str, Any]]:
        capture = cv2.VideoCapture(str(video_path))
        try:
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            if frame_count <= 0:
                return []
            frame_indexes = sorted(
                {
                    min(frame_count - 1, max(0, round((frame_count - 1) * fraction)))
                    for fraction in STANDARD_DEMO_ANNOTATION_FRAME_FRACTIONS
                }
            )
            output_dir = self.annotation_frame_root / case_id
            output_dir.mkdir(parents=True, exist_ok=True)
            frames: list[dict[str, Any]] = []
            for order, frame_index in enumerate(frame_indexes, start=1):
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                readable, frame = capture.read()
                if not readable or frame is None:
                    continue
                output_path = (
                    output_dir / f"ofdvdnet_{STANDARD_DEMO_VIDEO_RECORD_ID.lower()}_frame_{frame_index:06d}.jpg"
                )
                if not cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 94]):
                    continue
                timestamp_sec = frame_index / fps if math.isfinite(fps) and fps > 0 else 0.0
                frames.append(
                    {
                        "order": order,
                        "frame_index": frame_index,
                        "timestamp_sec": round(timestamp_sec, 4),
                        "evidence_path": str(output_path),
                        "preview_path": str(output_path),
                        "source_path": str(output_path),
                        "display_allowed": True,
                        "source_record_id": STANDARD_DEMO_VIDEO_RECORD_ID,
                        "data_boundary": STANDARD_DEMO_ANNOTATION_BOUNDARY,
                    }
                )
            return frames
        finally:
            capture.release()

    def _prepare_multichannel_demo(
        self,
        case: CaseRecord,
        candidate: dict[str, Any] | None,
    ) -> CaseRecord:
        if (
            self.multichannel_video is None
            or candidate is None
            or candidate.get("record_id") != STANDARD_DEMO_VIDEO_RECORD_ID
            or not candidate.get("composite_layout_available")
        ):
            return self._save_session_status(case, "blocked", None)
        session = self.multichannel_video.create_session(
            case,
            MultichannelVideoSessionCreateRequest(
                mode="composite_layout",
                composite_record_id=STANDARD_DEMO_VIDEO_RECORD_ID,
                keyframe_count=12,
            ),
        )
        refreshed = self.repo.get(case.case_id) or case
        warnings = list(refreshed.warnings)
        for warning in session.warnings:
            if warning not in warnings:
                warnings.append(warning)
        updated = refreshed.model_copy(update={"warnings": warnings})
        return self._save_session_status(updated, session.status, session.session_id)

    def _save_session_status(
        self,
        case: CaseRecord,
        status: str,
        session_id: str | None,
    ) -> CaseRecord:
        summary = {
            **case.review_summary,
            "standard_demo_version": STANDARD_DEMO_VERSION,
            "multichannel_session_status": status,
            "multichannel_session_id": session_id,
        }
        return self.repo.save(case.model_copy(update={"review_summary": summary}))

    def _selected_video_candidate(self) -> dict[str, Any] | None:
        preferred = self.video_library.get_candidate(STANDARD_DEMO_VIDEO_RECORD_ID)
        if isinstance(preferred, dict) and preferred.get("system_readable"):
            return preferred
        candidates = self.video_library.list_candidates(accepted_only=True, limit=1).get("items", [])
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("system_readable"):
                return candidate
        return None

    @staticmethod
    def _existing_demo_matches_candidate(
        case: CaseRecord,
        candidate: dict[str, Any] | None,
    ) -> bool:
        """Allow cached demos only when their packaged video still points at the active release."""
        demo_assets = [
            asset
            for asset in case.inputs
            if asset.channel == InputChannel.VIDEO
            and (
                asset.metadata.get("standard_demo") is True
                or asset.metadata.get("record_id") == STANDARD_DEMO_VIDEO_RECORD_ID
            )
        ]
        if candidate is None:
            # A release without the optional proxy video should remain an empty,
            # repeatable fallback rather than retaining a stale absolute path.
            return not demo_assets
        if len(demo_assets) != 1:
            return False
        asset = demo_assets[0]
        expected_path = StandardDemoCaseService._normalize_path(candidate.get("local_path"))
        actual_path = StandardDemoCaseService._normalize_path(asset.path)
        if not expected_path or expected_path != actual_path:
            return False
        expected_record_id = str(candidate.get("record_id") or "")
        actual_record_id = str(asset.metadata.get("record_id") or "")
        return bool(expected_record_id and expected_record_id == actual_record_id)

    @staticmethod
    def _normalize_path(value: Any) -> str:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            return ""
        try:
            return str(Path(value).expanduser().resolve(strict=False)).casefold()
        except (OSError, RuntimeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _video_input(candidate: dict[str, Any]) -> InputCreateRequest:
        return InputCreateRequest(
            channel=InputChannel.VIDEO,
            path=str(candidate["local_path"]),
            mime_type="video/mp4",
            metadata={
                "source": "standard_demo_public_proxy",
                "record_id": str(candidate.get("record_id") or ""),
                "source_page_original_link": str(candidate.get("source_page_original_link") or ""),
                "direct_download_link": str(candidate.get("direct_download_link") or ""),
                "fluorescence": candidate.get("fluorescence"),
                "medical_scene": str(candidate.get("medical_scene") or ""),
                "domain_boundary": str(candidate.get("domain_boundary") or ""),
                "standard_demo": True,
                "composite_layout_available": bool(candidate.get("composite_layout_available")),
                "view_layout": str(candidate.get("view_layout") or ""),
            },
        )
