import { defineStore } from "pinia";

import { apiClient } from "@/services/apiClient";
import type { CaseInputDraft, CaseRecord } from "@/types/case";

export const useCaseStore = defineStore("case", {
  state: () => ({
    currentCase: null as CaseRecord | null,
    loading: false,
    error: "",
    exportPath: "",
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
    async runAnalysis(parameters: Record<string, unknown>) {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        this.currentCase = await apiClient.startAnalysis(this.currentCase.case_id, parameters);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "分析运行失败";
      } finally {
        this.loading = false;
      }
    },
    async exportCase() {
      if (!this.currentCase) return;
      this.loading = true;
      this.error = "";
      try {
        const result = await apiClient.exportCase(this.currentCase.case_id);
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
  },
});
