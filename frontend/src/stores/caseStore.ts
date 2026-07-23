import { defineStore } from "pinia";

import { apiClient, type BackendJob, type BackendJobProgress } from "../services/apiClient";
import type {
  CaseInputDraft,
  CaseRecord,
  ClinicalContext,
  ExportResponse,
  NavigationFrameSelection,
  ReviewState,
} from "../types/case";

let loadCaseRequestId = 0;

export const useCaseStore = defineStore("case", {
  state: () => ({
    currentCase: null as CaseRecord | null,
    loading: false,
    error: "",
    exportPath: "",
    exportResult: null as ExportResponse | null,
    activeAnalysisJobId: "",
    activeAnalysisJobStatus: "",
    activeAnalysisJobError: "",
    activeAnalysisJobProgress: {} as BackendJobProgress,
    lastAnalysisJobTimedOut: false,
    analysisJobPolling: false,
    navigationFrameSelection: null as NavigationFrameSelection | null,
  }),
  actions: {
    selectNavigationFrame(selection: NavigationFrameSelection | null) {
      this.navigationFrameSelection = selection;
    },
    async createCase(title: string) {
      this.loading = true;
      this.error = "";
      try {
        const createdCase = await apiClient.createCase(title);
        this.resetCaseScopedState();
        this.currentCase = createdCase;
        return createdCase;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "病例创建失败";
        return null;
      } finally {
        this.loading = false;
      }
    },
    async loadCase(caseId: string) {
      const requestId = ++loadCaseRequestId;
      this.loading = true;
      this.error = "";
      try {
        const loadedCase = await apiClient.getCase(caseId);
        if (requestId !== loadCaseRequestId) return null;
        this.resetCaseScopedState();
        this.currentCase = loadedCase;
        return loadedCase;
      } catch (error) {
        if (requestId !== loadCaseRequestId) return null;
        this.error = error instanceof Error ? error.message : "病例加载失败";
        return null;
      } finally {
        if (requestId === loadCaseRequestId) this.loading = false;
      }
    },
    async importInputs(inputs: CaseInputDraft[]) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.addInputs(this.currentCase.case_id, inputs);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "输入写入失败";
      } finally {
        this.loading = false;
      }
    },
    async saveClinicalContext(context: ClinicalContext) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.updateClinicalContext(this.currentCase.case_id, context);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "临床上下文保存失败";
      } finally {
        this.loading = false;
      }
    },
    async runAnalysis(
      parameters: Record<string, unknown>,
      roiHints: Array<Record<string, unknown>> = [],
      selectedInputIds: string[] = [],
    ) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.startAnalysis(
          this.currentCase.case_id,
          parameters,
          roiHints,
          selectedInputIds,
        );
      } catch (error) {
        this.error = error instanceof Error ? error.message : "分析运行失败";
      } finally {
        this.loading = false;
      }
    },
    async runAnalysisJob(
      parameters: Record<string, unknown>,
      roiHints: Array<Record<string, unknown>> = [],
      selectedInputIds: string[] = [],
    ) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      this.lastAnalysisJobTimedOut = false;
      this.activeAnalysisJobError = "";
      try {
        const caseId = this.currentCase.case_id;
        const started = await apiClient.startAnalysisJob(caseId, parameters, roiHints, selectedInputIds);
        this.activeAnalysisJobId = started.job_id;
        this.loading = false;
        await this.pollAnalysisJob(started, caseId, 300);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "后台分析任务失败";
      } finally {
        this.loading = false;
      }
    },
    async refreshActiveAnalysisJob(maxAttempts = 60) {
      if (!this.activeAnalysisJobId) {
        this.error = "暂无可查询的后台分析任务";
        return;
      }
      this.loading = true;
      this.error = "";
      try {
        const job = await apiClient.getAnalysisJob(this.activeAnalysisJobId);
        const caseId = stringFrom(job.result?.case_id) || stringFrom(job.payload?.case_id) || this.currentCase?.case_id;
        this.loading = false;
        await this.pollAnalysisJob(job, caseId, maxAttempts);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "后台分析任务查询失败";
      } finally {
        this.loading = false;
      }
    },
    async cancelActiveAnalysisJob() {
      if (!this.activeAnalysisJobId) {
        this.error = "暂无可取消的后台分析任务";
        return;
      }
      this.error = "";
      try {
        const job = await apiClient.cancelAnalysisJob(this.activeAnalysisJobId);
        this.activeAnalysisJobStatus = job.status;
        this.activeAnalysisJobError = job.error ?? "";
        this.activeAnalysisJobProgress = job.progress ?? {};
        this.lastAnalysisJobTimedOut = false;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "后台分析任务取消失败";
      }
    },
    async retryActiveAnalysisJob(maxAttempts = 300) {
      if (!this.activeAnalysisJobId) {
        this.error = "暂无可重试的后台分析任务";
        return;
      }
      this.loading = true;
      this.error = "";
      this.lastAnalysisJobTimedOut = false;
      try {
        const previousJob = await apiClient.getAnalysisJob(this.activeAnalysisJobId);
        const caseId = stringFrom(previousJob.payload?.case_id) || stringFrom(previousJob.result?.case_id) || this.currentCase?.case_id;
        const parameters = recordFrom(previousJob.payload?.parameters) ? previousJob.payload.parameters : {};
        const roiHints = Array.isArray(previousJob.payload?.roi_hints) ? previousJob.payload.roi_hints : [];
        const selectedInputIds = Array.isArray(previousJob.payload?.selected_input_ids)
          ? previousJob.payload.selected_input_ids.filter((value): value is string => typeof value === "string")
          : [];
        if (!caseId) {
          this.error = "后台分析任务缺少病例编号，无法重试";
          return;
        }
        const retryJob = await apiClient.startAnalysisJob(
          caseId,
          parameters,
          roiHints as Array<Record<string, unknown>>,
          selectedInputIds,
        );
        this.loading = false;
        await this.pollAnalysisJob(retryJob, caseId, maxAttempts);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "后台分析任务重试失败";
      } finally {
        this.loading = false;
      }
    },
    async pollAnalysisJob(initialJob: BackendJob, caseId: string | undefined, maxAttempts: number) {
      let job = initialJob;
      const jobId = job.job_id;
      this.activeAnalysisJobId = job.job_id;
      this.activeAnalysisJobStatus = job.status;
      this.activeAnalysisJobError = job.error ?? "";
      this.activeAnalysisJobProgress = job.progress ?? {};
      this.lastAnalysisJobTimedOut = false;
      this.analysisJobPolling = true;

      try {
        for (let attempt = 0; attempt < maxAttempts && ["queued", "running"].includes(job.status); attempt += 1) {
          await sleep(1000);
          if (this.activeAnalysisJobId !== jobId) return;
          job = await apiClient.getAnalysisJob(job.job_id);
          if (this.activeAnalysisJobId !== jobId) return;
          this.activeAnalysisJobStatus = job.status;
          this.activeAnalysisJobError = job.error ?? "";
          this.activeAnalysisJobProgress = job.progress ?? {};
        }

        const resolvedCaseId = caseId || stringFrom(job.result?.case_id) || stringFrom(job.payload?.case_id);
        if (resolvedCaseId && this.currentCase?.case_id === resolvedCaseId) {
          const refreshedCase = await apiClient.getCase(resolvedCaseId);
          if (this.activeAnalysisJobId === jobId && this.currentCase?.case_id === resolvedCaseId) {
            this.currentCase = refreshedCase;
          }
        }
        if (this.activeAnalysisJobId !== jobId) return;
        if (job.status === "failed") {
          this.activeAnalysisJobError = job.error || "后台分析任务失败";
          this.error = this.activeAnalysisJobError;
        } else if (job.status === "canceled") {
          this.activeAnalysisJobError = job.error || "后台分析任务已取消";
        } else if (["queued", "running"].includes(job.status)) {
          this.lastAnalysisJobTimedOut = true;
        }
      } finally {
        if (this.activeAnalysisJobId === jobId) {
          this.analysisJobPolling = false;
        }
      }
    },
    async exportCase() {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        const caseId = this.currentCase.case_id;
        const result = await apiClient.exportCase(caseId);
        this.exportResult = result;
        this.exportPath = result.bundle_path;
        this.currentCase = await apiClient.getCase(caseId);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "证据包导出失败";
      } finally {
        this.loading = false;
      }
    },
    resetCaseScopedState() {
      this.exportPath = "";
      this.exportResult = null;
      this.activeAnalysisJobId = "";
      this.activeAnalysisJobStatus = "";
      this.activeAnalysisJobError = "";
      this.activeAnalysisJobProgress = {};
      this.lastAnalysisJobTimedOut = false;
      this.analysisJobPolling = false;
      this.navigationFrameSelection = null;
    },
    async addReviewEvent(action: string, targetId: string, afterState?: string) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.addReviewEvent(this.currentCase.case_id, action, targetId, afterState);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "复核记录写入失败";
      } finally {
        this.loading = false;
      }
    },
    async updateRegion(
      regionId: string,
      reviewState: ReviewState,
      geometry?: Record<string, unknown>,
      label?: string,
    ) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.updateRegion(this.currentCase.case_id, regionId, reviewState, geometry, label);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "ROI 复核写入失败";
      } finally {
        this.loading = false;
      }
    },
    async addRegionFromCandidate(candidateId: string) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.addRegionFromCandidate(this.currentCase.case_id, candidateId);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "候选区转 ROI 失败";
      } finally {
        this.loading = false;
      }
    },
    async updateCandidateRegionState(
      candidateId: string,
      reviewState: ReviewState,
      geometry?: Record<string, unknown>,
      label?: string,
      reviewerNotes?: string,
    ) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.updateCandidateRegion(
          this.currentCase.case_id,
          candidateId,
          reviewState,
          geometry,
          label,
          reviewerNotes,
        );
      } catch (error) {
        this.error = error instanceof Error ? error.message : "候选区复核状态写入失败";
      } finally {
        this.loading = false;
      }
    },
    async generateCandidateBoneGateMask(candidateId: string, geometry?: Record<string, unknown>) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.generateCandidateBoneGateMask(
          this.currentCase.case_id,
          candidateId,
          geometry,
        );
      } catch (error) {
        this.error = error instanceof Error ? error.message : "骨面门控生成失败";
      } finally {
        this.loading = false;
      }
    },
    async saveCandidateBoneGateMaskEdit(
      candidateId: string,
      maskPngBase64: string,
      reviewState: ReviewState,
      reviewerNotes?: string,
    ) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.saveCandidateBoneGateMaskEdit(
          this.currentCase.case_id,
          candidateId,
          maskPngBase64,
          reviewState,
          reviewerNotes,
        );
      } catch (error) {
        this.error = error instanceof Error ? error.message : "骨面 mask 修改保存失败";
      } finally {
        this.loading = false;
      }
    },
  },
});

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function stringFrom(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function recordFrom(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
