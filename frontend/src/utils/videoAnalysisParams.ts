export type PlatformColormap = "green" | "amber" | "magenta";

export interface FluorescenceControls {
  alpha: number;
  threshold: number;
  colormap: PlatformColormap;
}

export interface HotspotFrameSelector {
  timestampSec: number | null;
  frameIndex: number | null;
}

export function parseVideoTimepoints(value: string): number[] {
  return value
    .split(/[,\s，；;]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item >= 0);
}

export function videoFileAnalysisParameters(
  sourcePath: string,
  controls: FluorescenceControls,
  options: { keyframeCount: number; timestampsSec?: number[]; frameIndexes?: number[] },
): Record<string, unknown> {
  // 前端只负责声明“分析哪段视频/哪些帧”；真正抽帧、分割和叠加仍由后端统一执行。
  return {
    mode: "video_file",
    source_path: sourcePath,
    keyframe_count: options.keyframeCount,
    ...(options.timestampsSec?.length ? { keyframe_timestamps_sec: options.timestampsSec } : {}),
    ...(options.frameIndexes?.length ? { keyframe_frame_indexes: options.frameIndexes } : {}),
    alpha: controls.alpha,
    threshold: controls.threshold,
    colormap: controls.colormap,
  };
}

export function hotspotFrameSelection(detail: HotspotFrameSelector): {
  timestampsSec?: number[];
  frameIndexes?: number[];
} | null {
  if (typeof detail.timestampSec === "number" && Number.isFinite(detail.timestampSec)) {
    return { timestampsSec: [detail.timestampSec] };
  }
  if (typeof detail.frameIndex === "number" && Number.isFinite(detail.frameIndex)) {
    return { frameIndexes: [detail.frameIndex] };
  }
  return null;
}

export function keyframeCountFromJob(result: Record<string, unknown> | undefined): number {
  const keyframes = result?.keyframes;
  return Array.isArray(keyframes) ? keyframes.length : 0;
}

export function countLabel(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(Math.max(0, Math.round(value)));
  if (typeof value === "string" && value.trim()) return value.trim();
  return "0";
}

export function officialProfileLabel(metadata: Record<string, unknown> | undefined): string {
  const profile = recordFrom(metadata?.official_input_profile);
  if (!profile) return "官方规格未读取";
  if (profile.status === "official_profile_match") return "官方规格匹配";
  const observed = Array.isArray(profile.observed_resolution) ? profile.observed_resolution.join("×") : "";
  const target = Array.isArray(profile.target_resolution) ? profile.target_resolution.join("×") : "3840×2160";
  return observed ? `官方规格需确认：${observed} / 目标 ${target}` : "官方规格需确认";
}

function recordFrom(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}
