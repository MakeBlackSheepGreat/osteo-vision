interface FrameSelection { key?: string | null; frameIndex?: number | null }
function record(value: unknown): Record<string, unknown> | null { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; }
function numeric(value: unknown): number | null { if (typeof value === "number" && Number.isFinite(value)) return value; if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value); return null; }
function qualityWithin(value: unknown): Record<string, unknown> | null { const node = record(value); if (!node) return null; const direct = record(node.three_channel_quality); if (direct) return direct; for (const key of ["outputs", "video_signal_segmentation", "signal_masks"]) { const found = qualityWithin(node[key]); if (found) return found; } return null; }
function matches(frame: Record<string, unknown>, index: number, selection: FrameSelection): boolean { const frameIndex = numeric(frame.frame_index) ?? numeric(frame.frame_order); const selectedKey = selection.key?.trim() || ""; if (selectedKey && [frame.frame_key, frame.candidate_id, `${frameIndex ?? index + 1}-${index}`].includes(selectedKey)) return true; return selection.frameIndex != null && frameIndex === selection.frameIndex; }
/** Select active-frame QC and never borrow evidence from another video frame. */
export function threeChannelQualityForFrame(runValue: unknown, selection: FrameSelection): Record<string, unknown> | null {
  const run = record(runValue); if (!run) return null; const fused = record(run.fused_outputs) ?? run;
  const selected = Boolean(selection.key?.trim()) || selection.frameIndex != null;
  if (selected) { for (const key of ["frame_details", "hotspot_outputs", "frames", "keyframes"]) { const values = fused[key]; if (!Array.isArray(values)) continue; const match = values.map(record).find((frame, index) => Boolean(frame && matches(frame, index, selection))); if (match) return qualityWithin(match); } if (typeof fused.mode === "string" && fused.mode.includes("video")) return null; }
  return qualityWithin(fused) ?? qualityWithin(run);
}
