from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import backend.osteo_vision_api.services.hospital_intake_service as hospital_intake_module
from backend.osteo_vision_api.api.app import create_app
from backend.osteo_vision_api.domains.cases.repository import JsonCaseRepository
from backend.osteo_vision_api.domains.cases.schemas import CaseRecord


def _jpeg_bytes(value: int = 90) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 64), color=(value, value + 10, value + 20)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload_jpeg(client: TestClient, filename: str, payload: bytes) -> dict[str, Any]:
    response = client.post(
        "/uploads/raw?keyframe_mode=none",
        content=payload,
        headers={"content-type": "image/jpeg", "x-filename": filename},
    )
    assert response.status_code == 200
    return response.json()


def _batch_payload(batch_id: str, uploaded: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload = {
        "batch_id": batch_id,
        "handover_id": f"handover-{batch_id}",
        "source_organization": "合作医院A",
        "received_by": "project_receiver",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "authorization_status": "approved",
        "usage_scope": "competition_research_validation",
        "deidentification_confirmed": True,
        "deidentification_method": "institutional export review",
        "mapping_held_by_institution": True,
        "target_condition_confirmed": True,
        "files": [
            {
                "external_case_id": "HOSP_CASE_001",
                "path": uploaded["path"],
                "channel": "white_light",
                "acquisition_mode": "white_light",
                "channel_relationship": "single_channel",
                "original_filename": uploaded["original_filename"],
                "metadata": {"device": "official microscope", "icg_time_sec": None},
                "missing_fields": ["icg_time_sec", "exposure", "gain", "illumination"],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_hospital_batch_admission_persists_case_provenance_and_checksums(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = _jpeg_bytes()
    uploaded = _upload_jpeg(client, "deidentified_white.jpg", source)
    expected_checksum = hashlib.sha256(source).hexdigest()
    assert uploaded["sha256"] == expected_checksum

    response = client.post("/hospital-intake/batches", json=_batch_payload("batch-001", uploaded))

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["admitted_count"] == 1
    assert payload["summary"]["quarantined_count"] == 0
    assert payload["summary"]["training_eligible_count"] == 0
    record = payload["records"][0]
    assert record["sha256"] == uploaded["sha256"] == expected_checksum
    assert record["target_domain_flag"] is True
    assert record["review_state"] == "review_required"
    assert record["training_eligible"] is False
    assert "图像可读取，但分辨率不符合赛题设备的 3840x2160 规格。" in {item["message"] for item in record["warnings"]}
    assert Path(payload["report_path"]).is_file()
    assert Path(payload["csv_path"]).is_file()

    platform_case_id = record["platform_case_id"]
    stored = client.get(f"/cases/{platform_case_id}")
    assert stored.status_code == 200
    case = stored.json()
    assert case["intake_metadata"]["source_type"] == "institutional_handover"
    assert case["intake_metadata"]["external_case_id"] == "HOSP_CASE_001"
    assert case["intake_metadata"]["target_condition_confirmed"] is True
    assert case["inputs"][0]["metadata"]["sha256"] == record["sha256"]
    assert case["inputs"][0]["metadata"]["training_eligible"] is False
    assert any(item["kind"] == "hospital_intake_manifest" for item in case["artifacts"])


def test_hospital_batch_quarantines_unapproved_or_unconfirmed_handover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "pending.jpg", _jpeg_bytes(70))
    request = _batch_payload(
        "batch-pending",
        uploaded,
        authorization_status="pending",
        deidentification_confirmed=False,
    )

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["admitted_count"] == 0
    assert payload["summary"]["quarantined_count"] == 1
    codes = {item["code"] for item in payload["records"][0]["reasons"]}
    assert {"authorization_not_approved", "deidentification_unconfirmed"} <= codes
    assert payload["case_map"] == {}
    assert payload["records"][0]["target_domain_flag"] is False
    assert payload["summary"]["target_domain_source_count"] == 0


def test_hospital_batch_preserves_multiple_same_channel_files_for_one_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    first = _upload_jpeg(client, "white-first.jpg", _jpeg_bytes(20))
    second = _upload_jpeg(client, "white-second.jpg", _jpeg_bytes(65))
    request = _batch_payload("batch-same-channel", first)
    request["files"].append(
        {
            **request["files"][0],
            "path": second["path"],
            "original_filename": second["original_filename"],
        }
    )

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["admitted_count"] == 2
    platform_case_id = payload["case_map"]["HOSP_CASE_001"]
    case = client.get(f"/cases/{platform_case_id}").json()
    batch_inputs = [item for item in case["inputs"] if item["metadata"].get("batch_id") == "batch-same-channel"]
    assert len(batch_inputs) == 2
    assert {item["channel"] for item in batch_inputs} == {"white_light"}
    assert {item["metadata"]["sha256"] for item in batch_inputs} == {
        first["sha256"],
        second["sha256"],
    }


def test_hospital_batch_quarantines_incomplete_synchronized_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "white_pair.jpg", _jpeg_bytes(50))
    request = _batch_payload("batch-pair", uploaded)
    request["files"][0].update({"channel_relationship": "synchronized_pair", "pair_id": "pair-001"})

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "quarantined"
    assert "synchronized_pair_incomplete" in {item["code"] for item in record["reasons"]}


def test_hospital_batch_quarantines_pair_with_more_than_two_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    white = _upload_jpeg(client, "white.jpg", _jpeg_bytes(40))
    fluorescence_a = _upload_jpeg(client, "fluorescence-a.jpg", _jpeg_bytes(60))
    fluorescence_b = _upload_jpeg(client, "fluorescence-b.jpg", _jpeg_bytes(80))
    request = _batch_payload("batch-pair-extra", white)
    base_file = request["files"][0]
    base_file.update({"channel_relationship": "synchronized_pair", "pair_id": "pair-extra"})
    request["files"] = [
        base_file,
        {
            **base_file,
            "path": fluorescence_a["path"],
            "original_filename": fluorescence_a["original_filename"],
            "channel": "fluorescence",
            "acquisition_mode": "fluorescence",
        },
        {
            **base_file,
            "path": fluorescence_b["path"],
            "original_filename": fluorescence_b["original_filename"],
            "channel": "fluorescence",
            "acquisition_mode": "fluorescence",
        },
    ]

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 3
    assert all(record["status"] == "quarantined" for record in records)
    assert all("synchronized_pair_incomplete" in {item["code"] for item in record["reasons"]} for record in records)


def test_hospital_batch_accepts_nested_acquisition_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "nested-metadata.jpg", _jpeg_bytes(45))
    request = _batch_payload("batch-nested-metadata", uploaded)
    nested_metadata = {
        "device": {"manufacturer": "official", "model": "scope-v1"},
        "icg_time_sec": [{"phase": "baseline", "value": 0.0}],
        "exposure": {"value": 8.0, "unit": "ms"},
        "gain": [1.0, 1.5],
        "illumination": {"mode": "NIR", "power_percent": 60},
    }
    request["files"][0].update({"metadata": nested_metadata, "missing_fields": []})

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "admitted"
    assert record["missing_fields"] == []
    assert record["metadata"]["device"] == nested_metadata["device"]
    assert record["metadata"]["gain"] == nested_metadata["gain"]


def test_hospital_batch_does_not_read_files_outside_controlled_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    outside_path = tmp_path / "outside.jpg"
    outside_path.write_bytes(_jpeg_bytes(35))
    client = TestClient(create_app())
    request = _batch_payload(
        "batch-outside-path",
        {"path": str(outside_path), "original_filename": outside_path.name},
    )

    response = client.post("/hospital-intake/batches", json=request)

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "quarantined"
    assert record["sha256"] == ""
    assert "path_outside_controlled_storage" in {item["code"] for item in record["reasons"]}


def test_hospital_batch_quarantines_jpeg_that_cannot_be_decoded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    upload_dir = artifact_root / "uploads"
    upload_dir.mkdir(parents=True)
    corrupt_path = upload_dir / "corrupt.jpg"
    corrupt_path.write_bytes(b"\xff\xd8\xff\xe0corrupt-jpeg")
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())

    response = client.post(
        "/hospital-intake/batches",
        json=_batch_payload(
            "batch-corrupt-jpeg",
            {"path": str(corrupt_path), "original_filename": corrupt_path.name},
        ),
    )

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "quarantined"
    assert "input_unreadable" in {item["code"] for item in record["reasons"]}


def test_hospital_batch_quarantines_a_file_that_fails_during_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "unstable.jpg", _jpeg_bytes(58))

    def fail_hash(_path: Path) -> str:
        raise OSError("simulated read failure")

    monkeypatch.setattr(hospital_intake_module, "_sha256_file", fail_hash)
    response = client.post(
        "/hospital-intake/batches",
        json=_batch_payload("batch-read-failure", uploaded),
    )

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["status"] == "quarantined"
    assert record["sha256"] == ""
    assert "file_read_failed" in {item["code"] for item in record["reasons"]}


def test_hospital_batch_detects_duplicate_checksum_across_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = _jpeg_bytes(40)
    first = _upload_jpeg(client, "first.jpg", source)
    second = _upload_jpeg(client, "second.jpg", source)
    assert client.post("/hospital-intake/batches", json=_batch_payload("batch-first", first)).status_code == 200

    duplicate = client.post("/hospital-intake/batches", json=_batch_payload("batch-second", second))

    assert duplicate.status_code == 200
    record = duplicate.json()["records"][0]
    assert record["status"] == "quarantined"
    assert "duplicate_previous_batch" in {item["code"] for item in record["reasons"]}


def test_hospital_batch_id_is_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "immutable.jpg", _jpeg_bytes(30))
    request = _batch_payload("batch-fixed", uploaded)
    assert client.post("/hospital-intake/batches", json=request).status_code == 200

    repeated = client.post("/hospital-intake/batches", json=request)

    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "hospital_intake_conflict"


def test_hospital_batch_lookup_rejects_a_sanitized_identifier_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "lookup.jpg", _jpeg_bytes(75))
    assert (
        client.post(
            "/hospital-intake/batches",
            json=_batch_payload("batch.lookup", uploaded),
        ).status_code
        == 200
    )

    response = client.get("/hospital-intake/batches/batch@lookup")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "hospital_intake_not_found"
    invalid = client.get("/hospital-intake/batches/%40%40")
    assert invalid.status_code == 404
    assert invalid.json()["detail"]["code"] == "hospital_intake_not_found"


def test_hospital_batch_keeps_report_success_when_case_artifact_attachment_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    uploaded = _upload_jpeg(client, "artifact-failure.jpg", _jpeg_bytes(68))

    def fail_save(
        _repository: JsonCaseRepository,
        _record: CaseRecord,
    ) -> CaseRecord:
        raise OSError("simulated artifact attachment failure")

    monkeypatch.setattr(JsonCaseRepository, "save", fail_save)
    response = client.post(
        "/hospital-intake/batches",
        json=_batch_payload("batch-artifact-failure", uploaded),
    )

    assert response.status_code == 200
    payload = response.json()
    assert Path(payload["report_path"]).is_file()
    attachment = payload["artifact_attachment"]
    assert attachment["status"] == "completed_with_errors"
    assert attachment["attached_case_count"] == 0
    assert attachment["status_persisted"] is True
    assert Path(attachment["status_path"]).is_file()
    assert attachment["failures"][0]["code"] == "case_artifact_attachment_failed"
    assert attachment["failures"][0]["error_type"] == "OSError"

    stored = client.get("/hospital-intake/batches/batch-artifact-failure")
    assert stored.status_code == 200
    assert stored.json()["artifact_attachment"] == attachment
    platform_case_id = payload["case_map"]["HOSP_CASE_001"]
    case = client.get(f"/cases/{platform_case_id}").json()
    assert case["artifacts"] == []


def test_hospital_batch_retry_after_partial_case_persistence_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    first = _upload_jpeg(client, "retry-first.jpg", _jpeg_bytes(25))
    second = _upload_jpeg(client, "retry-second.jpg", _jpeg_bytes(55))
    request = _batch_payload("batch-retry", first)
    request["files"].append(
        {
            **request["files"][0],
            "external_case_id": "HOSP_CASE_002",
            "path": second["path"],
            "original_filename": second["original_filename"],
        }
    )

    original_create = JsonCaseRepository.create
    create_calls = 0

    def fail_second_create(repository: JsonCaseRepository, record: CaseRecord) -> CaseRecord:
        nonlocal create_calls
        create_calls += 1
        if create_calls == 2:
            raise OSError("simulated case persistence failure")
        return original_create(repository, record)

    monkeypatch.setattr(JsonCaseRepository, "create", fail_second_create)
    with pytest.raises(OSError, match="simulated case persistence failure"):
        client.post("/hospital-intake/batches", json=request)

    report_path = artifact_root / "hospital_intake" / "batch-retry" / "hospital_intake_report.json"
    assert not report_path.exists()
    monkeypatch.setattr(JsonCaseRepository, "create", original_create)

    retry = client.post("/hospital-intake/batches", json=request)

    assert retry.status_code == 200
    payload = retry.json()
    assert payload["summary"]["admitted_count"] == 2
    first_case_id = payload["case_map"]["HOSP_CASE_001"]
    first_case = client.get(f"/cases/{first_case_id}").json()
    matching_inputs = [item for item in first_case["inputs"] if item["metadata"].get("batch_id") == "batch-retry"]
    assert len(matching_inputs) == 1
