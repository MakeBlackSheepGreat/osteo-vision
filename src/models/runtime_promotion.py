from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.datasets.training_admission import TrainingAdmissionError, admit_keyframe_training_rows

PROMOTION_SCHEMA_VERSION = "osteo-vision-keyframe-runtime-promotion-v1"


def build_keyframe_runtime_promotion(
    *,
    checkpoint_path: str | Path,
    training_sidecar_path: str | Path,
    val_eval_path: str | Path,
    test_eval_path: str | Path,
    max_empty_mask_rate: float = 0.05,
    max_over_segmentation_rate: float = 0.05,
) -> dict[str, Any]:
    checkpoint = Path(checkpoint_path).resolve()
    training_path = Path(training_sidecar_path).resolve()
    val_path = Path(val_eval_path).resolve()
    test_path = Path(test_eval_path).resolve()
    errors: list[dict[str, Any]] = []

    if not checkpoint.is_file():
        errors.append({"code": "checkpoint_missing", "path": str(checkpoint)})
    training = _load_json_object(training_path, "training_sidecar", errors)
    val_eval = _load_json_object(val_path, "val_eval", errors)
    test_eval = _load_json_object(test_path, "test_eval", errors)
    actual_sha = _sha256_file(checkpoint) if checkpoint.is_file() else None

    if training is not None:
        _check_checkpoint_evidence(
            training,
            label="training_sidecar",
            evidence_path=training_path,
            checkpoint_path=checkpoint,
            actual_sha=actual_sha,
            errors=errors,
        )
        if training.get("clinical_claim_allowed") is not False:
            errors.append(
                {
                    "code": "clinical_claim_must_be_false",
                    "evidence": "training_sidecar",
                    "actual": training.get("clinical_claim_allowed"),
                }
            )

    for label, payload, path, expected_split in (
        ("val_eval", val_eval, val_path, "val"),
        ("test_eval", test_eval, test_path, "test"),
    ):
        if payload is None:
            continue
        _check_checkpoint_evidence(
            payload,
            label=label,
            evidence_path=path,
            checkpoint_path=checkpoint,
            actual_sha=actual_sha,
            errors=errors,
        )
        if str(payload.get("split") or "") != expected_split:
            errors.append(
                {
                    "code": "evaluation_split_mismatch",
                    "evidence": label,
                    "expected": expected_split,
                    "actual": payload.get("split"),
                }
            )
        if payload.get("clinical_claim_allowed") not in (None, False):
            errors.append(
                {
                    "code": "clinical_claim_must_be_false",
                    "evidence": label,
                    "actual": payload.get("clinical_claim_allowed"),
                }
            )

    split_reports: list[tuple[str, dict[str, Any] | None]] = [
        (
            "training_sidecar",
            _nested_dict(training, "training", "source_group_split") if training else None,
        ),
        ("val_eval", _as_dict(val_eval.get("source_group_split")) if val_eval else None),
        ("test_eval", _as_dict(test_eval.get("source_group_split")) if test_eval else None),
    ]
    for label, split_report in split_reports:
        _check_source_group_split(split_report, label=label, errors=errors)
    _check_split_report_alignment(split_reports, errors=errors)
    manifest_alignment = _check_manifest_alignment(training, val_eval, test_eval, errors=errors)
    _check_model_identity(training, val_eval, test_eval, errors=errors)

    val_threshold, val_selected = _check_evaluation_gates(
        val_eval,
        label="val_eval",
        max_empty_mask_rate=max_empty_mask_rate,
        max_over_segmentation_rate=max_over_segmentation_rate,
        errors=errors,
    )
    test_threshold, test_selected = _check_evaluation_gates(
        test_eval,
        label="test_eval",
        max_empty_mask_rate=max_empty_mask_rate,
        max_over_segmentation_rate=max_over_segmentation_rate,
        errors=errors,
    )
    if val_threshold is not None and test_threshold is not None:
        if abs(val_threshold - test_threshold) > 1e-9:
            errors.append(
                {
                    "code": "val_test_threshold_mismatch",
                    "val_threshold": val_threshold,
                    "test_threshold": test_threshold,
                }
            )

    passed = not errors
    report: dict[str, Any] = {
        "passed": passed,
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": actual_sha,
        "gate_policy": {
            "max_empty_mask_rate": float(max_empty_mask_rate),
            "max_over_segmentation_rate": float(max_over_segmentation_rate),
            "required_splits": ["val", "test"],
            "source_group_leakage_allowed": False,
            "clinical_claim_allowed": False,
        },
        "errors": errors,
    }
    if not passed or training is None or val_eval is None or test_eval is None:
        return report

    assert val_threshold is not None
    threshold = float(val_threshold)
    model_id = str(training.get("model_id") or "")
    model_family = str(training.get("model_family") or "")
    training_payload = _as_dict(training.get("training")) or {}
    source_warnings = [str(item) for item in training.get("warnings") or []]
    report["promotion_sidecar"] = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": actual_sha,
        "model_id": model_id,
        "model_family": model_family,
        "runtime_allowed": True,
        "clinical_claim_allowed": False,
        "threshold": threshold,
        "metrics": {
            "threshold": threshold,
            "validation": val_selected,
            "test": test_selected,
        },
        "promotion": {
            "status": "passed",
            "gate_policy": report["gate_policy"],
            "source_group_split": split_reports[0][1],
            "evidence": {
                "training_sidecar": _evidence_record(training_path),
                "val_threshold_eval": _evidence_record(val_path),
                "test_threshold_eval": _evidence_record(test_path),
            },
            "manifest_alignment": manifest_alignment,
        },
        "training": training_payload,
        "data_boundary": training_payload.get("data_boundary")
        or "Proxy or non-target-domain training evidence requiring explicit provenance review.",
        "medical_boundary": (
            "Runtime promotion covers platform keyframe stability on public, proxy, or pseudo-labeled evidence. "
            "It does not establish clinical diagnostic performance for intraoperative ICG jaw osteomyelitis."
        ),
        "evidence_medical_boundaries": [
            str(value) for value in (val_eval.get("medical_boundary"), test_eval.get("medical_boundary")) if value
        ],
        "warnings": list(
            dict.fromkeys(
                source_warnings
                + [
                    "The promoted checkpoint remains non-target-domain or proxy-label engineering evidence.",
                    "All candidate masks require physician review and cannot be used as a disease-final mask.",
                ]
            )
        ),
    }
    return report


def write_runtime_promotion_sidecar(path: str | Path, report: dict[str, Any]) -> Path:
    if report.get("passed") is not True or not isinstance(report.get("promotion_sidecar"), dict):
        raise ValueError("Runtime promotion report did not pass all gates.")
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report["promotion_sidecar"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _load_json_object(
    path: Path,
    label: str,
    errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append({"code": "evidence_missing", "evidence": label, "path": str(path)})
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            {
                "code": "evidence_json_invalid",
                "evidence": label,
                "path": str(path),
                "detail": str(exc),
            }
        )
        return None
    if not isinstance(payload, dict):
        errors.append({"code": "evidence_json_not_object", "evidence": label, "path": str(path)})
        return None
    return payload


def _check_checkpoint_evidence(
    payload: dict[str, Any],
    *,
    label: str,
    evidence_path: Path,
    checkpoint_path: Path,
    actual_sha: str | None,
    errors: list[dict[str, Any]],
) -> None:
    expected_sha = str(payload.get("checkpoint_sha256") or "")
    if not expected_sha:
        errors.append({"code": "checkpoint_sha_missing", "evidence": label, "path": str(evidence_path)})
    elif actual_sha is not None and expected_sha != actual_sha:
        errors.append(
            {
                "code": "checkpoint_sha_mismatch",
                "evidence": label,
                "expected": expected_sha,
                "actual": actual_sha,
            }
        )
    recorded_path = str(payload.get("checkpoint_path") or "").strip()
    if not recorded_path:
        errors.append({"code": "checkpoint_path_missing", "evidence": label})
    elif Path(recorded_path).resolve() != checkpoint_path:
        errors.append(
            {
                "code": "checkpoint_path_mismatch",
                "evidence": label,
                "expected": str(checkpoint_path),
                "actual": str(Path(recorded_path).resolve()),
            }
        )


def _check_source_group_split(
    payload: dict[str, Any] | None,
    *,
    label: str,
    errors: list[dict[str, Any]],
) -> None:
    if payload is None:
        errors.append({"code": "source_group_split_missing", "evidence": label})
        return
    if payload.get("leakage_detected") is not False:
        errors.append(
            {
                "code": "source_group_leakage_detected",
                "evidence": label,
                "actual": payload.get("leakage_detected"),
            }
        )
    for field in ("leaking_group_count", "missing_group_row_count"):
        value = _number(payload.get(field))
        if value is None or value != 0.0:
            errors.append(
                {
                    "code": f"source_group_{field}_invalid",
                    "evidence": label,
                    "actual": payload.get(field),
                }
            )
    group_count = _number(payload.get("group_count"))
    if group_count is None or group_count <= 0:
        errors.append(
            {
                "code": "source_group_count_invalid",
                "evidence": label,
                "actual": payload.get("group_count"),
            }
        )


def _check_split_report_alignment(
    reports: list[tuple[str, dict[str, Any] | None]],
    *,
    errors: list[dict[str, Any]],
) -> None:
    available = [(label, report) for label, report in reports if report is not None]
    if len(available) < 2:
        return
    base_label, base = available[0]
    assert base is not None
    base_signature = _split_signature(base)
    for label, report in available[1:]:
        assert report is not None
        if _split_signature(report) != base_signature:
            errors.append(
                {
                    "code": "source_group_split_evidence_mismatch",
                    "reference": base_label,
                    "evidence": label,
                    "reference_signature": base_signature,
                    "actual_signature": _split_signature(report),
                }
            )


def _check_manifest_alignment(
    training: dict[str, Any] | None,
    val_eval: dict[str, Any] | None,
    test_eval: dict[str, Any] | None,
    *,
    errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if training is None or val_eval is None or test_eval is None:
        return None
    training_block = _as_dict(training.get("training")) or {}
    reference = _normalized_paths(training_block.get("manifest_paths") or [training_block.get("manifest_path")])
    val_paths = _normalized_paths(val_eval.get("manifest_paths") or [])
    test_paths = _normalized_paths(test_eval.get("manifest_paths") or [])
    if val_paths != test_paths:
        errors.append(
            {
                "code": "evaluation_manifest_paths_mismatch",
                "val_manifests": val_paths,
                "test_manifests": test_paths,
            }
        )
        return None
    if reference and val_paths == reference:
        return {
            "method": "direct_manifest_paths",
            "training_manifests": reference,
            "evaluation_manifests": val_paths,
        }
    registry_alignment = _registry_manifest_alignment(training_block, val_paths, errors=errors)
    if registry_alignment is not None:
        return registry_alignment
    for label, actual in (("val_eval", val_paths), ("test_eval", test_paths)):
        errors.append(
            {
                "code": "manifest_evidence_mismatch",
                "evidence": label,
                "training_manifests": reference,
                "evaluation_manifests": actual,
            }
        )
    return None


def _registry_manifest_alignment(
    training: dict[str, Any],
    evaluation_paths: list[str],
    *,
    errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if str(training.get("source") or "") != "layered_registry_admission":
        return None
    registry_value = str(training.get("registry_path") or "").strip()
    quality_value = str(training.get("quality_report_path") or "").strip()
    admission = _as_dict(training.get("training_admission")) or {}
    if not registry_value or not quality_value or len(evaluation_paths) != 1:
        errors.append(
            {
                "code": "registry_manifest_alignment_evidence_missing",
                "registry_path": registry_value or None,
                "quality_report_path": quality_value or None,
                "evaluation_manifests": evaluation_paths,
            }
        )
        return None
    registry_path = Path(registry_value).resolve()
    quality_path = Path(quality_value).resolve()
    evaluation_path = Path(evaluation_paths[0]).resolve()
    try:
        admitted = admit_keyframe_training_rows(
            registry_path,
            quality_path,
            artifact_role=str(admission.get("artifact_role") or "training_keyframe::fluorescence_hotspot"),
            admission_stage=str(admission.get("admission_stage") or "proxy_pretrain"),
        )
        evaluation_rows = _read_csv_rows(evaluation_path)
    except (OSError, UnicodeError, ValueError, TrainingAdmissionError) as exc:
        errors.append(
            {
                "code": "registry_manifest_alignment_failed",
                "registry_path": str(registry_path),
                "evaluation_manifest": str(evaluation_path),
                "detail": str(exc),
            }
        )
        return None
    admitted_signatures = _row_identity_signatures(admitted.rows)
    evaluation_signatures = _row_identity_signatures(evaluation_rows)
    admitted_duplicates = len(admitted.rows) - len(admitted_signatures)
    evaluation_duplicates = len(evaluation_rows) - len(evaluation_signatures)
    if (
        admitted_duplicates
        or evaluation_duplicates
        or len(admitted.rows) != len(evaluation_rows)
        or admitted_signatures != evaluation_signatures
    ):
        errors.append(
            {
                "code": "registry_manifest_rows_mismatch",
                "admitted_row_count": len(admitted.rows),
                "evaluation_row_count": len(evaluation_rows),
                "admitted_duplicate_count": admitted_duplicates,
                "evaluation_duplicate_count": evaluation_duplicates,
                "missing_from_evaluation_first5": sorted(admitted_signatures - evaluation_signatures)[:5],
                "unexpected_in_evaluation_first5": sorted(evaluation_signatures - admitted_signatures)[:5],
            }
        )
        return None
    return {
        "method": "layered_registry_admitted_row_identity",
        "registry_path": str(registry_path),
        "registry_sha256": _sha256_file(registry_path),
        "quality_report_path": str(quality_path),
        "quality_report_sha256": _sha256_file(quality_path),
        "evaluation_manifest": str(evaluation_path),
        "evaluation_manifest_sha256": _sha256_file(evaluation_path),
        "artifact_role": admission.get("artifact_role"),
        "admission_stage": admission.get("admission_stage"),
        "matched_row_count": len(evaluation_rows),
        "identity_fields": ["image_path", "mask_path", "split", "source_group_id"],
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    import csv

    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{str(key): str(value or "") for key, value in row.items()} for row in csv.DictReader(handle)]


def _row_identity_signatures(rows: list[dict[str, str]]) -> set[str]:
    signatures: set[str] = set()
    for row in rows:
        image_path = _normalized_identity_path(row.get("image_path"))
        mask_path = _normalized_identity_path(row.get("mask_path"))
        split = str(row.get("split") or "").strip().casefold()
        group = str(row.get("source_group_id") or row.get("group_id") or "").strip().replace("\\", "/").casefold()
        signatures.add("|".join((image_path, mask_path, split, group)))
    return signatures


def _normalized_identity_path(value: Any) -> str:
    text = str(value or "").strip()
    return Path(text).resolve().as_posix().casefold() if text else ""


def _check_model_identity(
    training: dict[str, Any] | None,
    val_eval: dict[str, Any] | None,
    test_eval: dict[str, Any] | None,
    *,
    errors: list[dict[str, Any]],
) -> None:
    if training is None:
        return
    reference_id = str(training.get("model_id") or "")
    reference_family = str(training.get("model_family") or "")
    if not reference_id:
        errors.append({"code": "model_id_missing", "evidence": "training_sidecar"})
    if not reference_family:
        errors.append({"code": "model_family_missing", "evidence": "training_sidecar"})
    for label, payload in (("val_eval", val_eval), ("test_eval", test_eval)):
        if payload is None:
            continue
        metadata = _as_dict(payload.get("checkpoint_metadata")) or {}
        actual_id = str(metadata.get("model_id") or "")
        actual_family = str(metadata.get("model_family") or "")
        if actual_id != reference_id:
            errors.append(
                {
                    "code": "model_id_mismatch",
                    "evidence": label,
                    "expected": reference_id,
                    "actual": actual_id,
                }
            )
        if actual_family != reference_family:
            errors.append(
                {
                    "code": "model_family_mismatch",
                    "evidence": label,
                    "expected": reference_family,
                    "actual": actual_family,
                }
            )


def _check_evaluation_gates(
    payload: dict[str, Any] | None,
    *,
    label: str,
    max_empty_mask_rate: float,
    max_over_segmentation_rate: float,
    errors: list[dict[str, Any]],
) -> tuple[float | None, dict[str, Any] | None]:
    if payload is None:
        return None, None
    recommendation = _as_dict(payload.get("recommendation"))
    if recommendation is None:
        errors.append({"code": "threshold_recommendation_missing", "evidence": label})
        return None, None
    threshold = _number(recommendation.get("threshold"))
    selected = _as_dict(recommendation.get("selected_row"))
    if threshold is None:
        errors.append({"code": "recommended_threshold_invalid", "evidence": label})
    if selected is None:
        errors.append({"code": "recommended_threshold_row_missing", "evidence": label})
        return threshold, None
    selected_threshold = _number(selected.get("threshold"))
    if threshold is not None and (selected_threshold is None or abs(threshold - selected_threshold) > 1e-9):
        errors.append(
            {
                "code": "recommended_threshold_row_mismatch",
                "evidence": label,
                "recommendation": threshold,
                "selected_row": selected.get("threshold"),
            }
        )
    for metric, limit in (
        ("empty_mask_rate", max_empty_mask_rate),
        ("over_segmentation_rate", max_over_segmentation_rate),
    ):
        value = _number(selected.get(metric))
        if value is None:
            errors.append({"code": f"{metric}_missing", "evidence": label})
        elif value > float(limit) + 1e-12:
            errors.append(
                {
                    "code": f"{metric}_exceeds_gate",
                    "evidence": label,
                    "actual": value,
                    "maximum": float(limit),
                }
            )
    return threshold, selected


def _split_signature(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_count": payload.get("row_count"),
        "group_count": payload.get("group_count"),
        "split_group_counts": payload.get("split_group_counts") or {},
        "group_keys": payload.get("group_keys") or [],
        "split_key": payload.get("split_key"),
    }


def _nested_dict(payload: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _as_dict(current)


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _normalized_paths(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted(str(Path(str(value)).resolve()) for value in values if value)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": _sha256_file(path)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
