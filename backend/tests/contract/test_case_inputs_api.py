from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.api.app import create_app


def test_case_input_and_analysis_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    created = client.post("/cases", json={"title": "contract case"}).json()
    case_id = created["case_id"]
    white = Path("tests/fixtures/platform/white.png").resolve()
    fluorescence = Path("tests/fixtures/platform/fluorescence.png").resolve()

    response = client.post(
        f"/cases/{case_id}/inputs",
        json=[
            {"channel": "white_light", "path": str(white)},
            {"channel": "fluorescence", "path": str(fluorescence)},
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "loaded"
    assert len(payload["inputs"]) == 2

    loaded = client.get(f"/cases/{case_id}")
    assert loaded.status_code == 200
    assert loaded.json()["case_id"] == case_id

    analyzed = client.post(
        f"/cases/{case_id}/analysis-runs",
        json={"selected_input_ids": [], "parameters": {"threshold": 0.6, "colormap": "green"}, "roi_hints": []},
    )
    assert analyzed.status_code == 200
    analyzed_payload = analyzed.json()
    assert analyzed_payload["analysis_runs"]
    assert analyzed_payload["analysis_runs"][-1]["status"] == "completed"


def test_raw_upload_returns_backend_readable_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    source = Path("tests/fixtures/platform/white.png")

    response = client.post(
        "/uploads/raw",
        content=source.read_bytes(),
        headers={"content-type": "image/png", "x-filename": "white.png"},
    )

    assert response.status_code == 200
    payload = response.json()
    uploaded_path = Path(payload["path"])
    assert uploaded_path.exists()
    assert uploaded_path.read_bytes() == source.read_bytes()
