from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

REGISTRY_FIELDS = [
    "record_id",
    "source_id",
    "source_url",
    "direct_download_url",
    "local_path",
    "label_path",
    "medical_scene",
    "fluorescence",
    "domain_tier",
    "label_type",
    "review_state",
    "sample_weight",
    "target_domain_flag",
    "license",
    "checksum",
    "label_checksum",
    "split",
    "group_id",
    "artifact_role",
    "medical_boundary",
    "usage_policy",
    "training_eligible",
    "sampling_weight",
]

ALLOWED_DOMAIN_TIERS = {"target_domain", "near_domain", "fluorescence_proxy", "derived_proxy"}
ALLOWED_REVIEW_STATES = {"unlabeled", "review_required", "accepted", "modified", "rejected"}
ALLOWED_FLUORESCENCE = {"yes", "no", "unknown"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class DatasetRecord:
    record_id: str
    source_id: str
    source_url: str
    direct_download_url: str
    local_path: str
    label_path: str
    medical_scene: str
    fluorescence: str
    domain_tier: str
    label_type: str
    review_state: str
    sample_weight: float
    target_domain_flag: bool
    license: str
    checksum: str
    split: str
    group_id: str
    artifact_role: str
    medical_boundary: str
    usage_policy: str = "engineering_reference"
    training_eligible: bool = False
    sampling_weight: float = 1.0
    label_checksum: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["target_domain_flag"] = str(self.target_domain_flag).lower()
        row["training_eligible"] = str(self.training_eligible).lower()
        return row


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    record_id: str
    field: str
    message: str

    def to_row(self) -> dict[str, str]:
        return asdict(self)


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_registry(path: str | Path, records: Iterable[DatasetRecord]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_row())


def read_registry(path: str | Path) -> list[DatasetRecord]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [record_from_row(row) for row in csv.DictReader(handle)]


def record_from_row(row: dict[str, Any]) -> DatasetRecord:
    return DatasetRecord(
        record_id=str(row.get("record_id") or ""),
        source_id=str(row.get("source_id") or ""),
        source_url=str(row.get("source_url") or ""),
        direct_download_url=str(row.get("direct_download_url") or ""),
        local_path=str(row.get("local_path") or ""),
        label_path=str(row.get("label_path") or ""),
        medical_scene=str(row.get("medical_scene") or ""),
        fluorescence=str(row.get("fluorescence") or "unknown").lower(),
        domain_tier=str(row.get("domain_tier") or ""),
        label_type=str(row.get("label_type") or ""),
        review_state=str(row.get("review_state") or ""),
        sample_weight=float(row.get("sample_weight") or 0.0),
        target_domain_flag=str(row.get("target_domain_flag") or "").lower() in {"1", "true", "yes"},
        license=str(row.get("license") or ""),
        checksum=str(row.get("checksum") or "").lower(),
        label_checksum=str(row.get("label_checksum") or "").lower(),
        split=str(row.get("split") or ""),
        group_id=str(row.get("group_id") or ""),
        artifact_role=str(row.get("artifact_role") or ""),
        medical_boundary=str(row.get("medical_boundary") or ""),
        usage_policy=str(row.get("usage_policy") or "engineering_reference"),
        training_eligible=str(row.get("training_eligible") or "").lower() in {"1", "true", "yes"},
        sampling_weight=float(row.get("sampling_weight") or 1.0),
    )


def validate_registry(records: list[DatasetRecord], *, verify_checksums: bool = False) -> dict[str, Any]:
    issues: list[QualityIssue] = []
    seen_ids: Counter[str] = Counter(record.record_id for record in records)
    group_splits: dict[str, set[str]] = defaultdict(set)
    checksum_records: dict[str, list[DatasetRecord]] = defaultdict(list)

    for record in records:
        issues.extend(_validate_record(record, verify_checksums=verify_checksums))
        if seen_ids[record.record_id] > 1:
            issues.append(_issue("error", "duplicate_record_id", record, "record_id", "record_id must be unique"))
        if record.group_id and record.split:
            group_splits[record.group_id].add(record.split)
        if SHA256_PATTERN.fullmatch(record.checksum):
            checksum_records[record.checksum].append(record)

    for group_id, splits in sorted(group_splits.items()):
        if len(splits) > 1:
            issues.append(
                QualityIssue(
                    severity="error",
                    code="cross_split_group_leakage",
                    record_id=group_id,
                    field="split",
                    message=f"group_id occurs in multiple splits: {sorted(splits)}",
                )
            )

    for checksum, matches in checksum_records.items():
        if len(matches) < 2:
            continue
        splits = {record.split for record in matches if record.split}
        local_paths = {str(Path(record.local_path)).lower() for record in matches}
        multi_label_input = len(local_paths) == 1 and len({record.artifact_role for record in matches}) > 1
        if len(splits) > 1:
            severity = "error"
            code = "duplicate_sha_cross_split"
        elif multi_label_input:
            severity = "info"
            code = "shared_input_multilabel"
        else:
            severity = "warning"
            code = "duplicate_sha_same_split"
        issues.append(
            QualityIssue(
                severity=severity,
                code=code,
                record_id="|".join(record.record_id for record in matches[:5]),
                field="checksum",
                message=f"SHA256 {checksum} is shared by {len(matches)} records; splits={sorted(splits)}",
            )
        )

    severity_counts = Counter(issue.severity for issue in issues)
    code_counts = Counter(issue.code for issue in issues)
    return {
        "record_count": len(records),
        "passed": severity_counts["error"] == 0,
        "error_count": severity_counts["error"],
        "warning_count": severity_counts["warning"],
        "info_count": severity_counts["info"],
        "issue_code_counts": dict(sorted(code_counts.items())),
        "domain_tier_counts": dict(sorted(Counter(record.domain_tier for record in records).items())),
        "label_type_counts": dict(sorted(Counter(record.label_type for record in records).items())),
        "review_state_counts": dict(sorted(Counter(record.review_state for record in records).items())),
        "usage_policy_counts": dict(sorted(Counter(record.usage_policy for record in records).items())),
        "split_counts": dict(sorted(Counter(record.split or "unsplit" for record in records).items())),
        "target_domain_count": sum(record.target_domain_flag for record in records),
        "training_eligible_count": sum(record.training_eligible for record in records),
        "issues": [issue.to_row() for issue in issues],
    }


def _validate_record(record: DatasetRecord, *, verify_checksums: bool) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    required = {
        "record_id": record.record_id,
        "source_id": record.source_id,
        "source_url": record.source_url,
        "local_path": record.local_path,
        "medical_scene": record.medical_scene,
        "domain_tier": record.domain_tier,
        "label_type": record.label_type,
        "review_state": record.review_state,
        "license": record.license,
        "checksum": record.checksum,
        "group_id": record.group_id,
        "artifact_role": record.artifact_role,
        "medical_boundary": record.medical_boundary,
        "usage_policy": record.usage_policy,
    }
    for field, value in required.items():
        if not str(value).strip():
            issues.append(_issue("error", "missing_required_field", record, field, f"{field} is required"))
    if not record.source_url.startswith(("https://", "http://")):
        issues.append(_issue("error", "untraceable_source_url", record, "source_url", "source_url must use HTTP(S)"))
    if record.domain_tier not in ALLOWED_DOMAIN_TIERS:
        issues.append(_issue("error", "invalid_domain_tier", record, "domain_tier", record.domain_tier))
    if record.review_state not in ALLOWED_REVIEW_STATES:
        issues.append(_issue("error", "invalid_review_state", record, "review_state", record.review_state))
    if record.fluorescence not in ALLOWED_FLUORESCENCE:
        issues.append(_issue("error", "invalid_fluorescence", record, "fluorescence", record.fluorescence))
    if record.sampling_weight < 0:
        issues.append(
            _issue("error", "invalid_sampling_weight", record, "sampling_weight", str(record.sampling_weight))
        )
    policy = record.usage_policy.lower()
    license_name = record.license.lower()
    forbidden_training = any(token in policy for token in ("reference_only", "no_derivatives", "no_training"))
    forbidden_training = forbidden_training or "cc by-nc-nd" in license_name or "cc-by-nc-nd" in license_name
    if record.training_eligible and forbidden_training:
        issues.append(
            _issue(
                "error",
                "training_forbidden_by_usage_policy",
                record,
                "training_eligible",
                f"usage_policy={record.usage_policy}; license={record.license}",
            )
        )
    if record.training_eligible and record.label_type == "none":
        issues.append(
            _issue(
                "error",
                "training_record_missing_supervision",
                record,
                "label_type",
                "training-eligible segmentation records require a label",
            )
        )
    local_path = Path(record.local_path)
    if not local_path.is_file():
        issues.append(_issue("error", "missing_local_file", record, "local_path", str(local_path)))
    if not SHA256_PATTERN.fullmatch(record.checksum):
        issues.append(_issue("error", "invalid_or_missing_sha256", record, "checksum", record.checksum))
    elif verify_checksums and local_path.is_file() and sha256_file(local_path) != record.checksum:
        issues.append(_issue("error", "checksum_mismatch", record, "checksum", str(local_path)))

    label_path = Path(record.label_path) if record.label_path else None
    if record.label_type == "none":
        if record.label_path:
            issues.append(_issue("error", "unlabeled_record_has_label_path", record, "label_path", record.label_path))
        if record.review_state != "unlabeled":
            issues.append(_issue("error", "unlabeled_review_conflict", record, "review_state", record.review_state))
    else:
        if label_path is None or not label_path.is_file():
            issues.append(_issue("error", "missing_label_file", record, "label_path", record.label_path))
        if record.review_state == "unlabeled":
            issues.append(_issue("error", "label_review_conflict", record, "review_state", record.review_state))
        if record.training_eligible and not SHA256_PATTERN.fullmatch(record.label_checksum):
            issues.append(
                _issue(
                    "error",
                    "invalid_or_missing_label_sha256",
                    record,
                    "label_checksum",
                    record.label_checksum,
                )
            )
        elif (
            verify_checksums
            and label_path is not None
            and label_path.is_file()
            and record.label_checksum
            and sha256_file(label_path) != record.label_checksum
        ):
            issues.append(_issue("error", "label_checksum_mismatch", record, "label_checksum", str(label_path)))

    expected_weights = {"accepted": 4.0, "modified": 4.0, "rejected": 0.5, "review_required": 1.0, "unlabeled": 1.0}
    expected = expected_weights.get(record.review_state)
    if expected is not None and abs(record.sample_weight - expected) > 1e-6:
        issues.append(
            _issue(
                "error",
                "sample_weight_contract_violation",
                record,
                "sample_weight",
                f"state={record.review_state}, expected={expected}, actual={record.sample_weight}",
            )
        )
    if record.target_domain_flag:
        scene = record.medical_scene.lower()
        valid_scene = ("jaw" in scene or "mandib" in scene or "颌" in scene) and "osteomyel" in scene
        if record.domain_tier != "target_domain" or not valid_scene:
            issues.append(
                _issue(
                    "error",
                    "target_domain_mislabel",
                    record,
                    "target_domain_flag",
                    "target-domain rows require verified jaw osteomyelitis scene metadata",
                )
            )
    elif record.domain_tier == "target_domain":
        issues.append(_issue("error", "target_domain_flag_conflict", record, "target_domain_flag", "false"))
    if any(token in record.license.lower() for token in ("unknown", "verify", "verification")):
        issues.append(_issue("warning", "license_requires_verification", record, "license", record.license))
    return issues


def _issue(severity: str, code: str, record: DatasetRecord, field: str, message: str) -> QualityIssue:
    return QualityIssue(severity=severity, code=code, record_id=record.record_id, field=field, message=message)
