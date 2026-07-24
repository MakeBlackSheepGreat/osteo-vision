from __future__ import annotations

import csv
import hashlib
import json
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

from backend.osteo_vision_api.domains.cases.enums import ArtifactKind, InputChannel
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import (
    AnalysisRun,
    CaseRecord,
    EvidenceArtifact,
    ExportRequest,
    InputCreateRequest,
)
from backend.osteo_vision_api.services import analysis_service as analysis_service_module
from backend.osteo_vision_api.services.analysis_service import AnalysisService
from backend.osteo_vision_api.services.export_service import ExportService
from backend.osteo_vision_api.services.input_service import InputService
from osteo_vision_core.core.schemas import AdapterResult, AdapterStatus


def test_analysis_persists_proxy_checkpoint_evidence_with_spatial_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    white_path, fluorescence_path = _image_pair(tmp_path)
    case = repo.create(
        InputService().add_inputs(
            CaseRecord(case_id="case_bone_activity", title="bone activity checkpoint"),
            [
                InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(white_path)),
                InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(fluorescence_path)),
            ],
        )
    )
    gate_path = tmp_path / "reviewed_bone_gate.png"
    Image.fromarray(np.full((32, 32), 255, dtype=np.uint8)).save(gate_path)
    captured_metadata: dict = {}
    output_dir = tmp_path / "checkpoint_outputs"

    def trusted_gate(*_args, **_kwargs):
        return (
            {
                "path": str(gate_path),
                "sha256": _sha256(gate_path),
                "physician_reviewed": True,
                "trusted_review": True,
                "review_status": "physician_accepted",
                "annotation_id": "annotation_bone_gate",
                "annotation_version": 1,
                "source_input_id": case.inputs[0].input_id,
                "source_checksum": _sha256(white_path),
                "positive_pixel_count": 1024,
                "reviewed_at": "2026-07-19T08:00:00+00:00",
                "reviewed_by": {
                    "actor_id": "doctor.bone-activity",
                    "role": "physician",
                    "institution": "Mianyang Third People's Hospital",
                    "auth_source": "verified_identity_token",
                },
            },
            {
                "status": "selected",
                "reasons": [],
                "physician_reviewed_bone_gate": True,
                "annotation_id": "annotation_bone_gate",
                "annotation_version": 1,
            },
        )

    class FakeBoneActivityAdapter:
        def warmup(self) -> AdapterStatus:
            return AdapterStatus(
                model_id="bone_activity_multitask_d074_proxy_candidate",
                family="bone_activity_multitask",
                available=True,
            )

        def predict(self, request) -> AdapterResult:
            captured_metadata.update(request.metadata)
            output_dir.mkdir(parents=True, exist_ok=True)
            raw_path = output_dir / "raw_engineering_outputs.npz"
            np.savez_compressed(raw_path, activity_score=np.zeros((4, 4), dtype=np.float32))
            evidence_path = output_dir / "checkpoint_evidence.json"
            evidence_path.write_text('{"engineering_inference_executed": true}', encoding="utf-8")
            unsafe_class_map = output_dir / "unsafe_proxy_class_map.png"
            Image.fromarray(np.ones((32, 32), dtype=np.uint8)).save(unsafe_class_map)
            prediction = {
                "schema_version": "osteo-vision-bone-activity-runtime-evidence-v1",
                "available": True,
                "engineering_inference_executed": True,
                "proxy_checkpoint": True,
                "input_domain": "human_brain_ppix_fluorescence_proxy",
                "engineering_ready": True,
                "engineering_utility_ready": False,
                "spatial_candidates_available": True,
                "spatial_effect_applied": True,
                "safe_fallback_applied": False,
                "target_domain_promotion_ready": False,
                "runtime_replacement_allowed": False,
                "checkpoint_sha256": "a" * 64,
                "manifest_sha256": "b" * 64,
                "raw_engineering_outputs": {
                    "available": True,
                    "spatial_use_allowed": True,
                    "path": str(raw_path),
                    "sha256": _sha256(raw_path),
                    "summary": {"finite": True},
                },
                "evidence_manifest_path": str(evidence_path),
                "evidence_manifest_sha256": _sha256(evidence_path),
                "failure_reasons": [],
                "bone_activity_spectrum": {
                    "available": True,
                    "spatial_effect_applied": True,
                    "activity_class_map_path": str(unsafe_class_map),
                    "low_activity_candidate": {
                        "available": True,
                        "path": str(unsafe_class_map),
                        "positive_area_px": 16,
                    },
                },
                "medical_boundary": "Proxy checkpoint engineering evidence requiring physician review.",
            }
            return AdapterResult(
                model_id="bone_activity_multitask_d074_proxy_candidate",
                model_family="bone_activity_multitask",
                prediction=prediction,
                segmentation_mask={"available": True, "path": str(unsafe_class_map)},
                quantification={"low_activity_candidate_area_px": 16},
            )

    monkeypatch.setattr(analysis_service_module, "resolve_trusted_reviewed_bone_gate", trusted_gate)
    monkeypatch.setattr(analysis_service_module, "build_adapter", lambda _spec: FakeBoneActivityAdapter())
    updated = AnalysisService(repo, config_path=str(_config(tmp_path))).start_analysis(
        case,
        [],
        {"threshold": 0.6},
        [],
    )

    run = updated.analysis_runs[-1]
    evidence = run.fused_outputs["bone_activity_checkpoint_evidence"]
    assert run.status == "completed"
    assert captured_metadata["dual_channel_registration_verified"] is True
    assert Path(captured_metadata["fluorescence_path"]).is_file()
    assert captured_metadata["reviewed_bone_gate"]["trusted_review"] is True
    assert captured_metadata["target_domain_input_verified"] is False
    assert evidence["model_id"] == "bone_activity_multitask_d074_proxy_candidate"
    assert evidence["model_family"] == "bone_activity_multitask"
    assert evidence["input_domain"] == "human_brain_ppix_fluorescence_proxy"
    assert evidence["training_domain"]["target_domain"] is False
    assert evidence["engineering_inference_executed"] is True
    assert evidence["proxy_checkpoint"] is True
    assert evidence["spatial_candidates_available"] is False
    assert evidence["spatial_effect_applied"] is False
    assert evidence["safe_fallback_applied"] is True
    assert evidence["raw_engineering_outputs"]["spatial_use_allowed"] is False
    assert evidence["bone_activity_spectrum"]["activity_class_map_path"] is None
    assert evidence["bone_activity_spectrum"]["low_activity_candidate"]["path"] is None
    assert "non_target_domain_proxy" in evidence["failure_reasons"]
    assert run.quantitative_summary["bone_activity_checkpoint"]["spatial_candidates_available"] is False
    kinds = {artifact.kind for artifact in updated.artifacts}
    assert ArtifactKind.BONE_ACTIVITY_CHECKPOINT_EVIDENCE in kinds
    assert ArtifactKind.BONE_ACTIVITY_RAW_ENGINEERING_OUTPUTS in kinds
    checkpoint_artifacts = [
        artifact
        for artifact in updated.artifacts
        if artifact.kind
        in {
            ArtifactKind.BONE_ACTIVITY_CHECKPOINT_EVIDENCE,
            ArtifactKind.BONE_ACTIVITY_RAW_ENGINEERING_OUTPUTS,
        }
    ]
    assert len(checkpoint_artifacts) == 2
    assert all(Path(artifact.path).is_file() and artifact.checksum for artifact in checkpoint_artifacts)
    persisted = repo.get(case.case_id)
    assert persisted is not None
    assert (
        persisted.analysis_runs[-1].fused_outputs["bone_activity_checkpoint_evidence"]["checkpoint_sha256"] == "a" * 64
    )


def test_export_includes_checkpoint_json_npz_report_markdown_csv_and_zip(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    raw_path = tmp_path / "bone_activity_raw.npz"
    np.savez_compressed(raw_path, activity_score=np.zeros((2, 2), dtype=np.float32))
    evidence_path = tmp_path / "bone_activity_evidence.json"
    evidence_path.write_text('{"schema_version": "bone-activity-test-v1"}', encoding="utf-8")
    evidence = {
        "schema_version": "osteo-vision-bone-activity-runtime-evidence-v1",
        "model_id": "bone_activity_multitask_d074_proxy_candidate",
        "model_family": "bone_activity_multitask",
        "execution_state": "completed",
        "engineering_inference_executed": True,
        "proxy_checkpoint": True,
        "input_domain": "human_brain_ppix_fluorescence_proxy",
        "training_domain": {
            "input_domain": "human_brain_ppix_fluorescence_proxy",
            "target_domain": False,
        },
        "engineering_ready": True,
        "engineering_utility_ready": False,
        "spatial_candidates_available": False,
        "spatial_effect_applied": False,
        "safe_fallback_applied": True,
        "target_domain_promotion_ready": False,
        "runtime_replacement_allowed": False,
        "checkpoint_sha256": "c" * 64,
        "manifest_sha256": "d" * 64,
        "raw_engineering_outputs": {
            "available": True,
            "spatial_use_allowed": False,
            "path": str(raw_path),
            "sha256": _sha256(raw_path),
            "summary": {"finite": True},
        },
        "evidence_manifest_path": str(evidence_path),
        "evidence_manifest_sha256": _sha256(evidence_path),
        "failure_reasons": ["non_target_domain_proxy"],
        "reviewed_bone_gate_selection": {"status": "selected"},
        "target_domain_input_gate": {"verified": False},
        "registration_evidence": {"applied": True},
        "medical_boundary": "Proxy engineering evidence with spatial output disabled.",
    }
    case = repo.create(
        CaseRecord(
            case_id="case_bone_activity_export",
            title="bone activity export",
            analysis_runs=[
                AnalysisRun(
                    run_id="run_bone_activity",
                    case_id="case_bone_activity_export",
                    status="completed",
                    fused_outputs={"bone_activity_checkpoint_evidence": evidence},
                )
            ],
            artifacts=[
                EvidenceArtifact(
                    artifact_id="artifact_bone_activity_evidence",
                    case_id="case_bone_activity_export",
                    run_id="run_bone_activity",
                    kind=ArtifactKind.BONE_ACTIVITY_CHECKPOINT_EVIDENCE,
                    path=str(evidence_path),
                    checksum=_sha256(evidence_path),
                ),
                EvidenceArtifact(
                    artifact_id="artifact_bone_activity_raw",
                    case_id="case_bone_activity_export",
                    run_id="run_bone_activity",
                    kind=ArtifactKind.BONE_ACTIVITY_RAW_ENGINEERING_OUTPUTS,
                    path=str(raw_path),
                    checksum=_sha256(raw_path),
                ),
            ],
        )
    )

    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())

    report = json.loads(Path(response.report_path).read_text(encoding="utf-8"))
    section = report["bone_activity_checkpoint_evidence"]
    assert section["evidence_type"] == "checkpoint_engineering_evidence"
    assert section["rule_derived_spectrum_location"] == "video_signal_segmentation"
    assert section["engineering_inference_executed"] is True
    assert section["proxy_checkpoint"] is True
    assert section["input_domain"] == "human_brain_ppix_fluorescence_proxy"
    assert section["spatial_candidates_available"] is False
    assert section["checkpoint_sha256"] == "c" * 64
    assert section["manifest_sha256"] == "d" * 64
    assert section["raw_engineering_outputs"]["sha256"] == _sha256(raw_path)
    assert section["evidence_manifest_sha256"] == _sha256(evidence_path)
    markdown = Path(response.report_path.replace("_report.json", "_report.md")).read_text(encoding="utf-8")
    assert "Bone-Activity Checkpoint Engineering Evidence" in markdown
    assert "checkpoint_engineering_evidence" in markdown
    assert "non_target_domain_proxy" in markdown
    assert "c" * 64 in markdown
    csv_path = next(entry["path"] for entry in response.artifact_entries if entry["kind"] == "quantification_csv")
    csv_rows = list(csv.DictReader(StringIO(Path(csv_path).read_text(encoding="utf-8"))))
    row = next(item for item in csv_rows if item["record_type"] == "bone_activity_checkpoint_engineering_evidence")
    assert row["bone_activity_model_id"] == "bone_activity_multitask_d074_proxy_candidate"
    assert row["bone_activity_engineering_inference_executed"] == "True"
    assert row["bone_activity_input_domain"] == "human_brain_ppix_fluorescence_proxy"
    assert row["bone_activity_spatial_candidates_available"] == "False"
    assert row["bone_activity_checkpoint_sha256"] == "c" * 64
    assert row["bone_activity_raw_engineering_outputs_sha256"] == _sha256(raw_path)
    assert row["bone_activity_failure_reasons"] == "non_target_domain_proxy"
    with ZipFile(response.bundle_path) as archive:
        names = set(archive.namelist())
        bundled_report = json.loads(archive.read(f"reports/{case.case_id}_report.json").decode("utf-8"))
        bundled_csv = archive.read(f"reports/{case.case_id}_quantification.csv").decode("utf-8")
    assert f"artifacts/bone_activity_checkpoint_evidence/{evidence_path.name}" in names
    assert f"artifacts/bone_activity_raw_engineering_outputs/{raw_path.name}" in names
    assert bundled_report["bone_activity_checkpoint_evidence"]["proxy_checkpoint"] is True
    assert "bone_activity_checkpoint_engineering_evidence" in bundled_csv


def _image_pair(tmp_path: Path) -> tuple[Path, Path]:
    rng = np.random.default_rng(19)
    signal = rng.integers(0, 256, size=(32, 32), dtype=np.uint8)
    white_path = tmp_path / "white.jpg"
    fluorescence_path = tmp_path / "fluorescence.jpg"
    Image.fromarray(np.repeat(signal[:, :, None], 3, axis=2)).save(white_path, quality=100)
    Image.fromarray(signal).save(fluorescence_path, quality=100)
    return white_path, fluorescence_path


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "bone_activity.yml"
    path.write_text(
        "\n".join(
            [
                "runtime:",
                "  models:",
                "    - model_id: bone_activity_multitask_d074_proxy_candidate",
                "      family: bone_activity_multitask",
                "      task_types: [segmentation, multitask]",
                "      input_types: [dual_channel_image]",
                "      enabled: true",
                "      clinical_claim_allowed: false",
                "      extra:",
                "        runtime_allowed: true",
                "        candidate_only: true",
                "        engineering_candidate_execution_allowed: true",
                "        runtime_replacement_allowed: false",
                "        mainline_replacement_allowed: false",
                "        strict_promotion_authorized: false",
                "        input_domain: human_brain_ppix_fluorescence_proxy",
                "        target_domain: false",
                "reports:",
                f"  output_dir: {json.dumps(str(tmp_path / 'reports'))}",
                f"  visual_dir: {json.dumps(str(tmp_path / 'visual'))}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
