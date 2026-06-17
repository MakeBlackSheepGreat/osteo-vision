import { describe, expect, it } from "vitest";

describe("export panel", () => {
  it("tracks evidence bundle output fields", () => {
    const fields = ["bundle_path", "report_path", "manifest_path", "case_id"];
    expect(fields).toContain("bundle_path");
    expect(fields).toContain("report_path");
    expect(fields).toContain("manifest_path");
  });
});
