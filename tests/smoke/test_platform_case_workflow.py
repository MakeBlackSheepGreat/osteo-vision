from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.osteo_vision_api.api.app import create_app


def test_platform_import_review_export_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    case_id = client.post("/cases", json={"title": "smoke"}).json()["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()
    client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )
    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs", json={"selected_input_ids": [], "parameters": {}, "roi_hints": []}
    )
    assert analyzed.json()["analysis_runs"][-1]["status"] == "completed"
    exported = client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})
    assert Path(exported.json()["bundle_path"]).exists()
