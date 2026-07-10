import type { CaseInputDraft, CaseRecord, ExportResponse, ReviewState, VideoCandidate, VideoCandidateList } from "@/types/case";

const API_BASE_URL = import.meta.env.VITE_OSTEO_API_URL ?? "http://127.0.0.1:8001";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`接口请求失败，状态码 ${status}`);
  }
}

export interface UploadResponse {
  path: string;
  filename: string;
  original_filename: string;
  content_type?: string | null;
  size_bytes: number;
  input_type?: string;
  metadata?: Record<string, unknown>;
  keyframes?: Array<Record<string, unknown>>;
  keyframe_job_id?: string | null;
  keyframe_job_status?: string | null;
  warnings?: Array<Record<string, unknown>>;
}

export interface BackendJob {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed" | "canceled";
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  progress?: BackendJobProgress;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface BackendJobProgress {
  phase?: string;
  percent?: number;
  message?: string;
  details?: Record<string, unknown>;
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
      body: JSON.stringify({ title, disclaimer_version: "platform-safety-v1" }),
    });
  },
  getCase(caseId: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}`);
  },
  addInputs(caseId: string, inputs: CaseInputDraft[]): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/inputs`, {
      method: "POST",
      body: JSON.stringify(inputs),
    });
  },
  startAnalysis(
    caseId: string,
    parameters: Record<string, unknown>,
    roiHints: Array<Record<string, unknown>> = [],
  ): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/analysis-runs`, {
      method: "POST",
      body: JSON.stringify({ selected_input_ids: [], parameters, roi_hints: roiHints }),
    });
  },
  updateRegion(
    caseId: string,
    regionId: string,
    reviewState: ReviewState,
    geometry?: Record<string, unknown>,
    label?: string,
  ): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/regions/${regionId}`, {
      method: "PATCH",
      body: JSON.stringify({ review_state: reviewState, geometry, label }),
    });
  },
  addReviewEvent(caseId: string, action: string, targetId: string, afterState?: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/review-events`, {
      method: "POST",
      body: JSON.stringify({ action, target_id: targetId, after_state: afterState }),
    });
  },
  addRegionFromCandidate(caseId: string, candidateId: string): Promise<CaseRecord> {
    return request<CaseRecord>(
      `/cases/${caseId}/regions/from-candidate/${encodeURIComponent(candidateId)}`,
      { method: "POST" },
    );
  },
  updateCandidateRegion(
    caseId: string,
    candidateId: string,
    reviewState: ReviewState,
    geometry?: Record<string, unknown>,
    label?: string,
    reviewerNotes?: string,
  ): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/candidate-regions/${encodeURIComponent(candidateId)}`, {
      method: "PATCH",
      body: JSON.stringify({ review_state: reviewState, geometry, label, reviewer_notes: reviewerNotes }),
    });
  },
  generateCandidateBoneGateMask(
    caseId: string,
    candidateId: string,
    geometry?: Record<string, unknown>,
  ): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/candidate-regions/${encodeURIComponent(candidateId)}/bone-gate-mask`, {
      method: "POST",
      body: JSON.stringify({
        geometry,
        review_state: "review_required",
        label: "exposed_bone",
        prompt_source: "video_keyframe_candidate_bbox",
      }),
    });
  },
  saveCandidateBoneGateMaskEdit(
    caseId: string,
    candidateId: string,
    maskPngBase64: string,
    reviewState: ReviewState,
    reviewerNotes?: string,
  ): Promise<CaseRecord> {
    return request<CaseRecord>(
      `/cases/${caseId}/candidate-regions/${encodeURIComponent(candidateId)}/bone-gate-mask/edits`,
      {
        method: "POST",
        body: JSON.stringify({
          mask_png_base64: maskPngBase64,
          review_state: reviewState,
          label: "exposed_bone",
          reviewer_notes: reviewerNotes,
        }),
      },
    );
  },
  exportCase(caseId: string): Promise<ExportResponse> {
    return request<ExportResponse>(`/cases/${caseId}/exports`, {
      method: "POST",
      body: JSON.stringify({ export_format: "bundle", selected_artifacts: [] }),
    });
  },
  filePreviewUrl(path: string): string {
    const params = new URLSearchParams({ path });
    return `${API_BASE_URL}/files/preview?${params.toString()}`;
  },
  fileDownloadUrl(path: string): string {
    const params = new URLSearchParams({ path });
    return `${API_BASE_URL}/files/download?${params.toString()}`;
  },
  fileVideoUrl(path: string): string {
    const params = new URLSearchParams({ path });
    return `${API_BASE_URL}/files/video?${params.toString()}`;
  },
  getUploadJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/uploads/jobs/${jobId}`);
  },
  startAnalysisJob(
    caseId: string,
    parameters: Record<string, unknown>,
    roiHints: Array<Record<string, unknown>> = [],
  ): Promise<BackendJob> {
    return request<BackendJob>(`/cases/${caseId}/analysis-jobs`, {
      method: "POST",
      body: JSON.stringify({ selected_input_ids: [], parameters, roi_hints: roiHints }),
    });
  },
  getAnalysisJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/analysis-jobs/${jobId}`);
  },
  cancelAnalysisJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/analysis-jobs/${jobId}/cancel`, {
      method: "POST",
    });
  },
  listVideoCandidates(acceptedOnly = true): Promise<VideoCandidateList> {
    const params = new URLSearchParams({ accepted_only: String(acceptedOnly) });
    return request<VideoCandidateList>(`/video-library/candidates?${params.toString()}`);
  },
  importVideoCandidate(caseId: string, recordId: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/video-library/${encodeURIComponent(recordId)}/inputs`, {
      method: "POST",
    });
  },
  createVideoCandidatePreview(recordId: string): Promise<VideoCandidate> {
    return request<VideoCandidate>(`/video-library/candidates/${encodeURIComponent(recordId)}/preview`, {
      method: "POST",
    });
  },
  async uploadRawFile(file: File): Promise<UploadResponse> {
    // 上传浏览器选择的真实文件；后端会保存到 artifacts/platform/uploads 并返回可分析路径。
    const response = await fetch(`${API_BASE_URL}/uploads/raw`, {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    if (!response.ok) {
      const body = typeof response.json === "function" ? await response.json().catch(() => null) : null;
      throw new ApiError(response.status, body);
    }
    return response.json() as Promise<UploadResponse>;
  },
  uploadRawImage(file: File): Promise<UploadResponse> {
    return this.uploadRawFile(file);
  },
  async uploadThreeDAsset(file: File): Promise<UploadResponse> {
    const response = await fetch(`${API_BASE_URL}/uploads/raw?keyframe_mode=none`, {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    if (!response.ok) {
      const body = typeof response.json === "function" ? await response.json().catch(() => null) : null;
      throw new ApiError(response.status, body);
    }
    return response.json() as Promise<UploadResponse>;
  },
  startThreeDModelingJob(parameters: Record<string, unknown>): Promise<BackendJob> {
    return request<BackendJob>("/three-d/modeling-jobs", {
      method: "POST",
      body: JSON.stringify(parameters),
    });
  },
  getThreeDModelingJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/modeling-jobs/${jobId}`);
  },
  cancelThreeDModelingJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/modeling-jobs/${jobId}/cancel`, {
      method: "POST",
    });
  },
};
