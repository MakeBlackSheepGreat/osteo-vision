import { describe, expect, it } from "vitest";

describe("medical disclaimer wording", () => {
  it("keeps physician review boundary visible", () => {
    const text = "Research prototype only. Outputs are for physician review.";
    expect(text).toContain("Research prototype only");
    expect(text).toContain("physician review");
  });
});
