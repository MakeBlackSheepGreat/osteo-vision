from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.models.clinical_feature_vector import (
    DEFAULT_CLINICAL_FEATURE_NAMES,
    SUPPORTED_CLINICAL_FEATURE_NAMES,
    attach_runtime_consumption,
    build_clinical_feature_encoder_contract,
    build_clinical_feature_vector,
    validate_clinical_feature_encoder_contract,
    validate_clinical_feature_vector,
)

CONTEXT_CHECKSUM = "a" * 64
ROOT = Path(__file__).resolve().parents[2]


def _snapshot(**overrides: Any) -> dict[str, Any]:
    value = {
        "age_years": 68,
        "sex_at_birth": "female",
        "comorbidities": ["type_2_diabetes"],
        "comorbidities_reviewed": True,
        "medications": ["recorded_medication"],
        "medications_reviewed": True,
    }
    value.update(overrides)
    return value


def _labs(*, egfr: float = 76.0, eligible: bool = True) -> list[dict]:
    return [
        {
            "source_name": "eGFR",
            "canonical_name": "eGFR",
            "canonical_value": egfr,
            "eligible_for_rule_summary": eligible,
        },
        {
            "source_name": "CRP",
            "canonical_name": "CRP",
            "canonical_value": 18.0,
            "eligible_for_rule_summary": True,
        },
        {
            "source_name": "ALB",
            "canonical_name": "ALB",
            "canonical_value": 42.0,
            "eligible_for_rule_summary": True,
        },
    ]


def test_feature_encoder_contract_binds_order_bounds_masks_and_checksum() -> None:
    feature_names = ["age_years", "diabetes", "crp_mg_l"]
    contract = build_clinical_feature_encoder_contract(feature_names)

    assert contract["feature_names"] == feature_names
    assert contract["feature_bounds"] == {
        "age_years": [0.0, 130.0],
        "diabetes": [0.0, 1.0],
        "crp_mg_l": [0.0, 500.0],
    }
    assert set(contract["mask_semantics"]) == {"present", "missing", "out_of_distribution"}
    assert len(contract["contract_sha256"]) == 64
    assert (
        validate_clinical_feature_encoder_contract(
            contract,
            expected_feature_names=feature_names,
        )
        == []
    )


def test_feature_encoder_contract_rejects_version_bounds_and_checksum_tampering() -> None:
    feature_names = ["age_years", "diabetes"]
    contract = build_clinical_feature_encoder_contract(feature_names)

    version_tampered = deepcopy(contract)
    version_tampered["feature_version"] = "clinical-feature-vector-v2"
    assert set(
        validate_clinical_feature_encoder_contract(
            version_tampered,
            expected_feature_names=feature_names,
        )
    ) == {
        "clinical_feature_encoder_version_incompatible",
        "clinical_feature_encoder_contract_checksum_mismatch",
    }

    bounds_tampered = deepcopy(contract)
    bounds_tampered["feature_bounds"]["age_years"] = [0.0, 150.0]
    assert set(
        validate_clinical_feature_encoder_contract(
            bounds_tampered,
            expected_feature_names=feature_names,
        )
    ) == {
        "clinical_feature_encoder_bounds_mismatch",
        "clinical_feature_encoder_contract_checksum_mismatch",
    }


def test_vector_tracks_present_missing_ood_and_unconsumed_inputs() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )

    assert vector["feature_version"] == "clinical-feature-vector-v1"
    assert vector["feature_names"] == list(DEFAULT_CLINICAL_FEATURE_NAMES)
    assert vector["present_mask"] == [
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]
    assert sum(vector["missing_mask"]) == 4
    assert vector["ood_mask"] == [False] * len(DEFAULT_CLINICAL_FEATURE_NAMES)
    assert vector["recorded_input_domains"] == [
        "age",
        "sex_at_birth",
        "comorbidities",
        "medications",
        "laboratory_results",
    ]
    unconsumed_domains = {item["input_domain"] for item in vector["unconsumed_recorded_inputs"]}
    assert {"medications", "laboratory_results"} <= unconsumed_domains
    assert not validate_clinical_feature_vector(
        vector,
        expected_context_checksum=CONTEXT_CHECKSUM,
        expected_feature_names=DEFAULT_CLINICAL_FEATURE_NAMES,
    )


def test_negative_comorbidity_values_require_explicit_completeness_review() -> None:
    incomplete = build_clinical_feature_vector(
        _snapshot(comorbidities=[], comorbidities_reviewed=False),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )
    reviewed_none = build_clinical_feature_vector(
        _snapshot(comorbidities=[], comorbidities_reviewed=True),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )

    assert {"diabetes", "hypertension", "renal_disease", "immunosuppression"} <= set(
        incomplete["missing_feature_names"]
    )
    assert reviewed_none["model_input_values"][2:6] == [0.0, 0.0, 0.0, 0.0]


def test_negated_or_family_history_comorbidity_mentions_cannot_be_encoded_as_positive() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(
            comorbidities=["no diabetes", "family history of kidney disease"],
            comorbidities_reviewed=True,
        ),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )

    assert vector["present_mask"][2] is False
    assert vector["present_mask"][4] is False
    assert vector["missing_mask"][2] is True
    assert vector["missing_mask"][4] is True
    for row in (vector["feature_rows"][2], vector["feature_rows"][4]):
        assert "ambiguous_comorbidity_text_requires_structured_confirmation" in row["reason_codes"]


def test_out_of_distribution_lab_is_masked_before_checkpoint_input() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(),
        _labs(egfr=240.0),
        context_checksum=CONTEXT_CHECKSUM,
    )

    assert vector["ood_feature_names"] == ["egfr_ml_min_1_73m2"]
    assert vector["ood_mask"] == [False] * (len(DEFAULT_CLINICAL_FEATURE_NAMES) - 1) + [True]
    assert vector["present_mask"][-1] is False
    assert vector["model_input_values"][-1] == 0.0


def test_recorded_unencoded_sex_category_is_ood_and_cannot_be_consumed() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(sex_at_birth="intersex"),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )

    assert vector["ood_feature_names"] == ["sex_at_birth_female"]
    assert vector["ood_mask"][1] is True
    assert vector["present_mask"][1] is False


def test_vector_validation_detects_tampering_and_context_mismatch() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )
    tampered = deepcopy(vector)
    tampered["model_input_values"][0] = 31.0

    assert validate_clinical_feature_vector(
        tampered,
        expected_context_checksum="b" * 64,
        expected_feature_names=DEFAULT_CLINICAL_FEATURE_NAMES,
    ) == [
        "clinical_feature_vector_context_checksum_mismatch",
        "clinical_feature_vector_feature_row_semantics_invalid",
        "clinical_feature_vector_checksum_mismatch",
    ]


def test_vector_validation_rejects_non_finite_values_and_feature_row_semantic_mismatch() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )
    vector["model_input_values"][0] = float("inf")
    vector["feature_rows"][1]["present"] = False

    reasons = validate_clinical_feature_vector(
        vector,
        expected_context_checksum=CONTEXT_CHECKSUM,
        expected_feature_names=DEFAULT_CLINICAL_FEATURE_NAMES,
    )

    assert "clinical_feature_vector_model_input_values_non_finite" in reasons
    assert "clinical_feature_vector_feature_row_semantics_invalid" in reasons
    assert "clinical_feature_vector_checksum_mismatch" in reasons


def test_runtime_consumption_distinguishes_checkpoint_input_from_spatial_application() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )
    engineering_only = attach_runtime_consumption(
        vector,
        checkpoint_sha256="c" * 64,
        context_eligible=True,
        spatial_effect_applied=False,
    )

    assert engineering_only["checkpoint_consumed_count"] == sum(vector["present_mask"])
    assert engineering_only["spatial_effect_applied_mask"] == [False] * len(DEFAULT_CLINICAL_FEATURE_NAMES)
    assert engineering_only["spatially_applied_count"] == 0
    assert len(engineering_only["runtime_vector_checksum"]) == 64


def test_full_platform_vector_encodes_training_contract_features_and_kits_egfr() -> None:
    snapshot = _snapshot(
        comorbidities=["type_2_diabetes", "hypertension", "ckd", "immunosuppression"],
        medications=["denosumab"],
    )
    labs = [
        {
            "source_name": source_name,
            "canonical_name": canonical_name,
            "canonical_value": value,
            "eligible_for_rule_summary": True,
        }
        for source_name, canonical_name, value in (
            ("WBC", "WBC", 8.2),
            ("NEUT%", "NEUT%", 67.0),
            ("CRP", "CRP", 18.0),
            ("ESR", "ESR", 32.0),
            ("HGB", "HGB", 126.0),
            ("eGFR", "eGFR", 76.0),
        )
    ]

    vector = build_clinical_feature_vector(snapshot, labs, context_checksum=CONTEXT_CHECKSUM)

    assert vector["feature_names"] == list(DEFAULT_CLINICAL_FEATURE_NAMES)
    assert vector["present_mask"] == [True] * len(DEFAULT_CLINICAL_FEATURE_NAMES)
    assert vector["model_input_values"] == [
        68.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        8.2,
        67.0,
        18.0,
        32.0,
        126.0,
        76.0,
    ]
    assert vector["unconsumed_recorded_inputs"] == []


def test_platform_vector_covers_full_training_and_kits_runtime_feature_contracts() -> None:
    full_config = yaml.safe_load(
        (ROOT / "configs/training/patient_conditioned_segmentation_proxy.yml").read_text(encoding="utf-8")
    )
    kits_config = yaml.safe_load(
        (ROOT / "configs/training/patient_conditioned_kits23_proxy.yml").read_text(encoding="utf-8")
    )
    full_names = list(full_config["clinical_features"]["names"])
    kits_names = list(kits_config["clinical_features"]["names"])

    assert full_names == list(DEFAULT_CLINICAL_FEATURE_NAMES[:-1])
    assert kits_names == [
        "age_years",
        "sex_at_birth_female",
        "diabetes",
        "renal_disease",
        "egfr_ml_min_1_73m2",
    ]
    assert set(full_names).union(kits_names) == set(SUPPORTED_CLINICAL_FEATURE_NAMES)


def test_free_text_antiresorptive_dose_requires_structured_confirmation() -> None:
    vector = build_clinical_feature_vector(
        _snapshot(medications=["denosumab injection 60 mg"]),
        _labs(),
        context_checksum=CONTEXT_CHECKSUM,
    )
    row = vector["feature_rows"][6]

    assert row["feature_name"] == "antiresorptive_medication"
    assert row["present"] is False
    assert row["missing"] is True
    assert "ambiguous_medication_text_requires_structured_confirmation" in row["reason_codes"]
