from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from backend.src.domains.cases.schemas import ClinicalContext, ClinicalLabResult
from src.core.clinical_context_verification import clinical_context_verification_issues
from src.models.clinical_feature_vector import (
    build_clinical_feature_vector,
    compute_clinical_context_assessment_checksum,
)

CLINICAL_CONTEXT_ASSESSMENT_SCHEMA = "osteo-vision-clinical-context-assessment-v1"
LAB_FRESHNESS_HOURS = 7 * 24

_LAB_SPECS: dict[str, dict[str, Any]] = {
    "crp": {"name": "CRP", "units": {"mg/l": 1.0, "mg/dl": 10.0}, "range": (0.0, 10.0), "canonical_unit": "mg/L"},
    "wbc": {
        "name": "WBC",
        "units": {"10^9/l": 1.0, "10*9/l": 1.0, "g/l": 1.0},
        "range": (3.5, 9.5),
        "canonical_unit": "10^9/L",
    },
    "neutrophil_percent": {
        "name": "NEUT%",
        "units": {"%": 1.0},
        "range": (40.0, 75.0),
        "canonical_unit": "%",
    },
    "esr": {"name": "ESR", "units": {"mm/h": 1.0, "mm/hr": 1.0}, "range": (0.0, 20.0), "canonical_unit": "mm/h"},
    "hgb": {
        "name": "HGB",
        "units": {"g/l": 1.0, "g/dl": 10.0},
        "range": (110.0, 170.0),
        "canonical_unit": "g/L",
    },
    "pct": {"name": "PCT", "units": {"ng/ml": 1.0}, "range": (0.0, 0.5), "canonical_unit": "ng/mL"},
    "alb": {"name": "ALB", "units": {"g/l": 1.0, "g/dl": 10.0}, "range": (35.0, 55.0), "canonical_unit": "g/L"},
    "glu": {
        "name": "GLU",
        "units": {"mmol/l": 1.0, "mg/dl": 1 / 18.0},
        "range": (3.9, 6.1),
        "canonical_unit": "mmol/L",
    },
    "hba1c": {"name": "HbA1c", "units": {"%": 1.0}, "range": (4.0, 6.5), "canonical_unit": "%"},
    "creatinine": {
        "name": "CREA",
        "units": {"umol/l": 1.0, "µmol/l": 1.0, "mg/dl": 88.4},
        "range": (44.0, 133.0),
        "canonical_unit": "umol/L",
    },
    "egfr": {
        "name": "eGFR",
        "units": {
            "ml/min/1.73m2": 1.0,
            "ml/min/1.73m²": 1.0,
            "ml/min/1.73m^2": 1.0,
        },
        "range": (60.0, 120.0),
        "canonical_unit": "mL/min/1.73m2",
    },
}

_LAB_ALIASES = {
    "c-reactive protein": "crp",
    "超敏c反应蛋白": "crp",
    "c反应蛋白": "crp",
    "white blood cell": "wbc",
    "白细胞": "wbc",
    "白细胞计数": "wbc",
    "neut%": "neutrophil_percent",
    "neutrophil %": "neutrophil_percent",
    "neutrophil percent": "neutrophil_percent",
    "neutrophil percentage": "neutrophil_percent",
    "中性粒细胞百分比": "neutrophil_percent",
    "中性粒细胞%": "neutrophil_percent",
    "erythrocyte sedimentation rate": "esr",
    "血沉": "esr",
    "hemoglobin": "hgb",
    "haemoglobin": "hgb",
    "血红蛋白": "hgb",
    "procalcitonin": "pct",
    "降钙素原": "pct",
    "albumin": "alb",
    "白蛋白": "alb",
    "glucose": "glu",
    "血糖": "glu",
    "糖化血红蛋白": "hba1c",
    "肌酐": "creatinine",
    "crea": "creatinine",
    "estimated glomerular filtration rate": "egfr",
    "估算肾小球滤过率": "egfr",
}


def assess_clinical_context(
    context: ClinicalContext,
    *,
    assessed_at: datetime | None = None,
    revision: int | None = None,
) -> dict[str, Any]:
    now = _as_utc(assessed_at or datetime.now(timezone.utc))
    snapshot = context.model_dump(mode="json")
    checksum = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    lab_rows = [_assess_lab(item, now=now, index=index) for index, item in enumerate(context.labs)]
    latest_indices, conflicting_latest_indices = _latest_trusted_lab_indices(lab_rows)
    for row in lab_rows:
        if row["source_index"] in conflicting_latest_indices:
            row["duplicate_status"] = "conflicting_latest_results"
            row["eligible_for_rule_summary"] = False
            row["issues"] = _dedupe([*row["issues"], "lab_latest_result_conflict"])
        elif row["canonical_name"] and row["source_index"] not in latest_indices.get(row["canonical_name"], set()):
            row["duplicate_status"] = "superseded_by_newer_result"
            row["eligible_for_rule_summary"] = False

    usable_labs = [row for row in lab_rows if row["eligible_for_rule_summary"]]
    abnormal_labs = [row for row in usable_labs if row["derived_abnormality"] in {"low", "high"}]
    missing_fields = []
    if context.age_years is None:
        missing_fields.append("age_years")
    if context.sex_at_birth in {"unknown", "not_recorded"}:
        missing_fields.append("sex_at_birth")
    verification_issues = (
        clinical_context_verification_issues(snapshot, reference_time=now)
        if context.review_status == "verified"
        else []
    )
    verification_valid = context.review_status == "verified" and not verification_issues
    if not verification_valid:
        missing_fields.append("verified_review")
    if not usable_labs:
        missing_fields.append("fresh_unit_valid_labs")

    issues = _dedupe([*(issue for row in lab_rows for issue in row["issues"]), *verification_issues])
    if not context.deidentified:
        issues.append("context_deidentification_not_confirmed")
    contributing_factors = [
        {"type": "recorded_comorbidity", "label": value, "interpretation": "context_recorded_no_probability"}
        for value in _normalized_unique(context.comorbidities)
    ]
    contributing_factors.extend(
        {
            "type": "abnormal_lab_result",
            "label": row["canonical_name"],
            "direction": row["derived_abnormality"],
            "value": row["canonical_value"],
            "unit": row["canonical_unit"],
            "interpretation": "rule_flag_for_physician_review",
        }
        for row in abnormal_labs
    )
    quality_status = "ready_for_rule_summary"
    if not verification_valid:
        quality_status = "review_required"
    if issues or not usable_labs:
        quality_status = "limited"

    clinical_feature_vector = build_clinical_feature_vector(
        snapshot,
        lab_rows,
        context_checksum=checksum,
    )
    assessment = {
        "schema_version": CLINICAL_CONTEXT_ASSESSMENT_SCHEMA,
        "assessed_at": now.isoformat(),
        "clinical_context_revision": revision,
        "clinical_context_checksum": checksum,
        "clinical_context_snapshot": snapshot,
        "clinical_context_quality": {
            "status": quality_status,
            "review_status": context.review_status,
            "deidentified": context.deidentified,
            "missing_critical_fields": missing_fields,
            "issues": issues,
            "usable_lab_count": len(usable_labs),
            "recorded_lab_count": len(lab_rows),
        },
        "normalized_labs": lab_rows,
        "clinical_feature_vector": clinical_feature_vector,
        "rule_based_risk_summary": {
            "available": bool(contributing_factors),
            "status": "factors_recorded" if contributing_factors else "insufficient_context",
            "contributing_factors": contributing_factors,
            "factor_count": len(contributing_factors),
            "recorded_factor_count": len(contributing_factors),
            "review_required": not verification_valid or bool(issues),
            "probability": None,
            "interpretation": "contextual_rule_flags_only_no_clinical_risk_probability",
        },
        "calibration_evidence": {
            "applied": False,
            "status": "pending_target_domain_validation",
            "eligible": False,
            "method_id": None,
            "version": None,
            "reasons": ["no_validated_target_domain_clinical_calibrator"],
        },
        "spatial_effect_applied": False,
    }
    assessment["clinical_context_assessment_checksum"] = compute_clinical_context_assessment_checksum(assessment)
    return assessment


def clinical_context_warnings(assessment: dict[str, Any]) -> list[dict[str, Any]]:
    quality = assessment.get("clinical_context_quality") or {}
    snapshot = assessment.get("clinical_context_snapshot") or {}
    has_recorded_context = bool(
        snapshot.get("age_years") is not None
        or snapshot.get("comorbidities")
        or snapshot.get("medications")
        or snapshot.get("labs")
        or snapshot.get("source_organization")
        or snapshot.get("recorded_by")
        or snapshot.get("recorded_at")
    )
    if not has_recorded_context:
        return []
    warnings: list[dict[str, Any]] = []
    for issue in quality.get("issues") or []:
        code = str(issue)
        if not code.startswith("clinical_context_"):
            code = f"clinical_context_{code}"
        warnings.append(
            {
                "code": code,
                "message": f"Clinical context quality requires review: {issue}.",
                "blocking": False,
                "details": {"clinical_context_checksum": assessment.get("clinical_context_checksum")},
            }
        )
    if quality.get("review_status") != "verified":
        warnings.append(
            {
                "code": "clinical_context_not_verified",
                "message": "Clinical context has not been verified and is retained only as a review prompt.",
                "blocking": False,
            }
        )
    return warnings


def _assess_lab(lab: ClinicalLabResult, *, now: datetime, index: int) -> dict[str, Any]:
    key = _canonical_lab_key(lab.name)
    spec = _LAB_SPECS.get(key) if key else None
    unit_key = _unit_key(lab.unit)
    numeric_value = _numeric(lab.value)
    issues: list[str] = []
    canonical_value: float | None = None
    canonical_unit: str | None = spec.get("canonical_unit") if spec else None
    unit_status = "unknown_indicator"
    if spec:
        if unit_key in spec["units"]:
            unit_status = "valid"
            if numeric_value is not None:
                canonical_value = numeric_value * float(spec["units"][unit_key])
        else:
            unit_status = "missing" if not unit_key else "unsupported"
            issues.append("lab_unit_missing" if not unit_key else "lab_unit_unsupported")
    elif numeric_value is None:
        issues.append("lab_value_non_numeric")
    if not spec:
        issues.append("lab_indicator_unsupported")
    if spec and numeric_value is None:
        issues.append("lab_value_non_numeric")

    measured = _as_utc(lab.measured_at) if lab.measured_at else None
    age_hours: float | None = None
    freshness = "missing_timestamp"
    if measured:
        age_hours = (now - measured).total_seconds() / 3600.0
        if age_hours < -1 / 60:
            freshness = "future_timestamp"
            issues.append("lab_timestamp_in_future")
        elif age_hours > LAB_FRESHNESS_HOURS:
            freshness = "stale"
            issues.append("lab_result_stale")
        else:
            freshness = "current"
    else:
        issues.append("lab_timestamp_missing")

    derived = "unknown"
    reference_status = "unavailable"
    if spec and canonical_value is not None and unit_status == "valid":
        low, high = spec["range"]
        derived = "low" if canonical_value < low else "high" if canonical_value > high else "normal"
        reference_status = "canonical_engineering_reference"
        if lab.abnormal_flag != "unknown" and lab.abnormal_flag != derived:
            issues.append("lab_abnormal_flag_conflict")
    eligible = bool(spec and canonical_value is not None and freshness == "current" and unit_status == "valid")
    return {
        "source_index": index,
        "source_name": lab.name,
        "canonical_name": spec.get("name") if spec else None,
        "source_value": lab.value,
        "source_unit": lab.unit,
        "canonical_value": round(canonical_value, 4) if canonical_value is not None else None,
        "canonical_unit": canonical_unit,
        "unit_status": unit_status,
        "reference_status": reference_status,
        "source_reference_range": lab.reference_range,
        "source_abnormal_flag": lab.abnormal_flag,
        "derived_abnormality": derived,
        "measured_at": measured.isoformat() if measured else None,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "freshness_status": freshness,
        "duplicate_status": "unique_or_latest",
        "eligible_for_rule_summary": eligible,
        "issues": _dedupe(issues),
    }


def _latest_trusted_lab_indices(rows: list[dict[str, Any]]) -> tuple[dict[str, set[int]], set[int]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["canonical_name"]:
            grouped.setdefault(row["canonical_name"], []).append(row)
    selected: dict[str, set[int]] = {}
    conflicts: set[int] = set()
    for name, candidates in grouped.items():
        eligible = [row for row in candidates if row["eligible_for_rule_summary"]]
        if not eligible:
            selected[name] = set()
            continue
        newest = max(row["measured_at"] or "" for row in eligible)
        latest = [row for row in eligible if row["measured_at"] == newest]
        latest_values = {(row["canonical_value"], row["canonical_unit"]) for row in latest}
        if len(latest_values) > 1:
            selected[name] = set()
            conflicts.update(int(row["source_index"]) for row in latest)
            continue
        selected[name] = {int(latest[0]["source_index"])}
    return selected, conflicts


def _canonical_lab_key(name: str) -> str | None:
    value = re.sub(r"\s+", " ", name.strip().lower())
    value = _LAB_ALIASES.get(value, value)
    return value if value in _LAB_SPECS else None


def _unit_key(unit: str | None) -> str:
    return (unit or "").strip().lower().replace("×", "*").replace(" ", "")


def _numeric(value: float | str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _normalized_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.strip().split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _dedupe(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))
