"""Admit one hospital JPEG/MP4 handover batch from a UTF-8 JSON manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.core.settings import load_settings  # noqa: E402
from backend.src.domains.cases.repository import build_case_repository  # noqa: E402
from backend.src.domains.cases.schemas import HospitalIntakeBatchRequest  # noqa: E402
from backend.src.services.hospital_intake_service import (  # noqa: E402
    HospitalIntakeConflictError,
    HospitalIntakeService,
)
from backend.src.services.input_service import InputService  # noqa: E402

EXIT_OK = 0
EXIT_INVALID_MANIFEST = 2
EXIT_BATCH_CONFLICT = 3
EXIT_PROCESSING_ERROR = 4


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("从 UTF-8 JSON manifest 执行医院 JPEG/MP4 批次准入，输出准入 JSON/CSV 报告并登记通过的病例。"),
        epilog="退出码：0=完成，2=manifest 无效，3=批次编号冲突，4=处理失败。",
    )
    parser.add_argument("--manifest", required=True, help="医院批次 JSON manifest 路径。")
    parser.add_argument(
        "--artifact-root",
        help="受控数据与准入报告根目录；默认读取 OSTEO_ARTIFACT_ROOT 或项目配置。",
    )
    parser.add_argument(
        "--case-store",
        help="病例存储路径；覆盖 artifact root 时默认使用其下的 cases.sqlite。",
    )
    parser.add_argument(
        "--case-store-backend",
        choices=("json", "sqlite", "sqlite3"),
        help="病例存储后端；未指定时按配置或文件扩展名推断。",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest).expanduser().resolve()
    try:
        request = _load_request(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        _write_error("invalid_manifest", str(exc), manifest_path=str(manifest_path))
        return EXIT_INVALID_MANIFEST

    settings = load_settings()
    artifact_root = (
        Path(args.artifact_root).expanduser().resolve() if args.artifact_root else settings.artifact_root.resolve()
    )
    if args.case_store:
        case_store_path = Path(args.case_store).expanduser().resolve()
    elif args.artifact_root:
        case_store_path = artifact_root / "cases.sqlite"
    else:
        case_store_path = settings.case_store_path.resolve()
    repository_backend = args.case_store_backend
    if repository_backend is None and not args.case_store and not args.artifact_root:
        repository_backend = settings.case_store_backend

    try:
        repo = build_case_repository(case_store_path, repository_backend)
        service = HospitalIntakeService(
            artifact_root=artifact_root,
            repo=repo,
            input_service=InputService(),
        )
        report = service.admit_batch(request)
    except HospitalIntakeConflictError as exc:
        _write_error("batch_conflict", str(exc), batch_id=request.batch_id)
        return EXIT_BATCH_CONFLICT
    except ValueError as exc:
        _write_error("invalid_manifest", str(exc), batch_id=request.batch_id)
        return EXIT_INVALID_MANIFEST
    except Exception as exc:
        _write_error("processing_error", str(exc), batch_id=request.batch_id)
        return EXIT_PROCESSING_ERROR

    result = _build_result(report, case_store_path=case_store_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


def _build_result(report: dict[str, Any], *, case_store_path: Path) -> dict[str, Any]:
    summary = dict(report.get("summary") or {})
    artifact_attachment = dict(report.get("artifact_attachment") or {})
    attachment_status = str(artifact_attachment.get("status") or "unknown")
    status = (
        "completed_with_errors"
        if attachment_status == "completed_with_errors"
        else summary.get("status") or "completed"
    )
    return {
        "status": status,
        "batch_id": report.get("batch_id"),
        "admitted_count": summary.get("admitted_count", 0),
        "quarantined_count": summary.get("quarantined_count", 0),
        "case_count": summary.get("case_count", 0),
        "report_path": report.get("report_path"),
        "csv_path": report.get("csv_path"),
        "case_store_path": str(case_store_path),
        "platform_case_ids": [
            item.get("platform_case_id")
            for item in report.get("cases") or []
            if isinstance(item, dict) and item.get("platform_case_id")
        ],
        "artifact_attachment": artifact_attachment,
        "medical_boundary": report.get("medical_boundary"),
    }


def _load_request(manifest_path: Path) -> HospitalIntakeBatchRequest:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hospital intake manifest root must be a JSON object.")
    normalized = dict(payload)
    files = normalized.get("files")
    if isinstance(files, list):
        normalized["files"] = [
            _resolve_file_path(item, manifest_path.parent) if isinstance(item, dict) else item for item in files
        ]
    return HospitalIntakeBatchRequest.model_validate(normalized)


def _resolve_file_path(item: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    normalized = dict(item)
    raw_path = normalized.get("path")
    if isinstance(raw_path, str) and raw_path.strip():
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = manifest_dir / path
        normalized["path"] = str(path.resolve())
    return normalized


def _write_error(code: str, message: str, **details: Any) -> None:
    payload = {"status": "failed", "error": {"code": code, "message": message, "details": details}}
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _configure_cli_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


if __name__ == "__main__":
    _configure_cli_streams()
    raise SystemExit(main())
