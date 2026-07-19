import type { HotspotFrameDetail } from "@/components/analysisPreview";
import type { CandidateRegion } from "@/types/case";

export function candidateForHotspotFrame(
  candidates: CandidateRegion[],
  detail: Pick<HotspotFrameDetail, "frameIndex">,
): CandidateRegion | null {
  if (detail.frameIndex === null || !Number.isFinite(detail.frameIndex)) return null;
  return (
    candidates.find((candidate) => {
      const candidateFrameIndex = finiteFrameIndex(candidate.metadata?.frame_index);
      return candidateFrameIndex !== null && candidateFrameIndex === detail.frameIndex;
    }) ?? null
  );
}

export function candidateFrameIndexes(candidates: CandidateRegion[]): number[] {
  const indexes = new Set<number>();
  for (const candidate of candidates) {
    const frameIndex = finiteFrameIndex(candidate.metadata?.frame_index);
    if (frameIndex !== null) indexes.add(frameIndex);
  }
  return [...indexes];
}

function finiteFrameIndex(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
