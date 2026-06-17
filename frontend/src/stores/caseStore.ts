import { defineStore } from "pinia";

import { apiClient } from "@/services/apiClient";
import type { CaseRecord } from "@/types/case";

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
        this.error = error instanceof Error ? error.message : "Failed to create case";
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
        this.error = error instanceof Error ? error.message : "Failed to load case";
      } finally {
        this.loading = false;
      }
    },
    async importInputs(inputs: Array<{ channel: "white_light" | "fluorescence"; path: string }>) {
      if (!this.currentCase) return;
      this.loading = true;
      try {
        this.currentCase = await apiClient.addInputs(this.currentCase.case_id, inputs);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Failed to add inputs";
      } finally {
        this.loading = false;
      }
    },
    async runAnalysis(parameters: Record<string, unknown>) {
      if (!this.currentCase) return;
      this.loading = true;
      try {
        this.currentCase = await apiClient.startAnalysis(this.currentCase.case_id, parameters);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Failed to analyze case";
      } finally {
        this.loading = false;
      }
    },
    async exportCase() {
      if (!this.currentCase) return;
      this.loading = true;
      try {
        const result = await apiClient.exportCase(this.currentCase.case_id);
        this.exportPath = result.bundle_path;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Failed to export case";
      } finally {
        this.loading = false;
      }
    },
    async addReviewEvent(action: string, targetId: string, afterState?: string) {
      if (!this.currentCase) return;
      this.loading = true;
      try {
        this.currentCase = await apiClient.addReviewEvent(this.currentCase.case_id, action, targetId, afterState);
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Failed to record review event";
      } finally {
        this.loading = false;
      }
    },
  },
});
