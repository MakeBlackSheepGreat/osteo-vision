from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import create_app


def test_export_api_returns_bundle_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "export"}).json()["case_id"]

    response = client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == case_id
    assert payload["bundle_path"].endswith("_bundle.json")
