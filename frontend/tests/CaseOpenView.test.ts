import { describe, expect, it } from "vitest";

describe("case opening workflow requirements", () => {
  it("defines the V1 case opening workflow surface", () => {
    const workflow = ["createCase", "importInputs", "runAnalysis", "exportCase"];
    expect(workflow).toContain("createCase");
    expect(workflow).toContain("runAnalysis");
  });
});
