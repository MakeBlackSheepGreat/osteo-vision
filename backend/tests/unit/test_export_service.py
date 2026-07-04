from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pydicom

from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, ExportRequest
from backend.src.services.export_service import ExportService


def test_export_service_writes_reports(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = repo.create(CaseRecord(case_id="case_export", title="export"))
    response = ExportService(repo, tmp_path / "exports").export_case(case, ExportRequest())

    assert Path(response.report_path).exists()
    assert Path(response.manifest_path).exists()
    assert response.dicom_path is not None
    assert Path(response.dicom_path).exists()
    assert Path(response.bundle_path).suffix == ".zip"
    assert response.summary["total_artifact_count"] >= 6
    assert response.summary["dicom_included"] is True
    assert any(entry["kind"] == "evidence_bundle" for entry in response.artifact_entries)
    with ZipFile(response.bundle_path) as archive:
        assert f"reports/{case.case_id}_report.json" in archive.namelist()
        assert f"reports/{case.case_id}_secondary_capture.dcm" in archive.namelist()
        assert f"reports/{case.case_id}_quantification.csv" in archive.namelist()
    dicom = pydicom.dcmread(response.dicom_path)
    assert dicom.SOPClassUID == pydicom.uid.SecondaryCaptureImageStorage
    assert dicom.PatientIdentityRemoved == "YES"
    assert dicom.Rows > 0
    assert dicom.Columns > 0
    assert "Research prototype only" in Path(response.report_path).read_text(encoding="utf-8")
