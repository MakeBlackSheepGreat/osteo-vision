import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../src/services/apiClient";
import { useCaseStore } from "../src/stores/caseStore";
import type { AnalysisRun, CaseRecord } from "../src/types/case";

describe("case store background jobs", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("refreshes an active analysis job without starting a duplicate run", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_job", []);
    store.activeAnalysisJobId = "job_active";
    vi.spyOn(apiClient, "getAnalysisJob").mockResolvedValue({
      job_id: "job_active",
      kind: "case_analysis",
      status: "completed",
      payload: { case_id: "case_job" },
      result: { case_id: "case_job", run_id: "run_done" },
      progress: { phase: "completed", percent: 100, message: "Job completed." },
      error: null,
    });
    vi.spyOn(apiClient, "getCase").mockResolvedValue(caseRecord("case_job", [analysisRun("case_job", "run_done")]));
    const startSpy = vi.spyOn(apiClient, "startAnalysisJob");

    await store.refreshActiveAnalysisJob(0);

    expect(startSpy).not.toHaveBeenCalled();
    expect(store.activeAnalysisJobStatus).toBe("completed");
    expect(store.activeAnalysisJobProgress.percent).toBe(100);
    expect(store.currentCase?.analysis_runs.at(-1)?.run_id).toBe("run_done");
    expect(store.lastAnalysisJobTimedOut).toBe(false);
  });

  it("cancels and retries an active analysis job", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_retry", []);
    store.activeAnalysisJobId = "job_old";
    vi.spyOn(apiClient, "cancelAnalysisJob").mockResolvedValue({
      job_id: "job_old",
      kind: "case_analysis",
      status: "canceled",
      payload: { case_id: "case_retry", parameters: { mode: "video_file" } },
      result: {},
      progress: { phase: "canceled", percent: 40, message: "Job canceled by user." },
      error: "Job canceled by user.",
    });
    vi.spyOn(apiClient, "getAnalysisJob").mockResolvedValue({
      job_id: "job_old",
      kind: "case_analysis",
      status: "canceled",
      payload: { case_id: "case_retry", parameters: { mode: "video_file" } },
      result: {},
      progress: { phase: "canceled", percent: 40, message: "Job canceled by user." },
      error: "Job canceled by user.",
    });
    vi.spyOn(apiClient, "startAnalysisJob").mockResolvedValue({
      job_id: "job_retry",
      kind: "case_analysis",
      status: "completed",
      payload: { case_id: "case_retry", parameters: { mode: "video_file" } },
      result: { case_id: "case_retry", run_id: "run_retry" },
      progress: { phase: "completed", percent: 100, message: "Job completed." },
      error: null,
    });
    vi.spyOn(apiClient, "getCase").mockResolvedValue(caseRecord("case_retry", [analysisRun("case_retry", "run_retry")]));

    await store.cancelActiveAnalysisJob();
    await store.retryActiveAnalysisJob(0);

    expect(store.activeAnalysisJobStatus).toBe("completed");
    expect(store.activeAnalysisJobId).toBe("job_retry");
    expect(store.currentCase?.analysis_runs.at(-1)?.run_id).toBe("run_retry");
  });
});

function caseRecord(caseId: string, analysisRuns: AnalysisRun[]): CaseRecord {
  return {
    case_id: caseId,
    title: "case",
    status: "analyzed",
    version: 1,
    disclaimer_version: "platform-safety-v1",
    review_summary: {},
    inputs: [],
    analysis_runs: analysisRuns,
    rois: [],
    quality_flags: [],
    artifacts: [],
    warnings: [],
    disclaimer: null,
  };
}

function analysisRun(caseId: string, runId: string): AnalysisRun {
  return {
    run_id: runId,
    case_id: caseId,
    method_id: "osteo_vision",
    parameters: {},
    status: "completed",
    candidate_regions: [],
    fused_outputs: {},
    quantitative_summary: {},
    warnings: [],
  };
}
