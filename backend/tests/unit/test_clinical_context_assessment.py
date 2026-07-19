from datetime import datetime, timedelta, timezone

from backend.src.domains.cases.enums import ReviewerRole
from backend.src.domains.cases.schemas import ClinicalContext, ClinicalLabResult, ReviewActorIdentity
from backend.src.services.clinical_context_assessment import assess_clinical_context, clinical_context_warnings
from src.core.clinical_context_verification import CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS

NOW = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)


def _lab(name: str, value: float | str, unit: str, *, hours_ago: float = 2, flag: str = "unknown") -> ClinicalLabResult:
    return ClinicalLabResult(
        name=name,
        value=value,
        unit=unit,
        measured_at=NOW - timedelta(hours=hours_ago),
        abnormal_flag=flag,
    )


def _verified_context(**overrides) -> ClinicalContext:
    payload = {
        "age_years": 68,
        "sex_at_birth": "female",
        "labs": [_lab("CRP", 1.8, "mg/dL", flag="high")],
        "review_status": "verified",
        "verified_by": ReviewActorIdentity(
            actor_id="doctor-clinical-context",
            role=ReviewerRole.PHYSICIAN,
            institution="Example Stomatology Hospital",
            auth_source="verified_identity_token",
        ),
        "verified_at": NOW - timedelta(hours=1),
    }
    payload.update(overrides)
    return ClinicalContext(**payload)


def test_assessment_normalizes_units_and_never_produces_probability() -> None:
    assessment = assess_clinical_context(
        _verified_context(comorbidities=["type_2_diabetes", " type_2_diabetes "]),
        assessed_at=NOW,
        revision=7,
    )
    lab = assessment["normalized_labs"][0]
    assert lab["canonical_value"] == 18.0
    assert lab["canonical_unit"] == "mg/L"
    assert lab["derived_abnormality"] == "high"
    assert lab["eligible_for_rule_summary"] is True
    assert assessment["rule_based_risk_summary"]["factor_count"] == 2
    assert assessment["rule_based_risk_summary"]["probability"] is None
    assert assessment["calibration_evidence"]["applied"] is False
    assert assessment["spatial_effect_applied"] is False
    feature_vector = assessment["clinical_feature_vector"]
    assert feature_vector["feature_version"] == "clinical-feature-vector-v1"
    assert feature_vector["present_mask"][:3] == [True, True, True]
    assert "renal_disease" in feature_vector["missing_feature_names"]
    assert "egfr_ml_min_1_73m2" in feature_vector["missing_feature_names"]
    assert "crp_mg_l" in feature_vector["eligible_feature_names"]


def test_assessment_normalizes_egfr_for_feature_vector_with_explicit_comorbidity_review() -> None:
    assessment = assess_clinical_context(
        _verified_context(
            comorbidities=[],
            comorbidities_reviewed=True,
            labs=[_lab("eGFR", 74, "mL/min/1.73m2")],
        ),
        assessed_at=NOW,
    )

    row = assessment["normalized_labs"][0]
    vector = assessment["clinical_feature_vector"]
    assert row["canonical_name"] == "eGFR"
    assert row["canonical_value"] == 74.0
    assert vector["present_mask"][-1] is True
    assert vector["model_input_values"][-1] == 74.0


def test_assessment_normalizes_neutrophil_and_hemoglobin_units_for_full_vector() -> None:
    assessment = assess_clinical_context(
        _verified_context(
            comorbidities=[],
            comorbidities_reviewed=True,
            medications=[],
            medications_reviewed=True,
            labs=[
                _lab("neutrophil percent", 82, "%", flag="high"),
                _lab("hemoglobin", 12.6, "g/dL", flag="normal"),
            ],
        ),
        assessed_at=NOW,
    )

    rows = assessment["normalized_labs"]
    vector = assessment["clinical_feature_vector"]
    values = dict(zip(vector["feature_names"], vector["model_input_values"]))
    assert [(row["canonical_name"], row["canonical_value"], row["canonical_unit"]) for row in rows] == [
        ("NEUT%", 82.0, "%"),
        ("HGB", 126.0, "g/L"),
    ]
    assert values["neutrophil_percent"] == 82.0
    assert values["hemoglobin_g_l"] == 126.0


def test_verified_context_requires_complete_trusted_identity_and_timestamp() -> None:
    assessment = assess_clinical_context(
        _verified_context(verified_by=None, verified_at=None),
        assessed_at=NOW,
    )

    quality = assessment["clinical_context_quality"]
    assert quality["status"] == "limited"
    assert quality["issues"] == [
        "clinical_context_verified_by_missing",
        "clinical_context_verified_at_missing",
    ]
    assert "verified_review" in quality["missing_critical_fields"]
    assert assessment["rule_based_risk_summary"]["review_required"] is True


def test_verified_context_rejects_future_and_expired_verification_times() -> None:
    future = assess_clinical_context(
        _verified_context(verified_at=NOW + timedelta(minutes=2)),
        assessed_at=NOW,
    )
    expired = assess_clinical_context(
        _verified_context(verified_at=NOW - timedelta(hours=CLINICAL_CONTEXT_VERIFICATION_VALIDITY_HOURS, seconds=1)),
        assessed_at=NOW,
    )

    assert future["clinical_context_quality"]["issues"] == ["clinical_context_verified_at_in_future"]
    assert expired["clinical_context_quality"]["issues"] == ["clinical_context_verification_expired"]


def test_verified_context_rejects_untrusted_actor_role_auth_source_and_institution() -> None:
    context = _verified_context()
    object.__setattr__(
        context,
        "verified_by",
        ReviewActorIdentity.model_construct(
            actor_id="forged-reviewer",
            role=ReviewerRole.ENGINEERING_REVIEWER,
            institution="",
            auth_source="local_unverified_session",
        ),
    )

    assessment = assess_clinical_context(context, assessed_at=NOW)

    assert assessment["clinical_context_quality"]["issues"] == [
        "clinical_context_verified_actor_role_untrusted",
        "clinical_context_verified_actor_auth_source_untrusted",
        "clinical_context_verified_actor_institution_missing",
    ]


def test_assessment_excludes_stale_future_unsupported_and_superseded_labs() -> None:
    assessment = assess_clinical_context(
        ClinicalContext(
            labs=[
                _lab("CRP", 8, "mg/L", hours_ago=4),
                _lab("CRP", 22, "mg/L", hours_ago=1),
                _lab("WBC", 11, "10^9/L", hours_ago=200),
                _lab("ESR", 30, "mm/h", hours_ago=-2),
                _lab("CRP", 22, "unknown", hours_ago=1),
                _lab("custom marker", 4, "U/L", hours_ago=1),
            ]
        ),
        assessed_at=NOW,
    )
    rows = assessment["normalized_labs"]
    assert rows[0]["duplicate_status"] == "superseded_by_newer_result"
    assert rows[1]["eligible_for_rule_summary"] is True
    assert rows[2]["freshness_status"] == "stale"
    assert rows[3]["freshness_status"] == "future_timestamp"
    assert rows[4]["unit_status"] == "unsupported"
    assert "lab_indicator_unsupported" in rows[5]["issues"]
    assert assessment["rule_based_risk_summary"]["factor_count"] == 1


def test_same_timestamp_conflicting_latest_labs_fail_closed_and_mask_the_feature() -> None:
    first = _lab("eGFR", 80, "mL/min/1.73m2", flag="normal")
    second = _lab("eGFR", 20, "mL/min/1.73m2", flag="low")

    assessment = assess_clinical_context(
        _verified_context(
            comorbidities=[],
            comorbidities_reviewed=True,
            labs=[first, second],
        ),
        assessed_at=NOW,
    )
    reversed_assessment = assess_clinical_context(
        _verified_context(
            comorbidities=[],
            comorbidities_reviewed=True,
            labs=[second, first],
        ),
        assessed_at=NOW,
    )

    assert all(row["duplicate_status"] == "conflicting_latest_results" for row in assessment["normalized_labs"])
    assert all(row["eligible_for_rule_summary"] is False for row in assessment["normalized_labs"])
    assert "lab_latest_result_conflict" in assessment["clinical_context_quality"]["issues"]
    assert assessment["clinical_context_quality"]["status"] == "limited"
    assert assessment["clinical_feature_vector"]["missing_mask"][-1] is True
    assert reversed_assessment["clinical_feature_vector"]["missing_mask"][-1] is True


def test_assessment_checksum_is_deterministic_and_warnings_are_non_blocking() -> None:
    context = ClinicalContext(labs=[_lab("CRP", 2, "mg/L", hours_ago=300)], deidentified=False)
    first = assess_clinical_context(context, assessed_at=NOW, revision=2)
    second = assess_clinical_context(context, assessed_at=NOW + timedelta(hours=1), revision=2)
    assert first["clinical_context_checksum"] == second["clinical_context_checksum"]
    assert len(first["clinical_context_assessment_checksum"]) == 64
    assert "context_deidentification_not_confirmed" in first["clinical_context_quality"]["issues"]
    warnings = clinical_context_warnings(first)
    assert warnings
    assert all(item["blocking"] is False for item in warnings)
