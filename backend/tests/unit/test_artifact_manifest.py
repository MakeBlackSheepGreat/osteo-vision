from __future__ import annotations

from pathlib import Path

from backend.osteo_vision_api.core.artifacts import checksum_for_file, manifest_record


def test_manifest_record_includes_checksum(tmp_path: Path) -> None:
    target = tmp_path / "artifact.txt"
    target.write_text("artifact", encoding="utf-8")
    record = manifest_record("report_json", target)

    assert record["exists"] is True
    assert record["checksum"] == checksum_for_file(target)
