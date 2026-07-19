import { describe, expect, it } from "vitest";

import type { CandidateRegion } from "../src/types/case";
import { candidateForHotspotFrame, candidateFrameIndexes } from "../src/utils/boneGateActions";

const candidates: CandidateRegion[] = [
  {
    candidate_id: "candidate-frame-8",
    run_id: "run-1",
    risk_type: "video_keyframe_hotspot",
    status: "review_required",
    metadata: { frame_index: 8 },
  },
  {
    candidate_id: "candidate-frame-12",
    run_id: "run-1",
    risk_type: "video_keyframe_hotspot",
    status: "review_required",
    metadata: { frame_index: "12" },
  },
];

describe("bone gate frame actions", () => {
  it("matches only the candidate belonging to the current frame", () => {
    expect(candidateForHotspotFrame(candidates, { frameIndex: 12 })?.candidate_id).toBe("candidate-frame-12");
    expect(candidateForHotspotFrame(candidates, { frameIndex: 9 })).toBeNull();
    expect(candidateForHotspotFrame(candidates, { frameIndex: null })).toBeNull();
  });

  it("exposes only finite candidate frame indexes for UI availability", () => {
    expect(
      candidateFrameIndexes([
        ...candidates,
        { ...candidates[0], candidate_id: "invalid", metadata: {} },
        { ...candidates[0], candidate_id: "null-frame", metadata: { frame_index: null } },
      ]),
    ).toEqual([8, 12]);
  });
});
