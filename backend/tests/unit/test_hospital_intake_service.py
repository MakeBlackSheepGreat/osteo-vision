from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import backend.osteo_vision_api.services.hospital_intake_service as hospital_intake_service


def test_existing_checksums_reuses_cached_reports_and_invalidates_on_change(tmp_path: Path) -> None:
    service = hospital_intake_service.HospitalIntakeService(
        artifact_root=tmp_path / "artifacts",
        repo=None,  # type: ignore[arg-type]
        input_service=None,  # type: ignore[arg-type]
    )
    report_path = service.intake_root / "batch-001" / hospital_intake_service.REPORT_FILENAME
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"records": [{"status": "admitted", "sha256": "a" * 64}]}),
        encoding="utf-8",
    )

    with patch.object(hospital_intake_service.json, "loads", wraps=json.loads) as loads:
        assert service._existing_checksums() == {"a" * 64}
        assert service._existing_checksums() == {"a" * 64}
        assert loads.call_count == 1

        report_path.write_text(
            json.dumps({"records": [{"status": "admitted", "sha256": "b" * 64}]}),
            encoding="utf-8",
        )
        assert service._existing_checksums() == {"b" * 64}
        assert loads.call_count == 2
