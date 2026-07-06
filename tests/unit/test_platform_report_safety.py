from __future__ import annotations

from pathlib import Path

from backend.src.domains.cases.schemas import CaseRecord, ExportRequest
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.services.export_service import ExportService


def test_exported_platform_report_avoids_unsupported_claims(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_safety", title="safety"))
    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())
    text = Path(response.report_path).read_text(encoding="utf-8").lower()

    assert "platform software for research and competition validation" in text
    assert "automatic diagnosis" not in text
    assert "definitive surgical instruction" not in text
