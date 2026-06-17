from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import AnalysisRun, AnalysisRunCreateRequest, CaseRecord
from backend.src.services.analysis_service import AnalysisService


def router(repo: CaseRepository, service: AnalysisService) -> APIRouter:
    api = APIRouter()

    @api.post("/cases/{case_id}/analysis-runs", response_model=CaseRecord)
    def start_analysis(case_id: str, request: AnalysisRunCreateRequest) -> CaseRecord:
        case = repo.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return service.start_analysis(case, request.selected_input_ids, request.parameters, request.roi_hints)

    @api.get("/analysis-runs/{run_id}", response_model=AnalysisRun)
    def get_analysis_run(run_id: str) -> AnalysisRun:
        for case in repo.list():
            for run in case.analysis_runs:
                if run.run_id == run_id:
                    return run
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return api
