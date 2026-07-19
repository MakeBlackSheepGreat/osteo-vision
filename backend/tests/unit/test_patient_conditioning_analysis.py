from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.src.domains.annotations.enums import (
    AnnotationCoordinateSpace,
    AnnotationLabel,
    AnnotationOperationMode,
    AnnotationReviewDecision,
    AnnotationSourceType,
    AnnotationTool,
)
from backend.src.domains.annotations.repository import AnnotationRepository
from backend.src.domains.annotations.schemas import (
    AnnotationCreateRequest,
    AnnotationGeometry,
    AnnotationOperation,
    AnnotationPoint,
    AnnotationSourceRequest,
)
from backend.src.domains.cases.enums import InputChannel, ReviewerRole
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import (
    CaseRecord,
    InputCreateRequest,
    ReviewActorIdentity,
)
from backend.src.services import analysis_service as analysis_service_module
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.input_service import InputService
from backend.src.services.manual_annotation_service import ManualAnnotationService
from backend.src.services.patient_conditioning_gate import resolve_trusted_reviewed_bone_gate
from src.core.schemas import AdapterResult, AdapterStatus

ROOT = Path(__file__).resolve().parents[3]


def test_trusted_reviewed_exposed_bone_annotation_is_selected_and_hash_bound(tmp_path: Path) -> None:
    case_repo, annotation_repo, case, white_input_id = _reviewed_bone_case(tmp_path)

    gate, selection = resolve_trusted_reviewed_bone_gate(
        annotation_repo,
        case_id=case.case_id,
        white_light=next(item for item in case.inputs if item.input_id == white_input_id),
    )

    assert case_repo.get(case.case_id) is not None
    assert gate is not None
    assert selection["status"] == "selected"
    assert gate["physician_reviewed"] is True
    assert gate["trusted_review"] is True
    assert gate["review_status"] == "physician_accepted"
    assert gate["training_eligible"] is False
    assert gate["training_admission_required"] is False
    assert gate["source_input_id"] == white_input_id
    assert len(gate["sha256"]) == 64
    assert Path(gate["path"]).is_file()


def test_multiple_trusted_exposed_bone_annotations_fail_closed(tmp_path: Path) -> None:
    _case_repo, annotation_repo, case, white_input_id = _reviewed_bone_case(tmp_path)
    annotation_service = ManualAnnotationService(
        annotation_repo,
        _case_repo,
        tmp_path / "annotation_artifacts",
    )
    actor = _physician()
    reviewer = _physician_reviewer()
    second = annotation_service.create_annotation(
        case,
        _annotation_request(white_input_id, offset=4),
        actor,
    )
    annotation_service.submit(
        case.case_id,
        second.annotation_id,
        expected_version=1,
        notes=None,
        actor=actor,
    )
    annotation_service.review(
        case.case_id,
        second.annotation_id,
        expected_version=1,
        decision=AnnotationReviewDecision.ACCEPTED,
        notes=None,
        actor=reviewer,
    )

    gate, selection = resolve_trusted_reviewed_bone_gate(
        annotation_repo,
        case_id=case.case_id,
        white_light=next(item for item in case.inputs if item.input_id == white_input_id),
    )

    assert gate is None
    assert selection["status"] == "ambiguous"
    assert selection["reasons"] == ["multiple_trusted_reviewed_exposed_bone_annotations"]
    assert len(selection["eligible_annotation_ids"]) == 2


def test_unverified_registration_fallback_keeps_configured_model_identity(tmp_path: Path) -> None:
    case_repo, annotation_repo, case, _white_input_id = _reviewed_bone_case(tmp_path)
    service = AnalysisService(
        case_repo,
        config_path=str(_patient_conditioning_config(tmp_path)),
        annotation_repository=annotation_repo,
    )
    white = next(item for item in case.inputs if item.channel == InputChannel.WHITE_LIGHT)
    fluorescence = next(item for item in case.inputs if item.channel == InputChannel.FLUORESCENCE)

    evidence, warnings = service._patient_conditioned_ai(
        case=case,
        white=white,
        fluorescence=fluorescence,
        registered_fluorescence_path="",
        registration_evidence={"applied": False, "reason": "low_response_or_large_shift"},
        clinical_context_assessment={},
        output_dir=tmp_path / "patient_conditioning_fallback",
    )

    assert evidence["model_id"] == "patient_conditioning_test"
    assert evidence["model_family"] == "patient_conditioned_segmenter"
    assert evidence["failure_reasons"] == ["dual_channel_registration_unverified"]
    assert warnings[0]["code"] == "patient_conditioning_registration_unverified"


def test_analysis_service_persists_patient_conditioning_comparison_and_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case_repo, annotation_repo, case, _white_input_id = _reviewed_bone_case(tmp_path)
    config_path = _patient_conditioning_config(tmp_path)
    output_root = tmp_path / "adapter_outputs"
    captured_metadata: dict = {}

    class FakePatientAdapter:
        def warmup(self) -> AdapterStatus:
            return AdapterStatus(
                model_id="patient_conditioning_test",
                family="patient_conditioned_segmenter",
                available=True,
            )

        def predict(self, request) -> AdapterResult:
            captured_metadata.update(request.metadata)
            output_root.mkdir(parents=True, exist_ok=True)
            paths: dict[str, str] = {}
            for name in (
                "image_only_probability",
                "conditioned_probability",
                "delta_map",
                "difference_mask",
                "spatial_effect_mask",
                "uncertainty",
                "image_only_mask",
                "conditioned_mask",
            ):
                path = output_root / f"{name}.png"
                Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(path)
                paths[f"{name}_path"] = str(path)
            manifest_path = output_root / "evidence.json"
            manifest_path.write_text("{}", encoding="utf-8")
            prediction = {
                "schema_version": "osteo-vision-patient-conditioned-runtime-v1",
                "available": True,
                "proxy_checkpoint": True,
                "spatial_effect_applied": False,
                "safe_fallback_applied": True,
                "failure_reasons": ["non_target_domain_proxy"],
                "target_domain_promotion_ready": False,
                "runtime_replacement_allowed": False,
                "clinical_context_checksum": request.metadata["clinical_context_assessment"][
                    "clinical_context_checksum"
                ],
                "clinical_present_fraction": 0.6,
                "reviewed_bone_gate": request.metadata["reviewed_bone_gate"],
                "evidence_manifest_path": str(manifest_path),
                "medical_boundary": "Proxy comparison requiring physician review.",
                **paths,
            }
            return AdapterResult(
                model_id="patient_conditioning_test",
                model_family="patient_conditioned_segmenter",
                prediction=prediction,
                quantification={
                    "positive_area_px": 0,
                    "positive_area_fraction": 0.0,
                    "difference_area_px": 0,
                    "spatial_effect_area_px": 0,
                    "delta_abs_mean": 0.0,
                    "uncertainty_mean": 0.5,
                },
                warnings=[],
            )

    monkeypatch.setattr(analysis_service_module, "build_adapter", lambda _spec: FakePatientAdapter())
    updated = AnalysisService(
        case_repo,
        config_path=str(config_path),
        annotation_repository=annotation_repo,
    ).start_analysis(case, [], {"threshold": 0.6}, [])

    run = updated.analysis_runs[-1]
    evidence = run.fused_outputs["patient_conditioning_evidence"]
    assert run.status == "completed"
    assert evidence["model_id"] == "patient_conditioning_test"
    assert evidence["proxy_checkpoint"] is True
    assert evidence["spatial_effect_applied"] is False
    assert evidence["difference_area_fraction"] == 0.0
    assert evidence["physician_reviewed_bone_gate"] is True
    assert evidence["reviewed_bone_gate_selection"]["status"] == "selected"
    assert evidence["target_domain_input_gate"]["verified"] is False
    assert captured_metadata["dual_channel_registration_verified"] is True
    assert captured_metadata["reviewed_bone_gate"]["trusted_review"] is True
    assert captured_metadata["target_domain_input_verified"] is False
    assert captured_metadata["clinical_context_assessment"]["spatial_conditioning_authorized"] is False
    assert run.quantitative_summary["patient_conditioning"]["difference_area_px"] == 0
    patient_paths = {
        evidence[key]
        for key in (
            "image_only_probability_path",
            "conditioned_probability_path",
            "difference_mask_path",
            "evidence_manifest_path",
        )
    }
    persisted = {item.path for item in updated.artifacts}
    assert patient_paths <= persisted
    assert all(item.checksum for item in updated.artifacts if item.path in patient_paths)


def test_analysis_service_runs_registered_patient_checkpoint_with_image_only_fallback(tmp_path: Path) -> None:
    case_repo, annotation_repo, case, _white_input_id = _reviewed_bone_case(tmp_path)
    config_path = _registered_patient_conditioning_config(tmp_path)

    updated = AnalysisService(
        case_repo,
        config_path=str(config_path),
        annotation_repository=annotation_repo,
    ).start_analysis(case, [], {"threshold": 0.6}, [])

    run = updated.analysis_runs[-1]
    evidence = run.fused_outputs["patient_conditioning_evidence"]
    assert run.status == "completed"
    assert evidence["model_id"] == "patient_conditioned_kits23_proxy_candidate"
    assert evidence["available"] is True
    assert evidence["proxy_checkpoint"] is True
    assert evidence["spatial_effect_applied"] is False
    assert evidence["safe_fallback_applied"] is True
    assert evidence["runtime_replacement_allowed"] is False
    assert evidence["difference_area_fraction"] == 0.0
    assert evidence["reviewed_bone_gate_selection"]["status"] == "selected"
    assert evidence["target_domain_input_gate"]["verified"] is False
    assert "non_target_domain_proxy" in evidence["failure_reasons"]
    assert run.quantitative_summary["patient_conditioning"]["difference_area_px"] == 0
    evidence_path = Path(evidence["evidence_manifest_path"])
    assert evidence_path.is_file()
    assert any(item.path == str(evidence_path) and item.checksum for item in updated.artifacts)


def _reviewed_bone_case(
    tmp_path: Path,
) -> tuple[JsonCaseRepository, AnnotationRepository, CaseRecord, str]:
    white_path = tmp_path / "white.jpg"
    fluorescence_path = tmp_path / "fluorescence.jpg"
    rng = np.random.default_rng(17)
    signal = rng.integers(0, 256, size=(32, 32), dtype=np.uint8)
    Image.fromarray(np.repeat(signal[:, :, None], 3, axis=2)).save(white_path, quality=100)
    Image.fromarray(signal).save(fluorescence_path, quality=100)
    case_repo = JsonCaseRepository(tmp_path / "cases.json")
    case = InputService().add_inputs(
        CaseRecord(case_id="case_patient_conditioning", title="patient conditioning"),
        [
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(white_path)),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(fluorescence_path)),
        ],
    )
    case = case_repo.create(case)
    white_input_id = next(item.input_id for item in case.inputs if item.channel == InputChannel.WHITE_LIGHT)
    annotation_repo = AnnotationRepository(tmp_path / "annotations.sqlite")
    annotation_service = ManualAnnotationService(
        annotation_repo,
        case_repo,
        tmp_path / "annotation_artifacts",
    )
    actor = _physician()
    reviewer = _physician_reviewer()
    annotation = annotation_service.create_annotation(
        case,
        _annotation_request(white_input_id),
        actor,
    )
    annotation_service.submit(
        case.case_id,
        annotation.annotation_id,
        expected_version=1,
        notes=None,
        actor=actor,
    )
    annotation_service.review(
        case.case_id,
        annotation.annotation_id,
        expected_version=1,
        decision=AnnotationReviewDecision.ACCEPTED,
        notes=None,
        actor=reviewer,
    )
    return case_repo, annotation_repo, case, white_input_id


def _annotation_request(input_id: str, *, offset: int = 0) -> AnnotationCreateRequest:
    return AnnotationCreateRequest(
        source=AnnotationSourceRequest(source_type=AnnotationSourceType.CASE_JPEG, input_id=input_id),
        label=AnnotationLabel.EXPOSED_BONE,
        geometry=AnnotationGeometry(
            coordinate_space=AnnotationCoordinateSpace.IMAGE_PIXELS,
            operations=[
                AnnotationOperation(
                    tool=AnnotationTool.POLYGON,
                    mode=AnnotationOperationMode.ADD,
                    points=[
                        AnnotationPoint(x=2 + offset, y=2),
                        AnnotationPoint(x=20 + offset, y=2),
                        AnnotationPoint(x=20 + offset, y=20),
                        AnnotationPoint(x=2 + offset, y=20),
                    ],
                )
            ],
        ),
    )


def _physician() -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id="doctor.patient-conditioning",
        role=ReviewerRole.PHYSICIAN,
        institution="Mianyang Third People's Hospital",
        auth_source="verified_identity_token",
    )


def _physician_reviewer() -> ReviewActorIdentity:
    return ReviewActorIdentity(
        actor_id="doctor.patient-conditioning-reviewer",
        role=ReviewerRole.PHYSICIAN,
        institution="Mianyang Third People's Hospital",
        auth_source="verified_identity_token",
    )


def _patient_conditioning_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "patient_conditioning.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: patient_conditioning_test",
                "      family: patient_conditioned_segmenter",
                "      task_types: [segmentation]",
                "      input_types: [dual_channel_image]",
                "      enabled: true",
                "      clinical_claim_allowed: false",
                "      extra:",
                "        runtime_allowed: true",
                "        candidate_only: true",
                "        engineering_candidate_execution_allowed: true",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _registered_patient_conditioning_config(tmp_path: Path) -> Path:
    checkpoint = ROOT / "artifacts/patient_conditioned_kits23_proxy/training/patient_conditioned_manifest_proxy.pt"
    manifest = (
        ROOT / "artifacts/patient_conditioned_kits23_proxy/training/patient_conditioned_manifest_proxy_manifest.json"
    )
    assert checkpoint.is_file()
    assert manifest.is_file()
    config_path = tmp_path / "registered_patient_conditioning.yml"
    config_path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: patient_conditioned_kits23_proxy_candidate",
                "      family: patient_conditioned_segmenter",
                "      task_types: [segmentation]",
                "      input_types: [dual_channel_image]",
                f"      checkpoint_path: {json.dumps(str(checkpoint))}",
                "      dependency_group: torch",
                "      device_policy: cpu",
                "      enabled: true",
                "      clinical_claim_allowed: false",
                "      extra:",
                "        runtime_allowed: true",
                "        candidate_only: true",
                "        engineering_candidate_execution_allowed: true",
                "        runtime_replacement_allowed: false",
                "        strict_promotion_authorized: false",
                f"        checkpoint_manifest_path: {json.dumps(str(manifest))}",
                "        checkpoint_manifest_sha256: 27f1fe208cea184e0ee069ae16165b1d63cc766dcf8d291ebb3602d4cff4e1e3",
                f"        output_dir: {json.dumps(str(tmp_path / 'patient_conditioning_evidence'))}",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )
    return config_path
