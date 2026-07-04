import { describe, expect, it } from "vitest";

import { apiClient } from "../src/services/apiClient";

describe("export panel", () => {
  it("tracks evidence bundle output fields", () => {
    const fields = ["bundle_path", "report_path", "manifest_path", "case_id", "dicom_path", "summary", "artifact_entries"];
    expect(fields).toContain("bundle_path");
    expect(fields).toContain("report_path");
    expect(fields).toContain("manifest_path");
    expect(fields).toContain("dicom_path");
    expect(fields).toContain("summary");
    expect(fields).toContain("artifact_entries");
  });

  it("builds download URLs for exported local artifacts", () => {
    const url = apiClient.fileDownloadUrl("C:\\artifacts\\case\\bundle.zip");
    expect(url).toContain("/files/download?");
    expect(url).toContain("bundle.zip");
  });
});
