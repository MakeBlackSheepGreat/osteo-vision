from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFESTS = [
    ROOT / "research/datasets/public-candidates/patient_conditioning_starter_20260717/"
    "patient_conditioning_starter_manifest.json",
    ROOT / "research/datasets/public-candidates/three_priority_zenodo_20260717/" "three_priority_zenodo_manifest.json",
    ROOT / "research/datasets/public-candidates/navigation_starter_20260717/" "navigation_starter_manifest.json",
    ROOT / "research/datasets/public-candidates/patient_conditioning_gap_audit_20260718/"
    "patient_conditioning_gap_audit_manifest.json",
    ROOT / "research/datasets/public-candidates/bone_activity_gap_20260718/" "bone_activity_gap_manifest.json",
    ROOT / "research/datasets/public-candidates/navigation_cbct_stl_audit_20260718/"
    "navigation_cbct_stl_manifest.json",
    ROOT / "research/datasets/public-candidates/" "d051_mronj_imaging_mass_cytometry_starter_20260718/manifest.json",
    ROOT / "research/datasets/public-candidates/c3vd_l2_proxy_20260719/" "c3vd_l2_proxy_manifest.json",
    ROOT / "research/datasets/public-candidates/mmdental_patient_context_starter_20260719/"
    "mmdental_patient_context_starter_manifest.json",
    ROOT / "research/datasets/public-candidates/d090_breast_sentinel_icg_video_20260719/"
    "d090_breast_sentinel_icg_video_manifest.json",
    ROOT / "research/datasets/public-candidates/d091_icg_hepatic_dynamic_proxy_20260719/"
    "d091_icg_hepatic_dynamic_proxy_manifest.json",
    ROOT / "research/datasets/public-candidates/pmcanalseg_navigation_starter_20260719/"
    "pmcanalseg_navigation_starter_manifest.json",
    ROOT / "research/datasets/public-candidates/d093_mronj_spect_ct_figures_20260719/"
    "d093_mronj_spect_ct_figures_manifest.json",
    ROOT / "research/datasets/public-candidates/d094_clinrad_orn_context_20260719/"
    "d094_clinrad_orn_context_manifest.json",
    ROOT / "research/datasets/public-candidates/d095_mdacc_orn_time_to_event_20260719/"
    "d095_mdacc_orn_time_to_event_manifest.json",
]

PROVENANCE_CONTRACT_FIELDS = (
    "source_page",
    "download_access",
    "license",
    "license_review_status",
    "domain_tier",
    "modality",
    "labels",
    "sample_or_patient_count",
    "clinical_variables",
    "recommended_use",
    "local_path",
    "size_bytes",
    "sha256",
    "download_audit",
    "target_domain_flag",
    "training_eligible",
    "review_state",
    "data_boundary",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_LIMITATION_STATUS_MARKERS = (
    "author_request",
    "controlled",
    "large_sample_skipped",
    "metadata_only",
    "restricted",
    "signup_required",
    "unavailable",
)
_ABSENCE_MARKERS = (
    " cannot ",
    " do not ",
    " does not ",
    " no ",
    " unavailable",
    " without ",
)
_CLINICAL_SCOPE_MARKERS = (
    "animal",
    "case",
    "clinical",
    "ex vivo",
    "intraoperative",
    "jaw",
    "patient",
    "phantom",
    "synthetic",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(payload: dict[str, Any]) -> list[Any]:
    datasets = payload.get("datasets")
    if isinstance(datasets, list):
        return datasets
    records = payload.get("records")
    return records if isinstance(records, list) else []


def _file_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    if "local_path" in record:
        return [record]
    entries: list[dict[str, Any]] = []
    for key in ("local_artifacts", "assets", "metadata_files", "local_files"):
        value = record.get(key)
        if isinstance(value, list):
            entries.extend(item for item in value if isinstance(item, dict))
    return entries


def _entry_path(manifest_path: Path, entry: dict[str, Any]) -> Path | None:
    raw_path = entry.get("local_path") or entry.get("relative_path") or entry.get("path")
    if not _meaningful(raw_path):
        return None
    path = Path(str(raw_path))
    return path if path.is_absolute() else manifest_path.parent / path


def _meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _first_value(record: dict[str, Any], aliases: tuple[str, ...]) -> tuple[Any, str] | tuple[None, None]:
    for alias in aliases:
        value = record.get(alias)
        if _meaningful(value):
            return value, alias
    return None, None


def _http_urls(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip().lower().startswith(("https://", "http://"))]


def _first_http_source(record: dict[str, Any], aliases: tuple[str, ...]) -> tuple[list[str], str] | tuple[None, None]:
    for alias in aliases:
        urls = _http_urls(record.get(alias))
        if urls:
            return urls, alias
    return None, None


def _download_access_source(record: dict[str, Any], entries: list[dict[str, Any]]) -> str | None:
    _, alias = _first_http_source(
        record,
        ("direct_download_url", "direct_download_urls", "download_url", "url"),
    )
    if alias:
        return alias
    for entry in entries:
        _, entry_alias = _first_http_source(
            entry,
            ("direct_download_url", "direct_download_urls", "download_url", "url"),
        )
        if entry_alias:
            return f"file_entry.{entry_alias}"
    _, limitation_alias = _first_value(
        record,
        (
            "access_limitation",
            "access_limitation_reason",
            "data_availability",
            "governance_state",
        ),
    )
    if limitation_alias:
        return limitation_alias
    if _is_limitation_status(record.get("download_status")):
        return "download_status"
    return None


def _is_limitation_status(value: Any) -> bool:
    status = str(value or "").strip().lower()
    return any(marker in status for marker in _LIMITATION_STATUS_MARKERS)


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _download_audit_source(payload: dict[str, Any], record: dict[str, Any]) -> str | None:
    for alias in ("downloaded_at_utc", "download_timestamp", "acquired_at_utc"):
        if _valid_timestamp(record.get(alias)):
            return alias
    for alias in ("downloaded_at_utc", "generated_at_utc"):
        if _valid_timestamp(payload.get(alias)):
            return f"manifest.{alias}"
    if _is_limitation_status(record.get("download_status")):
        return "download_status"
    return None


def _dataset_key(record: dict[str, Any]) -> str | None:
    for alias in ("dataset_id", "candidate_id", "dataset_name"):
        value = record.get(alias)
        if _meaningful(value):
            return f"{alias}:{value}"
    return None


def _clinical_context_by_dataset(records: list[Any]) -> dict[str, str]:
    contexts: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        role = str(record.get("file_role") or "").lower()
        if "clinical_context" not in role:
            continue
        _, source = _first_value(record, ("clinical_variables", "labels"))
        key = _dataset_key(record)
        if key and source:
            contexts[key] = source
    return contexts


def _clinical_variable_source(record: dict[str, Any], clinical_contexts: dict[str, str]) -> str | None:
    _, alias = _first_value(record, ("clinical_variables", "patient_variables"))
    if alias:
        return alias
    _, reason_alias = _first_value(
        record,
        (
            "clinical_variables_unavailable_reason",
            "clinical_variables_status",
            "patient_variables_unavailable_reason",
        ),
    )
    if reason_alias:
        return reason_alias
    dataset_key = _dataset_key(record)
    if dataset_key in clinical_contexts:
        return f"dataset_clinical_context.{clinical_contexts[dataset_key]}"
    boundary = f" {str(record.get('data_boundary') or '').strip().lower()} "
    has_absence = any(marker in boundary for marker in _ABSENCE_MARKERS)
    has_clinical_scope = any(marker in boundary for marker in _CLINICAL_SCOPE_MARKERS)
    if has_absence and has_clinical_scope:
        return "data_boundary"
    return None


def _field_sources(
    payload: dict[str, Any],
    record: dict[str, Any],
    entries: list[dict[str, Any]],
    clinical_contexts: dict[str, str],
) -> dict[str, str | None]:
    _, source_page = _first_http_source(
        record,
        ("source_page_url", "source_url", "landing_page_url"),
    )
    _, license_source = _first_value(record, ("license", "licence"))
    _, license_review_source = _first_value(
        record,
        ("license_review_status", "license_status", "governance_state", "license_expected"),
    )
    if not license_review_source:
        _, license_review_source = _first_value(record, ("review_state",))
    _, domain_source = _first_value(
        record,
        ("domain_tier", "domain", "priority_target", "medical_scene"),
    )
    if not domain_source and isinstance(record.get("target_domain_flag"), bool):
        if _meaningful(record.get("data_boundary")):
            domain_source = "target_domain_flag+data_boundary"
    _, modality_source = _first_value(record, ("modality", "modalities", "medical_scene"))
    _, labels_source = _first_value(
        record,
        ("labels", "segmentation_labels", "labels_or_coordinates", "fluorescence"),
    )
    if not labels_source:
        _, labels_source = _first_value(record, ("priority_target",))
    _, sample_source = _first_value(record, ("patient_count", "sample_count"))
    if not sample_source:
        _, sample_source = _first_value(
            record,
            (
                "patient_count_unavailable_reason",
                "sample_count_unavailable_reason",
                "sample_count_status",
                "sample_count_detail",
            ),
        )
    if not sample_source and entries:
        sample_source = "local_file_count"
    _, recommended_use_source = _first_value(record, ("recommended_use", "intended_use"))
    _, review_state_source = _first_value(record, ("review_state", "review_status"))
    _, data_boundary_source = _first_value(record, ("data_boundary", "use_boundary"))

    all_paths = bool(entries) and all(
        _meaningful(entry.get("local_path") or entry.get("relative_path") or entry.get("path")) for entry in entries
    )
    all_sizes = bool(entries) and all(_meaningful(entry.get("size_bytes")) for entry in entries)
    all_hashes = bool(entries) and all(
        isinstance(entry.get("sha256"), str) and _SHA256_PATTERN.fullmatch(str(entry["sha256"]).strip()) is not None
        for entry in entries
    )
    return {
        "source_page": source_page,
        "download_access": _download_access_source(record, entries),
        "license": license_source,
        "license_review_status": license_review_source,
        "domain_tier": domain_source,
        "modality": modality_source,
        "labels": labels_source,
        "sample_or_patient_count": sample_source,
        "clinical_variables": _clinical_variable_source(record, clinical_contexts),
        "recommended_use": recommended_use_source,
        "local_path": "file_entries" if all_paths else None,
        "size_bytes": "file_entries" if all_sizes else None,
        "sha256": "file_entries" if all_hashes else None,
        "download_audit": _download_audit_source(payload, record),
        "target_domain_flag": ("target_domain_flag" if isinstance(record.get("target_domain_flag"), bool) else None),
        "training_eligible": ("training_eligible" if isinstance(record.get("training_eligible"), bool) else None),
        "review_state": review_state_source,
        "data_boundary": data_boundary_source,
    }


def _empty_result(manifest_path: Path, code: str, message: str) -> dict[str, Any]:
    return {
        "manifest_path": str(manifest_path),
        "status": "failed",
        "record_count": 0,
        "verified_record_count": 0,
        "file_count": 0,
        "verified_file_count": 0,
        "total_size_bytes": 0,
        "provenance_contract_fields": list(PROVENANCE_CONTRACT_FIELDS),
        "provenance_coverage": {field: 0 for field in PROVENANCE_CONTRACT_FIELDS},
        "provenance_source_aliases": {},
        "errors": [{"code": code, "message": message}],
    }


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if not manifest_path.is_file():
        return _empty_result(manifest_path, "manifest_missing", "Manifest file does not exist.")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _empty_result(manifest_path, "manifest_json_invalid", str(exc))
    if not isinstance(payload, dict):
        return _empty_result(
            manifest_path,
            "manifest_payload_invalid",
            "Manifest root must be a JSON object.",
        )
    records = _records(payload)
    if not records:
        return _empty_result(
            manifest_path,
            "manifest_records_invalid",
            "records or datasets must be a non-empty list.",
        )

    total_size = 0
    file_count = 0
    verified_file_count = 0
    verified_record_count = 0
    coverage = Counter[str]()
    alias_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    clinical_contexts = _clinical_context_by_dataset(records)
    for index, record in enumerate(records):
        record_error_start = len(errors)
        if not isinstance(record, dict):
            errors.append({"code": "record_invalid", "record_index": index})
            continue

        entries = _file_entries(record)
        sources = _field_sources(payload, record, entries, clinical_contexts)
        missing_fields = [field for field, source in sources.items() if source is None]
        for field, source in sources.items():
            if source is not None:
                coverage[field] += 1
                alias_counts[field][source] += 1
        if missing_fields:
            errors.append(
                {
                    "code": "provenance_fields_missing",
                    "record_index": index,
                    "fields": missing_fields,
                }
            )

        if record.get("target_domain_flag") is not False or record.get("training_eligible") is not False:
            errors.append({"code": "proxy_training_boundary_invalid", "record_index": index})
        if (
            "local_path" in record
            and record.get("download_status") != "verified"
            and not _is_limitation_status(record.get("download_status"))
        ):
            errors.append({"code": "download_status_not_verified", "record_index": index})

        if not entries:
            errors.append({"code": "record_files_missing", "record_index": index})
        for file_index, entry in enumerate(entries):
            file_count += 1
            file_path = _entry_path(manifest_path, entry)
            if file_path is None:
                errors.append(
                    {
                        "code": "data_file_path_missing",
                        "record_index": index,
                        "file_index": file_index,
                    }
                )
                continue
            if not file_path.is_file():
                errors.append(
                    {
                        "code": "data_file_missing",
                        "record_index": index,
                        "file_index": file_index,
                        "path": str(file_path),
                    }
                )
                continue
            if "size_bytes" not in entry or "sha256" not in entry:
                errors.append(
                    {
                        "code": "file_integrity_fields_missing",
                        "record_index": index,
                        "file_index": file_index,
                    }
                )
                continue
            try:
                expected_size = int(entry["size_bytes"])
            except (TypeError, ValueError):
                errors.append(
                    {
                        "code": "file_size_invalid",
                        "record_index": index,
                        "file_index": file_index,
                    }
                )
                continue
            actual_size = file_path.stat().st_size
            total_size += actual_size
            if actual_size != expected_size:
                errors.append(
                    {
                        "code": "size_mismatch",
                        "record_index": index,
                        "file_index": file_index,
                        "expected": expected_size,
                        "actual": actual_size,
                    }
                )
                continue
            actual_sha256 = _sha256(file_path)
            if actual_sha256.lower() != str(entry["sha256"]).lower():
                errors.append(
                    {
                        "code": "sha256_mismatch",
                        "record_index": index,
                        "file_index": file_index,
                        "expected": entry["sha256"],
                        "actual": actual_sha256,
                    }
                )
                continue
            verified_file_count += 1
        if len(errors) == record_error_start:
            verified_record_count += 1

    declared_count = payload.get("record_count")
    if declared_count is None:
        declared_count = payload.get("dataset_count")
    if declared_count is None:
        declared_count = payload.get("candidate_count")
    if declared_count is not None and int(declared_count) != len(records):
        errors.append({"code": "record_count_mismatch", "expected": int(declared_count), "actual": len(records)})
    declared_total = payload.get("total_size_bytes")
    if declared_total is not None and int(declared_total) != total_size:
        errors.append({"code": "total_size_mismatch", "expected": int(declared_total), "actual": total_size})
    return {
        "manifest_path": str(manifest_path),
        "schema_version": payload.get("schema_version"),
        "status": "passed" if not errors else "failed",
        "record_count": len(records),
        "verified_record_count": verified_record_count,
        "file_count": file_count,
        "verified_file_count": verified_file_count,
        "total_size_bytes": total_size,
        "provenance_contract_fields": list(PROVENANCE_CONTRACT_FIELDS),
        "provenance_coverage": {field: int(coverage.get(field, 0)) for field in PROVENANCE_CONTRACT_FIELDS},
        "provenance_source_aliases": {
            field: dict(sorted(counts.items())) for field, counts in sorted(alias_counts.items())
        },
        "errors": errors,
    }


def verify_manifests(manifest_paths: list[Path]) -> dict[str, Any]:
    results = [verify_manifest(path.resolve()) for path in manifest_paths]
    aggregate_coverage = {
        field: sum(int(result.get("provenance_coverage", {}).get(field, 0)) for result in results)
        for field in PROVENANCE_CONTRACT_FIELDS
    }
    return {
        "schema_version": "osteo-vision-three-priority-manifest-verification-v2",
        "provenance_contract_version": "osteo-vision-dataset-provenance-v1",
        "provenance_contract_fields": list(PROVENANCE_CONTRACT_FIELDS),
        "status": "passed" if all(result["status"] == "passed" for result in results) else "failed",
        "manifest_count": len(results),
        "record_count": sum(int(result["record_count"]) for result in results),
        "verified_record_count": sum(int(result.get("verified_record_count", 0)) for result in results),
        "file_count": sum(int(result.get("file_count", 0)) for result in results),
        "verified_file_count": sum(int(result.get("verified_file_count", 0)) for result in results),
        "total_size_bytes": sum(int(result["total_size_bytes"]) for result in results),
        "provenance_coverage": aggregate_coverage,
        "manifests": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", dest="manifests")
    parser.add_argument("--output")
    args = parser.parse_args()
    paths = [ROOT / value for value in args.manifests] if args.manifests else DEFAULT_MANIFESTS
    report = verify_manifests(paths)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = (ROOT / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
