import { defineStore } from "pinia";

import { apiClient, type BackendJob, type BackendJobProgress } from "../services/apiClient";
import type { CaseInputDraft, CaseRecord, ExportResponse, ReviewState } from "../types/case";

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
  }),
  actions: {
    async createCase(title: string) {
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.createCase(title);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "病例创建失败";
      } finally {
        this.loading = false;
      }
    },
    async loadCase(caseId: string) {
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.getCase(caseId);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "病例加载失败";
      } finally {
        this.loading = false;
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
    async runAnalysis(parameters: Record<string, unknown>, roiHints: Array<Record<string, unknown>> = []) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.startAnalysis(this.currentCase.case_id, parameters, roiHints);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "分析运行失败";
      } finally {
        this.loading = false;
      }
    },
    async runAnalysisJob(parameters: Record<string, unknown>, roiHints: Array<Record<string, unknown>> = []) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      this.lastAnalysisJobTimedOut = false;
      this.activeAnalysisJobError = "";
      try {
        const caseId = this.currentCase.case_id;
        const started = await apiClient.startAnalysisJob(caseId, parameters, roiHints);
        this.activeAnalysisJobId = started.job_id;
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
        if (!caseId) {
          this.error = "后台分析任务缺少病例编号，无法重试";
          return;
        }
        const retryJob = await apiClient.startAnalysisJob(caseId, parameters, roiHints as Array<Record<string, unknown>>);
        await this.pollAnalysisJob(retryJob, caseId, maxAttempts);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "后台分析任务重试失败";
      } finally {
        this.loading = false;
      }
    },
    async pollAnalysisJob(initialJob: BackendJob, caseId: string | undefined, maxAttempts: number) {
      let job = initialJob;
      this.activeAnalysisJobId = job.job_id;
      this.activeAnalysisJobStatus = job.status;
      this.activeAnalysisJobError = job.error ?? "";
      this.activeAnalysisJobProgress = job.progress ?? {};
      this.lastAnalysisJobTimedOut = false;

      for (let attempt = 0; attempt < maxAttempts && ["queued", "running"].includes(job.status); attempt += 1) {
        await sleep(1000);
        job = await apiClient.getAnalysisJob(job.job_id);
        this.activeAnalysisJobStatus = job.status;
        this.activeAnalysisJobError = job.error ?? "";
        this.activeAnalysisJobProgress = job.progress ?? {};
      }

      const resolvedCaseId = caseId || stringFrom(job.result?.case_id) || stringFrom(job.payload?.case_id);
      if (resolvedCaseId) {
        this.currentCase = await apiClient.getCase(resolvedCaseId);
      }
      if (job.status === "failed") {
        this.activeAnalysisJobError = job.error || "后台分析任务失败";
        this.error = this.activeAnalysisJobError;
      } else if (job.status === "canceled") {
        this.activeAnalysisJobError = job.error || "后台分析任务已取消";
      } else if (["queued", "running"].includes(job.status)) {
        this.lastAnalysisJobTimedOut = true;
      }
    },
    async exportCase() {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        const result = await apiClient.exportCase(this.currentCase.case_id);
        this.exportResult = result;
        this.exportPath = result.bundle_path;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "证据包导出失败";
      } finally {
        this.loading = false;
      }
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
