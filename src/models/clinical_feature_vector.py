from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

CLINICAL_FEATURE_VECTOR_SCHEMA = "osteo-vision-clinical-feature-vector-v1"
CLINICAL_FEATURE_VECTOR_VERSION = "clinical-feature-vector-v1"

DEFAULT_CLINICAL_FEATURE_NAMES: tuple[str, ...] = (
    "age_years",
    "sex_at_birth_female",
    "diabetes",
    "hypertension",
    "renal_disease",
    "immunosuppression",
    "antiresorptive_medication",
    "wbc_10e9_l",
    "neutrophil_percent",
    "crp_mg_l",
    "esr_mm_h",
    "hemoglobin_g_l",
    "egfr_ml_min_1_73m2",
)
SUPPORTED_CLINICAL_FEATURE_NAMES = frozenset(DEFAULT_CLINICAL_FEATURE_NAMES)

_FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "age_years": (0.0, 130.0),
    "sex_at_birth_female": (0.0, 1.0),
    "diabetes": (0.0, 1.0),
    "hypertension": (0.0, 1.0),
    "renal_disease": (0.0, 1.0),
    "immunosuppression": (0.0, 1.0),
    "antiresorptive_medication": (0.0, 1.0),
    "wbc_10e9_l": (0.0, 200.0),
    "neutrophil_percent": (0.0, 100.0),
    "crp_mg_l": (0.0, 500.0),
    "esr_mm_h": (0.0, 200.0),
    "hemoglobin_g_l": (20.0, 250.0),
    "egfr_ml_min_1_73m2": (0.0, 200.0),
}

_COMORBIDITY_POSITIVE_TERMS: dict[str, frozenset[str]] = {
    "diabetes": frozenset(
        {
            "diabetes",
            "diabetes mellitus",
            "type 1 diabetes",
            "type 1 diabetes mellitus",
            "type 2 diabetes",
            "type 2 diabetes mellitus",
            "t1dm",
            "t2dm",
            "糖尿病",
            "1型糖尿病",
            "2型糖尿病",
        }
    ),
    "hypertension": frozenset(
        {
            "hypertension",
            "essential hypertension",
            "high blood pressure",
            "高血压",
            "原发性高血压",
        }
    ),
    "renal_disease": frozenset(
        {
            "renal disease",
            "kidney disease",
            "chronic renal disease",
            "chronic kidney disease",
            "ckd",
            "renal insufficiency",
            "kidney insufficiency",
            "renal failure",
            "kidney failure",
            "肾病",
            "慢性肾病",
            "慢性肾脏病",
            "肾功能不全",
            "肾衰竭",
        }
    ),
    "immunosuppression": frozenset(
        {
            "immunosuppression",
            "immune suppression",
            "immunocompromised",
            "免疫抑制",
            "免疫功能低下",
        }
    ),
}
_COMORBIDITY_TOKENS: dict[str, tuple[str, ...]] = {
    "diabetes": ("diabet", "糖尿病"),
    "hypertension": ("hypertension", "high blood pressure", "高血压"),
    "renal_disease": ("renal", "kidney", "ckd", "肾病", "肾功能", "肾脏病", "肾衰"),
    "immunosuppression": ("immunosupp", "immunocomprom", "immune suppress", "免疫抑制", "免疫功能低下"),
}
_ANTIRESORPTIVE_POSITIVE_TERMS = frozenset(
    {
        "antiresorptive medication",
        "antiresorptive therapy",
        "bisphosphonate",
        "bisphosphonates",
        "alendronate",
        "risedronate",
        "ibandronate",
        "pamidronate",
        "zoledronic acid",
        "denosumab",
        "双膦酸盐",
        "阿仑膦酸",
        "利塞膦酸",
        "伊班膦酸",
        "帕米膦酸",
        "唑来膦酸",
        "地舒单抗",
        "抗骨吸收治疗",
    }
)
_ANTIRESORPTIVE_TOKENS = (
    "antiresorptive",
    "bisphosph",
    "alendron",
    "risedron",
    "ibandron",
    "pamidron",
    "zoledron",
    "denosumab",
    "膦酸",
    "地舒单抗",
    "抗骨吸收",
)
_LAB_FEATURE_NAMES: dict[str, frozenset[str]] = {
    "wbc_10e9_l": frozenset({"wbc", "white blood cell", "white blood cell count", "白细胞", "白细胞计数"}),
    "neutrophil_percent": frozenset(
        {"neut%", "neutrophil %", "neutrophil percent", "neutrophil percentage", "中性粒细胞百分比", "中性粒细胞%"}
    ),
    "crp_mg_l": frozenset({"crp", "c reactive protein", "c-reactive protein", "c反应蛋白", "超敏c反应蛋白"}),
    "esr_mm_h": frozenset({"esr", "erythrocyte sedimentation rate", "血沉"}),
    "hemoglobin_g_l": frozenset({"hgb", "hemoglobin", "haemoglobin", "血红蛋白"}),
    "egfr_ml_min_1_73m2": frozenset({"egfr", "estimated glomerular filtration rate", "估算肾小球滤过率"}),
}
_ASSESSMENT_CHECKSUM_EXCLUDED_FIELDS = frozenset(
    {
        "clinical_context_assessment_checksum",
        "spatial_conditioning_authorized",
    }
)


def compute_clinical_context_assessment_checksum(value: Mapping[str, Any]) -> str:
    """Bind the assessment evidence consumed by the runtime, excluding the runtime authorization bit."""
    payload = {key: item for key, item in value.items() if key not in _ASSESSMENT_CHECKSUM_EXCLUDED_FIELDS}
    return _checksum(payload)


def build_clinical_feature_encoder_contract(feature_names: Sequence[str]) -> dict[str, Any]:
    names = _validated_feature_names(feature_names)
    unsupported = [name for name in names if name not in SUPPORTED_CLINICAL_FEATURE_NAMES]
    if unsupported:
        raise ValueError("Unsupported clinical feature names: " + ", ".join(unsupported))
    payload: dict[str, Any] = {
        "schema_version": CLINICAL_FEATURE_VECTOR_SCHEMA,
        "feature_version": CLINICAL_FEATURE_VECTOR_VERSION,
        "feature_names": names,
        "feature_bounds": {name: list(_FEATURE_BOUNDS[name]) for name in names},
        "mask_semantics": {
            "present": "finite_in_distribution_value",
            "missing": "source_missing_or_not_eligible",
            "out_of_distribution": "recorded_value_blocked_by_encoder_bounds_or_category",
        },
    }
    payload["contract_sha256"] = _checksum(payload)
    return payload


def validate_clinical_feature_encoder_contract(
    value: Any,
    *,
    expected_feature_names: Sequence[str],
) -> list[str]:
    if not isinstance(value, Mapping):
        return ["clinical_feature_encoder_contract_missing"]
    expected = build_clinical_feature_encoder_contract(expected_feature_names)
    payload = dict(value)
    reasons: list[str] = []
    if payload.get("schema_version") != CLINICAL_FEATURE_VECTOR_SCHEMA:
        reasons.append("clinical_feature_encoder_schema_incompatible")
    if payload.get("feature_version") != CLINICAL_FEATURE_VECTOR_VERSION:
        reasons.append("clinical_feature_encoder_version_incompatible")
    if payload.get("feature_names") != expected["feature_names"]:
        reasons.append("clinical_feature_encoder_feature_names_mismatch")
    if payload.get("feature_bounds") != expected["feature_bounds"]:
        reasons.append("clinical_feature_encoder_bounds_mismatch")
    if payload.get("mask_semantics") != expected["mask_semantics"]:
        reasons.append("clinical_feature_encoder_mask_semantics_mismatch")
    declared_checksum = str(payload.get("contract_sha256") or "").lower()
    checksum_payload = {key: item for key, item in payload.items() if key != "contract_sha256"}
    if declared_checksum != _checksum(checksum_payload):
        reasons.append("clinical_feature_encoder_contract_checksum_mismatch")
    return list(dict.fromkeys(reasons))


def build_clinical_feature_vector(
    snapshot: Mapping[str, Any],
    normalized_labs: Sequence[Mapping[str, Any]],
    *,
    context_checksum: str,
    feature_names: Sequence[str] = DEFAULT_CLINICAL_FEATURE_NAMES,
) -> dict[str, Any]:
    names = _validated_feature_names(feature_names)
    rows = [_feature_row(name, snapshot=snapshot, normalized_labs=normalized_labs) for name in names]
    present_mask = [bool(row["present"]) for row in rows]
    missing_mask = [bool(row["missing"]) for row in rows]
    ood_mask = [bool(row["out_of_distribution"]) for row in rows]
    recorded_summary = _recorded_input_summary(snapshot, normalized_labs)
    payload: dict[str, Any] = {
        "schema_version": CLINICAL_FEATURE_VECTOR_SCHEMA,
        "feature_version": CLINICAL_FEATURE_VECTOR_VERSION,
        "context_checksum": str(context_checksum).lower(),
        "feature_names": names,
        "model_input_values": [float(row["model_input_value"]) for row in rows],
        "present_mask": present_mask,
        "missing_mask": missing_mask,
        "ood_mask": ood_mask,
        "feature_rows": rows,
        "recorded_input_summary": recorded_summary,
        "recorded_input_domains": _recorded_input_domains(recorded_summary),
        "eligible_feature_names": [name for name, present in zip(names, present_mask) if present],
        "missing_feature_names": [name for name, missing in zip(names, missing_mask) if missing],
        "ood_feature_names": [name for name, ood in zip(names, ood_mask) if ood],
        "unconsumed_recorded_inputs": _unconsumed_recorded_inputs(
            snapshot,
            normalized_labs,
            feature_names=names,
            rows=rows,
        ),
        "safety_boundary": (
            "Missing, unsupported, invalid, stale, or out-of-distribution values are masked before "
            "checkpoint conditioning. Runtime spatial use remains subject to all patient-safety gates."
        ),
    }
    payload["vector_checksum"] = _checksum(payload)
    return payload


def validate_clinical_feature_vector(
    value: Any,
    *,
    expected_context_checksum: str,
    expected_feature_names: Sequence[str],
) -> list[str]:
    if not isinstance(value, Mapping):
        return ["clinical_feature_vector_missing"]
    payload = dict(value)
    reasons: list[str] = []
    names = _validated_feature_names(expected_feature_names)
    if payload.get("schema_version") != CLINICAL_FEATURE_VECTOR_SCHEMA:
        reasons.append("clinical_feature_vector_schema_invalid")
    if payload.get("feature_version") != CLINICAL_FEATURE_VECTOR_VERSION:
        reasons.append("clinical_feature_vector_version_invalid")
    if str(payload.get("context_checksum") or "").lower() != str(expected_context_checksum).lower():
        reasons.append("clinical_feature_vector_context_checksum_mismatch")
    if payload.get("feature_names") != names:
        reasons.append("clinical_feature_vector_checkpoint_features_mismatch")
    expected_length = len(names)
    for field in ("model_input_values", "present_mask", "missing_mask", "ood_mask", "feature_rows"):
        source = payload.get(field)
        if not isinstance(source, list) or len(source) != expected_length:
            reasons.append(f"clinical_feature_vector_{field}_invalid")
    masks = [payload.get(field) for field in ("present_mask", "missing_mask", "ood_mask")]
    valid_masks = [mask for mask in masks if isinstance(mask, list) and len(mask) == expected_length]
    if len(valid_masks) == len(masks):
        for present, missing, ood in zip(*valid_masks):
            if not all(isinstance(item, bool) for item in (present, missing, ood)):
                reasons.append("clinical_feature_vector_mask_type_invalid")
                break
            if int(present) + int(missing) + int(ood) != 1:
                reasons.append("clinical_feature_vector_mask_state_invalid")
                break
    model_values = payload.get("model_input_values")
    if isinstance(model_values, list) and len(model_values) == expected_length:
        if any(_finite_float(item) is None for item in model_values):
            reasons.append("clinical_feature_vector_model_input_values_non_finite")
    feature_rows = payload.get("feature_rows")
    if (
        isinstance(feature_rows, list)
        and len(feature_rows) == expected_length
        and isinstance(model_values, list)
        and len(model_values) == expected_length
        and len(valid_masks) == len(masks)
    ):
        for index, row in enumerate(feature_rows):
            if not isinstance(row, Mapping) or row.get("feature_name") != names[index]:
                reasons.append("clinical_feature_vector_feature_row_semantics_invalid")
                break
            row_value = _finite_float(row.get("model_input_value"))
            expected_value = _finite_float(model_values[index])
            row_state = (row.get("present"), row.get("missing"), row.get("out_of_distribution"))
            expected_state = tuple(mask[index] for mask in valid_masks)
            if row_value != expected_value or row_state != expected_state:
                reasons.append("clinical_feature_vector_feature_row_semantics_invalid")
                break
    expected_checksum = str(payload.get("vector_checksum") or "").lower()
    checksum_payload = {key: item for key, item in payload.items() if key != "vector_checksum"}
    if expected_checksum != _checksum(checksum_payload):
        reasons.append("clinical_feature_vector_checksum_mismatch")
    return list(dict.fromkeys(reasons))


def attach_runtime_consumption(
    feature_vector: Mapping[str, Any],
    *,
    checkpoint_sha256: str,
    context_eligible: bool,
    spatial_effect_applied: bool,
) -> dict[str, Any]:
    payload = dict(feature_vector)
    names = [str(name) for name in payload.get("feature_names") or []]
    present_mask = [bool(value) for value in payload.get("present_mask") or []]
    if len(names) != len(present_mask):
        raise ValueError("Clinical feature vector names and present mask length mismatch")
    consumed_mask = [bool(context_eligible and present) for present in present_mask]
    spatial_mask = [bool(spatial_effect_applied and consumed) for consumed in consumed_mask]
    payload.update(
        {
            "checkpoint_sha256": str(checkpoint_sha256).lower(),
            "checkpoint_context_eligible": bool(context_eligible),
            "checkpoint_consumed_mask": consumed_mask,
            "spatial_effect_applied_mask": spatial_mask,
            "checkpoint_consumed_feature_names": [name for name, consumed in zip(names, consumed_mask) if consumed],
            "spatially_applied_feature_names": [name for name, applied in zip(names, spatial_mask) if applied],
            "checkpoint_consumed_count": sum(consumed_mask),
            "spatially_applied_count": sum(spatial_mask),
            "checkpoint_consumption_status": (
                "spatial_effect_applied"
                if spatial_effect_applied
                else (
                    "engineering_computation_only_safe_fallback"
                    if context_eligible
                    else "context_ineligible_safe_fallback"
                )
            ),
        }
    )
    checksum_payload = {key: item for key, item in payload.items() if key != "runtime_vector_checksum"}
    payload["runtime_vector_checksum"] = _checksum(checksum_payload)
    return payload


def _feature_row(
    name: str,
    *,
    snapshot: Mapping[str, Any],
    normalized_labs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value: float | None
    recorded: bool
    source: str
    reasons: list[str]
    if name == "age_years":
        raw = snapshot.get("age_years")
        value = _finite_float(raw)
        recorded = raw is not None
        source = "clinical_context.age_years"
        reasons = [] if value is not None else ["source_missing" if raw is None else "value_non_numeric"]
    elif name == "sex_at_birth_female":
        sex = str(snapshot.get("sex_at_birth") or "").strip().lower()
        recorded = sex not in {"", "unknown", "not_recorded"}
        source = "clinical_context.sex_at_birth"
        if sex == "female":
            value, reasons = 1.0, []
        elif sex == "male":
            value, reasons = 0.0, []
        elif recorded:
            value, reasons = None, ["category_not_encoded_by_feature_v1"]
        else:
            value, reasons = None, ["source_missing"]
    elif name in _COMORBIDITY_POSITIVE_TERMS:
        values = [_normalize_comorbidity_text(item) for item in snapshot.get("comorbidities") or []]
        matched, ambiguous = _comorbidity_match(name, values)
        reviewed = snapshot.get("comorbidities_reviewed") is True
        recorded = bool(values) or reviewed
        source = "clinical_context.comorbidities"
        if matched:
            value, reasons = 1.0, []
        elif ambiguous:
            value, reasons = None, ["ambiguous_comorbidity_text_requires_structured_confirmation"]
        elif reviewed:
            value, reasons = 0.0, []
        else:
            value, reasons = None, ["comorbidity_absence_not_verified"]
    elif name == "antiresorptive_medication":
        values = [_normalize_recorded_text(item) for item in snapshot.get("medications") or []]
        matched, ambiguous = _recorded_text_match(
            values,
            positive_terms=_ANTIRESORPTIVE_POSITIVE_TERMS,
            tokens=_ANTIRESORPTIVE_TOKENS,
        )
        reviewed = snapshot.get("medications_reviewed") is True
        recorded = bool(values) or reviewed
        source = "clinical_context.medications"
        if matched:
            value, reasons = 1.0, []
        elif ambiguous:
            value, reasons = None, ["ambiguous_medication_text_requires_structured_confirmation"]
        elif reviewed:
            value, reasons = 0.0, []
        else:
            value, reasons = None, ["medication_absence_not_verified"]
    elif name in _LAB_FEATURE_NAMES:
        value, recorded, reasons = _lab_value(name, normalized_labs)
        source = f"clinical_context.normalized_labs.{name}"
    else:
        value = None
        recorded = False
        source = "unsupported"
        reasons = ["feature_not_supported_by_clinical_feature_vector_v1"]

    bounds = _FEATURE_BOUNDS.get(name)
    category_ood = "category_not_encoded_by_feature_v1" in reasons
    out_of_distribution = bool(
        category_ood or (value is not None and (bounds is None or value < bounds[0] or value > bounds[1]))
    )
    if out_of_distribution:
        reasons.append("value_out_of_distribution")
    missing = value is None and not out_of_distribution
    present = value is not None and not out_of_distribution
    return {
        "feature_name": name,
        "source": source,
        "source_recorded": recorded,
        "model_input_value": float(value) if present and value is not None else 0.0,
        "present": present,
        "missing": missing,
        "out_of_distribution": out_of_distribution,
        "bounds": list(bounds) if bounds else None,
        "bounds_source": "clinical-feature-vector-v1-platform-safety-bound",
        "reason_codes": list(dict.fromkeys(reasons or (["eligible_for_checkpoint"] if present else []))),
    }


def _lab_value(
    feature_name: str,
    normalized_labs: Sequence[Mapping[str, Any]],
) -> tuple[float | None, bool, list[str]]:
    matches = [row for row in normalized_labs if _lab_matches_feature(row, feature_name)]
    if not matches:
        return None, False, ["source_missing"]
    eligible_values: list[float] = []
    for row in matches:
        if row.get("eligible_for_rule_summary") is not True:
            continue
        value = _finite_float(row.get("canonical_value"))
        if value is not None:
            eligible_values.append(value)
    if len(eligible_values) == 1:
        return eligible_values[0], True, []
    if len(eligible_values) > 1:
        return None, True, ["multiple_eligible_lab_values_require_review"]
    return None, True, ["lab_value_invalid_stale_or_unsupported"]


def _recorded_input_summary(
    snapshot: Mapping[str, Any],
    normalized_labs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sex = str(snapshot.get("sex_at_birth") or "").strip().lower()
    return {
        "age_recorded": snapshot.get("age_years") is not None,
        "sex_recorded": sex not in {"", "unknown", "not_recorded"},
        "comorbidity_record_count": len(snapshot.get("comorbidities") or []),
        "comorbidities_reviewed": snapshot.get("comorbidities_reviewed") is True,
        "medication_record_count": len(snapshot.get("medications") or []),
        "medications_reviewed": snapshot.get("medications_reviewed") is True,
        "lab_record_count": len(normalized_labs),
        "eligible_lab_record_count": sum(1 for row in normalized_labs if row.get("eligible_for_rule_summary") is True),
    }


def _recorded_input_domains(summary: Mapping[str, Any]) -> list[str]:
    domains: list[str] = []
    if summary.get("age_recorded"):
        domains.append("age")
    if summary.get("sex_recorded"):
        domains.append("sex_at_birth")
    if int(summary.get("comorbidity_record_count") or 0) > 0 or summary.get("comorbidities_reviewed"):
        domains.append("comorbidities")
    if int(summary.get("medication_record_count") or 0) > 0 or summary.get("medications_reviewed"):
        domains.append("medications")
    if int(summary.get("lab_record_count") or 0) > 0:
        domains.append("laboratory_results")
    return domains


def _unconsumed_recorded_inputs(
    snapshot: Mapping[str, Any],
    normalized_labs: Sequence[Mapping[str, Any]],
    *,
    feature_names: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    declared_features = set(feature_names)
    medications = [_normalize_recorded_text(item) for item in snapshot.get("medications") or []]
    antiresorptive_declared = "antiresorptive_medication" in declared_features
    mapped_medication_count = sum(
        1 for item in medications if antiresorptive_declared and item in _ANTIRESORPTIVE_POSITIVE_TERMS
    )
    if len(medications) > mapped_medication_count:
        entries.append(
            {
                "input_domain": "medications",
                "record_count": len(medications) - mapped_medication_count,
                "reason_codes": [
                    (
                        "recorded_medication_not_mapped_to_checkpoint_feature"
                        if antiresorptive_declared
                        else "checkpoint_declares_no_medication_features"
                    )
                ],
            }
        )
    comorbidities = [_normalize_comorbidity_text(item) for item in snapshot.get("comorbidities") or []]
    declared_comorbidity_features = declared_features.intersection(_COMORBIDITY_POSITIVE_TERMS)
    mapped_comorbidity_count = sum(
        1
        for item in comorbidities
        if any(item in _COMORBIDITY_POSITIVE_TERMS[name] for name in declared_comorbidity_features)
    )
    if len(comorbidities) > mapped_comorbidity_count:
        entries.append(
            {
                "input_domain": "comorbidities",
                "record_count": len(comorbidities) - mapped_comorbidity_count,
                "reason_codes": ["recorded_comorbidity_not_mapped_to_checkpoint_feature"],
            }
        )
    unconsumed_labs = [
        row
        for row in normalized_labs
        if not (
            any(name in declared_features and _lab_matches_feature(row, name) for name in _LAB_FEATURE_NAMES)
            and row.get("eligible_for_rule_summary") is True
        )
    ]
    if unconsumed_labs:
        entries.append(
            {
                "input_domain": "laboratory_results",
                "record_count": len(unconsumed_labs),
                "reason_codes": ["recorded_lab_not_consumed_by_checkpoint"],
            }
        )
    for row in rows:
        if row.get("source_recorded") and row.get("present") is not True:
            entries.append(
                {
                    "input_domain": str(row.get("source") or "clinical_feature"),
                    "record_count": 1,
                    "feature_name": row.get("feature_name"),
                    "reason_codes": list(row.get("reason_codes") or ["feature_value_not_eligible"]),
                }
            )
    return entries


def _validated_feature_names(values: Sequence[str]) -> list[str]:
    names = [str(value).strip() for value in values]
    if not names or any(not value for value in names) or len(set(names)) != len(names):
        raise ValueError("Clinical feature names must be non-empty and unique")
    return names


def unsupported_clinical_feature_names(values: Sequence[str]) -> list[str]:
    names = _validated_feature_names(values)
    return [name for name in names if name not in SUPPORTED_CLINICAL_FEATURE_NAMES]


def _normalize_comorbidity_text(value: Any) -> str:
    return _normalize_recorded_text(value)


def _normalize_recorded_text(value: Any) -> str:
    normalized = str(value).strip().casefold().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized)


def _comorbidity_match(name: str, values: Sequence[str]) -> tuple[bool, bool]:
    return _recorded_text_match(
        values,
        positive_terms=_COMORBIDITY_POSITIVE_TERMS[name],
        tokens=_COMORBIDITY_TOKENS[name],
    )


def _recorded_text_match(
    values: Sequence[str],
    *,
    positive_terms: frozenset[str],
    tokens: Sequence[str],
) -> tuple[bool, bool]:
    matched = any(value in positive_terms for value in values)
    ambiguous = any(value not in positive_terms and any(token in value for token in tokens) for value in values)
    return matched, ambiguous


def _lab_matches_feature(row: Mapping[str, Any], feature_name: str) -> bool:
    accepted_names = _LAB_FEATURE_NAMES.get(feature_name, frozenset())
    if not accepted_names:
        return False
    source_name = _normalize_lab_name(row.get("source_name"))
    canonical_name = _normalize_lab_name(row.get("canonical_name"))
    return source_name in accepted_names or canonical_name in accepted_names


def _normalize_lab_name(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("_", " ")
    return re.sub(r"\s+", " ", normalized)


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _checksum(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
