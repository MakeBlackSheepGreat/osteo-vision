import type { CaseInputDraft, CaseRecord, ClinicalContext, ExportResponse, L1StaticRegistrationRequest, L2PoseReplayRequest, MultichannelVideoSession, MultichannelVideoSessionCreateRequest, ReviewState, VideoCandidate, VideoCandidateList } from "@/types/case";
import type {
  AnnotationList,
  AnnotationSourceList,
  AnnotationTrainingManifestResponse,
  AnnotationVersionList,
  CreateAnnotationRequest,
  ManualAnnotation,
  UpdateAnnotationVersionRequest,
} from "@/types/annotation";
import type {
  DatasetReviewMaskRequest,
  DatasetReviewCropRequest,
  DatasetReviewQueue,
  DatasetReviewRecord,
} from "@/types/datasetReview";
import type {
  HospitalIntakeBatchList,
  HospitalIntakeBatchRequest,
  HospitalIntakeReport,
} from "@/types/hospitalIntake";
import type { ReviewIdentityStatus } from "@/types/reviewIdentity";

const API_BASE_URL = import.meta.env.VITE_OSTEO_API_URL ?? "http://127.0.0.1:8001";
let reviewAccessToken = "";

export function setReviewAccessToken(token: string): void {
  reviewAccessToken = token.trim();
}

export function clearReviewAccessToken(): void {
  reviewAccessToken = "";
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    public readonly retryAfterMs: number | null = null,
  ) {
    super(`接口请求失败，状态码 ${status}`);
    this.name = "ApiError";
  }
}

export interface UploadResponse {
  path: string;
  filename: string;
  original_filename: string;
  content_type?: string | null;
  size_bytes: number;
  sha256: string;
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

export interface LiveFrameAnalysisResult {
  frame_id: string;
  case_id: string;
  captured_at: string;
  completed_at: string;
  inference_latency_ms: number;
  model_inference_latency_ms?: number;
  model_id: string;
  model_family?: string | null;
  analysis_method?: string | null;
  source_path: string;
  overlay_path?: string | null;
  mask_path?: string | null;
  probability_path?: string | null;
  risk_mask_path?: string | null;
  uncertain_mask_path?: string | null;
  pseudo_color_path?: string | null;
  performance?: {
    total_ms?: number;
    model_ms?: number;
    decoded_width?: number;
    decoded_height?: number;
  };
  signal_masks?: Record<string, unknown>;
  quantification?: Record<string, unknown>;
  warnings?: Array<Record<string, unknown>>;
  medical_boundary: string;
}

export interface LiveFrameWarmupResult {
  model_id: string;
  model_family: string;
  available: boolean;
  warnings?: Array<Record<string, unknown>>;
  case_preparation?: Record<string, unknown> | null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(reviewAccessToken ? { Authorization: `Bearer ${reviewAccessToken}` } : {}),
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
  getReviewIdentity(): Promise<ReviewIdentityStatus> {
    return request<ReviewIdentityStatus>("/review-identity");
  },
  createCase(title: string): Promise<CaseRecord> {
    return request<CaseRecord>("/cases", {
      method: "POST",
      body: JSON.stringify({ title, disclaimer_version: "platform-safety-v1" }),
    });
  },
  ensureStandardDemoCase(): Promise<CaseRecord> {
    return request<CaseRecord>("/platform/standard-demo-case", { method: "POST" });
  },
  ensureDemoCases(): Promise<CaseRecord[]> {
    return request<CaseRecord[]>("/platform/demo-cases", { method: "POST" });
  },
  listCases(): Promise<CaseRecord[]> {
    return request<CaseRecord[]>("/cases");
  },
  getCase(caseId: string): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}`);
  },
  updateClinicalContext(caseId: string, context: ClinicalContext): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${encodeURIComponent(caseId)}/clinical-context`, {
      method: "PUT",
      body: JSON.stringify(context),
    });
  },
  listAnnotationSources(caseId: string): Promise<AnnotationSourceList> {
    return request<AnnotationSourceList>(`/cases/${encodeURIComponent(caseId)}/annotation-sources`);
  },
  listAnnotations(caseId: string): Promise<AnnotationList> {
    return request<AnnotationList | ManualAnnotation[]>(`/cases/${encodeURIComponent(caseId)}/annotations`).then((payload) =>
      Array.isArray(payload) ? { case_id: caseId, items: payload } : payload,
    );
  },
  getAnnotation(caseId: string, annotationId: string): Promise<ManualAnnotation> {
    return request<ManualAnnotation>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}`,
    );
  },
  createAnnotation(caseId: string, payload: CreateAnnotationRequest): Promise<ManualAnnotation> {
    return request<ManualAnnotation>(`/cases/${encodeURIComponent(caseId)}/annotations`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  saveAnnotationVersion(
    caseId: string,
    annotationId: string,
    payload: UpdateAnnotationVersionRequest,
  ): Promise<ManualAnnotation> {
    return request<ManualAnnotation>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}/versions`,
      { method: "PUT", body: JSON.stringify(payload) },
    );
  },
  listAnnotationVersions(caseId: string, annotationId: string): Promise<AnnotationVersionList> {
    return request<AnnotationVersionList>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}/versions`,
    );
  },
  submitAnnotation(
    caseId: string,
    annotationId: string,
    expectedVersion: number,
    notes = "",
  ): Promise<ManualAnnotation> {
    return request<ManualAnnotation>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}/submit`,
      { method: "POST", body: JSON.stringify({ expected_version: expectedVersion, notes }) },
    );
  },
  reviewAnnotation(
    caseId: string,
    annotationId: string,
    expectedVersion: number,
    decision: "accepted" | "modified" | "rejected" | "changes_requested",
    notes = "",
  ): Promise<ManualAnnotation> {
    return request<ManualAnnotation>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}/review`,
      { method: "POST", body: JSON.stringify({ expected_version: expectedVersion, decision, notes }) },
    );
  },
  deleteAnnotation(caseId: string, annotationId: string): Promise<{ deleted: boolean; annotation_id: string }> {
    return request<{ deleted: boolean; annotation_id: string }>(
      `/cases/${encodeURIComponent(caseId)}/annotations/${encodeURIComponent(annotationId)}`,
      { method: "DELETE" },
    );
  },
  createAnnotationTrainingManifest(
    caseIds: string[] = [],
    includeIneligible = false,
  ): Promise<AnnotationTrainingManifestResponse> {
    return request<AnnotationTrainingManifestResponse>("/annotation-training-manifests", {
      method: "POST",
      body: JSON.stringify({ case_ids: caseIds, include_ineligible: includeIneligible }),
    });
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
    selectedInputIds: string[] = [],
  ): Promise<CaseRecord> {
    return request<CaseRecord>(`/cases/${caseId}/analysis-runs`, {
      method: "POST",
      body: JSON.stringify({ selected_input_ids: selectedInputIds, parameters, roi_hints: roiHints }),
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
  apiAssetUrl(path: string): string {
    if (/^https?:\/\//i.test(path)) return path;
    return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  },
  startAnalysisJob(
    caseId: string,
    parameters: Record<string, unknown>,
    roiHints: Array<Record<string, unknown>> = [],
    selectedInputIds: string[] = [],
  ): Promise<BackendJob> {
    return request<BackendJob>(`/cases/${caseId}/analysis-jobs`, {
      method: "POST",
      body: JSON.stringify({ selected_input_ids: selectedInputIds, parameters, roi_hints: roiHints }),
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
  createMultichannelVideoSession(
    caseId: string,
    payload: MultichannelVideoSessionCreateRequest,
  ): Promise<MultichannelVideoSession> {
    return request<MultichannelVideoSession>(`/cases/${caseId}/multichannel-video-sessions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getMultichannelVideoSession(caseId: string, sessionId: string): Promise<MultichannelVideoSession> {
    return request<MultichannelVideoSession>(
      `/cases/${caseId}/multichannel-video-sessions/${encodeURIComponent(sessionId)}`,
    );
  },
  analyzeRealtimeMultichannelFrame(
    caseId: string,
    sessionId: string,
    payload: {
      timestamp_sec: number;
      alpha: number;
      threshold: number;
      colormap: string;
      white_frame_base64?: string;
      fluorescence_frame_base64?: string;
    },
    signal?: AbortSignal,
  ): Promise<{
    frame: {
      overlay_path: string;
      registered_fluorescence_path: string;
      performance: { registration_fusion_compute_ms: number };
    };
    compute_ms: number;
    compute_gate_passed: boolean;
  }> {
    return request(`/cases/${caseId}/multichannel-video-sessions/${encodeURIComponent(sessionId)}/realtime-frame`, {
      method: "POST",
      body: JSON.stringify(payload),
      signal,
    });
  },
  listDatasetReviewQueue(): Promise<DatasetReviewQueue> {
    return request<DatasetReviewQueue | DatasetReviewRecord[]>("/dataset-review/queue").then((payload) =>
      Array.isArray(payload) ? { items: payload } : payload,
    );
  },
  saveDatasetReviewMask(
    recordId: string,
    payload: DatasetReviewMaskRequest,
  ): Promise<DatasetReviewRecord> {
    return request<DatasetReviewRecord>(
      `/dataset-review/${encodeURIComponent(recordId)}/mask`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  generateDatasetReviewSeed(recordId: string, threshold = 0.6): Promise<DatasetReviewRecord> {
    return request<DatasetReviewRecord>(`/dataset-review/${encodeURIComponent(recordId)}/seed`, {
      method: "POST",
      body: JSON.stringify({ threshold }),
    });
  },
  saveDatasetReviewCrop(
    recordId: string,
    payload: DatasetReviewCropRequest,
  ): Promise<DatasetReviewRecord> {
    return request<DatasetReviewRecord>(`/dataset-review/${encodeURIComponent(recordId)}/crop`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async uploadRawFile(file: File, keyframeMode: "async" | "sync" | "none" = "async"): Promise<UploadResponse> {
    // 上传浏览器选择的真实文件；后端会保存到 artifacts/platform/uploads 并返回可分析路径。
    const response = await fetch(`${API_BASE_URL}/uploads/raw?keyframe_mode=${keyframeMode}`, {
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
  submitHospitalIntakeBatch(payload: HospitalIntakeBatchRequest): Promise<HospitalIntakeReport> {
    return request<HospitalIntakeReport>("/hospital-intake/batches", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listHospitalIntakeBatches(): Promise<HospitalIntakeBatchList> {
    return request<HospitalIntakeBatchList>("/hospital-intake/batches");
  },
  getHospitalIntakeBatch(batchId: string): Promise<HospitalIntakeReport> {
    return request<HospitalIntakeReport>(`/hospital-intake/batches/${encodeURIComponent(batchId)}`);
  },
  async analyzeLiveFrame(
    caseId: string,
    frame: Blob,
    options: {
      capturedAt: string;
      sequence: number;
      timestampSec?: number;
      threshold: number;
      colormap: string;
      modelId?: string;
      signal?: AbortSignal;
    },
  ): Promise<LiveFrameAnalysisResult> {
    const response = await fetch(`${API_BASE_URL}/cases/${encodeURIComponent(caseId)}/live-frames`, {
      method: "POST",
      headers: {
        "Content-Type": frame.type || "image/jpeg",
        "X-Filename": `live_frame_${String(options.sequence).padStart(6, "0")}.jpg`,
        "X-Captured-At": options.capturedAt,
        "X-Frame-Sequence": String(options.sequence),
        "X-Source-Timestamp-Sec": String(options.timestampSec ?? 0),
        "X-Hotspot-Threshold": String(options.threshold),
        "X-Colormap": options.colormap,
        ...(options.modelId ? { "X-Segmentation-Model-Id": options.modelId } : {}),
      },
      body: frame,
      signal: options.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(response.status, body, parseRetryAfterMs(response.headers.get("Retry-After")));
    }
    return response.json() as Promise<LiveFrameAnalysisResult>;
  },
  warmupLiveFrameModel(modelId?: string, caseId?: string): Promise<LiveFrameWarmupResult> {
    return request<LiveFrameWarmupResult>("/live-frames/warmup", {
      method: "POST",
      body: JSON.stringify({
        ...(modelId ? { model_id: modelId } : {}),
        ...(caseId ? { case_id: caseId } : {}),
      }),
    });
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
  getThreeDModelingExample(exampleId = "d036-toothfairy2"): Promise<Record<string, unknown>> {
    return request<Record<string, unknown>>(`/three-d/modeling-examples/${encodeURIComponent(exampleId)}`);
  },
  getThreeDModelingJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/modeling-jobs/${jobId}`);
  },
  cancelThreeDModelingJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/modeling-jobs/${jobId}/cancel`, {
      method: "POST",
    });
  },
  startL1RegistrationJob(parameters: L1StaticRegistrationRequest): Promise<BackendJob> {
    return request<BackendJob>("/three-d/registration-jobs", { method: "POST", body: JSON.stringify(parameters) });
  },
  getL1RegistrationJob(jobId: string, signal?: AbortSignal): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/registration-jobs/${encodeURIComponent(jobId)}`, { signal });
  },
  cancelL1RegistrationJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/registration-jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
  },
  startL2PoseReplayJob(parameters: L2PoseReplayRequest): Promise<BackendJob> {
    return request<BackendJob>("/three-d/pose-replay-jobs", { method: "POST", body: JSON.stringify(parameters) });
  },
  getL2PoseReplayJob(jobId: string, signal?: AbortSignal): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/pose-replay-jobs/${encodeURIComponent(jobId)}`, { signal });
  },
  cancelL2PoseReplayJob(jobId: string): Promise<BackendJob> {
    return request<BackendJob>(`/three-d/pose-replay-jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
  },
};

function parseRetryAfterMs(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value.trim());
  if (Number.isFinite(seconds) && seconds >= 0) return Math.round(seconds * 1000);
  const retryAt = Date.parse(value);
  if (!Number.isFinite(retryAt)) return null;
  return Math.max(0, retryAt - Date.now());
}
