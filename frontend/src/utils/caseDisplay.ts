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
  device_overlay: "设备叠加图",
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
  video_keyframe_hotspot: "视频关键帧高信号候选区",
  video_keyframe_model_segmentation: "视频关键帧模型分割候选区",
  boundary_risk: "荧光灌注/活性风险提示",
};

const metricLabels: Record<string, string> = {
  mean_intensity: "平均荧光强度",
  max_intensity: "最大荧光强度",
  p95_intensity: "P95 荧光强度",
  positive_area_px: "阳性面积（阈值内）",
  positive_area_pixels: "阳性面积像素",
  positive_area_fraction: "阳性面积占比",
  positive_area_ratio: "阳性面积占比",
  hotspot_frame_count: "关键帧分析数",
  hotspot_candidate_count: "关键帧候选区数",
  hotspot_max_positive_area_fraction: "最大关键帧阳性占比",
  hotspot_mean_positive_area_fraction: "平均关键帧阳性占比",
  component_count: "连通候选区数",
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
  colorbar: "荧光色标",
  roi_mask: "ROI 掩码",
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
  const parsed = parsedApiErrorMessage(error);
  if (parsed) return parsed;
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
  if (!version || version === "platform-safety-v1") return "平台安全边界 V1";
  // 旧版本兼容：读取历史病例时保留识别能力，不作为当前项目自称。
  if (version === "research-prototype-v1") return "历史 V1.0.0";
  return version;
}

export function inputMetaLabel(asset: CaseInputAsset): string {
  const [width, height] = asset.dimensions;
  const resolution = width && height ? `分辨率: ${width} × ${height}` : "分辨率: 待读取";
  const officialProfile = isRecord(asset.metadata?.official_input_profile) ? asset.metadata.official_input_profile : null;
  const officialStatus =
    officialProfile?.status === "official_profile_match"
      ? "官方规格: 匹配"
      : officialProfile?.status
        ? "官方规格: 需确认"
        : "";
  const acquisitionTime = isRecord(asset.metadata) ? stringFrom(asset.metadata.acquisition_time) : "";
  return [resolution, officialStatus, acquisitionTime ? `采集时间: ${acquisitionTime}` : ""].filter(Boolean).join(" / ");
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
    return "浏览器摄像头实时预览已登记；当前平台尚未接入流式 AI 推理。";
  }
  return message;
}

function parsedApiErrorMessage(error: unknown): string {
  if (!isRecord(error)) return "";
  const status = typeof error.status === "number" ? error.status : null;
  const body = error.body;
  const detail = isRecord(body) ? body.detail : undefined;
  const detailMessage = detailText(detail);
  const detailCode = isRecord(detail) ? stringFrom(detail.code) : "";
  if (detailMessage) return translateApiError(status, detailCode, detailMessage);
  return status ? translateStatus(status) : "";
}

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (isRecord(detail)) {
    return stringFrom(detail.message) || stringFrom(detail.reason) || stringFrom(detail.detail);
  }
  return "";
}

function translateApiError(status: number | null, code: string, message: string): string {
  if (message.includes("uploaded image content does not match the filename extension")) {
    return "上传文件内容与图片后缀不匹配，请确认选择的是 JPEG/PNG/BMP/TIFF 图像。";
  }
  if (message.includes("uploaded MP4 container signature is missing")) {
    return "上传文件不是有效 MP4 容器，请确认使用赛题设备导出的 MP4 文件。";
  }
  if (message.includes("Unsupported file type")) {
    return "当前仅支持 JPEG/PNG/BMP/TIFF 图像和 MP4 视频。";
  }
  if (message.includes("Uploaded file is too large")) {
    return "上传文件超过当前限制；图片上限 64MB，MP4 上限 1GB。";
  }
  if (message.includes("Uploaded file is empty")) {
    return "上传文件为空，请重新选择有效文件。";
  }
  if (code === "case_analysis_job_already_active" || code === "upload_keyframe_job_already_active") {
    return "该病例或视频已有后台任务正在运行，请等待完成后再重试。";
  }
  if (code === "case_analysis_job_capacity_exceeded" || code === "upload_keyframe_job_capacity_exceeded") {
    return "后台任务队列已满，请等待当前任务完成后再重试。";
  }
  if (code === "upload_content_unreadable") {
    return "上传文件无法解码或校验未通过，请确认 MP4/JPEG 文件可正常打开。";
  }
  if (code === "case_version_conflict") {
    return "病例已被其他操作更新，请重新加载病例后再提交。";
  }
  return status ? `${translateStatus(status)}：${message}` : message;
}

function translateStatus(status: number): string {
  const labels: Record<number, string> = {
    400: "请求参数无效",
    403: "文件访问被拒绝",
    404: "资源不存在",
    409: "操作冲突",
    413: "文件过大",
    415: "文件类型不支持",
    422: "文件内容无法处理",
    429: "任务过多",
    500: "后端处理失败",
  };
  return labels[status] ?? `接口请求失败，状态码 ${status}`;
}
