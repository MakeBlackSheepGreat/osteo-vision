from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def test_cli_promotes_only_fixture_review_evidence(tmp_path: Path) -> None:
    source_path = tmp_path / "fixture_publication_figure.png"
    Image.new("RGB", (64, 48), (20, 40, 70)).save(source_path)
    mask = np.zeros((48, 64), dtype=np.uint8)
    mask[12:36, 16:48] = 255
    mask_path = tmp_path / "fixture_reviewer_mask.png"
    Image.fromarray(mask).save(mask_path)
    manifest_path = tmp_path / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "fixture_figure_1",
                        "pmcid": "PMC_FIXTURE",
                        "license": "CC BY",
                        "usage_policy": "weak_label_training_seed_with_attribution",
                        "training_seed_allowed": True,
                        "local_path": str(source_path),
                        "source_page_url": "https://example.test/fixture",
                        "asset_url": "https://example.test/fixture.png",
                        "medical_scene": "fixture_jaw_fluorescence_scene",
                        "fluorescence": "fixture_autofluorescence",
                        "sample_weight": 0.25,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    updates_path = tmp_path / "fixture_review_updates.json"
    updates_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "fixture_figure_1",
                        "crop_bbox": [8, 6, 56, 42],
                        "review_state": "modified",
                        "panel_role": "fluorescence_signal",
                        "mask_path": str(mask_path),
                        "review_notes": "test fixture only",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_pmc_figure_review_seed.py"),
            "--manifest",
            str(manifest_path),
            "--review-updates",
            str(updates_path),
            "--output-dir",
            str(output_dir),
            "--no-contact-sheet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["training_candidate_count"] == 1
    payload = json.loads((output_dir / "pmc_figure_training_candidates.json").read_text(encoding="utf-8"))
    assert payload["records"][0]["source_group_id"] == "PMC_FIXTURE"
    assert payload["records"][0]["target_domain_flag"] is False
