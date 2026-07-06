// 后端 fused_outputs 允许扩展字段，前端先用这些小工具把 unknown 数据收敛成稳定展示值。
export function recordFrom(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function stringFrom(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

export function numberFrom(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export function finiteNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function booleanFrom(value: unknown): boolean {
  return value === true || value === "true";
}

export function bboxLabel(value: unknown): string {
  if (!Array.isArray(value) || value.length !== 4) return "";
  return value.map((item) => Math.round(numberFrom(item))).join(", ");
}

// 尺寸、位移、bbox 等医学图像元数据经常以数组形式返回，统一在这里做容错格式化。
export function arrayNumberLabel(value: unknown, suffix = ""): string {
  if (!Array.isArray(value) || !value.length) return "";
  const numbers = value
    .map((item) => finiteNumberOrNull(item))
    .filter((item): item is number => item !== null)
    .map((item) => trimNumber(item));
  if (!numbers.length) return "";
  return `${numbers.join(", ")}${suffix ? ` ${suffix}` : ""}`;
}

export function sizeResizeLabel(fusion: Record<string, unknown>): string {
  const whiteSize = arrayNumberLabel(fusion.white_light_size);
  const fluorescenceSize = arrayNumberLabel(fusion.fluorescence_original_size);
  const resized = fusion.fluorescence_resized_to_white_light === true;
  if (!whiteSize && !fluorescenceSize) return "暂无";
  const resizeLabel = resized ? "已重采样" : "原始匹配";
  return `${resizeLabel}${whiteSize ? ` · 白光 ${whiteSize}` : ""}${fluorescenceSize ? ` · 荧光 ${fluorescenceSize}` : ""}`;
}

export function methodLabel(value: string): string {
  const labels: Record<string, string> = {
    background_corrected_registered_alpha_blend_pseudocolor: "背景扣除 + 平移配准 + 伪彩融合",
  };
  return labels[value] ?? (value || "暂无");
}

export function registrationMethodLabel(value: string): string {
  const labels: Record<string, string> = {
    phase_correlation_translation: "相位相关平移",
    disabled: "已关闭",
    unsupported: "不支持",
  };
  return labels[value] ?? value;
}

export function trimNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

export function shortPath(path: string): string {
  if (!path) return "暂无";
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

export function clampUnitNumber(value: unknown): number {
  const numeric = numberFrom(value);
  return Math.max(0, Math.min(1, numeric));
}

export function formatSeconds(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}s`;
}

export function formatPercent(value: number): string {
  return `${(Math.max(0, value) * 100).toFixed(2)}%`;
}
