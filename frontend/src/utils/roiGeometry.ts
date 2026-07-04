export interface RoiPoint {
  x: number;
  y: number;
}

export interface RoiRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RoiGeometryPayload extends RoiRect {
  type: "rect";
  coordinate_space: "normalized";
}

export type RoiResizeHandle = "n" | "s" | "e" | "w" | "nw" | "ne" | "sw" | "se";

export function clampUnit(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function rectFromPoints(start: RoiPoint, end: RoiPoint): RoiRect {
  const left = clampUnit(Math.min(start.x, end.x));
  const top = clampUnit(Math.min(start.y, end.y));
  const right = clampUnit(Math.max(start.x, end.x));
  const bottom = clampUnit(Math.max(start.y, end.y));
  return {
    x: roundUnit(left),
    y: roundUnit(top),
    width: roundUnit(right - left),
    height: roundUnit(bottom - top),
  };
}

export function roiGeometryPayload(rect: RoiRect): RoiGeometryPayload {
  const normalized = normalizeRect(rect);
  return {
    type: "rect",
    coordinate_space: "normalized",
    x: normalized.x,
    y: normalized.y,
    width: normalized.width,
    height: normalized.height,
  };
}

export function normalizeRect(rect: RoiRect): RoiRect {
  const rawLeft = Math.min(rect.x, rect.x + rect.width);
  const rawTop = Math.min(rect.y, rect.y + rect.height);
  const rawWidth = Math.abs(rect.width);
  const rawHeight = Math.abs(rect.height);
  const width = clampUnit(rawWidth);
  const height = clampUnit(rawHeight);
  const left = Math.max(0, Math.min(Math.max(0, 1 - width), clampUnit(rawLeft)));
  const top = Math.max(0, Math.min(Math.max(0, 1 - height), clampUnit(rawTop)));
  return {
    x: roundUnit(left),
    y: roundUnit(top),
    width: roundUnit(width),
    height: roundUnit(height),
  };
}

export function translateRect(rect: RoiRect, delta: RoiPoint): RoiRect {
  const normalized = normalizeRect(rect);
  const maxX = Math.max(0, 1 - normalized.width);
  const maxY = Math.max(0, 1 - normalized.height);
  return {
    x: roundUnit(Math.max(0, Math.min(maxX, normalized.x + delta.x))),
    y: roundUnit(Math.max(0, Math.min(maxY, normalized.y + delta.y))),
    width: normalized.width,
    height: normalized.height,
  };
}

export function resizeRectFromHandle(rect: RoiRect, handle: RoiResizeHandle, point: RoiPoint): RoiRect {
  const normalized = normalizeRect(rect);
  let left = normalized.x;
  let top = normalized.y;
  let right = normalized.x + normalized.width;
  let bottom = normalized.y + normalized.height;
  if (handle.includes("w")) left = clampUnit(point.x);
  if (handle.includes("e")) right = clampUnit(point.x);
  if (handle.includes("n")) top = clampUnit(point.y);
  if (handle.includes("s")) bottom = clampUnit(point.y);
  return rectFromPoints({ x: left, y: top }, { x: right, y: bottom });
}

export function roiAreaFraction(rect: RoiRect): number {
  return roundUnit(clampUnit(rect.width) * clampUnit(rect.height));
}

export function roiRectFromGeometry(geometry: Record<string, unknown> | undefined): RoiRect | null {
  if (!geometry || geometry.type !== "rect") return null;
  return normalizeRect({
    x: Number(geometry.x),
    y: Number(geometry.y),
    width: Number(geometry.width),
    height: Number(geometry.height),
  });
}

function roundUnit(value: number): number {
  return Number(value.toFixed(4));
}
