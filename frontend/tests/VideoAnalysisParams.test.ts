import { describe, expect, it } from "vitest";

import {
  countLabel,
  hotspotFrameSelection,
  keyframeCountFromJob,
  officialProfileLabel,
  parseVideoTimepoints,
  videoFileAnalysisParameters,
} from "../src/utils/videoAnalysisParams";

describe("video analysis parameter helpers", () => {
  it("parses comma, whitespace, and Chinese separators into non-negative seconds", () => {
    expect(parseVideoTimepoints("0, 1.5  3，4；bad;-1")).toEqual([0, 1.5, 3, 4]);
  });

  it("builds MP4 analysis parameters with optional timestamps and frame indexes", () => {
    expect(
      videoFileAnalysisParameters(
        "artifacts/platform/uploads/demo.mp4",
        { alpha: 0.45, threshold: 0.6, colormap: "green" },
        { keyframeCount: 2, timestampsSec: [1.2] },
      ),
    ).toMatchObject({
      mode: "video_file",
      source_path: "artifacts/platform/uploads/demo.mp4",
      keyframe_count: 2,
      keyframe_timestamps_sec: [1.2],
      alpha: 0.45,
      threshold: 0.6,
      colormap: "green",
    });

    expect(
      videoFileAnalysisParameters(
        "artifacts/platform/uploads/demo.mp4",
        { alpha: 0.5, threshold: 0.7, colormap: "amber" },
        { keyframeCount: 1, frameIndexes: [12] },
      ),
    ).toMatchObject({ keyframe_frame_indexes: [12], colormap: "amber" });
  });

  it("selects a hotspot frame by timestamp first, then by frame index", () => {
    expect(hotspotFrameSelection({ timestampSec: 0.8, frameIndex: 8 })).toEqual({ timestampsSec: [0.8] });
    expect(hotspotFrameSelection({ timestampSec: null, frameIndex: 8 })).toEqual({ frameIndexes: [8] });
    expect(hotspotFrameSelection({ timestampSec: null, frameIndex: null })).toBeNull();
  });

  it("formats upload/job summaries for user-facing messages", () => {
    expect(keyframeCountFromJob({ keyframes: [{}, {}] })).toBe(2);
    expect(countLabel(2.4)).toBe("2");
    expect(countLabel("3")).toBe("3");
    expect(officialProfileLabel(undefined)).toBe("官方规格未读取");
    expect(
      officialProfileLabel({
        official_input_profile: {
          status: "official_profile_mismatch",
          observed_resolution: [96, 64],
          target_resolution: [3840, 2160],
        },
      }),
    ).toBe("官方规格需确认：96×64 / 目标 3840×2160");
  });
});
