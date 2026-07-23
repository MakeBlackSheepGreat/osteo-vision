import { describe, expect, it } from "vitest";

import { apiClient } from "../src/services/apiClient";

describe("apiClient.fileDownloadUrl", () => {
  it("builds a controlled download URL for exported local artifacts", () => {
    const url = apiClient.fileDownloadUrl("C:\\artifacts\\case\\bundle.zip");

    expect(url).toContain("/files/download?");
    expect(url).toContain("bundle.zip");
  });
});
