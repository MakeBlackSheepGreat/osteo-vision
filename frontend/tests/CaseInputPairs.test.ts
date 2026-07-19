import { describe, expect, it } from "vitest";

import type { CaseInputAsset } from "../src/types/case";
import { caseImagePairs, selectedImageInputIds } from "../src/utils/caseInputPairs";

describe("case JPEG input pairing", () => {
  it("groups complete hospital pairs by batch and pair_id", () => {
    const inputs = [
      input("white-a", "white_light", "a-white.jpg", "pair-001", "batch-a"),
      input("fluor-a", "fluorescence", "a-icg.jpg", "pair-001", "batch-a"),
      input("white-b", "white_light", "b-white.jpg", "pair-001", "batch-b"),
      input("fluor-b", "fluorescence", "b-icg.jpg", "pair-001", "batch-b"),
    ];

    const pairs = caseImagePairs(inputs);

    expect(pairs).toHaveLength(2);
    expect(pairs.map((pair) => [pair.batchId, pair.pairId])).toEqual([
      ["batch-a", "pair-001"],
      ["batch-b", "pair-001"],
    ]);
    expect(pairs[1].whiteLight.input_id).toBe("white-b");
    expect(pairs[1].fluorescence.input_id).toBe("fluor-b");
  });

  it("returns explicit input IDs only for the same admitted pair", () => {
    const inputs = [
      input("white-1", "white_light", "white-1.jpg", "pair-001", "batch-a"),
      input("fluor-1", "fluorescence", "fluor-1.jpg", "pair-001", "batch-a"),
      input("white-2", "white_light", "white-2.jpg", "pair-002", "batch-a"),
      input("fluor-2", "fluorescence", "fluor-2.jpg", "pair-002", "batch-a"),
    ];

    expect(selectedImageInputIds(inputs, "white-1.jpg", "fluor-1.jpg")).toEqual(["white-1", "fluor-1"]);
    expect(selectedImageInputIds(inputs, "white-1.jpg", "fluor-2.jpg")).toEqual([]);
  });

  it("keeps manually uploaded JPEG pairs selectable when neither input has pair metadata", () => {
    const inputs = [
      input("white-manual", "white_light", "manual-white.jpg"),
      input("fluor-manual", "fluorescence", "manual-icg.jpg"),
    ];

    expect(selectedImageInputIds(inputs, "manual-white.jpg", "manual-icg.jpg")).toEqual([
      "white-manual",
      "fluor-manual",
    ]);
  });

  it("includes an optional device overlay evidence input", () => {
    const inputs = [
      input("white", "white_light", "white.jpg", "pair-1"),
      input("fluor", "fluorescence", "fluor.jpg", "pair-1"),
      input("overlay", "device_overlay", "overlay.jpg", "pair-1"),
    ];
    expect(caseImagePairs(inputs)[0].deviceOverlay?.input_id).toBe("overlay");
    expect(selectedImageInputIds(inputs, "white.jpg", "fluor.jpg", "overlay.jpg")).toEqual([
      "white", "fluor", "overlay",
    ]);
  });
});

function input(
  inputId: string,
  channel: "white_light" | "fluorescence" | "device_overlay",
  path: string,
  pairId = "",
  batchId = "",
): CaseInputAsset {
  return {
    input_id: inputId,
    channel,
    path,
    mime_type: "image/jpeg",
    dimensions: [3840, 2160],
    metadata: pairId ? { pair_id: pairId, batch_id: batchId } : {},
    quality_flags: [],
  };
}
