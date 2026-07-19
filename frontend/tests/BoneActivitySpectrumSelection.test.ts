import { describe, expect, it } from "vitest";
import { boneActivitySpectrumForFrame } from "../src/utils/boneActivitySpectrum";

function spectrum(id: string): Record<string, unknown> {
  return { schema_version: "v1", evidence_id: id };
}

describe("boneActivitySpectrumForFrame", () => {
  it("binds the spectrum to the selected hotspot key across multiple keyframes", () => {
    const run = {
      fused_outputs: {
        hotspot_outputs: [
          { frame_index: 12, video_signal_segmentation: { bone_activity_spectrum: spectrum("old-frame") } },
          { frame_index: 24, video_signal_segmentation: { bone_activity_spectrum: spectrum("selected-frame") } },
        ],
      },
    };

    expect(boneActivitySpectrumForFrame(run, { key: "24-1", frameIndex: 24 })?.evidence_id).toBe("selected-frame");
  });

  it("prefers an explicit frame key and does not return the first stale frame", () => {
    const run = {
      fused_outputs: {
        frame_details: [
          { frame_key: "frame-a", frame_index: 10, signal_masks: { bone_activity_spectrum: spectrum("frame-a") } },
          { frame_key: "frame-b", frame_index: 20, signal_masks: { bone_activity_spectrum: spectrum("frame-b") } },
        ],
      },
    };

    expect(boneActivitySpectrumForFrame(run, { key: "frame-b", frameIndex: 20 })?.evidence_id).toBe("frame-b");
  });

  it("returns no spectrum when the selected frame has no bound evidence", () => {
    const run = {
      fused_outputs: {
        frame_details: [
          { frame_key: "frame-a", frame_index: 10, signal_masks: { bone_activity_spectrum: spectrum("stale") } },
          { frame_key: "frame-b", frame_index: 20, signal_masks: {} },
        ],
      },
    };

    expect(boneActivitySpectrumForFrame(run, { key: "frame-b", frameIndex: 20 })).toBeNull();
  });

  it("allows a run-level spectrum only when there is no active frame selection", () => {
    const run = { fused_outputs: { bone_activity_spectrum: spectrum("run-level") } };
    expect(boneActivitySpectrumForFrame(run, {} as { key?: string; frameIndex?: number | null })?.evidence_id).toBe("run-level");
    expect(boneActivitySpectrumForFrame(run, { key: "missing", frameIndex: 30 })).toBeNull();
  });
});
