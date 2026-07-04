import { describe, expect, it } from "vitest";

import {
  resizeRectFromHandle,
  rectFromPoints,
  roiAreaFraction,
  roiGeometryPayload,
  roiRectFromGeometry,
  translateRect,
} from "../src/utils/roiGeometry";

describe("roi geometry", () => {
  it("normalizes drag points into a stable rectangular ROI payload", () => {
    const rect = rectFromPoints({ x: 0.8, y: 0.7 }, { x: 0.2, y: 0.25 });
    const payload = roiGeometryPayload(rect);

    expect(payload).toEqual({
      type: "rect",
      coordinate_space: "normalized",
      x: 0.2,
      y: 0.25,
      width: 0.6,
      height: 0.45,
    });
    expect(roiAreaFraction(rect)).toBe(0.27);
  });

  it("reads persisted ROI geometry for review overlays", () => {
    const rect = roiRectFromGeometry({ type: "rect", x: 1.2, y: -0.2, width: 0.5, height: 0.4 });

    expect(rect).toEqual({ x: 0.5, y: 0, width: 0.5, height: 0.4 });
    expect(roiRectFromGeometry({ type: "polygon", points: [] })).toBeNull();
  });

  it("keeps moved and resized ROI boxes inside normalized bounds", () => {
    expect(translateRect({ x: 0.8, y: 0.8, width: 0.3, height: 0.25 }, { x: 0.2, y: 0.2 })).toEqual({
      x: 0.7,
      y: 0.75,
      width: 0.3,
      height: 0.25,
    });

    expect(resizeRectFromHandle({ x: 0.2, y: 0.25, width: 0.4, height: 0.35 }, "se", { x: 1.2, y: -0.2 })).toEqual({
      x: 0.2,
      y: 0,
      width: 0.8,
      height: 0.25,
    });
  });
});
