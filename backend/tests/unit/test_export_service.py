from __future__ import annotations

from pathlib import Path

from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, ExportRequest
from backend.src.services.export_service import ExportService


def test_export_service_writes_reports(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_export", title="export"))
    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())

    assert Path(response.report_path).exists()
    assert Path(response.manifest_path).exists()
    assert "Research prototype only" in Path(response.report_path).read_text(encoding="utf-8")
