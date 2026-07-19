from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.src.domains.cases.enums import ArtifactKind, InputChannel
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import (
    CaseRecord,
    EvidenceArtifact,
    HospitalIntakeBatchRequest,
    HospitalIntakeFileRequest,
    HospitalIntakeMetadata,
    InputCreateRequest,
)
from backend.src.services.input_service import InputService
from src.core.paths import ensure_dir
from src.io.content_probe import signature_matches_upload_suffix
from src.preprocess.input_validation import validate_input

OFFICIAL_INTAKE_SUFFIXES = {".jpg", ".jpeg", ".mp4"}
SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
REPORT_FILENAME = "hospital_intake_report.json"
REPORT_CSV_FILENAME = "hospital_intake_records.csv"
ARTIFACT_STATUS_FILENAME = "hospital_intake_artifact_status.json"


class HospitalIntakeConflictError(RuntimeError):
    pass


class HospitalIntakeService:
    def __init__(
        self,
        *,
        artifact_root: str | Path,
        repo: CaseRepository,
        input_service: InputService,
    ) -> None:
        self.artifact_root = Path(artifact_root).resolve()
        self.intake_root = ensure_dir(self.artifact_root / "hospital_intake")
        self.repo = repo
        self.input_service = input_service

    def admit_batch(self, request: HospitalIntakeBatchRequest) -> dict[str, Any]:
        batch_token = _safe_token(request.batch_id)
        batch_dir = self.intake_root / batch_token
        report_path = batch_dir / REPORT_FILENAME
        if report_path.exists():
            raise HospitalIntakeConflictError(f"Hospital intake batch already exists: {request.batch_id}")
        ensure_dir(batch_dir)

        batch_blockers = _batch_blockers(request)
        existing_checksums = self._existing_checksums()
        seen_checksums: set[str] = set()
        records = [
            self._inspect_file(
                item,
                request=request,
                position=position,
                existing_checksums=existing_checksums,
                seen_checksums=seen_checksums,
            )
            for position, item in enumerate(request.files, start=1)
        ]
        _apply_pair_quality_gate(records)
        if batch_blockers:
            for record in records:
                record["status"] = "quarantined"
                record["admission_stage"] = "quarantined"
                record["target_domain_flag"] = False
                record["fusion_eligible"] = False
                record["reasons"] = _unique_findings([*record["reasons"], *batch_blockers])

        case_map = self._case_map(request, records)
        for record in records:
            record["platform_case_id"] = case_map.get(record["external_case_id"])

        report = self._report_payload(
            request,
            records=records,
            case_map=case_map,
            report_path=report_path,
            csv_path=batch_dir / REPORT_CSV_FILENAME,
        )
        persisted_cases = self._persist_admitted_cases(request, records, report)
        report["cases"] = persisted_cases
        self._write_report(report)
        artifact_status = self._attach_report_artifact(report, persisted_cases)
        try:
            self._write_artifact_status(report_path.parent, artifact_status)
        except OSError as exc:
            artifact_status["status_persisted"] = False
            artifact_status["failures"] = [
                *artifact_status["failures"],
                {
                    "code": "artifact_status_write_failed",
                    "error_type": type(exc).__name__,
                },
            ]
            artifact_status["status"] = "completed_with_errors"
        report["artifact_attachment"] = artifact_status
        return report

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        try:
            batch_token = _safe_token(batch_id)
        except ValueError:
            return None
        path = self.intake_root / batch_token / REPORT_FILENAME
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("batch_id") != batch_id:
            return None
        artifact_status = self._read_artifact_status(path.parent)
        if artifact_status is not None:
            payload["artifact_attachment"] = artifact_status
        return payload

    def list_batches(self) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        for path in sorted(self.intake_root.glob(f"*/{REPORT_FILENAME}"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            artifact_status = self._read_artifact_status(path.parent)
            batches.append(
                {
                    "batch_id": payload.get("batch_id"),
                    "handover_id": payload.get("handover_id"),
                    "received_at": payload.get("received_at"),
                    "source_organization": payload.get("source_organization"),
                    "summary": payload.get("summary") or {},
                    "artifact_attachment": artifact_status or payload.get("artifact_attachment") or {},
                    "report_path": str(path),
                }
            )
        return batches

    def _inspect_file(
        self,
        item: HospitalIntakeFileRequest,
        *,
        request: HospitalIntakeBatchRequest,
        position: int,
        existing_checksums: set[str],
        seen_checksums: set[str],
    ) -> dict[str, Any]:
        reasons: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        path = Path(item.path).expanduser().resolve()
        suffix = ".jpeg" if path.suffix.lower() == ".jpeg" else path.suffix.lower()
        checksum = ""
        size_bytes = 0
        metadata: dict[str, Any] = {}

        controlled_path = _is_within(path, self.artifact_root)
        if not controlled_path:
            reasons.append(_finding("path_outside_controlled_storage", "文件不在平台受控数据目录中。"))
        elif not path.is_file():
            reasons.append(_finding("file_missing", "文件不存在或不是常规文件。"))
        elif suffix not in OFFICIAL_INTAKE_SUFFIXES:
            reasons.append(_finding("unsupported_official_format", "医院准入仅接受 JPEG 与 MP4。"))
        else:
            try:
                size_bytes = path.stat().st_size
                checksum = _sha256_file(path)
                if checksum in seen_checksums:
                    reasons.append(_finding("duplicate_in_batch", "同一批次包含重复文件。"))
                if checksum in existing_checksums:
                    reasons.append(_finding("duplicate_previous_batch", "该文件已存在于历史准入批次。"))
                seen_checksums.add(checksum)

                signature_ok, signature_reason, probe = signature_matches_upload_suffix(path, suffix)
                metadata["content_probe"] = probe
                expected_mime = "video/mp4" if suffix == ".mp4" else "image/jpeg"
                if signature_ok and probe.get("detected_mime") != expected_mime:
                    signature_ok = False
                    signature_reason = f"文件内容必须为 {expected_mime}。"
                if not signature_ok:
                    reasons.append(_finding("content_signature_mismatch", signature_reason))
                else:
                    summary = validate_input(path)
                    metadata.update(summary.metadata)
                    warnings.extend(_normalized_warnings(summary.warnings))
                    jpeg_decode_failed = suffix in {".jpg", ".jpeg"} and (
                        bool(summary.metadata.get("image_probe_error"))
                        or not summary.metadata.get("width")
                        or not summary.metadata.get("height")
                    )
                    if not summary.accepted or jpeg_decode_failed:
                        reasons.append(_finding("input_unreadable", summary.reason or "文件无法解码。"))
            except OSError:
                checksum = ""
                reasons.append(_finding("file_read_failed", "文件在准入检查期间无法稳定读取。"))

        if not SAFE_CASE_ID.fullmatch(item.external_case_id):
            reasons.append(_finding("invalid_deidentified_case_id", "脱敏病例编号格式无效。"))
        if item.channel == InputChannel.VIDEO and suffix != ".mp4":
            reasons.append(_finding("video_channel_requires_mp4", "视频通道必须使用 MP4 文件。"))
        if item.channel in {
            InputChannel.WHITE_LIGHT,
            InputChannel.FLUORESCENCE,
        } and suffix not in {".jpg", ".jpeg"}:
            reasons.append(_finding("image_channel_requires_jpeg", "白光与荧光通道必须使用 JPEG 文件。"))
        if item.channel == InputChannel.SEQUENCE:
            reasons.append(
                _finding(
                    "sequence_channel_not_supported",
                    "医院批次准入暂不接受独立帧序列通道。",
                )
            )
        if item.channel_relationship == "synchronized_pair" and not str(item.pair_id or "").strip():
            reasons.append(_finding("pair_id_missing", "同步白光/荧光配对缺少 pair_id。"))
        if item.channel_relationship == "unknown":
            warnings.append(_finding("channel_relationship_unknown", "通道关系待医院或设备团队确认。"))
        if not item.missing_fields:
            missing_fields = _inferred_missing_fields(item.metadata)
        else:
            missing_fields = sorted({str(value).strip() for value in item.missing_fields if str(value).strip()})
        if missing_fields:
            warnings.append(
                _finding(
                    "acquisition_metadata_incomplete",
                    "采集元数据存在缺失字段。",
                    fields=missing_fields,
                )
            )

        status = "quarantined" if reasons else "admitted"
        target_domain_flag = bool(request.target_condition_confirmed and status == "admitted")
        return {
            "record_id": f"{_safe_token(request.batch_id)}_{position:04d}",
            "external_case_id": item.external_case_id,
            "platform_case_id": None,
            "path": str(path),
            "original_filename": item.original_filename or path.name,
            "suffix": suffix,
            "size_bytes": size_bytes,
            "sha256": checksum,
            "channel": item.channel.value,
            "acquisition_mode": item.acquisition_mode,
            "channel_relationship": item.channel_relationship,
            "pair_id": item.pair_id,
            "metadata": {**item.metadata, **metadata},
            "missing_fields": missing_fields,
            "status": status,
            "admission_stage": (
                "target_registry_ready"
                if target_domain_flag
                else ("engineering_analysis_ready" if status == "admitted" else "quarantined")
            ),
            "reasons": _unique_findings(reasons),
            "warnings": _unique_findings(warnings),
            "target_domain_flag": target_domain_flag,
            "review_state": "review_required",
            "label_type": "unlabeled",
            "training_eligible": False,
            "fusion_eligible": False,
        }

    def _case_map(self, request: HospitalIntakeBatchRequest, records: list[dict[str, Any]]) -> dict[str, str]:
        admitted_case_ids = sorted(
            {str(record["external_case_id"]) for record in records if record["status"] == "admitted"}
        )
        return {
            external_case_id: _platform_case_id(request.source_organization, external_case_id)
            for external_case_id in admitted_case_ids
        }

    def _report_payload(
        self,
        request: HospitalIntakeBatchRequest,
        *,
        records: list[dict[str, Any]],
        case_map: dict[str, str],
        report_path: Path,
        csv_path: Path,
    ) -> dict[str, Any]:
        admitted_count = sum(record["status"] == "admitted" for record in records)
        quarantined_count = len(records) - admitted_count
        target_count = sum(bool(record["target_domain_flag"]) for record in records)
        return {
            "schema_version": "osteo-vision-hospital-intake-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "batch_id": request.batch_id,
            "handover_id": request.handover_id,
            "source_type": "institutional_handover",
            "source_organization": request.source_organization,
            "received_by": request.received_by,
            "received_at": request.received_at.isoformat(),
            "authorization_status": request.authorization_status,
            "usage_scope": request.usage_scope,
            "deidentification_confirmed": request.deidentification_confirmed,
            "deidentification_method": request.deidentification_method,
            "mapping_held_by_institution": request.mapping_held_by_institution,
            "target_condition_confirmed": request.target_condition_confirmed,
            "case_map": case_map,
            "summary": {
                "status": "completed_with_quarantine" if quarantined_count else "completed",
                "file_count": len(records),
                "admitted_count": admitted_count,
                "quarantined_count": quarantined_count,
                "target_domain_source_count": target_count,
                "training_eligible_count": 0,
                "case_count": len(case_map),
            },
            "records": records,
            "cases": [],
            "artifact_attachment": {
                "status": "pending",
                "status_path": str(report_path.parent / ARTIFACT_STATUS_FILENAME),
                "expected_case_count": len(case_map),
                "attached_case_count": 0,
                "attached_case_ids": [],
                "failures": [],
                "status_persisted": False,
            },
            "report_path": str(report_path),
            "csv_path": str(csv_path),
            "medical_boundary": (
                "准入状态只表示文件、来源和交接条件通过工程质量门。所有样本保持待复核，"
                "真实目标域来源不会自动生成临床标签或训练资格。"
            ),
        }

    def _write_report(self, report: dict[str, Any]) -> None:
        report_path = Path(str(report["report_path"]))
        csv_path = Path(str(report["csv_path"]))
        report_temp = report_path.with_name(f".{report_path.name}.{uuid4().hex}.tmp")
        csv_temp = csv_path.with_name(f".{csv_path.name}.{uuid4().hex}.tmp")
        fieldnames = [
            "record_id",
            "external_case_id",
            "platform_case_id",
            "original_filename",
            "path",
            "sha256",
            "size_bytes",
            "channel",
            "acquisition_mode",
            "channel_relationship",
            "pair_id",
            "status",
            "admission_stage",
            "target_domain_flag",
            "review_state",
            "training_eligible",
            "fusion_eligible",
            "reason_codes",
            "warning_codes",
        ]
        try:
            with csv_temp.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for record in report["records"]:
                    writer.writerow(
                        {
                            **{field: record.get(field) for field in fieldnames},
                            "reason_codes": ";".join(item["code"] for item in record["reasons"]),
                            "warning_codes": ";".join(item["code"] for item in record["warnings"]),
                        }
                    )
            report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            csv_temp.replace(csv_path)
            report_temp.replace(report_path)
        finally:
            csv_temp.unlink(missing_ok=True)
            report_temp.unlink(missing_ok=True)

    def _persist_admitted_cases(
        self,
        request: HospitalIntakeBatchRequest,
        records: list[dict[str, Any]],
        report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        persisted: list[dict[str, Any]] = []
        admitted = [record for record in records if record["status"] == "admitted"]
        external_case_ids = sorted({str(record["external_case_id"]) for record in admitted})
        existing_cases: dict[str, CaseRecord | None] = {}
        for external_case_id in external_case_ids:
            platform_case_id = _platform_case_id(request.source_organization, external_case_id)
            case = self.repo.get(platform_case_id)
            if (
                case is not None
                and case.intake_metadata
                and (
                    case.intake_metadata.external_case_id != external_case_id
                    or case.intake_metadata.source_organization != request.source_organization
                )
            ):
                raise HospitalIntakeConflictError(f"Platform case id collision: {platform_case_id}")
            existing_cases[external_case_id] = case

        for external_case_id in external_case_ids:
            case_records = [record for record in admitted if record["external_case_id"] == external_case_id]
            platform_case_id = str(case_records[0]["platform_case_id"])
            case = existing_cases[external_case_id]
            is_new = case is None
            if case is None:
                case = CaseRecord(
                    case_id=platform_case_id,
                    title=f"医院数据病例 {platform_case_id[-6:].upper()}",
                )

            intake_metadata = _merged_intake_metadata(
                case.intake_metadata,
                request=request,
                external_case_id=external_case_id,
                report_path=str(report["report_path"]),
            )
            input_requests = [
                InputCreateRequest(
                    channel=InputChannel(record["channel"]),
                    path=record["path"],
                    mime_type="video/mp4" if record["suffix"] == ".mp4" else "image/jpeg",
                    metadata={
                        **record["metadata"],
                        "admission_status": record["status"],
                        "source_type": "institutional_handover",
                        "source_organization": request.source_organization,
                        "batch_id": request.batch_id,
                        "intake_record_id": record["record_id"],
                        "handover_id": request.handover_id,
                        "external_case_id": external_case_id,
                        "original_filename": record["original_filename"],
                        "sha256": record["sha256"],
                        "size_bytes": record["size_bytes"],
                        "acquisition_mode": record["acquisition_mode"],
                        "channel_relationship": record["channel_relationship"],
                        "pair_id": record["pair_id"],
                        "authorization_status": request.authorization_status,
                        "usage_scope": request.usage_scope,
                        "deidentification_confirmed": request.deidentification_confirmed,
                        "target_domain_flag": record["target_domain_flag"],
                        "review_state": "review_required",
                        "label_type": "unlabeled",
                        "training_eligible": False,
                    },
                )
                for record in case_records
                if not _case_contains_intake_record(case, request.batch_id, record)
            ]
            updated = (
                self.input_service.add_inputs(case, input_requests, replace_existing_channels=False)
                if input_requests
                else case
            )
            updated = updated.model_copy(update={"intake_metadata": intake_metadata})
            saved = self.repo.create(updated) if is_new else self.repo.save(updated)
            persisted.append(
                {
                    "external_case_id": external_case_id,
                    "platform_case_id": saved.case_id,
                    "input_count_added": len(input_requests),
                    "case_version": saved.version,
                }
            )
        return persisted

    def _attach_report_artifact(self, report: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
        status: dict[str, Any] = {
            "status": "completed",
            "status_path": str(Path(str(report["report_path"])).parent / ARTIFACT_STATUS_FILENAME),
            "expected_case_count": len(cases),
            "attached_case_count": 0,
            "attached_case_ids": [],
            "failures": [],
            "status_persisted": True,
        }
        if not cases:
            return status
        report_path = Path(str(report["report_path"]))
        try:
            checksum = _sha256_file(report_path)
        except OSError as exc:
            status["status"] = "completed_with_errors"
            status["failures"] = [
                {
                    "code": "report_checksum_failed",
                    "error_type": type(exc).__name__,
                }
            ]
            return status
        for item in cases:
            platform_case_id = str(item["platform_case_id"])
            try:
                case = self.repo.get(platform_case_id)
                if case is None:
                    raise LookupError("Persisted intake case is unavailable")
                artifacts = [
                    artifact
                    for artifact in case.artifacts
                    if not (
                        artifact.kind == ArtifactKind.HOSPITAL_INTAKE_MANIFEST and artifact.path == str(report_path)
                    )
                ]
                artifacts.append(
                    EvidenceArtifact(
                        artifact_id=f"artifact_{uuid4().hex[:10]}",
                        case_id=case.case_id,
                        kind=ArtifactKind.HOSPITAL_INTAKE_MANIFEST,
                        path=str(report_path),
                        checksum=checksum,
                    )
                )
                self.repo.save(case.model_copy(update={"artifacts": artifacts}))
            except Exception as exc:
                status["status"] = "completed_with_errors"
                status["failures"].append(
                    {
                        "code": "case_artifact_attachment_failed",
                        "platform_case_id": platform_case_id,
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            status["attached_case_ids"].append(platform_case_id)
            status["attached_case_count"] += 1
        return status

    def _write_artifact_status(
        self,
        batch_dir: Path,
        status: dict[str, Any],
    ) -> None:
        path = batch_dir / ARTIFACT_STATUS_FILENAME
        temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

    def _read_artifact_status(self, batch_dir: Path) -> dict[str, Any] | None:
        path = batch_dir / ARTIFACT_STATUS_FILENAME
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _existing_checksums(self) -> set[str]:
        checksums: set[str] = set()
        for path in self.intake_root.glob(f"*/{REPORT_FILENAME}"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            records = payload.get("records") if isinstance(payload, dict) else None
            if not isinstance(records, list):
                continue
            checksums.update(
                str(record.get("sha256") or "")
                for record in records
                if isinstance(record, dict) and record.get("status") == "admitted" and record.get("sha256")
            )
        return checksums


def _batch_blockers(request: HospitalIntakeBatchRequest) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if request.authorization_status != "approved":
        findings.append(_finding("authorization_not_approved", "机构授权状态尚未批准。"))
    if not request.deidentification_confirmed:
        findings.append(_finding("deidentification_unconfirmed", "脱敏状态尚未确认。"))
    if not request.mapping_held_by_institution:
        findings.append(_finding("institution_mapping_not_retained", "病例映射表保管责任尚未确认。"))
    return findings


def _apply_pair_quality_gate(records: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        if record["channel_relationship"] != "synchronized_pair" or record["status"] != "admitted":
            continue
        pair_id = str(record.get("pair_id") or "").strip()
        if pair_id:
            groups.setdefault((record["external_case_id"], pair_id), []).append(record)
    for pair_records in groups.values():
        channels = {record["channel"] for record in pair_records}
        expected = {InputChannel.WHITE_LIGHT.value, InputChannel.FLUORESCENCE.value}
        if len(pair_records) != 2 or channels != expected:
            for record in pair_records:
                record["status"] = "quarantined"
                record["admission_stage"] = "quarantined"
                record["target_domain_flag"] = False
                record["reasons"] = _unique_findings(
                    [
                        *record["reasons"],
                        _finding(
                            "synchronized_pair_incomplete",
                            "同步配对必须同时包含白光与荧光 JPEG。",
                        ),
                    ]
                )
            continue
        sizes = {(record["metadata"].get("width"), record["metadata"].get("height")) for record in pair_records}
        fusion_eligible = len(sizes) == 1 and None not in next(iter(sizes), (None, None))
        for record in pair_records:
            record["fusion_eligible"] = fusion_eligible
            if not fusion_eligible:
                record["warnings"] = _unique_findings(
                    [
                        *record["warnings"],
                        _finding(
                            "paired_dimensions_mismatch",
                            "同步配对尺寸不一致，像素级融合保持待确认。",
                        ),
                    ]
                )


def _merged_intake_metadata(
    current: HospitalIntakeMetadata | None,
    *,
    request: HospitalIntakeBatchRequest,
    external_case_id: str,
    report_path: str,
) -> HospitalIntakeMetadata:
    batch_ids = list(current.batch_ids) if current else []
    handover_ids = list(current.handover_ids) if current else []
    report_paths = list(current.report_paths) if current else []
    for values, value in (
        (batch_ids, request.batch_id),
        (handover_ids, request.handover_id),
        (report_paths, report_path),
    ):
        if value not in values:
            values.append(value)
    return HospitalIntakeMetadata(
        source_organization=request.source_organization,
        external_case_id=external_case_id,
        batch_ids=batch_ids,
        handover_ids=handover_ids,
        authorization_status=request.authorization_status,
        usage_scope=request.usage_scope,
        deidentification_confirmed=request.deidentification_confirmed,
        deidentification_method=request.deidentification_method,
        mapping_held_by_institution=request.mapping_held_by_institution,
        target_condition_confirmed=request.target_condition_confirmed,
        admission_status=(
            "target_registry_ready" if request.target_condition_confirmed else "engineering_analysis_ready"
        ),
        report_paths=report_paths,
    )


def _normalized_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _finding(
            str(item.get("code") or "input_warning"),
            _intake_warning_message(
                str(item.get("code") or "input_warning"),
                str(item.get("message") or "输入存在质量提示。"),
            ),
            **dict(item.get("details") or {}),
        )
        for item in warnings
    ]


def _intake_warning_message(code: str, fallback: str) -> str:
    messages = {
        "official_image_format_mismatch": "图像可读取，但文件不符合赛题设备要求的 JPEG 规格。",
        "official_image_resolution_mismatch": "图像可读取，但分辨率不符合赛题设备的 3840x2160 规格。",
        "official_video_resolution_mismatch": "视频可读取，但分辨率不符合赛题设备的 3840x2160 规格。",
        "official_video_rotation_present": "视频包含旋转元数据，分析前需要统一画面方向。",
        "official_video_codec_unverified": "视频编码超出平台当前完成验证的编码集合。",
        "ffprobe_unavailable": "当前环境无法使用 ffprobe，编码、码率和旋转信息检查能力受限。",
    }
    return messages.get(code, fallback)


def _inferred_missing_fields(metadata: dict[str, Any]) -> list[str]:
    expected = ["device", "icg_time_sec", "exposure", "gain", "illumination"]
    return [field for field in expected if _metadata_value_is_missing(metadata.get(field))]


def _metadata_value_is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    return False


def _case_contains_intake_record(
    case: CaseRecord,
    batch_id: str,
    record: dict[str, Any],
) -> bool:
    record_id = str(record.get("record_id") or "")
    checksum = str(record.get("sha256") or "")
    channel = str(record.get("channel") or "")
    for asset in case.inputs:
        metadata = asset.metadata
        if metadata.get("batch_id") != batch_id:
            continue
        if record_id and metadata.get("intake_record_id") == record_id:
            return True
        if checksum and metadata.get("sha256") == checksum and asset.channel.value == channel:
            return True
    return False


def _finding(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


def _unique_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in findings:
        code = str(item.get("code") or "unknown")
        if code in seen:
            continue
        seen.add(code)
        unique.append(item)
    return unique


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    if len(token) < 3:
        raise ValueError("Hospital intake identifier is invalid")
    return token[:64]


def _platform_case_id(source_organization: str, external_case_id: str) -> str:
    digest = hashlib.sha256(f"{source_organization.strip()}|{external_case_id.strip()}".encode("utf-8")).hexdigest()
    return f"case_{digest[:12]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
