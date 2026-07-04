import type { VideoCandidate } from "@/types/case";

export interface VideoCandidateDetail {
  label: string;
  value: string;
}

export type VideoCandidateFluorescenceFilter = "all" | "fluorescence" | "non_fluorescence" | "unknown";
export type VideoCandidateTrainingFilter =
  | "all"
  | "enhancement_or_self_supervised"
  | "demo_or_self_supervised"
  | "documentation"
  | "unknown";

export interface VideoCandidateFilters {
  fluorescence: VideoCandidateFluorescenceFilter;
  training: VideoCandidateTrainingFilter;
}

export const videoCandidateFluorescenceFilterOptions: Array<{
  value: VideoCandidateFluorescenceFilter;
  label: string;
}> = [
  { value: "all", label: "全部通道" },
  { value: "fluorescence", label: "荧光" },
  { value: "non_fluorescence", label: "非荧光" },
  { value: "unknown", label: "未知通道" },
];

export const videoCandidateTrainingFilterOptions: Array<{
  value: VideoCandidateTrainingFilter;
  label: string;
}> = [
  { value: "all", label: "全部用途" },
  { value: "enhancement_or_self_supervised", label: "增强/自监督" },
  { value: "demo_or_self_supervised", label: "演示/自监督" },
  { value: "documentation", label: "文档资料" },
  { value: "unknown", label: "未标注" },
];

export function findVideoCandidate(candidates: VideoCandidate[], recordId: string): VideoCandidate | null {
  return candidates.find((candidate) => candidate.record_id === recordId) ?? null;
}

export function videoCandidateFluorescenceLabel(candidate: VideoCandidate): string {
  if (candidate.fluorescence === true) return "荧光";
  if (candidate.fluorescence === false) return "非荧光";
  return "未知通道";
}

export function videoCandidateReadableLabel(candidate: VideoCandidate): string {
  if (candidate.exists && candidate.system_readable) return "本地可读";
  if (candidate.exists) return "本地存在但不可读";
  return "未落地";
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) return "未知";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const precision = unitIndex <= 1 ? 0 : 1;
  return `${size.toFixed(precision)} ${units[unitIndex]}`;
}

export function videoCandidateSourceUrl(candidate: VideoCandidate): string {
  return candidate.source_page_original_link || candidate.direct_download_link || "";
}

export function videoCandidateTrainingBucket(candidate: VideoCandidate): VideoCandidateTrainingFilter {
  const normalized = candidate.usable_for_training.trim().toLowerCase();
  if (!normalized) return "unknown";
  if (normalized === "documentation") return "documentation";
  if (normalized.includes("enhancement")) return "enhancement_or_self_supervised";
  if (normalized.includes("demo") || normalized.includes("no_labels")) return "demo_or_self_supervised";
  return "unknown";
}

export function filterVideoCandidates(
  candidates: VideoCandidate[],
  filters: VideoCandidateFilters,
): VideoCandidate[] {
  return candidates.filter((candidate) => {
    if (filters.fluorescence === "fluorescence" && candidate.fluorescence !== true) return false;
    if (filters.fluorescence === "non_fluorescence" && candidate.fluorescence !== false) return false;
    if (filters.fluorescence === "unknown" && candidate.fluorescence !== null) return false;
    if (filters.training !== "all" && videoCandidateTrainingBucket(candidate) !== filters.training) return false;
    return true;
  });
}

export function videoCandidateFilterSummary(totalCount: number, filteredCount: number): string {
  if (totalCount <= 0) return "0 条";
  if (filteredCount === totalCount) return `${totalCount} 条`;
  return `${filteredCount} / ${totalCount} 条`;
}

export function videoCandidateDetails(candidate: VideoCandidate): VideoCandidateDetail[] {
  return [
    { label: "医学场景", value: candidate.medical_scene || "未标注" },
    { label: "训练可用性", value: candidate.usable_for_training || "未标注" },
    { label: "视频规格", value: videoCandidateGeometryLabel(candidate) },
    { label: "预览状态", value: videoCandidatePreviewLabel(candidate) },
    { label: "文件大小", value: formatBytes(candidate.size_bytes) },
    { label: "读取状态", value: videoCandidateReadableLabel(candidate) },
    { label: "数据边界", value: candidate.domain_boundary || "非目标域候选，需人工核验" },
  ];
}

export function videoCandidatePreviewLabel(candidate: VideoCandidate): string {
  const status = candidate.preview_status || "not_requested";
  if (status === "generated" || status === "cached") return "已生成";
  if (status === "failed") return candidate.preview_error || "生成失败";
  if (status === "unsupported_or_missing") return "不可预览";
  return "未生成";
}

export function videoCandidateGeometryLabel(candidate: VideoCandidate): string {
  const size = candidate.width && candidate.height ? `${candidate.width} × ${candidate.height}` : "分辨率未知";
  const duration =
    typeof candidate.duration_sec === "number" && Number.isFinite(candidate.duration_sec)
      ? `${candidate.duration_sec.toFixed(1)} 秒`
      : "时长未知";
  return `${size} / ${duration}`;
}
