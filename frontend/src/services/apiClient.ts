import type { CaseRecord, ExportResponse, InputChannel, ReviewState } from "@/types/case";

const API_BASE_URL = import.meta.env.VITE_OSTEO_API_URL ?? "http://127.0.0.1:8001";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body);
  }
  return response.json() as Promise<T>;
}

export const apiClient = {
  createCase(title: string): Promise<CaseRecord> {
    return request<CaseRecord>("/cases", {
      method: "POST",
      body: JSON.stringify({ title, disclaimer_version: "research-prototype-v1" }),
    });
  },
  getCase(caseId: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}`);
  },
  addInputs(caseId: string, inputs: Array<{ channel: InputChannel; path: string }>): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/inputs`, {
      method: "POST",
      body: JSON.stringify(inputs),
    });
  },
  startAnalysis(caseId: string, parameters: Record<string, unknown>): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/analysis-runs`, {
      method: "POST",
      body: JSON.stringify({ selected_input_ids: [], parameters, roi_hints: [] }),
    });
  },
  updateRegion(caseId: string, regionId: string, reviewState: ReviewState): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/regions/${regionId}`, {
      method: "PATCH",
      body: JSON.stringify({ review_state: reviewState }),
    });
  },
  addReviewEvent(caseId: string, action: string, targetId: string, afterState?: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/review-events`, {
      method: "POST",
      body: JSON.stringify({ action, target_id: targetId, after_state: afterState }),
    });
  },
  exportCase(caseId: string): Promise<ExportResponse> {
    return request<ExportResponse>(`/cases/${caseId}/exports`, {
      method: "POST",
      body: JSON.stringify({ export_format: "bundle", selected_artifacts: [] }),
    });
  },
};
