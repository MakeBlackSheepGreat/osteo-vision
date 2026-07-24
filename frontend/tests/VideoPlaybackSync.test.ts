import { describe, expect, it } from "vitest";

import type { HotspotFrameDetail } from "../src/components/analysisPreview";
import { nearestFrameDetailForTime } from "../src/composables/useVideoPlaybackSync";

function frame(key: string, timestampSec: number | null, displayAllowed = true): HotspotFrameDetail {
  return {
    key,
    frameIndex: 0,
    timestampSec,
    frameLabel: key,
    timestampLabel: timestampSec === null ? "--" : `${timestampSec}s`,
    candidateCountLabel: "0",
    positiveAreaLabel: "0%",
    roiAreaLabel: "0%",
    topBBoxLabel: "--",
    evidenceLabel: key,
    domainBoundary: "工程验证",
    reviewRequired: true,
    displayAllowed,
  };
}

describe("video playback keyframe lookup", () => {
  it("preserves nearest-frame selection for unsorted timestamps and midpoint ties", () => {
    const details = [frame("late", 8), frame("early", 2), frame("middle", 5)];

    expect(nearestFrameDetailForTime(details, 6.5, "")).toMatchObject({ key: "late" });
    expect(nearestFrameDetailForTime(details, 5, "")).toMatchObject({ key: "middle" });
  });

  it("preserves source ordering for equal timestamps and excludes blocked frames", () => {
    const details = [frame("first-at-4", 4), frame("blocked", 3.9, false), frame("second-at-4", 4)];

    expect(nearestFrameDetailForTime(details, 4, "")).toMatchObject({ key: "first-at-4" });
    expect(nearestFrameDetailForTime(details, 3.9, "")).toMatchObject({ key: "first-at-4" });
  });

  it("falls back to the selected displayable detail when no timestamps are available", () => {
    const details = [frame("first", null), frame("selected", null), frame("blocked", null, false)];

    expect(nearestFrameDetailForTime(details, 1, "selected")).toMatchObject({ key: "selected" });
  });
});
