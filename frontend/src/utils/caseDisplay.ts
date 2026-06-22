import type { CaseInputAsset, CaseStatus, InputChannel, QualityFlag, ReviewState } from "@/types/case";

// 所有病例相关展示文案集中在这里，避免页面和组件各自维护一套翻译表。
export interface WarningRow {
  key: string;
  code: string;
  message: string;
  blocking: boolean;
}

const inputChannelLabels: Record<InputChannel, string> = {
  white_light: "白光",
  fluorescence: "ICG 荧光",
  sequence: "帧序列",
  video: "短视频 / 摄像头",
};

const caseStatusLabels: Record<CaseStatus, string> = {
  draft: "草稿",
  loaded: "已加载",
  analyzed: "已分析",
  reviewing: "复核中",
  reviewed: "已复核",
  exported: "已导出",
  archived: "已归档",
};

const reviewStateLabels: Record<ReviewState, string> = {
  review_required: "待复核",
  accepted: "已接受",
  modified: "已修改",
  rejected: "已驳回",
};

const riskLabels: Record<string, string> = {
  fluorescence_hotspot: "荧光高信号候选区",
};

const metricLabels: Record<string, string> = {
  mean_intensity: "平均荧光强度",
  max_intensity: "最大荧光强度",
  p95_intensity: "P95 荧光强度",
  positive_area_px: "阳性面积（阈值内）",
  positive_area_pixels: "阳性面积像素",
  positive_area_fraction: "阳性面积占比",
  positive_area_ratio: "阳性面积占比",
  threshold: "阈值",
  alpha: "融合透明度",
  colormap: "伪彩方案",
};

const colormapLabels: Record<string, string> = {
  green: "绿色",
  amber: "琥珀色",
  magenta: "品红色",
};

const runStatusLabels: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  failed: "未通过",
};

const artifactLabels: Record<string, string> = {
  overlay: "融合图",
  heatmap: "热图",
  normalized_fluorescence: "归一化荧光",
  report_json: "JSON 报告",
  report_md: "Markdown 报告",
  quantification_csv: "量化 CSV",
  evidence_bundle: "证据包",
};

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function stringFrom(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function errorMessage(error: unknown, fallback = "操作失败，请检查后端服务是否已启动。"): string {
  return error instanceof Error ? error.message : fallback;
}

export function inputChannelLabel(channel: InputChannel): string {
  return inputChannelLabels[channel] ?? channel;
}

export function caseStatusLabel(status?: CaseStatus | string): string {
  return status ? caseStatusLabels[status as CaseStatus] ?? status : "未载入";
}

export function reviewStateLabel(status: ReviewState): string {
  return reviewStateLabels[status] ?? status;
}

export function riskLabel(riskType: string): string {
  return riskLabels[riskType] ?? riskType;
}

export function metricLabel(key: string): string {
  return metricLabels[key] ?? key;
}

export function colormapLabel(value: string): string {
  return colormapLabels[value] ?? value;
}

export function runStatusLabel(status?: string): string {
  return status ? runStatusLabels[status] ?? status : "未运行";
}

export function artifactLabel(kind: string): string {
  return artifactLabels[kind] ?? kind;
}

export function numberLabel(value?: number | null, digits = 2): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "暂无";
  return value.toFixed(digits);
}

export function valueLabel(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "是" : "否";
  if (value === null || value === undefined) return "暂无";
  return JSON.stringify(value);
}

export function disclaimerVersionLabel(version?: string | null): string {
  return !version || version === "research-prototype-v1" ? "V1.0.0" : version;
}

export function compactPath(path: string, head = 24, tail = 36): string {
  return path.length <= head + tail + 3 ? path : `${path.slice(0, head)}...${path.slice(-tail)}`;
}

export function inputMetaLabel(asset: CaseInputAsset): string {
  const [width, height] = asset.dimensions;
  const resolution = width && height ? `分辨率: ${width} × ${height}` : "分辨率: 待读取";
  const acquisitionTime = isRecord(asset.metadata) ? stringFrom(asset.metadata.acquisition_time) : "";
  return acquisitionTime ? `${resolution} / 采集时间: ${acquisitionTime}` : resolution;
}

export function normalizeWarning(warning: Record<string, unknown> | QualityFlag, index: number): WarningRow {
  return {
    key: `${String(warning.code ?? "warning")}-${index}`,
    code: String(warning.code ?? "运行提示"),
    message: translateWarningMessage(String(warning.message ?? "需要医生复核的运行提示。")),
    blocking: Boolean(warning.blocking),
  };
}

function translateWarningMessage(message: string): string {
  if (message.includes("Dual-channel white-light and fluorescence inputs")) {
    return "需要同时提供白光和 ICG 荧光输入后才能进行融合分析。";
  }
  if (message.includes("Realtime browser camera preview is registered")) {
    return "浏览器摄像头实时预览已登记；当前原型尚未接入真正的流式 AI 推理。";
  }
  return message;
}
