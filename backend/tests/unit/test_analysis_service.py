from __future__ import annotations

from pathlib import Path

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.repository import JsonCaseRepository
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.input_service import InputService


def test_analysis_service_creates_fluorescence_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_analysis", title="analysis")
    case = InputService().add_inputs(
        case,
        [
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(Path("tests/fixtures/platform/white.png").resolve())),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(Path("tests/fixtures/platform/fluorescence.png").resolve())),
        ],
    )
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(case, [], {"threshold": 0.6}, [])

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.quantitative_summary["positive_area_px"] > 0
    assert Path(run.fused_outputs["outputs"]["overlay_path"]).exists()


def test_analysis_service_accepts_realtime_video_preview(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OSTEO_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    repo = JsonCaseRepository(tmp_path / "cases.json")
    case = CaseRecord(case_id="case_realtime", title="realtime")
    case = InputService().add_inputs(
        case,
        [InputCreateRequest(channel=InputChannel.VIDEO, path="camera://browser/default")],
    )
    repo.create(case)

    updated = AnalysisService(repo).start_analysis(
        case,
        [],
        {"mode": "realtime_video", "source_path": "camera://browser/default"},
        [],
    )

    run = updated.analysis_runs[-1]
    assert run.status == "completed"
    assert run.fused_outputs["mode"] == "realtime_video"
    assert run.fused_outputs["source_path"] == "camera://browser/default"
    assert run.warnings[0]["code"] == "realtime_stream_not_connected"
    assert updated.status == "analyzed"
