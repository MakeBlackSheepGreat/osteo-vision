import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../src/services/apiClient";
import { useCaseStore } from "../src/stores/caseStore";
import type { AnalysisRun, CaseRecord } from "../src/types/case";

describe("case store background jobs", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it("returns null for failed case selection requests without reporting the stale case as success", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_existing", []);
    vi.spyOn(apiClient, "createCase").mockRejectedValue(new Error("create failed"));
    vi.spyOn(apiClient, "getCase").mockRejectedValue(new Error("load failed"));

    const createdCase = await store.createCase("new case");
    expect(createdCase).toBeNull();
    expect(store.error).toBe("create failed");
    expect(store.currentCase?.case_id).toBe("case_existing");

    const loadedCase = await store.loadCase("case_missing");
    expect(loadedCase).toBeNull();
    expect(store.error).toBe("load failed");
    expect(store.currentCase?.case_id).toBe("case_existing");
  });

  it("does not let an older case load overwrite a newer selection", async () => {
    const store = useCaseStore();
    let resolveFirst!: (value: CaseRecord) => void;
    let resolveSecond!: (value: CaseRecord) => void;
    vi.spyOn(apiClient, "getCase")
      .mockReturnValueOnce(new Promise<CaseRecord>((resolve) => { resolveFirst = resolve; }))
      .mockReturnValueOnce(new Promise<CaseRecord>((resolve) => { resolveSecond = resolve; }));

    const first = store.loadCase("case_old");
    const second = store.loadCase("case_new");
    resolveFirst(caseRecord("case_old", []));
    await first;
    expect(store.currentCase).toBeNull();
    resolveSecond(caseRecord("case_new", []));
    await second;

    expect(store.currentCase?.case_id).toBe("case_new");
    expect(store.loading).toBe(false);
  });

  it("clears case-scoped export, job, and navigation state after loading a case", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_existing", []);
    store.exportPath = "old.zip";
    store.exportResult = {
      case_id: "case_existing",
      bundle_path: "old.zip",
      report_path: "old.json",
      manifest_path: "old-manifest.json",
    };
    store.activeAnalysisJobId = "job-old";
    store.activeAnalysisJobStatus = "running";
    store.activeAnalysisJobError = "old error";
    store.activeAnalysisJobProgress = { percent: 50 };
    store.lastAnalysisJobTimedOut = true;
    store.analysisJobPolling = true;
    store.navigationFrameSelection = {
      caseId: "case_existing",
      candidateId: "candidate-old",
      frameKey: "frame-old",
      frameIndex: 1,
      timestampSec: 1,
    };
    vi.spyOn(apiClient, "getCase").mockResolvedValue(caseRecord("case_loaded", []));

    await store.loadCase("case_loaded");

    expect(store.currentCase?.case_id).toBe("case_loaded");
    expect(store.exportPath).toBe("");
    expect(store.exportResult).toBeNull();
    expect(store.activeAnalysisJobId).toBe("");
    expect(store.activeAnalysisJobStatus).toBe("");
    expect(store.activeAnalysisJobError).toBe("");
    expect(store.activeAnalysisJobProgress).toEqual({});
    expect(store.lastAnalysisJobTimedOut).toBe(false);
    expect(store.analysisJobPolling).toBe(false);
    expect(store.navigationFrameSelection).toBeNull();
  });

  it("refreshes the case after export so artifact state is current", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_export", []);
    vi.spyOn(apiClient, "exportCase").mockResolvedValue({
      case_id: "case_export",
      bundle_path: "bundle.zip",
      report_path: "report.json",
      manifest_path: "manifest.json",
    });
    const refreshed = caseRecord("case_export", []);
    refreshed.version = 2;
    refreshed.artifacts = [
      { artifact_id: "artifact-export", case_id: "case_export", kind: "evidence_bundle", path: "bundle.zip" },
    ];
    vi.spyOn(apiClient, "getCase").mockResolvedValue(refreshed);

    await store.exportCase();

    expect(store.exportPath).toBe("bundle.zip");
    expect(store.currentCase?.version).toBe(2);
    expect(store.currentCase?.artifacts[0].path).toBe("bundle.zip");
  });

  it("submits explicit selected input IDs for JPEG analysis", async () => {
    const store = useCaseStore();
    store.currentCase = caseRecord("case_pair", []);
    const startSpy = vi.spyOn(apiClient, "startAnalysis").mockResolvedValue(caseRecord("case_pair", []));

    await store.runAnalysis({ threshold: 0.6 }, [], ["white-001", "fluor-001"]);

    expect(startSpy).toHaveBeenCalledWith(
      "case_pair",
      { threshold: 0.6 },
      [],
      ["white-001", "fluor-001"],
    );
  });

  it("releases global loading while a queued job is polled", async () => {
    vi.useFakeTimers();
    const store = useCaseStore();
    store.currentCase = caseRecord("case_poll", []);
    vi.spyOn(apiClient, "startAnalysisJob").mockResolvedValue({
      job_id: "job-poll",
      kind: "case_analysis",
      status: "queued",
      payload: { case_id: "case_poll" },
      progress: { percent: 0 },
    });
    vi.spyOn(apiClient, "getAnalysisJob").mockResolvedValue({
      job_id: "job-poll",
      kind: "case_analysis",
      status: "completed",
      payload: { case_id: "case_poll" },
      result: { case_id: "case_poll" },
      progress: { percent: 100 },
    });
    vi.spyOn(apiClient, "getCase").mockResolvedValue(caseRecord("case_poll", []));

    const pending = store.runAnalysisJob({ mode: "video_file" });
    await Promise.resolve();
    await Promise.resolve();

    expect(store.loading).toBe(false);
    expect(store.analysisJobPolling).toBe(true);

    await vi.advanceTimersByTimeAsync(1000);
    await pending;
    expect(store.activeAnalysisJobStatus).toBe("completed");
    expect(store.analysisJobPolling).toBe(false);
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
