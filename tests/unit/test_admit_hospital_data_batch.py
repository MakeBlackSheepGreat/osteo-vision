from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pytest import CaptureFixture, MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]
intake_cli = importlib.import_module("tools.admit_hospital_data_batch")


def _manifest_payload(relative_path: str, *, batch_id: str = "hospital-batch-001") -> dict:
    return {
        "batch_id": batch_id,
        "handover_id": f"handover-{batch_id}",
        "source_organization": "合作医院A",
        "received_by": "project_receiver",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "authorization_status": "approved",
        "usage_scope": "competition_research_validation",
        "deidentification_confirmed": True,
        "deidentification_method": "hospital export review",
        "mapping_held_by_institution": True,
        "target_condition_confirmed": True,
        "files": [
            {
                "external_case_id": "HOSP_CASE_001",
                "path": relative_path,
                "channel": "white_light",
                "acquisition_mode": "white_light",
                "channel_relationship": "single_channel",
                "metadata": {
                    "device": "official microscope",
                    "icg_time_sec": 30,
                    "exposure": "locked",
                    "gain": "locked",
                    "illumination": "locked",
                },
            }
        ],
    }


def _run_cli(manifest: Path, artifact_root: Path, case_store: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/admit_hospital_data_batch.py",
            "--manifest",
            str(manifest),
            "--artifact-root",
            str(artifact_root),
            "--case-store",
            str(case_store),
            "--case-store-backend",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_admit_hospital_data_batch_cli_writes_reports_and_case(tmp_path: Path) -> None:
    artifact_root = tmp_path / "controlled"
    artifact_root.mkdir()
    image_path = artifact_root / "case_001_white.jpg"
    Image.new("RGB", (96, 64), color=(80, 100, 120)).save(image_path, format="JPEG")
    manifest_path = artifact_root / "batch.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(image_path.name), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    case_store = tmp_path / "cases.json"

    completed = _run_cli(manifest_path, artifact_root, case_store)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "completed"
    assert result["admitted_count"] == 1
    assert result["quarantined_count"] == 0
    assert len(result["platform_case_ids"]) == 1
    assert Path(result["report_path"]).is_file()
    assert Path(result["csv_path"]).is_file()
    assert result["case_store_path"] == str(case_store)
    assert result["artifact_attachment"]["status"] == "completed"
    assert result["artifact_attachment"]["attached_case_count"] == 1
    assert result["artifact_attachment"]["expected_case_count"] == 1
    assert Path(result["artifact_attachment"]["status_path"]).is_file()

    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert report["records"][0]["status"] == "admitted"
    assert report["records"][0]["review_state"] == "review_required"
    assert report["records"][0]["training_eligible"] is False
    cases = json.loads(case_store.read_text(encoding="utf-8"))
    assert cases[0]["intake_metadata"]["external_case_id"] == "HOSP_CASE_001"


def test_admit_hospital_data_batch_cli_reports_batch_conflict(tmp_path: Path) -> None:
    artifact_root = tmp_path / "controlled"
    artifact_root.mkdir()
    image_path = artifact_root / "case_001_white.jpg"
    Image.new("RGB", (96, 64), color=(60, 80, 100)).save(image_path, format="JPEG")
    manifest_path = artifact_root / "batch.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(image_path.name), ensure_ascii=False),
        encoding="utf-8",
    )
    case_store = tmp_path / "cases.json"
    assert _run_cli(manifest_path, artifact_root, case_store).returncode == 0

    repeated = _run_cli(manifest_path, artifact_root, case_store)

    assert repeated.returncode == 3
    error = json.loads(repeated.stderr)
    assert error["error"]["code"] == "batch_conflict"
    assert error["error"]["details"]["batch_id"] == "hospital-batch-001"


def test_admit_hospital_data_batch_cli_rejects_invalid_utf8_json_manifest(tmp_path: Path) -> None:
    artifact_root = tmp_path / "controlled"
    artifact_root.mkdir()
    manifest_path = artifact_root / "broken.json"
    manifest_path.write_bytes(b"\xff\xfe{broken")

    completed = _run_cli(manifest_path, artifact_root, tmp_path / "cases.json")

    assert completed.returncode == 2
    error = json.loads(completed.stderr)
    assert error["error"]["code"] == "invalid_manifest"
    assert error["error"]["details"]["manifest_path"] == str(manifest_path)


def test_cli_keeps_exit_zero_and_surfaces_artifact_attachment_errors(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "batch.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload("pending.jpg"), ensure_ascii=False),
        encoding="utf-8",
    )
    status_path = tmp_path / "hospital_intake_artifact_status.json"
    report = {
        "batch_id": "hospital-batch-001",
        "summary": {
            "status": "completed",
            "admitted_count": 1,
            "quarantined_count": 0,
            "case_count": 1,
        },
        "report_path": str(tmp_path / "hospital_intake_report.json"),
        "csv_path": str(tmp_path / "hospital_intake_records.csv"),
        "cases": [{"platform_case_id": "case_001"}],
        "artifact_attachment": {
            "status": "completed_with_errors",
            "status_path": str(status_path),
            "expected_case_count": 1,
            "attached_case_count": 0,
            "attached_case_ids": [],
            "failures": [{"code": "case_artifact_attachment_failed"}],
            "status_persisted": True,
        },
        "medical_boundary": "医生复核边界",
    }
    monkeypatch.setattr(
        intake_cli.HospitalIntakeService,
        "admit_batch",
        lambda self, request: report,
    )

    exit_code = intake_cli.main(
        [
            "--manifest",
            str(manifest_path),
            "--artifact-root",
            str(tmp_path),
            "--case-store",
            str(tmp_path / "cases.json"),
            "--case-store-backend",
            "json",
        ]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "completed_with_errors"
    assert result["artifact_attachment"]["status_path"] == str(status_path)
    assert result["artifact_attachment"]["attached_case_count"] == 0
    assert result["artifact_attachment"]["expected_case_count"] == 1
