from __future__ import annotations

from typing import Any

from backend.osteo_vision_api.domains.cases.schemas import AnalysisRun, CaseRecord
from backend.osteo_vision_api.reports.platform_report import build_platform_report


def test_platform_report_serializes_each_run_once_and_preserves_report_values(
    monkeypatch: Any,
) -> None:
    runs = [
        AnalysisRun(
            run_id=f"run_{index}",
            case_id="case_report_cache",
            fused_outputs={"nested": {"value": index}},
        )
        for index in range(3)
    ]
    case = CaseRecord(
        case_id="case_report_cache",
        title="Report cache",
        analysis_runs=runs,
    )
    calls: list[str] = []
    original_model_dump = AnalysisRun.model_dump

    def counted_model_dump(self: AnalysisRun, *args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(self.run_id)
        return original_model_dump(self, *args, **kwargs)

    monkeypatch.setattr(AnalysisRun, "model_dump", counted_model_dump)

    report = build_platform_report(case)

    assert calls == ["run_0", "run_1", "run_2"]
    assert report["case"] == case.model_dump(mode="json")
    assert report["latest_analysis_run"] == report["analysis_runs"][-1]
