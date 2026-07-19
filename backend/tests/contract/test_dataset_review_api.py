from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.src.api.app import create_app
from backend.src.services.static_dataset_review import (
    DATASET_RELATIVE_ROOTS,
    REVIEWED_MANIFEST_NAME,
    SEED_MANIFEST_NAME,
)


def _png_base64(values: np.ndarray) -> str:
    buffer = BytesIO()
    Image.fromarray(values.astype(np.uint8)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _write_dataset(project_root: Path, dataset_id: str, record_id: str, *, license_name: str = "CC BY 4.0") -> Path:
    dataset_root = project_root / DATASET_RELATIVE_ROOTS[dataset_id]
    crop_path = dataset_root / "derived/figure_review/crops" / f"{record_id}_crop.png"
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24), color=(40, 90, 55)).save(crop_path)
    queue_path = dataset_root / "derived/figure_review/pmc_figure_review_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": "fixture-v1",
                "records": [
                    {
                        "record_id": f"review_{record_id}",
                        "source_record_id": record_id,
                        "source_group_id": record_id.split("_figure", 1)[0],
                        "source_url": f"https://example.org/{record_id}",
                        "cropped_image_path": str(crop_path),
                        "review_state": "review_required",
                        "review_notes": "pending review",
                        "panel_role": "fluorescence_signal",
                        "license": license_name,
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "sampling_weight": 0.25,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return queue_path


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    _write_dataset(tmp_path, "d047", "PMC47_figure_1")
    _write_dataset(tmp_path, "d048", "PMC48_figure_2")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    return TestClient(create_app())


def test_dataset_review_queue_and_mask_persistence_contract(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    queued = client.get("/dataset-review/queue")

    assert queued.status_code == 200
    payload = queued.json()
    assert payload["record_count"] == 2
    assert payload["items"] == payload["records"]
    item = next(row for row in payload["items"] if row["dataset_id"] == "d047")
    assert item["record_id"] == "review_PMC47_figure_1"
    assert item["image_href"].endswith("/image")
    assert item["mask_path"] is None
    assert item["physician_reviewed"] is False
    assert item["training_eligible"] is False
    assert (item["width"], item["height"]) == (32, 24)
    assert client.get(item["image_href"]).status_code == 200

    mask = np.zeros((24, 32), dtype=np.uint8)
    mask[4:18, 7:24] = 255
    saved = client.post(
        f"/dataset-review/{item['record_id']}/mask",
        json={
            "mask_png_base64": _png_base64(mask),
            "review_state": "modified",
            "reviewer_notes": "physician corrected fluorescence boundary",
            "reviewer_role": "physician",
        },
    )

    assert saved.status_code == 200
    reviewed = saved.json()
    assert reviewed["review_state"] == "modified"
    assert reviewed["physician_reviewed"] is True
    assert reviewed["reviewer_role"] == "physician"
    assert reviewed["review_authority"] == "physician"
    assert reviewed["training_eligible"] is True
    assert reviewed["sample_weight"] == 4.0
    assert reviewed["reviewer_notes"] == "physician corrected fluorescence boundary"
    mask_path = Path(reviewed["mask_path"])
    assert mask_path.is_file()
    assert mask_path.parent == tmp_path / DATASET_RELATIVE_ROOTS["d047"] / "derived/reviewed_masks"
    assert reviewed["label_checksum"] == hashlib.sha256(mask_path.read_bytes()).hexdigest()
    assert client.get(reviewed["mask_href"]).status_code == 200

    reviewed_manifest = tmp_path / "research/datasets/public-candidates" / REVIEWED_MANIFEST_NAME
    manifest_payload = json.loads(reviewed_manifest.read_text(encoding="utf-8"))
    assert manifest_payload["record_count"] == 1
    assert manifest_payload["training_eligible_count"] == 1
    assert manifest_payload["records"][0]["source_group_id"] == "PMC47"
    assert manifest_payload["records"][0]["license"] == "CC BY 4.0"
    assert manifest_payload["records"][0]["checksum"] == reviewed["image_checksum"]

    source_queue = json.loads(
        (tmp_path / DATASET_RELATIVE_ROOTS["d047"] / "derived/figure_review/pmc_figure_review_queue.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_queue["records"][0]["review_state"] == "review_required"
    assert source_queue["records"][0].get("mask_path") is None


def test_dataset_review_mask_validation_and_fail_closed_license(tmp_path: Path, monkeypatch) -> None:
    queue_path = _write_dataset(tmp_path, "d047", "PMC47_figure_1", license_name="All rights reserved")
    _write_dataset(tmp_path, "d048", "PMC48_figure_2")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    record_id = "review_PMC47_figure_1"

    invalid_state = client.post(
        f"/dataset-review/{record_id}/mask",
        json={"mask_png_base64": _png_base64(np.eye(24, 32, dtype=np.uint8) * 255), "review_state": "review_required"},
    )
    assert invalid_state.status_code == 400

    invalid_reviewer = client.post(
        f"/dataset-review/{record_id}/mask",
        json={
            "mask_png_base64": _png_base64(np.eye(24, 32, dtype=np.uint8) * 255),
            "review_state": "accepted",
            "reviewer_role": "unverified_clinician",
        },
    )
    assert invalid_reviewer.status_code == 400

    wrong_size = np.zeros((12, 16), dtype=np.uint8)
    wrong_size[2:8, 2:8] = 255
    assert (
        client.post(
            f"/dataset-review/{record_id}/mask",
            json={"mask_png_base64": _png_base64(wrong_size), "review_state": "accepted"},
        ).status_code
        == 400
    )

    non_binary = np.zeros((24, 32), dtype=np.uint8)
    non_binary[4:18, 7:24] = 127
    assert (
        client.post(
            f"/dataset-review/{record_id}/mask",
            json={"mask_png_base64": _png_base64(non_binary), "review_state": "accepted"},
        ).status_code
        == 400
    )

    almost_full = np.full((24, 32), 255, dtype=np.uint8)
    almost_full[0, 0] = 0
    assert (
        client.post(
            f"/dataset-review/{record_id}/mask",
            json={"mask_png_base64": _png_base64(almost_full), "review_state": "accepted"},
        ).status_code
        == 400
    )

    valid = np.zeros((24, 32), dtype=np.uint8)
    valid[4:18, 7:24] = 255
    saved = client.post(
        f"/dataset-review/{record_id}/mask",
        json={"mask_png_base64": _png_base64(valid), "review_state": "accepted"},
    )
    assert saved.status_code == 200
    assert saved.json()["training_eligible"] is False
    assert saved.json()["physician_reviewed"] is False
    assert saved.json()["reviewer_role"] == "project_reviewer"
    assert json.loads(queue_path.read_text(encoding="utf-8"))["records"][0]["license"] == "All rights reserved"


def test_dataset_review_rejects_unknown_record_and_escaped_crop(tmp_path: Path, monkeypatch) -> None:
    queue_path = _write_dataset(tmp_path, "d047", "PMC47_figure_1")
    outside = tmp_path / "outside.png"
    Image.new("RGB", (32, 24), color="white").save(outside)
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    payload["records"][0]["cropped_image_path"] = str(outside)
    queue_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())

    queued = client.get("/dataset-review/queue")
    assert queued.status_code == 200
    assert queued.json()["record_count"] == 0
    assert queued.json()["skipped_invalid_record_count"] == 1
    unknown = client.post(
        "/dataset-review/review_PMC47_figure_1/mask",
        json={"mask_png_base64": _png_base64(np.eye(24, 32, dtype=np.uint8) * 255), "review_state": "accepted"},
    )
    assert unknown.status_code == 403


def test_dataset_review_generates_editable_automatic_seed(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    record_id = "review_PMC47_figure_1"

    seeded = client.post(
        f"/dataset-review/{record_id}/seed",
        json={"threshold": 0.6, "colormap": "green"},
    )

    assert seeded.status_code == 200
    item = seeded.json()
    assert item["review_state"] == "review_required"
    assert item["reviewer_role"] == "automated_seed"
    assert item["review_authority"] == "automated_heuristic"
    assert item["physician_reviewed"] is False
    assert item["training_eligible"] is False
    assert item["record_kind"] == "automated_seed"
    assert item["mask_source"] == "heuristic_fluorescence_hotspot_seed"
    assert item["threshold"] == 0.6
    assert item["colormap"] == "green"
    assert item["quality_status"] == "warning"
    assert "empty_seed_mask" in item["quality_warnings"]
    assert Path(item["mask_path"]).is_file()
    assert client.get(item["mask_href"]).status_code == 200

    queued = client.get("/dataset-review/queue").json()
    queued_item = next(row for row in queued["items"] if row["record_id"] == record_id)
    assert queued["seed_count"] == 1
    assert queued_item["mask_href"] == item["mask_href"]
    assert queued_item["training_eligible"] is False

    common_root = tmp_path / "research/datasets/public-candidates"
    seed_manifest = json.loads((common_root / SEED_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert seed_manifest["record_count"] == 1
    assert seed_manifest["training_eligible_count"] == 0
    assert seed_manifest["records"][0]["mask_source"] == "heuristic_fluorescence_hotspot_seed"
    assert not (common_root / REVIEWED_MANIFEST_NAME).exists()


def test_dataset_review_seed_keeps_abnormal_full_mask_for_review(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    seeded = client.post(
        "/dataset-review/review_PMC48_figure_2/seed",
        json={"threshold": 0.0, "colormap": "amber"},
    )

    assert seeded.status_code == 200
    item = seeded.json()
    assert item["positive_area_fraction"] == 1.0
    assert "seed_mask_area_above_review_threshold" in item["quality_warnings"]
    assert item["training_eligible"] is False

    invalid_colormap = client.post(
        "/dataset-review/review_PMC48_figure_2/seed",
        json={"threshold": 0.6, "colormap": "rainbow"},
    )
    assert invalid_colormap.status_code == 400


def test_dataset_review_exposes_uncropped_source_and_persists_crop(tmp_path: Path, monkeypatch) -> None:
    d047_queue = _write_dataset(tmp_path, "d047", "PMC47_figure_uncropped")
    _write_dataset(tmp_path, "d048", "PMC48_figure_2")
    payload = json.loads(d047_queue.read_text(encoding="utf-8"))
    crop_path = Path(payload["records"][0]["cropped_image_path"])
    payload["records"][0]["local_path"] = str(crop_path)
    payload["records"][0]["cropped_image_path"] = None
    payload["records"][0]["crop_bbox"] = None
    d047_queue.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    record_id = "review_PMC47_figure_uncropped"

    queued = client.get("/dataset-review/queue").json()
    item = next(row for row in queued["items"] if row["record_id"] == record_id)
    assert queued["record_count"] == 2
    assert item["crop_required"] is True
    assert item["mask_href"] is None
    assert client.get(item["image_href"]).status_code == 200

    invalid = client.post(
        f"/dataset-review/{record_id}/crop",
        json={"x": 20, "y": 10, "width": 20, "height": 16},
    )
    assert invalid.status_code == 400

    saved = client.post(
        f"/dataset-review/{record_id}/crop",
        json={
            "x": 4,
            "y": 3,
            "width": 20,
            "height": 16,
            "panel_role": "paired_fluorescence",
            "pair_id": "PMC47_pair_1",
            "crop_notes": "fluorescence panel",
        },
    )
    assert saved.status_code == 200
    cropped = saved.json()
    assert cropped["crop_required"] is False
    assert cropped["crop_bbox"] == {"x": 4, "y": 3, "width": 20, "height": 16}
    assert cropped["panel_role"] == "paired_fluorescence"
    assert cropped["pair_id"] == "PMC47_pair_1"
    assert (cropped["width"], cropped["height"]) == (20, 16)
    assert Path(cropped["image_path"]).is_file()

    persisted = json.loads(d047_queue.read_text(encoding="utf-8"))["records"][0]
    assert persisted["crop_bbox"] == {"x": 4, "y": 3, "width": 20, "height": 16}
    assert persisted["crop_source_checksum"]
    seeded = client.post(
        f"/dataset-review/{record_id}/seed",
        json={"threshold": 0.6, "colormap": "green"},
    )
    assert seeded.status_code == 200
    assert seeded.json()["training_eligible"] is False


def test_dataset_review_accepts_traced_crop_suggestion_and_keeps_mask_gate(tmp_path: Path, monkeypatch) -> None:
    d047_queue = _write_dataset(tmp_path, "d047", "PMC47_figure_suggested")
    _write_dataset(tmp_path, "d048", "PMC48_figure_2")
    payload = json.loads(d047_queue.read_text(encoding="utf-8"))
    source_path = Path(payload["records"][0]["cropped_image_path"])
    Image.new("RGB", (160, 120), color=(40, 90, 55)).save(source_path)
    payload["records"][0].update(
        {
            "local_path": str(source_path),
            "cropped_image_path": None,
            "crop_bbox": None,
            "suggestion_id": "suggestion_fixture_1",
            "suggested_crop_bbox": {"x": 10, "y": 12, "width": 100, "height": 80},
            "suggested_panel_role": "paired_fluorescence",
            "suggested_pair_id": "fixture_pair",
            "suggested_pair_alignment": "approximate_view",
            "suggestion_method": "fixture",
            "suggestion_score": 0.95,
            "suggestion_quality_status": "pass",
            "suggestion_quality_warnings": [],
            "record_kind": "crop_suggestion",
        }
    )
    d047_queue.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OSTEO_DATASET_REVIEW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OSTEO_CASE_STORE_PATH", str(tmp_path / "cases.json"))
    client = TestClient(create_app())
    record_id = "review_PMC47_figure_suggested"

    queued = client.get("/dataset-review/queue").json()
    item = next(row for row in queued["items"] if row["record_id"] == record_id)
    assert item["suggested_crop_bbox"] == {"x": 10, "y": 12, "width": 100, "height": 80}
    assert item["suggested_pair_alignment"] == "approximate_view"

    mismatch = client.post(
        f"/dataset-review/{record_id}/crop",
        json={
            "x": 12,
            "y": 12,
            "width": 100,
            "height": 80,
            "suggestion_id": "suggestion_fixture_1",
            "crop_review_action": "accepted",
        },
    )
    assert mismatch.status_code == 400

    saved = client.post(
        f"/dataset-review/{record_id}/crop",
        json={
            "x": 10,
            "y": 12,
            "width": 100,
            "height": 80,
            "panel_role": "paired_fluorescence",
            "pair_id": "fixture_pair",
            "suggestion_id": "suggestion_fixture_1",
            "crop_review_action": "accepted",
        },
    )
    assert saved.status_code == 200
    saved_payload = saved.json()
    assert saved_payload["crop_review_action"] == "accepted"
    assert saved_payload["review_state"] == "review_required"
    assert saved_payload["training_eligible"] is False
