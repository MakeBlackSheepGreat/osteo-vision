from __future__ import annotations

from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app


def test_export_api_returns_bundle_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "export"}).json()["case_id"]

    response = client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == case_id
    assert payload["bundle_path"].endswith("_evidence_bundle.zip")
    assert payload["dicom_path"].endswith("_secondary_capture.dcm")
    assert payload["summary"]["total_artifact_count"] >= 6
    assert payload["summary"]["dicom_included"] is True
    assert any(entry["kind"] == "evidence_bundle" for entry in payload["artifact_entries"])

    download_response = client.get("/files/download", params={"path": payload["bundle_path"]})
    assert download_response.status_code == 200
    assert "_evidence_bundle.zip" in download_response.headers["content-disposition"]
