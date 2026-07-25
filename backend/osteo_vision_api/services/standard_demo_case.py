from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.osteo_vision_api.domains.cases.enums import InputChannel
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
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
STANDARD_DEMO_VERSION = 5


class StandardDemoCaseService:
    """Creates one deterministic, non-target-domain case for local demonstrations."""

    def __init__(
        self,
        repo: CaseRepository,
        input_service: InputService,
        video_library: VideoLibraryService,
        multichannel_video: MultichannelVideoService | None = None,
    ) -> None:
        self.repo = repo
        self.input_service = input_service
        self.video_library = video_library
        self.multichannel_video = multichannel_video

    def ensure_case(self) -> CaseRecord:
        existing = self.repo.get(STANDARD_DEMO_CASE_ID)
        if (
            existing is not None
            and existing.review_summary.get("standard_demo_version") == STANDARD_DEMO_VERSION
            and existing.review_summary.get("multichannel_session_status") in {"ready", "degraded", "blocked"}
        ):
            return existing

        if existing is None:
            now = datetime.now(timezone.utc)
            case = CaseRecord(
                case_id=STANDARD_DEMO_CASE_ID,
                title="标准演示病例 · OFDVDnet 三视图荧光代理",
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
            case = existing.model_copy(
                update={
                    "title": "标准演示病例 · OFDVDnet 三视图荧光代理",
                    "inputs": retained_inputs,
                    "review_summary": {
                        **existing.review_summary,
                        "standard_demo_version": STANDARD_DEMO_VERSION,
                        "video_source_policy": "ofdvdnet_public_composite_proxy",
                    },
                }
            )
        candidate = self._selected_video_candidate()
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
        candidates = self.video_library.list_candidates(accepted_only=True, limit=500).get("items", [])
        readable = [item for item in candidates if isinstance(item, dict) and item.get("system_readable")]
        if not readable:
            return None
        return next(
            (item for item in readable if item.get("record_id") == STANDARD_DEMO_VIDEO_RECORD_ID),
            readable[0],
        )

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
